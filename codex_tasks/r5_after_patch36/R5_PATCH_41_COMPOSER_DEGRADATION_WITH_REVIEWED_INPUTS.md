# Codex Task Card — R5 Patch 41：composer degradation with reviewed inputs

## 任务名称

composer degradation with reviewed inputs

## 背景

即使 market / peer / forecast assumption registry 被建立，composer 也不能自动升级为 sample-quality。writer/composer 必须根据 gate 结果降级：缺数字 forecast、缺估值、缺完整证据时，只能输出 source-gapped research draft，并把 source gap appendix 显示出来。

## 目标

1. 强化 R5 composer：读取 gate result 与 registries 后决定 allowed_report_level。
2. 当输入仍 pending 时，composer 必须输出 research_draft，不得补数字、不写强结论。
3. 当输入 reviewed-degraded 时，composer 可输出 source-gapped pilot note，但仍不得 sample-quality。
4. 增加 fixture 测试覆盖 pending / reviewed_degraded 两种路径。

## 允许新增 / 修改文件

- `scripts/compose_r5_report_from_pack.py`
- `templates/r5_stock_research_note.md`
- `tests/fixtures/r5_minimal_stock_run/` 下必要 fixture
- `tests/test_r5_report_composer_degradation.py`
- `tests/test_compose_r5_report_from_pack.py`
- `reports/p1_6/R5_PATCH_41_COMPOSER_DEGRADATION_READOUT.md`

## 禁止事项

- 不让 composer 创造研究结论。
- 不自动把 TODO 改成普通文字。
- 不隐藏 Source Gap Appendix。
- 不输出买入、卖出、持有、建仓、减仓、仓位建议、目标价或保证收益。
- 不生成真实个股样例级报告。

## 验收标准

1. pending inputs → allowed_report_level = research_draft。
2. reviewed_degraded inputs → allowed_report_level = source_gapped_research_draft 或 source_gapped_pilot_note，但 sample_quality=false。
3. 输出正文包含 Forecast/Valuation/Technical/Sentiment 的 TODO 或 source gap。
4. no-advice 测试通过。
5. composer 测试通过。

## 测试命令

```bash
python -m py_compile scripts/compose_r5_report_from_pack.py
pytest -q tests/test_r5_report_composer_degradation.py tests/test_compose_r5_report_from_pack.py tests/test_r5_report_no_advice_and_todos.py --tb=short
```

## 输出要求

完成后输出：新增/修改文件、测试结果、diff summary、degradation behavior、readout 路径。
