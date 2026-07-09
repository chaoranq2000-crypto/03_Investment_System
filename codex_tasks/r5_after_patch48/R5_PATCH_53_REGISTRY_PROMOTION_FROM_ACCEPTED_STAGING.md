# R5 Patch 53 - Registry promotion from accepted staging only

## Goal

Allow accepted reviewed-input staging rows to update R5 reviewed registries, while proving that pending or TODO rows never unblock the pilot.

## Background

The current registries are pending and contain TODOs. Promotion must be evidence-bound and accepted-only. This patch should add the mechanism without inventing data.

## Allowed files

- `scripts/promote_r5_reviewed_inputs_to_registries.py`
- `tests/test_r5_reviewed_input_registry_promotion.py`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_reviewed_input_registry_promotion_result.yaml`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_market_peer_input_registry.yaml`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_forecast_assumption_registry.yaml`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_request_review_ledger.yaml`
- `reports/p1_6/R5_PATCH_53_REGISTRY_PROMOTION_FROM_ACCEPTED_STAGING_READOUT.md`

## Required behavior

1. Promotion consumes `R5_reviewed_input_staging_result.yaml` and dropzone files.
2. Only rows with `review_status: accepted` may unblock reviewed flags.
3. Rows with `accepted_degraded` may populate limitations but must not allow sample-quality.
4. Pending/rejected rows must keep registry status pending or degraded.
5. Promotion must fail if an accepted row has:

```text
source_evidence_id: null
as_of_date: null
TODO_*
MISSING_DISCLOSURE
LOW_CONFIDENCE_CLUE_ONLY
```

6. If no accepted reviewed rows exist, the promotion result must say:

```text
promotion_status: no_accepted_inputs
registries_changed: false
allowed_report_level: source_gapped_research_draft
```

7. Do not overwrite existing source-gap visibility.
8. Do not change source-gapped report facts.

## Tests

```bash
python -m py_compile scripts/promote_r5_reviewed_inputs_to_registries.py scripts/build_r5_reviewed_input_staging.py scripts/validate_r5_reviewed_input_dropzone.py
python -m pytest -q tests/test_r5_reviewed_input_registry_promotion.py tests/test_r5_002837_reviewed_input_staging.py --tb=short
python scripts/promote_r5_reviewed_inputs_to_registries.py --workflow-id wf_20260703_stock_first_002837_invic --json reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_reviewed_input_registry_promotion_result.yaml
```

## Readout

Add `reports/p1_6/R5_PATCH_53_REGISTRY_PROMOTION_FROM_ACCEPTED_STAGING_READOUT.md`.

## Global boundaries

- Do not call live APIs.
- Do not invent market/peer/forecast values.
- Do not mark sample-quality or P2 ready.
- Do not output direct trading advice.
