# Market, Sentiment and Event Contract

## 1. Purpose

This contract supports the technical analysis, sentiment analysis and event-driven sections of a sample-quality report.

## 2. Technical snapshot schema

```yaml
technical_snapshot:
  as_of_date:
  price:
  ma:
    ma5:
    ma10:
    ma20:
    ma60:
    ma120:
  high_low:
    high_52w:
    low_52w:
    recent_high:
    recent_low:
  volume_turnover:
    turnover_rate:
    amount:
    volume:
  trend_state: uptrend | downtrend | range | overheated | oversold | insufficient_data
  support_resistance:
    support: []
    resistance: []
  metric_ids: []
```

## 3. Sentiment pack schema

```yaml
market_sentiment_pack:
  as_of_date:
  macro:
    summary:
    indicators: []
  industry_theme:
    summary:
    indicators: []
    clues: []
  company:
    summary:
    indicators: []
    clues: []
  sentiment_state: cold | warming | hot | euphoric | panic | mixed | insufficient_data
```

## 4. Catalyst calendar schema

```yaml
catalyst_calendar:
  events:
    - event_id:
      date_or_window:
      event_name:
      event_type: earnings | shareholder_meeting | mna | policy | product | capacity | lockup | index | macro | other
      affected_variables: []
      expected_case:
      upside_case:
      downside_case:
      evidence_id_or_clue_id:
      confidence:
```

## 5. Source policy

```text
- Technical data must be dated.
- Sentiment clues must not become facts.
- Event dates must come from official announcements, exchange calendars, regulatory rules, or be marked as estimate.
- Macro views must not dominate company evidence.
```
