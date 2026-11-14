//! An MCP server on `POST /mcp` (#263): the Model Context Protocol over
//! Streamable HTTP, stateless, every answer one JSON body (no SSE stream,
//! no session). Clients such as Claude Code query FRANK through it.
//!
//! Each tool calls the `/v1` handler it wraps with the request's own
//! headers, so the caller, its status and every disclosure rule (ADR-002:
//! suppressed cells, TLP) are those of the `/v1` route; nothing here
//! decides what a caller may see. All tools only read.
//!
//! The caller is named before the message is read, as on `/v1`: an unknown
//! token is HTTP 401 for every method. A status too low for a tool is a
//! tool result with `isError`, so the model can read why.

use std::collections::BTreeMap;

use axum::extract::{Path, Query, State};
use axum::http::{HeaderMap, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::post;
use axum::{Json, Router};
use frank_core::Tier;
use serde::de::DeserializeOwned;
use serde::Deserialize;
use serde_json::{json, Map, Value};

use crate::api::{self, require, ApiError, Shared};

/// Protocol versions this server speaks, newest first.
const VERSIONS: [&str; 3] = ["2025-11-25", "2025-06-18", "2025-03-26"];

const PARSE_ERROR: i64 = -32700;
const INVALID_REQUEST: i64 = -32600;
const METHOD_NOT_FOUND: i64 = -32601;
const INVALID_PARAMS: i64 = -32602;

pub fn routes() -> Router<Shared> {
    Router::new().route("/mcp", post(mcp))
}

async fn mcp(State(app): State<Shared>, headers: HeaderMap, body: String) -> Response {
    let caller = match require(&app, &headers, Tier::Public) {
        Ok(c) => c,
        Err(e) => return e.into_response(),
    };
    let Ok(msg) = serde_json::from_str::<Value>(&body) else {
        return reply(&Value::Null, Err((PARSE_ERROR, "not JSON".into())));
    };
    // A batch (an array) was dropped from MCP in 2025-06-18.
    let Some(msg) = msg.as_object().filter(|m| m["jsonrpc"] == "2.0") else {
        return reply(
            &Value::Null,
            Err((INVALID_REQUEST, "one JSON-RPC 2.0 object".into())),
        );
    };
    let (id, method) = (msg.get("id"), msg.get("method").and_then(Value::as_str));
    let (id, method) = match (id, method) {
        // A notification, or a response to a request (this server sends
        // none): accepted, nothing to answer.
        (None, Some(_)) => return StatusCode::ACCEPTED.into_response(),
        (Some(_), None) if msg.contains_key("result") || msg.contains_key("error") => {
            return StatusCode::ACCEPTED.into_response();
        }
        (Some(id), Some(m)) => (id, m),
        _ => return reply(&Value::Null, Err((INVALID_REQUEST, "no method".into()))),
    };
    let params = msg.get("params").cloned().unwrap_or(json!({}));
    let result = match method {
        "initialize" => Ok(initialize(&params)),
        "ping" => Ok(json!({})),
        "tools/list" => Ok(json!({ "tools": tools() })),
        "tools/call" => {
            let name = params["name"].as_str().unwrap_or_default().to_string();
            let args = params.get("arguments").cloned().unwrap_or(json!({}));
            let r = call(app.clone(), headers, &name, args).await;
            let ok = matches!(r, Ok(Ok(_)));
            if r.is_ok() {
                if let Err(e) = app.audit.record(
                    (app.now)(),
                    &caller.label(),
                    "mcp_call",
                    json!({ "tool": name, "ok": ok }),
                ) {
                    tracing::error!("audit mcp_call: {e}");
                }
            }
            r.map(tool_result)
        }
        other => Err((METHOD_NOT_FOUND, format!("unknown method {other:?}"))),
    };
    reply(id, result)
}

fn reply(id: &Value, result: Result<Value, (i64, String)>) -> Response {
    let body = match result {
        Ok(r) => json!({ "jsonrpc": "2.0", "id": id, "result": r }),
        Err((code, message)) => {
            json!({ "jsonrpc": "2.0", "id": id, "error": { "code": code, "message": message } })
        }
    };
    Json(body).into_response()
}

fn initialize(params: &Value) -> Value {
    let asked = params["protocolVersion"].as_str().unwrap_or_default();
    let version = VERSIONS
        .into_iter()
        .find(|v| *v == asked)
        .unwrap_or(VERSIONS[0]);
    json!({
        "protocolVersion": version,
        "capabilities": { "tools": { "listChanged": false } },
        "serverInfo": { "name": "frank", "version": env!("CARGO_PKG_VERSION") },
        "instructions": "FRANK holds sighting statistics of SIGMA rules and IoCs shared by known \
            participants. What a tool returns depends on the caller's status (public, observer, \
            contributor, partner, core): below partner, cells of fewer than 3 reporters are \
            suppressed. Call whoami first to learn the status.",
    })
}

/// A handler's answer as a tool result: the JSON as text and as structured
/// content, or the refusal as text with `isError`.
fn tool_result(r: Result<Json<Value>, ApiError>) -> Value {
    match r {
        Ok(Json(v)) => json!({
            "content": [{ "type": "text", "text": v.to_string() }],
            "structuredContent": v,
            "isError": false,
        }),
        Err(ApiError(status, message)) => json!({
            "content": [{ "type": "text", "text": format!("{}: {message}", status.as_u16()) }],
            "isError": true,
        }),
    }
}

#[derive(Deserialize)]
struct Id {
    id: String,
}

/// The arguments as `T`, or a JSON-RPC "invalid params".
fn args<T: DeserializeOwned>(args: &Value) -> Result<T, (i64, String)> {
    serde_json::from_value(args.clone()).map_err(|e| (INVALID_PARAMS, format!("arguments: {e}")))
}

/// The arguments as query parameters, for the routes that take any of
/// several (Explore's dimensions, the sightings list's filters).
fn params(args: &Value) -> Result<BTreeMap<String, String>, (i64, String)> {
    let empty = Map::new();
    let obj = match args {
        Value::Null => &empty,
        Value::Object(o) => o,
        _ => return Err((INVALID_PARAMS, "arguments: an object".into())),
    };
    obj.iter()
        .map(|(k, v)| match v {
            Value::String(s) => Ok((k.clone(), s.clone())),
            Value::Number(_) | Value::Bool(_) => Ok((k.clone(), v.to_string())),
            _ => Err((INVALID_PARAMS, format!("arguments: {k} is not a value"))),
        })
        .collect()
}

/// Runs the tool `name`: the `/v1` handler's answer, or a JSON-RPC error
/// for an unknown tool or arguments of the wrong shape.
async fn call(
    app: Shared,
    headers: HeaderMap,
    name: &str,
    a: Value,
) -> Result<Result<Json<Value>, ApiError>, (i64, String)> {
    let s = State(app);
    Ok(match name {
        "whoami" => api::whoami(s, headers).await,
        "explore" => api::explore(s, headers, Query(params(&a)?)).await,
        "list_sightings" => api::list(s, headers, Query(params(&a)?)).await,
        "rule_detail" | "get_sighting" => call_by_id(s, headers, name, &a).await?,
        _ => call_with_args(s, headers, name, &a).await?,
    })
}

/// [`call`] for the tools on one record named by an `id` argument.
async fn call_by_id(
    s: State<Shared>,
    headers: HeaderMap,
    name: &str,
    a: &Value,
) -> Result<Result<Json<Value>, ApiError>, (i64, String)> {
    let Id { id } = args(a)?;
    Ok(match name {
        "rule_detail" => api::rule_detail(s, headers, Path(id), Query(args(a)?)).await,
        _ => api::sighting(s, headers, Path(id)).await,
    })
}

/// [`call`] for the tools whose arguments are one typed query, and the
/// error for an unknown tool.
async fn call_with_args(
    s: State<Shared>,
    headers: HeaderMap,
    name: &str,
    a: &Value,
) -> Result<Result<Json<Value>, ApiError>, (i64, String)> {
    Ok(match name {
        "statistics" => api::statistics(s, headers, Query(args(a)?)).await,
        "summary" => api::summary(s, headers, Query(args(a)?)).await,
        "lookup_ioc" => api::ioc_lookup(s, headers, Query(args(a)?)).await,
        "ioc_range" => api::ioc_range(s, headers, Query(args(a)?)).await,
        other => return Err((INVALID_PARAMS, format!("unknown tool {other:?}"))),
    })
}

/// The tools, each with the JSON Schema of its arguments.
fn tools() -> Value {
    let days = json!({ "type": "integer", "minimum": 1, "maximum": 3650,
        "description": "Days back from now; 30 by default." });
    let filters = "Filters, one value each: rule, ioc (type:value), campaign, technique, \
        sector, ioc_type, severity.";
    let tool = |name: &str, title: &str, description: &str, schema: Value| {
        json!({
            "name": name,
            "title": title,
            "description": description,
            "inputSchema": schema,
            "annotations": { "readOnlyHint": true, "openWorldHint": false },
        })
    };
    let str_props = |names: &[&str]| -> Map<String, Value> {
        names
            .iter()
            .map(|n| ((*n).to_string(), json!({ "type": "string" })))
            .collect()
    };
    let mut explore = str_props(&[
        "rule",
        "ioc",
        "campaign",
        "technique",
        "sector",
        "ioc_type",
        "severity",
    ]);
    explore.insert(
        "group".into(),
        json!({ "type": "string", "enum": ["rule", "ioc", "campaign", "technique", "sector", "ioc_type", "severity"] }),
    );
    explore.insert("days".into(), days.clone());
    explore.insert(
        "common".into(),
        json!({ "type": "string", "enum": ["include", "exclude"],
            "description": "With group=ioc: keep IoCs a warning list marks as common infrastructure." }),
    );
    explore.insert(
        "listed".into(),
        json!({ "type": "string",
            "description": "With group=ioc: any, none or a reference list's name." }),
    );
    let mut list = str_props(&[
        "rule",
        "ioc",
        "campaign",
        "technique",
        "sector",
        "ioc_type",
        "severity",
    ]);
    for (k, v) in [
        (
            "since",
            json!({ "type": "string", "description": "RFC 3339; 30 days ago by default." }),
        ),
        (
            "until",
            json!({ "type": "string", "description": "RFC 3339." }),
        ),
        (
            "order",
            json!({ "type": "string", "enum": ["asc", "desc"] }),
        ),
        (
            "mine",
            json!({ "type": "boolean", "description": "Only the caller's own sightings." }),
        ),
        (
            "cursor",
            json!({ "type": "string", "description": "The next_cursor of the previous page." }),
        ),
        (
            "limit",
            json!({ "type": "integer", "minimum": 1, "maximum": 500 }),
        ),
    ] {
        list.insert(k.into(), v);
    }
    json!([
        tool("whoami", "Who am I",
            "The caller's status (public, observer, contributor, partner, core), user and organisation.",
            json!({ "type": "object", "properties": {} })),
        tool("statistics", "Statistics",
            "Totals of the sightings over the last days; breakdowns by sector, IoC type and severity \
             from observer, by rule and technique from contributor.",
            json!({ "type": "object", "properties": { "days": days } })),
        tool("summary", "Summary",
            "A summary of the sightings over the last days. Contributor and up.",
            json!({ "type": "object", "properties": { "days": days } })),
        tool("lookup_ioc", "Look up an IoC",
            "How often, where and when one IoC was seen. Contributor and up.",
            json!({ "type": "object", "required": ["type", "value"], "properties": {
                "type": { "type": "string", "description": "The IoC type, e.g. ipv4-addr, domain-name, url, file:hashes.SHA-256." },
                "value": { "type": "string" },
                "day": { "type": "string", "description": "Limit to one day, YYYY-MM-DD." } } })),
        tool("ioc_range", "IoCs in an address range",
            "The IP addresses seen inside a CIDR block. Contributor and up.",
            json!({ "type": "object", "required": ["cidr"], "properties": {
                "cidr": { "type": "string", "description": "e.g. 192.0.2.0/24 or 2001:db8::/48." } } })),
        tool("explore", "Explore",
            &format!("Sightings grouped by one dimension, optionally filtered. Grouping or \
             filtering by sector, ioc_type or severity needs observer; by rule, ioc, campaign \
             or technique, contributor. {filters}"),
            json!({ "type": "object", "required": ["group"], "properties": explore })),
        tool("rule_detail", "A rule's prevalence",
            "One SIGMA rule's prevalence over the last days. Contributor and up.",
            json!({ "type": "object", "required": ["id"], "properties": {
                "id": { "type": "string", "description": "The rule id." }, "days": days } })),
        tool("list_sightings", "List sightings",
            &format!("The records of the visible sightings, a page at a time. Contributor and up. {filters}"),
            json!({ "type": "object", "properties": list })),
        tool("get_sighting", "One sighting",
            "One sighting's records by its sighting_id. Contributor and up.",
            json!({ "type": "object", "required": ["id"], "properties": {
                "id": { "type": "string", "description": "The sighting_id (a UUID)." } } })),
    ])
}
