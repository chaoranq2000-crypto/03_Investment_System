# Codex Task Card — R5 Patch 38：reviewed forecast assumption registry

## 任务名称

reviewed forecast assumption registry

## 背景

当前 `forecast_model.yaml` 仍以 `TODO_MODEL_INPUT` 保留 2026E-2028E 预测项，说明系统还不能生成数字化预测。下一步不是直接填预测，而是建立 reviewed forecast assumption registry：只有经过 evidence / metric / claim 绑定的假设，才能进入 forecast builder；否则 forecast 必须继续 degraded。

## 目标

1. 新增 forecast assumption registry contract。
2. 为 002837 workflow run 建立 `R5_forecast_assumption_registry.yaml`，默认不填数字预测。
3. 新增 validator，强制 assumption_id、period、driver、evidence_id / metric_id、review_status、allowed_usage。
4. 将 forecast_model 与 registry 建立 interlock：没有 reviewed assumptions 时，forecast_model 保持 TODO。

## 允许新增 / 修改文件

- `.agents/skills/stock-deep-dive/references/r5_forecast_assumption_registry_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_forecast_assumption_registry.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_forecast_assumption_registry.py`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_forecast_assumption_registry.yaml`
- `tests/test_validate_r5_forecast_assumption_registry.py`
- `reports/p1_6/R5_PATCH_38_FORECAST_ASSUMPTION_REGISTRY_READOUT.md`

## 禁止事项

- 不生成真实 2026E-2028E 收入、毛利率、净利润、EPS。
- 不把历史收入自动外推成预测。
- 不把券商预测、新闻线索、模型推断直接提升为 reviewed assumption。
- 不输出买入、卖出、持有、目标价或仓位建议。
- 不让 composer 根据 assumption TODO 写强判断。

## Schema 要求

```yaml
schema_version: r5_forecast_assumption_registry_v0.1
artifact_type: R5_forecast_assumption_registry
workflow_id: wf_20260703_stock_first_002837_invic
stock_code: '002837'
review_status: pending
assumptions:
  - assumption_id: TODO_REVIEWED_REVENUE_GROWTH
    driver: revenue_growth
    periods: [2026E, 2027E, 2028E]
    value: TODO_MODEL_INPUT
    unit: pct
    evidence_ids: []
    metric_ids:
      - metric_cn_002837_invic_revenue_20260331_4f7f22
    missing_reason: TODO_MODEL_INPUT
    allowed_usage: degraded_forecast_only
    review_status: pending
blocking_rules:
  - if any core forecast driver is pending, sample-quality must remain false
```

## 验收标准

1. pending registry 可通过结构校验，但不得让 forecast_model 输出数字预测。
2. reviewed assumption 必须至少绑定一个 evidence_id 或 accepted metric_id，并有 reviewer_note。
3. 核心 drivers 至少覆盖 revenue_growth、gross_margin、opex、net_profit、eps 或显式缺口。
4. forecast_model 中 `TODO_MODEL_INPUT` 仍应可见，不得被隐藏。
5. readout 明确说明“本 patch 只建假设登记层，不做预测”。

## 测试命令

```bash
python -m py_compile .agents/skills/stock-deep-dive/scripts/validate_r5_forecast_assumption_registry.py
pytest -q tests/test_validate_r5_forecast_assumption_registry.py --tb=short
python .agents/skills/stock-deep-dive/scripts/validate_r5_forecast_assumption_registry.py reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_forecast_assumption_registry.yaml
```

## 输出要求

完成后输出：新增/修改文件、测试结果、diff summary、未完成项、readout 路径。
