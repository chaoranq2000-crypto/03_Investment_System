# R5 Bundle 5.8 — Close readout and next decision

## Background

Bundle 5 closes real reviewed-input onboarding and draft generation only. It must not merge that decision with sample-quality or P2.

## Goal

Run the complete relevant regression set, validate the Bundle 5 artifact inventory and truthfully select one close state.

## Allowed files

- `tests/test_r5_bundle5_close.py`
- `config/r5_bundle5_expected_artifacts.yaml` only for final path reconciliation
- `reports/p1_6/R5_BUNDLE_5_REAL_REVIEWED_INPUT_ONBOARDING_CLOSE_READOUT.md`
- Bundle 5 truthfulness result
- `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md`

## Forbidden scope

- Do not edit implementation merely to make the close test pass; return to the owning card.
- Do not rewrite old readouts to erase a blocker.
- Do not claim fresh test execution without command evidence.
- Do not set sample-quality or P2 true.
- Do not publish direct investment advice.

## Required close checks

Verify:

- every manifest-declared artifact exists;
- accepted real inputs have valid reviewer/evidence metadata;
- no templates/fixtures/sample reports are counted as evidence;
- staging and promotion consume only allowed review statuses;
- registry writes are atomic, rollback-protected and idempotent;
- registry-derived readiness and TODOs reconcile independently;
- four core subpacks and preflight pass at the allowed level;
- render type matches the real pilot gate;
- benchmark precheck does not promote quality state;
- no-advice and truthfulness checks pass;
- Bundle 4 close and earlier core regressions still pass;
- full repository pytest and `git diff --check` pass.

## Close-state decision

### A. Target ready

Use only when all target gates pass:

```text
status = accepted_with_todos | accepted
current_r5_state = R5_REAL_002837_REVIEWED_INPUT_RESEARCH_DRAFT_READY
real_reviewed_inputs_supplied = true
real_registry_promotion_completed = true
reviewed_input_research_draft_rendered = true
sample_quality_report_allowed = false
p2_allowed = false
```

Use the repository's existing canonical state token if it differs, and document the mapping.

### B. Partial onboarding

Use when some real inputs are valid but the research draft gate remains blocked:

```text
status = blocked_with_partial_progress
current_r5_state = R5_REAL_002837_REVIEWED_INPUT_ONBOARDING_PARTIAL
sample_quality_report_allowed = false
p2_allowed = false
```

List exact missing input types, evidence requests, owners and next actions.

### C. Blocked/rolled back

Use when promotion, atomicity, provenance, quality or regression fails. Prove rollback and keep the previous canonical state.

## Suggested commands

```bash
python -m pytest -q tests/test_r5_bundle5_close.py tests/test_r5_bundle4_close.py tests/test_r5_bundle3_close.py tests/test_r5_after_patch55_close.py --tb=short -p no:cacheprovider
python scripts/check_r5_readout_truthfulness.py --rules config/r5_readout_truthfulness_rules.yaml --glob 'reports/p1_6/R5_BUNDLE_5*READOUT.md' --strict --json reports/p1_6/r5_bundle5_readout_truthfulness_result.json
python -m pytest -q --tb=short -p no:cacheprovider
git diff --check
```

## Next decision

- If target ready and all critical TODOs are cleared, recommend a **separate** sample-quality readiness bundle.
- If partial/blocked, recommend only the smallest remediation bundle for the missing evidence or failing owner.
- P2 remains closed in either case.
