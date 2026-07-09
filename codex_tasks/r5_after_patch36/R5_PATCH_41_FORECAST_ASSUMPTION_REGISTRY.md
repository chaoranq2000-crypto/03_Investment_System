# R5 Patch 41 - Forecast Assumption Registry

## Goal

Define and validate a registry of reviewed forecast assumptions before any numeric forecast can be produced.

## Background

Forecast is currently blocked by `TODO_MODEL_INPUT`. Patch 34 established that historical metric anchors are not forecast assumptions. This patch creates the reviewed assumption layer that sits between evidence/metrics and the forecast model.

## Allowed files

- `.agents/skills/stock-deep-dive/references/r5_forecast_assumption_registry_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_forecast_assumption_registry.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_forecast_assumptions.py`
- `tests/test_validate_r5_forecast_assumptions.py`
- `reports/p1_6/R5_PATCH_41_FORECAST_ASSUMPTION_REGISTRY_READOUT.md`

## Required behavior

1. Define assumption fields:
   - `assumption_id`
   - `scope`: company, segment, product, margin, opex, tax, capex, cashflow
   - `periods`: 2026E-2028E or explicit range
   - `value` or `formula`
   - `unit`
   - `scenario`: base, bull, bear
   - `supporting_evidence_ids`
   - `supporting_metric_ids`
   - `rationale`
   - `limitations`
   - `review_status`
2. Validator must reject:
   - assumptions without reviewed evidence or metric anchors,
   - assumptions that map company-level revenue to a segment without disclosure,
   - bull/bear scenarios without base case,
   - assumptions that imply trading advice.
3. Validator may allow source-gapped assumption TODO rows but must not treat them as forecast-ready.

## Tests

```bash
python -m py_compile .agents/skills/stock-deep-dive/scripts/validate_r5_forecast_assumptions.py
python -m pytest -q tests/test_validate_r5_forecast_assumptions.py --tb=short
```

## Readout

Add `reports/p1_6/R5_PATCH_41_FORECAST_ASSUMPTION_REGISTRY_READOUT.md`.


## Global boundaries

- Do not call live APIs.
- Do not download unreviewed external files.
- Do not generate buy / sell / hold / position-size advice.
- Do not promote `TODO_*`, `MISSING_DISCLOSURE`, `LOW_CONFIDENCE_CLUE_ONLY`, or `evidence_id: null` into facts.
- Do not mark sample-quality or P2 ready unless the explicit readiness gate allows it.
- Do not rewrite historical legacy readouts; add canonical readouts only.
- Every patch must add a readout under `reports/p1_6/` with: files_added, files_modified, commands_run, exit_code, stdout/stderr summary, artifact_evidence, known_todos, and next_recommended_patch.
