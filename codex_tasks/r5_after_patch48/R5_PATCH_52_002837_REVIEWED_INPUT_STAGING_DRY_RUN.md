# R5 Patch 52 - 002837 reviewed input staging dry run

## Goal

Run a 002837 staging dry run using the reviewed-input dropzone. The dry run must prove that, without accepted reviewed rows, the current 002837 pack remains blocked/source-gapped.

## Background

The existing dry-run uses stub registries and records all reviewed input flags as false. This patch should add a real staging path that will later accept manually reviewed inputs, while still keeping the current state closed if no accepted data exists.

## Allowed files

- `scripts/build_r5_reviewed_input_staging.py`
- `tests/test_r5_002837_reviewed_input_staging.py`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/reviewed_inputs_staging/README.md`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_reviewed_input_staging_result.yaml`
- `reports/p1_6/R5_PATCH_52_002837_REVIEWED_INPUT_STAGING_DRY_RUN_READOUT.md`

## Required behavior

1. Consume:

```text
data/reviewed_inputs/wf_20260703_stock_first_002837_invic/
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_request_review_ledger.yaml
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_reviewed_input_dry_run_result.yaml
```

2. Produce `R5_reviewed_input_staging_result.yaml` with:

```text
reviewed_market_inputs_available
reviewed_peer_inputs_available
reviewed_forecast_assumptions_available
reviewed_business_disclosure_available
reviewed_valuation_inputs_available
accepted_count
accepted_degraded_count
pending_count
rejected_count
remaining_todos
allowed_report_level
sample_quality_report_allowed
p2_allowed
```

3. With no accepted reviewed inputs, the result must keep:

```text
allowed_report_level: source_gapped_research_draft
sample_quality_report_allowed: false
p2_allowed: false
```

4. Do not write accepted rows into registries in this patch.
5. Do not use templates as evidence.

## Tests

```bash
python -m py_compile scripts/build_r5_reviewed_input_staging.py scripts/validate_r5_reviewed_input_dropzone.py
python -m pytest -q tests/test_r5_002837_reviewed_input_staging.py tests/test_validate_r5_reviewed_input_dropzone.py --tb=short
python scripts/build_r5_reviewed_input_staging.py --workflow-id wf_20260703_stock_first_002837_invic --json reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_reviewed_input_staging_result.yaml
```

## Readout

Add `reports/p1_6/R5_PATCH_52_002837_REVIEWED_INPUT_STAGING_DRY_RUN_READOUT.md`.

## Global boundaries

- Do not call live APIs.
- Do not modify existing R5 registries.
- Do not generate any report.
- Do not mark sample-quality or P2 ready.
