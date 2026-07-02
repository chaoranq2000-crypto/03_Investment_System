# Exposure Change Note: wf_20260703_stock_first_002837_invic

## Input

- segment_exposure_path: `segment_exposure.yaml`
- company_id: `cn_002837_invic`
- stock_code: `002837`
- candidate_segment: `ai_server_liquid_cooling`

## Decision

`blocked`

## Registry Action

No global `data/processed/normalized/segment_company_exposure.csv` update in this run.

## Reason

The workflow-local `segment_exposure.yaml` contains evidence_id `ev_annual_report_002837_20260421_ce7f64` and company-level metric candidates, but no newly extracted annual-report claim locator. Per B4-lite guardrails, structured metrics cannot prove business exposure, and product exposure cannot be accepted without reviewed official-disclosure extraction.

## Required Fix

1. Extract annual report text/table locator for liquid-cooling / data-center thermal-management statements.
2. Generate claim candidate(s) with claim_type separated from inference.
3. Re-run G6 Exposure Gate before appending any global exposure registry row.
