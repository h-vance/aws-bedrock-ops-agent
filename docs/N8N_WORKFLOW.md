# n8n Triage Workflow

A small n8n workflow that closes the loop end to end: a support ticket comes in via webhook, gets triaged by this repo's live `/triage` API, and the result is posted to Slack.

**Pipeline:** `Webhook → Call Triage API → Format Slack Message → Post to Slack → Respond to Webhook`

Workflow file: [`docs/n8n/triage-workflow.json`](n8n/triage-workflow.json)

## Import

1. In n8n: **Workflows → Import from File** → select `docs/n8n/triage-workflow.json`.
2. Open **Post to Slack** and set your own Slack credential (n8n never exports credentials, so this always has to be wired up after import) and pick a real channel in **Channel**.
3. Optionally set an n8n environment variable `TRIAGE_API_URL` if you want to point at something other than the deployed demo (`https://aws-bedrock-ops-agent.onrender.com`) — e.g. a local `http://localhost:8001` during development.
4. Activate the workflow to get a live webhook URL, or use the test URL shown in the editor while building.

## Triggering it

```bash
curl -X POST https://<your-n8n-instance>/webhook/bedrock-ops-triage \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"TICKET-4821","summary":"Users getting 403s right after login, started ~20 min ago"}'
```

Accepts either a raw ticket shape (`ticket_id`/`summary`) or the full `IncidentBundle` shape from the main API — the **Call Triage API** node falls back sensibly across common field names (`ticket_id`/`incident_id`, `summary`/`subject`/`description`).

## What I verified vs. what needs your n8n instance

I don't have access to your n8n instance from this session, so this JSON is hand-authored against n8n's documented node schema, not exported from a live run — unlike everything else in this roadmap so far, **this one hasn't been click-tested**. Before relying on it:
- Import it and click **Execute workflow** with the curl payload above; n8n will flag anything it can't parse.
- If a node shows a version-mismatch warning on import, that's normal — n8n will offer to update it to the installed version.
- The REST `/triage` endpoint it calls is the same one covered by `tests/test_assistant.py`, so the API side is solid; the n8n side is the untested part.

## Stretch: swap in n8n's native MCP Client Tool node

n8n has a built-in **MCP Client Tool** node (`n8n-nodes-langchain.mcpClientTool`) that connects to an MCP server's streamable-HTTP endpoint and hands its tools to an AI Agent node — pointed at `https://aws-bedrock-ops-agent.onrender.com/mcp/`, it would let an n8n agent call `triage_incident` directly instead of going through the plain REST call above. That's a more direct demonstration of the MCP work, but it's a multi-node "AI Agent + Chat Model + MCP Client Tool" cluster with its own credential requirements (an LLM credential for the Agent node), which is a bigger surface to get right blind. Worth building by hand in the n8n editor once the simpler pipeline above is confirmed working, rather than hand-authoring untested cluster-node JSON here.
