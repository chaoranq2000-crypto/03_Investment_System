# 9R.0 — Baseline and evidence-generation binding

## Goal

Bind every new forecast and valuation artifact to the current corrected generation `evidence_gen_r5_bundle8r_231a51f4673156df` and prove the six locked Bundle 8R inputs have not changed. The original package generation remains preserved as a historical invalid-forward lock; see `R5_bundle8r_generation_lock_correction.yaml`.

## Required work

- Confirm `HEAD` is `fe7ae5f5dd1b10b9e9111f2f69e664ef5d7506a4` or a compatible descendant.
- Run `validate_r5_bundle9r_generation_binding.py` with `--verify-locked-input-hashes`.
- Preview the workflow-state transition; inspect that historical Bundle 9/10 blocks and completed stages remain.
- Write the transition only after the preview passes.
- Mark old unprefixed Bundle 9 artifacts as historical snapshots, never current inputs.

## Acceptance

- Current evidence generation ID and aggregate hash match the package binding.
- Zero locked-input hash differences.
- `bundle9r_rebuild.status = in_progress`.
- `sample_quality_allowed = false`; `p2_allowed = false`.
