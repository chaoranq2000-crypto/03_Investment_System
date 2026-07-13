# Handoff: R5_bundle9r_4_scenario_and_sensitivity -> company-valuation

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| workflow_type | `stock_first_closed_loop` |
| run_mode | `forward_rebuild_not_history_rewrite` |
| current_stage | `R5_bundle9r_5_valuation_rebuild` |
| target_skill | `company-valuation` |

## Objective

消费已审阅的 9R 预测核心，重建同业经营口径、市场分母、反向估值和三情景估值，并把低置信度和缺失输入显式留在产物中。

## Inputs

| input | path_or_value | required | notes |
|---|---|---:|---|
| valuation_request | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_valuation_request.yaml` | true | 方法资格与边界 |
| evidence_generation_lock | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8r_evidence_generation_lock_v2.yaml` | true | 当前代际 |
| forecast_scenario_pack | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_scenario_pack.yaml` | true | 2026E-2028E 三情景 |
| statement_bridge | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_financial_statement_bridge.yaml` | true | 归母利润和自由现金流 |
| market_source | `data/processed/normalized/tencent_quote_adapter_quote_and_valuation_002837_2026-07-13_79bd83ad.csv` | true | 日期化市场快照 |
| peer_context | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_market_peer_input_registry.yaml` | true | 四家公司低置信度集合 |

## Expected Outputs

| output | path | required | notes |
|---|---|---:|---|
| peer_reconciliation | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_peer_operating_reconciliation.yaml` | true | 禁止排名 |
| market_snapshot | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_market_snapshot.yaml` | true | 收盘价×股本核对总市值 |
| reverse_valuation | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_reverse_valuation.yaml` | true | inference |
| scenario_valuation | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_scenario_valuation.yaml` | true | bear/base/bull research ranges |
| integrated_model_pack | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_model_pack.yaml` | true | 交回 stock-deep-dive/quality-review |

## Required Artifacts

| artifact_type | path | required | notes |
|---|---|---:|---|
| forecast_assumption_registry | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_forecast_assumption_registry.yaml` | true | 45 条估计假设 |
| sensitivity | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_sensitivity.csv` | true | 单变量与双变量 |
| consensus | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_consensus_comparison.csv` | true | analyst_view |

## Guardrails

- `LOW_CONFIDENCE_PEER_SET` 下 `ranking_allowed=false`。
- DCF 缺少净债务、折现率和终值假设；SOTP 缺少独立液冷经济性，两者均保持不合格。
- 场景权益价值仅为 `inference`，不是交易动作或确定性结论。
- 不修改历史 Bundle 9/10 和现有 `bundle10r/`。

## Completion Criteria

- 市值与 `close_price × shares_outstanding` 相对差异不超过 0.5%。
- 反向估值和情景估值均存在、可追溯且情景值单调。
- 所有估值数字带 evidence_id、metric_id、assumption_id 或明确缺失原因。

## Next Gate

| field | value |
|---|---|
| next_gate | `R5_bundle9r_7_quality_gate` |
| gate_owner | `quality-review` |

## Open TODOs

| issue_id | severity | owner | next_action |
|---|---|---|---|
| `missing_peer_liquid_cooling_purity` | medium | company-valuation | 保持低置信度且禁止排名 |
| `TODO_DCF_INPUTS` | medium | company-valuation | 不满足时不启用 DCF |
| `TODO_SEGMENT_DISCLOSURE` | medium | company-valuation | 不满足时不启用 SOTP |
