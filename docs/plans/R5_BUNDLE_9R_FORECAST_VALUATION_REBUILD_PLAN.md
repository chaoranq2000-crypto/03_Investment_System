# R5 Bundle 9R — Forecast and valuation rebuild plan

Baseline: `fe7ae5f5dd1b10b9e9111f2f69e664ef5d7506a4`

Original package binding: `evidence_gen_r5_bundle8r_b82ba6f33b5044e6` (preserved historical lock; invalid for forward consumption because it captured an intermediate `claims_draft.csv` hash)

Current corrected input evidence generation: `evidence_gen_r5_bundle8r_231a51f4673156df`

Current aggregate: `231a51f4673156dfd2fa24aa96ad7b915dfd3466483ac7bcd87c39b8d0b17e2b`

Correction record: `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8r_generation_lock_correction.yaml`

This plan rebuilds forecast and valuation from the Bundle 8R evidence generation. Old Bundle 9/10 artifacts remain historical snapshots. The new artifacts use the `R5_bundle9r_` prefix and cannot be consumed by Bundle 10R until the model-generation lock exists.

The execution order and acceptance criteria are defined under `codex_tasks/r5_bundle9r/`.
