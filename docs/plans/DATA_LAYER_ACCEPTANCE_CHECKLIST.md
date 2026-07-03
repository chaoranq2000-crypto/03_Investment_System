# Data Layer Acceptance Checklist

updated_at: 2026-07-03
scope: P1.6 data-layer next tasks
current_workflow: `reports/workflow_runs/wf_20260703_data_layer_002837_invic/`
current_status: `accepted_with_todos`

## Current State

| item | status | blocker | accepted_todo | next_owner_skill | next_artifact |
|---|---|---|---|---|---|
| DL-0 execution sanity | done | none | none | quality-review | `reports/p1_6/DATA_LAYER_EXECUTION_SANITY_READOUT.md` |
| DL-1 quality state reconciliation | done | none | accepted TODOs visible | quality-review | `reports/p1_6/DATA_LAYER_DL1_QUALITY_STATE_READOUT.md` |
| DL-1.5 artifact formatting | done | none | none | quality-review | `reports/p1_6/DATA_LAYER_DL1_5_ARTIFACT_FORMATTING_READOUT.md` |
| DL-2 technical semantics | done | none | short fixture window labeled `INSUFFICIENT_PRICE_WINDOW` | evidence-ingest | `reports/p1_6/DATA_LAYER_DL2_TECHNICAL_MARKET_SEMANTICS_READOUT.md` |
| DL-3 peer snapshot | done | none | live peer market data hardening remains low TODO | evidence-ingest | `peer_market_snapshot.csv` |
| DL-5 stock report bridge draft | done | none | source gaps carried forward | stock-deep-dive | `R4_stock_report_data_layer_bridge_draft.md` |
| DL-7 integrated debug | done | none | accepted TODOs carried forward | research-orchestrator / quality-review | `integrated_data_layer_readout.md` |
| DATA_LAYER_NEXT_TASKS_MASTER_READOUT produced | done | none | R4/disclosure work deferred to next task file | research-orchestrator | `reports/p1_6/DATA_LAYER_NEXT_TASKS_MASTER_READOUT.md` |
| Official disclosure reconciliation MVP | partial_done | mismatch and official_missing rows require review | DL-GAP-002 medium | evidence-ingest / quality-review | `official_financial_reconciliation.csv` |
| Business segment disclosure extraction MVP | done_with_missing_disclosure | liquid-cooling revenue_pct/profit_pct missing | DISCLOSURE-SEGMENT-002 medium | stock-deep-dive / quality-review | `business_segment_metric_pack.csv` |
| R4 publishable stock report gate | bridge_only | publishable_ready not met | source gaps visible | stock-deep-dive / quality-review | `R4_quality_gate_report.md` |
| R4 stock deep dive v0.1 | done_bridge_only | R4 gate remains bridge_only | source gaps visible | stock-report-writer / quality-review | `R4_stock_deep_dive_v0_1.md` |
| DL-4 live adapter hardening | done_with_manual_live_smoke_pending | real-service live smoke skipped by default | live mode implemented, mocked, and gated by explicit `--allow-network` | evidence-ingest | `DATA_LAYER_DL4_ADAPTER_HARDENING_READOUT.md` |
| Manual real-service Tushare / Baostock smoke | pending_manual_only | explicit external prerequisites required | not needed for R4 bridge_only | evidence-ingest | `docs/playbooks/MANUAL_LIVE_DATA_SMOKE_PLAYBOOK.md` |
| P2 readiness precheck | pending | R4 publishable gate not ready | do not enter P2 yet | research-orchestrator | `reports/p1_6/P2_READINESS_PRECHECK_AFTER_DATA_LAYER.md` |

## Current True State

| state_key | value |
|---|---|
| engineering_data_layer_bridge | done |
| data_layer_status | accepted_with_todos |
| stock_bridge_status | accepted_with_todos |
| disclosure_reconciliation | partial_completed_with_review_todos |
| business_segment_disclosure | completed_with_missing_disclosure |
| publishable_r4 | bridge_only |
| p2_readiness | blocked |

Notes:

- data-layer bridge completion is not the same as R4 publishable report completion.
- fixture peer snapshot completion is not the same as real API peer data completion.
- reconciliation stub completion is not the same as official reconciliation completion.
- partial official reconciliation does not promote structured metrics to reported facts.
- product_line_clue rows do not create liquid-cooling revenue_pct or profit_pct.

## 1. Documentation And Architecture

