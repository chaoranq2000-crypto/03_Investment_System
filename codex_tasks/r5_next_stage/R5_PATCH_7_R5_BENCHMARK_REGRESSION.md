# R5 Patch 7：R5 benchmark regression

## 背景

R5 质量不能靠主观“像不像样例”判断，必须有 benchmark rubric 和 regression test。本 patch 将已有 rubric 扩展为可测试标准。

## 目标

1. 新增 section density targets。
2. 新增 sample reports benchmark README，说明样例如何使用，避免直接复制版权内容。
3. 新增 rubric regression test。
4. 新增 no-advice / hidden TODO / required section 检查。
5. 输出 readout。

## 允许修改文件

- `benchmarks/r5_report_quality_rubric.yaml`
- `benchmarks/r5_section_density_targets.yaml`
- `benchmarks/sample_reports/README.md`
- `tests/test_r5_report_quality_rubric.py`
- `tests/test_r5_report_no_advice_and_todos.py`
- `reports/p1_6/R5_PATCH_7_BENCHMARK_READOUT.md`

## 禁止事项

- 不粘贴外部版权研报全文。
- 不新增真实个股报告。
- 不修改历史 workflow run。
- 不输出交易建议。
- 不把“样例风格”理解为必须给评级或仓位建议。

## 交付物

- density targets YAML。
- sample reports README。
- rubric tests。
- readout。

## 验收标准

1. rubric 覆盖：financial_overview、business_breakdown、industry_analysis、forecast、valuation、technical、sentiment、catalyst、conclusion。
2. 每章定义 `required`、`optional`、`blocked` 条件。
3. forecast 缺失时不能 sample-quality。
4. valuation 缺 market snapshot / peer context 时不能 sample-quality。
5. source gap / TODO 必须显式展示。
6. no-advice gate 必须存在。
7. pytest 通过。

## 测试命令

```bash
pytest tests/test_r5_report_quality_rubric.py tests/test_r5_report_no_advice_and_todos.py
```

## 输出要求

1. 列出修改文件。
2. 粘贴测试结果。
3. 说明 benchmark 不包含外部版权正文。
4. 输出 readout 文件。
