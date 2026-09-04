# EDI Failure Triage

I built this in one weekend after reading the Product Support Engineer posting and Orderful's public docs. It is a domain port of the triage agent in this repo: same prompt shape, same ranked-hypothesis output, pointed at Orderful's documented transaction statuses instead of AWS incidents. The failure cases are invented. They are shaped after the status enums, the AS2 troubleshooting page, and the acknowledgment API example in the docs, not after any real customer data. I have not used the Orderful product. Where I guessed at how an error surfaces, I say so in the fixture's `_note` field.

Planning notes, taxonomy check, and the demo script are in [EDI_TRIAGE_ROADMAP.md](EDI_TRIAGE_ROADMAP.md).

## What it does

In: one failed transaction (status fields, error text, a payload snippet, the customer's note).

Out:

1. **Tier**: which integration path the customer is on (Mosaic, Orderful JSON, X12 passthrough, file over MFT). Code, not the model.
2. **Classification**: one of `unprocessed`, `invalid.guideline`, `invalid.rule`, `invalid.mapping`, `delivery.pending`, `delivery.failed`, `ack.rejected`, `ack.overdue`. Code, not the model.
3. **Hypotheses**: two or three ranked root causes with the evidence field each one rests on and one concrete thing to check.
4. **Customer reply**: a short draft that says what happened, whose side it is on, what to do, and whether to resend.
5. **Ticket two**: the rule, knowledge article, alert, mapping test, or partner contact that stops the next ticket. `kind` is a closed list so it can be counted.

Classification is deterministic because the status enums are documented and finite. The model only does the parts that need judgment.

## Run it

Mock mode, no AWS credentials:

```bash
python edi_triage.py fixtures/invalid_date_format_dtm.json
```

Raw JSON:

```bash
python edi_triage.py fixtures/ack_overdue_quiet_partner.json --json
```

Live Bedrock (needs AWS credentials and `BEDROCK_MODEL_ID`):

```bash
python edi_triage.py fixtures/ack_rejected_997.json --bedrock
```

Same logic over REST and MCP, gated by the same `BEDROCK_MOCK` flag as the incident path:

```bash
curl -s -X POST http://localhost:8001/triage/edi \
  -H 'Content-Type: application/json' \
  -d @fixtures/delivery_failed_as2_mdn.json
```

The MCP tool is `triage_edi_transaction`. See [MCP_SERVER.md](MCP_SERVER.md).

In the browser, open `/` and pick any item under "EDI Transactions" in the sidebar. The Triage tab shows the output; the Transaction tab shows the input.

## Fixtures

| File | Classification | Tier | Ticket two |
|---|---|---|---|
| `unprocessed_unknown_partner.json` | unprocessed | orderful_json | knowledge_article |
| `invalid_missing_mandatory_n1.json` | invalid.guideline | orderful_json | rule |
| `invalid_date_format_dtm.json` | invalid.guideline | orderful_json | rule |
| `invalid_rule_lookup_failed.json` | invalid.rule | orderful_json | rule |
| `invalid_mapping_jsonata.json` | invalid.mapping | orderful_json | mapping_test |
| `delivery_pending_channel.json` | delivery.pending | orderful_json | alert |
| `delivery_failed_as2_mdn.json` | delivery.failed | orderful_json | alert |
| `ack_rejected_997.json` | ack.rejected | orderful_json | rule |
| `ack_overdue_quiet_partner.json` | ack.overdue | orderful_json | partner_contact |
| `tier_ambiguous_x12_passthrough.json` | invalid.guideline | x12_passthrough | knowledge_article |

Each fixture carries a `mock_result` block. Mock mode returns it by transaction id, falls back to the first fixture with the same classification, and then to a generic "nothing is broken" result. `tests/test_edi_triage.py` runs every fixture and fails if one is added without an expected tier and classification.

## What the fixtures borrow from the docs

- Status enums and field names: https://docs.orderful.com/reference/transactionv4controller_gettransaction
- `errors[]` shape and the ship-to example: https://docs.orderful.com/reference/compositetransactioncontroller_getacknowledgment
- Unprocessed causes: https://docs.orderful.com/docs/unprocessed-transactions
- Guideline requirement wording and DT data type: https://docs.orderful.com/docs/enter-guideline-requirements
- Rules run before validation, `LOOKUPDATA`, `FORMATDATE`, `IFERROR`: https://docs.orderful.com/docs/use-the-rules-engine
- Validation Errors tab and `?tab=errors`: https://docs.orderful.com/docs/fix-an-invalid-transaction
- AS2 error text: https://docs.orderful.com/docs/as2-troubleshooting
- Delivery success and retry rules per channel: https://docs.orderful.com/docs/transaction-success-and-failure
- Integration tiers: https://docs.orderful.com/reference/overview

The transaction API does not document an errors array on the transaction itself. The fixtures put one there anyway, modeled on the acknowledgment endpoint and the Validation Errors tab, because that is what a support engineer has on screen.

## What is reused from the incident path

- `triage_core._bedrock_client()` and `BEDROCK_MODEL_ID` for live mode, imported lazily so mock mode never loads boto3.
- The `BEDROCK_MOCK` flag, the rate limiter (it matches the `/triage` prefix), and the MCP server.
- The test style, including the fake Bedrock client.

Not reused: Langfuse tracing. The incident path has it; this path does not yet.

## Live run notes

First live attempt, 2026-09-03, `us-east-2`, with a fresh IAM user that has only `AmazonBedrockFullAccess`:

- Claude on Bedrock needs the cross-region inference profile id, not the bare model id. Use `BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-6` (or another `us.anthropic...` id from `aws bedrock list-inference-profiles`). The repo default, Titan Text Express, is not a good fit for strict JSON.
- Opus 5 and Sonnet 5 returned `AccessDeniedException: not available for this account`. The fallback path caught it and returned a low-confidence result with `ticket_two.kind: alert`, exactly as the tests expect.
- Every enabled model then returned `ThrottlingException: Too many tokens per day`. That is the daily token quota on a new Bedrock account, not a burst limit, and it applies before the first successful call. The fix is a quota increase in Service Quotas, or waiting for the account to age.

So the live path has been exercised end to end through both error branches. A successful model response is still pending the quota change.

## Limits

- No calls to the Orderful API. With real access, the input would come from the transaction endpoint and the Validation Errors tab instead of a JSON file.
- No EDI parsing. The `snippet` is text the model reads.
- No retrieval over the docs. The prompt carries a short cheat sheet with URLs.
- The browser console lists the ten fixtures under "EDI Transactions" and calls the same endpoint. It does not let you paste your own transaction yet.
- The sibling [n8n-workflow-as-code](https://github.com/h-vance/n8n-workflow-as-code) repo is where the ticket-two automations (the PENDING alert, the certificate watcher) would run. None are built.
