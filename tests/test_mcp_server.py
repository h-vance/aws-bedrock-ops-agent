import json
import unittest

from fastapi.testclient import TestClient

import assistant
import mcp_server
from triage_core import IncidentBundle


class TriageIncidentToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_auth_incident_returns_high_confidence_hypothesis(self):
        result = await mcp_server.triage_incident(
            IncidentBundle(incident_id="INC-001", summary="Auth cascade after token rotation")
        )

        self.assertEqual(result.hypotheses[0].confidence, "high")
        self.assertTrue(result.escalation_ready)

    async def test_webhook_incident_is_not_escalation_ready(self):
        result = await mcp_server.triage_incident(
            IncidentBundle(incident_id="INC-002", summary="Webhook signature mismatch")
        )

        self.assertFalse(result.escalation_ready)
        self.assertIn("signature", result.hypotheses[0].hypothesis.lower())

    async def test_timeout_incident_returns_expected_checks(self):
        result = await mcp_server.triage_incident(
            IncidentBundle(incident_id="INC-003", summary="Upstream timeout on external call")
        )

        self.assertTrue(result.escalation_ready)
        self.assertTrue(any("timeout" in check.lower() for check in result.recommended_checks))


class McpHttpEndpointTests(unittest.TestCase):
    # The MCP session manager backing assistant.app's /mcp mount can only be
    # started/stopped once per process, so the TestClient lifespan is entered
    # once for the whole class rather than per test.
    @classmethod
    def setUpClass(cls):
        cls._client_cm = TestClient(assistant.app, base_url="http://localhost:8001")
        cls.client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)

    def setUp(self):
        self.client = self.__class__.client
        self.headers = {"Accept": "application/json, text/event-stream"}

    def _parse_sse_json(self, text):
        for line in text.splitlines():
            if line.startswith("data: "):
                return json.loads(line[len("data: ") :])
        raise AssertionError(f"no SSE data line in response: {text!r}")

    def test_mcp_endpoint_lists_triage_tool(self):
        response = self.client.post(
            "/mcp/",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        body = self._parse_sse_json(response.text)
        tool_names = [tool["name"] for tool in body["result"]["tools"]]
        self.assertIn("triage_incident", tool_names)

    def test_mcp_endpoint_calls_triage_tool(self):
        response = self.client.post(
            "/mcp/",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "triage_incident",
                    "arguments": {
                        "bundle": {
                            "incident_id": "INC-001",
                            "summary": "Auth cascade after token rotation",
                        }
                    },
                },
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        body = self._parse_sse_json(response.text)
        payload = json.loads(body["result"]["content"][0]["text"])
        self.assertEqual(payload["incident_id"], "INC-001")
        self.assertEqual(payload["mode"], "mock")


if __name__ == "__main__":
    unittest.main()
