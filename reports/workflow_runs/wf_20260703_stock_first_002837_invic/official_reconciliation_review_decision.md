# Official Reconciliation Review Decision

workflow_id: wf_20260703_stock_first_002837_invic
status: resolved_review_completed_no_structured_promotion

## Decision Counts

| review_decision | count |
|---|---:|
| explicit_official_missing | 4 |
| official_available_structured_missing | 3 |
| reviewed_no_structured_promotion | 3 |

## Decisions

| metric | period | status | decision | promotion_allowed | owner |
| --- | --- | --- | --- | --- | --- |
| total_revenue | 20251231 | mismatch | reviewed_no_structured_promotion | false | quality-review |
| n_income_attr_p | 20251231 | mismatch | reviewed_no_structured_promotion | false | quality-review |
| gross_margin | 20251231 | official_missing | explicit_official_missing | false | quality-review |
| net_margin | 20251231 | official_missing | explicit_official_missing | false | quality-review |
| basic_eps | 20251231 | mismatch | reviewed_no_structured_promotion | false | quality-review |
| operating_cash_flow | 20251231 | structured_missing | official_available_structured_missing | false | quality-review |
| total_assets | 20251231 | structured_missing | official_available_structured_missing | false | quality-review |
| total_liabilities | 20251231 | official_missing | explicit_official_missing | false | quality-review |
| roe | 20251231 | structured_missing | official_available_structured_missing | false | quality-review |
| debt_to_asset | 20251231 | official_missing | explicit_official_missing | false | quality-review |

## Boundary

- P2-BLOCK-001 is resolved as review-completed, not as metric promotion.
- Structured values remain cross-check inputs when mismatch or missing status exists.
- Company-level metric reconciliation does not create liquid-cooling exposure evidence.
