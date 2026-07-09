# R5 Peer Snapshot Review Contract

Peer valuation context requires a reviewed peer set and dated peer metrics. A TODO peer stub may remain valid for a source-gapped draft, but it cannot support relative valuation language.

## Required Peer Fields

- `peer_id`
- `stock_code`
- `company_name`
- `exchange`
- `selection_reason`
- `segment_overlap`
- `source_evidence_ids`

## Required Metric Fields

- `as_of_date`
- `market_cap`
- `pe_ttm`
- `pb`
- `ps`
- `source_evidence_ids`

Optional metric fields include `forward_pe`, `gross_margin`, and `revenue_growth`.

`sample_quality_candidate` requires at least three reviewed peers, dated metrics, selection reasons, and evidence IDs for both peer selection and peer metrics.
