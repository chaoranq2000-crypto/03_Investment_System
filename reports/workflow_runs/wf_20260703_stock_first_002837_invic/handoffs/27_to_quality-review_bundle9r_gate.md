# Handoff: R5_bundle9r_6_model_pack_integration -> quality-review

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| workflow_type | `stock_first_closed_loop` |
| run_mode | `forward_rebuild_not_history_rewrite` |
| current_stage | `R5_bundle9r_7_quality_gate` |
| target_skill | `quality-review` |

## Objective

对 9R 当前代际、预测模型、估值方法、证据/估计边界、算术勾稽、缺口保留和无交易建议边界执行 fail-closed 质量门。

## Inputs

| input | path_or_value | required | notes |
|---|---|---:|---|
| evidence_lock | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8r_evidence_generation_lock_v2.yaml` | true | 需复核全部输入哈希 |
| model_pack | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_model_pack.yaml` | true | 集成模型 |
| model_contract | `config/r5_bundle9r_model_contract.yaml` | true | fail-closed 规则 |
| input_review | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_input_review_ledger.yaml` | true | 输入接受/拒绝 |
| assumptions | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_forecast_assumption_registry.yaml` | true | 45 条 |
| sensitivity | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_sensitivity.csv` | true | 12+9 条 |
| valuation_request | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_valuation_request.yaml` | true | 方法资格 |

## Expected Outputs

| output | path | required | notes |
|---|---|---:|---|
| quality_scorecard | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_quality_scorecard.yaml` | true | critical/high 必须为 0 |
| regression_result | test output | true | 正向与负向 fixtures 均通过 |
| open_issues | close readout / open_todos | true | 中低风险 TODO 可见 |

## Required Artifacts

| artifact_type | path | required | notes |
|---|---|---:|---|
| expected_artifacts | `config/r5_bundle9r_expected_artifacts.yaml` | true | 15 个关闭产物 |
| peer_reconciliation | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_peer_operating_reconciliation.yaml` | true | low confidence/no ranking |
| market_snapshot | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_market_snapshot.yaml` | true | 分母核对 |
| reverse_valuation | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_reverse_valuation.yaml` | true | 必需方法 |
| scenario_valuation | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_scenario_valuation.yaml` | true | 必需方法 |

## Guardrails

- critical/high 任一存在即 `needs_fix`，不得生成关闭锁。
- 检查 stale generation、锁定输入漂移、液冷事实越界/重复加总、缺分部、禁用平衡项、桥接算术、情景单调性、市值分母、同业排名、缺估值方法、consensus claim_type 和交易动作语言。
- 允许显式中/低风险 TODO，但必须有 owner 和 next_action。
- sample-quality 与 P2 均保持 false；不触发 Bundle 10R。

## Completion Criteria

- generation binding 与所有锁定输入哈希通过。
- model quality scorecard 为 `pass`，critical/high 均为 0。
- 所有规定负向变异均因目标规则失败，正向 fixture 通过。
- 15 个 expected artifacts 在关闭前全部存在。

## Next Gate

| field | value |
|---|---|
| next_gate | `R5_bundle9r_8_close_and_model_generation_lock` |
| gate_owner | `research-orchestrator` |

## Open TODOs

| issue_id | severity | owner | next_action |
|---|---|---|---|
| `R5B9R-DISC-001` | medium | evidence-ingest | 刷新独立液冷经济性披露 |
| `R5B9R-PEER-001` | medium | company-valuation | 后续补齐官方同业经营口径 |
| `R5B9R-DCF-001` | medium | company-valuation | 补齐净债务、折现率和终值输入后再评估资格 |
