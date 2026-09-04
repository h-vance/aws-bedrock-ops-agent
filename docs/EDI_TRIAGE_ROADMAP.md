# Roadmap: EDI Failure Triage

A weekend-sized feature on a branch of this repo. It points the triage pattern in `triage_core.py` at the transaction failure states documented in Orderful's public docs. Roadmap first, code after review. See [EDI_TRIAGE.md](EDI_TRIAGE.md) for what shipped.

## 0. What the docs actually say (taxonomy check)

Source: https://docs.orderful.com/llms.txt and linked pages, read 2026-09-03.

Orderful tracks a transaction on **three separate status axes**, not one. This matters: the demo should classify on the axis first, then the cause.

| Axis | Enum values (API, verbatim) | Failure values |
|---|---|---|
| `validationStatus` | `PROCESSING`, `VALID`, `INVALID` | `INVALID` |
| `deliveryStatus` | `PENDING`, `SENT`, `DELIVERED`, `FAILED` | `PENDING` (stuck), `FAILED` |
| `acknowledgmentStatus` | `NOT_ACKNOWLEDGED`, `ACCEPTED`, `REJECTED`, `OVERDUE`, `ACCEPTED_WITH_ERRORS` | `REJECTED`, `OVERDUE`, `ACCEPTED_WITH_ERRORS` |

Plus one pre-lifecycle bucket: **Unprocessed** (transaction was never created; API returned non-200). Causes listed in docs: sender/receiver/partnership/relationship does not exist, relationship still in testing, payload does not match Orderful JSON schema or X12 schema, format/version mismatch.

Corrections to the taxonomy in the original brief:

- **Rejected is an acknowledgment status**, driven by the receiver's 997. The docs say the sender must "resend an updated transaction correcting the errors." The acknowledgment API exposes an `errors[]` array with `path`, `code`, `message` (example in docs: "Purchase order references an unknown ship-to location").
- **Pending and Failed are different delivery failures.** `PENDING` means the transaction has not been handed to the receiver's channel yet. `FAILED` means the channel did not receive it after retries (HTTP: 3 attempts on 404/408/409/423/429/502/503/504; AS2: negative MDN or 3 failed attempts).
- **Rules run before validation.** Docs: "Orderful will check whether a transaction is valid after it applies Rules." So a rule that produces a bad value shows up as `INVALID`, not as a separate status. This is a good hypothesis-ranking point for the demo.
- **Mapping errors have a home in the UI.** The "Validation Errors" tab (`?tab=errors`) "surfaces errors collected during the transformation process, for example mapping failures or missing required values." Docs describe JSONata mapping for inbound API transformations.
- **Guideline validation errors** happen when the sender omits a mandatory loop/segment/element or uses a code not in the allowed list. Data types include `DT` (YYMMDD or CCYYMMDD), `TM`, `ID`, `AN`, `N`, `R`.
- **OVERDUE** acknowledgment is a real state the docs say needs "direct contact with the trading partner." Worth one fixture: it is the case where the right answer is "nothing is broken on our side."

Doc pages used:

- https://docs.orderful.com/docs/transaction-statuses
- https://docs.orderful.com/docs/transaction-status-monitoring
- https://docs.orderful.com/docs/transaction-success-and-failure
- https://docs.orderful.com/docs/fix-an-invalid-transaction
- https://docs.orderful.com/docs/unprocessed-transactions
- https://docs.orderful.com/docs/use-the-rules-engine
- https://docs.orderful.com/docs/enter-guideline-requirements
- https://docs.orderful.com/docs/as2-troubleshooting
- https://docs.orderful.com/docs/x12-to-json-conversion
- https://docs.orderful.com/reference/overview
- https://docs.orderful.com/reference/transactionv4controller_gettransaction
- https://docs.orderful.com/reference/compositetransactioncontroller_getacknowledgment

Integration tiers (from the API overview) and how to tell them apart from a payload:

| Tier | Tell |
|---|---|
| Mosaic | `type` like `855_PURCHASE_ORDER_ACKNOWLEDGMENT`, business field names, no segment codes |
| Orderful JSON | camelCase segment names like `beginningSegmentForPurchaseOrder`, `transactionType: "850"` |
| X12 Passthrough | raw `ISA*...~GS*...~ST*850*0001~` text |
| Any file over MFT | CSV/XML/custom, non-EDI |

Final demo taxonomy (7 leaves):

