# Handoff: T2/T7 Stock Draft -> stock-deep-dive

## Workflow
- workflow_id: wf_20260703_stock_first_002837_invic
- workflow_type: stock_first_closed_loop
- current_stage: T2/T7 Stock Draft
- requested_skill: stock-deep-dive

## Objective
Consume workflow-local evidence package and produce traceable stock draft.

## Inputs
- stock_code: 002837
- company_id: cn_002837_invic
- run_dir: reports/workflow_runs/wf_20260703_stock_first_002837_invic
- prior_artifact: reports/stocks/002837_invic/ as structure reference only

## Expected Outputs
stock_report_draft.md; evidence_map.md; segment_exposure.yaml

## Guardrails
- Do not use prior report as evidence; use delta evidence/metrics/TODO only.
- Keep P2 out of scope.
- Do not create trading instructions.

## Completion Criteria
- Output exists in workflow run directory.
- Material statements cite evidence_id, metric_candidate_id, or TODO.

## Next Gate
- quality-review stock-led gates G1/G3/G6/G7/G8/G9.
