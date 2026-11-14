# Asking FRANK from an AI assistant (MCP)

FRANK speaks the [Model Context Protocol](https://modelcontextprotocol.io) on `POST /mcp`. An assistant such as Claude Code can then answer questions like *"which SIGMA rules fired most in the energy sector this month?"* or *"has anyone seen 192.0.2.10?"* from FRANK's sightings, with your own access and nothing more.

This page is for users. The requirements are in [spec 015](../.openspec/specs/015-mcp/spec.md), access tiers in [ADR-002](../.openspec/architecture/decisions/002-tiered-access-control.md), sign-in in [ADR-020](../.openspec/architecture/decisions/020-sso-with-openid-connect.md).

## What you can and cannot do

- **Read only.** The assistant can query statistics, IoCs, rules and sightings. It cannot submit sightings, change anything, or download the Parquet files.
- **Your access, no more.** Every tool calls the `/v1` route of the same name with your token, so it sees exactly what that token sees in the API and the web app: the same tier, the same TLP levels, the same suppression of small groups.
- **Audited.** Every tool call is written to the audit log as `mcp_call`, with the tool, whether it answered, and who called. Your token is never logged.

## Connect Claude Code

You need a FRANK API token. Ask your organisation's admin for one; an admin creates it in the web app's admin page, under *tokens* (or `POST /v1/admin/tokens`). A new token is shown once. Keep it in a password manager and read it into an environment variable rather than pasting it into a command:

```bash
export FRANK_TOKEN=$(op read 'op://<vault>/<item>/token')    # 1Password, or your own manager

claude mcp add --transport http frank https://<your FRANK host>/mcp \
  --header "Authorization: Bearer ${FRANK_TOKEN}"

claude mcp list            # frank: … ✓ Connected
```

Against a local `make up`, the host is `frank.local:8443`, after `make trust`. On a server reached over SSH, forward the port (`ssh -L 8443:127.0.0.1:8443 host`) and use the same command.

**Which token?** The token's user decides what the assistant can see. For an assistant, a separate machine user in an observer or contributor organisation is sensible: you can disable it on its own, and its calls are easy to tell apart in the audit log.

Other MCP clients work the same way: Streamable HTTP, the URL above, the `Authorization` header. A Claude.ai connector with Okta sign-in is not there yet (#264).

## The tools

| Tool | Answers | Needs at least | Same as |
|---|---|---|---|
| `whoami` | Your status (public, observer, contributor, partner, core), user and organisation | anyone | `GET /v1/whoami` |
| `statistics` | Totals over the last `days` (30 by default); breakdowns by sector, IoC type and severity from observer, by rule and technique from contributor | anyone | `GET /v1/statistics` |
| `summary` | A summary of the sightings over the last `days` | contributor | `GET /v1/summary` |
| `lookup_ioc` | How often, where and when one IoC was seen (`type`, `value`, optionally one `day`) | contributor | `GET /v1/iocs` |
| `ioc_range` | The IP addresses seen inside a CIDR block | contributor | `GET /v1/iocs/range` |
| `explore` | Sightings grouped by one dimension (`group`), optionally filtered | observer for sector, IoC type, severity; contributor for rule, IoC, campaign, technique | `GET /v1/explore` |
| `rule_detail` | One SIGMA rule's prevalence: trend, sectors, severities, techniques, campaigns, IoCs | contributor | `GET /v1/rules/{id}` |
| `list_sightings` | The records of the visible sightings, a page at a time (`limit` up to 500, `cursor` for the next page) | contributor | `GET /v1/sightings` |
| `get_sighting` | One sighting's records by its `sighting_id` | contributor | `GET /v1/sightings/{id}` |

`explore` and `list_sightings` take the same filters, one value each: `rule`, `ioc` (as `type:value`), `campaign`, `technique`, `sector`, `ioc_type`, `severity`. `list_sightings` also takes `since` and `until` (RFC 3339), `order` (`asc`, `desc`) and `mine` (only your own sightings).

You don't call the tools yourself: the assistant picks them from your question. Ask in plain language and name what you care about: a period, a sector, a rule, an IoC.

## What you will see

- **Your tier decides the detail.** An observer gets totals and breakdowns by sector, IoC type and severity; a contributor also gets rules, IoCs, campaigns and techniques; a partner also sees groups that are suppressed below it.
- **TLP.** You only get sightings at the TLP levels your tier may see: CLEAR public, GREEN observer, AMBER contributor, AMBER+STRICT partner.
- **Small groups are left out.** Below partner, a group seen by too few reporters is suppressed, so no single reporter can be singled out. A breakdown can therefore add up to less than the total.
- **A refusal is an answer.** When your tier is too low for a tool, the assistant gets a tool error with the status and the reason (for example 403) and can tell you so. It does not get the data.

## When something goes wrong

| What you see | Why | What to do |
|---|---|---|
| `claude mcp list` shows the server as failed, or every call gets 401 | The token is unknown, or its user is disabled | Check the token; ask your admin whether the user is active |
| The assistant says a tool needs a higher status | Your tier is below the tool's minimum | Use a token of a user with that status, or ask a narrower question |
| A breakdown misses a sector you expected | Too few reporters in that group for your tier | Expected; a partner sees it |
| Certificate errors against `frank.local` | The local CA is not trusted | `make trust` |
| `GET /mcp` gives 405 | FRANK answers one JSON message per POST and keeps no stream open | Nothing: MCP clients use POST |

To check the endpoint without an assistant:

```bash
curl -s https://<your FRANK host>/mcp \
  -H "Authorization: Bearer ${FRANK_TOKEN}" -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"whoami","arguments":{}}}'
```

## How it works, briefly

The transport is MCP's Streamable HTTP in its stateless form: one JSON-RPC message per request, one JSON answer, no event stream and no session. FRANK speaks protocol versions `2025-11-25`, `2025-06-18` and `2025-03-26`. Without a token, a request is named by your SSO session cookie if you have one, otherwise it is the public tier. The tool code holds no access rules of its own: the `/v1` handler it calls decides, so the API, the web app and the assistant can never disagree about what you may see.
