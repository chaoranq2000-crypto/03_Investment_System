# R5 Bundle 4.6 — Close readout and real-input next decision

## Background

Bundle 4 closes only the fixture-based activation and registry-promotion capability. It must not claim that 002837 now has reviewed market, peer, forecast, valuation or business inputs.

## Goal

Run the full relevant test set, truthfully close Bundle 4, update the canonical readout index and define the next real-input onboarding bundle.

## Allowed files

- `tests/test_r5_bundle4_close.py`
- `reports/p1_6/R5_BUNDLE_4_REVIEWED_INPUT_FIXTURE_PROMOTION_CLOSE_READOUT.md`
- `reports/p1_6/r5_bundle4_readout_truthfulness_result.json`
- `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md`
- `config/r5_bundle4_expected_artifacts.yaml` only to reconcile final physical paths

## Forbidden scope

- Do not alter implementation merely to make the close test pass; return to the owning card instead.
- Do not edit historical readouts to erase blockers.
- Do not supply real 002837 evidence in this card.
- Do not allow sample-quality or P2.
- Do not generate a stock report.

## Required close checks

Verify:

- every artifact declared in `config/r5_bundle4_expected_artifacts.yaml` exists;
- positive and invalid fixtures behave as specified;
- registry promotion physically writes valid files;
- invalid promotion is atomic;
- identical rerun is idempotent;
- post-promotion flags come from registries, not accepted-row presence alone;
- fixture mode caps sample-quality and P2;
- real 002837 committed gate result remains source-gapped;
- Bundle 3 close tests still pass;
- readout truthfulness and `git diff --check` pass.

## Canonical close decision

If all checks pass, use:

```text
status: accepted_with_todos
current_r5_state: R5_REVIEWED_INPUT_FIXTURE_PROMOTION_SMOKE_PASSED
fixture_pipeline_executable: true
real_002837_reviewed_inputs_supplied: false
real_002837_reviewed_input_pilot_allowed: false
sample_quality_report_allowed: false
p2_allowed: false
```

Do not use `R5_REVIEWED_INPUT_PILOT_ALLOWED` for the real workflow.

If the material writer, atomicity, idempotency, registry validation or fixture isolation fails, close as blocked and list the failing card. A partial positive path is not sufficient.

## Next recommended bundle

Recommend **R5 Bundle 5 — Real reviewed-input onboarding for 002837**, ordered as:

1. locally reviewed dated market snapshot;
2. reviewed peer set and peer metrics;
3. reviewed forecast assumptions tied to accepted evidence/metrics;
4. reviewed valuation-input registry and method eligibility;
5. reviewed official business disclosure;
6. rerun core subpacks, composer and quality gate.

Bundle 5 must use real evidence IDs and reviewer metadata. It should first target `reviewed_input_research_draft`, not sample-quality. Sample-quality remains a separate explicit gate after all critical TODOs and quality blockers are cleared.

## Suggested commands

```bash
python scripts/run_r5_bundle4_reviewed_input_smoke.py   --fixture-root tests/fixtures/r5_reviewed_inputs   --json reports/p1_6/r5_bundle4_reviewed_input_smoke_result.json
python -m pytest -q   tests/test_validate_r5_reviewed_input_dropzone.py   tests/test_r5_reviewed_input_registry_promotion.py   tests/test_r5_bundle4_fixture_contract.py   tests/test_r5_bundle4_registry_promotion.py   tests/test_r5_bundle4_registry_idempotency.py   tests/test_r5_bundle4_post_promotion_dry_run.py   tests/test_r5_bundle4_reviewed_input_smoke.py   tests/test_r5_bundle4_close.py   tests/test_r5_bundle3_close.py --tb=short
python scripts/check_r5_readout_truthfulness.py   --rules config/r5_readout_truthfulness_rules.yaml   --glob 'reports/p1_6/R5_BUNDLE_4*READOUT.md'   --strict   --json reports/p1_6/r5_bundle4_readout_truthfulness_result.json
git diff --check
```

## Output requirements

- List files added and modified.
- List every command, exit code and concise stdout/stderr summary.
- Record fixture and real-workflow decisions separately.
- Record blockers, known TODOs and next recommended bundle.
