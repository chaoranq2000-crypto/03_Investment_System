# TASK 06 — Quality Review V2 and Backflow Maintenance

## Goal

Upgrade `quality-review` to enforce sample-quality gates and write back reviewed artifacts.

## Files to create or modify

```text
src/qa/stock_report_quality_review.py
src/qa/check_evidence_map.py
src/qa/check_no_unsupported_advice.py
src/qa/check_forecast_valuation.py
src/maintenance/backflow_stock_report.py
tests/test_stock_report_quality_review.py
```

## Required behavior

1. Read `stock_report_quality_gates_v2.md` as gate contract.
2. Validate report, analysis pack, evidence map, claims, metrics and exposure.
3. Output `quality_issue_list.md`, `quality_gate_report.md`, `stock_report_acceptance_checklist.yaml`.
4. Decide accepted_sample_quality / accepted_with_todos / needs_fix / blocked.
5. If accepted, update report_status and prepare backflow.

## Acceptance criteria

```text
- Any material claim without evidence produces high issue.
- Any direct buy/sell/hold instruction produces high issue.
- Segment exposure cannot update registry without support.
- accepted_sample_quality requires no high issues.
```
