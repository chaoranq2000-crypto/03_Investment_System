# R5 Patch 51 Reviewed Input Dropzone Validators Readout

status: accepted_with_todos

## files_added

- `scripts/validate_r5_reviewed_input_dropzone.py`
- `tests/test_validate_r5_reviewed_input_dropzone.py`
- `tests/fixtures/r5_reviewed_inputs/valid_pending/`
- `tests/fixtures/r5_reviewed_inputs/valid_accepted_degraded/`
- `tests/fixtures/r5_reviewed_inputs/invalid_accepted_todo/`
- `tests/fixtures/r5_reviewed_inputs/invalid_missing_evidence/`
- `reports/p1_6/r5_reviewed_input_dropzone_valid_pending.json`
- `reports/p1_6/R5_PATCH_51_REVIEWED_INPUT_DROPZONE_VALIDATORS_READOUT.md`

## files_modified

- none

## commands_run

- `.\\.conda\\investment-system\\python.exe -m py_compile scripts\\validate_r5_reviewed_input_dropzone.py`
- `.\\.conda\\investment-system\\python.exe -m pytest -q tests\\test_validate_r5_reviewed_input_dropzone.py --tb=short`
- `.\\.conda\\investment-system\\python.exe scripts\\validate_r5_reviewed_input_dropzone.py --root tests\\fixtures\\r5_reviewed_inputs\\valid_pending --json reports\\p1_6\\r5_reviewed_input_dropzone_valid_pending.json`

## exit_code

- py_compile: 0
- pytest: 0
- valid_pending CLI: 0

## stdout_or_stderr_summary

- pytest: `4 passed in 0.07s`
- valid_pending CLI: `r5_reviewed_input_dropzone_status=pass checked_files=1 accepted=0 accepted_degraded=0 pending=1 rejected=0 failed=0`
- stderr: none observed

## artifact_evidence

- critical_evidence: checked=7 declared Patch 51 validator, fixture, result, and readout artifacts.
- Validator reads CSV and YAML files under a provided root path.
- JSON summary includes `status`, `checked_files`, accepted/pending/rejected counts, `failed_count`, and `issues`.
- Accepted rows reject TODO tokens and null evidence anchors.
- `accepted_degraded` requires `sample_quality_allowed: false`.
- Pending rows may preserve TODO markers but produce `accepted_count: 0`.

## known_todos

- No real reviewed inputs are present in `data/reviewed_inputs/`.
- The validator does not promote registries; promotion is deferred to Patch 53.

## next_recommended_patch

- R5 Patch 52 - 002837 Reviewed Input Staging Dry Run
