# Security Notes

This project is a portfolio demo, not a production incident management system. The public deployment should run in mock mode and should not process customer data, secrets, or private incident evidence.

## Data Handling

- Demo incident bundles are synthetic and embedded in the static console.
- The app does not persist request payloads or generated responses.
- Live Bedrock mode sends incident summaries and evidence counts to the configured Bedrock model. Do not use live mode with sensitive data unless the surrounding AWS account controls are production-ready.

## Access Controls

| Surface | Current control | Production expectation |
|---------|-----------------|------------------------|
| Public Render app | No user authentication; mock mode only | Add auth, rate limiting, and request size limits |
| FastAPI CORS | Configurable allow-list via `CORS_ORIGINS` | Restrict to owned domains |
| Lambda IAM | `bedrock:InvokeModel` plus CloudWatch Logs writes | Review Bedrock resource scoping and account guardrails |
| Local development | Developer AWS credentials if live mode is enabled | Use least-privilege roles and short-lived credentials |

## Model Output Safety

- Bedrock triage responses are validated before the API returns them.
- The browser escapes dynamic response fields before inserting them into the page.
- Malformed model output produces a low-confidence fallback instead of an exception or partial response.

## Secrets

No secrets should be committed to this repo. Use environment variables for runtime configuration:

- `BEDROCK_MOCK`
- `AWS_REGION`
- `BEDROCK_MODEL_ID`
- `LAB_BASE_URL`
- `CORS_ORIGINS`

## Security Review Checklist

- Confirm public demo uses `BEDROCK_MOCK=true`.
- Confirm no real incident payloads are used in screenshots, docs, tests, or static fixtures.
- Confirm CORS does not include wildcard origins in production.
- Confirm Lambda logs do not include sensitive prompts or responses before enabling live traffic.
- Confirm CI does not require long-lived AWS credentials for lint/test validation.

## Reporting

If you find a security issue in this demo, open a private report through GitHub if available, or contact the repository owner directly. Do not include real secrets or customer data in public issues.
