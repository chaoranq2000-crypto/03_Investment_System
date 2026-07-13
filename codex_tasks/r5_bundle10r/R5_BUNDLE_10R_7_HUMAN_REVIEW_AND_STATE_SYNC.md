# 10R.7 — Human review and canonical state sync

## Goal

Create a truthful human-review handoff and keep all workflow surfaces synchronized.

## Required work

- Generate the handoff only after the automated candidate gate passes.
- Keep human review `pending` until an actual reviewer records a decision.
- Synchronize workflow state, artifact manifest, open todos, run log, workflow readout, and quality report.
- Preserve old accepted/rejected states as dated historical records, not current canonical status.
- Route each failed criterion to the owning skill and stage.

## Acceptance

- No artifact claims human acceptance before reviewer action.
- `sample_quality_allowed` and `p2_allowed` remain false.
- One canonical current Reader status exists across all workflow surfaces.
