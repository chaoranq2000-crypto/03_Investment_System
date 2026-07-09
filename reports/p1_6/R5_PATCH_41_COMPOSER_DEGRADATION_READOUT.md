# R5 Patch 41 Composer Degradation Readout

status: accepted_with_todos

## files_added

- `scripts/compose_r5_report_from_pack.py`
- `reports/p1_6/R5_PATCH_41_COMPOSER_DEGRADATION_READOUT.md`

## files_modified

- `templates/r5_stock_research_note.md`
- `tests/test_r5_report_composer_degradation.py`

## commands_run

- `.\\.conda\\investment-system\\python.exe -m py_compile scripts\\compose_r5_report_from_pack.py`
- `.\\.conda\\investment-system\\python.exe -m pytest -q tests\\test_r5_report_composer_degradation.py tests\\test_compose_r5_report_from_pack.py tests\\test_r5_report_no_advice_and_todos.py --tb=short`

## exit_code

- py_compile: 0
- pytest: 0

## stdout_or_stderr_summary

- pytest: `18 passed in 0.34s`

## artifact_evidence

- checked=4 declared Patch 41 files.
- Pending registries degrade composer output to `research_draft`.
- Reviewed-degraded registries can only reach `source_gapped_pilot_note`, not sample-quality.
- Source Gap Appendix remains visible and no-advice tests pass.

## known_todos

- Composer does not create forecast, valuation, technical, or sentiment facts while registry inputs remain pending.

## next_recommended_patch

- R5 Patch 42 - Close Readout and Status Freeze
