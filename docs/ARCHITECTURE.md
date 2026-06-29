# Architecture

This repo demonstrates an L2 incident triage copilot backed by Amazon Bedrock. It is intentionally small: the product surface is a FastAPI service and a static browser console.

## System Boundaries

| Component | Responsibility | Runtime |
|-----------|----------------|---------|
| FastAPI app | Serves the triage API, health check, and static demo console | Render, Docker, local Python |
| Static console | Lets reviewers run curated incident bundles and inspect triage output | Browser |
| Bedrock client | Calls `bedrock-runtime.converse` in live mode | FastAPI |

## Request Flow

1. The browser loads `/` from the FastAPI app.
2. A reviewer selects an incident scenario in the static console.
3. The console posts an evidence bundle to `POST /triage`.
4. In mock mode, the app returns deterministic hypotheses for offline demos.
5. In live mode, the app sends a constrained prompt to Bedrock, validates the model response, and falls back to a stable error shape if parsing or validation fails.
6. The console renders hypotheses, checks, escalation readiness, and the raw JSON response.

## Operating Modes

| Mode | Trigger | Behavior |
|------|---------|----------|
| Mock | `BEDROCK_MOCK=true` | No AWS credentials required; deterministic demo output |
| Live Bedrock | `BEDROCK_MOCK=false` | Requires AWS credentials and access to the configured Bedrock model |

## Design Choices

- Mock mode is the default so the portfolio demo is reliable without AWS credentials.
- Bedrock response validation keeps model output from breaking the API contract.
- The browser console escapes dynamic response fields before rendering to reduce XSS risk from model or API output.

## Known Limits

- The public demo is unauthenticated and should remain mock-only.
- The app does not persist incident bundles, traces, or generated triage output.
