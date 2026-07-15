# R5 Bundle 15R — Reviewed Official Evidence Qualification Contract

## 1. Purpose

Bundle 15R is the reviewed-evidence qualification bridge for the Bundle 14R
cross-industry golden-regression harness.

Bundle 14R already defines four issuer-neutral economic-model contracts, a
non-compensating semantic gate, deterministic seed execution, targeted
backflow, and exact-hash review boundaries. Its seed lane intentionally starts
with no reviewed qualification packs. Bundle 15R converts already-reviewed,
physically archived official evidence into the exact qualification mapping
consumed by Bundle 14R.

Bundle 15R does **not**:

- fetch or invent evidence;
- review evidence automatically;
- treat narrative samples as evidence;
- write or accept a Reader report;
- mutate canonical workflow state;
- authorize sample quality or P2.

A blocked case is a correct result when evidence, overlap reconciliation,
forecast bridges, valuation eligibility, semantic quality, or determinism is
missing.

## 2. Baseline and namespace

Implementation baseline:

```text
main = 60f3e24af8572faaf1c7a9b12a37b4ac085d7b36
```

Recommended branch:

```text
codex/r5-bundle15r-reviewed-evidence-qualification
```

Generated outputs must live outside committed source paths, for example:

```text
bundle15r/generated/<run_id>/
```

The implementation patch is add-only. Existing evidence manifests, generated
reports, ZIP deletions, local downloads, caches, and unrelated worktree changes
must remain unstaged.

## 3. Inputs

### 3.1 Bundle 14R case contracts

Default path:

```text
tests/fixtures/r5_bundle14r/cases/*.yaml
```

The compiler reads, rather than duplicates:

- case ID and issuer identity;
- required operating drivers;
- research questions;
- required source classes;
- forecast coverage thresholds;
- eligible valuation methods.

### 3.2 Reviewed evidence packs

One YAML pack may be supplied per case. Every real source must be:

- official under the configured source-class policy;
- accepted or accepted-with-limitations by a named reviewer;
- archived at a safe repository-relative path;
- bound to its physical SHA-256;
- dated and assigned a covered period.

Each operating record must preserve:

- driver ID and linked research-question IDs;
- status (`confirmed`, `bounded_estimate`, `context_only`, `blocked`, or
  `not_applicable`);
- value or bounded range;
- unit, period, and operating definition;
- confidence and review status;
- source IDs;
- overlap rule and stale trigger.

Narrative samples and generated reports are prohibited as evidence or numeric
model inputs.

## 4. Qualification algorithm

For each case, Bundle 15R evaluates the following non-compensating gates.

### G15R-1 — Pack identity and review

- schema, case ID, and ticker match the Bundle 14R case;
- pack review is human-authored and accepted;
- automated release flags remain false.

### G15R-2 — Physical official evidence

- every qualifying source is official and reviewed;
- archive path exists;
- SHA-256 matches the physical file;
- required source classes are covered.

### G15R-3 — Driver and question coverage

- records reference only drivers and questions defined by Bundle 14R;
- every required driver has at least one qualifying, non-conflicting record;
- every research question is classified by a reviewed record;
- low-confidence or context-only records cannot qualify a driver.

### G15R-4 — Duplicate and conflict handling

Equal reviewed records with the same driver, period, unit, definition, and value
are deterministically suppressed. Different reviewed values for the same
operating definition create a conflict ledger and fail closed for that driver.

### G15R-5 — Overlap reconciliation

Revenue and gross-profit overlap must both be resolved. A broad segment and a
cross-cutting theme cannot be double-counted.

### G15R-6 — Driver-to-financial bridge

The pack must pass:

- driver-to-statement reconciliation;
- working-capital bridge;
- cash-flow bridge;
- the case-specific minimum revenue explanation ratio;
- the case-specific minimum gross-profit explanation ratio.

### G15R-7 — Independent valuation eligibility

At least one method must pass its own gate:

- reverse valuation: market value, share count, forecast definition, and
  implied operating assumptions reconcile;
- peer multiples: at least three definition-, period-, and metric-compatible
  peers;
- DCF/SOTP: qualified cash-flow or segment economics, overlap elimination,
  discount inputs, and terminal assumptions.

Declaring a method eligible is not sufficient.

### G15R-8 — Semantic artifact and determinism

- the Bundle 14R semantic result is physically hash-bound and passed;
- rerun hashes match;
- input and output generation locks are complete.

### G15R-9 — Exact-hash human review pass-through

Bundle 15R may preserve `not_triggered`, `pending`, `accepted`, or `rejected`.
An accepted review must identify a reviewer, timestamp, physical review path,
and matching SHA-256. Acceptance still does not authorize sample quality or P2.

## 5. Bundle 14R qualification output

The compiler emits one YAML per case containing the exact fields Bundle 14R
currently consumes:

```yaml
qualified_driver_ids: []
reviewed_official_source_count: 0
overlap_resolved: false
forecast_bridge_complete: false
valuation_eligible: false
semantic_gate_passed: false
deterministic_rerun: false
exact_hash_human_review_status: not_triggered
```

Bundle 15R adds an audit block, but the three release keys remain hard-false. Any truthy
value for sample quality, P2, or workflow-state mutation is a contract violation.

## 6. Outputs

A run emits:

```text
qualification/<case_id>.yaml

audit/<case_id>_qualification_audit.json
R5_bundle15r_qualification_suite.json
R5_bundle15r_generation_lock.json
R5_bundle15r_evidence_request_queue.csv
R5_bundle15r_conflict_ledger.csv
R5_bundle15r_status_proposal.yaml
R5_bundle15r_close_readout.md
```

`R5_bundle15r_status_proposal.yaml` is explicitly non-canonical. It exists to
make status drift visible without overwriting a workflow-state file.

## 7. Selective Bundle 14R activation

The compiler may invoke the existing Bundle 14R runner with its generated
qualification directory. Cases are evaluated independently:

- a qualified case may advance to Bundle 14R candidate evaluation;
- a blocked case remains in targeted backflow;
- one strong case cannot compensate for another blocked case;
- Bundle 15R cannot self-close Bundle 14R or change release authority.

## 8. Seed and closure semantics

With no real reviewed evidence packs, the expected seed is:

```yaml
case_count: 4
evidence_pack_present_count: 0
evidence_pack_complete_count: 0
bundle14r_candidate_ready_count: 0
sample_quality_allowed: false
p2_allowed: false
workflow_state_mutation_allowed: false
```

Engineering close means the compiler, negative tests, deterministic outputs,
CI, and backflow artifacts work. Research close requires real reviewed official
evidence and independent passage of all case gates. These states must never be
conflated.
