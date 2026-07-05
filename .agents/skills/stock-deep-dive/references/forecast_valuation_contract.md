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
