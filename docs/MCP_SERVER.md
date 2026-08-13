# MCP Server

The same triage logic behind `POST /triage` is also exposed as an MCP tool, so any MCP-aware client — an n8n MCP node, a custom agent, or anything else speaking the protocol — can call it directly instead of going through a bespoke REST integration.

## How it's wired

- `triage_core.py` holds the shared logic (`IncidentBundle`, `TriageResult`, mock responses, the Bedrock call) with no FastAPI or MCP dependency.
- `mcp_server.py` defines one tool, `triage_incident`, on top of `triage_core`, using the official `mcp` Python SDK's `MCPServer`.
- `assistant.py` mounts the MCP server's ASGI app at `/mcp` inside the existing FastAPI app, so both the REST API and the MCP tool are served from one process and one deployment.

This means the REST and MCP surfaces can never drift apart — there is exactly one implementation of the triage logic underneath both.

## Transport

Built against the [2026-07-28 MCP specification](https://blog.modelcontextprotocol.io/posts/2026-07-28/): the stateless streamable-HTTP transport, not the older stateful/SSE transport. No session ID is required between requests.

## Connecting a client

Local (mock mode):
```bash
BEDROCK_MOCK=true python assistant.py
```
Then point an MCP client at `http://localhost:8001/mcp/` (streamable HTTP; note the trailing slash — a bare `/mcp` 307-redirects there).

Deployed:
```
https://aws-bedrock-ops-agent.onrender.com/mcp/
```

## Host allowlisting

The SDK's DNS-rebinding protection validates the `Host`/`Origin` headers on every MCP request. It's configured via two env vars (comma-separated), defaulting to localhost-only for local dev:

| Variable | Default | Purpose |
|----------|---------|---------|
| `MCP_ALLOWED_HOSTS` | `127.0.0.1:*,localhost:*,[::1]:*` | Allowed `Host` header values |
| `MCP_ALLOWED_ORIGINS` | `http://127.0.0.1:*,http://localhost:*,http://[::1]:*` | Allowed `Origin` header values |

The deployed Render service sets `MCP_ALLOWED_HOSTS` to include its own public hostname — without this, every request to `/mcp` in production would 421 (the SDK's rebinding protection only auto-allows localhost by default).

## The tool

`triage_incident(bundle: IncidentBundle) -> TriageToolResult`

Same request shape as `POST /triage`'s body; same `hypotheses` / `recommended_checks` / `escalation_ready` / `customer_comms_draft` response shape, plus `incident_id` and `mode` (`mock` or `bedrock`) so a client can tell which run produced the result.

## Testing it locally without a full MCP client

```bash
curl -s http://localhost:8001/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"triage_incident","arguments":{"bundle":{"incident_id":"INC-001","summary":"Auth cascade after token rotation"}}}}'
```
