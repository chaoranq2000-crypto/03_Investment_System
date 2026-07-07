# R5 Stock Evidence Plan Contract

## Purpose

The R5 stock evidence plan defines what `evidence-ingest` should register before an R5 stock research pack can be built. It is a schema and handoff plan, not a downloader.

## Required families

```text
official_filings
structured_financial_data
market_snapshot
peer_snapshot
industry_context
news_event_clues
investor_relations
source_gap_policy
```

Every evidence request must include:

```text
source_priority
required_for_pack
freshness_requirement
fallback_if_missing
```

Official disclosures must have higher priority than third-party summaries. Missing disclosures must remain `MISSING_DISCLOSURE`; do not invent facts or claims.

## Expected artifacts

```yaml
expected_artifacts:
  manifest_rows: true
  claim_candidates: true
  metric_candidates: true
  ingest_log: true
```

## Boundaries

- No downloader is added by this contract.
- No live API is called by the validator.
- No `data/raw/` or `data/processed/` artifact is modified.
- No real claims or metrics are generated.
