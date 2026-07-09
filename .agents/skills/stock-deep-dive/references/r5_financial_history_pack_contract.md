# R5 Financial History Pack Contract

`R5_financial_history_pack` is a standalone R5 core research asset subpack.
It records reviewed financial history, financial quality checks and adjusted
profit bridges without creating business exposure facts.

Required root fields:

- `artifact_type`
- `schema_version`
- `status`
- `as_of_date`
- `currency`
- `periods`
- `income_statement`
- `balance_sheet`
- `cashflow_statement`
- `key_metrics`
- `financial_quality`
- `adjusted_profit_bridge`
- `cashflow_quality`
- `working_capital_flags`
- `roe_roic_commentary`
- `evidence_ids`
- `missing_items`

Allowed `status` values:

- `TODO`
- `partial`
- `ready`
- `blocked`

Metric row shape:

```yaml
metric_name: revenue
period: 2025A
value: null
unit: CNY
currency: CNY
evidence_id: null
metric_id: null
missing_reason: TODO_MODEL_INPUT
```

Rules:

- Non-null numeric values require `evidence_id` or `metric_id`.
- Null values require `missing_reason` or a matching entry in `missing_items`.
- `status: ready` is forbidden when required financial sections are empty.
- `status: ready` must not hide TODO or missing markers.
- This subpack is not evidence acquisition and must not call live APIs.
