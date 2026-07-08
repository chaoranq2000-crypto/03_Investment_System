# Codex Task Card — R5 Patch 10：quality-review R5 sample-quality gate

## 任务名称

quality-review R5 sample-quality gate

## 目标

1. 实现 R5-G1 到 R5-G11 的 gate 契约与校验。
2. 输出 issue list 与 `accepted|accepted_with_todos|needs_fix|blocked`。
3. high issue 阻断 accepted；缺 forecast/valuation 降级。

## 允许新增 / 修改文件

- `.agents/skills/quality-review/SKILL.md`
- `.agents/skills/quality-review/references/r5_quality_gate.md`
- `.agents/skills/quality-review/references/r5_issue_schema.md`
- `.agents/skills/quality-review/assets/r5_quality_issues.example.csv`
- `.agents/skills/quality-review/scripts/validate_r5_quality_gate.py`
- `tests/test_r5_quality_gate.py`
- `reports/p1_6/R5_PATCH_10_R5_QUALITY_GATE_READOUT.md`

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

- Gate 覆盖 evidence、financial、business、industry、forecast、valuation、technical、sentiment/event、narrative、no-advice、benchmark。
- source gap 隐藏或交易指令直接 blocked。

## 测试命令

~~~bash
python -m py_compile .agents/skills/quality-review/scripts/validate_r5_quality_gate.py
pytest tests/test_r5_quality_gate.py
~~~

## 输出要求

完成后请输出：

1. 新增 / 修改文件列表；
2. 测试命令和结果；
3. 简短 diff summary；
4. 未完成项和 source gap；
5. 一个 readout 文件，放入 `reports/p1_6/`。
