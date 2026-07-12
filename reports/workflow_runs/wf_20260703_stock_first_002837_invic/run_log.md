# Run Log: wf_20260703_stock_first_002837_invic

| Step | Status | Notes |
|---|---|---|
| T0 Intake | done | stock_first_closed_loop for 002837 英维克; P2 out of scope. |
| T1 Evidence Plan | done | Generated stock_evidence_plan.yaml. |
| T1 Evidence Ingest | done | Created workflow-local evidence_manifest_delta.csv, metrics_draft_delta.csv, ingest_log.json. |
| T2/T7 Stock Draft | done | Generated stock_report_draft.md and evidence_map.md from workflow-local deltas. |
| T6/T8 Exposure Mapping | done | Generated segment_exposure.yaml and exposure_change_note.md; no global registry update. |
| T9 Quality Review | done | Generated quality_issue_list.md and quality_gate_report.md. |
| T10 Readout | done | workflow_readout.md status is needs_fix. |
| Validation | done | workflow_state validator OK; artifact contract OK; targeted pytest 2 passed; full pytest 30 passed. |

Global registry append: false.

Global registry verification:

| path | lines | sha256 |
|---|---:|---|
| data/manifests/evidence_manifest.csv | 16 | 2398E8ACC2E4C870E9D709C10FE3FF05863CE432136C8E5212574F59C83C3B90 |
| data/manifests/metrics_draft.csv | 45 | 8A84922442F63B6E64463A8475BDD0FC2CAE5CCCAECDF80CA0A8458EC609D09E |
| data/processed/normalized/segment_company_exposure.csv | 6 | F580DA4915C46A7EBE368C5572A41E763A1CCDD379E20FB651FE4E5539732233 |
| R4 Disclosure/Backflow Review | done | Formatted artifacts verified; official review decisions, liquid-cooling evidence review, product-only backflow review, R4 v0.2 and P2 readiness check generated. |

## Bundle 7 close update

| Step | Status | Notes |
|---|---|---|
| M1 Reader Quality Gate v0.2 | done | Positive-from-zero gate reclassified the current Reader as 59/100 research_draft while truthfulness remained pass. |
| M2 Workflow Quality Backflow | done | State moved to needs_fix; 12 unique issues and 7 deterministic routes were synchronized; evidence-ingest is first. |
| Rollback rehearsal | done | Isolated full checkout applied and rolled back the overlay; baseline hashes and tracked-clean state were restored. |
| Implementation publish | done | PR #1 passed both GitHub Actions checks and merged as 1530e7e291efe9176aca0e93b54d3dc482d3d2f9. |
| Bundle 7 close | done | Current quality report and canonical close readout added; Bundle 6 candidate readout marked superseded; sample-quality and P2 remain closed. |

Bundle 8 handoff was explicitly not dispatched in this close task. The recorded next owner is `evidence-ingest`; segment-company exposure was not updated because Bundle 7 produced no new exposure evidence.

## Bundle 8 research-depth execution

| Step | Status | Notes |
|---|---|---|
| B8-M3 Evidence Coverage | done | Registered 14 reviewed underlying sources with 10 independent sources; coverage matrix is 7/7 with zero blockers. |
| B8-M3 Industry Research | done | Official CAICT and NDRC materials were archived, extracted, page-mapped and visually checked; industry validator passed with demand=2 and supply=2. |
| B8-M4 Analysis Engine | done | Seven analyst-authored units passed; analysis pack and five deterministic subpacks were generated with counterevidence, falsification and watch metrics. |
| B8 Integration Gate | done_local | Gate result is `bundle8_research_depth_inputs_ready`; deterministic rebuild changed 0 of 12 artifacts. |
| Quality Review | accepted_with_todos | R5-G1 to R5-G11 are explicitly represented; liquid-cooling segment disclosure remains missing and uncommitted changes have no GitHub Actions result. |
| Regression | done_local | Focused pytest: 22 passed. Full pytest: 575 passed, 2 skipped. No-advice scan: 0 hits. |
| State boundary | preserved | `workflow_state.yaml` and `R5_stock_research_report_reader_v2.md` hashes remained unchanged; Reader was not regenerated and Bundle 8 was not closed. |
| Next dispatch | pending | Handoff 16 records a close-only patch followed by Bundle 9; neither is started until explicit publish/CI and close review. |

Bundle 8 local M3/M4 execution is complete. Remote CI, close-only state synchronization, Bundle 9, Bundle 10 and P2 remain outside this execution boundary.
