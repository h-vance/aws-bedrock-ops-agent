import os
import json

import boto3
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from botocore.exceptions import ClientError

app = FastAPI(title="Triage Copilot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

UVICORN_PORT = int(os.getenv("PORT", 8001))
BEDROCK_MOCK = os.getenv("BEDROCK_MOCK", "true").lower() == "true"
LAB_BASE_URL = os.getenv("LAB_BASE_URL", "http://localhost:8000")


class IncidentBundle(BaseModel):
    incident_id: str
    summary: str
    timeline: list[dict] = []
    log_lines: list[dict] = []
    request_samples: list[dict] = []
    related_endpoints: list[str] = []


MOCK_RESPONSES = {
    "auth": {
        "hypotheses": [
            {
                "rank": 1,
                "hypothesis": "Token rotation invalidated active sessions without a grace period",
                "confidence": "high",
                "evidence_ids": ["tx-001", "tx-003"],
                "check_command": "curl -s -H 'Authorization: Bearer valid-token-xyz' http://localhost:8000/api/v1/data",
            },
            {
                "rank": 2,
                "hypothesis": "Client cached stale token after rotation event",
                "confidence": "medium",
                "evidence_ids": ["tx-003"],
                "check_command": "curl -s -X POST http://localhost:8000/login -H 'Content-Type: application/json' -d '{\"username\":\"admin\",\"password\":\"password123\"}'",
            },
        ],
        "recommended_checks": [
            "Verify token expiry in /login response",
            "Check if /api/v1/data accepts the new token format",
            "Inspect retry logic in client C — 4 retries suggests no backoff",
        ],
        "escalation_ready": True,
        "customer_comms_draft": "We identified an authentication failure caused by a token rotation that invalidated active sessions. Engineering is reviewing the rollout sequence to add a grace period.",
    },
    "webhook": {
        "hypotheses": [
            {
                "rank": 1,
                "hypothesis": "Partner sent webhook without HMAC-SHA256 signature header",
                "confidence": "high",
                "evidence_ids": ["tx-wh-001"],
                "check_command": "curl -s -X POST http://localhost:8000/webhooks/inbound -H 'Content-Type: application/json' -d '{\"event\":\"test\"}'",
            },
            {
                "rank": 2,
                "hypothesis": "Partner webhook secret was rotated without updating our integration",
                "confidence": "medium",
                "evidence_ids": ["tx-wh-001", "tx-wh-003"],
                "check_command": "curl -s http://localhost:8000/webhooks/inbox | python3 -c 'import sys,json; [print(d[\"status\"]) for d in json.load(sys.stdin)[\"deliveries\"]]'",
            },
        ],
        "recommended_checks": [
            "Verify partner's webhook secret matches our records",
            "Check if partner updated their webhook endpoint recently",
            "Review webhook documentation shared with partner",
        ],
        "escalation_ready": False,
        "customer_comms_draft": "We detected webhook delivery failures due to a signature mismatch. Please verify your webhook signing secret matches the one provided in your integration settings.",
    },
    "timeout": {
        "hypotheses": [
            {
                "rank": 1,
                "hypothesis": "Client-side timeout (30s) is shorter than upstream processing time (45s+)",
                "confidence": "high",
                "evidence_ids": ["tx-to-001", "tx-to-002"],
                "check_command": "curl -s --max-time 60 http://localhost:8000/api/v1/external-call",
            },
            {
                "rank": 2,
                "hypothesis": "No circuit breaker — every request hits upstream even when degraded",
                "confidence": "medium",
                "evidence_ids": ["tx-to-002", "tx-to-003"],
                "check_command": "for i in $(seq 1 5); do curl -s -o /dev/null -w \"%{http_code} %{time_total}\\n\" --max-time 10 http://localhost:8000/api/v1/external-call; done",
            },
        ],
        "recommended_checks": [
            "Compare client timeout config vs upstream SLA",
            "Check if upstream retry-on-timeout is idempotent",
            "Evaluate adding async callback pattern instead of synchronous wait",
        ],
        "escalation_ready": True,
        "customer_comms_draft": "An upstream API timeout occurred because the client timeout (30s) is shorter than the server processing time. We are reviewing timeout configurations and considering async patterns.",
    },
}


def _classify_incident(summary: str) -> str:
    s = summary.lower()
    if "auth" in s or "token" in s or "401" in s or "403" in s:
        return "auth"
    if "webhook" in s or "signature" in s or "hmac" in s:
        return "webhook"
    if "timeout" in s or "upstream" in s:
        return "timeout"
    return "auth"


def _call_bedrock(bundle: IncidentBundle) -> dict:
    bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
    prompt = (
        f"You are an L2 support engineer triaging an incident. "
        f"Analyze this evidence and return structured hypotheses, checks, and escalation readiness. "
        f"Incident: {bundle.summary}\n"
        f"Timeline events: {len(bundle.timeline)}\n"
        f"Log lines: {len(bundle.log_lines)}\n"
        f"Request samples: {len(bundle.request_samples)}\n"
        f"Do not invent metrics. Cite evidence trace IDs. Output JSON only."
    )
    try:
        response = bedrock.converse(
            modelId="amazon.titan-text-express-v1",
            messages=[{"role": "user", "content": [{"text": prompt}]}],
        )
        text = response["output"]["message"]["content"][0]["text"]
        return json.loads(text)
    except (ClientError, json.JSONDecodeError, KeyError) as e:
        return {
            "hypotheses": [{"rank": 1, "hypothesis": f"Bedrock error: {e}", "confidence": "low"}],
            "recommended_checks": [],
            "escalation_ready": True,
            "customer_comms_draft": "Unable to complete AI triage due to model error.",
        }


@app.post("/triage")
async def triage(bundle: IncidentBundle):
    if not bundle.incident_id:
        raise HTTPException(status_code=400, detail="incident_id is required")

    if BEDROCK_MOCK:
        category = _classify_incident(bundle.summary)
        result = MOCK_RESPONSES.get(category, MOCK_RESPONSES["auth"]).copy()
        result["incident_id"] = bundle.incident_id
        result["mode"] = "mock"
        return result

    result = _call_bedrock(bundle)
    result["incident_id"] = bundle.incident_id
    result["mode"] = "bedrock"
    return result


@app.get("/")
async def root():
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(html_path):
        with open(html_path) as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Triage Copilot</h1><p>Demo page not found.</p>")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "mode": "mock" if BEDROCK_MOCK else "bedrock",
        "lab_url": LAB_BASE_URL,
    }


def lambda_handler(event, context):
    user_input = event.get("text", "Hello")
    try:
        bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
        response = bedrock.converse(
            modelId="amazon.titan-text-express-v1",
            messages=[{"role": "user", "content": [{"text": user_input}]}],
        )
        result = response["output"]["message"]["content"][0]["text"]
    except ClientError as error:
        result = f"Gracefully caught an API error: {error.response['Error']['Code']}"
    return {"statusCode": 200, "body": json.dumps({"response": result})}


if __name__ == "__main__":
    import sys
    if "--api" in sys.argv:
        uvicorn.run(app, host="0.0.0.0", port=UVICORN_PORT)
    elif "--legacy-chat" in sys.argv:
        print("Legacy chat mode. Type 'quit' to exit.")
        while True:
            user_input = input("\nYou: ")
            if user_input.lower() == "quit":
                break
            bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
            response = bedrock.converse(
                modelId="amazon.titan-text-express-v1",
                messages=[{"role": "user", "content": [{"text": user_input}]}],
            )
            print(f"Assistant: {response['output']['message']['content'][0]['text']}")
    else:
        uvicorn.run(app, host="0.0.0.0", port=UVICORN_PORT)
