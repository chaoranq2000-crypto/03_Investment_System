# Handoff: T3 Metrics and Market -> evidence-ingest

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| current_stage | `R5 Bundle 5.3 market and peer onboarding` |
| target_skill | `evidence-ingest` |
| reviewer | `codex` |
| authorization_source | `workspace_user: 授权, 2026-07-12` |

## Objective

Acquire one immutable same-date Tushare snapshot for 002837 and an exposure-grounded peer candidate set, normalize native units explicitly, review the archived rows offline, and create accepted market/peer dropzone records without registry promotion.

## Data Boundary

- as_of_trading_date: `2026-07-10`, the latest completed open day verified through `trade_cal` on 2026-07-12.
- subject: `002837.SZ`.
- reviewed peers: `301018.SZ` and `300499.SZ`, selected from `data/processed/normalized/segment_company_exposure.csv` because they have the strongest product-level exposure in the current local universe after the subject.
- excluded candidates: `300731.SZ` and `300602.SZ`, whose current exposure rows are technology-level and lower-scored; exclusion is unrelated to their valuation levels.

## Unit Contract

- `close`: CNY/share.
- `total_share`, `float_share`, `free_share`: Tushare native 10,000 shares; multiply by 10,000 for normalized shares.
- `total_mv`, `circ_mv`: Tushare native CNY 10,000; multiply by 10,000 for normalized CNY.
- `pe`, `pe_ttm`, `pb`, `ps`, `ps_ttm`: multiples.
- market capitalization must use source-reported `total_mv * 10,000`; do not silently recompute from rounded close and shares.

## Guardrails

- Load token and custom endpoint through the project Tushare client; never persist the token.
- Preserve raw response bytes immutably and record API parameters, hash, retrieval time and unit map.
- A live response becomes a reviewed input only after offline row/unit/date reconciliation.
- Record exchange, timestamp/timezone, adjustment convention, share-count basis, currency, accounting/period basis and peer inclusion/exclusion rationale.
- Do not select peers from valuation outputs, mix dates, write canonical registries, open sample-quality/P2, or emit trading advice.

## Expected Outputs

- immutable raw snapshot under `data/raw/market_data/`
- normalized market/peer table under `data/processed/normalized/`
- evidence/ingest manifest entries
- accepted `market_snapshot` and `peer_snapshot` records
- Card 5.3 validation JSONs, focused test and readout
