# R5 Patch 18 Reproducible Fixture Smoke Readout

status: `PASS`

## Scope

Patch 18 added a reproducible local smoke test for the virtual, source-gapped R5 fixture. It does not use real stock data, does not call live APIs, does not generate investment conclusions, and does not output buy / sell / hold / position-sizing language.

## Files Added

```text
tests/test_r5_mvp_fixture_smoke.py
reports/p1_6/R5_PATCH_18_REPRODUCIBLE_FIXTURE_SMOKE_READOUT.md
```

## Files Modified

```text
None.
```

## Fixture Strategy

The test reuses the existing virtual workflow fixture:

```text
tests/fixtures/r5_minimal_stock_run/R5_stock_research_pack.yaml
tests/fixtures/r5_minimal_stock_run/R5_quality_issues.csv
```

Invalid cases are produced by in-test mutations of that fixture instead of copying another large YAML file. This keeps the smoke reproducible while avoiding duplicated fixture drift.

## Smoke Coverage

- Valid source-gapped R5 pack validates as `accepted_with_todos`.
- Forecast and valuation example subpack validators run successfully.
- R5 composer generates a note with visible `Source Gap Appendix`.
- R5 quality issue validator returns `accepted_with_todos`.
- Missing valuation pack is blocked or downgraded.
- Hidden source gap register is blocked.
- Sample-quality candidate with missing valuation is downgraded to `research_draft`.
- Generated note avoids direct trading-action language.

## Artifact Evidence

```text
checked=4 Patch 18 smoke tests
checked=5 existing R5 stock-led smoke tests
line_count tests/test_r5_mvp_fixture_smoke.py: 97
```

## Commands Run

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m pytest -q tests/test_r5_mvp_fixture_smoke.py --tb=short
```

exit_code: `0`

stdout_or_stderr_summary:

```text
4 passed in 0.13s
```

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m pytest -q tests/test_r5_stock_led_smoke_dry_run.py --tb=short
```

exit_code: `0`

stdout_or_stderr_summary:

```text
5 passed in 0.08s
```

## Known TODOs

- This smoke uses the R5 quality issue validator, not the older R4-oriented `stock_report_quality_review.py`, because the latter expects `stock_analysis_pack.yaml`, claims registry, metrics registry, and R4 sample-quality draft surfaces.
- Patch 15 inventory remains `accepted: false`; smoke success does not promote Patch 4-12 to `validated_complete`.

## Next Recommended Patch

```text
R5_PATCH_19_READOUT_TRUTHFULNESS_GATE.md
```
