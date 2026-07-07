# R5 Research Pack Output Contract

## 1. Path

```text
reports/workflow_runs/<workflow_id>/R5_stock_research_pack.yaml
```

Example asset for B5-lite:

```text
.agents/skills/stock-deep-dive/assets/r5_stock_research_pack.example.yaml
```

## 2. Required top-level keys

```text
schema_version
artifact_type
status
as_of_date
workflow_id
stock
quality_status
source_gap_policy
company_identity_pack
evidence_snapshot_pack
financial_history_pack
business_breakdown_pack
segment_exposure_pack
industry_context_pack
peer_comparison_pack
forecast_model_pack
valuation_pack
technical_market_pack
sentiment_event_pack
risk_counterevidence_pack
report_composition_pack
```

## 3. Status enums

Pack status:

```text
TODO
partial
ready
blocked
```

Report level:

```text
not_assessed
source_gapped_draft
research_draft
sample_quality_ready
blocked
```

## 4. Missing-value tokens

Use explicit tokens such as `MISSING_DISCLOSURE`, `TODO_SOURCE_REQUIRED`, `TODO_MODEL_INPUT`, `TODO_MARKET_DATA`, `TODO_PEER_DATA`, `NOT_APPLICABLE`, and `LOW_CONFIDENCE_CLUE_ONLY`.

If `value: null`, a nearby `missing_reason`, `missing_items`, or source-gap entry must explain why.

## 5. B5-lite forecast / valuation boundary

Legal placeholders:

```yaml
forecast_model_pack:
  status: TODO
  scenarios:
    base_case:
      status: TODO_MODEL_INPUT

valuation_pack:
  status: TODO
  market_snapshot:
    missing_reason: TODO_MARKET_DATA
```

Illegal outputs include unsupported 2026E-2028E forecasts, remembered market data, peer multiples without source, target prices, trading instructions, and position sizing.

## 6. Validation

```bash
python .agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py \
  .agents/skills/stock-deep-dive/assets/r5_stock_research_pack.example.yaml

python -m pytest tests/test_validate_r5_stock_research_pack.py
```
