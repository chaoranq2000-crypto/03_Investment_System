# R5 Market Snapshot Review Contract

R5 market and technical language requires a reviewed, dated market snapshot. This contract supports TODO stubs without promoting them into valuation or technical-state facts.

Required reviewed fields:

- `as_of_date`
- `currency`
- `current_price`
- `market_cap`
- `share_count`
- `pe_ttm`
- `pb`
- `ps`
- `source_evidence_ids`
- `allowed_usage`

Optional fields include return history, moving averages, turnover, volume percentile, and 52-week range fields.

If any numeric market field is present without `source_evidence_ids`, the snapshot is blocked. If required fields are null or status is `TODO_MARKET_DATA`, the allowed level remains `source_gapped_research_draft`.
