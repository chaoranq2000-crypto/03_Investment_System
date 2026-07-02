# Quality Issue List: wf_20260703_stock_first_002837_invic

| issue_id | severity | gate_id | stage | target_artifact | description | fix_owner_skill | status |
|---|---|---|---|---|---|---|---|
| Q002837-001 | high | G1 | T1 Company Evidence | evidence_manifest_delta.csv | Annual report is registered but not parsed; no page/table locator or extracted claim exists for material business exposure. | evidence-ingest | open |
| Q002837-002 | high | G6 | T6 Exposure Mapping | segment_exposure.yaml | Segment exposure remains todo_insufficient_evidence; global exposure registry must not be updated until reviewed claim support exists. | segment-company-mapping | open |
| Q002837-003 | medium | G3 | T2 Business & Financial Skeleton | metrics_draft_delta.csv | Metric candidates are generated from local fixtures and remain draft; period_type and units need normalization before promotion. | evidence-ingest | open |
| Q002837-004 | medium | G7 | T7 Stock Report Draft | stock_report_draft.md | Draft report is traceable but intentionally skeletal; customer, order, capacity and segment revenue fields remain TODO/MISSING. | stock-deep-dive | accepted_todo |
| Q002837-005 | low | G8 | T8 Backflow | exposure_change_note.md | Backflow is blocked with clear next step; rerun mapping after extraction. | research-orchestrator | accepted_todo |
