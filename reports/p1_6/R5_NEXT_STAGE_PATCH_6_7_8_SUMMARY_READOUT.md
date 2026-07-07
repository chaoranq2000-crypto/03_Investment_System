# R5 Next Stage Summary Readout - Patch 6, 7, 8

## Result

Status: `patch_6_7_8_completed`

本组按 `codex_tasks/r5_next_stage/APPLY_ORDER.md` 完成 R5 composer skeleton、benchmark regression、fixture stock-led smoke dry-run，并在 Patch 8 后生成 R5-MVP smoke readout。

未生成真实个股研究结论，未调用 live API，未修改历史 `reports/workflow_runs/` 产物。

## Files added or changed

- `.agents/skills/stock-deep-dive/references/r5_report_composer_contract.md`
- `.agents/skills/stock-deep-dive/scripts/compose_r5_report_from_pack.py`
- `.agents/skills/stock-deep-dive/assets/r5_stock_research_note.fixture.md`
- `tests/test_compose_r5_report_from_pack.py`
- `reports/p1_6/R5_PATCH_6_COMPOSER_READOUT.md`
- `benchmarks/r5_report_quality_rubric.yaml`
- `benchmarks/r5_section_density_targets.yaml`
- `benchmarks/sample_reports/README.md`
- `tests/test_r5_report_quality_rubric.py`
- `tests/test_r5_report_no_advice_and_todos.py`
- `reports/p1_6/R5_PATCH_7_BENCHMARK_READOUT.md`
- `tests/fixtures/r5_minimal_stock_run/R5_stock_research_pack.yaml`
- `tests/fixtures/r5_minimal_stock_run/R5_quality_issues.csv`
- `tests/fixtures/r5_minimal_stock_run/expected_R5_stock_research_note.md`
- `tests/test_r5_stock_led_smoke_dry_run.py`
- `reports/p1_6/R5_PATCH_8_STOCK_LED_SMOKE_READOUT.md`
- `reports/p1_6/R5_MVP_SMOKE_READOUT_AFTER_PATCH_8.md`

## Test results

```text
pytest tests/test_compose_r5_report_from_pack.py
5 passed

pytest tests/test_r5_report_quality_rubric.py tests/test_r5_report_no_advice_and_todos.py
11 passed

pytest tests/test_r5_stock_led_smoke_dry_run.py
5 passed
```

## Source gaps and remaining work

- Composer 只消费 pack，不创造事实、数字或研究结论。
- Smoke dry-run 使用 fixture，不代表真实样例报告质量。
- 后续仍需 evidence-ingest evidence plan、close readout/task queue 模板、sample benchmark placeholder policy 与 valuation mini validator。
