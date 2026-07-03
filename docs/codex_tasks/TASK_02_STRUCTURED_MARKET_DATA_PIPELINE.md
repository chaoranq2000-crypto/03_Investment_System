# TASK 02 — Implement Structured Financial / Market Data Pipeline

## Goal

Turn Tushare / Baostock / optional public adapters into standardized metric candidates, market snapshots and technical snapshots.

## Files to create or modify

```text
src/ingest/structured_api_pull.py
src/ingest/market_snapshot_pull.py
src/research/technical_snapshot_builder.py
src/research/market_sentiment_pack_builder.py
tests/test_structured_api_pull.py
tests/test_technical_snapshot_builder.py
```

## Required outputs

```text
data/raw/structured_api/<source>/<run_id>/
data/processed/normalized/<run_id>/
data/processed/candidates/metric_candidates_<run_id>.csv
reports/workflow_runs/<run_id>/technical_snapshot.yaml
reports/workflow_runs/<run_id>/market_sentiment_pack.yaml
```

## Minimum endpoints

```text
- stock_basic / company identity snapshot
- income statement
- balance sheet
- cashflow statement
- financial indicator
- daily price history
- daily_basic or equivalent valuation fields
```

## Rules

```text
- Structured snapshots are metric-only by default.
- Do not prove business exposure from Tushare/Baostock alone.
- Record source, endpoint, params hash, date, fields and adapter version.
- All market data must include as_of_date.
```

## Optional reference

Use a-stock-data only as adapter design reference. Do not paste a monolithic external SKILL.md into this project.
