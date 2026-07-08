# Codex Task Card — R5 Patch 11：R5 report planner / composer skeleton

## 任务名称

R5 report planner / composer skeleton

## 目标

1. 拆出 report_planner 与 report_composer 契约。
2. planner 输出 outline / thesis_stack / section_claim_plan / missing warnings。
3. composer 只能转译通过 gate 的 research pack，不创造新事实。

## 允许新增 / 修改文件

- `.agents/skills/stock-deep-dive/references/r5_report_planner_contract.md`
- `.agents/skills/stock-deep-dive/references/r5_report_composer_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_report_outline.example.yaml`
- `.agents/skills/stock-deep-dive/assets/r5_thesis_stack.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_report_plan.py`
- `tests/test_r5_report_planner_composer.py`
- `reports/p1_6/R5_PATCH_11_REPORT_PLANNER_COMPOSER_SKELETON_READOUT.md`

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

- Composer 不得新增数字。
- Composer 不得删除 source gap。
- 输出必须包含 Source Gap Appendix。

## 测试命令

~~~bash
python -m py_compile .agents/skills/stock-deep-dive/scripts/validate_r5_report_plan.py
pytest tests/test_r5_report_planner_composer.py
~~~

## 输出要求

完成后请输出：

1. 新增 / 修改文件列表；
2. 测试命令和结果；
3. 简短 diff summary；
4. 未完成项和 source gap；
5. 一个 readout 文件，放入 `reports/p1_6/`。
