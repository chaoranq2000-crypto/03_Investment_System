# TASK 04 — Build Stock Analysis Pack

## Goal

Implement builders that convert reviewed claims and metrics into stock_analysis_pack.yaml and component files.

## Files to create or modify

```text
src/research/stock_analysis_pack_builder.py
src/research/business_breakdown_builder.py
src/research/financial_quality_builder.py
src/research/forecast_model_builder.py
src/research/valuation_model_builder.py
src/research/event_calendar_builder.py
tests/test_stock_analysis_pack_builder.py
```

## Inputs

```text
claims_registry.csv
metrics_registry.csv
segment_taxonomy.yaml
stock_evidence_plan.yaml
technical_snapshot.yaml
market_sentiment_pack.yaml
```

## Outputs

```text
stock_analysis_pack.yaml
financial_quality.yaml
business_breakdown.yaml
segment_exposure_draft.yaml
industry_context_card.yaml
forecast_model.yaml
valuation_model.yaml
peer_comparison.csv
catalyst_calendar.yaml
risk_counter_evidence.yaml
evidence_gap_requests.yaml
```

## Acceptance criteria

```text
- Missing business revenue is represented as MISSING_DISCLOSURE.
- Forecast assumptions have supporting ids or TODO.
- Segment exposure score >=4 requires strong evidence.
- Industry context can be minimal but must exist for R3.
```
