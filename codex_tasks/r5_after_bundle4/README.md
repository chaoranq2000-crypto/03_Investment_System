# R5 After Bundle 4 — Bundle 5 real reviewed-input onboarding task package

Base snapshot: `aeb846b` (`Add R5 Bundle 4 reviewed-input fixture pipeline`).

## Current state to preserve

- R5 Bundle 4 closed as `R5_REVIEWED_INPUT_FIXTURE_PROMOTION_SMOKE_PASSED` with `accepted_with_todos`.
- The reviewed-input fixture pipeline is executable, validator-checked, rollback-protected and idempotent.
- The real workflow `wf_20260703_stock_first_002837_invic` remains `R5_REVIEWED_INPUT_PILOT_BLOCKED_SOURCE_GAPPED`.
- No accepted real market, peer, forecast, valuation or business-disclosure input exists in the Bundle 4 close state.
- Sample-quality remains closed.
- P2 remains closed.

## Bundle 5 objective

Onboard real, locally reviewed, evidence-anchored inputs for 002837; validate and stage them; promote accepted records into canonical registries with backup, rollback and idempotency evidence; rebuild the core research subpacks; and render a truthful `reviewed_input_research_draft` if and only if the existing gates allow it.

## Included cards

1. `R5_AFTER_BUNDLE4_COMPLETION_REVIEW.md`
2. `R5_BUNDLE_5_0_STATUS_TRUTH_SYNC_AND_EXPECTED_ARTIFACTS.md`
3. `R5_BUNDLE_5_1_REAL_INPUT_INVENTORY_AND_PROVENANCE_MATRIX.md`
4. `R5_BUNDLE_5_2_OFFICIAL_DISCLOSURE_AND_FINANCIAL_HISTORY_ONBOARDING.md`
5. `R5_BUNDLE_5_3_MARKET_AND_PEER_INPUT_ONBOARDING.md`
6. `R5_BUNDLE_5_4_FORECAST_AND_VALUATION_INPUT_ONBOARDING.md`
7. `R5_BUNDLE_5_5_REAL_REGISTRY_PROMOTION_AND_CORE_ASSET_REBUILD.md`
8. `R5_BUNDLE_5_6_RESEARCH_DRAFT_RENDER_AND_QUALITY_GATE.md`
9. `R5_BUNDLE_5_7_BENCHMARK_COVERAGE_PRECHECK_NO_ADVICE.md`
10. `R5_BUNDLE_5_8_CLOSE_READOUT_AND_NEXT_DECISION.md`

## Hard boundaries

- Do not fabricate reviewer identity, reviewed timestamps, evidence IDs, source ranks, dates, metrics or limitations.
- Do not set `review_status: accepted` merely because a file parses.
- Do not treat templates, fixtures, user sample reports, analyst prose or unresolved TODOs as accepted real evidence.
- Do not mutate the committed real workflow before Card 5.5 passes validation, dry-run, backup and pre-hash gates.
- Do not overwrite files under `data/raw/`; archive new versions.
- Do not hide pending, rejected, missing, low-confidence or conflicting evidence.
- Do not generate direct buy/sell/hold, position-sizing, timing or guaranteed-return language.
- Do not open sample-quality or P2 in Bundle 5.

## Intended successful close state

```text
current_r5_state = R5_REAL_002837_REVIEWED_INPUT_RESEARCH_DRAFT_READY
real_reviewed_inputs_supplied = true
real_registry_promotion_completed = true
reviewed_input_research_draft_rendered = true
sample_quality_report_allowed = false
p2_allowed = false
```

If the current implementation emits a different established state name, preserve the implementation's canonical state vocabulary and document the mapping instead of silently inventing a new gate token.
