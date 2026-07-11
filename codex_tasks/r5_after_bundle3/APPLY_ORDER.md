# Apply order for R5 After Bundle 3 task package

Execute the cards one at a time. Each implementation card must be a separate Codex patch with its own readout.

1. `R5_AFTER_BUNDLE3_COMPLETION_REVIEW.md`
2. `R5_BUNDLE_4_0_STATUS_BASELINE_AND_EXPECTED_ARTIFACTS.md`
3. `R5_BUNDLE_4_1_ACCEPTED_REVIEWED_INPUT_FIXTURE_SET.md`
4. `R5_BUNDLE_4_2_DROPZONE_VALIDATION_AND_FIXTURE_BOUNDARY.md`
5. `R5_BUNDLE_4_3_REGISTRY_PROMOTION_WRITE_AND_IDEMPOTENCY.md`
6. `R5_BUNDLE_4_4_POST_PROMOTION_DRY_RUN_FROM_REGISTRIES.md`
7. `R5_BUNDLE_4_5_END_TO_END_FIXTURE_SMOKE_GATE.md`
8. `R5_BUNDLE_4_6_CLOSE_READOUT_AND_REAL_INPUT_NEXT_DECISION.md`

Do not combine multiple implementation cards into one patch. If a card discovers a blocking defect in the current foundation, stop after recording the blocker and do not continue to later cards.

Before every card:

```bash
git status --short
git diff --check
```

After every card, record changed files, commands, exit codes, stdout/stderr summary, blockers, TODOs and the next card. A passing fixture test must never be described as accepted real evidence.
