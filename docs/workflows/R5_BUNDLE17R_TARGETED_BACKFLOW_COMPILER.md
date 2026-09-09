# R5 Bundle 17R-BF1 — Historical Targeted Backflow Compiler

## Purpose

This document preserves the historical Bundle 17R-BF1 contract and its frozen
activation baseline. Git commit `274d47ec299a42946bc3b83f7908257e80f0f99b` retired
the compiler implementation and the Bundle 14R–17R execution chain. The original
fields, routes and acceptance conditions below support historical interpretation
and recovery under the [canonical retention manifest](../meta/DOCS_REPORTS_RETENTION_DEPENDENCY_MANIFEST.yaml).
They are not a current work queue or an executable rerun plan. Current run
selection and workflow decisions remain owned by `RESEARCH_WORKFLOW.md` and
`config/r5_readout_canonical_index.yaml.current_runs`.

The recorded Bundle 17R activation outcome was:

```text
needs_targeted_backflow
0 / 4 engineering cases activated
63 blockers
sample_quality_allowed = false
p2_allowed = false
```

The `0/4` and `63` values above are frozen historical results, not current-run
status. The planned next step for that failure branch was to compile the exact
physical blocker queue into deterministic, dependency-ordered work orders;
Bundle 18R human review and a further Reader rebuild were not that step. The
diagram records the former chain, including its now-retired rerun stage:

```text
Bundle 17R receipt + generation lock
+ case matrix + 63-row backflow queue
        ↓ exact path/hash/boundary verification
63 immutable blocker records
        ↓ route and cluster without dropping rows
case/route work orders + dependency graph + execution batches
        ↓ existing T0–T10 skills
reviewed evidence / mappings / operating models / forecasts / valuation / Reader
        ↓ rerun physical chain
16R → 15R → 14R → 17R
```

## Why the historical package was named Bundle 17R-BF1

The original Bundle 17R success branch reserved Bundle 18R for exact-hash human
review. The recorded activation took the failure branch
`R5_bundle17r_targeted_backflow`; the corrective package was therefore named
`17R-BF1`. These labels do not select a current stage or create reviewer authority.

## Historical inputs

A manifest bound four physical artifacts from the committed Bundle 17R run:

- activation receipt;
- activation generation lock;
- backflow queue;
- case matrix.

The historical policy owned the expected values. A manifest could choose
physical paths and hashes but could not change `0/4`, `63`, the expected decision
or the release boundaries.

## Historical validation gates

The retired compiler failed closed when:

- a bound file is absent, outside an allowed root, forbidden, or hash-mismatched;
- receipt and generation-lock generation IDs differ;
- the queue or case matrix is not bound by the Bundle 17R generation lock;
- the receipt is not `needs_targeted_backflow`;
- the case count, pass count, or blocker count differs from policy;
- any release flag is truthy;
- any blocker lacks code, stage, owner, target, message, or requested action;
- a case-specific blocker references a case absent from the matrix;
- a dependency is unknown or cyclic.

## Historical routing and clustering

Every source row remained in the issue ledger with a stable issue ID, including
duplicate rows. Clustering reduced execution noise without reducing blocker accounting.

The historical policy owned these routes:

1. physical binding and generation integrity;
2. official evidence acquisition and review;
3. evidence mapping and qualification;
4. operating-driver economics;
5. overlap and scope reconciliation;
6. forecast bridge;
7. valuation eligibility;
8. semantic Reader and traceability;
9. exact-hash human-review handoff;
10. manual orchestrator triage for anything not safely classified.

The former terminal work order required rerunning Bundle 16R, 15R, 14R and 17R
only after all preceding work orders were physically evidenced. That execution
chain is retired; this requirement is retained to explain the historical close
boundary, not to request or enable a current rerun.

## Historical outputs

```text
R5_bundle17r_backflow_compilation.json
R5_bundle17r_backflow_issue_ledger.csv
R5_bundle17r_backflow_work_orders.csv
R5_bundle17r_backflow_dependency_graph.json
R5_bundle17r_backflow_case_matrix.csv
R5_bundle17r_backflow_execution_batches.yaml
work_order_handoffs/<work_order_id>.yaml
R5_bundle17r_backflow_status_proposal.yaml
R5_bundle17r_backflow_close_readout.md
R5_bundle17r_backflow_generation_lock.json
```

## Historical state semantics

| Decision | Meaning |
|---|---|
| `backflow_compilation_blocked` | physical/contract validation failed; remain in 17R targeted backflow |
| `needs_manual_route_review` | all physical inputs are valid but at least one blocker needs an explicit owner/stage route |
| `ready_for_targeted_backflow_execution` | every source blocker is preserved, routed, clustered, and dependency-ordered |

None of these states authorizes sample quality, human acceptance, canonical workflow-state mutation, or P2.

## Historical close boundary

In the original contract, 17R-BF1 engineering close meant that the compiler and
plans were installed and deterministic. Its research-close requirements were:

```text
all work-order acceptance artifacts physically present
+ reviewed official evidence and mappings
+ complete operating/forecast/valuation/semantic reruns
+ Bundle 16R/15R/14R/17R two-run deterministic equality
+ Bundle 17R activation = 4/4 and blockers = 0
```

Only after those conditions did the historical plan permit a Bundle 18R
exact-hash human-review handoff. This does not restore the retired chain or
dispatch a current workflow. Historical human-review records cannot replace
current final-report review, and P2 remains a separate canonical decision.
