# Integrated Data Layer Readout

workflow_id: wf_20260703_stock_first_002837_invic
source_data_layer_run: wf_20260703_data_layer_002837_invic
status: accepted_with_todos

## Consumption Chain

| step | input | result |
|---|---|---|
| research-orchestrator reads data-layer run | `workflow_readout.md` | pass |
| stock-deep-dive consumes financial pack | `financial_metric_pack.csv` | pass |
| stock-deep-dive consumes valuation pack | `valuation_snapshot.yaml` | pass_with_todo |
| stock-deep-dive consumes technical pack | `technical_snapshot.yaml` | pass_with_todo |
| stock-deep-dive consumes peer pack | `peer_market_snapshot.csv` | pass_with_low_todo |
| quality-review checks G10 | `data_layer_bridge_readout.md` | accepted_with_todos |

## Quality Gate Summary

| gate | status | notes |
|---|---|---|
| G1 Evidence Gate | pass | source data-layer evidence ids carried into bridge |
| G2 Claim Gate | pass | no claim generated from data-layer snapshots |
| G3 Metric Gate | pass | financial/market fields remain metric context |
| G6 Exposure Gate | pass | business exposure remains official-disclosure-gated |
| G7 Stock Report Gate | accepted_with_todos | bridge draft only; formal report not regenerated |
| G8 Backflow Gate | pass | no global exposure update |
| G9 No Advice Gate | pass | no trading conclusion language |
| G10 Data Layer Pack Gate | accepted_with_todos | accepted TODOs retained |

## Accepted TODOs Carried Forward

| source_issue | severity | carried_to | handling |
|---|---|---|---|
| DL-GAP-001 | low | DLBR-003 | peer snapshot is fixture-only for non-target peers |
| DL-GAP-002 | medium | DLBR-001 | official disclosure reconciliation required |
| DL-GAP-003 | low | DLBR-002 | `pe_forward` remains `TODO_MARKET_DATA` |

## Boundary Result

- Market, valuation and technical packs are used as context only.
- Structured financial metrics are not used as business exposure facts.
- The bridge draft does not replace official disclosure reconciliation.
- P2 remains not entered.
