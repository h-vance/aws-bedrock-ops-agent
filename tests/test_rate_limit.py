import unittest

from fastapi.testclient import TestClient

import assistant
import rate_limit


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        rate_limit.reset()
        self._original_limit = rate_limit.RATE_LIMIT_REQUESTS
        rate_limit.RATE_LIMIT_REQUESTS = 2
        self.client = TestClient(assistant.app)

    def tearDown(self):
        rate_limit.RATE_LIMIT_REQUESTS = self._original_limit
        rate_limit.reset()

    def _triage_request(self):
        return self.client.post(
            "/triage",
            json={"incident_id": "INC-001", "summary": "timeout"},
        )

    def test_allows_requests_within_the_limit(self):
        for _ in range(2):
            response = self._triage_request()
            self.assertEqual(response.status_code, 200)

    def test_blocks_requests_over_the_limit(self):
        for _ in range(2):
            self._triage_request()

        response = self._triage_request()

        self.assertEqual(response.status_code, 429)
        self.assertIn("Rate limit", response.json()["detail"])

    def test_unrelated_endpoints_are_not_rate_limited(self):
        for _ in range(5):
            response = self.client.get("/health")
            self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
