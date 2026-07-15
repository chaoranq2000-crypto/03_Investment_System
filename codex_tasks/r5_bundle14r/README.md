# R5 Bundle 14R task chain

This task chain implements and executes the cross-industry golden-regression lane. It is **not** a plan-only package: the patch also adds runtime code, semantic quality gates, fixtures, tests, a CLI, and CI.

Execution order:

1. `00_BASELINE_AND_SCOPE.md`
2. `01_CONTRACT_AND_HARNESS.md`
3. `02_OFFICIAL_EVIDENCE_PACKS.md`
4. `03_DRIVER_FINANCIAL_MODELS.md`
5. `04_VALUATION_READER.md`
6. `05_SEMANTIC_ADVERSARIAL_GATE.md`
7. `06_EXACT_HASH_HUMAN_REVIEW.md`
8. `07_CLOSE_OR_BACKFLOW.md`

Hard boundary for every task:

```yaml
release_authority: false
sample_quality_allowed: false
p2_allowed: false
workflow_state_mutation_allowed: false
```

The existing Bundle 13R evidence-backflow state is read-only for this task chain.
