# Source Gap Report

workflow_id: wf_20260703_data_layer_002837_invic
as_of_date: 2026-07-01

## Available Data Packs

| pack | status | evidence |
|---|---|---|
| financial_metric_pack.csv | available | run-local metrics from Tushare income fixture |
| valuation_snapshot.yaml | available_with_todo | Tushare daily_basic fixture; pe_forward remains TODO_MARKET_DATA |
| technical_snapshot.yaml | available_with_todo | Baostock K-line fixture; MA20/MA60/pct_chg_20d/pct_chg_60d and weekly MA fields remain INSUFFICIENT_PRICE_WINDOW because the fixture price window is short |
| peer_market_snapshot.csv | available_with_low_todo | Fixture-only peer snapshot generated from company_universe.csv; live peer market data hardening remains pending |
| official_disclosure_reconciliation_stub.md | available_with_todo | Structured financial metrics still require official disclosure reconciliation |

## Explicit Gaps

| gap_id | severity | status | handling |
|---|---|---|---|
| DL-GAP-001 | low | lowered_to_low_todo | peer_market_snapshot.csv generated in fixture-only mode; live peer market data hardening remains pending |
| DL-GAP-002 | medium | TODO_DISCLOSURE_RECONCILIATION | structured financial metrics need official filing reconciliation before material company facts |
| DL-GAP-003 | low | TODO_MARKET_DATA | pe_forward missing from fixture and left as TODO_MARKET_DATA |

## Boundary Notes

- Tushare and Baostock outputs are metric-only.
- Peer valuation output is context-only and non-conclusive.
- No business exposure fact is created from structured snapshots.
- Missing fields stay visible as TODO or INSUFFICIENT_PRICE_WINDOW.
