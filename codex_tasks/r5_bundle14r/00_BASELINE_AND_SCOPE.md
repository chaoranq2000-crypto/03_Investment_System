# 14R-0 — Baseline and scope lock

## Inputs

- Base commit: `0966b914476b8f0a89b39d0f06a58dca5d3b20a7`
- Existing Bundle 13R workflow state and exact-hash locks
- This Bundle 14R patch

## Actions

1. Record `git rev-parse HEAD`, `git status --short`, and the untracked/deleted path set.
2. Confirm the base commit or explicitly approved descendant.
3. Create `codex/r5-bundle14r-golden-regression`.
4. Run `git apply --check`.
5. Apply only this patch; do not stage pre-existing evidence, generated reports, ZIPs, or deletions.
6. Confirm the Bundle 13R workflow-state file is byte-identical before and after installation.

## Exit criteria

- patch applies cleanly;
- no existing file is modified by the patch;
- Bundle 13R state and locks are unchanged;
- local pre-existing work remains present and unstaged.
