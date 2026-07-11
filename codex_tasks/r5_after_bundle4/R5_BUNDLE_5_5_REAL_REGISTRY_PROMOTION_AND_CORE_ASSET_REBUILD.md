# R5 Bundle 5.5 — Real registry promotion and core-asset rebuild

## Background

This is the first Bundle 5 card allowed to mutate the real workflow's canonical registries. It must use the Bundle 4 material writer, validator, rollback and idempotency guarantees against real accepted inputs.

## Goal

Validate the complete dropzone, build staging, perform a no-write dry-run, back up the real registries, promote accepted inputs atomically, prove idempotency, rebuild readiness from physical registries, and rerun the four core research subpacks.

## Preconditions

- Cards 5.1–5.4 close without blocking input defects.
- Worktree is clean except for the current card.
- All accepted records have real evidence IDs and reviewer metadata.
- A pre-promotion inventory and hash set exists.

## Allowed files

- existing reviewed-input validation/staging/promotion scripts and focused fixes owned by discovered defects
- real workflow registry files targeted by the existing promoter
- backup artifacts outside canonical registry paths or in the existing temporary/backup convention
- real workflow staging, promotion, dry-run, gate and core-subpack outputs
- focused tests and readout
- `reports/p1_6/R5_BUNDLE_5_5_REAL_REGISTRY_PROMOTION_READOUT.md`

## Forbidden scope

- Do not hand-edit canonical registries to simulate promotion.
- Do not promote pending/rejected rows.
- Do not treat accepted_degraded as fully accepted unless the existing contract explicitly allows it.
- Do not overwrite raw evidence.
- Do not proceed after a validator failure.
- Do not leave partial writes after failure.
- Do not open sample-quality/P2.

## Required work

1. Validate the full workflow dropzone.
2. Build staging and capture input counts, accepted IDs, TODOs and allowed report level.
3. Run promotion dry-run/no-write mode if supported; otherwise add a focused, tested no-write plan mode before real mutation.
4. Capture pre-promotion file inventory, byte hashes and semantic summaries.
5. Back up every target registry.
6. Promote through the existing material writer.
7. Validate each resulting registry and cross-registry provenance.
8. Run an identical second promotion and prove byte-level/semantic idempotency.
9. On any failure, restore all targets and prove the restore hashes match pre-state.
10. Rebuild the reviewed-input dry-run/readiness from physical registry bytes.
11. Rerun financial history, business breakdown, forecast, valuation and core-asset preflight.

## Acceptance gate

- `registries_changed` corresponds to actual validated filesystem changes.
- Every promoted value has a source input ID and evidence anchor.
- Atomicity, rollback and idempotency tests pass.
- Readiness is reconstructed from registries, not dropzone presence.
- Core subpacks validate at the level allowed by the real gate.

## Suggested commands

First inspect current CLI contracts:

```bash
python scripts/promote_r5_reviewed_inputs_to_registries.py --help
python scripts/build_r5_reviewed_input_staging.py --help
python scripts/build_r5_reviewed_input_dry_run_from_registries.py --help
```

Then run the equivalent repository-supported flow, including:

```bash
python scripts/validate_r5_reviewed_input_dropzone.py --root data/reviewed_inputs/wf_20260703_stock_first_002837_invic --json reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_dropzone_validation_final.json
python scripts/build_r5_reviewed_input_staging.py --repo-root . --workflow-id wf_20260703_stock_first_002837_invic --dropzone-root data/reviewed_inputs/wf_20260703_stock_first_002837_invic --json reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_reviewed_input_staging.yaml
python scripts/run_r5_core_asset_preflight.py --repo-root . --workflow-id wf_20260703_stock_first_002837_invic --json reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_core_asset_preflight.yaml
python -m pytest -q tests/test_r5_bundle5_real_registry_promotion.py tests/test_r5_reviewed_input_registry_promotion.py tests/test_r5_bundle4_registry_idempotency.py tests/test_r5_bundle4_post_promotion_dry_run.py --tb=short -p no:cacheprovider
git diff --check
```

## Stop condition

Any partial write, missing backup, non-idempotent second run, provenance loss or validator error requires rollback and a blocked close for this card.
