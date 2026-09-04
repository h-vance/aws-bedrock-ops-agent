import json
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import assistant
import edi_triage
import mcp_server
import triage_core
from edi_triage import (
    EdiTriageResult,
    FailedTransaction,
    classify,
    detect_tier,
    run_edi_triage,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

# filename -> (tier, classification). Every fixture must be listed, and every
# listed file must exist, so adding a fixture without a test fails loudly.
EXPECTED = {
    "unprocessed_unknown_partner.json": ("orderful_json", "unprocessed"),
    "invalid_missing_mandatory_n1.json": ("orderful_json", "invalid.guideline"),
    "invalid_date_format_dtm.json": ("orderful_json", "invalid.guideline"),
    "invalid_rule_lookup_failed.json": ("orderful_json", "invalid.rule"),
    "invalid_mapping_jsonata.json": ("orderful_json", "invalid.mapping"),
    "delivery_pending_channel.json": ("orderful_json", "delivery.pending"),
    "delivery_failed_as2_mdn.json": ("orderful_json", "delivery.failed"),
    "ack_rejected_997.json": ("orderful_json", "ack.rejected"),
    "ack_overdue_quiet_partner.json": ("orderful_json", "ack.overdue"),
    "tier_ambiguous_x12_passthrough.json": ("x12_passthrough", "invalid.guideline"),
}


def _load(name):
    return FailedTransaction.model_validate(json.loads((FIXTURES / name).read_text()))


def _tx(**overrides):
    base = {
        "id": "test-tx",
        "ediTransactionType": "850_PURCHASE_ORDER",
        "senderId": "A",
        "receiverId": "B",
        "validationStatus": "VALID",
        "deliveryStatus": "DELIVERED",
        "acknowledgmentStatus": "ACCEPTED",
    }
    return FailedTransaction.model_validate({**base, **overrides})


class FakeBedrockClient:
    def __init__(self, text):
        self.text = text

    def converse(self, **kwargs):
        return {"output": {"message": {"content": [{"text": self.text}]}}}


class TierDetectionTests(unittest.TestCase):
    def test_raw_x12_is_passthrough(self):
        self.assertEqual(detect_tier("ISA*00*  *ZZ*A*ZZ*B~GS*PO~ST*850*0001~"), "x12_passthrough")

    def test_transaction_type_key_is_orderful_json(self):
        self.assertEqual(detect_tier('{"transactionType": "850"}'), "orderful_json")

    def test_type_key_is_mosaic(self):
        self.assertEqual(detect_tier('{"type": "855_PURCHASE_ORDER_ACKNOWLEDGMENT"}'), "mosaic")

    def test_non_json_text_is_mft_file(self):
        self.assertEqual(detect_tier("po_number,sku,qty\nPO-1,123,4"), "mft_file")

    def test_empty_or_unrecognized_is_unknown(self):
        self.assertEqual(detect_tier(""), "unknown")
        self.assertEqual(detect_tier('{"hello": 1}'), "unknown")
        self.assertEqual(detect_tier("[1, 2]"), "unknown")


class ClassifyTests(unittest.TestCase):
    def test_never_created_is_unprocessed(self):
        self.assertEqual(classify(_tx(validationStatus=None)), "unprocessed")

    def test_invalid_splits_on_error_source(self):
        err = {"message": "x"}
        self.assertEqual(classify(_tx(validationStatus="INVALID", errors=[err])), "invalid.guideline")
        self.assertEqual(
            classify(_tx(validationStatus="INVALID", errors=[{**err, "source": "rule"}])),
            "invalid.rule",
        )
        self.assertEqual(
            classify(_tx(validationStatus="INVALID", errors=[{**err, "source": "mapping"}])),
            "invalid.mapping",
        )

    def test_rule_error_outranks_guideline_error(self):
        errors = [{"message": "a"}, {"message": "b", "source": "rule"}]
        self.assertEqual(classify(_tx(validationStatus="INVALID", errors=errors)), "invalid.rule")

    def test_delivery_states(self):
        self.assertEqual(classify(_tx(deliveryStatus="FAILED")), "delivery.failed")
        self.assertEqual(
            classify(_tx(deliveryStatus="PENDING", acknowledgmentStatus="NOT_ACKNOWLEDGED")),
            "delivery.pending",
        )

    def test_acknowledgment_states(self):
        self.assertEqual(classify(_tx(acknowledgmentStatus="REJECTED")), "ack.rejected")
        self.assertEqual(classify(_tx(acknowledgmentStatus="ACCEPTED_WITH_ERRORS")), "ack.rejected")
        self.assertEqual(classify(_tx(acknowledgmentStatus="OVERDUE")), "ack.overdue")

    def test_all_good_is_healthy(self):
        self.assertEqual(classify(_tx()), "healthy")


class FixtureTests(unittest.TestCase):
    def test_every_fixture_is_listed_and_every_listed_fixture_exists(self):
        on_disk = {p.name for p in FIXTURES.glob("*.json")}
        self.assertEqual(on_disk, set(EXPECTED))

    def test_each_fixture_classifies_and_mocks_as_expected(self):
        for name, (tier, leaf) in EXPECTED.items():
            with self.subTest(fixture=name):
                tx = _load(name)
                result = run_edi_triage(tx, mock=True)
                self.assertEqual(result["tier"], tier)
                self.assertEqual(result["classification"], leaf)
                self.assertEqual(result["mode"], "mock")
                self.assertEqual(result["transaction_id"], tx.id)
                EdiTriageResult.model_validate(result)
                self.assertGreaterEqual(len(result["hypotheses"]), 2)
                self.assertEqual(result["hypotheses"][0]["rank"], 1)

    def test_overdue_fixture_recommends_partner_contact_not_engineering(self):
        result = run_edi_triage(_load("ack_overdue_quiet_partner.json"), mock=True)
        self.assertEqual(result["ticket_two"]["kind"], "partner_contact")

    def test_unknown_id_falls_back_to_same_leaf_then_generic(self):
        by_leaf = run_edi_triage(_tx(id="nope", deliveryStatus="FAILED"), mock=True)
        self.assertEqual(by_leaf["classification"], "delivery.failed")
        self.assertIn("certificate", by_leaf["hypotheses"][0]["hypothesis"].lower())

        healthy = run_edi_triage(_tx(id="nope"), mock=True)
        self.assertEqual(healthy["classification"], "healthy")
        self.assertEqual(healthy["ticket_two"]["kind"], "knowledge_article")

    def test_mock_results_are_copies(self):
        first = run_edi_triage(_load("ack_rejected_997.json"), mock=True)
        first["hypotheses"].clear()
        second = run_edi_triage(_load("ack_rejected_997.json"), mock=True)
        self.assertTrue(second["hypotheses"])


class BedrockPathTests(unittest.TestCase):
    def _with_fake(self, text):
        original = triage_core._bedrock_client
        triage_core._bedrock_client = lambda: FakeBedrockClient(text)
        try:
            return run_edi_triage(_load("invalid_date_format_dtm.json"), mock=False)
        finally:
            triage_core._bedrock_client = original

    def test_valid_model_json_is_accepted_even_inside_code_fence(self):
        payload = {
            "hypotheses": [{"rank": 1, "hypothesis": "Date export changed", "confidence": "high"}],
            "customer_reply": "The date format changed.",
            "ticket_two": {"kind": "rule", "title": "FORMATDATE", "why": "One rule.", "effort": "S"},
        }
        result = self._with_fake("```json\n" + json.dumps(payload) + "\n```")
        self.assertEqual(result["mode"], "bedrock")
        self.assertEqual(result["classification"], "invalid.guideline")
        self.assertEqual(result["hypotheses"][0]["evidence"], [])
        self.assertEqual(result["ticket_two"]["kind"], "rule")

    def test_malformed_model_output_returns_stable_fallback(self):
        result = self._with_fake("not json")
        self.assertEqual(result["mode"], "bedrock")
        self.assertEqual(result["hypotheses"][0]["confidence"], "low")
        self.assertEqual(result["ticket_two"]["kind"], "alert")
        self.assertEqual(result["customer_reply"], "")

    def test_prompt_carries_preclassification_and_evidence(self):
        tx = _load("delivery_failed_as2_mdn.json")
        prompt = edi_triage.build_prompt(tx, "orderful_json", "delivery.failed")
        self.assertIn("classification=delivery.failed", prompt)
        self.assertIn("The signature is unverified", prompt)
        self.assertIn("Return JSON only", prompt)


class EdiEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(assistant.app)

    def test_endpoint_returns_mock_triage(self):
        body = json.loads((FIXTURES / "ack_rejected_997.json").read_text())
        response = self.client.post("/triage/edi", json=body)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["classification"], "ack.rejected")
        self.assertEqual(response.json()["mode"], "mock")

    def test_fixture_listing_feeds_the_console(self):
        response = self.client.get("/fixtures/edi")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual({f["name"] + ".json" for f in body}, set(EXPECTED))
        self.assertTrue(all("mock_result" not in f for f in body))

        # The console posts a listed fixture back as-is; extra keys must be ignored.
        triage = self.client.post("/triage/edi", json=body[0])
        self.assertEqual(triage.status_code, 200)
        self.assertEqual(triage.json()["transaction_id"], body[0]["id"])

    def test_endpoint_rejects_blank_id(self):
        response = self.client.post(
            "/triage/edi",
            json={"id": " ", "ediTransactionType": "850_PURCHASE_ORDER", "senderId": "A", "receiverId": "B"},
        )
        self.assertEqual(response.status_code, 400)

    def test_endpoint_rejects_unknown_status_value(self):
        response = self.client.post(
            "/triage/edi",
            json={
                "id": "x",
                "ediTransactionType": "850_PURCHASE_ORDER",
                "senderId": "A",
                "receiverId": "B",
                "deliveryStatus": "LOST",
            },
        )
        self.assertEqual(response.status_code, 422)


class EdiMcpToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_returns_typed_result(self):
        result = await mcp_server.triage_edi_transaction(_load("delivery_pending_channel.json"))

        self.assertEqual(result.classification, "delivery.pending")
        self.assertEqual(result.ticket_two.kind, "alert")
        self.assertEqual(result.mode, "mock")


if __name__ == "__main__":
    unittest.main()
