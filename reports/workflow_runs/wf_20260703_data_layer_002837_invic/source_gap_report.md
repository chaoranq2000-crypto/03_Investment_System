# Source Gap Report

workflow_id: wf_20260703_data_layer_002837_invic
as_of_date: 2026-07-01

## Available Data Packs

| pack | status | evidence |
|---|---|---|
| financial_metric_pack.csv | available | run-local metrics from Tushare income fixture |
| valuation_snapshot.yaml | available_with_todo | Tushare daily_basic fixture; pe_forward remains TODO_MARKET_DATA |
| technical_snapshot.yaml | available_with_todo | Baostock K-line fixture; MA20/MA60 remain MISSING_DISCLOSURE because fixture window is short |

## Explicit Gaps

| gap_id | severity | status | handling |
|---|---|---|---|
| DL-GAP-001 | medium | TODO_PEER_DATA | peer_market_snapshot.csv not generated in this data-layer-only pass |
| DL-GAP-002 | medium | TODO_DISCLOSURE_RECONCILIATION | structured financial metrics need official filing reconciliation before material company facts |
| DL-GAP-003 | low | TODO_MARKET_DATA | pe_forward missing from fixture and left as TODO_MARKET_DATA |

## Boundary Notes

- Tushare and Baostock outputs are metric-only.
- No business exposure fact is created from structured snapshots.
- Missing fields stay visible as TODO or MISSING.
