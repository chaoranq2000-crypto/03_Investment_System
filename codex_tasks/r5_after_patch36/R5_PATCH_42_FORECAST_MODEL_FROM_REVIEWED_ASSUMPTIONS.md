# R5 Patch 42 - Forecast Model From Reviewed Assumptions

## Goal

Modify forecast model building so it consumes only the reviewed forecast assumption registry and keeps TODOs otherwise.

## Background

Patch 34 removed default forecast values. This patch should make the builder explicitly require reviewed assumptions before producing numeric revenue, margin, net profit or EPS forecasts.

## Allowed files

- `src/research/forecast_model_builder.py`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_forecast_model.py`
- `tests/test_r5_forecast_model_from_reviewed_assumptions.py`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/forecast_model.yaml` only if preserving TODO state or consuming reviewed local fixtures
- `reports/p1_6/R5_PATCH_42_FORECAST_MODEL_FROM_REVIEWED_ASSUMPTIONS_READOUT.md`

## Required behavior

1. Forecast builder must produce `TODO_MODEL_INPUT` for a metric if required assumptions are absent.
2. Numeric forecast output requires:
   - validated assumption registry,
   - evidence or metric anchors,
   - explicit period, unit and scenario,
   - no hidden TODOs.
3. The builder must separate:
   - historical metric anchors,
   - reviewed assumptions,
   - forecast outputs,
   - limitations.
4. Tests must cover:
   - all TODO path,
   - partial reviewed assumption path,
   - invalid assumption rejected path,
   - no segment attribution without disclosure.

## Tests

```bash
python -m py_compile src/research/forecast_model_builder.py
python -m pytest -q tests/test_r5_forecast_model_from_reviewed_assumptions.py tests/test_r5_forecast_valuation_interlock.py --tb=short
```

## Readout

Add `reports/p1_6/R5_PATCH_42_FORECAST_MODEL_FROM_REVIEWED_ASSUMPTIONS_READOUT.md`.


## Global boundaries

- Do not call live APIs.
- Do not download unreviewed external files.
- Do not generate buy / sell / hold / position-size advice.
- Do not promote `TODO_*`, `MISSING_DISCLOSURE`, `LOW_CONFIDENCE_CLUE_ONLY`, or `evidence_id: null` into facts.
- Do not mark sample-quality or P2 ready unless the explicit readiness gate allows it.
- Do not rewrite historical legacy readouts; add canonical readouts only.
- Every patch must add a readout under `reports/p1_6/` with: files_added, files_modified, commands_run, exit_code, stdout/stderr summary, artifact_evidence, known_todos, and next_recommended_patch.
