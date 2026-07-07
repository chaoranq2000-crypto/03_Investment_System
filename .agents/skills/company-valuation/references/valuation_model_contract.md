# Valuation Model Contract

## 1. Purpose

This contract defines the structured output of `company-valuation` when it is called by `stock-deep-dive`.

`valuation_model.yaml` and `valuation_section_draft.md` are model artifacts. They are not evidence, not promoted claims, and not trading advice.

`company-valuation` expects `stock-deep-dive` to normalize valuation inputs with `.agents/skills/stock-deep-dive/references/valuation_input_enrichment_contract.md` before the sub-skill handoff. Parseable TODO rows are valid inputs when reviewed market, peer, or forecast data is unavailable.

## 2. Input contract

The caller should provide `valuation_request.yaml`:

```yaml
valuation_request:
  workflow_id:
  stock_code:
  company_id:
  stock_name:
  exchange:
  as_of_date:
  quality_target: bridge | internal_draft | publishable_candidate
  caller_skill: stock-deep-dive
  parent_stage: RP6 | SDD-2.5
  no_advice_boundary: true
  input_paths:
    stock_analysis_pack:
    forecast_model:
    financial_metric_pack:
    reviewed_claims:
    reviewed_metrics:
    market_snapshot:
    peer_market_snapshot:
    valuation_input_readiness:
    source_gap_report:
  allowed_methods:
    static_multiples: true
    dynamic_multiples: true
    peer_comparison: true
    scenario_valuation: true
    dcf: conditional
    sotp: conditional
    ddm_or_pb: conditional
    nav_or_resource: conditional
  requested_sections:
    - static_valuation
    - dynamic_valuation
    - peer_comparison
    - scenario_sensitivity
    - valuation_risks
```

## 3. Output contract

### 3.1 `valuation_model.yaml`

```yaml
valuation_model:
  metadata:
    workflow_id:
    stock_code:
    company_id:
    stock_name:
    as_of_date:
    source_skill: company-valuation
    caller_skill: stock-deep-dive
    quality_target:
    no_advice_boundary: true

  input_status:
    forecast_model: ready | partial | todo_forecast_model
    market_data: ready | stale_market_data | todo_market_data
    peer_data: ready | low_confidence_peer_data | todo_peer_data
    official_metric_support: ready | partial | official_missing
    business_segment_support: ready | partial | missing_disclosure

  selected_methods:
    - method_id:
      method_name:
      status: used | skipped | todo
      reason:
      required_inputs:
      missing_inputs:
      confidence: high | medium | low

  static_valuation:
    as_of_date:
    metrics:
      pe_ttm:
      pb:
      ps:
      ev_ebitda:
      dividend_yield:
    source_metric_ids: []
    source_paths: []
    notes:
    confidence:

  dynamic_valuation:
    forecast_periods: [2026E, 2027E, 2028E]
    metrics:
      pe_2026E:
      pe_2027E:
      pe_2028E:
      ev_ebitda_2026E:
      ps_2026E:
    forecast_metric_ids: []
    assumptions_ids: []
    notes:
    confidence:

  peer_comparison:
    peer_table_path:
    peer_set_quality: high | medium | low | todo
    median_metrics:
      pe_ttm:
      pe_2026E:
      pb:
      ps:
      ev_ebitda:
    target_position:
      relative_to_peer_median: below | inline | above | not_assessable
      explanation:
    limitations: []

  scenario_valuation:
    scenarios:
      bear:
        assumptions: {}
        output_range:
        support_ids: []
        uncertainties: []
      base:
        assumptions: {}
        output_range:
        support_ids: []
        uncertainties: []
      bull:
        assumptions: {}
        output_range:
        support_ids: []
        uncertainties: []
    sensitivity_table_path:
    most_sensitive_variable:
    interpretation_boundary:

  dcf_or_other_intrinsic_method:
    method_used: dcf | ddm | nav | resource_ev | skipped
    reason:
    assumptions:
      discount_rate:
      terminal_growth:
      forecast_horizon:
      margin_path:
      reinvestment_or_capex:
    sensitivity_table_path:
    sanity_checks:
      wacc_gt_terminal_growth:
      terminal_value_share:
      cyclicality_adjustment:
    confidence:

  valuation_section:
    draft_path:
    evidence_map_path:
    open_gaps_path:

  quality_handoff:
    path:
    no_advice_boundary: pass | needs_review | fail
    open_gap_count:
    blocking_gap_count:
```

### 3.2 `valuation_snapshot.yaml`

Use for concise market-state snapshot:

```yaml
valuation_snapshot:
  metadata:
    workflow_id:
    stock_code:
    as_of_date:
    generated_by: company-valuation
  market_data:
    current_price:
    market_cap:
    shares_outstanding:
    currency:
    source_path:
    source_metric_ids: []
    freshness_status: fresh | stale | unknown
  multiples:
    pe_ttm:
    pb:
    ps:
    ev_ebitda:
    pe_forward:
  peer_context:
    peer_market_snapshot_path:
    peer_set_quality:
    peer_median_multiples: {}
  model_context:
    forecast_model_path:
    sensitivity_table_path:
    scenario_summary:
      bear:
      base:
      bull:
  labels:
    valuation_context_label: below_peer_median | inline_with_peers | above_peer_median | not_assessable
    confidence: high | medium | low
  gaps: []
```

## 4. Gap request contract

`valuation_gap_requests.yaml`:

```yaml
valuation_gap_requests:
  - gap_id:
    target_section:
    missing_claim_or_metric:
    required_source_type:
    preferred_source_name:
    blocking_level: high | medium | low
    owner_skill: evidence-ingest | stock-deep-dive | data-layer | manual_review
    notes:
```

## 5. CSV output contracts

### 5.1 `peer_comparison.csv`

```csv
peer_company,peer_stock_code,exchange,selection_reason,business_similarity,segment_overlap,market_cap,pe_ttm,pe_2026E,pb,ps,ev_ebitda,as_of_date,metric_source,limitations,confidence
```

### 5.2 `sensitivity_table.csv`

```csv
variable,case_label,delta,output_metric,output_value,impact_vs_base,assumption_type,supporting_metric_ids,supporting_claim_ids,notes
```

## 6. Prohibited schema fields

Do not add these fields:

```text
target_price_instruction
buy_rating
sell_rating
hold_rating
position_size
stop_loss
take_profit
guaranteed_return
```

If legacy inputs include them, move them to `ignored_legacy_fields` and record a no-advice note.

## 7. R5 mini validator output fields

For R5 handoff validation, `valuation_output.yaml` must include:

```yaml
valuation_as_of_date:
input_status: complete | partial_with_todos | blocked
market_snapshot:
peer_set:
method_selection:
scenario_outputs:
  base:
  bull:
  bear:
sensitivity:
source_gap:
no_advice_disclaimer:
```

If market snapshot is missing, `input_status` must not be `complete`.

Each valuation output number must carry `assumption_id` or `missing_reason`.
