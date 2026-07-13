# Handoff: stock-deep-dive / company-valuation -> quality-review

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| current_stage | `R5_bundle9_forecast_valuation` |
| target_skill | `quality-review` |
| dispatch_status | `ready_for_bundle9_gate` |

## Scope

审查 Bundle 9 的自下而上预测、利润与现金流桥、三情景、敏感性、同业上下文、动态/反向/情景估值及来源缺口；不重生成 Reader，不放行样例质量，不进入 P2。

## Authoritative Inputs

- `R5_bundle9_forecast_assumption_registry.yaml`
- `segment_forecast_model.yaml`
- `forecast_bridge.yaml`
- `R5_bundle9_valuation_input_registry.yaml`
- `R5_bundle9_valuation_pack.yaml`
- `reverse_valuation.yaml`
- `scenario_valuation.yaml`
- `valuation/R5_valuation_handoff.yaml`
- `R5_bundle9_close_input_validation.json`

## Required Boundary Checks

- 液冷独立收入与毛利缺口不得被模型假设替换。
- 同业比较必须保留低置信标签和业务口径限制。
- 不满足输入门的方法必须跳过并写明缺口。
- 所有模型数字必须可回链 evidence、metric、assumption 或 TODO。
- Reader 与样例质量状态保持不变。
