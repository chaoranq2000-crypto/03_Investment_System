# Workflow Readout: wf_20260703_stock_first_002837_invic

## Status

needs_fix

## Scope

| Field | Value |
|---|---|
| workflow_type | stock_first_closed_loop |
| object | 002837 英维克 |
| date_range | 2025-01-01 to 2026-07-03 |
| depth | debug MVP |
| P2 | out_of_scope |

## Skills Used

| skill | stages | outputs |
|---|---|---|
| research-orchestrator | T0, T10 | workflow_state.yaml, handoffs, artifact_manifest.csv, workflow_readout.md |
| evidence-ingest | T1 | stock_evidence_plan.yaml, evidence_manifest_delta.csv, metrics_draft_delta.csv, ingest_log.json |
| stock-deep-dive | T2, T3, T7 | stock_report_draft.md, evidence_map.md, segment_exposure.yaml |
| segment-company-mapping | T6, T8 | exposure_change_note.md |
| quality-review | T9 | quality_issue_list.md, quality_gate_report.md |

## Artifacts

| artifact | path | status |
|---|---|---|
| evidence plan | stock_evidence_plan.yaml | current |
| evidence delta | evidence_manifest_delta.csv | current, 6 rows |
| metrics delta | metrics_draft_delta.csv | current, 262 rows |
| stock draft | stock_report_draft.md | needs_fix |
| segment exposure | segment_exposure.yaml | needs_fix |
| exposure note | exposure_change_note.md | current |
| issue list | quality_issue_list.md | current |

## Quality Gates

| gate | status | notes |
|---|---|---|
| G1 Evidence | fail | official filing registered but no locator extraction |
| G3 Metric | pass_with_todos | 262 draft metric candidates generated; all `stock_code=002837` |
| G6 Exposure | fail | exposure remains `todo_insufficient_evidence` |
| G7 Stock Report | pass_with_todos | report draft is traceable but intentionally skeletal |
| G8 Backflow | fail | global exposure registry not updated |
| G9 No Advice | pass | no trading instruction produced |
| G10 Close | pass | status and TODOs explicit |

## Backflow Decisions

| decision | target | action | status |
|---|---|---|---|
| blocked | data/processed/normalized/segment_company_exposure.csv | no global update | open until annual report extraction creates reviewed claim locator |

## Remaining TODOs

| issue | severity | owner_skill | next_action |
|---|---|---|---|
| Q002837-001 | high | evidence-ingest | extract annual report text/table/page locator and produce reviewed claim candidates |
| Q002837-002 | high | segment-company-mapping | rerun exposure mapping after claim support exists |
| Q002837-003 | medium | evidence-ingest | normalize metric units and period_type before promotion |
| Q002837-004 | medium | stock-deep-dive | expand business/customer/order/capacity sections after evidence extraction |

## P2 Readiness

- ready_for_limited_p2: false
- reasons:
  - stock-first loop now produces workflow-local evidence, metrics, draft report, exposure, issue list and readout.
  - high severity evidence/exposure issues remain open.
- blockers:
  - annual report extraction and claim locator missing.
  - global exposure registry deliberately not updated.

## Global Registry Check

This run was designed to avoid appending global files. The following files were checked after the run and remained at the expected line counts and hashes:

| path | lines | sha256 |
|---|---:|---|
| data/manifests/evidence_manifest.csv | 16 | 2398E8ACC2E4C870E9D709C10FE3FF05863CE432136C8E5212574F59C83C3B90 |
| data/manifests/metrics_draft.csv | 45 | 8A84922442F63B6E64463A8475BDD0FC2CAE5CCCAECDF80CA0A8458EC609D09E |
| data/processed/normalized/segment_company_exposure.csv | 6 | F580DA4915C46A7EBE368C5572A41E763A1CCDD379E20FB651FE4E5539732233 |

## Validation

| check | result |
|---|---|
| workflow_state validator | pass |
| artifact contract | pass: 19 required files, 6 evidence rows, 262 metric rows, 0 non-002837 metric rows |
| targeted pytest | pass: 2 passed |
| full pytest | pass: 30 passed |
