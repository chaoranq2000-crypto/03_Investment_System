# R5 Market / Peer Input Registry Contract

This registry is the only reviewed-input surface that R5 valuation and pilot gates may use for market and peer context. It does not fetch live data and does not authorize valuation conclusions.

## Artifact

- `artifact_type`: `R5_market_peer_input_registry`
- `schema_version`: `r5_market_peer_input_registry_v0.1`
- `workflow_id`
- `stock_code`
- `as_of_date`
- `review_status`: `pending`, `reviewed`, or `explicitly_degraded_but_reviewed`
- `market_inputs`
- `peer_inputs`
- `allowed_usage`
- `blocking_rules`

## Review Rules

`pending` records may use `TODO_MARKET_DATA` and `TODO_PEER_DATA` with `evidence_id: null` and visible `missing_reason`.

`reviewed` and `explicitly_degraded_but_reviewed` require `as_of_date`. For `reviewed`, every core market or peer field must include an `evidence_id`. For `explicitly_degraded_but_reviewed`, unresolved fields may remain TODO only when the missing reason is visible and the reviewer explicitly limits usage to degraded draft or source-gapped pilot checks.

No market or peer input may be used for sample-quality or valuation output while `review_status` is `pending`.
