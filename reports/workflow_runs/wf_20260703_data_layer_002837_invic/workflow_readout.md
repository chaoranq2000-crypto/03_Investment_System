# Data Layer Workflow Readout

workflow_id: wf_20260703_data_layer_002837_invic
workflow_type: stock_first_closed_loop / data_layer_only
status: accepted
as_of_date: 2026-07-01

## Result

| item | result |
|---|---|
| evidence_manifest_rows | 3 |
| metric_candidates | 93 |
| claim_candidates | 0 |
| data_layer_quality_status | accepted |
| high_issues | 0 |
| medium_issues | 0 |

## Artifacts

| artifact | path |
|---|---|
| data request plan | `data_request_plan.yaml` |
| adapter queue | `adapter_run_queue.yaml` |
| workflow-local manifest | `evidence_manifest.csv` |
| metric candidates | `metrics_draft.csv` |
| financial metric pack | `financial_metric_pack.csv` |
| valuation snapshot | `valuation_snapshot.yaml` |
| technical snapshot | `technical_snapshot.yaml` |
| source gap report | `source_gap_report.md` |
| quality gate | `data_layer_quality_report.md` |

## Boundaries

- All structured snapshots remain metric-only.
- No business exposure fact is created from Tushare or Baostock fixtures.
- Global registries were not appended.
- Missing peer and disclosure reconciliation work remains visible in `open_todos.csv`.

## Handoff

The run is ready for the stock report readiness bridge. Downstream report logic may consume `valuation_snapshot.yaml`, `technical_snapshot.yaml` and `financial_metric_pack.csv`; missing peer or official-disclosure reconciliation fields must remain TODO/MISSING.
