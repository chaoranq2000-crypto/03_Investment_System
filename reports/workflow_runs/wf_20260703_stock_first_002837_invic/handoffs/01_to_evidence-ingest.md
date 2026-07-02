# Handoff: T1 Company Evidence -> evidence-ingest

## Workflow
- workflow_id: wf_20260703_stock_first_002837_invic
- workflow_type: stock_first_closed_loop
- current_stage: T1 Company Evidence
- requested_skill: evidence-ingest

## Objective
Generate workflow-local evidence and metrics deltas from existing annual report and local CSV fixtures.

## Inputs
- stock_code: 002837
- company_id: cn_002837_invic
- run_dir: reports/workflow_runs/wf_20260703_stock_first_002837_invic
- prior_artifact: reports/stocks/002837_invic/ as structure reference only

## Expected Outputs
evidence_manifest_delta.csv; metrics_draft_delta.csv; ingest_log.json

## Guardrails
- Do not append global manifest or metrics registry.
- Keep P2 out of scope.
- Do not create trading instructions.

## Completion Criteria
- Output exists in workflow run directory.
- Material statements cite evidence_id, metric_candidate_id, or TODO.

## Next Gate
- quality-review stock-led gates G1/G3/G6/G7/G8/G9.
