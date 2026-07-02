# Handoff: T9 Quality Review -> quality-review

## Workflow
- workflow_id: wf_20260703_stock_first_002837_invic
- workflow_type: stock_first_closed_loop
- current_stage: T9 Quality Review
- requested_skill: quality-review

## Objective
Review evidence, metrics, exposure, report draft and backflow decision.

## Inputs
- stock_code: 002837
- company_id: cn_002837_invic
- run_dir: reports/workflow_runs/wf_20260703_stock_first_002837_invic
- prior_artifact: reports/stocks/002837_invic/ as structure reference only

## Expected Outputs
quality_issue_list.md; quality_gate_report.md

## Guardrails
- Surface concrete fixable issues; do not generate new claims.
- Keep P2 out of scope.
- Do not create trading instructions.

## Completion Criteria
- Output exists in workflow run directory.
- Material statements cite evidence_id, metric_candidate_id, or TODO.

## Next Gate
- quality-review stock-led gates G1/G3/G6/G7/G8/G9.
