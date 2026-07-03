# Quality Gate Report After Data Layer Bridge

workflow_id: wf_20260703_stock_first_002837_invic
source_data_layer_run: wf_20260703_data_layer_002837_invic
final_status: accepted_with_todos
blocking_issues: 0
accepted_todos: 3
high_issues: 0
medium_issues: 1
low_issues: 2

## Gates

| gate | status | evidence |
|---|---|---|
| G1 Evidence Gate | pass | `R4_stock_report_data_layer_bridge_draft.md` carries data-layer evidence ids |
| G2 Claim Gate | pass | no data-layer claim candidates generated |
| G3 Metric Gate | pass | metric context remains metric-only |
| G6 Exposure Gate | pass | business exposure remains official-disclosure-gated |
| G7 Stock Report Gate | accepted_with_todos | bridge draft generated; formal report unchanged |
| G8 Backflow Gate | pass | no exposure registry update |
| G9 No Advice Gate | pass | static no-advice scan passed |
| G10 Data Layer Pack Gate | accepted_with_todos | accepted TODOs carried forward |

## Accepted TODOs

| issue_id | severity | status | required_follow_up |
|---|---|---|---|
| DLBR-001 | medium | accepted_todo | reconcile structured financial metrics to official disclosure |
| DLBR-002 | low | accepted_todo | fill `pe_forward` through future market data source |
| DLBR-003 | low | accepted_todo | harden live peer market data source |
