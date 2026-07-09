# R5 Patch 47 Composer Research Draft Plus Mode Readout

status: accepted_with_todos

## files_added

- `tests/test_r5_composer_research_draft_plus.py`

## files_modified

- `src/report/stock_report_writer.py`

## commands_run

- `.\\.conda\\investment-system\\python.exe -m py_compile scripts\\r5_pack_promotion_gate.py .agents\\skills\\quality-review\\scripts\\validate_r5_quality_scorecard.py src\\report\\stock_report_writer.py scripts\\r5_reviewed_input_pilot_gate.py`
- `.\\.conda\\investment-system\\python.exe -m pytest -q tests\\test_r5_002837_reviewed_input_dry_run.py tests\\test_r5_pack_promotion_gate.py tests\\test_validate_r5_quality_scorecard.py tests\\test_r5_composer_research_draft_plus.py tests\\test_r5_report_composer_degradation.py tests\\test_r5_reviewed_input_pilot_gate.py --tb=short`

## exit_code

- py_compile: 0
- pytest: 0

## stdout_or_stderr_summary

- pytest: `18 passed in 0.28s`
- stderr: none observed

## artifact_evidence

- critical_evidence: checked=2 declared Patch 47 files.
- `render_reviewed_input_research_draft` renders mixed readiness sections.
- Source-gap appendix and open questions remain visible.
- Existing source-gapped composer degradation tests still pass.
- Direct trading language is rejected.

## known_todos

- Draft-plus mode does not mark the current 002837 output as sample-quality.

## next_recommended_patch

- R5 Patch 48 - Pilot Readiness Decision
