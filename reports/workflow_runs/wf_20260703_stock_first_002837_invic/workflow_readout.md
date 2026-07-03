# Workflow Readout: wf_20260703_stock_first_002837_invic

## Status

accepted_sample_quality

## Scope

| Field | Value |
|---|---|
| workflow_type | stock_report_production |
| object | 002837 英维克 |
| date_range | 2025-01-01 to 2026-07-03 |
| quality_target | R3_sample_quality_draft |
| P2 | not_entered |

## Regression Result

| item | result |
|---|---|
| annual_report_page_map | pass: 7 pages |
| table_inventory | pass: 16 entries |
| claim_candidates | pass: 18 generated, 18 promoted |
| metric_candidates | pass: 262 promoted workflow-local metrics |
| stock_analysis_pack | pass |
| stock_report_sample_quality_draft | pass |
| quality_review_v2 | accepted_sample_quality; high_issues=0; medium_issues=0 |
| no_trading_instruction | pass |
| backflow_decision | no_global_exposure_update_with_todos |

## Artifacts

| artifact | path | status |
|---|---|---|
| parse job | mineru_parse_job.yaml | current |
| parse log | data/processed/logs/ev_annual_report_002837_20260421_ce7f64_parse_log.json | current |
| page map | data/processed/page_maps/ev_annual_report_002837_20260421_ce7f64_page_map.yaml | current |
| table inventory | data/processed/tables/ev_annual_report_002837_20260421_ce7f64_tables.json | current |
| claim candidates | data/processed/candidates/claim_candidates_ev_annual_report_002837_20260421_ce7f64.csv | current |
| claims registry | claims_registry.csv | workflow-local reviewed |
| metrics registry | metrics_registry.csv | workflow-local reviewed |
| analysis pack | stock_analysis_pack.yaml | current |
| report draft | stock_report_sample_quality_draft.md | current |
| quality gate report | quality_gate_report.md | accepted_sample_quality |
| acceptance checklist | stock_report_acceptance_checklist.yaml | accepted_sample_quality |
| backflow decision | backflow_decision.yaml | explicit no global exposure update |

## Closed Previous High Issues

| old_issue | previous_status | new_status | evidence |
|---|---|---|---|
| Q002837-001 annual report locator missing | high open | fixed | page_map + parse_log + 18 reviewed claim locators |
| Q002837-002 exposure unsupported | high open | fixed | product exposure now supported by reviewed claims; revenue/profit exposure remains MISSING |
| Q002837-003 metric candidates draft | medium open | fixed | 262 workflow-local metrics promoted to metrics_registry.csv |
| Q002837-004 skeletal report | medium accepted_todo | fixed | sample-quality draft generated |
| Q002837-005 backflow blocked | low accepted_todo | fixed | backflow_decision.yaml records explicit no-update with TODOs |

## Quality Gates

| gate | status |
|---|---|
| G1 Evidence Completeness | pass |
| G2 Claim Locator | pass |
| G3 Metric Normalization | pass |
| G4 Business Breakdown | pass |
| G5 Segment Exposure | pass |
| G6/G7 Forecast Valuation | pass |
| G8 Technical Sentiment Event | pass |
| G10 No Unsupported Advice | pass |
| G11 Backflow Maintenance | pass |

## Evidence Gaps Kept Visible

| gap | status |
|---|---|
| liquid_cooling_revenue_pct | MISSING_DISCLOSURE; follow-up evidence required |
| liquid_cooling_gross_margin | MISSING_DISCLOSURE; follow-up evidence required |
| customer/order/capacity evidence | TODO_SOURCE_REQUIRED |
| market price/valuation fields | TODO_MARKET_DATA |

## Parser Note

MinerU CLI was invoked from `C:\Users\Q\anaconda3\envs\mineru\Scripts\mineru.EXE` on the first two pages, but the local CLI returned a non-zero code at client-side output generation because an intermediate image file was missing. The workflow used `pypdf_text_extraction` as a deterministic fallback for the full 7-page locator map, and this produced complete page_map, table inventory, candidates and reviewed claims.

## Validation

| check | result |
|---|---|
| targeted patch tests | pass: 10 passed |
| full pytest | pass: 40 passed |
| quality-review v2 | pass: accepted_sample_quality |
| unsupported advice scan on final draft | pass: no matches |
