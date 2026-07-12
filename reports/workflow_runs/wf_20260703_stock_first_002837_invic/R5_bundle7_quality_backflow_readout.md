# R5 Bundle 7 — quality rebaseline and backflow readout

status: `needs_fix`
mode: `applied`
as_of_date: `2026-07-12`

## Decision

- reader-quality decision: `rejected`
- quality band: `research_draft`
- positive score: `59/82`
- truthfulness: `pass`
- prior workflow status: `accepted_with_todos`
- current workflow status: `needs_fix`
- sample-quality promotion: `false`
- P2 promotion: `false`

## Fix routes

| priority | stage | owner | reason codes |
|---|---|---|---|
| medium | T2_evidence_acquire_parse | evidence-ingest | independent_research_evidence_below_minimum, peer_operating_evidence_missing |
| medium | T5_analysis_pack_build | segment-research | independent_industry_evidence_missing |
| medium | T5_analysis_pack_build | stock-deep-dive | insufficient_analytical_unit_coverage |
| medium | T6_forecast_valuation_model | stock-deep-dive | forecast_bridge_uses_aggregate_residual, forecast_not_bottom_up_or_segment_driven |
| medium | RP6_valuation | company-valuation | credible_peer_context_below_minimum, valuation_lacks_reverse_or_scenario_value_range |
| medium | T7_technical_sentiment_event_pack | stock-deep-dive | catalyst_event_chain_incomplete, sentiment_analysis_inputs_missing, technical_analysis_inputs_missing |
| medium | T8_report_draft | memo-writer | reader_report_below_research_density_floor |

## Generated issues

| issue_id | severity | owner | code |
|---|---|---|---|
| R5Q-B7-A823A644 | medium | memo-writer | reader_report_below_research_density_floor |
| R5Q-B7-0BF5FA3E | medium | stock-deep-dive | insufficient_analytical_unit_coverage |
| R5Q-B7-44F6297D | medium | evidence-ingest | independent_research_evidence_below_minimum |
| R5Q-B7-8E0E9760 | medium | segment-research | independent_industry_evidence_missing |
| R5Q-B7-E54AC257 | medium | evidence-ingest | peer_operating_evidence_missing |
| R5Q-B7-EDEA2DF6 | medium | stock-deep-dive | forecast_not_bottom_up_or_segment_driven |
| R5Q-B7-FC4A9CE0 | medium | stock-deep-dive | forecast_bridge_uses_aggregate_residual |
| R5Q-B7-5F606C21 | medium | company-valuation | valuation_lacks_reverse_or_scenario_value_range |
| R5Q-B7-47122D56 | medium | company-valuation | credible_peer_context_below_minimum |
| R5Q-B7-0B636DD2 | medium | stock-deep-dive | technical_analysis_inputs_missing |
| R5Q-B7-E0B818E7 | medium | stock-deep-dive | sentiment_analysis_inputs_missing |
| R5Q-B7-9A50BA49 | medium | stock-deep-dive | catalyst_event_chain_incomplete |

## State policy

Historical acceptance/readout artifacts remain available for audit, but they are not current decision surfaces. The current state is derived from the positive-from-zero reader-quality scorecard and cannot be promoted automatically.

## files_added

- none

## files_modified

- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle7_quality_backflow_readout.md`

## commands_run

- `./.conda/investment-system/python.exe scripts/reconcile_r5_quality_backflow.py --repo-root . --as-of-date 2026-07-12 --apply`

## exit_code

- reconciliation command: `0`

## stdout_or_stderr_summary

- `quality_backflow mode=apply status=needs_fix score=59 routes=7 issues=12`

## artifact_evidence

- inventory_status: `pass`
- generated issue inventory: `checked=12`
- fix route inventory: `checked=7`
- source scorecard: `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_report_reader_v2_quality_scorecard.yaml`

## known_todos

- `R5Q-B7-A823A644`: `reader_report_below_research_density_floor`; owner=`memo-writer`
- `R5Q-B7-0BF5FA3E`: `insufficient_analytical_unit_coverage`; owner=`stock-deep-dive`
- `R5Q-B7-44F6297D`: `independent_research_evidence_below_minimum`; owner=`evidence-ingest`
- `R5Q-B7-8E0E9760`: `independent_industry_evidence_missing`; owner=`segment-research`
- `R5Q-B7-E54AC257`: `peer_operating_evidence_missing`; owner=`evidence-ingest`
- `R5Q-B7-EDEA2DF6`: `forecast_not_bottom_up_or_segment_driven`; owner=`stock-deep-dive`
- `R5Q-B7-FC4A9CE0`: `forecast_bridge_uses_aggregate_residual`; owner=`stock-deep-dive`
- `R5Q-B7-5F606C21`: `valuation_lacks_reverse_or_scenario_value_range`; owner=`company-valuation`
- `R5Q-B7-47122D56`: `credible_peer_context_below_minimum`; owner=`company-valuation`
- `R5Q-B7-0B636DD2`: `technical_analysis_inputs_missing`; owner=`stock-deep-dive`
- `R5Q-B7-E0B818E7`: `sentiment_analysis_inputs_missing`; owner=`stock-deep-dive`
- `R5Q-B7-9A50BA49`: `catalyst_event_chain_incomplete`; owner=`stock-deep-dive`

## next_recommended_patch

- Run `evidence-ingest` at `T2_evidence_acquire_parse` for `independent_research_evidence_below_minimum, peer_operating_evidence_missing`; do not enter P2.
