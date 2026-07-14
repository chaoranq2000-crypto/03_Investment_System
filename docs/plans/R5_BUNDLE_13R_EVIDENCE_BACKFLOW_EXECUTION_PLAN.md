# R5 Bundle 13R — Evidence Backflow Execution Plan

## Baseline

- commit prefix: `64f6787b`
- upstream generation: `op_evidence_gen_r5_bundle12r_fd5d23c5eb35ac27`
- upstream decision: `needs_backflow`

The archive originally named an older fixture generation. Baseline audit against the physical workflow run rejected that binding; the execution contract is repaired to the canonical Bundle 12R generation and exact artifact hashes. The original failed audit remains in the run package for traceability.

## Objective

Execute the open Bundle 12R backflow rather than generating another Reader. Convert reviewed evidence into a new Bundle 12R operating-evidence input, reconcile material business definitions, rerun the gate, and only then refresh valuation eligibility.

## Ordered work

1. exact baseline and hash audit;
2. T1 driver and financial-denominator qualification;
3. T2 independent-exposure and overlap reconciliation;
4. deterministic promotion and Bundle 12R rerun;
5. conditional RP6 valuation eligibility refresh;
6. state synchronization and generation lock;
7. close readout with remaining evidence requests.

## Success conditions

The preferred outcome is `operating_evidence_requalified`. A truthful `backflow_execution_in_progress` with fewer blockers is also a valid outcome. No outcome in Bundle 13R authorizes human acceptance, sample-quality status or P2.
