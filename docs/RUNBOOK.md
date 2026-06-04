# Operations Runbook

Use this runbook to validate the demo, troubleshoot failures, and explain the operational path during a portfolio review.

## Quick Health Check

```bash
curl http://localhost:8001/health
```

Expected mock response:

```json
{
  "status": "ok",
  "mode": "mock",
  "lab_url": "http://failure-lab:8000"
}
```

## Local Demo

```bash
pip install -r requirements-dev.txt
BEDROCK_MOCK=true python assistant.py --api
```

Open `http://localhost:8001`, select each incident, and verify that the triage panel returns hypotheses and recommended checks.

## Render Demo

Render runs the FastAPI app with:

```bash
uvicorn assistant:app --host 0.0.0.0 --port $PORT
```

Required Render environment variables:

| Variable | Expected demo value |
|----------|---------------------|
| `BEDROCK_MOCK` | `true` |
| `LAB_BASE_URL` | Deployed app or connected lab URL |
| `CORS_ORIGINS` | Deployed origin plus local debug origins |

Validate:

```bash
curl https://aws-bedrock-ops-agent.onrender.com/health
```

## Live Bedrock Mode

Only use live mode in an AWS-authenticated environment.

```bash
export BEDROCK_MOCK=false
export AWS_REGION=us-east-1
export BEDROCK_MODEL_ID=amazon.titan-text-express-v1
python assistant.py --api
```

Failure handling:

- If AWS credentials are missing, `/triage` returns a controlled low-confidence fallback.
- If Bedrock returns malformed JSON, `/triage` returns a controlled low-confidence fallback.
- If model access is denied, confirm Bedrock model access in the AWS console and IAM permission for `bedrock:InvokeModel`.

## Lambda Deployment

```bash
terraform init
terraform fmt -check
terraform validate
terraform apply
```

The Lambda deployment packages `lambda_handler.py`, not the FastAPI app. It is intended to demonstrate a minimal Bedrock invocation path with IAM and logs.

Post-deploy checks:

- Confirm the Lambda function exists as `BedrockAgent`.
- Invoke it with an event like `{"text": "Summarize this incident"}`.
- Check CloudWatch Logs if the response body contains a graceful Bedrock error.

## Common Failures

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Browser shows `Offline` | App is not running or `/health` is unreachable | Start the FastAPI app and check the port |
| Triage panel shows endpoint failure | `/triage` returned non-2xx or network failed | Check server logs and request body |
| Live mode always returns low-confidence fallback | AWS credentials, model access, or Bedrock output format issue | Validate credentials, model access, and prompt response |
| Terraform validates locally but Lambda fails at runtime | AWS account lacks Bedrock model access | Enable model access and retry invocation |
| Render demo returns live mode unexpectedly | `BEDROCK_MOCK` changed to `false` | Reset Render env var to `true` for public demo |

## Rollback

- Render: redeploy the previous successful deploy from the Render dashboard.
- Lambda: revert the Terraform change or run `terraform apply` from the previous commit.
- Local: restart with `BEDROCK_MOCK=true` to restore deterministic demo behavior.
