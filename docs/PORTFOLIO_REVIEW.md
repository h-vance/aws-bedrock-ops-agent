# Portfolio Review Guide

This guide is for reviewers who want to quickly understand what the project demonstrates and where to inspect the implementation.

## What This Demonstrates

- FastAPI API design for a small incident-triage service.
- Deterministic mock mode for reliable demos without AWS credentials.
- Amazon Bedrock integration path with validated structured output.
- Infrastructure-as-code example for a minimal Lambda Bedrock caller.
- Frontend handling for a realistic support workflow: evidence, hypotheses, checks, escalation status, and customer comms.
- CI coverage for Python linting, unit tests, Markdown checks, and Terraform validation.

## Best Review Path

1. Open the live demo and run the three built-in incident scenarios.
2. Read `assistant.py` for the API contract, mock/live mode switch, and Bedrock fallback handling.
3. Read `static/index.html` for the evidence console and escaped rendering of API output.
4. Read `main.tf` and `lambda_handler.py` for the AWS Lambda deployment path.
5. Run the local verification commands in the README.

## Engineering Tradeoffs

- The demo favors reliability over live model dependency by defaulting to mock mode.
- The Lambda example is intentionally separate from the FastAPI app to keep packaging simple and explicit.
- The project validates Bedrock output but does not implement a full evaluation harness.
- The public demo is unauthenticated because it is mock-only; production use would require authentication, rate limiting, and stricter observability.

## Review Commands

```bash
pip install -r requirements-dev.txt
ruff check .
python -m unittest discover -s tests
terraform fmt -check
terraform validate
```

## Suggested Discussion Topics

- How to extend this into an authenticated internal support tool.
- How to add evaluation cases for Bedrock responses and escalation quality.
- How to connect real observability data while preserving least privilege and data boundaries.
- How to split the frontend into a framework if the demo grows beyond a static console.
