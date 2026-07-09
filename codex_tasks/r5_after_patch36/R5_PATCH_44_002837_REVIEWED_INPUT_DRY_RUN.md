# R5 Patch 44 - 002837 Reviewed Input Dry Run

## Goal

Run a controlled 002837 dry-run using the reviewed-input contracts. This patch should not require real market/peer/forecast values; it should prove the workflow correctly remains blocked or source-gapped unless reviewed fixtures exist.

## Background

The 002837 pack is the current pilot artifact. The next dry-run must prove that reviewed-input paths do not hide gaps and that the system can distinguish TODO stubs from reviewed inputs.

## Allowed files

- `tests/test_r5_002837_reviewed_input_dry_run.py`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_reviewed_input_dry_run_result.yaml`
- `reports/p1_6/R5_PATCH_44_002837_REVIEWED_INPUT_DRY_RUN_READOUT.md`

## Required behavior

1. Dry-run consumes:
   - `R5_evidence_request_queue.yaml`
   - market snapshot stub or reviewed fixture
   - peer snapshot stub or reviewed fixture
   - forecast assumption registry stub or reviewed fixture
   - valuation input registry stub or reviewed fixture
2. Dry-run result must state:
   - `reviewed_market_inputs_available`
   - `reviewed_peer_inputs_available`
   - `reviewed_forecast_assumptions_available`
   - `reviewed_valuation_inputs_available`
   - `allowed_report_level`
   - `remaining_todos`
3. With only stubs, result must not exceed `source_gapped_research_draft`.
4. If reviewed fixtures are included, they must be clearly marked fixture-only and must not be confused with real reviewed evidence.

## Tests

```bash
python -m pytest -q tests/test_r5_002837_reviewed_input_dry_run.py --tb=short
```

## Readout

Add `reports/p1_6/R5_PATCH_44_002837_REVIEWED_INPUT_DRY_RUN_READOUT.md`.


## Global boundaries

- Do not call live APIs.
- Do not download unreviewed external files.
- Do not generate buy / sell / hold / position-size advice.
- Do not promote `TODO_*`, `MISSING_DISCLOSURE`, `LOW_CONFIDENCE_CLUE_ONLY`, or `evidence_id: null` into facts.
- Do not mark sample-quality or P2 ready unless the explicit readiness gate allows it.
- Do not rewrite historical legacy readouts; add canonical readouts only.
- Every patch must add a readout under `reports/p1_6/` with: files_added, files_modified, commands_run, exit_code, stdout/stderr summary, artifact_evidence, known_todos, and next_recommended_patch.
