# R5 Bundle 17R — Historical Activation Receipt and Human-Review Handoff

## Purpose

This is the historical contract for the retired Bundle 17R activation receipt.
Git commit `274d47ec299a42946bc3b83f7908257e80f0f99b` retired its implementation
and the Bundle 14R–16R execution chain. The fields, gates and decision branches
below describe those historical generations; they provide no current execution,
publication, reviewer authority or run-selection entry point. Retained records
follow the [canonical retention manifest](../meta/DOCS_REPORTS_RETENTION_DEPENDENCY_MANIFEST.yaml).
Current routing and final-report review remain governed by `RESEARCH_WORKFLOW.md`.

Bundle 16R supplied the reviewed-evidence materializer. Its execution could
publish evidence packs and invoke the then-existing Bundle 15R qualification
compiler and Bundle 14R four-company regression. Bundle 17R added the following
historical close boundary:

```text
Bundle 16R materialization suite + lock
+ Bundle 15R qualification suite + lock
+ Bundle 14R regression suite + lock
+ per-case qualification/result/Reader/quality/traceability locks
        ↓
physical hash verification + policy-owned pointer assertions
        ↓
deterministic activation receipt
+ targeted backflow queue
+ exact-hash human-review handoffs
+ non-canonical status proposal
```

The Bundle 17R receipt did not fetch, extract, review or fabricate evidence.
It did not rerun upstream engines, edit expected values, synthesize reviewer
approval, mutate canonical workflow state, authorize sample quality or open P2.

## Historical entry conditions

- `main` contains commit `7ab395283f432faac7bbc0e83a0b0cf4976ed5dc` or a reviewed descendant.
- Bundle 16R, 15R and 14R outputs have been generated from the real reviewed catalogs and mappings.
- Every path in the activation manifest is repository-relative and bound to the exact physical SHA-256.
- Narrative samples and generated prose are not evidence inputs.

## Historical gate ownership

The activation manifest chose only where a required assertion lived. The policy
owned the expected value. This prevented a mapping from changing “four packs
complete” to “three packs complete” or converting a failed candidate into a pass.

The historical suite assertions required:

- four cases;
- four materialized and fully mapped packs;
- four complete qualification packs and four Bundle 14R-ready cases;
- Bundle 14R contract suite passes;
- four research-ready and four exact-hash-review candidate cases;
- all canonical-state, sample-quality and P2 flags remain false.

Each historical case had to bind:

- the registered Bundle 14R case contract, so `case_id` and issuer ticker cannot be relabeled in the activation manifest;
- the exact Bundle 15R qualification YAML, including evidence-pack completeness, official-source count, qualified drivers, overlap resolution, forecast bridge, valuation eligibility, semantic gate, deterministic rerun and review-status fields;
- the corresponding Bundle 14R qualification result. This may be a case-local extraction or the shared suite file with a case-specific JSON pointer;
- Reader;
- Reader generation lock;
- semantic quality scorecard;
- traceability artifact.

The historical Bundle 14R result had to be both `research_ready` and
`candidate_ready_for_exact_hash_review`. The semantic quality scorecard used the
upstream `candidate_ready_for_exact_hash_review` field. The Reader generation
lock bound the exact Reader, quality and traceability hashes. Under that
generation's review policy, human review started `pending`; a blocked case was
`not_ready`. These records do not satisfy current final-report review.

## Historical decisions

These decision branches preserve the original contract, not current dispatch
instructions. A recorded `0/4` activation or `63` blockers belongs to its frozen
historical run and does not select or describe the current run.

```yaml
all_four_pass:
  decision: activation_ready_for_exact_hash_human_review
  next_stage: R5_bundle18r_exact_hash_human_review
  sample_quality_allowed: false
  p2_allowed: false

any_blocker:
  decision: needs_targeted_backflow
  next_stage: R5_bundle17r_targeted_backflow
  sample_quality_allowed: false
  p2_allowed: false
```

The original success branch planned a later Bundle 18R step to record exact-hash
human decisions and reconcile sample-quality state. Its `next_stage` values are
historical metadata; they do not dispatch an active workflow or replace current
review requirements. P2 remains a separate canonical decision.
