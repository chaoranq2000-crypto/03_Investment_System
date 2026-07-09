# R5 Valuation Pack Contract

`R5_valuation_pack` records valuation context, source gaps and method readiness.
It must distinguish valuation analysis scaffolding from direct trading
instructions.

Required root fields:

- `artifact_type`
- `schema_version`
- `status`
- `as_of_date`
- `market_snapshot`
- `peer_valuation_context`
- `valuation_methods`
- `valuation_scenarios`
- `valuation_sensitivity`
- `limitations`
- `missing_items`
- `source_gap_register`

Market snapshot fields:

- `current_price`
- `market_cap`
- `share_count`
- `net_cash_or_net_debt`
- `enterprise_value`
- `pe_ttm`
- `forward_pe`
- `pb`
- `ps`
- `ev_ebitda`
- `as_of_date`
- `evidence_id` or `metric_id`
- `missing_reason`

Rules:

- Non-null market snapshot values require `evidence_id` or `metric_id`.
- Null market snapshot values require `TODO_MARKET_DATA` or explicit missing reason.
- Peer context rows with non-null multiples require evidence or metric support.
- `status: ready` requires a dated market snapshot, at least one peer context row,
  and at least one valuation method with supported output.
- Forecast-dependent ready methods must reference forecast assumptions or metrics.
- Direct trading instruction language is forbidden.
