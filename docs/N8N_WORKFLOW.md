# n8n Triage Workflow

An importable example for receiving a support ticket by webhook, calling this repo's `/triage` API, and posting the result to Slack. Import and execution in n8n remain unverified; the public API uses canned mock responses.

**Pipeline:** `Webhook → Call Triage API → Format Slack Message → Post to Slack → Respond to Webhook`

Workflow file: [`docs/n8n/triage-workflow.json`](n8n/triage-workflow.json)

## Import

1. In n8n: **Workflows → Import from File** → select `docs/n8n/triage-workflow.json`.
2. Open **Post to Slack** and set your own Slack credential (n8n never exports credentials, so this always has to be wired up after import) and pick a real channel in **Channel**.
3. Optionally set an n8n environment variable `TRIAGE_API_URL` if you want to point at something other than the deployed demo (`https://aws-bedrock-ops-agent.onrender.com`), e.g. a local `http://localhost:8001` during development.
4. Activate the workflow to get a live webhook URL, or use the test URL shown in the editor while building.

## Triggering it

```bash
curl -X POST https://<your-n8n-instance>/webhook/bedrock-ops-triage \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"TICKET-4821","summary":"Users getting 403s right after login, started ~20 min ago"}'
```

Accepts either a raw ticket shape (`ticket_id`/`summary`) or the full `IncidentBundle` shape from the main API. The **Call Triage API** node falls back sensibly across common field names (`ticket_id`/`incident_id`, `summary`/`subject`/`description`).

## Verify in your instance

The JSON was authored against the node schema and has not been exported from a successful n8n run. Before relying on it:

1. Import the workflow and resolve any node-version or configuration warnings.
2. Configure the Slack credential, channel, and API URL.
3. Use the test webhook with synthetic input and inspect each node's output.
4. Confirm the Slack message and webhook response before activating the workflow.

API tests cover the service independently; they do not validate n8n node compatibility, credentials, or Slack delivery.
