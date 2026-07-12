# R5 Bundle 6.0 — Status and reader-quality baseline

## Goal

Freeze the truthful Bundle 5 state and create a reproducible before-state for reader-quality remediation.

## Required work

1. Re-run the current canonical truthfulness, Bundle 5 close and repository tests.
2. Record the current report SHA-256 and current quality-gate SHA-256.
3. Produce a machine-readable reader-surface inventory covering:
   - report length;
   - headings;
   - raw internal evidence IDs;
   - internal file paths;
   - readiness tokens;
   - TODO/MISSING/LOW_CONFIDENCE/UNREVIEWED tokens;
   - duplicate machine-readiness sections;
   - values rendered with more than four decimal places;
   - missing and partial benchmark dimensions.
4. Preserve the current draft unchanged as the before-state.
5. Confirm that no canonical state or gate is promoted by this card.

## Expected artifacts

- `reports/p1_6/R5_BUNDLE_6_0_STATUS_READER_QUALITY_BASELINE_READOUT.md`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle6_reader_surface_baseline.yaml`

## Acceptance gate

```text
bundle5_truthfulness = pass
current_draft_hash_recorded = true
reader_surface_inventory_complete = true
sample_quality_report_allowed = false
p2_allowed = false
```

The baseline must explicitly classify the existing draft as an audit-oriented research draft, not a reader-facing candidate.

## Forbidden scope

- Do not rewrite the report in this card.
- Do not change evidence or registry state.
- Do not relax existing truthfulness gates.
- Do not declare the current report acceptable.
