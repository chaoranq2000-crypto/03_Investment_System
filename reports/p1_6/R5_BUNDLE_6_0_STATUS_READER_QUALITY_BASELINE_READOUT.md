# R5 Bundle 6.0 — Status and Reader-quality Baseline Readout

status: accepted_baseline_only

## files_added

- `scripts/build_r5_bundle6_reader_baseline.py`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle6_reader_surface_baseline.yaml`
- `tests/test_r5_bundle6_reader_baseline.py`
- `reports/p1_6/R5_BUNDLE_6_0_STATUS_READER_QUALITY_BASELINE_READOUT.md`

## files_modified

- none; the Bundle 5 draft, evidence and registries were preserved byte-for-byte.

## commands_run

- `.\.conda\investment-system\python.exe scripts\check_r5_readout_truthfulness.py --rules config\r5_readout_truthfulness_rules.yaml --glob 'reports/p1_6/R5_BUNDLE_5*READOUT.md' --strict`
- `.\.conda\investment-system\python.exe -m pytest -q tests\test_r5_bundle5_close.py --tb=short -p no:cacheprovider`
- `.\.conda\investment-system\python.exe -m pytest -q --tb=short -p no:cacheprovider`
- `.\.conda\investment-system\python.exe scripts\build_r5_bundle6_reader_baseline.py --repo-root . --full-pytest-summary "510 passed, 2 skipped in 20.98s" --bundle5-close-summary "9 passed in 0.17s"`

## exit_code

- truthfulness_exit_code: `0`
- bundle5_close_exit_code: `0`
- full_pytest_exit_code: `0`
- baseline_builder_exit_code: `0`

## stdout_or_stderr_summary

- truthfulness: `pass checked=8 failed=0`
- Bundle 5 close: `9 passed in 0.17s`
- full repository: `510 passed, 2 skipped in 20.98s`
- report_sha256: `5a3b041d87cebd1dbf7f433ef5cd5f5032bc4fd5c1000733d9ae2ceebe95f64c`
- quality_gate_sha256: `1930d40da623aee924e6fbaed8a003455709c887171e5d7adf3ed920de78c320`
- reader_surface_inventory_status: `complete`
- raw_internal_ids=5; internal_paths=4; gap_tokens=5; over_precise_values=3; duplicate_machine_sections=10
- coverage_checked=10; covered=4; partial=4; missing=2

## known_todos

- The frozen Bundle 5 draft remains an audit-oriented research draft and is not a reader-facing candidate.
- Cards 6.1-6.8 must build a separate reader report, traceability appendix and reader-quality gate.

## next_recommended_patch

- Execute Card 6.1 and define the reader-report/traceability split contract without changing evidence or Registry state.

## fixed_boundaries

- current_draft_rewritten: `false`
- canonical_state_changed: `false`
- sample_quality_report_allowed: `false`
- p2_allowed: `false`
