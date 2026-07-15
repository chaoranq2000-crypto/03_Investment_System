# R5 Bundle 15R task chain

Execute in order:

1. `00_BASELINE_AND_SCOPE.md`
2. `01_INSTALL_AND_SEED.md`
3. `02_BUILD_REVIEWED_EVIDENCE_PACKS.md`
4. `03_COMPILE_AND_QUALIFY.md`
5. `04_RUN_BUNDLE14R_SELECTIVELY.md`
6. `05_EXACT_HASH_REVIEW_AND_CLOSE.md`

Hard boundary for every card:

```yaml
fetch_or_review_evidence_automatically: false
sample_reports_as_evidence: prohibited
canonical_workflow_state_mutation_allowed: false
sample_quality_allowed: false
p2_allowed: false
```

Every card must leave the repository testable and record changed paths, commands,
exit codes, concise output, generated hashes, blockers, and the next card.
