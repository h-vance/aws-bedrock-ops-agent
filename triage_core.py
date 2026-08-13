import base64
import json
import os
from copy import deepcopy

from opentelemetry import trace
from pydantic import BaseModel, Field

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "amazon.titan-text-express-v1")

LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://us.cloud.langfuse.com")


def _init_tracer():
    # No-op unless both Langfuse keys are configured — get_tracer() with no
    # provider registered returns OpenTelemetry's built-in no-op tracer, so
    # every span/attribute call below is a safe no-op when unconfigured.
    if not (LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY):
        return trace.get_tracer(__name__)

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    auth = base64.b64encode(f"{LANGFUSE_PUBLIC_KEY}:{LANGFUSE_SECRET_KEY}".encode()).decode()
    exporter = OTLPSpanExporter(
        endpoint=f"{LANGFUSE_HOST}/api/public/otel/v1/traces",
        headers={
            "Authorization": f"Basic {auth}",
            "x-langfuse-ingestion-version": "4",
        },
    )
    provider = TracerProvider(resource=Resource.create({"service.name": "aws-bedrock-ops-agent"}))
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return trace.get_tracer(__name__)


_tracer = _init_tracer()


class IncidentBundle(BaseModel):
    incident_id: str
    summary: str
    timeline: list[dict] = Field(default_factory=list)
    log_lines: list[dict] = Field(default_factory=list)
    request_samples: list[dict] = Field(default_factory=list)
    related_endpoints: list[str] = Field(default_factory=list)


class Hypothesis(BaseModel):
    rank: int
    hypothesis: str
    confidence: str
    evidence_ids: list[str] = Field(default_factory=list)
    check_command: str = ""


class TriageResult(BaseModel):
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    recommended_checks: list[str] = Field(default_factory=list)
    escalation_ready: bool = False
    customer_comms_draft: str = ""


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


def _bedrock_client():
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("boto3 is required when BEDROCK_MOCK=false") from exc

    return boto3.client("bedrock-runtime", region_name=AWS_REGION)


def _fallback_triage(error: Exception) -> dict:
    return TriageResult(
        hypotheses=[
            Hypothesis(
                rank=1,
                hypothesis=f"Bedrock error: {error}",
                confidence="low",
            )
        ],
        escalation_ready=True,
        customer_comms_draft="Unable to complete AI triage due to model error.",
    ).model_dump()


def _call_bedrock(bundle: IncidentBundle) -> dict:
    with _tracer.start_as_current_span("triage_incident") as span:
        span.set_attribute("gen_ai.system", "aws.bedrock")
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.request.model", BEDROCK_MODEL_ID)
        span.set_attribute("incident.id", bundle.incident_id)

        bedrock = _bedrock_client()
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
                modelId=BEDROCK_MODEL_ID,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
            )
            text = response["output"]["message"]["content"][0]["text"]
            usage = response.get("usage", {})
            if usage:
                span.set_attribute("gen_ai.usage.input_tokens", usage.get("inputTokens", 0))
                span.set_attribute("gen_ai.usage.output_tokens", usage.get("outputTokens", 0))
            result = TriageResult.model_validate(json.loads(text)).model_dump()
            span.set_attribute("triage.escalation_ready", result["escalation_ready"])
            return result
        except Exception as e:  # noqa: BLE001 - deliberate catch-all fallback boundary for any Bedrock/parsing failure
            span.record_exception(e)
            span.set_attribute("error", True)
            return _fallback_triage(e)


def mock_triage(bundle: IncidentBundle) -> dict:
    category = _classify_incident(bundle.summary)
    return deepcopy(MOCK_RESPONSES.get(category, MOCK_RESPONSES["auth"]))


def run_triage(bundle: IncidentBundle, mock: bool) -> dict:
    result = mock_triage(bundle) if mock else _call_bedrock(bundle)
    result["incident_id"] = bundle.incident_id
    result["mode"] = "mock" if mock else "bedrock"
    return result
