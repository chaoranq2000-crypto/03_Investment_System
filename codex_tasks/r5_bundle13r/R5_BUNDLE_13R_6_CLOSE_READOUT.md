# 13R.6 — Close readout

## Allowed close states

- `R5_BUNDLE13R_READY_FOR_BUNDLE12R_RERUN`
- `R5_BUNDLE13R_OPERATING_EVIDENCE_REQUALIFIED`
- `R5_BUNDLE13R_BACKFLOW_IN_PROGRESS`
- `R5_BUNDLE13R_BLOCKED_INVALID_REVIEWED_BACKFILL`

## Required readout

Record:

- baseline commit and exact upstream generation;
- resolved and unresolved T1/T2 items;
- Bundle 12R rerun decision and hashes, when available;
- valuation methods opened or kept closed;
- tests, compile, diff check and lock validation;
- remaining evidence requests and owners;
- explicit `sample_quality_allowed=false` and `p2_allowed=false`.

Technical close does not authorize a new Reader, human acceptance, sample quality or P2.
