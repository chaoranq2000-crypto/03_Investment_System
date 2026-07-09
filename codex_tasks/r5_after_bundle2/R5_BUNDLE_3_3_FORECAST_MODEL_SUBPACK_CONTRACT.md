# R5 Bundle 3.3 — Forecast model subpack contract and validator

## Background

Forecast remains one of the main blockers. Current TODO forecast fields must stay visible until reviewed assumptions exist. R5 needs a validator that requires explicit assumptions and prevents unsupported forecast numbers.

## Goal

Add a forecast model subpack contract, example YAML, validator and pytest coverage.

## Allowed files

- `.agents/skills/stock-deep-dive/references/r5_forecast_model_pack_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_forecast_model_pack.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_forecast_model_pack.py`
- `tests/test_validate_r5_forecast_model_pack.py`
- `.agents/skills/stock-deep-dive/SKILL.md` only for a minimal reference link
- `reports/p1_6/R5_BUNDLE_3_3_FORECAST_MODEL_SUBPACK_READOUT.md`

## Forbidden scope

- Do not create real forecasts.
- Do not fill 2026E-2028E values without reviewed assumptions.
- Do not read live consensus data.
- Do not write report prose.
- Do not mark sample-quality ready.

## Required contract behavior

The forecast model subpack must define:

```text
artifact_type
schema_version
status
as_of_date
model_type
forecast_years
scenarios
assumptions
forecast_table
required_metrics
sensitivity_tests
consensus_comparison
missing_items
source_gap_register
```

Required years:

```text
2026E
2027E
2028E
```

Required metrics:

```text
revenue
gross_margin
gross_profit
net_profit_attributable
eps
```

Validator rules:

- `forecast_years` must include 2026E-2028E.
- `base_case`, `bull_case` and `bear_case` must be represented, even if TODO.
- Forecast rows with non-null values require `assumption_id` plus `evidence_id` or `metric_id`.
- Forecast rows with null values require `missing_reason: TODO_MODEL_INPUT` or equivalent visible source gap.
- `status: ready` is forbidden while any required metric is missing in base case.
- `status: ready` requires at least one sensitivity test.
- `consensus_comparison` is optional, but if present must have `as_of_date` and source support.

## Acceptance criteria

- Example YAML parses and validates as `accepted_with_todos` if all forecasts are TODO.
- Validator fails unsupported non-null forecast rows.
- Validator fails `status: ready` without base-case required metrics and sensitivity tests.
- Pytest covers valid, TODO and invalid cases.

## Suggested tests

```bash
python -m py_compile .agents/skills/stock-deep-dive/scripts/validate_r5_forecast_model_pack.py
python .agents/skills/stock-deep-dive/scripts/validate_r5_forecast_model_pack.py --input .agents/skills/stock-deep-dive/assets/r5_forecast_model_pack.example.yaml
python -m pytest -q tests/test_validate_r5_forecast_model_pack.py --tb=short
git diff --check
```

## Output requirements

- List changed files.
- Include validator outcome.
- Include pytest result.
- Write the readout file.
