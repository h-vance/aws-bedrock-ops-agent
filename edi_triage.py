"""Triage for failed EDI transactions.

Same pattern as triage_core.py, pointed at the transaction statuses documented
at https://docs.orderful.com/llms.txt. Classification is code; the model only
does the parts that need judgment (ranking causes, drafting the reply, and
proposing the "ticket two" action that prevents the next ticket).
"""

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

FIXTURES_DIR = Path(__file__).with_name("fixtures")

# ---------------------------------------------------------------------------
# Models. Field names on FailedTransaction copy the Orderful transaction API
# where one exists. errors[] copies the acknowledgment API shape.
# ---------------------------------------------------------------------------


class TxError(BaseModel):
    path: str = ""
    code: str = ""
    message: str
    # Where the error surfaced. In the product this is the tab or notification
    # it came from; in a fixture it is written down.
    source: Literal["guideline", "rule", "mapping", "channel", "ack", "api"] = "guideline"


class FailedTransaction(BaseModel):
    id: str
    direction: Literal["in", "out"] = "in"
    stream: Literal["test", "live"] = "live"
    ediTransactionType: str
    senderId: str
    receiverId: str
    # None means the transaction was never created (API returned non-200).
    validationStatus: Literal["PROCESSING", "VALID", "INVALID"] | None = None
    deliveryStatus: Literal["PENDING", "SENT", "DELIVERED", "FAILED"] = "PENDING"
    acknowledgmentStatus: Literal[
        "NOT_ACKNOWLEDGED", "ACCEPTED", "REJECTED", "OVERDUE", "ACCEPTED_WITH_ERRORS"
    ] = "NOT_ACKNOWLEDGED"
    errors: list[TxError] = Field(default_factory=list)
    snippet: str = ""
    customer_note: str = ""
    context: dict = Field(default_factory=dict)


class EdiHypothesis(BaseModel):
    rank: int
    hypothesis: str
    confidence: Literal["high", "medium", "low"]
    evidence: list[str] = Field(default_factory=list)
    check: str = ""


class TicketTwo(BaseModel):
    kind: Literal["rule", "knowledge_article", "alert", "mapping_test", "partner_contact"]
    title: str
    why: str
    effort: Literal["S", "M", "L"]


class EdiTriageResult(BaseModel):
    hypotheses: list[EdiHypothesis] = Field(default_factory=list)
    customer_reply: str = ""
    ticket_two: TicketTwo


# ---------------------------------------------------------------------------
# Taxonomy. Deterministic, no LLM. The status enums are documented and finite.
# ---------------------------------------------------------------------------

LEAVES = (
    "unprocessed",
    "invalid.guideline",
    "invalid.rule",
    "invalid.mapping",
    "delivery.pending",
    "delivery.failed",
    "ack.rejected",
    "ack.overdue",
    "healthy",
)

TIERS = ("mosaic", "orderful_json", "x12_passthrough", "mft_file", "unknown")


def detect_tier(snippet: str) -> str:
    """Which integration path the customer is on, from the first lines of the payload."""
    text = snippet.strip()
    if not text:
        return "unknown"
    if text.startswith("ISA*"):
        return "x12_passthrough"
    try:
        body = json.loads(text)
    except ValueError:
        return "mft_file"
    if not isinstance(body, dict):
        return "unknown"
    if "transactionType" in body:
        return "orderful_json"
    if "type" in body:
        return "mosaic"
    return "unknown"


def classify(tx: FailedTransaction) -> str:
    """Map the three status axes plus error source to one taxonomy leaf.

    Order follows the lifecycle: created, validated, delivered, acknowledged.
    The first failed stage wins, because later stages cannot have run.
    """
    if tx.validationStatus is None:
        return "unprocessed"
    if tx.validationStatus == "INVALID":
        sources = {e.source for e in tx.errors}
        if "rule" in sources:
            return "invalid.rule"
        if "mapping" in sources:
            return "invalid.mapping"
        return "invalid.guideline"
    if tx.deliveryStatus == "FAILED":
        return "delivery.failed"
    if tx.deliveryStatus == "PENDING":
        return "delivery.pending"
    if tx.acknowledgmentStatus in ("REJECTED", "ACCEPTED_WITH_ERRORS"):
        return "ack.rejected"
    if tx.acknowledgmentStatus == "OVERDUE":
        return "ack.overdue"
    return "healthy"


