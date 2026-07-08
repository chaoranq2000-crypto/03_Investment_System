# Codex Task Card — R5 Patch 5：forecast_model_pack contract and validator

## 任务名称

forecast_model_pack contract and validator

## 目标

1. 定义 2026E-2028E 预测包 schema。
2. 要求每个预测值有 `assumption_id`、source 或 `missing_reason`。
3. 定义 base / bull / bear、敏感性、一致预期差异字段。
4. 缺 forecast 时不得 sample-quality。

## 允许新增 / 修改文件

- `.agents/skills/stock-deep-dive/references/r5_forecast_model_pack_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_forecast_model_pack.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_forecast_model_pack.py`
- `tests/test_r5_forecast_model_pack.py`
- `reports/p1_6/R5_PATCH_5_FORECAST_MODEL_CONTRACT_AND_VALIDATOR_READOUT.md`

## 禁止事项

- 不修改 `reports/workflow_runs/` 历史 run。
- 不修改已有 R4 报告正文产物，除非本任务明确要求兼容指针。
- 不新增真实 API 调用，不执行联网下载。
- 不生成任何真实股票研究报告。
- 不计算真实 forecast 或真实 valuation，除非本任务明确只做 schema fixture。
- 不把 `TODO_SOURCE_REQUIRED`、`MISSING_DISCLOSURE`、`TODO_MODEL_INPUT` 写成事实。
- 不输出买入、卖出、持有、建仓、减仓、仓位建议、保证收益或自动交易指令。
- 不让 writer / composer 创造研究结论。

## 交付物 / 规则要求

- 年份必须覆盖 `2026E`、`2027E`、`2028E`。
- 每年至少有 revenue、gross_margin、net_profit_attributable、eps。
- 每个关键值必须有 assumption/source/missing_reason。
- 不生成真实预测值。

## 测试命令

~~~bash
python -m py_compile .agents/skills/stock-deep-dive/scripts/validate_r5_forecast_model_pack.py
pytest tests/test_r5_forecast_model_pack.py
~~~

## 输出要求

完成后请输出：

1. 新增 / 修改文件列表；
2. 测试命令和结果；
3. 简短 diff summary；
4. 未完成项和 source gap；
5. 一个 readout 文件，放入 `reports/p1_6/`。
