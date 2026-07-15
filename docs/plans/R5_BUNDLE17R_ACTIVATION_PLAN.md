# R5 Bundle 17R Execution Plan

## Executive decision

Do not jump from the Bundle 16R implementation commit directly to human acceptance. The committed code materializes already-reviewed evidence, but the local reviewer mappings and generated readouts were intentionally not published. The next step is to run the real chain, lock its physical outputs, and only then hand exact artifacts to human reviewers.

## Phase 0 — Baseline and worktree preservation

1. Require `7ab395283f432faac7bbc0e83a0b0cf4976ed5dc` as the Bundle 16R ancestor.
2. Record the complete 262-entry worktree inventory and hashes.
3. Confirm all Bundle 17R target paths are absent.
4. Apply the add-only patch without touching local mappings, generated readouts, ZIPs, caches or unrelated files.

## Phase 1 — Real Bundle 16R preview

1. Point only to reviewed physical official-source and normalized record catalogs.
2. Use real reviewer-authored mappings; do not allow numeric overrides.
3. Run the Bundle 16R preview twice and require byte-identical trees.
4. Inspect source requests, mapping tasks, catalog conflicts and targeted backflow.
5. Repair mappings only through reviewed source/record bindings.

Exit: four mappings are valid, or every remaining blocker has an owner, stage and requested evidence.

## Phase 2 — Atomic pack publication and selective 15R/14R execution

1. Publish pack candidates atomically with the existing Bundle 16R CLI.
2. Invoke Bundle 15R through the existing CLI boundary.
3. Let Bundle 15R invoke Bundle 14R selectively.
4. Do not lower thresholds. Partial execution is valid and remains backflow.
5. Rerun the complete chain and compare all generation locks.

Exit: physical materialization, qualification and regression outputs exist and are deterministic.

## Phase 3 — Bundle 17R activation receipt

1. Copy the manifest template outside committed source paths.
2. Bind exact stage suite/lock paths and assertion pointers.
3. Bind each case’s registered Bundle 14R case contract, Bundle 15R qualification, case-specific Bundle 14R qualification result (or shared suite plus exact array pointers), Reader, generation lock, semantic quality scorecard and traceability artifacts.
4. Run Bundle 17R with `--fail-on-blockers`.
5. Run twice and compare output trees byte-for-byte.

Exit: either all four cases are ready for exact-hash human review, or a deterministic targeted backflow queue is produced.

## Phase 4 — Close and next decision

Allowed close when all four engineering gates pass:

```yaml
bundle17r_engineering_status: closed
all_four_cases_activated: true
human_review_status: pending
sample_quality_allowed: false
p2_allowed: false
next_stage: R5_bundle18r_exact_hash_human_review
```

Blocked close:

```yaml
bundle17r_engineering_status: closed_with_backflow
all_four_cases_activated: false
sample_quality_allowed: false
p2_allowed: false
next_stage: R5_bundle17r_targeted_backflow
```

## Suggested commit

```text
feat(r5): add Bundle 17R activation receipt and review handoff
```
