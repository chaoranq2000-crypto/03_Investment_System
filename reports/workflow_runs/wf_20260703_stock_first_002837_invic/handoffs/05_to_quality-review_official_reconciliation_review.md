# Handoff: R4 disclosure review -> quality-review

## Workflow
- workflow_id: wf_20260703_stock_first_002837_invic
- workflow_type: stock_first_closed_loop
- current_stage: R4_disclosure_review_and_backflow
- requested_skill: quality-review

## Objective
Review official reconciliation decisions and keep structured metrics from being promoted without matching official support.

## Inputs
- reports/workflow_runs/wf_20260703_data_layer_002837_invic/official_financial_reconciliation.csv
- reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_stock_deep_dive_v0_1.md

## Expected Outputs
- reports/workflow_runs/wf_20260703_stock_first_002837_invic/official_reconciliation_review_decision.csv
- reports/workflow_runs/wf_20260703_stock_first_002837_invic/official_reconciliation_review_decision.md

## Guardrails
- Structured values remain metric-only unless explicitly reviewed.
- Company-level reconciliation cannot support liquid-cooling business exposure.
- Missing official fields remain visible.

## Completion Criteria
- Every mismatch, official_missing and structured_missing row has a review_decision.
- promotion_allowed=true requires official_evidence_id and locator.
