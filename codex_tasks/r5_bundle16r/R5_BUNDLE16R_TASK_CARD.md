# R5 Bundle 16R Task Card — Four-Company Golden Regression and Release Gate

## Baseline

- Required base commit: `1d4b1f151b97337d8def33c409532f28794b6652`
- Recommended branch: `codex/r5-bundle16r-real-company-regression`
- Bundle 15R must remain intact.
- Do not include ZIP files, `bundle16r/generated/`, caches, backups or the pre-existing unstaged deletion of `r5_after_patch12_patch_package.zip`.

## Objective

Implement and wire the first real-company, cross-economic-model regression gate for:

1. 铜冠铜箔 / 301217 — high-end manufacturing and product generation;
2. 赤峰黄金 / 600988 — cyclical resource mining;
3. 药明康德 / 603259 — backlog and project-funnel service platform;
4. 东阳光 / 600673 — multi-business, project economics and M&A consolidation.

The bundle must prove that one issuer-neutral runtime can consume official evidence, build different operating-driver models, produce traceable forecasts and Reader reports, and return precise backflow when a case is not research-useful.

## This patch supplies

- a deterministic suite evaluator;
- the four-case registry and thresholds;
- an executable test suite;
- the governing workflow contract;
- an acceptance matrix; and
- a close-readout template.

The evaluator is implementation code, not a substitute for the four real evidence packs. The sample reports are narrative benchmarks only.

## Required integration work

### 1. Preserve the global workflow kernel

Do not add a parallel workflow. Consume the existing T0–T10 interfaces and Bundle 11R–15R runtime outputs. Only add adapters where an existing artifact does not yet expose a required metric.

### 2. Produce one physical case-result manifest per company

Place generated manifests outside committed source paths, for example:

```text
bundle16r/generated/case_results/
  301217_high_end_copper_foil.json
  600988_cycle_resource_gold.json
  603259_crdmo_backlog_funnel.json
  600673_multi_business_ma.json
```

Every artifact path must be repository-relative and every SHA must match the physical file.

### 3. Use reviewed official evidence

For each company, onboard a reviewed source pack dominated by issuer filings and other primary sources. Industry and peer evidence must have explicit definitions, dates and confidence. The four external sample reports may shape the research-question matrix but cannot be evidence or numeric model inputs.

### 4. Bind each material segment to an economic driver

Do not satisfy the gate by mapping all segments to `revenue_growth × margin`. Use the registered archetypes and document any residual. When evidence is missing, create a targeted research gap/backflow item instead of fabricating a value.

### 5. Emit the required metrics from upstream artifacts

Metrics in the case manifest must be derived, not handwritten. Add adapters/tests for:

- material segment driver coverage;
- revenue and gross-profit explanation ratios;
- residual ratios;
- forecast assumption traceability;
- model-linked core-section ratio;
- section novelty;
- citation resolution;
- company-specific metric count;
- future-event-to-model links;
- qualified peers; and
- unresolved critical questions.

### 6. Route failures to the owning stage

At minimum:

| Failure | Required backflow owner |
|---|---|
| missing official operating variable | evidence-ingest / research-question planner |
| driver coverage or overlap failure | operating-driver engine |
| forecast traceability failure | forecast model |
| peer definition failure | peer eligibility / valuation |
| repeated generic prose or no model link | report planner / semantic quality |
| unresolved citation or truthfulness flag | quality review |
| exact-hash human review mismatch | review handoff, never automated acceptance |

### 7. Keep release states conservative

Until all four cases pass and are exact-hash accepted by a real reviewer:

```yaml
sample_quality_allowed: false
p2_allowed: false
```

Bundle 16R engineering close may state that the harness is complete. It may not state that sample-quality or P2 has been authorized.

## Required commands

```bash
python -m src.research.r5_bundle16r_real_company_regression \
  validate-registry \
  --registry config/r5_bundle16r_real_company_cases.yaml

pytest -q tests/test_r5_bundle16r_real_company_regression.py

python -m src.research.r5_bundle16r_real_company_regression \
  evaluate \
  --repo-root . \
  --registry config/r5_bundle16r_real_company_cases.yaml \
  --case-results-dir bundle16r/generated/case_results \
  --output-dir bundle16r/generated/readout
```

The final command is expected to fail until all four real case manifests and physical artifacts exist. Do not weaken thresholds to make it pass.

## Required regression tests

1. all four valid synthetic cases pass the engineering gate while human reviews remain pending;
2. a missing golden case blocks the suite;
3. a hash mismatch blocks the case;
4. a narrative sample path used as evidence blocks the case;
5. low operating-driver explanation ratios block the case;
6. peer multiples with fewer than three qualified peers block the case;
7. accepted human review with mismatched report/lock hashes blocks sample-quality;
8. issuer-specific runtime tokens outside allowed registry/test paths block the suite;
9. repeated evaluation produces byte-identical JSON and Markdown;
10. `p2_allowed` remains false even after all automated and human prerequisites pass.

## Commit scope

The supplied patch contains seven repository files. Integration may modify the narrowest necessary existing files, but the final commit must list every extra path in the close readout and justify it. Do not commit generated case outputs before review.

## Completion definition

Bundle 16R is engineering-complete only when:

- supplied tests pass;
- existing CI remains green;
- four real case manifests can be generated from official evidence and current runtime outputs;
- evaluator readouts are deterministic;
- failure backflow is routed to the owning stage;
- canonical state remains conservative; and
- the close readout distinguishes engineering completion from human sample-quality acceptance.
