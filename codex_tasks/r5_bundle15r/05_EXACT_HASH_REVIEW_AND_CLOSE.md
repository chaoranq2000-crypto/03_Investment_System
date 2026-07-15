# 15R-5 — Exact-hash review handoff and close

## Actions

1. Bind evidence packs, qualification audits, operating models, forecast and
   valuation outputs, Reader/semantic outputs, and generation locks.
2. Create or validate human-review handoffs against exact physical hashes.
3. Never synthesize reviewer identity, timestamp, or acceptance.
4. Produce a close readout and a non-canonical status proposal.
5. Run the full repository test command, Bundle 14R/15R focused tests,
   `git diff --check`, and sensitive/untracked-file review.
6. Stage only intended Bundle 15R source paths and separately approved reviewed
   evidence packs.

## Allowed close

```yaml
engineering_implementation: complete
real_case_ready_count: 0..4
canonical_workflow_state_mutated: false
sample_quality_allowed: false
p2_allowed: false
```

Any release or P2 transition requires a separate canonical decision.