1. `unprocessed` (never created)
2. `invalid.guideline` (mandatory segment/element missing, bad code, bad DT format)
3. `invalid.rule` (rules engine produced a bad value or lookup failed)
4. `invalid.mapping` (JSONata / transformation, Validation Errors tab)
5. `delivery.pending` (stuck, channel not reached)
6. `delivery.failed` (channel reached, refused: AS2 MDN, HTTP 4xx/5xx, SFTP)
7. `ack.rejected` / `ack.overdue` (receiver backend said no, or said nothing)

## 1. Scope for one weekend

**In**

- One module, `edi_triage.py`, next to `triage_core.py`. Same shape: models, mock, Bedrock call, one entry function.
- CLI: `python edi_triage.py fixtures/<name>.json` prints tier, classification, ranked hypotheses, draft reply, ticket-two action.
- `POST /triage/edi` on the existing FastAPI app and a `triage_edi_transaction` MCP tool, both one function call deep.
- 10 JSON fixtures, one per taxonomy leaf plus tier-ambiguity and "nothing is broken" cases. Each carries its own `mock_result`.
- Mock mode that works with no AWS credentials so the demo cannot die on a screen-share.
- Bedrock mode using the client and model id already in `triage_core.py`.
- One test file that runs every fixture through mock mode and checks tier and classification.
- Docs with honest framing (see section 6).

**Out** (say so in the docs)

- No Orderful API calls, no webhooks, no real accounts.
- No changes to the browser console in `static/`. Terminal, REST, and MCP only.
- No n8n workflow. One sentence in the docs says the sibling n8n repo is where the ticket-two automations would run.
- No EDI parsing. Fixtures carry a `snippet` string, the model reads it as text.
- No retrieval over the docs. Doc facts live in the prompt as a short cheat sheet with URLs.
- No Langfuse tracing on this path. The incident path has it; one line in the docs says so.

## 2. Architecture

Feature add on a branch. Nothing existing is restructured.

| Existing piece | Where | How the EDI path uses it |
|---|---|---|
| `_bedrock_client()`, `BEDROCK_MODEL_ID` | `triage_core.py` | Imported lazily inside `_invoke_bedrock`, so mock mode never touches boto3 |
| `BEDROCK_MOCK` env flag | `assistant.py`, `mcp_server.py` | Same flag drives both triage paths |
| `run_triage` return style (dict with id and `mode`) | `triage_core.py` | `run_edi_triage` returns the same style |
| `TriageToolResult(TriageResult)` subclass | `mcp_server.py` | `EdiTriageToolResult(EdiTriageResult)` |
| `RATE_LIMITED_PATHS` prefix match on `/triage` | `rate_limit.py` | Covers `/triage/edi` with no change |
| `FakeBedrockClient` and unittest style | `tests/test_assistant.py` | Copied into `tests/test_edi_triage.py` |

Files touched:

```
edi_triage.py                 new: models, taxonomy, prompt, mock lookup, Bedrock call, CLI
fixtures/*.json               new: 10 transactions, each with a mock_result block
tests/test_edi_triage.py      new
assistant.py                  + POST /triage/edi
mcp_server.py                 + triage_edi_transaction tool
docs/EDI_TRIAGE.md            new: what it is, what is real, how to run
docs/EDI_TRIAGE_ROADMAP.md    this file
README.md, docs/ARCHITECTURE.md, docs/MCP_SERVER.md   one line or row each
```

Flow:

```
fixture.json (or request body)
   -> FailedTransaction (pydantic)
   -> detect_tier(snippet)               # deterministic, no LLM
   -> classify(statuses, error sources)  # deterministic, no LLM
   -> build_prompt(tx, tier, leaf)       # cheat sheet + full transaction as JSON
   -> run_edi_triage(mock | bedrock)     # LLM does hypotheses, reply, ticket two
   -> dict: transaction_id, tier, classification, hypotheses, customer_reply, ticket_two, mode
```

Key design point to say out loud in the interview: **classification is code, not the model.** The status enums are documented and finite, so a 30-line function does it and a test proves it. The model only does the parts that need judgment: ranking causes, writing the reply, proposing the ticket-two action. That keeps the demo cheap, testable, and honest about what the LLM adds.

Second point: the old incident prompt only passed evidence counts to the model. The EDI prompt passes the whole transaction. That is a lesson learned, and it is why the fixtures carry `context` and `customer_note`.

Output shape:

