# 14R-6 — Deterministic lock and exact-hash review

## Actions

1. rerun each candidate and compare all output hashes;
2. lock evidence, driver model, forecast/valuation model, Reader, traceability, semantic quality, and handoff files;
3. create an exact-hash human-review record;
4. require a real reviewer to mark research usefulness, with comments and timestamp;
5. invalidate review after any locked input/output change.

## Boundary

Automation may emit `candidate_ready_for_exact_hash_review` only. It may not emit human approval, sample-quality approval, or P2 approval.
