# MCP Server Specification

**Domain:** HTTP API / AI clients
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-11-11

**Owner:** Platform Team
- **Related ADR:** [ADR-002](../../architecture/decisions/002-tiered-access-control.md), [ADR-020](../../architecture/decisions/020-sso-with-openid-connect.md)
- **Issues:** #263; OAuth for a Claude.ai connector: #264
**Implementation:** `crates/frank/src/mcp.rs`
**Tests:** `crates/frank/tests/api.rs`

## Overview

FRANK answers the Model Context Protocol (MCP) on `POST /mcp`, so that an AI client such as Claude Code can query it. The transport is MCP's Streamable HTTP in its stateless form: one JSON-RPC message per request, one JSON body per answer, no SSE stream and no session. The tools are the read-only `/v1` queries; each calls its `/v1` route's handler with the request's own credentials.

### Philosophy

- **One gate**: who the caller is and what it may see is decided by the `/v1` handler a tool wraps, never by the MCP code.
- **Read only**: no tool submits, changes or downloads.
- **Same credentials**: a bearer token, or the SSO session cookie without one (ADR-020).

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## Requirements

### Requirement 1: The protocol [MUST]

`POST /mcp` MUST take one JSON-RPC 2.0 object and answer `initialize`, `ping`, `tools/list` and `tools/call` with one JSON body. `initialize` MUST answer the protocol version the client asks for when it is one FRANK speaks (`2025-11-25`, `2025-06-18`, `2025-03-26`), otherwise the newest. A notification (no `id`) MUST get 202 and no body. `GET /mcp` MUST get 405: there is no SSE stream.

**Implementation:** `crates/frank/src/mcp.rs::mcp`, `crates/frank/src/mcp.rs::initialize`

#### Scenario: Handshake

- GIVEN any caller
- WHEN it sends `initialize` with `2025-06-18`, then `notifications/initialized`
- THEN the answer names `2025-06-18`, the server `frank` and the `tools` capability, and the notification gets 202

**Tests:** `crates/frank/tests/api.rs::mcp_initialises_and_lists_its_tools`

### Requirement 2: The tools [MUST]

`tools/list` MUST list `whoami`, `statistics`, `summary`, `lookup_ioc`, `ioc_range`, `explore`, `rule_detail`, `list_sightings` and `get_sighting`, each with a description, a JSON Schema of its arguments and `readOnlyHint`. Each tool MUST answer as the `/v1` route it wraps answers the same caller: the route's body as `structuredContent` and as text, or, when the route refuses (403, 422), a result with `isError` and the status and message as text.

**Implementation:** `crates/frank/src/mcp.rs::tools`, `crates/frank/src/mcp.rs::call`, `crates/frank/src/mcp.rs::tool_result`

#### Scenario: Tools answer as their routes

- GIVEN sightings from three contributors
- WHEN the public tier, an observer, a contributor and a partner call every tool and its route
- THEN each tool's content equals the route's body, and each refusal of the route is a tool error with the same status

**Tests:** `crates/frank/tests/api.rs::mcp_tools_answer_as_their_routes`

### Requirement 3: Disclosure applies unchanged [MUST]

Every disclosure rule of the `/v1` routes (statuses, TLP, the reporter threshold; spec 013-disclosure) MUST hold through MCP.

**Implementation:** `crates/frank/src/mcp.rs::call`

#### Scenario: A small cell stays suppressed

- GIVEN a sector seen by one reporter
- WHEN a contributor explores by sector through MCP
- THEN the sector is left out, and a partner sees it; an observer asking for rules gets a tool error

**Tests:** `crates/frank/tests/api.rs::mcp_suppresses_small_cells_below_partner`

### Requirement 4: Credentials [MUST]

The caller MUST be named before the message is read, as on `/v1`: an unknown token, or the token of a disabled user, MUST get HTTP 401 for every message, notifications included. Without credentials the caller is the public tier.

**Implementation:** `crates/frank/src/mcp.rs::mcp`

#### Scenario: Unknown and disabled tokens

- GIVEN a token that names no user, and a user that is then disabled
- WHEN either sends a message
- THEN the answer is 401

**Tests:** `crates/frank/tests/api.rs::mcp_refuses_unknown_and_disabled_tokens`

### Requirement 5: Malformed messages [MUST]

A message that is not JSON MUST get a JSON-RPC parse error (-32700); a batch, a non-2.0 message or one without a method an invalid request (-32600); an unknown method -32601; an unknown tool or arguments of the wrong shape -32602. None of them MUST be a 500.

**Implementation:** `crates/frank/src/mcp.rs::mcp`, `crates/frank/src/mcp.rs::params`

#### Scenario: Errors

- GIVEN a contributor
- WHEN it sends broken JSON, a batch, an unknown method, an unknown tool, or a lookup without its value
- THEN each gets the JSON-RPC error code above with HTTP 200

**Tests:** `crates/frank/tests/api.rs::mcp_malformed_messages_are_json_rpc_errors`

### Requirement 6: Audit [MUST]

Each `tools/call` of a known tool MUST write an `mcp_call` audit line with the tool and whether it answered, `by` the caller. A token MUST NOT appear in it.

**Implementation:** `crates/frank/src/mcp.rs::mcp`

#### Scenario: Calls are audited

- GIVEN a contributor and an observer
- WHEN they call `whoami` and `rule_detail`
- THEN there are two `mcp_call` lines, by `mdr@mdr` (ok) and `obs@obs` (not ok)

**Tests:** `crates/frank/tests/api.rs::mcp_tool_calls_are_audited`
