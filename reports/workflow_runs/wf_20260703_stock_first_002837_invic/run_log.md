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
