# Security Notes

This project is a portfolio demo, not a production incident management system. The public deployment should run in mock mode and should not process customer data, secrets, or private incident evidence.

## Data Handling

- Demo incident bundles are synthetic and embedded in the static console.
- The app does not store payloads or responses locally. When incident tracing is configured, Langfuse receives the same filtered prompt as Bedrock, the original incident ID as metadata, and the model output or error. Metadata, output, and errors do not pass through the prompt filter.
- Live incident mode sends the summary and selected evidence to Bedrock as described below. REST and MCP use the same prompt builder.
- Live EDI mode sends the supplied transaction fields as JSON. The incident evidence filter does not apply to EDI, and EDI calls are not traced with Langfuse.

### Live incident evidence

The prompt includes the first **10 items** of each collection, in submitted order:

| Collection | Included fields |
|------------|-----------------|
| Timeline | `ts`, `event`, `trace_id` |
| Logs | `level`, `message`, `trace_id` |
| Request samples | `method`, `path`, `status`, `trace_id` |
| Related endpoints | Path only |

Only scalar field values are included, represented as text. Headers, bodies, nested values, and unknown fields are omitted. Request and endpoint URLs retain only their path, excluding authority/user information, query, and fragment. Malformed URLs that cannot be parsed become `[invalid path]`.

Included values and the incident ID are limited to **500 characters**, and the summary to **2,000 characters**, after filtering. Original collection counts accompany the selected evidence; the prompt warns that evidence may be truncated. These are outbound field limits, not HTTP request-size limits or token budgets. JSON escaping can expand the serialized size.

The text filter replaces Bearer/Basic credentials and common `key=value` or `key: value` assignments (`password`, `passwd`, `api_key`, `token`, access/refresh/id tokens, `secret`, and `client_secret`, including hyphenated forms) with `[REDACTED]`. Quoted values are supported. This is best-effort filtering, not comprehensive secret or personal-data detection: unlabeled credentials, secrets in paths, encoded values, and ordinary personal information can remain. Review and sanitize inputs before live use; keep the public deployment mock-only.

## Access Controls

| Surface | Current control | Production expectation |
|---------|-----------------|------------------------|
| Public Render app | No user authentication; mock mode only; per-IP rate limiting on `/triage` and `/mcp` (`RATE_LIMIT_REQUESTS` per `RATE_LIMIT_WINDOW_SECONDS`, default 20/hour) | Add auth and request size limits before enabling live mode publicly |
| FastAPI CORS | Configurable allow-list via `CORS_ORIGINS` | Restrict to owned domains |
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
- `MCP_ALLOWED_HOSTS` / `MCP_ALLOWED_ORIGINS`
- `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS`
- `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` (tracing is off unless both keys are set)

## Security Review Checklist

- Confirm public demo uses `BEDROCK_MOCK=true`.
- Confirm no real incident payloads are used in screenshots, docs, tests, or static fixtures.
- Confirm CORS does not include wildcard origins in production.
- Confirm CI does not require long-lived AWS credentials for lint/test validation.

## Reporting

If you find a security issue in this demo, open a private report through GitHub if available, or contact the repository owner directly. Do not include real secrets or customer data in public issues.