```json
{
  "transaction_id": "...",
  "tier": "orderful_json",
  "classification": "invalid.guideline",
  "hypotheses": [
    {"rank": 1, "hypothesis": "...", "confidence": "high", "evidence": ["errors[0].message"], "check": "Open ?tab=errors and confirm the DTM02 raw value"}
  ],
  "customer_reply": "...",
  "ticket_two": {
    "kind": "rule | knowledge_article | alert | mapping_test | partner_contact",
    "title": "...",
    "why": "...",
    "effort": "S | M | L"
  },
  "mode": "mock | bedrock"
}
```

`ticket_two.kind` is a closed list on purpose. It is the field the interviewer will look at.

## 3. Fixtures

Every fixture is one JSON file with the same shape. Field names copy the Orderful transaction API where one exists, so the interviewer sees familiar names.

```json
{
  "_note": "what is invented and what is borrowed from the docs",
  "id": "0192f3a1-...",
  "direction": "in",
  "stream": "live",
  "ediTransactionType": "850_PURCHASE_ORDER",
  "senderId": "RETAILER01",
  "receiverId": "ACMEFOODS",
  "validationStatus": "INVALID",
  "deliveryStatus": "PENDING",
  "acknowledgmentStatus": "NOT_ACKNOWLEDGED",
  "errors": [{"path": "...", "code": "...", "message": "...", "source": "guideline"}],
  "snippet": "first lines of the payload, enough to show the tier",
  "customer_note": "what the customer wrote in the ticket",
  "context": {"anything a support engineer would have on screen"},
  "mock_result": {"the canned triage returned in mock mode"}
}
```

`errors[]` reuses the acknowledgment API shape (`path`, `code`, `message`). The transaction API does not document an errors array, so the docs say this field is modeled on the acknowledgment endpoint and the Validation Errors tab. `source` records where the error surfaced; in the product that is the tab or notification it came from.

| # | File | Leaf | `errors[].message` (invented, doc-shaped) | Ticket two |
|---|---|---|---|---|
| 1 | `unprocessed_unknown_partner.json` | unprocessed | `The Trading Partnership doesn't exist in Orderful for sender RETAILER01 and receiver ACMEFOOD` (one character off on purpose) | knowledge_article: ISA ID mismatch checklist |
| 2 | `invalid_missing_mandatory_n1.json` | invalid.guideline | `Mandatory segment N1 (Ship To, N101=ST) is missing. Guideline: RETAILER01 850 v2` | rule: copy Bill To into Ship To when absent |
| 3 | `invalid_date_format_dtm.json` | invalid.guideline | `Element DTM02 value "08-28-2026" does not match data type DT (CCYYMMDD)` | rule: FORMATDATE on DTM02 |
| 4 | `invalid_rule_lookup_failed.json` | invalid.rule | `Rule "UPC to vendor item" failed: LOOKUPDATA("UPC_TO_VN", "01234567890") returned no match` | rule: wrap in IFERROR plus weekly unmapped-UPC report |
| 5 | `invalid_mapping_jsonata.json` | invalid.mapping | `Transformation error: required value "purchaseOrderNumber" resolved to undefined at $.beginningSegmentForPurchaseOrder[0].purchaseOrderNumber` | mapping_test: regression test with the customer's sample |
| 6 | `delivery_pending_channel.json` | delivery.pending | no `errors[]`; PENDING for 47 minutes, self-hosted SFTP, channel note `Connection timed out after 30s to sftp.acmefoods.example:22` | alert: PENDING older than 15 minutes |
| 7 | `delivery_failed_as2_mdn.json` | delivery.failed | `Received an MDN with errors: The signature is unverified` (verbatim from the AS2 troubleshooting page) | alert: certificate expiry watcher |
| 8 | `ack_rejected_997.json` | ack.rejected | `Purchase order references an unknown ship-to location` (verbatim from the acknowledgment API example) | rule: validate ship-to against partner location list |
| 9 | `ack_overdue_quiet_partner.json` | ack.overdue | no errors; OVERDUE, delivered 26 hours ago, seven others from the same partner also overdue | partner_contact: nothing to engineer |
| 10 | `tier_ambiguous_x12_passthrough.json` | invalid.guideline on passthrough | `snippet` is raw `ISA*00*...~ST*856*0001~`; `Element BSN05 (Hierarchical Structure Code) value "0001" is not allowed by RETAILER01 856 guideline. Allowed: "0004" (Shipment, Order, Item)` | knowledge_article: 856 structure codes by partner |

Fixture 10 is the "which tier are you on" case from the brief. Fixtures 1 and 9 are the two that test whether the agent knows when NOT to blame the customer.

