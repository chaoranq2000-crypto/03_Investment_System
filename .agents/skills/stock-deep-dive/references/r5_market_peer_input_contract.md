# R5 Market And Peer Input Contract

status: `contract`

R5 market and peer inputs are reviewed-input artifacts. They can be TODO-visible
stubs for `source_gapped_research_draft`, but a `sample_quality_candidate` must
not pass without dated market data and a reviewed peer-selection method.

Market snapshot minimum fields:

- `artifact_type: R5_market_snapshot`
- `workflow_id`
- `stock_code`
- `status`
- `as_of_date` or `missing_reason: TODO_MARKET_DATA`
- `no_live_api: true`
- no unreviewed `current_price`, `market_cap`, `PE`, `PB`, or `PS`

Peer snapshot minimum fields:

- `artifact_type: R5_peer_snapshot`
- `workflow_id`
- `stock_code`
- `status`
- `peer_selection_method` or `missing_reason: TODO_PEER_DATA`
- `no_live_api: true`
- no unreviewed peer multiples or valuation claims

The validator must return blocking errors when `--level sample_quality_candidate`
is used and market or peer inputs still carry TODO/missing markers.
