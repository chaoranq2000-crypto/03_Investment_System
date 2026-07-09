# R5 Reviewed Input Dropzone Contract

This reference defines the evidence-ingest boundary for manually supplied R5
reviewed inputs.

## Intake Boundary

Use this path pattern:

```text
data/reviewed_inputs/<workflow_id>/<input_type>/
```

Allowed `input_type` values:

- `market_snapshot`
- `peer_snapshot`
- `forecast_assumptions`
- `business_disclosure`
- `valuation_inputs`
- `sentiment_event_sources`

Evidence-ingest may help archive and describe local reviewed inputs, but it must
not call live APIs for this dropzone and must not treat templates as evidence.

## Accepted Rows

Rows with `review_status: accepted` or `review_status: accepted_degraded` must
include:

```text
input_id
workflow_id
stock_code
input_type
as_of_date
source_evidence_id
source_rank
review_status
reviewer
reviewed_at
capture_method
no_live_api
limitations
```

Accepted rows must not contain TODO markers, `MISSING_DISCLOSURE`,
`LOW_CONFIDENCE_CLUE_ONLY`, `evidence_id: null`, or
`source_evidence_id: null`.

## Pending And Rejected Rows

`pending` and `rejected` rows may preserve TODO markers. They are useful for
auditability but must not unblock gates or registry promotion.

## Validation Command

```bash
python scripts/validate_r5_reviewed_input_dropzone.py --root data/reviewed_inputs/<workflow_id> --json reports/workflow_runs/<workflow_id>/reviewed_inputs_staging/dropzone_validation.json
```
