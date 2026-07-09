# R5 Forecast Model Pack Contract

`R5_forecast_model_pack` records forecast structure and assumptions. It must
preserve `TODO_MODEL_INPUT` until reviewed assumptions and supporting evidence or
metrics exist.

Required root fields:

- `artifact_type`
- `schema_version`
- `status`
- `as_of_date`
- `model_type`
- `forecast_years`
- `scenarios`
- `assumptions`
- `forecast_table`
- `required_metrics`
- `sensitivity_tests`
- `consensus_comparison`
- `missing_items`
- `source_gap_register`

Required forecast years:

- `2026E`
- `2027E`
- `2028E`

Required metrics:

- `revenue`
- `gross_margin`
- `gross_profit`
- `net_profit_attributable`
- `eps`

Rules:

- `base_case`, `bull_case` and `bear_case` must be represented.
- Non-null forecast rows require `assumption_id` and `evidence_id` or `metric_id`.
- Null forecast rows require `missing_reason: TODO_MODEL_INPUT` or an equivalent visible source gap.
- `status: ready` is forbidden while any required metric is missing in the base case.
- `status: ready` requires at least one sensitivity test.
- `consensus_comparison`, when present, requires `as_of_date` and source support.
