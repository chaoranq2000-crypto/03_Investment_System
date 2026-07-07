# Forecast and Valuation Contract

## 1. Forecast model purpose

Forecasting translates reviewed facts and explicit assumptions into 2026E-2028E scenarios.

It must not present estimates as facts.

## 2. Forecast model schema

```yaml
forecast_model:
  base_year:
  forecast_periods: [2026E, 2027E, 2028E]
  segments:
    - segment_or_business_line:
      revenue:
        2026E:
        2027E:
        2028E:
      revenue_growth:
      gross_margin:
      assumptions:
      supporting_claim_ids: []
      supporting_metric_ids: []
      confidence:
  consolidated:
    revenue:
    gross_profit:
    gross_margin:
    operating_profit:
    net_profit_attributable:
    eps:
  sensitivity:
    - variable:
      delta:
      net_profit_impact:
      notes:
  scenario:
    bear:
    base:
    bull:
```

## 3. Forecast requirements

R2 minimum:

```text
- Three-year consolidated revenue and net profit.
- Key assumptions explicitly listed.
- At least one sensitivity variable.
```

R3 minimum:

```text
- Business-line or segment-based forecast.
- Bear/base/bull scenarios.
- Comparison with consensus or historical trend if available.
- EPS and valuation link.
```

## 4. Valuation model schema

```yaml
valuation_model:
  as_of_date:
  market_data:
    price:
    market_cap:
    shares_outstanding:
    pe_ttm:
    pb:
    ps:
  dynamic_valuation:
    pe_2026E:
    pe_2027E:
    pe_2028E:
  peer_comparison:
    peers: []
    peer_metric_table_path:
    premium_discount_reason:
  scenario_valuation:
    bear:
    base:
    bull:
  conclusion:
    valuation_status: low | fair | high | stretched | not_assessable
    reasoning:
    evidence_ids: []
```

## 5. Prohibited outputs

```text
- Do not output direct target-price instruction.
- Do not output position sizing.
- Do not call buy/sell/hold.
- Do not use peer PE without noting period and source.
```

## 6. Company-valuation sub-skill mode

When a valuation section is required, `stock-deep-dive` should create `valuation_request.yaml` and call `company-valuation` as a sub-skill.

### 6.1 Handoff input

```yaml
valuation_request:
  workflow_id:
  stock_code:
  company_id:
  as_of_date:
  caller_skill: stock-deep-dive
  parent_stage: RP6
  no_advice_boundary: true
  input_paths:
    stock_analysis_pack:
    forecast_model:
    financial_metric_pack:
    market_snapshot:
    peer_market_snapshot:
  requested_sections:
    - static_valuation
    - dynamic_valuation
    - peer_comparison
    - scenario_sensitivity
```

### 6.2 Sub-skill outputs

```text
valuation/valuation_model.yaml
valuation/valuation_snapshot.yaml
valuation/peer_comparison.csv
valuation/sensitivity_table.csv
valuation/valuation_section_draft.md
valuation/valuation_gap_requests.yaml
valuation/valuation_quality_handoff.yaml
```

### 6.3 Valuation status labels

Use context labels, not trading labels:

```text
below_peer_median
inline_with_peers
above_peer_median
not_assessable
```

Do not use these labels as direct trading advice.

### 6.4 Missing data rules

```text
TODO_MARKET_DATA     when current market valuation snapshot is unavailable
TODO_PEER_DATA       when peer multiples are unavailable
TODO_FORECAST_MODEL  when dynamic valuation has no forecast model
TODO_SEGMENT_DISCLOSURE when SOTP is requested but segment disclosure is missing
LOW_CONFIDENCE_PEER_SET when peer comparability is weak
```

### 6.5 Additional prohibited outputs

```text
Do not output buy/sell/hold language.
Do not output target-price instruction.
Do not convert scenario ranges into a recommended trading range.
Do not use market valuation context as business exposure proof.
```
