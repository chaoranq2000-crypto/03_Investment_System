# Apply order for R5 After Bundle 4 task package

Execute one card at a time. Each implementation card must be a separate Codex patch with its own canonical readout.

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

Before every card:

```bash
git status --short
git diff --check
```

Stop after a blocking failure. Do not continue to a later card by weakening a validator, changing an accepted record to bypass a gate, or converting missing evidence into an estimate.

After every card, record changed files, exact commands, exit codes, concise stdout/stderr, artifact hashes where applicable, blockers, TODOs and the next card.
