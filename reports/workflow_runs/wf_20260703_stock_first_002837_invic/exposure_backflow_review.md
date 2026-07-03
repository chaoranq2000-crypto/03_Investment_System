# Exposure Backflow Review

workflow_id: wf_20260703_stock_first_002837_invic
status: update_exposure_product_only

## Decision

| item | value |
|---|---|
| backflow_decision | update_exposure |
| allowed_scope | product exposure evidence and notes only |
| revenue_pct | MISSING_DISCLOSURE |
| profit_pct | MISSING_DISCLOSURE |
| P2-BLOCK-003 | resolved_product_only_update |

## Updated State

- `data/processed/normalized/segment_company_exposure.csv` keeps product exposure and appends the R4 official evidence clue.
- `reports/segments/ai_server_liquid_cooling/company_universe.csv` stays at five companies and keeps disclosure gaps visible.
- `segment_exposure.yaml` now records update_exposure for product-only backflow.

## Boundary

- No revenue or profit exposure is promoted.
- Narrative-only rows are not backflowed.
- Segment-led replay is prepared, but no P2 comparison is started.
