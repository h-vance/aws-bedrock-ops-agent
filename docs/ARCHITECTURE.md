# Architecture

This repo demonstrates an L2 incident triage copilot backed by Amazon Bedrock. It is intentionally small: the product surface is a FastAPI service, a static browser console, and an MCP tool, all served from one process.

## System Boundaries

| Component | Responsibility | Runtime |
|-----------|----------------|---------|
| `triage_core.py` | Shared triage logic (models, mock responses, Bedrock call), no web framework dependency | Imported by both surfaces below |
| FastAPI app (`assistant.py`) | Serves the triage REST API, health check, and static demo console | Render, Docker, local Python |
| MCP server (`mcp_server.py`) | Exposes the same triage logic as an MCP tool, mounted at `/mcp` inside the FastAPI app | Same process as the FastAPI app |
| Static console | Lets reviewers run curated incident bundles and inspect triage output | Browser |
| Bedrock client | Calls `bedrock-runtime.converse` in live mode | `triage_core.py` |

## Request Flow

1. The browser loads `/` from the FastAPI app.
2. A reviewer selects an incident scenario in the static console.
3. The console posts an evidence bundle to `POST /triage`.
4. In mock mode, the app returns deterministic hypotheses for offline demos.
5. In live mode, the app sends a constrained prompt to Bedrock, validates the model response, and falls back to a stable error shape if parsing or validation fails.
6. The console renders hypotheses, checks, escalation readiness, and the raw JSON response.
7. Alternatively, an MCP client calls the `triage_incident` tool at `/mcp`: same underlying logic, no REST integration needed. See [docs/MCP_SERVER.md](MCP_SERVER.md).

## Operating Modes

| Mode | Trigger | Behavior |
|------|---------|----------|
| Mock | `BEDROCK_MOCK=true` | No AWS credentials required; deterministic demo output |
| Live Bedrock | `BEDROCK_MOCK=false` | Requires AWS credentials and access to the configured Bedrock model |

## Design Choices

- Mock mode is the default so the portfolio demo is reliable without AWS credentials.
- Bedrock response validation keeps model output from breaking the API contract.
- The browser console escapes dynamic response fields before rendering to reduce XSS risk from model or API output.
- The REST and MCP surfaces share one implementation (`triage_core.py`) so they can't drift apart, and are mounted in the same ASGI app rather than deployed as two services.

## Observability

`triage_core._call_bedrock` is wrapped in a [Langfuse](https://langfuse.com) `generation` observation via the official Python SDK (`langfuse.start_as_current_observation(as_type="generation", ...)`), with trace-level attributes (name, tags, incident metadata) set through `propagate_attributes`. This is a no-op unless `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are both set: `_get_langfuse()` returns `None` otherwise, and callers skip straight to the plain Bedrock call, so mock mode and tests are unaffected. Mock-mode triage calls (`mock_triage`) aren't traced since there's no model call to observe.

Each generation records the Bedrock model ID, a role-labeled `input` matching the actual message sent to the model, `output` (the parsed triage result on success, or the fallback triage result on failure), and token usage (`input_tokens`/`output_tokens`) when the call succeeds. Failures set `level="ERROR"` with a `status_message` in addition to the fallback `output`, so error traces stay queryable rather than showing a blank result. Each call flushes explicitly (`langfuse.flush()`) before returning, since the FastAPI host can idle and a buffered batch could otherwise be lost on a cold shutdown.

## Known Limits

- The public demo is unauthenticated and should remain mock-only.
- The app does not persist incident bundles, traces, or generated triage output beyond what's sent to Langfuse when tracing is enabled.
