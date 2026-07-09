# R5 Forecast Assumption Registry Contract

Numeric forecast outputs require a reviewed forecast assumption registry. Historical revenue, profit, or EPS metrics are anchors only; they are not forward assumptions.

## Artifact

- `artifact_type`: `R5_forecast_assumption_registry`
- `schema_version`: `r5_forecast_assumption_registry_v0.1`
- `workflow_id`
- `stock_code`
- `review_status`: `pending`, `reviewed`, or `explicitly_degraded_but_reviewed`
- `assumptions`
- `blocking_rules`

Each assumption row must include:

- `assumption_id`
- `driver`
- `periods`
- `value`
- `unit`
- `evidence_ids`
- `metric_ids`
- `missing_reason`
- `allowed_usage`
- `review_status`

Reviewed assumptions require at least one `evidence_id` or accepted `metric_id` plus `reviewer_note`. Pending assumptions may keep `TODO_MODEL_INPUT`, but they cannot unlock sample-quality or numeric forecasts.

Core drivers are `revenue_growth`, `gross_margin`, `opex`, `net_profit`, and `eps`. Missing core drivers must appear as explicit TODO rows.
