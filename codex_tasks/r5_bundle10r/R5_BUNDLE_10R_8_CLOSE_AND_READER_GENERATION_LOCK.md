# 10R.8 — Close and Reader-generation lock

## Goal

Lock the exact Reader candidate generation consumed by human review without promoting it to sample quality.

## Required work

- Hash the normalized payload, Reader, traceability appendix, quality scorecard, and human-review handoff.
- Store the input model generation ID and aggregate model hash in the lock.
- Rebuild twice and require zero hash differences.
- Run focused tests, full repository regression, compile checks, and `git diff --check`.
- Write close readout with retained TODOs and explicit boundaries.

## Acceptance

- Missing locked artifact count is zero.
- Candidate quality gate has no core/truthfulness blockers.
- Human review is still pending or explicitly recorded; it is never fabricated.
- Reader generation ID is deterministic.
- Bundle 10R close does not enable sample-quality or P2.