- [x] `docs/workflows/DATA_LAYER_WORKFLOW.md` exists as the data-layer workflow fact source.
- [x] `docs/adr/ADR_0002_data_layer_as_evidence_ingest_subsystem.md` exists.
- [x] evidence-ingest references include source adapter matrix, structured adapter contract, market context contract and data quality gate.
- [x] `config/data_source_registry_overlay.yaml` exists as an overlay for structured data source routing.
- [x] Data layer is documented as an evidence-ingest subsystem, not a new peer research skill.

## 2. Contract Consistency

- [x] `.agents/skills/evidence-ingest/SKILL.md` references the data-layer contracts.
- [x] `.agents/skills/stock-deep-dive/SKILL.md` and `references/data_layer_pack_consumption.md` define safe downstream consumption.
- [x] `.agents/skills/quality-review/SKILL.md` includes G10 Data Layer Pack Gate.
- [x] `config/source_registry.yaml` includes Tushare, Baostock and market context source groups.
- [x] Structured snapshots remain `material_claim_allowed=metric_only`.

## 3. Execution Sanity And Quality State

- [x] DL-0 Python/YAML/TOML execution sanity passed.
- [x] CI compile scope covers all tracked Python files.
- [x] DL-1 final_status logic distinguishes `blocking_issue` and `accepted_todo`.
- [x] Current workflow status is `accepted_with_todos`, not plain `accepted`.
- [x] Current quality gate has `blocking_issues: 0`.
- [x] Medium accepted TODOs are visible and not hidden.

## 4. Artifact Formatting And Semantics

- [x] `data_layer_quality_report.md` is multi-line Markdown with Summary, Blocking Issues and Accepted Todos.
- [x] `data_layer_issue_list.csv` is header plus one row per visible issue/TODO.
- [x] `workflow_state.yaml`, `valuation_snapshot.yaml` and `technical_snapshot.yaml` parse with `yaml.safe_load`.
- [x] Target data-layer artifacts use repo-relative POSIX paths.
- [x] `technical_snapshot.yaml` no longer uses `MISSING_DISCLOSURE` for short price-window fields.
- [x] `source_gap_report.md` uses `INSUFFICIENT_PRICE_WINDOW` for short fixture market history.

## 5. First Implementation Acceptance

- [x] Local fixture mode passes tests.
- [x] Tushare adapter supports dry-run/no-token blocked behavior.
- [x] Baostock adapter supports fixture/blocking behavior when package or live session is unavailable.
- [x] No API token is written to tracked output.
- [x] Raw snapshots remain unchanged during DL-1.5 through DL-3.
- [x] Evidence manifest rows exist for structured snapshots.
- [x] Metric candidates are generated only as metric context.
- [x] `source_gap_report.md` exposes remaining gaps.

## 6. Stock Report Readiness

- [x] `valuation_snapshot.yaml` exists and preserves `TODO_MARKET_DATA` for missing `pe_forward`.
- [x] `technical_snapshot.yaml` exists and preserves no-advice note.
- [x] `financial_metric_pack.csv` exists.
- [x] `business_segment_metric_pack.csv` exists and business exposure gaps remain `MISSING_DISCLOSURE`.
- [x] `peer_market_snapshot.csv` exists before peer valuation comparison.
- [x] `official_disclosure_reconciliation_stub.md` exists.
- [x] Official disclosure reconciliation MVP exists, with mismatch/official_missing rows still visible.
- [x] R4 stock report data-layer bridge draft is generated.
- [x] Integrated stock-first data-layer debug is generated.
- [x] R4 publishable gate exists and currently outputs `bridge_only`.
- [x] R4 stock deep dive v0.1 exists as readiness draft, not publishable_ready.

## 7. Explicit Blockers To Keep Closed

These conditions must remain false:

- [x] Market/context data is not used as company fact.
- [x] Tushare/Baostock data is not used to prove segment revenue exposure.
- [x] Raw files were not overwritten.
- [x] Metric candidates retain source evidence linkage.
- [x] No promoted metric has unknown source field mapping.
- [x] Data-layer artifacts do not generate trading advice.
- [x] Accepted TODOs are not hidden.

## 8. Pending Work

- [x] Complete official disclosure reconciliation MVP beyond the stub.
- [x] Generate DL-5 R4 stock report data-layer bridge draft.
- [x] Run DL-7 stock-first integrated data-layer debug.
- [x] Generate R4 stock deep dive v0.1 with visible source gaps.
- [x] Add CI-safe DL-4 live adapter guards, mocked live success tests and default-skipped manual live smoke tests.
- [ ] Execute manual live smoke when external token/package prerequisites are intentionally enabled.
- [ ] Produce `reports/p1_6/R4_READINESS_NEXT_TASKS_MASTER_READOUT.md` after R4 readiness tasks are complete.
