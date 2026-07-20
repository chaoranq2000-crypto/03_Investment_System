# Overnight Mission — Review Acceleration and Conditional Unlock

## Why Night04 exists

Night03 completed the engineering candidate closure honestly:

```text
43 candidate-ready + 20 dependency-blocked + 6 parents
0/63 resolved
```

The next bottleneck is review throughput and safe execution after approval, not another round of
candidate generation. Night04 must reduce human review cost, rank decisions by unlock leverage,
prevalidate pointer changes, and be ready to consume authentic exact-hash decisions at any point.

## Mission outcomes

- `delivered_with_resolution_delta`: delivery gates pass and at least one independent resolution receipt exists.
- `delivered_review_acceleration_ready`: delivery gates pass, no valid external decision arrived, all 43 review bundles and 8 pointer dry-runs are complete, and 0/63 remains explicit.
- `partial`: cutoff reached with carry-forward and bounded failure packets.
- `blocked` / `failed`: delivery gates did not pass; never label delivered.

## Required end state

- authoritative IDs preserved;
- review dashboard ranks all 43 candidates by unlock leverage and critical path;
- blank approve/reject/defer manifests bind exact artifact hashes;
- all 8 pointer proposals have sandboxed dry-run patches, targeted test receipts and conflict analysis;
- approved decisions, if any, are ingested idempotently and executed only within scoped sandboxes;
- 20 dependency blockers and 6 parents are recomputed from receipts only;
- full Night Shift tests, source-route, full repository tests, scope audit and target-branch CI pass;
- Night05 queue carries every unresolved ID without compression or disappearance.
