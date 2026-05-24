# AWS Bedrock Agent

[![Live Demo](https://img.shields.io/badge/Live%20Demo-46E3B7?style=for-the-badge&logo=render&logoColor=black)](https://aws-bedrock-ops-agent.onrender.com)
[![Deploy](https://img.shields.io/badge/Deploy%20to%20Render-46E3B7?style=for-the-badge&logo=render&logoColor=black)](https://render.com/deploy)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![AWS](https://img.shields.io/badge/AWS-232F3E?style=for-the-badge)](https://aws.amazon.com/bedrock/)

> **L2 triage copilot for support engineers: ingests incident evidence bundles and returns hypotheses, checks, and escalation-ready notes — not a general chat assistant.**

Part of the [Ops Support Demo](https://aws-bedrock-ops-agent.onrender.com/) portfolio.

## Overview

A structured triage copilot that consumes incident evidence from [api-failure-analysis](https://github.com/h-vance/api-failure-analysis) and returns ranked hypotheses, recommended checks, and escalation documentation. Designed for support engineers who need AI assistance grounded in actual incident data — not open-ended conversation.

## Features

- **Structured Triage:** `POST /triage` accepts an incident evidence bundle; returns JSON with hypotheses, checks, and escalation readiness.
- **Mock Mode:** `BEDROCK_MOCK=true` returns deterministic canned responses — works offline with no AWS credentials.
- **AWS Lambda Ready:** Deploy as a Lambda function via Terraform for production use.
- **Dual-Mode Operation:** Local FastAPI server for development and demo; Lambda handler for deployment.

## Quickstart

```bash
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

Note: CORS is pre-configured to accept requests from `http://localhost:8080` and `http://127.0.0.1:8080` (the debug console). For production, update `allow_origins` in `assistant.py`.

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
# Deploys assistant.lambda_handler with 30s timeout + bedrock:InvokeModel IAM
terraform init && terraform apply
```

The Terraform config (`main.tf`) zips `assistant.py`, creates a Lambda function with `assistant.lambda_handler` as entry point, 30-second timeout, and a least-privilege IAM role scoped to `bedrock:InvokeModel`. Set `BEDROCK_MOCK=false` and `LAB_BASE_URL` in the Lambda environment variables for production use.

## CORS

Both APIs include pre-configured `CORSMiddleware` allowing `http://localhost:8080` and `http://127.0.0.1:8080` (the debug console). Update `allow_origins` when deploying under a custom domain.

## Security

Follows Principle of Least Privilege — IAM role is scoped to `bedrock:InvokeModel` only.

## Related

- [api-failure-analysis](https://github.com/h-vance/api-failure-analysis) — evidence engine that feeds incident bundles
- [ops-support-demo](https://github.com/h-vance/ops-support-demo) — umbrella docker-compose demo

## License

MIT
