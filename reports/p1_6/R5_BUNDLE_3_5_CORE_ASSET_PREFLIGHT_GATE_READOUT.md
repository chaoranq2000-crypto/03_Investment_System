# R5 Bundle 3.5 Core Asset Preflight Gate Readout

status: accepted_with_todos

## files_added

- `.agents/skills/stock-deep-dive/scripts/run_r5_core_asset_preflight.py`
- `tests/test_r5_core_asset_preflight.py`
- `reports/p1_6/r5_core_asset_preflight_result.json`
- `reports/p1_6/R5_BUNDLE_3_5_CORE_ASSET_PREFLIGHT_GATE_READOUT.md`

## files_modified

- none

## commands_run

- `.\\.conda\\investment-system\\python.exe -m py_compile .agents\\skills\\stock-deep-dive\\scripts\\run_r5_core_asset_preflight.py`
- `.\\.conda\\investment-system\\python.exe .agents\\skills\\stock-deep-dive\\scripts\\run_r5_core_asset_preflight.py --json reports\\p1_6\\r5_core_asset_preflight_result.json`
- `.\\.conda\\investment-system\\python.exe -m pytest -q tests\\test_r5_core_asset_preflight.py --tb=short`

## exit_code

- py_compile: 0
- preflight CLI: 0
- pytest: 0

## stdout_or_stderr_summary

- preflight CLI: `r5_core_asset_state=R5_CORE_ASSET_SCHEMAS_EXECUTABLE_WITH_TODOS financial=accepted_with_todos business=accepted_with_todos forecast=accepted_with_todos valuation=accepted_with_todos sample_quality_allowed=false p2_allowed=false blockers=0`
- pytest: `4 passed in 0.14s`
- stderr: none observed

## artifact_evidence

- critical_evidence: checked=4 declared Bundle 3.5 artifacts.
- `reports/p1_6/r5_core_asset_preflight_result.json` records all four subpack statuses as `accepted_with_todos`.
- `sample_quality_report_allowed` is `false`.
- `p2_allowed` is `false`.
- Missing or malformed inputs fail closed in tests.

## known_todos

- Core subpack examples still contain visible TODO and missing markers.
- No reviewed input promotion was attempted.

## next_recommended_patch

- R5 Bundle 3.6 - Close Readout And Next Decision
