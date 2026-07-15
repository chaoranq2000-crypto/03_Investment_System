# R5 Bundle 14R — Official Evidence Trigger and Selective Backflow

## Purpose

Bundle 13R resolved 6 items and left 11 unresolved: nine same-period operating-driver
contracts and two liquid-cooling overlap-elimination contracts. Bundle 14R turns the
waiting state into an executable, deterministic trigger layer. It does **not** invent
missing disclosures and does **not** reopen valuation, model, Reader, sample-quality, or P2.

## Trigger boundary

A candidate qualifies only when all conditions hold:

1. issuer periodic report, issuer announcement, or issuer IR record;
2. official issuer source;
3. reviewed or accepted by the normal evidence process;
4. compatible with the Bundle 12R period anchor;
5. covers the exact metric key;
6. contains every required dimension, source hash, and locator.

Qualification means “eligible for selective backflow review”, not “accepted research fact”.

## Runtime flow

```text
new issuer disclosure
  -> normal raw archive and evidence review
  -> Bundle 14R candidate pack
  -> deterministic trigger evaluation
  -> matched operating drivers: selective T1
  -> matched overlap eliminations: selective T2
  -> all 11 qualified and promoted: rerun Bundle 12R gates
  -> valuation eligibility remains independent
  -> model / Reader generation only after downstream gates pass
  -> exact-hash human review
  -> P2 remains separately closed
```

## Non-compensating release rules

- A high-severity missing driver cannot be offset by another metric.
- Revenue overlap evidence cannot substitute for gross-profit overlap evidence.
- The two overlap contracts map one-to-one to physical unresolved items `OVL-002`
  (room/liquid) and `OVL-003` (cabinet/liquid); each relationship requires both
  revenue and gross-profit numeric deductions before it qualifies.
- A broker estimate, news article, or unreviewed IR clue cannot qualify.
- Partial evidence schedules only the affected stage and cannot trigger a full rerun.
- Even when all 11 candidates qualify, Bundle 14R authorizes only Bundle 12R
  requalification. It does not authorize valuation refresh, model regeneration,
  Reader regeneration, sample-quality, or P2.

## Command

```bash
python scripts/plan_r5_bundle14r_evidence_trigger.py \
  --registry reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle14r/R5_bundle14r_evidence_trigger_registry.yaml \
  --candidates reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle14r/R5_bundle14r_candidate_evidence_pack.yaml \
  --workflow-state reports/workflow_runs/wf_20260703_stock_first_002837_invic/workflow_state.yaml \
  --output-dir reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle14r/generated
```

The command writes a proposed workflow-state copy; it never overwrites the canonical state.

## Expected empty-pack result

```text
R5_BUNDLE14R_WAITING_FOR_OFFICIAL_EVIDENCE
qualified_trigger_count: 0
unresolved_trigger_count: 11
bundle12r_rerun_allowed: false
valuation_refresh_allowed: false
reader_regeneration_allowed: false
p2_allowed: false
```

## Exit criteria

Bundle 14R can close as `READY_FOR_BUNDLE12R_SELECTIVE_RERUN` only after all eleven
contracts have reviewed candidates and deterministic output is stable. Research quality
is not upgraded merely because the trigger layer closes.
