# EDI design notes

Historical source review: September 3, 2026. These notes explain the fixture taxonomy; they are not a current vendor API guarantee. See [EDI_TRIAGE.md](EDI_TRIAGE.md) for shipped interfaces, fixtures, and live-run limits.

## Status taxonomy

Orderful tracks a transaction on **three separate status axes**, not one. This matters: the demo should classify on the axis first, then the cause.

| Axis | Enum values (API, verbatim) | Failure values |
|---|---|---|
| `validationStatus` | `PROCESSING`, `VALID`, `INVALID` | `INVALID` |
| `deliveryStatus` | `PENDING`, `SENT`, `DELIVERED`, `FAILED` | `PENDING` (stuck), `FAILED` |
| `acknowledgmentStatus` | `NOT_ACKNOWLEDGED`, `ACCEPTED`, `REJECTED`, `OVERDUE`, `ACCEPTED_WITH_ERRORS` | `REJECTED`, `OVERDUE`, `ACCEPTED_WITH_ERRORS` |

Plus one pre-lifecycle bucket: **Unprocessed** (transaction was never created; API returned non-200). Causes listed in docs: sender/receiver/partnership/relationship does not exist, relationship still in testing, payload does not match Orderful JSON schema or X12 schema, format/version mismatch.

Design rationale recorded during the September 3 research:

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

Classification groups:

1. `unprocessed` (never created)
2. `invalid.guideline` (mandatory segment/element missing, bad code, bad DT format)
3. `invalid.rule` (rules engine produced a bad value or lookup failed)
4. `invalid.mapping` (JSONata / transformation, Validation Errors tab)
5. `delivery.pending` (stuck, channel not reached)
6. `delivery.failed` (channel reached, refused: AS2 MDN, HTTP 4xx/5xx, SFTP)
7. `ack.rejected` / `ack.overdue` (receiver backend said no, or said nothing)

## Deterministic classification

Code selects the integration tier and failure classification before a model is called. Bedrock supplies hypotheses, a draft reply, and a follow-up action. Mock mode returns fixture results instead. REST, MCP, and the CLI share `run_edi_triage`.

The fixtures are synthetic. Their `errors[]` shape borrows from the acknowledgment endpoint and Validation Errors tab; the transaction API does not document that array on the transaction itself. The added `source` field identifies where a diagnostic surfaced. Each fixture's `_note` describes its assumptions.

The EDI prompt includes the supplied transaction as JSON. This differs from the incident prompt and needs its own data-handling review before using real customer data. There is no Orderful API integration, EDI parser, or documentation retrieval in this demo.