## 4. Milestones (each one is demo-able on its own)

| # | Name | What exists after | Demo line if you stop here |
|---|---|---|---|
| M0 | Docs | This roadmap, `EDI_TRIAGE.md`, one line each in README, ARCHITECTURE, MCP_SERVER | "Here is how I scoped it before writing code." |
| M1 | Module + fixtures + tests | `edi_triage.py` runs every fixture in mock mode; `tests/test_edi_triage.py` green | "The status axes are finite. This is the deterministic part, with tests." **Minimum bar for the interview.** |
| M2 | REST + MCP | `POST /triage/edi` and `triage_edi_transaction` return the same dict; full `pytest` and `ruff` green | "Same logic, three surfaces, one implementation." |
| M3 | Bedrock live | `--bedrock` on two fixtures with real AWS credentials; real output pasted into `EDI_TRIAGE.md` | "Same run, real model. Here is where the mock and the model disagreed." |

Cut order if late: M3 first. Never cut M1 or the tests.

Verification:

```bash
ruff check . && pytest -q
```

```bash
python edi_triage.py fixtures/invalid_date_format_dtm.json
```

```bash
BEDROCK_MOCK=false python edi_triage.py fixtures/ack_rejected_997.json --bedrock
```

## 5. Three-minute demo script

Setup before the call: terminal open in the repo on the `edi-failure-triage` branch, font large, `pytest -q` already green in scrollback, `docs/EDI_TRIAGE.md` open in a browser tab, fixtures 3 and 9 open in an editor tab.

**0:00 to 0:30, frame it.** Say: "After I read the posting I built a small thing over a weekend on a branch of my existing incident-triage agent. It points the same pattern at your documented transaction statuses. Everything is invented and shaped after your public docs. I have not used the product." Show the first paragraph of `EDI_TRIAGE.md`.

**0:30 to 1:00, show the input.** Open `fixtures/invalid_date_format_dtm.json`. Point at three things: the three status fields with the same enum names as the API, the `errors[]` message, and the `snippet` that shows it is Orderful JSON, not passthrough.

**1:00 to 1:45, run it.** Run:

```bash
python edi_triage.py fixtures/invalid_date_format_dtm.json
```

Walk the output top to bottom. Tier: Orderful JSON. Classification: `invalid.guideline`, and say "that part is code, not the model, because the enums are documented." Hypotheses: DTM02 in MMDDYYYY, rank one; a rule ran before validation and reformatted it wrong, rank two. Customer reply: read the first two sentences. Ticket two: a `FORMATDATE` rule on inbound 850 for this partner, effort S.

**1:45 to 2:30, run the one where nothing is broken.** Run:

```bash
python edi_triage.py fixtures/ack_overdue_quiet_partner.json
```

Say: "This is the case I care about. Delivered 26 hours ago, no 997. The right answer is not an engineering ticket, it is a partner contact and a template. The agent says so." Point at `ticket_two.kind: partner_contact`.

**2:30 to 3:00, the honest part and the ask.** Say: "What is fake: the fixtures. What is real: the taxonomy, the tests, the prompt, the Bedrock call, and the REST and MCP surfaces it shares with the incident path. What I would do on day one with real access: swap the fixture loader for the transaction API and the Validation Errors tab, and start counting which `ticket_two.kind` shows up most. That count is the backlog for making the front line smaller." Stop talking.

If asked "why not let the model classify": "Because I can test code. I cannot test a vibe. The model gets the parts that need judgment."

If asked "what broke": be ready with one real thing from M3, for example the model wrapping the JSON in a code fence and the parser stripping it.

## 6. Honest framing (goes in `EDI_TRIAGE.md`, near the top)

> I built this in one weekend after reading the Product Support Engineer posting and Orderful's public docs. It is a domain port of the triage agent in this repo: same prompt shape, same ranked-hypothesis output, pointed at Orderful's documented transaction statuses instead of AWS incidents. The failure cases are invented. They are shaped after the status enums, the AS2 troubleshooting page, and the acknowledgment API example in the docs, not after any real customer data. I have not used the Orderful product. Where I guessed at how an error surfaces, I say so in the fixture's `_note` field.

Rules for the docs:

- Link every doc page the fixtures borrow wording from.
- No Orderful logo, no color scheme copy.
- One line on what would be different with real access: the input would come from the transaction API and the Validation Errors tab, not from a JSON file.
- US spelling throughout. No em dashes.
