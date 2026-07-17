# R5 Bundle 17R-BF2 — Exact-hash backflow intake and review-promotion gate

## Purpose

Bundle 17R-BF1 compiles the source blocker queue into deterministic work orders. BF2 consumes the
BF1 generation lock, work-order CSV, occurrence-preserving issue ledger, case matrix and local
work-order result packages. It does **not** execute arbitrary commands and does **not** mutate the
canonical workflow state.

The implementation closes the gap between “a work order exists” and “the work order has an
inspectable result receipt”. It is specifically designed for the uncommitted 14R/15R/16R follow-up
fixes, evidence packs and review materials that remain in the local workspace.

## Invariants

1. Every BF1 input is checked against the BF1 generation lock.
2. Every result binds to the canonical SHA-256 of its BF1 work-order row.
3. Every source blocker occurrence remains present in the BF2 ledger.
4. A blocker is resolved only by an engineering-pass receipt that explicitly owns that blocker ID.
5. A passed result requires all declared checks to pass.
6. Manual routes require a signed manual attestation.
7. ZIP files, screenshots, logs and local archives never enter the repo-promotion manifest.
8. Cache, temporary, secret-like, hash-mismatched and unsafe-path artifacts are rejected.
9. Exact-hash human review binds to the case generation SHA, not merely the case name.
10. BF2 never grants sample-quality or P2 permission and never edits canonical workflow state.

## Runtime inputs

Copy `templates/r5_bundle17r_backflow_execution_manifest.yaml`, update the physical BF1 paths if
needed, and create a result dropzone such as:

```text
.local/r5_bundle17r_backflow_results/
  WO-001/
    result.yaml
    implementation_or_evidence_files...
  WO-002/
    result.yaml
  reviews/
    CASE-ID.yaml
```

Each result package follows `schemas/r5_bundle17r_work_order_result.schema.json`. A repository
candidate stored inside the dropzone must declare a safe `promotion_target`; an archive must declare
`archive_only` or `local_only`.

BF1 suite-level and terminal rerun work orders have an empty source `case_id`. Their BF2 result
manifests must use the reserved value `__suite__`. This value is a global scope marker and must not
be counted as a fifth research case or receive a case-review decision.

## Command

```bash
python scripts/run_r5_bundle17r_backflow_execution.py \
  --repo-root . \
  --manifest path/to/R5_bundle17r_bf2_execution_manifest.yaml
```

Use `--fail-on-manual-route` only when CI is expected to reject any remaining manual or pending work
orders.

## Deterministic outputs

```text
R5_bundle17r_bf2_execution_receipts.json
R5_bundle17r_bf2_issue_ledger.csv
R5_bundle17r_bf2_case_matrix.csv
R5_bundle17r_bf2_artifact_inventory.csv
R5_bundle17r_bf2_promotion_manifest.yaml
R5_bundle17r_bf2_archive_manifest.yaml
R5_bundle17r_bf2_rejected_artifacts.csv
review_handoffs/<case_id>.yaml
R5_bundle17r_bf2_status_proposal.yaml
R5_bundle17r_bf2_close_readout.md
R5_bundle17r_bf2_validation_report.json
R5_bundle17r_bf2_generation_lock.json
```

## State semantics

| Condition | Proposal |
|---|---|
| Any unresolved blocker or failed/pending work order | `R5_bundle17r_targeted_backflow` |
| All cases engineering-pass, exact-hash reviews incomplete | `R5_bundle17r_human_review` |
| All exact-hash reviews accepted | `R5_bundle17r_reviewed_candidate` |

Even the final row is only a proposal. A separate activation step must decide whether the canonical
state may move. `sample_quality_allowed` and `p2_allowed` remain false throughout BF2.

## Required execution sequence

1. Run BF1 against the four Bundle 17R case packages.
2. Place each 14R/15R/16R follow-up artifact into a work-order result directory.
3. Mark ZIP/screenshots/logs as archive-only; delete caches and temporary files.
4. Run BF2 and inspect rejected artifacts and unresolved blocker counts.
5. Execute targeted research/implementation work for remaining work orders.
6. Re-run BF2 until each case reaches engineering pass.
7. Review each `review_handoffs/<case_id>.yaml` and sign an exact-hash decision.
8. Re-run BF2; confirm accepted reviews bind to the current case generation SHA.
9. Apply only the promotion manifest in a separate, reviewed commit.
10. Run general CI plus Bundle 17R-BF1/BF2 CI before any canonical state activation.