# ---------------------------------------------------------------------------
# Prompt. Doc facts live here as a short cheat sheet, not in a vector store.
# ---------------------------------------------------------------------------

CHEATSHEET = """\
You are a product support engineer on an EDI platform. Triage one failed transaction.

Status axes (from the transaction API):
- validationStatus: PROCESSING, VALID, INVALID. Rules run before validation, so a bad
  rule output shows up as INVALID.
- deliveryStatus: PENDING (not yet handed to the receiver's channel), SENT, DELIVERED,
  FAILED (channel refused it after retries; HTTP retries 3 times, AS2 needs a positive MDN).
- acknowledgmentStatus: NOT_ACKNOWLEDGED, ACCEPTED, REJECTED (receiver's 997 said no;
  sender fixes and resends), OVERDUE (no 997 in time; contact the partner),
  ACCEPTED_WITH_ERRORS.
- A transaction that was never created (API returned non-200) is "unprocessed": the
  sender, receiver, partnership, or relationship does not exist, or the payload does
  not match the schema.

Integration tiers: mosaic (business-friendly JSON with a "type" field), orderful_json
(camelCase segment names, "transactionType"), x12_passthrough (raw ISA/GS/ST text; the
fix lives in the customer's translator), mft_file (CSV/XML over MFT).

Where errors surface: guideline validation (mandatory segment/element missing, code not
allowed, data type such as DT = CCYYMMDD), rules engine (LOOKUPDATA, FORMATDATE, IFERROR),
the Validation Errors tab (mapping failures, missing required values), the AS2
troubleshooting table (MDN with errors, signature unverified, decryption failed), the
acknowledgment API (errors[] with path, code, message).

Docs: https://docs.orderful.com/docs/transaction-statuses
https://docs.orderful.com/docs/fix-an-invalid-transaction
https://docs.orderful.com/docs/as2-troubleshooting
https://docs.orderful.com/docs/use-the-rules-engine
"""

OUTPUT_SCHEMA = """\
Return JSON only, no prose, matching exactly:
{
  "hypotheses": [
    {"rank": 1, "hypothesis": "...", "confidence": "high|medium|low",
     "evidence": ["errors[0].message", "context.some_key"], "check": "one concrete thing to look at"}
  ],
  "customer_reply": "3 to 5 sentences. Crisp and kind. Say what happened, whose side it is on, what to do, and whether to resend.",
  "ticket_two": {"kind": "rule|knowledge_article|alert|mapping_test|partner_contact",
                 "title": "...", "why": "one or two sentences", "effort": "S|M|L"}
}
Give 2 or 3 hypotheses. Cite evidence by field path. Do not invent fields that are not in the transaction.
If nothing is broken on the platform side, say so and pick partner_contact.
"""


def build_prompt(tx: FailedTransaction, tier: str, leaf: str) -> str:
    return (
        f"{CHEATSHEET}\n"
        f"Deterministic pre-classification (trust it): tier={tier}, classification={leaf}\n\n"
        f"Transaction:\n{tx.model_dump_json(indent=2)}\n\n"
        f"{OUTPUT_SCHEMA}"
    )


# ---------------------------------------------------------------------------
# Mock mode. Canned results live inside each fixture under "mock_result", keyed
# by transaction id, so the demo cannot die on a screen-share.
# ---------------------------------------------------------------------------


def _load_mocks() -> tuple[dict[str, dict], dict[str, dict]]:
    by_id: dict[str, dict] = {}
    by_leaf: dict[str, dict] = {}
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        mock = data.get("mock_result")
        if mock is None:
            continue
        by_id[data["id"]] = mock
        by_leaf.setdefault(classify(FailedTransaction.model_validate(data)), mock)
    return by_id, by_leaf


MOCKS_BY_ID, MOCKS_BY_LEAF = _load_mocks()


def list_fixtures() -> list[dict]:
    """Fixtures for the demo console, without the canned mock result."""
    out = []
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        data.pop("mock_result", None)
        out.append({"name": path.stem, **data})
    return out

