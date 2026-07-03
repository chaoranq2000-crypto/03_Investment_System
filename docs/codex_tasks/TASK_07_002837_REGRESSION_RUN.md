# TASK 07 — 002837 Regression Run to R3 Draft

## Goal

Use the existing 002837 workflow run as a regression case and upgrade it from R0 debug MVP to R1/R2/R3 progressively.

## Steps

```text
1. Keep existing run folder or create a new run linked to it.
2. Parse registered annual report PDF with MinerU.
3. Generate page_map/table_map/parse_log.
4. Generate claim_candidates and metric_candidates.
5. Promote key claims/metrics after review.
6. Build stock_analysis_pack.
7. Generate stock_report_sample_quality_draft.md.
8. Run quality-review v2.
9. If high issues remain, do not mark R3.
10. Write regression readout.
```

## Must close previous high issues

```text
- Annual report has locator extraction.
- Segment exposure is supported or remains blocked with explicit gap.
- Backflow decision is explicit.
```

## Expected final outputs

```text
reports/workflow_runs/<run_id>/stock_report_sample_quality_draft.md
reports/workflow_runs/<run_id>/stock_analysis_pack.yaml
reports/workflow_runs/<run_id>/quality_gate_report.md
reports/workflow_runs/<run_id>/workflow_readout.md
```
