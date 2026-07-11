# R5 Bundle 5.4 — Forecast and valuation input onboarding

## Background

Forecast and valuation are derived layers. They may only be accepted after official disclosure, market and peer inputs have valid evidence anchors.

## Goal

Create reviewed `forecast_assumptions` and `valuation_inputs` records tied to accepted evidence/metrics, while preserving scenarios, method eligibility and uncertainty.

## Preconditions

Cards 5.2 and 5.3 must have accepted evidence chains or this card closes blocked. Do not create assumptions to compensate for missing base data.

## Allowed files

- `data/reviewed_inputs/wf_20260703_stock_first_002837_invic/forecast_assumptions/**`
- `data/reviewed_inputs/wf_20260703_stock_first_002837_invic/valuation_inputs/**`
- evidence/claim/metric/model manifests
- staging-only forecast/valuation candidate artifacts
- existing forecast/valuation subpack inputs and candidate outputs
- focused validators/tests
- `reports/p1_6/R5_BUNDLE_5_4_FORECAST_VALUATION_INPUT_READOUT.md`

## Forbidden scope

- Do not present assumptions as facts.
- Do not accept an assumption without evidence/metric/claim links and a method note.
- Do not activate valuation methods whose required inputs are missing or stale.
- Do not use a target price, rating or expected return as an evidence source.
- Do not promote registries or open sample-quality/P2.

## Required work

1. Forecast assumptions:
   - explicit scenario (`base`, `upside`, `downside` or existing canonical vocabulary);
   - period, unit, formula/method and dependency IDs;
   - reviewer and limitations;
   - sensitivity or uncertainty range for material drivers;
   - separation of management guidance from analyst/model assumptions.
2. Valuation inputs:
   - valuation date, share-count basis, net debt/cash bridge and currency;
   - peer/market source links;
   - method eligibility and exclusion reasons;
   - consistent forecast period and accounting basis;
   - scenario outputs described as research estimates, not action instructions.
3. Run existing forecast/valuation interlock and validators in candidate/staging mode.
4. Reconcile every promoted-ready field to accepted input IDs.

## Acceptance gate

- All critical forecast assumptions and valuation inputs required for `reviewed_input_research_draft` are accepted or the existing gate explicitly allows a degraded draft with visible TODOs.
- Method eligibility fails closed.
- No output contains direct trade, position or certainty language.

## Suggested commands

```bash
python scripts/validate_r5_reviewed_input_dropzone.py   --root data/reviewed_inputs/wf_20260703_stock_first_002837_invic/forecast_assumptions   --json reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_forecast_assumption_validation.json
python scripts/validate_r5_reviewed_input_dropzone.py   --root data/reviewed_inputs/wf_20260703_stock_first_002837_invic/valuation_inputs   --json reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_valuation_input_validation.json
python -m pytest -q tests/test_r5_bundle5_forecast_valuation_onboarding.py tests/test_r5_forecast_assumption_registry.py tests/test_r5_valuation_input_registry_and_interlock.py --tb=short -p no:cacheprovider
git diff --check
```
