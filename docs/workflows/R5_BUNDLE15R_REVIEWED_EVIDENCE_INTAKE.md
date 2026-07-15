# R5 Bundle 15R — Reviewed Evidence Intake Bridge

## Purpose

Bundle 14R already defines eleven non-compensating trigger contracts and a deterministic
selective-backflow evaluator. Its checked-in candidate pack is intentionally empty. Bundle
15R adds the missing intake bridge between the normal reviewed-evidence process and the
Bundle 14R candidate-pack contract.

Bundle 15R does **not** acquire issuer evidence, promote a claim, rerun Bundle 12R, refresh
valuation, regenerate a model or Reader, accept human review, open sample-quality status, or
open P2.

## Baseline

- repository: `chaoranq2000-crypto/03_Investment_System`
- intended descendant baseline: `86ab78675f5b2594bba23733e2dceb6ae66323ac`
- workflow: `wf_20260703_stock_first_002837_invic`
- source state: `R5_BUNDLE14R_WAITING_FOR_OFFICIAL_EVIDENCE`

The baseline SHA is user-supplied. Before application, the operator must confirm that the
target checkout is this commit or a compatible descendant and that the seven Bundle 14R
paths are present.

## Runtime flow

```text
immutable issuer source
  -> normal evidence-ingest extraction and review
  -> Bundle 15R normalized reviewed-evidence input
  -> source / review / period / hash / locator validation
  -> exact metric-contract matching
  -> same-value deduplication
  -> conflicting-value fail-closed ledger
  -> Bundle 14R-compatible candidate pack
  -> existing Bundle 14R trigger evaluator
  -> selective T1/T2 backflow only
```

## Input boundary

Each input record represents one reviewed issuer document and may contain one or more
normalized metrics. A metric is eligible only when:

1. its source class is an issuer periodic report, issuer announcement, or issuer IR record;
2. `official_issuer_source` is true;
3. `review_status` is `reviewed` or `accepted`;
4. the period anchor matches Bundle 14R and `period_compatible` is true;
5. the source hash is a 64-character SHA-256 and the locator is non-empty;
6. the metric key exactly matches one Bundle 14R trigger;
7. every trigger-required field has a concrete value;
8. the business scope is compatible with the trigger contract.

News, broker research, clue-only material, pending review, period-incompatible values, or
plausible estimates cannot enter the candidate pack.

## Conflict and duplicate policy

- Same metric, period, and business scope with the same normalized value is deduplicated
  deterministically.
- Same metric, period, and business scope with different normalized values is excluded
  entirely and written to the conflict ledger.
- Conflicting reviewed values never qualify by majority vote or by source recency alone.
- Resolution requires an explicit reviewed correction or reconciliation record.

## Command

```bash
python scripts/build_r5_bundle15r_reviewed_evidence_intake.py \
  --registry reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle14r/R5_bundle14r_evidence_trigger_registry.yaml \
  --reviewed-input reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle15r/R5_bundle15r_reviewed_evidence_input.yaml \
  --workflow-state reports/workflow_runs/wf_20260703_stock_first_002837_invic/workflow_state.yaml \
  --output-dir reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle15r/generated
```

The command writes generated artifacts and a **proposed** workflow-state copy. It never
overwrites the canonical workflow state.

## Generated outputs

- `R5_bundle15r_candidate_pack.yaml`
- `R5_bundle15r_rejection_ledger.csv`
- `R5_bundle15r_conflict_ledger.yaml`
- `R5_bundle15r_intake_summary.yaml`
- `R5_bundle15r_generation_lock.yaml`
- optional `workflow_state.bundle15r.proposed.yaml`

## Release boundary

A Bundle 15R candidate is only an input to Bundle 14R evaluation. Even when all eleven
trigger keys are represented:

```text
bundle12r_rerun_allowed: false
valuation_refresh_allowed: false
model_regeneration_allowed: false
reader_regeneration_allowed: false
sample_quality_allowed: false
p2_allowed: false
```

Bundle 12R can be reconsidered only after the existing Bundle 14R evaluator qualifies all
contracts and the selective T1/T2 review receipts are complete. Valuation, model, Reader,
human review, sample quality, and P2 remain independent downstream gates.
