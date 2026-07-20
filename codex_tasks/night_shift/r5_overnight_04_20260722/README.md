# R5_Overnight_Mission_04_20260721

Self-contained Night04 package for `03_Investment_System`.

## Mission shift

Night03 correctly reached `delivered_candidate_ready` while preserving `0/63 resolved`.
Night04 therefore does **not** regenerate the same 43 candidates. It builds a review-acceleration
and conditional-execution control plane around them:

- exact-hash batch review bundles for 43 candidate occurrences;
- unblock-leverage and critical-path ranking;
- dry-run prevalidation for 8 pointer proposals;
- conflict-safe partial decision intake;
- conditional execution only when authentic external decisions arrive;
- truthful recomputation of 20 dependent blockers and 6 parent work orders;
- full validation, publication, and Night05 carry-forward.

## Package-level workload

- 60 mission wrapper tasks;
- imports the 69-item Night04 authoritative queue;
- preserves 63 atomic blocker IDs and 6 parent IDs;
- starts from 43 candidate-ready + 20 dependency-blocked + 0 resolved.

Wrapper tasks and research occurrences remain distinct.
