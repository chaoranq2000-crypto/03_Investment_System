# R5 Bundle 4.2 Dropzone Validation Readout

status: accepted_with_todos

## decision

- positive_bundle4_fixtures: `pass`
- invalid_bundle4_fixtures: `fail_closed`
- validator_output_deterministic: `true`
- fixture_paths_normalized_relative_to_root: `true`
- promotion_or_workflow_artifacts_changed: `false`
- sample_quality_report_allowed: `false`
- p2_allowed: `false`
- next_card_allowed: `true`

## issue_ids_added

- `R5DROP-ID-001`: duplicate non-empty `input_id` values across the validated root.
- `R5DROP-WORKFLOW-001`: more than one non-empty `workflow_id` in the root.
- `R5DROP-STOCK-001`: more than one non-empty `stock_code` in the root.
- `R5DROP-TEMPLATE-001`: accepted or accepted-degraded row has `template_only: true`.
- `R5DROP-NOTEVID-001`: accepted or accepted-degraded row has `not_evidence: true`.
- `R5DROP-EVIDENCE-003`: non-empty accepted `source_evidence_id` is TODO/MISSING/placeholder-like.
- `R5DROP-FOLDER-001`: row `input_type` disagrees with an allowed parent input-type directory.
- `R5DROP-DATE-001`: accepted `as_of_date` is not a valid ISO date.
- `R5DROP-DATETIME-001`: accepted `reviewed_at` is not a valid ISO timestamp.
- `R5DROP-RANK-001`: accepted `source_rank` is outside `A`, `B`, `C`, `D`, `unknown`.

## compatibility_decisions

- Existing pending rows may retain visible TODOs.
- Existing accepted-degraded rows still require `sample_quality_allowed: false`.
- Existing accepted metadata, evidence-anchor and `no_live_api` requirements remain in force.
- Unknown optional fields remain accepted for forward compatibility.
- Blank evidence continues to use the existing `R5DROP-EVIDENCE-001`; `R5DROP-EVIDENCE-003` is reserved for non-empty placeholder-like IDs.
- `checked_files` and row issue paths are now repository-independent paths relative to the validated root.

## deterministic_summary_fields

- `record_count`
- `unique_workflow_ids`
- `unique_stock_codes`
- `duplicate_input_ids`
- `counts_by_input_type`

## files_added

- `reports/p1_6/R5_BUNDLE_4_2_DROPZONE_VALIDATION_READOUT.md`

## files_modified

- `scripts/validate_r5_reviewed_input_dropzone.py`
- `tests/test_validate_r5_reviewed_input_dropzone.py`
- `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md`

## commands_run

- `$env:PYTHONDONTWRITEBYTECODE='1'; .\\.conda\\investment-system\\python.exe -B -m pytest -q tests\\test_validate_r5_reviewed_input_dropzone.py tests\\test_r5_bundle4_fixture_contract.py --tb=short -p no:cacheprovider`
- `$tmp=Join-Path $env:TEMP 'r5_bundle4_dropzone_validation.json'; & .\\.conda\\investment-system\\python.exe scripts\\validate_r5_reviewed_input_dropzone.py --root tests\\fixtures\\r5_reviewed_inputs\\accepted_core_complete --json $tmp`
- `git diff --check`
- `$tmp=Join-Path $env:TEMP 'r5_bundle4_2_truthfulness.json'; & .\\.conda\\investment-system\\python.exe scripts\\check_r5_readout_truthfulness.py --rules config\\r5_readout_truthfulness_rules.yaml --glob reports/p1_6/R5_BUNDLE_4_2_DROPZONE_VALIDATION_READOUT.md --strict --json $tmp`

## exit_code

- targeted pytest: `0`
- positive fixture CLI: `0`
- git diff check: `0`
- truthfulness check: `0`

## stdout_or_stderr_summary

- targeted pytest: `19 passed in 0.32s`.
- positive fixture CLI: `status=pass`, `checked_files=4`, `accepted=8`, `failed=0`.
- git diff check: no whitespace errors reported.
- truthfulness check: `truthfulness_status=pass checked=1 failed=0`.

## artifact_evidence

- inventory_status: `pass`
- critical_evidence: `checked=10` new stable boundary issue conditions.
- Two validations of `accepted_core_complete` are structurally identical and contain no absolute temporary paths.
- Existing pending, degraded, missing-evidence and accepted-TODO compatibility tests remain passing.

## blockers

- none for Card 4.3.

## known_todos

- Dropzone input-type payload mapping to the four physical registries is implemented and tested in Card 4.3, not inferred here.
- Validator acceptance does not itself promote any value or change a real workflow gate.

## next_recommended_patch

- R5 Bundle 4.3 - Material registry promotion, atomicity and idempotency.
