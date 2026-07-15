# R5 Bundle 14R — Cross-Industry Golden Regression and Benchmark Qualification

## 1. Baseline and current boundary

Target baseline:

```text
main = 0966b914476b8f0a89b39d0f06a58dca5d3b20a7
```

The baseline already contains the Bundle 11R runtime refactor, Bundle 12R operating-evidence qualification, and Bundle 13R evidence-backflow implementation. The active issuer-specific workflow remains in the Bundle 13R T1/T2 official-evidence backflow lane. Bundle 14R must not bypass, close, or mutate that lane.

Hard preserved flags:

```yaml
sample_quality_allowed: false
p2_allowed: false
workflow_state_mutation_allowed: false
```

The existing exact-hash human review remains valid until one of its locked inputs or outputs changes. Bundle 14R runs in a separate regression namespace and does not invalidate it.

## 2. Objective

Bundle 14R proves that the same research kernel can formulate, qualify, model, render, and review materially different economic models without issuer-specific runtime code.

The four golden regressions are:

| Case | Economic-model stress test | Required operating chain |
|---|---|---|
| Copper foil / product generation | High-end manufacturing and product iteration | capacity × utilization × yield × product mix × processing fee → unit margin → cash conversion |
| Gold mining / commodity cycle | Commodity price, mine plan, and capital intensity | realized price × saleable volume − unit cost; ore × grade × recovery; stripping/capex → free cash flow |
| CRDMO / backlog conversion | Backlog, project stage, capacity, and regulatory transition | backlog × conversion + new orders; stage mix × revenue/project × margin; capacity utilization → cash flow |
| Multi-business AI infrastructure | Mixed industrial, project, IDC, and M&A economics | quota/price/cost + capacity/mix + project/unit value/acceptance + IDC utilization/power + consolidation/financing |

Narrative samples are permitted only as a benchmark for analytical dimensions, section emphasis, and adversarial test design. They are prohibited as factual evidence.

## 3. Non-goals

Bundle 14R does not:

- manufacture missing issuer evidence;
- declare any of the four companies research-ready merely because a case contract validates;
- reuse sample-report numbers as facts;
- add issuer-name branches to the generic runtime;
- force peer multiples, DCF, or SOTP when their independent eligibility gates fail;
- change the existing Bundle 13R workflow state;
- grant sample-quality or P2 status automatically;
- output direct trading, position-sizing, or target-price instructions.

## 4. Deliverables

### Runtime

- `src/research/r5_bundle14r_golden_regression.py`
  - validates company-specific economic-model contracts;
  - separates contract validity from evidence/research readiness;
  - creates targeted backflow items;
  - scans generic runtime files for issuer-specific tokens;
  - produces deterministic suite and generation-lock payloads.

- `src/quality/r5_bundle14r_semantic_regression.py`
  - applies non-compensating gates to truthfulness, driver-to-statement linkage, semantic incrementality, valuation eligibility, actionable backflow, and determinism;
  - rejects long but generic reports;
  - rejects ineligible valuation even if other sections score highly;
  - can only prepare a candidate for exact-hash human review.

- `scripts/run_r5_bundle14r_golden_regression.py`
  - verifies an optional Git baseline;
  - loads four case contracts and optional reviewed qualification summaries;
  - writes results only to `--output-dir`;
  - never mutates workflow state or release flags.

### Golden case contracts

- `tests/fixtures/r5_bundle14r/cases/copper_foil.yaml`
- `tests/fixtures/r5_bundle14r/cases/gold_mining.yaml`
- `tests/fixtures/r5_bundle14r/cases/crdmo.yaml`
- `tests/fixtures/r5_bundle14r/cases/multi_business_ai_infrastructure.yaml`

The contracts define research questions, driver formulas, official evidence requirements, fallback policies, forecast mappings, valuation eligibility, narrative emphasis, backflow ownership, and expected locked artifacts. They contain no assertion that the requested facts are already available.

### Tests and CI

- contract and genericity tests;
- sample-as-evidence negative test;
- missing-driver negative test;
- automated-release negative test;
- deterministic-lock test;
- long-but-empty semantic negative test;
- non-compensating valuation test;
- isolated-output test;
- dedicated GitHub Actions workflow.

## 5. Execution stages

### 14R-0 — Baseline and namespace lock

1. Verify `HEAD` is the declared baseline or an approved descendant.
2. Verify the existing Bundle 13R state remains unchanged.
3. Create a dedicated implementation branch.
4. Apply the patch with `git apply --check` before mutation.
5. Record all pre-existing uncommitted paths; do not stage or delete them.

Exit condition: patch applies without touching existing issuer evidence, generated reports, ZIP files, or deletion state.

### 14R-1 — Contract and runtime installation

1. Install the generic case-contract validator and suite runner.
2. Install the non-compensating semantic gate.
3. Install four case contracts.
4. Run the focused tests.
5. Run the contract suite with no qualification packs.

Expected result:

```text
contract_passed = true
research_ready_case_count = 0
candidate_ready_case_count = 0
sample_quality_allowed = false
p2_allowed = false
```

This is a successful seed state, not a quality failure.

### 14R-2 — Reviewed official evidence packs

