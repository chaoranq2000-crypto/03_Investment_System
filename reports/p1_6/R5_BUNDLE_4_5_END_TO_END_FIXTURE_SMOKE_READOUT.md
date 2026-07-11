# R5 Bundle 4.5 End-to-End Fixture Smoke Readout

status: accepted_with_todos

## decision

- overall_status: `pass`
- fixture_mode: `true`
- scenario_count: `6`
- real_002837_workflow_changed: `false`
- sample_quality_report_allowed: `false`
- p2_allowed: `false`
- next_card_allowed: `true`
- recommended_close_state: `R5_REVIEWED_INPUT_FIXTURE_PROMOTION_SMOKE_PASSED`

## scenario_decisions

- `empty_or_pending`: pass; five reviewed flags false, all five TODOs visible, four registry actions unchanged.
- `accepted_core_complete`: pass; market/peer/forecast/valuation true, business false, `MISSING_DISCLOSURE` remains, four registries created.
- `accepted_all_complete`: pass; all five internal flags true, no remaining fixture TODO, external level capped at `reviewed_input_research_draft`.
- `mixed_status`: pass; only accepted market activates a flag; accepted-degraded, pending and rejected rows remain non-facts.
- `invalid_input`: pass as an expected negative; dropzone blocks and all four registry actions are blocked with unchanged hashes.
- `idempotent_rerun`: pass; second run reports four unchanged actions and stable hashes.

## executed_chain

```text
dropzone validation
  -> physical registry promotion
  -> registry validators
  -> registry-derived dry-run reconstruction
  -> fixture safety-cap decision
  -> scenario expectation check
```

Every scenario uses a fresh isolated work directory. The committed smoke result contains no absolute or transient work paths, timestamps or durations.

## files_added

- `scripts/run_r5_bundle4_reviewed_input_smoke.py`
- `tests/test_r5_bundle4_reviewed_input_smoke.py`
- `reports/p1_6/r5_bundle4_reviewed_input_smoke_result.json`
- `reports/p1_6/R5_BUNDLE_4_5_END_TO_END_FIXTURE_SMOKE_READOUT.md`

## files_modified

- `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md`

## commands_run

- `$env:PYTHONDONTWRITEBYTECODE='1'; .\\.conda\\investment-system\\python.exe -B -m py_compile scripts\\run_r5_bundle4_reviewed_input_smoke.py`
- `$env:PYTHONDONTWRITEBYTECODE='1'; .\\.conda\\investment-system\\python.exe -B -m pytest -q tests\\test_r5_bundle4_reviewed_input_smoke.py tests\\test_r5_reviewed_input_pilot_gate.py tests\\test_r5_after_patch55_close.py tests\\test_r5_bundle3_close.py --tb=short -p no:cacheprovider`
- `.\\.conda\\investment-system\\python.exe scripts\\run_r5_bundle4_reviewed_input_smoke.py --repo-root . --fixture-root tests\\fixtures\\r5_reviewed_inputs --work-root .codex_tmp\\r5_bundle4_smoke_card45_20260711_1320 --json reports\\p1_6\\r5_bundle4_reviewed_input_smoke_result.json`
- `rg -n "C:\\\\|\\.codex_tmp|r5_bundle4_smoke_card45" reports\\p1_6\\r5_bundle4_reviewed_input_smoke_result.json`
- `git diff --check`
- `$tmp=Join-Path $env:TEMP 'r5_bundle4_5_truthfulness.json'; & .\\.conda\\investment-system\\python.exe scripts\\check_r5_readout_truthfulness.py --rules config\\r5_readout_truthfulness_rules.yaml --glob reports/p1_6/R5_BUNDLE_4_5_END_TO_END_FIXTURE_SMOKE_READOUT.md --strict --json $tmp`

## exit_code

- py_compile: `0`
- targeted pytest: `0`
- end-to-end smoke CLI: `0`
- transient-path scan: `1`, the expected no-match result.
- git diff check: `0`
- truthfulness check: `0`

## stdout_or_stderr_summary

- targeted pytest: `17 passed in 7.62s`.
- smoke CLI: `overall_status=pass`, six scenarios, `real_workflow_unchanged=true`, sample-quality/P2 false.
- transient-path scan: no absolute, `.codex_tmp` or smoke work-root strings found in the committed JSON.
- git diff check: no whitespace errors reported.
- truthfulness check: `truthfulness_status=pass checked=1 failed=0`.

## artifact_evidence

- inventory_status: `pass`
- critical_evidence: `checked=6` scenario decisions with step results, registry actions/hashes, reviewed flags, TODOs, safety caps, blockers and expectation outcomes.
- The network-guard test monkeypatches socket connection paths to fail if any network call is attempted.
- The real-workflow test hashes the four committed 002837 registry targets before and after the smoke.

## blockers

- none for Card 4.6.

## known_todos

- Fixture pipeline success does not supply any real 002837 reviewed input.
- Real reviewed-input pilot, sample-quality report generation and P2 remain closed.

## next_recommended_patch

- R5 Bundle 4.6 - Close readout and real-input next decision.
