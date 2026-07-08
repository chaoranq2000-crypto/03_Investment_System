# Codex Task Card — R5 Patch 9：risk_counterevidence_pack and source gap pack

## 任务名称

risk_counterevidence_pack and source gap pack

## 目标

1. 定义风险、反证、证伪条件、监控指标与 source gap schema。
2. 所有核心 thesis 必须有风险或反证。
3. 缺 risk/counterevidence 不得通过 R5 gate。

## 允许新增 / 修改文件

- `.agents/skills/stock-deep-dive/references/r5_risk_counterevidence_pack_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_risk_counterevidence_pack.example.yaml`
- `.agents/skills/stock-deep-dive/assets/r5_source_gap_report_template.md`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_risk_counterevidence_pack.py`
- `tests/test_r5_risk_counterevidence_pack.py`
- `reports/p1_6/R5_PATCH_9_RISK_COUNTEREVIDENCE_SOURCE_GAP_PACK_READOUT.md`

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

- source gap 必须包含 section、missing_data、impact_on_conclusion、fix_owner_skill、next_action。
- 缺口不得被 writer 隐藏。
- fix owner 必须可回到具体 skill。

## 测试命令

~~~bash
python -m py_compile .agents/skills/stock-deep-dive/scripts/validate_r5_risk_counterevidence_pack.py
pytest tests/test_r5_risk_counterevidence_pack.py
~~~

## 输出要求

完成后请输出：

1. 新增 / 修改文件列表；
2. 测试命令和结果；
3. 简短 diff summary；
4. 未完成项和 source gap；
5. 一个 readout 文件，放入 `reports/p1_6/`。
