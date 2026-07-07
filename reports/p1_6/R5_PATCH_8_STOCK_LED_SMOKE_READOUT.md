# R5 Patch 8 Readout — stock-led fixture smoke dry-run

## Result

Status: fixture_only_not_real_stock_report

This patch adds a fixture-only smoke dry-run. It does not use real stock data, does not generate a real stock report, does not modify historical workflow runs, does not call APIs, and does not output trading advice.

## Files changed

- `tests/fixtures/r5_minimal_stock_run/R5_stock_research_pack.yaml`
- `tests/fixtures/r5_minimal_stock_run/R5_quality_issues.csv`
- `tests/fixtures/r5_minimal_stock_run/expected_R5_stock_research_note.md`
- `tests/test_r5_stock_led_smoke_dry_run.py`
- `reports/p1_6/R5_PATCH_8_STOCK_LED_SMOKE_READOUT.md`

## Dry-run coverage

- R5 stock research pack validator.
- Forecast / valuation / technical / sentiment example validators.
- Quality issue validator returning `accepted_with_todos`.
- Composer skeleton output from fixture pack.

## Remaining gaps before real 002837 R5 dry-run

- Real official disclosure evidence must be registered.
- Real forecast assumptions must be reviewed.
- Real market and peer snapshots must be dated and reviewed.
- Business breakdown revenue and margin gaps must remain visible until official disclosure supports them.

## Tests

```bash
pytest tests/test_r5_stock_led_smoke_dry_run.py
```

Result:

```text
tests/test_r5_stock_led_smoke_dry_run.py: 5 passed
```
