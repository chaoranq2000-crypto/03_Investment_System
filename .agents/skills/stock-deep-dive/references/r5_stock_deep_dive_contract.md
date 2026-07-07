# R5 Stock Deep Dive Contract — B5-lite

> This is the R5-MVP execution contract for `stock-deep-dive`. It supplements the current R4 stock-deep-dive contract; it does not override `AGENTS.md`, `docs/workflows/RESEARCH_WORKFLOW.md`, evidence discipline, or the no-advice boundary.

## 1. Goal

B5-lite does **not** generate a sample-quality report. It makes `stock-deep-dive` able to produce the structured source artifact for a future R5 report:

```text
reports/workflow_runs/<workflow_id>/R5_stock_research_pack.yaml
```

The report composer may only translate this pack. It must not invent facts, estimates, valuation numbers, catalysts, or conclusions.

## 2. Inputs

R5 mode may consume:

```text
stock_code
company_name
company_id
exchange
workflow_id
evidence_manifest
claim_candidates or claims_registry
metric_candidates or metrics_registry
financial_metric_pack.csv or TODO_SOURCE_REQUIRED
market_snapshot.csv or TODO_MARKET_DATA
peer_market_snapshot.csv or TODO_PEER_DATA
industry_context_card.yaml or TODO_SOURCE_REQUIRED
segment_exposure.yaml or TODO_SOURCE_REQUIRED
prior stock_analysis_pack.yaml if available
```

Rules:

```text
1. Official disclosure has priority over third-party data.
2. Market data may support valuation/technical context, not business exposure proof.
3. Management comments, analyst views, news clues, and investor-interaction clues must retain claim_type/source_type.
4. Missing fields must remain TODO / MISSING_DISCLOSURE / TODO_SOURCE_REQUIRED.
5. Company-level metrics cannot be used to infer segment revenue_pct or profit_pct.
```

## 3. Outputs

Minimum B5-lite outputs:

```text
R5_stock_research_pack.yaml
R5_source_gap_report.md
R5_open_questions.md
r5_quality_handoff.yaml
```

Optional structured sidecars:

```text
financial_history_pack.csv
business_breakdown_pack.yaml
segment_exposure.yaml
industry_context_pack.yaml
```

B5-lite must not mark a run as `sample_quality_ready`.

## 4. Local procedure

### R5-SDD-0 Company identity gate

Confirm `stock_code`, `company_id`, `company_name`, `exchange`, security identity, and `workflow_id`. Block if the listed entity is ambiguous or inconsistent.

### R5-SDD-1 Evidence snapshot gate

Record evidence counts and critical missing sources. Missing market, peer, financial, or industry inputs may be accepted only if the missing reason is explicit.

### R5-SDD-2 Financial history pack

Build `financial_history_pack` according to `r5_financial_history_contract.md`. The pack should identify revenue driver, margin driver, adjusted profit bridge, cash-flow quality, working-capital flags, and ROE/ROIC commentary.

### R5-SDD-3 Business breakdown pack

Build `business_breakdown_pack` according to `r5_business_breakdown_contract.md`. Every business line must have explicit values or explicit missing reasons for revenue, revenue_pct, gross_margin, gross_profit, and gross_profit_pct.

### R5-SDD-4 Segment exposure pack

Build `segment_exposure_pack`. Product clues cannot be promoted into revenue or profit exposure. `revenue_pct` and `profit_pct` remain `MISSING_DISCLOSURE` unless directly disclosed or accepted by quality review from official sources.

### R5-SDD-5 Industry context bridge

Create a light individual-stock industry bridge, not a full segment report. Each core linked segment should capture demand drivers, supply constraints, price/margin mechanism, competition structure, company position, and missing items.

### R5-SDD-6 Forecast / valuation placeholders

B5-lite only preserves structure:

```text
forecast_model_pack.status = TODO or TODO_MODEL_INPUT
valuation_pack.status = TODO or TODO_MARKET_DATA
```

Do not create 2026E-2028E forecasts, market cap, PE/PB/PS, peer multiples, target prices, or trading actions.

### R5-SDD-7 Market / sentiment / event placeholders

Technical, sentiment, and catalyst fields must have `as_of_date` before they can support state language. Without current data, keep TODOs visible.

### R5-SDD-8 Quality handoff

Create `r5_quality_handoff.yaml` with artifact path, allowed report level, known blockers, medium TODOs, source-gap visibility, no-advice input, fix owner, and next actions.

## 5. Degrade rules

```text
Missing company_identity_pack -> blocked.
Missing evidence_snapshot_pack -> blocked.
Missing financial_history_pack -> source_gapped_draft.
Missing business_breakdown_pack -> research_draft.
Missing forecast_model_pack -> not sample-quality.
Missing valuation_pack / market_snapshot -> not sample-quality.
Missing technical_market_pack.as_of_date -> no trading-state language.
Missing risk_counterevidence_pack -> fail R5 quality gate.
```

## 6. Prohibited in B5-lite

```text
No external data acquisition.
No real forecast calculation.
No real valuation calculation.
No R5 report-note prose generation.
No modification of reports/workflow_runs/ historical outputs.
No conversion of TODO / MISSING_DISCLOSURE into facts.
No direct trading instruction, position sizing, or guaranteed-return language.
```
