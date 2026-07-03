# Official Disclosure Reconciliation Stub

workflow_id: wf_20260703_data_layer_002837_invic
status: accepted_todo
owner_skill: evidence-ingest
next_review_skill: quality-review

## Scope

This stub records the reconciliation work still required before structured financial metrics can be treated as reported company facts. It does not complete reconciliation and does not promote any metric to a business exposure fact.

## Metrics Needing Official Disclosure Reconciliation

| metric_source | current_artifact | current_status | required_official_source |
|---|---|---|---|
| Tushare income fixture | `financial_metric_pack.csv` | metric-only candidate | annual report or quarterly report table |
| Tushare daily_basic fixture | `valuation_snapshot.yaml` | market context only | exchange/market data source review if used downstream |
| Baostock K-line fixture | `technical_snapshot.yaml` | market-state observation only | market data source review if used downstream |

## Allowed Current Use

- Structured financial rows may remain `metric_candidate` records.
- Valuation fields may be used as market context with source and TODO labels.
- Technical fields may be used as market-state observations with no trading conclusion.

## Disallowed Current Use

- Structured snapshots must not become `business exposure fact`.
- Structured snapshots must not prove segment revenue, customer orders, product share, project wins or capacity.
- Peer valuation context must not become a rating, ranking conclusion or trading conclusion.

## Required Official Disclosure Files

| requirement | needed_artifact | purpose |
|---|---|---|
| 2025 annual report table extraction | official disclosure text/table with locator | reconcile company-level reported financial metrics |
| 2025 or latest interim/quarterly report extraction | official disclosure text/table with locator | reconcile updated financial metrics |
| Segment/product revenue table extraction | official disclosure text/table with locator | decide whether any business exposure fact can be promoted |

## Follow-Up Rule

Until reconciliation is completed and reviewed, all structured financial outputs remain metric-only. Any future promotion to reported fact must cite the official disclosure evidence id, page/table locator, metric name, period, unit and review status.
