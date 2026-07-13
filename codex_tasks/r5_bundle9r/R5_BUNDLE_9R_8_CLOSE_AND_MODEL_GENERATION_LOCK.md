# 9R.8 — Close and model-generation lock

## Goal

Close Bundle 9R only after the model gate passes and emit a hash-bound model generation for Bundle 10R.

## Required close evidence

- generation-binding validation;
- full repository tests and focused 9R tests;
- model quality scorecard with zero critical/high blockers;
- artifact inventory and hashes;
- state/readout/TODO/manifest synchronization;
- no mutation or deletion of historical Bundle 9/10 files.

## Required output

`reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_model_generation_lock.yaml` with:

- input evidence generation ID;
- all current 9R model artifact hashes;
- aggregate model hash;
- downstream consumer `R5_BUNDLE_10R_READER_REBUILD`.

## Close state

`accepted_with_todos` is allowed only for explicitly noncritical disclosure gaps. `sample_quality_allowed` remains false until Bundle 10R and a new human review pass.