_GENERIC_MOCK = EdiTriageResult(
    hypotheses=[
        EdiHypothesis(
            rank=1,
            hypothesis="No failure state on any status axis",
            confidence="high",
            evidence=["validationStatus", "deliveryStatus", "acknowledgmentStatus"],
            check="Confirm the customer is looking at the right transaction id",
        )
    ],
    customer_reply=(
        "This transaction is valid, delivered, and acknowledged on our side. "
        "If you are seeing a different result, send us the transaction id you are looking at."
    ),
    ticket_two=TicketTwo(
        kind="knowledge_article",
        title="How to read the three status fields on a transaction",
        why="Tickets about healthy transactions usually come from reading one status as all three.",
        effort="S",
    ),
).model_dump()


def mock_edi_triage(tx: FailedTransaction, leaf: str) -> dict:
    result = MOCKS_BY_ID.get(tx.id) or MOCKS_BY_LEAF.get(leaf) or _GENERIC_MOCK
    return deepcopy(result)


# ---------------------------------------------------------------------------
# Live mode. Reuses the Bedrock client and model id from triage_core.
# ---------------------------------------------------------------------------


def _invoke_bedrock(prompt: str) -> dict:
    from triage_core import BEDROCK_MODEL_ID, _bedrock_client

    response = _bedrock_client().converse(
        modelId=BEDROCK_MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
    )
    text = response["output"]["message"]["content"][0]["text"].strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return EdiTriageResult.model_validate(json.loads(text)).model_dump()


def _fallback_edi_triage(error: Exception) -> dict:
    return EdiTriageResult(
        hypotheses=[
            EdiHypothesis(rank=1, hypothesis=f"Bedrock error: {error}", confidence="low")
        ],
        customer_reply="",
        ticket_two=TicketTwo(
            kind="alert",
            title="Triage model call failed",
            why=str(error),
            effort="S",
        ),
    ).model_dump()


def run_edi_triage(tx: FailedTransaction, mock: bool) -> dict:
    tier = detect_tier(tx.snippet)
    leaf = classify(tx)
    if mock:
        result = mock_edi_triage(tx, leaf)
    else:
        try:
            result = _invoke_bedrock(build_prompt(tx, tier, leaf))
        except Exception as e:  # noqa: BLE001 - same fallback boundary as triage_core
            result = _fallback_edi_triage(e)
    return {
        "transaction_id": tx.id,
        "tier": tier,
        "classification": leaf,
        **result,
        "mode": "mock" if mock else "bedrock",
    }


# ---------------------------------------------------------------------------
# CLI: python edi_triage.py fixtures/<name>.json [--bedrock] [--json]
# ---------------------------------------------------------------------------


def format_result(tx: FailedTransaction, result: dict) -> str:
    lines = [
        f"Transaction   {result['transaction_id']}",
        (
            f"Type          {tx.ediTransactionType}  {tx.direction}/{tx.stream}  "
            f"{tx.senderId} -> {tx.receiverId}"
        ),
        (
            f"Statuses      validation={tx.validationStatus or 'NOT_CREATED'}  "
            f"delivery={tx.deliveryStatus}  ack={tx.acknowledgmentStatus}"
        ),
        f"Tier          {result['tier']}",
        f"Class         {result['classification']}",
        "",
        "Hypotheses",
    ]
    for h in result["hypotheses"]:
        lines.append(f"  {h['rank']}. [{h['confidence']}] {h['hypothesis']}")
        if h.get("evidence"):
            lines.append(f"     evidence: {', '.join(h['evidence'])}")
        if h.get("check"):
            lines.append(f"     check:    {h['check']}")
    t = result["ticket_two"]
    lines += [
        "",
        "Customer reply",
        f"  {result['customer_reply']}",
        "",
        f"Ticket two    [{t['kind']}, effort {t['effort']}]",
        f"  {t['title']}",
        f"  {t['why']}",
        "",
        f"Mode          {result['mode']}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Triage one failed EDI transaction.")
    parser.add_argument("fixture", type=Path, help="path to a transaction JSON file")
    parser.add_argument("--bedrock", action="store_true", help="call Bedrock instead of mock")
    parser.add_argument("--json", action="store_true", help="print raw JSON")
    args = parser.parse_args(argv)

    tx = FailedTransaction.model_validate(json.loads(args.fixture.read_text()))
    result = run_edi_triage(tx, mock=not args.bedrock)
    print(json.dumps(result, indent=2) if args.json else format_result(tx, result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
