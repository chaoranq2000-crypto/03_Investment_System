# P2G-1 executable example matrix

P2G-1 examples are generated from the canonical P2F fixture chain during tests instead of
checking in large duplicated review artifacts. This keeps the P2F facts projection as the
single fixture source and still exercises real schema, source replay and CLI serialization.

| Example | Executable test | Expected state |
|---|---|---|
| release-ready cohort | `test_sch_01_minimal_valid_cohort_is_release_ready` | `ready` / `verified` |
| cutoff-later revision | `test_tim_05_future_correction_cannot_change_earlier_cohort` | byte-identical early cohort |
| ambiguous leaves | `test_det_06_two_valid_revision_one_roots_are_ambiguous` | blocked: `ambiguous_current_revision` |
| replay mismatch | `test_src_02_fact_tamper_is_replay_mismatch` | blocked: `source_replay_mismatch` |
| missing predecessor | `test_rev_04_missing_predecessor_is_fail_closed` | blocked: `revision_chain_invalid` |
| open episode close anchor | `test_tim_07_missing_closed_anchor_is_explicit_for_open_episode` | nonblocking exclusion |

Run:

```powershell
python -m pytest -q tests/test_investment_review_behavior_cohort.py
```

The CLI end-to-end example writes and reloads a real `p2g.behavior_cohort.v1` JSON artifact
under pytest's isolated temporary directory; output is create-only and is replayed from the
explicit P2F review and input bundle.
