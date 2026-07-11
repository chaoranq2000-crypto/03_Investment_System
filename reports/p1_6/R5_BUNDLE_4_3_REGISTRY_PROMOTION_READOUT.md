# R5 Bundle 4.3 Registry Promotion Readout

status: accepted_with_todos

## decision

- material_registry_writer: `pass`
- candidate_validation_before_write: `pass`
- caught_failure_rollback: `pass`
- identical_second_run_idempotent: `pass`
- fixture_mode_isolated: `true`
- real_002837_workflow_changed: `false`
- sample_quality_report_allowed: `false`
- p2_allowed: `false`
- next_card_allowed: `true`

## materialized_registries

- `R5_market_peer_input_registry.yaml`: accepted market and peer snapshots become evidence-anchored fields; missing sections retain explicit TODO values.
- `R5_forecast_assumption_registry.yaml`: accepted forecast rows become a superset compatible with the canonical registry validator and downstream assumption validator; five core drivers remain visible when pending.
- `R5_valuation_input_registry.yaml`: market, peer, forecast, business and valuation references are recorded separately; relative, DCF and SOTP eligibility is re-derived from prerequisite readiness.
- `R5_evidence_request_review_ledger.yaml`: every intake decision is retained; accepted-degraded maps to `needs_manual_collection`, while pending and rejected rows never become facts.

## merge_and_provenance_rules

- Stable keys are market/peer field name, forecast driver/assumption ID, valuation method, and ledger request ID.
- Every promoted fact retains `input_id`, source evidence ID/rank, as-of date, reviewer, reviewed timestamp and limitations.
- Unrelated valid market fields, forecast rows, valuation methods and ledger items are preserved.
- Different accepted evidence competing for the same logical record blocks the whole transaction.
- All four serialized candidates are validator-checked before any target replacement.

## first_run_summary

- promotion_status: `accepted_inputs_promoted`
- registries_changed: `true`
- registry actions: `created, created, created, created`
- allowed_report_level: `reviewed_input_research_draft`
- accepted inputs: `8`

## second_run_summary

- promotion_status: `accepted_inputs_unchanged`
- registries_changed: `false`
- registry actions: `unchanged, unchanged, unchanged, unchanged`
- all four before/after hashes remained stable.

## rollback_summary

- The test changed both a market value and a forecast value, then injected failure on the second `os.replace`.
- The helper restored all four pre-run byte sequences, removed explicit staging files and returned `blocked_atomic_commit`.

## files_added

- `scripts/r5_reviewed_input_registry_io.py`
- `tests/test_r5_bundle4_registry_promotion.py`
- `tests/test_r5_bundle4_registry_idempotency.py`
- `reports/p1_6/R5_BUNDLE_4_3_REGISTRY_PROMOTION_READOUT.md`

## files_modified

- `scripts/promote_r5_reviewed_inputs_to_registries.py`
- `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md`

## commands_run

- `$env:PYTHONDONTWRITEBYTECODE='1'; .\\.conda\\investment-system\\python.exe -B -m py_compile scripts\\r5_reviewed_input_registry_io.py scripts\\promote_r5_reviewed_inputs_to_registries.py`
- `$env:PYTHONDONTWRITEBYTECODE='1'; .\\.conda\\investment-system\\python.exe -B -m pytest -q tests\\test_r5_reviewed_input_registry_promotion.py tests\\test_r5_bundle4_registry_promotion.py tests\\test_r5_bundle4_registry_idempotency.py tests\\test_validate_r5_market_peer_input_registry.py tests\\test_validate_r5_forecast_assumption_registry.py tests\\test_validate_r5_forecast_assumptions.py tests\\test_validate_r5_valuation_inputs.py tests\\test_validate_r5_evidence_request_review_ledger.py --tb=short -p no:cacheprovider`
- `.\\.conda\\investment-system\\python.exe scripts\\promote_r5_reviewed_inputs_to_registries.py --repo-root . --workflow-id wf_fixture_r5_bundle4 --stock-code 000000 --dropzone-root tests\\fixtures\\r5_reviewed_inputs\\accepted_core_complete --output-run-dir $env:TEMP\\r5_bundle4_card43_run --fixture-mode --json $env:TEMP\\r5_bundle4_card43_first.json`
- Repeat the previous CLI command with `--json $env:TEMP\\r5_bundle4_card43_second.json`.
- `git diff --check`
- `$tmp=Join-Path $env:TEMP 'r5_bundle4_3_truthfulness.json'; & .\\.conda\\investment-system\\python.exe scripts\\check_r5_readout_truthfulness.py --rules config\\r5_readout_truthfulness_rules.yaml --glob reports/p1_6/R5_BUNDLE_4_3_REGISTRY_PROMOTION_READOUT.md --strict --json $tmp`

## exit_code

- py_compile: `0`
- targeted pytest: `0`
- first promotion CLI: `0`
- second promotion CLI: `0`
- git diff check: `0`
- truthfulness check: `0`

## stdout_or_stderr_summary

- targeted pytest: `33 passed in 2.25s`.
- first CLI: `accepted_inputs_promoted`, `registries_changed=true`, four `created` actions.
- second CLI: `accepted_inputs_unchanged`, `registries_changed=false`, four `unchanged` actions.
- git diff check: no whitespace errors reported.
- truthfulness check: `truthfulness_status=pass checked=1 failed=0`.

## artifact_evidence

- inventory_status: `pass`
- critical_evidence: `checked=4` physical registry candidates, each with before/after SHA-256, action and validator decision.
- Core, all-complete, mixed, invalid, dry-run, idempotency, unrelated-row preservation and injected-failure rollback scenarios are executable tests.

## blockers

- none for Card 4.4.

## known_todos

- Process-caught write failures are rollback-protected; no ordinary filesystem can provide a single OS-level atomic rename spanning four separate files during abrupt power loss.
- Registry validity does not itself prove readiness; Card 4.4 must derive flags and TODO resolution from the validated physical files.
- Synthetic fixture facts do not resolve real 002837 research gaps.

## next_recommended_patch

- R5 Bundle 4.4 - Post-promotion dry run derived from registries.
