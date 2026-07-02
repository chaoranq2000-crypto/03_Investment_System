# Handoff: T6/T8 Exposure Mapping -> segment-company-mapping

## Workflow
- workflow_id: wf_20260703_stock_first_002837_invic
- workflow_type: stock_first_closed_loop
- current_stage: T6/T8 Exposure Mapping
- requested_skill: segment-company-mapping

## Objective
Receive segment_exposure.yaml and decide whether global exposure can be updated.

## Inputs
- stock_code: 002837
- company_id: cn_002837_invic
- run_dir: reports/workflow_runs/wf_20260703_stock_first_002837_invic
- prior_artifact: reports/stocks/002837_invic/ as structure reference only

## Expected Outputs
exposure_change_note.md

## Guardrails
- Do not update global exposure registry unless quality gate passes.
- Keep P2 out of scope.
- Do not create trading instructions.

## Completion Criteria
- Output exists in workflow run directory.
- Material statements cite evidence_id, metric_candidate_id, or TODO.

## Next Gate
- quality-review stock-led gates G1/G3/G6/G7/G8/G9.
