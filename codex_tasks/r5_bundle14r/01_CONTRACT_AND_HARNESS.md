# 14R-1 — Install and verify contracts/harness

## Actions

1. Run the focused pytest file.
2. Run the CLI with no qualification directory and an output directory outside the repository.
3. Confirm all four case contracts pass.
4. Confirm all four remain `evidence_qualification_pending`.
5. Confirm the genericity scan finds no issuer names or tickers in the new runtime.
6. Confirm deterministic seed output across two runs.

## Expected seed outcome

```text
contract_passed = true
research_ready_case_count = 0
candidate_ready_case_count = 0
sample_quality_allowed = false
p2_allowed = false
```

A non-zero research-ready count without reviewed evidence is a blocker.
