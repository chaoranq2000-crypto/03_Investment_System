# R5 Stock Research Pack Contract

## Purpose

`R5_stock_research_pack.yaml` is the structured source artifact for an R5 stock research note. It is a fact and gap carrier, not a report draft.

Report writers may translate this pack into prose only after the pack and issue list are reviewed. They must not invent missing forecast, valuation, business breakdown, market, sentiment, catalyst, or exposure facts.

## Canonical path

```text
reports/workflow_runs/<workflow_id>/R5_stock_research_pack.yaml
```

Reusable examples:

```text
templates/r5_stock_research_pack.yaml
.agents/skills/stock-deep-dive/assets/r5_stock_research_pack.example.yaml
```

## Required core subpacks

The validator treats these 12 subpacks as the R5 core:

```text
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
```

`report_composition_pack` is also required for writer handoff, but it is not counted as one of the 12 core research subpacks.

## Status values

Pack status:

```text
TODO
partial
ready
blocked
```

Allowed report level:

```text
not_assessed
source_gapped_draft
research_draft
sample_quality_ready
blocked
```

`sample_quality_ready` is forbidden unless `forecast_model_pack`, `valuation_pack`, and `business_breakdown_pack` are all `ready`, `high_issue_count == 0`, and `no_advice_gate_passed == true`.

## Source-gap policy

Missing or unavailable fields must remain visible through tokens such as:

```text
MISSING_DISCLOSURE
TODO_SOURCE_REQUIRED
TODO_MODEL_INPUT
TODO_MARKET_DATA
TODO_PEER_DATA
NOT_APPLICABLE
LOW_CONFIDENCE_CLUE_ONLY
```

If a metric value is `null`, the nearby object must carry `missing_reason`, `missing_items`, or another explicit source-gap explanation.

## Market and trading-state boundary

`technical_market_pack` may support market state language only when it has an `as_of_date`. Market, peer, and technical context never prove business exposure.

The pack must not contain direct trading instructions, target-price instructions, position sizing, or guaranteed-return language.

## Validation

Run:

```bash
python .agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py --pack templates/r5_stock_research_pack.yaml
python .agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py --pack .agents/skills/stock-deep-dive/assets/r5_stock_research_pack.example.yaml
```

The validator outputs one of:

```text
accepted
accepted_with_todos
needs_fix
blocked
```
