# R5 Bundle 8R.0 — Baseline audit and forward-state transition

## Goal
Preserve Bundle 8/9/10 historical artifacts, suspend their canonical eligibility, record the baseline commit and activate Bundle 8R without deleting or rewriting historical close records.

## Required work
- Run capability and adapter gates in baseline mode.
- Run `start_r5_bundle8r_forward_requalification.py` first in preview, then `--write`.
- Confirm Bundle 9/10 close hashes are unchanged.
- Add the new state artifact to the workflow manifest and open TODO register.

## Acceptance
- Mode is `forward_requalification_not_rollback`.
- Current canonical sample-quality permission is false.
- Bundle 9/10 close blocks remain byte-equivalent in meaning and are listed as retained history.
- Next owner is `evidence-ingest`.
