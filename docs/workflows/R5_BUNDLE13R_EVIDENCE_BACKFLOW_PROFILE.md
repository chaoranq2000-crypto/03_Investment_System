# R5 Bundle 13R — Evidence Backflow Execution Profile

Bundle 13R consumes the exact Bundle 12R generation that returned `needs_backflow`. It does not replace the global T0–T10 workflow and does not rebuild the Reader.

## Dependency order

```text
BF12R-002 / T1 reviewed evidence and financial denominators
    ↓
BF12R-003 / T2 independent exposure and overlap reconciliation
    ↓
re-run RP-12R-OE on the promoted input
    ↓
BF12R-001 / RP6 peer, DCF and SOTP eligibility refresh
```

The order is non-negotiable. Valuation work cannot substitute for missing operating evidence.

## Outputs

- `R5_bundle13r_execution_queue.yaml`
- `R5_bundle13r_backflow_execution_result.yaml`
- `R5_bundle13r_promoted_operating_evidence_input.yaml`
- `R5_bundle13r_unresolved_items.csv`
- `R5_bundle13r_rerun_bundle12r.md`
- `R5_bundle13r_generation_lock.yaml`

## Boundaries

- raw evidence remains immutable;
- reviewed values require evidence IDs and locators;
- bounded estimates require ordered bounds, methodology, overlap treatment and a dated replacement trigger;
- missing/conflicting values remain visible and cannot carry promoted numbers;
- contained or overlapping business definitions require numeric revenue and gross-profit adjustments;
- Bundle 11R review and Bundle 12R generation remain historical and immutable;
- human review remains pending;
- `sample_quality_allowed=false` and `p2_allowed=false`.
