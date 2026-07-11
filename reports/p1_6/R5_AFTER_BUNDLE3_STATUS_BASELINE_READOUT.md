# R5 After Bundle 3 Status Baseline Readout

status: accepted_with_todos

## baseline_decision

- base_state: `R5_CORE_ASSET_SCHEMAS_EXECUTABLE_WITH_TODOS`
- real_workflow: `wf_20260703_stock_first_002837_invic`
- real_reviewed_input_pilot_allowed: `false`
- real_accepted_reviewed_inputs_present: `false`
- sample_quality_report_allowed: `false`
- p2_allowed: `false`
- fixture_mode_may_open_sample_quality: `false`
- fixture_mode_may_open_p2: `false`

This card defines expected artifacts only. It does not create fixtures, promote inputs, modify workflow-run artifacts or change any gate decision.

## files_added

- `config/r5_bundle4_expected_artifacts.yaml`
- `reports/p1_6/R5_AFTER_BUNDLE3_STATUS_BASELINE_READOUT.md`

## files_modified

- `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md`

## commands_run

- `.\\.conda\\investment-system\\python.exe -c "import yaml; from pathlib import Path; p=Path('config/r5_bundle4_expected_artifacts.yaml'); data=yaml.safe_load(p.read_text(encoding='utf-8')); assert isinstance(data, dict); assert data.get('bundle') == 'R5_BUNDLE_4_REVIEWED_INPUT_FIXTURE_PROMOTION_SMOKE'; assert data.get('fixture_mode_sample_quality_allowed') is False; assert data.get('p2_allowed') is False; print('bundle4 expected artifacts yaml ok')"`
- `git diff --check`
- `$tmp=Join-Path $env:TEMP 'r5_bundle4_baseline_truthfulness.json'; & .\\.conda\\investment-system\\python.exe scripts\\check_r5_readout_truthfulness.py --rules config\\r5_readout_truthfulness_rules.yaml --glob reports/p1_6/R5_AFTER_BUNDLE3*READOUT.md --strict --json $tmp`

## exit_code

- expected-artifact YAML parse: `0`
- git diff check: `0`
- truthfulness check: `0`

## stdout_or_stderr_summary

- expected-artifact YAML parse: `bundle4 expected artifacts yaml ok`.
- git diff check: no whitespace errors reported.
- truthfulness check: `truthfulness_status=pass checked=1 failed=0`.

## artifact_evidence

- inventory_status: `pass`
- critical_evidence: `checked=3` Card 4.0 manifest, baseline readout and canonical index surfaces.
- The manifest groups repository-relative expected artifacts for Cards 4.1 through 4.6.
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_reviewed_input_staging_result.yaml` records `accepted_count: 0`, all five reviewed flags false, `sample_quality_report_allowed: false` and `p2_allowed: false`.
- `reports/p1_6/r5_reviewed_input_pilot_gate_result.json` records `R5_REVIEWED_INPUT_PILOT_BLOCKED_SOURCE_GAPPED` with the real pilot, sample-quality and P2 all false.
- forbidden_scope_diff: `0` changes under `reports/workflow_runs/**`, `data/reviewed_inputs/**`, `data/raw/**`, `data/processed/**` and `data/manifests/**` in Card 4.0.

## known_todos

- Fixture matrix, validator hardening, material registry writes, post-promotion reconstruction and smoke runner are expected artifacts, not yet implemented by this card.
- The real 002837 workflow remains source-gapped.
- `TODO_MODEL_INPUT`, `TODO_MARKET_DATA`, `TODO_PEER_DATA`, `MISSING_DISCLOSURE` and `TODO_SOURCE_REQUIRED` remain unresolved for the real workflow.

## next_recommended_patch

- R5 Bundle 4.1 - Accepted reviewed-input fixture set.
