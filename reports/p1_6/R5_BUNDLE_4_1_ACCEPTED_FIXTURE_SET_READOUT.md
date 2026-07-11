# R5 Bundle 4.1 Accepted Fixture Set Readout

status: accepted_with_todos

## decision

- fixture_workflow: `wf_fixture_r5_bundle4`
- fixture_stock_code: `000000`
- fixture_values_are_research_evidence: `false`
- real_002837_workflow_changed: `false`
- sample_quality_report_allowed: `false`
- p2_allowed: `false`
- next_card_allowed: `true`

## fixture_scenarios

- `accepted_core_complete`: eight accepted rows across market, peer, five core forecast drivers and valuation; business disclosure intentionally absent.
- `accepted_all_complete`: nine accepted rows covering all readiness types and five core forecast drivers; fixture-mode gate caps remain false.
- `mixed_status`: one accepted, one accepted-degraded, one pending and one rejected row.
- `invalid_duplicate_input_id`: two otherwise valid rows share `fixture_duplicate_001`.
- `invalid_cross_workflow`: one row uses `wf_fixture_r5_bundle4_other`.
- `invalid_cross_stock`: one row uses `fixture_other_stock`.
- `invalid_template_as_evidence`: one accepted row is `template_only`, another is `not_evidence`.
- `invalid_folder_type_mismatch`: a `peer_snapshot` row is stored below `market_snapshot/`.
- Existing `invalid_missing_evidence` and `invalid_accepted_todo` cases remain present and unchanged.

## compatibility_decisions

- The eight new Bundle 4 scenarios use the synthetic fixture identity except the two scenarios that deliberately test workflow or stock mismatch.
- Four pre-Bundle4 compatibility fixtures retain their historical 002837-shaped metadata because Card 4.1 requires retaining them but does not authorize changing their directories. They are validated only in isolated test roots, are never promoted, and do not write to the real workflow.

## files_added

- `tests/fixtures/r5_reviewed_inputs/README.md`
- `tests/fixtures/r5_reviewed_inputs/accepted_core_complete/**`
- `tests/fixtures/r5_reviewed_inputs/accepted_all_complete/**`
- `tests/fixtures/r5_reviewed_inputs/mixed_status/**`
- `tests/fixtures/r5_reviewed_inputs/invalid_duplicate_input_id/**`
- `tests/fixtures/r5_reviewed_inputs/invalid_cross_workflow/**`
- `tests/fixtures/r5_reviewed_inputs/invalid_cross_stock/**`
- `tests/fixtures/r5_reviewed_inputs/invalid_template_as_evidence/**`
- `tests/fixtures/r5_reviewed_inputs/invalid_folder_type_mismatch/**`
- `tests/test_r5_bundle4_fixture_contract.py`
- `reports/p1_6/R5_BUNDLE_4_1_ACCEPTED_FIXTURE_SET_READOUT.md`

## files_modified

- `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md`

## commands_run

- `$env:PYTHONDONTWRITEBYTECODE='1'; .\\.conda\\investment-system\\python.exe -B -m pytest -q tests\\test_r5_bundle4_fixture_contract.py tests\\test_validate_r5_reviewed_input_dropzone.py --tb=short -p no:cacheprovider`
- `git diff --check`
- `$tmp=Join-Path $env:TEMP 'r5_bundle4_1_truthfulness.json'; & .\\.conda\\investment-system\\python.exe scripts\\check_r5_readout_truthfulness.py --rules config\\r5_readout_truthfulness_rules.yaml --glob reports/p1_6/R5_BUNDLE_4_1_ACCEPTED_FIXTURE_SET_READOUT.md --strict --json $tmp`

## exit_code

- targeted pytest: `0`
- git diff check: `0`
- truthfulness check: `0`

## stdout_or_stderr_summary

- targeted pytest: `12 passed in 0.19s` after expanding both positive forecast fixtures to all five core drivers.
- git diff check: no whitespace errors reported.
- truthfulness check: `truthfulness_status=pass checked=1 failed=0`.

## artifact_evidence

- inventory_status: `pass`
- critical_evidence: `checked=22` new fixture payload files across eight scenarios.
- The boundary README and fixture-contract test are present.
- The contract test confirms that no `wf_fixture_r5_bundle4` path or `ev_fixture_*` content exists under `data/reviewed_inputs/**`.

## blockers

- none for Card 4.2.

## known_todos

- The current dropzone validator does not yet enforce duplicate IDs, cross-identity consistency, template/evidence separation, folder/type consistency or accepted-row date formatting; Card 4.2 owns those checks.
- Synthetic accepted rows are test inputs only and do not resolve any real 002837 TODO.

## next_recommended_patch

- R5 Bundle 4.2 - Dropzone validation and fixture boundary.
