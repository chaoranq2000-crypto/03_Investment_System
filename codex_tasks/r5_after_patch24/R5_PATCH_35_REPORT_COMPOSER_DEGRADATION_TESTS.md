# R5 Patch 35 — Report Composer Degradation Tests

status: `TASK_CARD`

## 背景

R5 composer 不能在 forecast / valuation / market / sentiment 缺口仍存在时写出样例级强判断。需要测试降级行为。

## 目标

确保 composer 在 source-gapped pack 输入下只能生成：

```text
source_gapped_research_draft
source_gap_report
open_questions
```

而不能生成 sample-quality note 或投资评级。

## 允许修改

```text
src/report/stock_report_writer.py
tests/test_r5_report_composer_degradation.py
reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_note_source_gapped.md  # 如需要
reports/p1_6/R5_PATCH_35_REPORT_COMPOSER_DEGRADATION_READOUT.md
```

## 要求

1. 输入 `pack_status: research_draft` 时，输出标题/metadata 必须明确 `source_gapped_research_draft`。
2. 缺 forecast / valuation / market / sentiment 时，对应章节只写缺口和 next_action。
3. 不出现直接交易语言。
4. 不把 business exposure clue 写成收入或利润贡献。
5. 不输出 sample-quality 标识。

## 全局禁止事项

- 不生成任何买入、卖出、持有、建仓、减仓、仓位建议。
- 不生成 sample-quality 个股报告。
- 不进入 P2。
- 不调用 live API。
- 不把 TODO / MISSING_DISCLOSURE / LOW_CONFIDENCE_CLUE_ONLY 写成事实。
- 不用 readout 自述替代实际命令、exit_code、stdout/stderr 和 artifact evidence。


## 必跑命令

```bash
python -m py_compile src/report/stock_report_writer.py
python -m pytest -q tests/test_r5_report_composer_degradation.py --tb=short
python -m pytest -q tests/test_r5_report_no_advice_and_todos.py tests/test_compose_r5_report_from_pack.py --tb=short
```

## 验收标准

- 降级输出可审计。
- 每个 TODO 都在 source gap appendix 或 open questions 中出现。
- readout 给出命令证据。
