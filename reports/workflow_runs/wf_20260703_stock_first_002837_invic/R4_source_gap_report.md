# R4 Source Gap Report

workflow_id: wf_20260703_stock_first_002837_invic
status: source_gaps_visible

## Data-layer Source Gaps

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
| official_financial_reconciliation.csv | available_with_review_todo | Partial official reconciliation completed; mismatch and official_missing rows require quality-review before promotion |

## Explicit Gaps

| gap_id | severity | status | handling |
|---|---|---|---|
| DL-GAP-001 | low | lowered_to_low_todo | peer_market_snapshot.csv generated in fixture-only mode; live peer market data hardening remains pending |
| DL-GAP-002 | medium | PARTIAL_RECONCILIATION_COMPLETED_REVIEW_TODO | official_financial_reconciliation.csv exists; mismatches and remaining official_missing fields stay visible before any promotion |
| DL-GAP-003 | low | TODO_MARKET_DATA | pe_forward missing from fixture and left as TODO_MARKET_DATA |

## Boundary Notes

- Tushare and Baostock outputs are metric-only.
- Peer valuation output is context-only and non-conclusive.
- No business exposure fact is created from structured snapshots.
- Missing fields stay visible as TODO or INSUFFICIENT_PRICE_WINDOW.

## Stock-first Remaining Source Gaps

# Remaining Source Gaps After Data Layer Bridge

workflow_id: wf_20260703_stock_first_002837_invic
source_data_layer_run: wf_20260703_data_layer_002837_invic

## Remaining Gaps

| gap_id | severity | source | next_action |
|---|---|---|---|
| DLBR-001 | medium | official_financial_reconciliation.csv | Partial company-level reconciliation exists; mismatch rows still require review before promotion. |
| DLBR-002 | low | valuation_snapshot.yaml | Fill `pe_forward` through future market data source or keep `TODO_MARKET_DATA`. |
| DLBR-003 | low | peer_market_snapshot.csv | Replace fixture-only peer TODO fields through live peer data hardening. |
| DISCLOSURE-SEGMENT-001 | medium | stock report bridge boundary | Keep liquid-cooling revenue share as `MISSING_DISCLOSURE` until official disclosure table support exists. |
| DISCLOSURE-SEGMENT-002 | medium | stock report bridge boundary | Keep customer/order/capacity assertions as `TODO_SOURCE_REQUIRED` until reviewed source support exists. |

## Carry-Forward Rule

These gaps must remain visible in downstream stock-deep-dive work. Data-layer packs cannot be used to close business exposure gaps without official disclosure reconciliation and quality-review approval.

## R4 Additional Gaps

| gap_id | severity | status | handling |
|---|---|---|---|
| R4-GAP-001 | medium | MISSING_DISCLOSURE | Liquid-cooling revenue_pct and profit_pct remain unavailable from official disclosure. |
| R4-GAP-002 | medium | NEEDS_REVIEW | Official reconciliation contains mismatch rows; quality-review must decide promotion. |
| R4-GAP-003 | low | TODO_MARKET_DATA | pe_forward remains unavailable in current fixture context. |
