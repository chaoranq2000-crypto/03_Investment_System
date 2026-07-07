# R5 Forecast Model Contract

## Purpose

`r5_forecast_model_pack` carries 2026E-2028E forecast structure for R5 stock research. It is not a calculator and does not create real estimates by itself.

## Required shape

```yaml
artifact_type: R5_forecast_model_pack
status: TODO | partial | ready | blocked
sample_quality_allowed: false
forecast_years: [2026E, 2027E, 2028E]
scenarios:
  base_case: {}
  bull_case: {}
  bear_case: {}
sensitivity_table: []
source_gap_register: []
```

Each year in each scenario must expose:

```yaml
revenue:
  value:
  unit:
  assumption_id:
  missing_reason:
gross_margin:
net_profit_attributable:
eps:
```

Each forecast value must have `assumption_id` or `missing_reason`. Missing model inputs must remain `TODO_MODEL_INPUT`; do not fill values from memory or peer averages.

## Sensitivity table

Each row must contain:

```text
driver
change
impact_metric
impact_value
assumption_id_or_missing_reason
```

## Boundaries

- Do not calculate real forecasts in this validator.
- Do not present estimates as facts.
- Missing forecast model inputs block sample-quality status.
