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

This is a local reviewed-input path, not the only possible Research evidence
intake path and not a parallel workflow.

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

`review_status` is one of `pending`, `accepted`, `rejected` or
`accepted_degraded`. `accepted_degraded` is allowed only with explicit
limitations and `sample_quality_allowed: false`; it may support limited draft
context but cannot independently unblock sample quality or P2.

Templates are empty contract examples. They are not evidence and cannot be
copied into an accepted registry row without reviewed metadata and evidence
anchors.

## Pending And Rejected Rows

`pending` and `rejected` rows may preserve TODO markers. They are useful for
auditability but must not unblock gates or registry promotion.

If the dropzone contains no accepted reviewed inputs, downstream output remains
source-gapped and no gate is promoted.

## Validation Command

```bash
python scripts/validate_r5_reviewed_input_dropzone.py --root data/reviewed_inputs/<workflow_id> --json reports/workflow_runs/<workflow_id>/reviewed_inputs_staging/dropzone_validation.json
```
