# Valuation Input Enrichment Contract

## Purpose

`stock-deep-dive` prepares valuation inputs before calling `company-valuation`.
These inputs are handoff artifacts, not investment conclusions and not evidence by themselves.

The contract allows visible `TODO_*`, `MISSING_*`, `LOW_CONFIDENCE_*`, and `not_assessable` values when reviewed data is unavailable. It does not allow guessed market prices, multiples, peer values, net profit forecasts, target prices, or trading instructions.

## Required Files

For each workflow run, `stock-deep-dive` should provide:

```text
reports/workflow_runs/<workflow_id>/market_snapshot.csv
reports/workflow_runs/<workflow_id>/peer_market_snapshot.csv
reports/workflow_runs/<workflow_id>/financial_metric_pack.csv
reports/workflow_runs/<workflow_id>/valuation_input_readiness.yaml
```

If an input cannot be filled, keep a parseable placeholder row or explicit readiness gap rather than replacing the file path with a bare TODO string.

## `market_snapshot.csv`

Required columns:

```csv
stock_code,company_id,stock_name,exchange,as_of_date,currency,close_price,market_cap,free_float_market_cap,shares_outstanding,float_shares,pe_ttm,pe_lyr,pe_forward_2026e,pb_lf,ps_ttm,ev,ev_ebitda_ttm,dividend_yield,turnover_rate,pct_chg_20d,pct_chg_60d,source_name,source_type,source_path,source_evidence_id,source_metric_id,reliability_rank,capture_method,snapshot_status,limitations
```

Rules:

- `snapshot_status: TODO_MARKET_DATA` is valid with blank numeric fields.
- Any ready or stale market value must include `as_of_date`, `currency`, `source_name`, `source_type`, `source_path`, and a source id where available.
- Market fields are valuation context only and cannot prove business exposure.

## `peer_market_snapshot.csv`

Required columns:

```csv
subject_stock_code,subject_company_id,peer_company,peer_stock_code,exchange,peer_selection_reason,business_similarity,segment_overlap,as_of_date,currency,market_cap,pe_ttm,pe_forward_2026e,pe_forward_2027e,pb_lf,ps_ttm,ev_ebitda_ttm,revenue_growth_2026e,net_profit_growth_2026e,roe,gross_margin,source_name,source_type,source_path,source_evidence_id,reliability_rank,confidence,limitations
```

Rules:

- `confidence: todo` or `peer_company: TODO_PEER_DATA` is valid with blank multiple fields.
- Any usable peer row must include a peer selection reason, business similarity label, segment overlap label, source fields, and limitations.
- Peer rows are comparison context only and cannot rank a company unless the source set is dated and reviewed.

## `financial_metric_pack.csv`

Required columns:

```csv
metric_id,company_id,stock_code,metric_name,period,value,unit,currency,source_evidence_id,source_path,calculation_method,claim_type,confidence,review_status,limitations
```

Rules:

- Rows must be derived from reviewed or explicitly candidate metric registries.
- `review_status: reviewed`, `reviewed_r3_candidate`, or `accepted` rows require a metric id, period, unit, source evidence id, source path, calculation method, and limitations.
- Company-level financial metrics do not prove segment exposure.

## `valuation_input_readiness.yaml`

Required root key:

```yaml
valuation_input_readiness:
```

Required fields:

```yaml
valuation_input_readiness:
  workflow_id:
  stock_code:
  company_id:
  as_of_date:
  generated_by: stock-deep-dive
  no_advice_boundary: true
  input_paths:
    market_snapshot:
    peer_market_snapshot:
    financial_metric_pack:
    forecast_model:
    valuation_request:
  statuses:
    market_snapshot:
      status:
      source_paths: []
      source_metric_ids: []
      open_gaps: []
      limitations: []
    peer_market_snapshot:
      status:
      source_paths: []
      source_metric_ids: []
      open_gaps: []
      limitations: []
    financial_metric_pack:
      status:
      source_paths: []
      source_metric_ids: []
      open_gaps: []
      limitations: []
    forecast_model:
      status:
      source_paths: []
      source_metric_ids: []
      open_gaps: []
      limitations: []
  open_gaps: []
```

Statuses may be `ready`, `partial`, `todo_market_data`, `todo_peer_data`, `todo_forecast_model_net_profit`, `missing_disclosure`, `low_confidence_fixture`, or another explicit TODO/MISSING label.

## Validation

Run:

```text
python .agents/skills/stock-deep-dive/scripts/validate_valuation_inputs.py --workflow-run reports/workflow_runs/<workflow_id>
```

The validator writes:

```text
reports/workflow_runs/<workflow_id>/valuation_input_validation.json
reports/workflow_runs/<workflow_id>/valuation_input_validation.md
```

It checks parseability, required columns, identity consistency, future dates, source requirements for ready rows, tolerated TODO placeholders, and no-advice boundaries.
