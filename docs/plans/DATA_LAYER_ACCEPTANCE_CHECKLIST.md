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
| Official disclosure reconciliation | pending | official disclosure extraction/reconciliation not complete | DL-GAP-002 medium | evidence-ingest / quality-review | `official_disclosure_reconciliation_stub.md` |
| DL-5 stock report bridge draft | pending | bridge draft not generated | source gaps must be exposed | stock-deep-dive | `R4_stock_report_data_layer_bridge_draft.md` |
| DL-7 integrated debug | pending | DL-5 not complete | accepted TODOs must carry forward | research-orchestrator / quality-review | `integrated_data_layer_readout.md` |
| DL-4 live adapter hardening | done_with_manual_live_smoke_pending | real-service live smoke skipped by default | live mode implemented, mocked, and gated by explicit `--allow-network` | evidence-ingest | `DATA_LAYER_DL4_ADAPTER_HARDENING_READOUT.md` |
| P2 readiness gate | pending | stock bridge and integrated debug not complete | do not enter P2 yet | research-orchestrator | final master readout |

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
- [ ] `business_segment_metric_pack.csv` exists or business exposure remains `MISSING_DISCLOSURE`.
- [x] `peer_market_snapshot.csv` exists before peer valuation comparison.
- [x] `official_disclosure_reconciliation_stub.md` exists.
- [ ] Official disclosure reconciliation is complete.
- [ ] R4 stock report data-layer bridge draft is generated.
- [ ] Integrated stock-first data-layer debug is generated.

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

- [ ] Complete official disclosure reconciliation beyond the stub.
- [ ] Generate DL-5 R4 stock report data-layer bridge draft.
- [ ] Run DL-7 stock-first integrated data-layer debug.
- [x] Add CI-safe DL-4 live adapter guards, mocked live success tests and default-skipped manual live smoke tests.
- [ ] Execute manual live smoke when external token/package prerequisites are intentionally enabled.
- [ ] Produce `reports/p1_6/DATA_LAYER_NEXT_TASKS_MASTER_READOUT.md` after all master-plan tasks are complete.
