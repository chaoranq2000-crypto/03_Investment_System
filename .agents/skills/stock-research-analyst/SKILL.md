---
name: stock-research-analyst
description: 个股研究分析与建模。当 evidence-ingest 已生成证据、claim/metric candidates 或 reviewed claims/metrics 后，用于生成 business breakdown、financial quality、linked segments、forecast、valuation、technical/sentiment/event packs 和 stock_analysis_pack。不得用于下载证据或写最终研报正文。
---

# Stock Research Analyst Skill

## Goal

Transform reviewed evidence assets into a structured `stock_analysis_pack.yaml` that can support sample-quality stock report writing.

This skill does analysis and modeling, not evidence acquisition and not final prose writing.

## Inputs

Required:

```yaml
run_id:
stock_code:
stock_name:
company_id:
evidence_snapshot:
reviewed_claims:
reviewed_metrics:
metric_candidates:
claim_candidates:
```

Optional:

```yaml
linked_segments_hint:
segment_taxonomy:
peer_list:
industry_context_sources:
market_snapshot:
technical_snapshot:
sentiment_snapshot:
existing_segment_exposure:
```

## Responsibilities

1. Confirm company identity and research scope.
2. Build financial quality analysis from metrics.
3. Build business breakdown from reviewed claims and annual report tables.
4. Discover linked segments and classify exposure type.
5. Create a minimal industry context card.
6. Build three-year forecast assumptions.
7. Build valuation scenarios and peer comparison.
8. Build technical / sentiment / event packs if data exists.
9. Generate evidence_gap_requests when missing evidence blocks analysis.
10. Output `stock_analysis_pack.yaml` and component files.

## Out of scope

Do not:

```text
- Download or parse PDFs.
- Register evidence.
- Promote candidates to registry without quality review.
- Write final report prose.
- Produce buy/sell/hold recommendations or trading instructions.
- Invent missing business revenue, customer, order or capacity figures.
```

## Workflow

```text
A0 Intake
A1 Financial quality
A2 Business breakdown
A3 Segment exposure discovery
A4 Minimal industry context
A5 Forecast model
A6 Valuation model
A7 Technical / sentiment / event analysis
A8 Risk and counter-evidence
A9 Evidence gap requests
A10 Output analysis pack
```

## Output contract

Write under the workflow run folder:

```text
stock_analysis_pack.yaml
financial_quality.yaml
business_breakdown.yaml
segment_exposure_draft.yaml
industry_context_card.yaml
forecast_model.yaml
valuation_model.yaml
peer_comparison.csv
technical_snapshot.yaml
market_sentiment_pack.yaml
catalyst_calendar.yaml
risk_counter_evidence.yaml
evidence_gap_requests.yaml
```

## Handoff

Next skill: `stock-report-writer`.

Pass only:

```text
stock_analysis_pack.yaml
component yaml/csv files
reviewed claim/metric ids
evidence_gap_requests.yaml
```

## Quality checklist

- [ ] Every material business line has evidence or explicit MISSING.
- [ ] Segment exposure does not rely only on structured financial snapshots.
- [ ] Forecast assumptions are separated from facts.
- [ ] Valuation uses dated market data and peer table.
- [ ] Industry context has at least demand / supply / company position / key indicators.
- [ ] Missing inputs create evidence_gap_requests.
- [ ] No buy/sell/hold language.
