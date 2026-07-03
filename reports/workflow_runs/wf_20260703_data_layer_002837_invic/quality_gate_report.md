# Quality Gate Report

final_status: accepted_with_todos
high_issues: 0
medium_issues: 2
low_issues: 1
blocking_issues: 0
accepted_todos: 3

| gate | status | evidence |
|---|---|---|
| G-DL1 Source Permission | pass | `data_layer_quality_report.md` |
| G-DL2 Raw Archive | pass | `raw/` snapshots and `evidence_manifest.csv` |
| G-DL3 Reproducibility | pass | `api_params_hash` present in manifest |
| G-DL4 Field Schema | pass | `normalized/` tables |
| G-DL5 Metric-only Boundary | pass | no claim candidates generated |
| G-DL6 Freshness | pass | valuation snapshot has as_of_date |
| G-DL7 License / Token | pass | no token value detected |
| G-DL8 Pack Completeness | accepted_todo | financial, valuation, technical and source gap packs present; TODOs remain visible |

## Accepted Todos

| issue_id | severity | target_artifact | handling |
|---|---|---|---|
| DL-GAP-001 | medium | `peer_market_snapshot.csv` | Keep peer comparison as `TODO_PEER_DATA`. |
| DL-GAP-002 | medium | `official_disclosure_reconciliation` | Structured metrics need official disclosure reconciliation before business facts. |
| DL-GAP-003 | low | `valuation_snapshot.yaml` | `pe_forward` remains `TODO_MARKET_DATA`. |
