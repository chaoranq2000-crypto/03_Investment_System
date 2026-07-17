# R5 Bundle 17R-BF1 Targeted Backflow Plan

## Executive decision

The committed Bundle 17R run is an honest engineering success and a research block: 0 of 4 cases activated and 63 blockers remain. Do not weaken the gates, promote sample quality, open P2, or jump to human acceptance. Compile the exact blocker queue, resolve root causes in dependency order, and rerun the existing chain.

## Phase 0 — Bind the committed run

1. Start from commit `d61df6e457dc9bd02d13f1722a0630c9d6b134ea` or a reviewed descendant.
2. Record the complete working-tree status and preserve all unstaged local files/deletions.
3. Locate the committed Bundle 17R activation receipt, generation lock, backflow queue, and case matrix.
4. Copy the manifest template to a run-specific local directory.
5. Fill only repository-relative paths and exact SHA-256 values.
6. Do not edit the policy-owned assertions: decision `needs_targeted_backflow`, 4 cases, 0 engineering passes, 63 blockers.

Exit: all four physical inputs are exact-hash bound and the source Bundle 17R generation is coherent.

## Phase 1 — Compile and inspect all blockers

Run the compiler twice into separate output directories and require byte-identical trees.

Inspect:

- every source blocker appears exactly once in the enriched issue ledger, with duplicates preserved by occurrence ID;
- route distribution and manual-route count;
- per-case blocker totals;
- clustered work orders;
- dependency graph and batches;
- release flags all remain false.

Exit: `ready_for_targeted_backflow_execution`, or every unrouted issue has a manual route-review work order.

## Phase 2 — Execute root-cause batches

### B0 — Physical integrity

Repair only exact paths, hashes, JSON/YAML pointers, generation IDs, schema mismatches, and deterministic output bindings. Never change upstream research values merely to satisfy an assertion.

### B1 — Official evidence

For each missing or weak research input:

- archive immutable official filings/announcements/IR records;
- extract normalized records with source hash and locator;
- record unit, period, definition, scope, and review status;
- reject news, samples, unreviewed claims, and narrative benchmarks as evidence.

### B2 — Mapping and qualification

- create reviewer-authored record-to-driver/question mappings;
- resolve equal-value duplicates deterministically;
- fail closed on conflicting values until reviewed reconciliation;
- prove, range-estimate, or explicitly block every critical research question.

### B3 — Operating economics and overlap

Use company-specific economic-driver contracts rather than a universal growth-rate proxy.

| Case archetype | Required operating bridge |
|---|---|
| 301217 high-end manufacturing | HVLP generation / processing fee / capacity / utilization / certification → segment revenue and gross profit |
| 600988 resource mining | commodity price / production / grade-recovery / unit cost / stripping / capex → mine and consolidated cash earnings |
| 603259 project-funnel services | backlog / project stage / conversion / capacity / mix → revenue recognition, margin and cash conversion |
| 600673 multi-business and M&A | quota-price-volume, materials capacity/mix, liquid-cooling project value/acceptance, IDC utilization/unit revenue, consolidation and financing cost |

Eliminate segment overlap and double counting before forecasts or valuation.

### B4 — Forecast and valuation

- rebuild Base/Bull/Bear from qualified operating drivers;
- trace every material assumption to evidence or an explicit bounded proxy;
- reconcile profit, working capital, capex, cash flow, and capital structure;
- independently qualify peer multiples, reverse valuation, DCF, or SOTP;
- disable ineligible methods rather than forcing a conclusion.

### B5 — Semantic Reader and traceability

- rerender only after evidence/model generation changes;
- require company-specific metrics, causal mechanisms, model links, novelty, counter-evidence, and falsifiable watch conditions;
- resolve every material citation;
- produce stable Reader, scorecard, traceability, and generation-lock hashes;
- keep human review pending.

Exit: every non-terminal work order has physical output artifacts and passes its acceptance checks.

## Phase 3 — Rerun the existing chain

1. Run Bundle 16R materialization twice; compare complete trees.
2. Run Bundle 15R qualification and selective Bundle 14R regression.
3. Run Bundle 17R activation twice with exact bindings.
4. Compare all generation locks and output hashes.
5. Do not hand-edit suite counts or candidate states.

Success path:

```yaml
bundle17r_decision: activation_ready_for_exact_hash_human_review
engineering_pass_count: 4
blocker_count: 0
human_review_status: pending
sample_quality_allowed: false
p2_allowed: false
next_stage: R5_bundle18r_exact_hash_human_review
```

Blocked path:

```yaml
bundle17r_decision: needs_targeted_backflow
sample_quality_allowed: false
p2_allowed: false
next_stage: R5_bundle17r_targeted_backflow
```

## Phase 4 — Commit boundary

Commit only the 14 implementation/contract paths in this patch. By default do not commit:

- real evidence downloads or reviewer-local mappings unless separately reviewed for promotion;
- generated BF1/16R/15R/14R/17R run directories;
- ZIP/patch packages;
- caches, backups, screenshots, temporary directories;
- unrelated local modifications or deletions.

Suggested commit:

```text
feat(r5): add deterministic Bundle 17R targeted-backflow compiler
```
