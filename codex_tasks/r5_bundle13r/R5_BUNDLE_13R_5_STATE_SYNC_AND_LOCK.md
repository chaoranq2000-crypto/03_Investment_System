# 13R.5 — State sync and deterministic lock

## Goal

Synchronize workflow state to the exact Bundle 13R result.

## Required work

- validate the generation lock;
- apply the state adapter in preview mode, review the diff, then write with backup;
- sync run log, artifact manifest, TODO ledger, quality report and canonical index;
- verify deterministic rebuild and zero hash drift.

## Acceptance

- one canonical decision across all state surfaces;
- a new artifact hash invalidates any stale downstream handoff;
- human review remains pending; sample quality and P2 remain false.
