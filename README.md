# AWS Bedrock Agent

[![Live Demo](https://www.shieldcn.dev/badge/Live%20Demo-000000.svg?variant=default&logo=Render&logoColor=FFFFFF&size=xs)](https://aws-bedrock-ops-agent.onrender.com)
[![Deploy](https://www.shieldcn.dev/badge/Deploy%20to%20Render-000000.svg?variant=default&logo=Render&logoColor=FFFFFF&size=xs)](https://render.com/deploy)
[![FastAPI](https://www.shieldcn.dev/badge/FastAPI-009688.svg?variant=default&logo=FastAPI&logoColor=FFFFFF&size=xs)](https://fastapi.tiangolo.com)
[![Python](https://www.shieldcn.dev/badge/Python-3776AB.svg?variant=default&logo=Python&logoColor=FFFFFF&size=xs)](https://python.org)

> **L2 triage copilot for support engineers: ingests incident evidence bundles and returns hypotheses, checks, and escalation-ready notes — not a general chat assistant.**

Part of the [Ops Support Demo](https://aws-bedrock-ops-agent.onrender.com/) portfolio.

## Overview

A structured triage copilot that consumes incident evidence from [api-failure-analysis](https://github.com/h-vance/api-failure-analysis) and returns ranked hypotheses, recommended checks, and escalation documentation. Designed for support engineers who need AI assistance grounded in actual incident data — not open-ended conversation.

## Features

- **Structured Triage:** `POST /triage` accepts an incident evidence bundle; returns JSON with hypotheses, checks, and escalation readiness.
- **Mock Mode:** `BEDROCK_MOCK=true` returns deterministic canned responses — works offline with no AWS credentials.
- **Live Bedrock Mode:** `BEDROCK_MOCK=false` invokes Amazon Bedrock Runtime with validated structured output.
- **AWS Lambda Example:** Terraform deploys a minimal Lambda handler for Bedrock invocation and IAM review.
- **Dual-Mode Operation:** Local FastAPI server for development and demo; Lambda handler for deployment.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - system boundaries, request flow, modes, and known limits
- [Operations Runbook](docs/RUNBOOK.md) - health checks, local/Render/Lambda operations, failures, and rollback
- [Security Notes](docs/SECURITY.md) - data handling, access controls, model output safety, and review checklist
- [Portfolio Review Guide](docs/PORTFOLIO_REVIEW.md) - suggested reviewer path, tradeoffs, and discussion topics

## Quickstart

```bash
# Install runtime dependencies
pip install -r requirements.txt

# Start with mock mode (no AWS needed)
BEDROCK_MOCK=true python assistant.py --api

# Or via docker-compose in the meta-repo
cd ../ops-support-demo && make demo
```

## API

### POST /triage

**Request** — incident evidence bundle (same schema as api-failure-analysis evidence-bundle):

```json
{
  "incident_id": "INC-001",
  "summary": "Auth cascade after token rotation",
  "timeline": [
    { "ts": "2025-01-15T10:00:00Z", "event": "...", "trace_id": "tx-001" }
  ],
  "log_lines": [
    { "level": "error", "message": "...", "trace_id": "tx-001" }
  ],
  "request_samples": [
    { "method": "GET", "path": "/api/v1/data", "status": 403 }
  ],
  "related_endpoints": ["/login", "/api/v1/data"]
}
```

**Response** — structured triage output:

```json
{
  "incident_id": "INC-001",
  "hypotheses": [
    {
      "rank": 1,
      "hypothesis": "Token rotation invalidated active sessions without grace period",
      "confidence": "high",
      "evidence_ids": ["tx-001"],
      "check_command": "curl -s -H 'Authorization: Bearer <old_token>' http://localhost:8000/api/v1/data"
    }
  ],
  "recommended_checks": [
    "Verify token expiry on /login response",
    "Check if /api/v1/data accepts the new token format"
  ],
  "escalation_ready": true,
  "customer_comms_draft": "We identified an authentication failure caused by a token rotation that invalidated active sessions. Engineering is reviewing the rollout sequence."
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BEDROCK_MOCK` | `true` | Use canned responses (no AWS) or call Bedrock |
| `LAB_BASE_URL` | `http://failure-lab:8000` | Used in `/health` response to indicate connected lab |
| `CORS_ORIGINS` | `http://localhost:8080,http://127.0.0.1:8080` | Comma-separated browser origins allowed to call the API |
| `AWS_REGION` | `us-east-1` | AWS region for Bedrock runtime calls |
| `BEDROCK_MODEL_ID` | `amazon.titan-text-express-v1` | Bedrock model invoked in live mode |

Note: CORS is pre-configured to accept requests from `http://localhost:8080` and `http://127.0.0.1:8080` (the debug console). For production, set `CORS_ORIGINS` to the deployed browser origin.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Returns `status`, `mode` (mock/live), and `lab_url` |
| POST | `/triage` | Accepts evidence bundle; returns hypotheses, checks, escalation notes |

## Deployment

### Live Demo (Render)
```bash
curl https://aws-bedrock-ops-agent.onrender.com/health
curl -X POST https://aws-bedrock-ops-agent.onrender.com/triage \
  -H "Content-Type: application/json" \
  -d '{"incident_id":"INC-001","summary":"Auth cascade after token rotation","timeline":[],"log_lines":[],"request_samples":[],"related_endpoints":[]}'
```

The live demo runs on Render's free tier with `BEDROCK_MOCK=true`. No AWS credentials needed.

### Local (Mock)
```bash
BEDROCK_MOCK=true python assistant.py --api
```

### AWS Lambda
```bash
# Deploys lambda_handler.lambda_handler with 30s timeout + Bedrock and log IAM
terraform init && terraform apply
```

The Terraform config (`main.tf`) zips `lambda_handler.py`, creates a Lambda function with `lambda_handler.lambda_handler` as entry point, 30-second timeout, and an IAM role scoped to Bedrock invocation plus CloudWatch Logs writes. The Lambda handler is a minimal Bedrock text endpoint; the FastAPI triage demo is deployed separately through Render or Docker.

## CORS

The FastAPI app includes pre-configured `CORSMiddleware` allowing `http://localhost:8080` and `http://127.0.0.1:8080` (the debug console). Set `CORS_ORIGINS` when deploying under a custom domain.

## Development

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
terraform fmt -check
terraform validate
```

## Security

Follows Principle of Least Privilege. The Lambda IAM role is scoped to `bedrock:InvokeModel` plus the CloudWatch Logs actions required for runtime logging.

## Related

- [api-failure-analysis](https://github.com/h-vance/api-failure-analysis) — evidence engine that feeds incident bundles
- [ops-support-demo](https://github.com/h-vance/ops-support-demo) — umbrella docker-compose demo

## License

MIT
