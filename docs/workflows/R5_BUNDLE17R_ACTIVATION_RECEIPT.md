# R5 Bundle 17R — Activation Receipt and Exact-Hash Human-Review Handoff

## Purpose

Bundle 16R installs the reviewed-evidence materializer. Its real execution can publish evidence packs and invoke the existing Bundle 15R qualification compiler and Bundle 14R four-company regression. Bundle 17R adds the missing close boundary:

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

Bundle 17R does not fetch, extract, review or fabricate evidence. It does not rerun upstream engines, edit expected values, synthesize reviewer approval, mutate canonical workflow state, authorize sample quality or open P2.

## Entry conditions

- `main` contains commit `7ab395283f432faac7bbc0e83a0b0cf4976ed5dc` or a reviewed descendant.
- Bundle 16R, 15R and 14R outputs have been generated from the real reviewed catalogs and mappings.
- Every path in the activation manifest is repository-relative and bound to the exact physical SHA-256.
- Narrative samples and generated prose are not evidence inputs.

## Gate ownership

The activation manifest chooses only where a required assertion lives. The policy owns the expected value. This prevents a mapping from changing “four packs complete” to “three packs complete” or converting a failed candidate into a pass.

Suite assertions require:

- four cases;
- four materialized and fully mapped packs;
- four complete qualification packs and four Bundle 14R-ready cases;
- Bundle 14R contract suite passes;
- four research-ready and four exact-hash-review candidate cases;
- all canonical-state, sample-quality and P2 flags remain false.

Each case must bind:

- the registered Bundle 14R case contract, so `case_id` and issuer ticker cannot be relabeled in the activation manifest;
- the exact Bundle 15R qualification YAML, including evidence-pack completeness, official-source count, qualified drivers, overlap resolution, forecast bridge, valuation eligibility, semantic gate, deterministic rerun and review-status fields;
- the corresponding Bundle 14R qualification result. This may be a case-local extraction or the shared suite file with a case-specific JSON pointer;
- Reader;
- Reader generation lock;
- semantic quality scorecard;
- traceability artifact.

The Bundle 14R result must be both `research_ready` and `candidate_ready_for_exact_hash_review`. The semantic quality scorecard must use the upstream `candidate_ready_for_exact_hash_review` field. The Reader generation lock must bind the exact Reader, quality and traceability hashes. Human review starts `pending`; a blocked case is `not_ready`.

## Decisions

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

Bundle 18R may later record real exact-hash human decisions and reconcile canonical sample-quality state. P2 remains a separate decision.
