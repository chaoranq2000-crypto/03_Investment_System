# R5 Bundle 17R-BF1 — Targeted Backflow Compiler

## Purpose

Bundle 17R activation has a truthful blocked outcome:

```text
needs_targeted_backflow
0 / 4 engineering cases activated
63 blockers
sample_quality_allowed = false
p2_allowed = false
```

The next step is not Bundle 18R human review and not another Reader rebuild. This bundle compiles the exact physical Bundle 17R blocker queue into a deterministic, dependency-ordered set of work orders.

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

## Why this remains under Bundle 17R

The Bundle 17R success branch reserves Bundle 18R for exact-hash human review. The current activation decision is the failure branch `R5_bundle17r_targeted_backflow`; therefore the corrective package is named `17R-BF1` and keeps Bundle 18R reserved.

## Inputs

A manifest binds four physical artifacts from the committed Bundle 17R run:

- activation receipt;
- activation generation lock;
- backflow queue;
- case matrix.

The policy owns the expected values. A manifest can choose physical paths and hashes but cannot change `0/4`, `63`, the expected decision, or the release boundaries.

## Validation gates

The compiler fails closed when:

- a bound file is absent, outside an allowed root, forbidden, or hash-mismatched;
- receipt and generation-lock generation IDs differ;
- the queue or case matrix is not bound by the Bundle 17R generation lock;
- the receipt is not `needs_targeted_backflow`;
- the case count, pass count, or blocker count differs from policy;
- any release flag is truthy;
- any blocker lacks code, stage, owner, target, message, or requested action;
- a case-specific blocker references a case absent from the matrix;
- a dependency is unknown or cyclic.

## Routing and clustering

Every source row remains in the issue ledger with a stable issue ID, including duplicate rows. Clustering reduces execution noise but never reduces blocker accounting.

Routes are policy-owned:

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

A terminal work order reruns Bundle 16R, 15R, 14R, and 17R only after all preceding work orders are physically evidenced.

## Outputs

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

## State semantics

| Decision | Meaning |
|---|---|
| `backflow_compilation_blocked` | physical/contract validation failed; remain in 17R targeted backflow |
| `needs_manual_route_review` | all physical inputs are valid but at least one blocker needs an explicit owner/stage route |
| `ready_for_targeted_backflow_execution` | every source blocker is preserved, routed, clustered, and dependency-ordered |

None of these states authorizes sample quality, human acceptance, canonical workflow-state mutation, or P2.

## Close boundary

17R-BF1 engineering close means the compiler and plans are installed and deterministic. Research close requires:

```text
all work-order acceptance artifacts physically present
+ reviewed official evidence and mappings
+ complete operating/forecast/valuation/semantic reruns
+ Bundle 16R/15R/14R/17R two-run deterministic equality
+ Bundle 17R activation = 4/4 and blockers = 0
```

Only then may the workflow route to Bundle 18R exact-hash human review. Bundle 18R still cannot grant P2 automatically.
