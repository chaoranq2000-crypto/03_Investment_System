# R5 Stock Evidence Plan Contract

## Purpose

`R5_stock_evidence_snapshot_plan` is a plan-only bridge from R5 source gaps to evidence-ingest work. It does not download files, call live APIs, or promote clues into facts.

## Required Boundary

- `implementation_boundary.no_live_api: true`
- `implementation_boundary.no_downloader_added: true`
- `implementation_boundary.plan_only: true`
- Missing values must remain `TODO_*`, `MISSING_DISCLOSURE`, or source-gap rows until evidence is ingested and reviewed.

## Required Families

- `official_filings`
- `structured_financial_metrics`
- `market_snapshot`
- `peer_snapshot`
- `industry_context_clues`
- `news_event_clues`
- `investor_relations`

Context-only families cannot independently prove business exposure, profit exposure, customer exposure, or revenue exposure.

## Bridge Fields

The bridge should expose these top-level fields for operators:

```yaml
stock_code:
workflow_id:
official_filings_needed:
structured_financial_data_needed:
market_snapshot_needed:
peer_snapshot_needed:
industry_data_needed:
analyst_consensus_needed:
news_and_event_sources_needed:
priority:
blocking_for_r5:
```

The same plan must also keep validator-compatible `evidence_requests` and `handoff_to_stock_deep_dive` sections.
