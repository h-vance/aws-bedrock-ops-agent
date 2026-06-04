# Architecture

This repo demonstrates an L2 incident triage copilot backed by Amazon Bedrock. It is intentionally small: the core product surface is a FastAPI service, a static browser console, and a minimal Lambda Bedrock entrypoint for infrastructure demonstration.

## System Boundaries

| Component | Responsibility | Runtime |
|-----------|----------------|---------|
| FastAPI app | Serves the triage API, health check, and static demo console | Render, Docker, local Python |
| Static console | Lets reviewers run curated incident bundles and inspect triage output | Browser |
| Bedrock client | Calls `bedrock-runtime.converse` in live mode | FastAPI or Lambda |
| Lambda handler | Minimal text-to-Bedrock endpoint for Terraform deployment | AWS Lambda |
| Terraform | Provisions Lambda IAM and function packaging | Local or CI validation |

The FastAPI triage demo and the Lambda handler are separate deployment targets. The Lambda handler is not the web application; it exists to show AWS packaging, IAM, and Bedrock invocation with the smallest viable runtime surface.

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
| Lambda | `terraform apply` | Deploys `lambda_handler.lambda_handler` as a minimal Bedrock caller |

## Design Choices

- Mock mode is the default so the portfolio demo is reliable without AWS credentials.
- Bedrock response validation keeps model output from breaking the API contract.
- The browser console escapes dynamic response fields before rendering to reduce XSS risk from model or API output.
- The Lambda package is minimal so the Terraform example does not depend on FastAPI or web server dependencies.

## Known Limits

- The public demo is unauthenticated and should remain mock-only.
- The app does not persist incident bundles, traces, or generated triage output.
- The Lambda function is a minimal Bedrock text endpoint, not an API Gateway-backed replacement for the FastAPI app.
- The Terraform IAM policy scopes Bedrock to `Resource = "*"`, which is common for Bedrock model invocation but should be revisited for account-specific production controls.
