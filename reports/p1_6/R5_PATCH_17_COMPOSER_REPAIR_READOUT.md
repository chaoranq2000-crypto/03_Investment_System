# R5 Patch 17 Composer Repair Readout

status: `PASS`

## Scope

Patch 17 repaired the existing R5 composer at `.agents/skills/stock-deep-dive/scripts/compose_r5_report_from_pack.py`. It did not call an LLM, did not generate a real stock report, did not alter historical workflow-run conclusions, and did not output buy / sell / hold / position-sizing language.

## Files Added

```text
reports/p1_6/R5_PATCH_17_COMPOSER_REPAIR_READOUT.md
```

## Files Modified

```text
.agents/skills/stock-deep-dive/scripts/compose_r5_report_from_pack.py
tests/test_compose_r5_report_from_pack.py
```

## Behavior Added

- `sample_quality_candidate` is downgraded to `research_draft` unless required packs are ready and quality gates pass.
- The composer scans input pack text for forbidden trading-action phrases before rendering.
- `assert_no_new_numbers(pack_text, note)` makes the no-new-number rule directly testable.
- CLI composition now uses the same no-new-number assertion.
- Source gaps remain visible in `Source Gap Appendix`.

## Artifact Evidence

```text
checked=9 composer/writer regression tests
line_count compose_r5_report_from_pack.py: 160
line_count test_compose_r5_report_from_pack.py: 85
```

## Command Note

The task card names `src/report/stock_report_writer.py` as a possible composer surface. The current checkout already has a dedicated R5 composer:

```text
.agents/skills/stock-deep-dive/scripts/compose_r5_report_from_pack.py
```

Patch 17 repaired that R5-specific live composer and reran the legacy writer test to confirm no regression.

## Commands Run

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m py_compile .agents/skills/stock-deep-dive/scripts/compose_r5_report_from_pack.py src/report/stock_report_writer.py
```

exit_code: `0`

stdout_or_stderr_summary:

```text
Both composer/writer files compiled successfully.
```

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m pytest -q tests/test_compose_r5_report_from_pack.py tests/test_stock_report_writer.py --tb=short
```

exit_code: `0`

stdout_or_stderr_summary:

```text
9 passed in 0.18s
```

## Known TODOs

- The R5 composer remains a source-gapped skeleton composer. It intentionally does not write analyst conclusions or create new numeric analysis.
- Patch 15 inventory remains `accepted: false`; this composer repair does not promote Patch 1-12 to `validated_complete`.

## Next Recommended Patch

```text
R5_PATCH_18_REPRODUCIBLE_FIXTURE_SMOKE.md
```
