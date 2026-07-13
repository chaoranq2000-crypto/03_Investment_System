# 10R.0 — Baseline and model-generation binding

## Goal

Bind every new Reader artifact to `model_gen_r5_bundle9r_1cd42241e6a38fb3` and the aggregate model hash `1cd42241e6a38fb3fc24e6ceb5be1261dbad6e1ee860393b44932282bacd54cc`.

## Required work

- Confirm `HEAD` is `b9395b10b278cf9e1355fae506f3740b265f69ea` or a compatible descendant.
- Validate `R5_bundle9r_model_generation_lock.yaml`, including all 13 locked model artifacts.
- Preview the workflow transition and prove historical Bundle 10 blocks and artifacts remain unchanged.
- Start `bundle10r_rebuild` only after the binding check passes.
- Keep `sample_quality_allowed = false` and `p2_allowed = false`.

## Acceptance

- Model generation ID, aggregate hash, input evidence generation ID, artifact hashes, and downstream consumer all match.
- Old Reader v3 and old Bundle 10 close records remain historical.
- `bundle10r_rebuild.status = in_progress`.
