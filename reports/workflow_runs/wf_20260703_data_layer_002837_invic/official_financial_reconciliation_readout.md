# Official Disclosure Reconciliation Readout

workflow_id: wf_20260703_data_layer_002837_invic
stock_code: 002837
company_id: cn_002837_invic
status: partial_reconciliation_completed_with_review_todos

## Scope

This MVP reconciles company-level structured financial metrics against the registered 2025 annual-report summary. It does not promote structured data into reported facts and does not evaluate business-segment exposure.

## Status Counts

| reconciliation_status | count |
|---|---:|
| matched | 0 |
| matched_with_rounding | 0 |
| mismatch | 3 |
| official_missing | 4 |
| structured_missing | 3 |
| needs_manual_review | 0 |

## Required Core Metrics

| metric | period | structured_value | official_value | status | evidence |
|---|---|---:|---:|---|---|
| total_revenue | 20251231 | 3520000000 | 6067759091.55 | mismatch | ev_annual_report_002837_20260421_ce7f64 |
| n_income_attr_p | 20251231 | 450000000 | 521914773.00 | mismatch | ev_annual_report_002837_20260421_ce7f64 |
| basic_eps | 20251231 | 0.62 | 0.54 | mismatch | ev_annual_report_002837_20260421_ce7f64 |

## Boundary Decision

- DLBR-001 is refined from unreconciled stub to partial reconciliation completed with mismatches and remaining official_missing fields.
- Mismatch rows are visible and require quality-review before any promotion.
- Company-level metrics still cannot prove liquid-cooling revenue share, orders, customer exposure or segment profitability.
- Structured data is not promoted to reported fact; it remains metric-only until an explicit review step promotes a candidate.