For each case, build a reviewed evidence pack from primary or issuer-official sources. Every claim must include:

- source identifier and URL/file reference;
- issuer/peer/industry/market source class;
- period and as-of date;
- unit and currency;
- definition and business boundary;
- fact, management statement, estimate, or inference label;
- confidence;
- overlap/double-counting rule;
- stale dependency targets.

Each research question must resolve to one of:

```text
official fact
bounded estimate with explicit range and bridge
context only
blocked / missing
```

No missing driver may be replaced with a narrative sample number.

### 14R-3 — Operating-driver and financial models

For every material segment:

1. qualify required operating drivers;
2. calculate segment revenue and gross profit;
3. eliminate cross-cutting and segment overlap;
4. reconcile segment results to consolidated statements;
5. build working-capital, cash-tax, capex, and free-cash-flow bridges;
6. retain explicit residuals and proxy shares;
7. run single-variable and paired sensitivities;
8. generate targeted backflow for unqualified drivers.

Minimum release floors:

| Metric | Floor |
|---|---:|
| Segment revenue explained by drivers | 80% |
| Segment gross profit explained by drivers | 80% |
| Required driver qualification | 100%, unless the contract explicitly permits a bounded estimate |
| Driver-to-statement reconciliation | pass |
| Material overlap elimination | pass |
| Cash-flow and working-capital bridges | pass |

### 14R-4 — Valuation qualification and expectation gap

Each method is independently gated:

- peer multiples require at least three definition/period/metric/confidence-compatible peers;
- DCF requires a qualified free-cash-flow bridge, discount inputs, terminal assumptions, and period consistency;
- SOTP requires independent segment economics and explicit overlap elimination;
- reverse valuation requires reconciled market value, share count, forecast definition, and implied operating assumptions.

An ineligible method may be discussed only as context and may not be used to derive a valuation conclusion.

### 14R-5 — Reader, thesis planner, and semantic adversarial gate

The report planner must place at least 60% of analytical emphasis on the three highest-priority company-specific contradictions. Each core section must add a new metric, model link, conclusion, or falsification condition.

Adversarial failures include:

- long report with generic language;
- the same thesis paraphrased across sections;
- non-empty causal fields with no company-specific variable;
- forecast assumptions with no driver-to-statement bridge;
- three low-confidence peers satisfying peer completeness;
- observations without thresholds, dates, or falsification criteria;
- past events presented as future catalysts;
- direct trading or position instructions;
- issuer-specific tokens in generic runtime code.

### 14R-6 — Determinism and exact-hash human review

For each candidate:

1. run a deterministic rerender;
2. lock all evidence, model, report, traceability, quality, and review-handoff files;
3. compare rerun hashes;
4. submit the exact generation ID and hashes to a real reviewer;
5. invalidate the review if any locked input or output changes.

Automated gates may produce only:

```text
candidate_ready_for_exact_hash_review
```

They may not produce human approval, sample-quality approval, or P2 approval.

### 14R-7 — Close or targeted backflow

Bundle 14R may close only when:

- all four contracts pass;
- the same core runtime is used for all four cases;
- no issuer-specific code is added to generic modules;
- truthfulness and determinism pass for all four;
- all four have explicit qualification outcomes;
- at least three cases receive exact-hash `research_useful` human acceptance;
- the fourth case is accepted or has a closed, owner-assigned evidence limitation that does not masquerade as completion;
- sample-quality and P2 remain separately controlled by the canonical release workflow.

Any failure must return to the named stage and skill. “Write more text” is never an acceptable backflow instruction.

## 6. Acceptance matrix

| Gate | Pass condition | Failure owner |
|---|---|---|
| Contract validity | all four schemas, drivers, questions, mappings, artifacts, and release policies pass | research-orchestrator |
| Core genericity | no issuer name or ticker in generic Bundle 14R runtime | engineering |
| Official evidence | every required driver has reviewed official support or an allowed bounded estimate | evidence-ingest |
| Driver model | required drivers explain ≥80% revenue and gross profit and reconcile to statements | stock-deep-dive |
| Overlap | segment/cross-cutting revenue and gross profit double counting is eliminated | stock-deep-dive |
| Valuation | at least one method independently qualifies; ineligible methods are not used | valuation-model |
| Semantic quality | all non-compensating core gates pass and score ≥80 | quality-review |
| Determinism | input/output locks and rerun hashes agree | research-orchestrator |
| Human review | exact generation/hash accepted by a real reviewer | human reviewer |
| Release boundary | automated sample-quality, P2, and workflow mutation remain false | research-orchestrator |

## 7. Relationship to Bundle 13R

Bundle 13R remains the active issuer-specific evidence-backflow lane. Bundle 14R is an orthogonal cross-industry regression lane. It may reuse generic runtime components, but it may not:

- set Bundle 13R issues to resolved;
- regenerate the Bundle 13R model or Reader without new reviewed evidence;
- modify the Bundle 13R `next_stage` or required skill;
- replace the existing exact-hash review;
- infer missing liquid-cooling economics from benchmark cases.

The only legitimate trigger for the blocked Bundle 13R items remains reviewed, same-period, definition-compatible official operating evidence.
