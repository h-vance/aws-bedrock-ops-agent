import json
import unittest

from fastapi.testclient import TestClient

import assistant
import lambda_handler


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
        original_client = assistant._bedrock_client
        assistant._bedrock_client = lambda: FakeBedrockClient(
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
            result = assistant._call_bedrock(
                assistant.IncidentBundle(incident_id="INC-003", summary="timeout")
            )
        finally:
            assistant._bedrock_client = original_client

        self.assertEqual(result["hypotheses"][0]["evidence_ids"], [])
        self.assertEqual(result["hypotheses"][0]["check_command"], "")

    def test_bedrock_malformed_json_returns_stable_fallback(self):
        original_client = assistant._bedrock_client
        assistant._bedrock_client = lambda: FakeBedrockClient("not json")
        try:
            result = assistant._call_bedrock(
                assistant.IncidentBundle(incident_id="INC-003", summary="timeout")
            )
        finally:
            assistant._bedrock_client = original_client

        self.assertTrue(result["escalation_ready"])
        self.assertEqual(result["hypotheses"][0]["confidence"], "low")
        self.assertEqual(result["recommended_checks"], [])


class LambdaHandlerTests(unittest.TestCase):
    def test_lambda_handler_uses_minimal_bedrock_entrypoint(self):
        original_client = lambda_handler._bedrock_client
        lambda_handler._bedrock_client = lambda: FakeBedrockClient("hello from bedrock")
        try:
            response = lambda_handler.lambda_handler({"text": "hello"}, None)
        finally:
            lambda_handler._bedrock_client = original_client

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["response"], "hello from bedrock")


if __name__ == "__main__":
    unittest.main()
