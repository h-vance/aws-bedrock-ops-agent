import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import assistant
import rate_limit
import triage_core


class FakeBedrockClient:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        return {"output": {"message": {"content": [{"text": self.text}]}}}


class AssistantApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(assistant.app)

    def test_health_reports_mock_mode_and_lab_url(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "mock")
        self.assertEqual(response.json()["lab_url"], "http://failure-lab:8000")

    def test_triage_returns_deterministic_mock_response(self):
        response = self.client.post(
            "/triage",
            json={
                "incident_id": "INC-001",
                "summary": "Auth cascade after token rotation",
                "timeline": [],
                "log_lines": [],
                "request_samples": [],
                "related_endpoints": [],
            },
        )

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["incident_id"], "INC-001")
        self.assertEqual(body["mode"], "mock")
        self.assertEqual(body["hypotheses"][0]["confidence"], "high")

    def test_triage_rejects_blank_incident_id(self):
        response = self.client.post(
            "/triage",
            json={"incident_id": "  ", "summary": "timeout"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "incident_id is required")

    def test_bedrock_response_is_validated(self):
        original_client = triage_core._bedrock_client
        triage_core._bedrock_client = lambda: FakeBedrockClient(
            json.dumps(
                {
                    "hypotheses": [
                        {
                            "rank": 1,
                            "hypothesis": "Upstream timeout",
                            "confidence": "high",
                        }
                    ],
                    "recommended_checks": ["Compare timeout settings"],
                    "escalation_ready": True,
                    "customer_comms_draft": "We are reviewing timeout settings.",
                }
            )
        )
        try:
            result = triage_core._call_bedrock(
                triage_core.IncidentBundle(incident_id="INC-003", summary="timeout")
            )
        finally:
            triage_core._bedrock_client = original_client

        self.assertEqual(result["hypotheses"][0]["evidence_ids"], [])
        self.assertEqual(result["hypotheses"][0]["check_command"], "")


class LiveIncidentApiTests(unittest.TestCase):
    def setUp(self):
        rate_limit.reset()
        self.addCleanup(rate_limit.reset)
        self.client = TestClient(assistant.app)
        self.addCleanup(self.client.close)
        self.enterContext(patch.object(assistant, "BEDROCK_MOCK", False))
        self.enterContext(patch.object(triage_core, "LANGFUSE_PUBLIC_KEY", ""))
        self.bedrock = FakeBedrockClient("{}")
        self.enterContext(patch("boto3.client", return_value=self.bedrock))

    def test_live_triage_sends_distinguishing_evidence_and_trace_ids(self):
        prompts = []
        for event, message, path, status, trace in (
            ("Token rotated", "Signature expired", "/login", 403, "trace-auth"),
            ("Upstream stalled", "Read timed out", "/orders", 504, "trace-slow"),
        ):
            with self.subTest(trace=trace):
                response = self.client.post(
                    "/triage",
                    json={
                        "incident_id": "INC-EVIDENCE",
                        "summary": "Requests fail",
                        "timeline": [
                            {
                                "ts": "2026-10-17T12:00:00Z",
                                "event": event,
                                "trace_id": trace,
                            }
                        ],
                        "log_lines": [
                            {"level": "ERROR", "message": message, "trace_id": trace}
                        ],
                        "request_samples": [
                            {
                                "method": "GET",
                                "path": path,
                                "status": status,
                                "trace_id": trace,
                            }
                        ],
                        "related_endpoints": ["/health"],
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["mode"], "bedrock")
                prompt = self.bedrock.calls[-1]["messages"][0]["content"][0]["text"]
                prompts.append(prompt)
                for evidence in (
                    event,
                    message,
                    path,
                    str(status),
                    trace,
                    "GET",
                    "ERROR",
                    "/health",
                ):
                    self.assertIn(evidence, prompt)
        self.assertNotEqual(prompts[0], prompts[1])

    def test_live_triage_bounds_evidence_and_omits_unapproved_fields(self):
        rows = [
            {
                "ts": "2026-10-17T12:00:00Z",
                "event": "E" * 501,
                "level": "ERROR",
                "message": "M" * 501,
                "trace_id": f"trace-{i:02}",
                "method": "GET",
                "path": "/orders",
                "status": 503,
                "headers": {"Authorization": "header-secret"},
                "body": "body-secret",
                "password": "field-secret",
            }
            for i in range(11)
        ]
        rows[0]["level"] = {"nested": "nested-secret"}
        response = self.client.post(
            "/triage",
            json={
                "incident_id": "I" * 501,
                "summary": "S" * 2001,
                "timeline": rows,
                "log_lines": rows,
                "request_samples": rows,
                "related_endpoints": ["/endpoint-" + str(i) for i in range(11)],
            },
        )
        self.assertEqual(response.status_code, 200)
        prompt = self.bedrock.calls[-1]["messages"][0]["content"][0]["text"]
        for omitted in (
            "trace-10",
            "/endpoint-10",
            "header-secret",
            "body-secret",
            "field-secret",
            "nested-secret",
            "S" * 2001,
            "I" * 501,
            "E" * 501,
            "M" * 501,
        ):
            self.assertNotIn(omitted, prompt)
        for retained in ("trace-09", "/endpoint-9", "S" * 2000, "I" * 500, "E" * 500):
            self.assertIn(retained, prompt)
        self.assertIn("truncated", prompt)
        self.assertLess(len(prompt), 65000)

    def test_live_triage_filters_credentials_and_url_private_parts(self):
        response = self.client.post(
            "/triage",
            json={
                "incident_id": "INC-secret=identifier-secret",
                "summary": 'Failed with password="two word secret" and api_key=summary-key',
                "timeline": [
                    {
                        "event": "Authorization: Bearer timeline-token",
                        "trace_id": "trace-safe",
                    }
                ],
                "log_lines": [
                    {
                        "message": 'Basic dXNlcjpwYXNz refresh_token=refresh-secret "client_secret": "client value"'
                    },
                    {"message": r'password="escaped\" private-tail"'},
                ],
                "request_samples": [
                    {
                        "method": "GET",
                        "status": 403,
                        "path": "https://url-user:url-pass@example.test/orders?key=query-secret#fragment-secret",
                    }
                ],
                "related_endpoints": ["/login?token=endpoint-secret#private-fragment"],
            },
        )
        self.assertEqual(response.status_code, 200)
        prompt = self.bedrock.calls[-1]["messages"][0]["content"][0]["text"]
        for secret in (
            "identifier-secret",
            "two word secret",
            "summary-key",
            "timeline-token",
            "dXNlcjpwYXNz",
            "refresh-secret",
            "client value",
            "private-tail",
            "url-user",
            "url-pass",
            "query-secret",
            "fragment-secret",
            "endpoint-secret",
            "private-fragment",
        ):
            self.assertNotIn(secret, prompt)
        for diagnostic in ("trace-safe", "/orders", "/login", "403", "[REDACTED]"):
            self.assertIn(diagnostic, prompt)

    def test_live_triage_returns_stable_fallback_when_model_output_is_invalid(self):
        for output in ("not json", '{"hypotheses": "invalid shape"}'):
            with self.subTest(output=output):
                self.bedrock.text = output
                response = self.client.post(
                    "/triage",
                    json={
                        "incident_id": "INC-FALLBACK",
                        "summary": "Upstream timeout",
                    },
                )
                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertEqual(body["incident_id"], "INC-FALLBACK")
                self.assertEqual(body["mode"], "bedrock")
                self.assertTrue(body["escalation_ready"])
                self.assertEqual(body["hypotheses"][0]["confidence"], "low")
                self.assertEqual(body["recommended_checks"], [])


if __name__ == "__main__":
    unittest.main()
