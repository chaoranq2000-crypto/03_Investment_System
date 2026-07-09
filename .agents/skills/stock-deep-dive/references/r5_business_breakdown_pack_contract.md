# R5 Business Breakdown Pack Contract

`R5_business_breakdown_pack` records reviewed business-line structure and keeps
missing disclosure visible. It must not promote product clues, customer clues,
capacity clues or order clues into revenue or profit facts without reviewed
metrics.

Required root fields:

- `artifact_type`
- `schema_version`
- `status`
- `as_of_date`
- `stock_code`
- `business_lines`
- `profit_pool_summary`
- `structural_contradictions`
- `linked_segments`
- `missing_items`
- `source_gap_register`

Each `business_lines` row supports:

- `business_name`
- `role`
- `revenue`
- `revenue_pct`
- `gross_margin`
- `gross_profit`
- `gross_profit_pct`
- `products`
- `customers`
- `capacity`
- `orders`
- `pricing_driver`
- `cost_driver`
- `linked_segments`
- `confidence`
- `evidence_ids`
- `missing_items`

Core metric object shape:

```yaml
value: null
unit: pct
evidence_id: null
metric_id: null
missing_reason: MISSING_DISCLOSURE
```

Rules:

- Non-null revenue, margin or profit metrics require `evidence_id` or `metric_id`.
- Null revenue, margin or profit metrics require `MISSING_DISCLOSURE`,
  `TODO_SOURCE_REQUIRED`, or evidence-backed `NOT_APPLICABLE`.
- `status: ready` requires no hidden missing disclosure.
- Product clues alone cannot set `confidence: high`.
