# R5 Reviewed Input Dropzone Spec

status: active_contract

## Purpose

The reviewed-input dropzone is the only manual intake path for reviewed R5 market,
peer, forecast, valuation, business-disclosure and sentiment-event inputs.

It exists to add reviewed local inputs without live API calls and without turning
visible source gaps into facts.

## Path Pattern

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

## Required Metadata For Accepted Inputs

Every `accepted` or `accepted_degraded` reviewed input must include:

- `input_id`
- `workflow_id`
- `stock_code`
- `input_type`
- `as_of_date`
- `source_evidence_id`
- `source_rank`
- `review_status`
- `reviewer`
- `reviewed_at`
- `capture_method`
- `no_live_api`
- `limitations`

`review_status` must be one of:

- `pending`
- `accepted`
- `rejected`
- `accepted_degraded`

## Accepted-Only Boundary

Rows with `review_status: accepted` or `review_status: accepted_degraded` must
not contain:

- `TODO_MARKET_DATA`
- `TODO_PEER_DATA`
- `TODO_MODEL_INPUT`
- `TODO_SOURCE_REQUIRED`
- `MISSING_DISCLOSURE`
- `LOW_CONFIDENCE_CLUE_ONLY`
- `evidence_id: null`
- `source_evidence_id: null`

`accepted_degraded` can only be used when limitations are explicit and
`sample_quality_allowed` is false. It can support limited draft context, but it
must not unblock sample-quality or P2 by itself.

## Template Boundary

Templates under `templates/` are empty contract examples only:

- They are not evidence.
- They do not unblock gates.
- They must not be copied into registries as accepted rows without reviewed
  metadata and evidence anchors.

## Validation

Use:

```bash
python scripts/validate_r5_reviewed_input_dropzone.py --root data/reviewed_inputs/<workflow_id> --json <output.json>
```

The validator emits:

```text
status
checked_files
accepted_count
accepted_degraded_count
pending_count
rejected_count
failed_count
issues
```

If no accepted reviewed inputs are present, downstream gates must preserve
`source_gapped_research_draft`.
