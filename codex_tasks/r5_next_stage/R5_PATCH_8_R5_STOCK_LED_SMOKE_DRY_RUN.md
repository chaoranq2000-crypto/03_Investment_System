# R5 Patch 8：R5 stock-led fixture smoke dry-run

## 背景

完成 R5 pack validator、mapping validator、quality issue validator、forecast/valuation/technical/sentiment validators 和 composer skeleton 后，需要一次 fixture dry-run 验证 R5-MVP 工程闭环。本 patch 使用测试 fixture，不写真实个股研究结论。

## 目标

1. 新增 R5 minimal fixture run。
2. 使用 fixture pack 跑 validator、composer、quality issue validator。
3. 输出 dry-run readout，标明当前是 fixture，不是正式报告。
4. 给出进入真实英维克 R5 dry-run 前的 remaining gaps。

## 允许修改文件

- `tests/fixtures/r5_minimal_stock_run/R5_stock_research_pack.yaml`
- `tests/fixtures/r5_minimal_stock_run/R5_quality_issues.csv`
- `tests/fixtures/r5_minimal_stock_run/expected_R5_stock_research_note.md`
- `tests/test_r5_stock_led_smoke_dry_run.py`
- `reports/p1_6/R5_PATCH_8_STOCK_LED_SMOKE_READOUT.md`

## 禁止事项

- 不使用真实股票数据。
- 不生成真实股票报告。
- 不修改 `reports/workflow_runs/` 历史 run。
- 不接 API。
- 不输出交易建议。
- 不把 fixture 中的 TODO 当事实。

## 交付物

- fixture pack。
- fixture quality issues。
- expected note。
- smoke test。
- readout。

## 验收标准

1. fixture pack 能通过 `validate_r5_stock_research_pack.py`。
2. fixture forecast / valuation / technical / sentiment 子包能通过对应 validator。
3. composer 能从 fixture pack 生成 note。
4. quality issue validator 能识别 `accepted_with_todos`。
5. dry-run readout 明确标注 `fixture_only_not_real_stock_report`。
6. pytest 通过。

## 测试命令

```bash
pytest tests/test_r5_stock_led_smoke_dry_run.py
```

## 输出要求

1. 列出修改文件。
2. 粘贴测试结果。
3. 明确说明该 patch 没有生成真实股票结论。
4. 输出 readout 文件。
