# Stock Analysis Pack Contract

## 1. Purpose

`stock_analysis_pack.yaml` is the single structured input for sample-quality report writing.

Report writer must not independently discover new facts. If a fact is missing from this pack, it should ask for an evidence gap, not invent it.

## 2. Top-level schema

```yaml
metadata:
  run_id:
  stock_code:
  stock_name:
  company_id:
  analysis_date:
  quality_target:
  evidence_snapshot:
  claim_ids: []
  metric_ids: []

core_thesis:
  one_sentence:
  facts: []
  inferences: []
  key_assumptions: []
  largest_uncertainties: []

financial_quality:
  summary:
  income_statement:
  cashflow:
  balance_sheet:
  ratios:
  non_recurring_adjustments:
  red_flags: []

business_breakdown:
  business_lines: []
  segment_links: []
  missing_disclosures: []

industry_context:
  linked_segments: []
  demand_drivers: []
  supply_competition: []
  value_chain_position:
  key_indicators: []

forecast_model:
  periods: [2026E, 2027E, 2028E]
  revenue_forecast: []
  margin_forecast: []
  net_profit_forecast: []
  key_assumptions: []
  sensitivity: []

valuation_model:
  source_skill: company-valuation
  valuation_request_path:
  valuation_model_path:
  valuation_snapshot_path:
  valuation_section_draft_path:
  peer_comparison_path:
  sensitivity_table_path:
  valuation_gap_requests_path:
  input_status:
    forecast_model:
    market_data:
    peer_data:
    official_metric_support:
  static_valuation: {}
  dynamic_valuation: {}
  peer_comparison: {}
  scenarios: {}
  sensitivity: []
  conclusion_boundary:
    claim_type: inference
    no_advice_boundary: true
    valuation_context_label: below_peer_median | inline_with_peers | above_peer_median | not_assessable
  gaps: []

technical_sentiment_event:
  technical_snapshot:
  macro_sentiment:
  industry_sentiment:
  company_sentiment:
  catalyst_calendar:

risks_and_counter_evidence:
  risks: []
  counter_evidence: []
  falsification_conditions: []
  tracking_items: []

evidence_gaps: []
```

## 3. Material conclusion rule

Every item in these fields must carry ids:

```yaml
required_id_fields:
  facts: claim_ids or metric_ids
  financial_quality: metric_ids
  business_lines: claim_ids and metric_ids
  segment_links: claim_ids or evidence_gap_id
  forecast_assumptions: supporting_claim_ids / supporting_metric_ids
  valuation: supporting_metric_ids / peer_source_ids / valuation_model_path / explicit TODO
  catalyst_calendar: evidence_id or clue_id
```

## 4. Missing data representation

Use explicit values:

```yaml
MISSING_DISCLOSURE
TODO_PARSE_REQUIRED
TODO_SOURCE_REQUIRED
NOT_APPLICABLE
LOW_CONFIDENCE_CLUE_ONLY
```

Do not use blank fields for important data.
