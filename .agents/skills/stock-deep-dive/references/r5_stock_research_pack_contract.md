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

## Required / optional / blocked fields by subpack

| Subpack | Required fields | Optional fields | Blocked when |
|---|---|---|---|
| `company_identity_pack` | `company_id`, `legal_name`, `stock_code`, `exchange`, `identity_evidence_ids` | headquarters, primary industry, business summary | identity is ambiguous or no accepted source exists |
| `evidence_snapshot_pack` | `as_of_date`, evidence counts, official filing status, `critical_missing_sources` | manifest paths, parse quality notes | no evidence manifest or no explicit missing reason |
| `financial_history_pack` | 3 annual periods or gaps, latest quarter/interim or gap, revenue, profit, cash flow, abnormal items | ROE/ROIC bridge, turnover, leverage | metrics lack source or missing reason |
| `business_breakdown_pack` | business lines, revenue/gross margin/gross profit fields or gaps, confidence | products, customers, capacity, orders | company total is used as business-line proof |
| `segment_exposure_pack` | exposure type, confidence, evidence or missing reason, backflow decision | exposure score, linked segment notes | product clues are promoted into revenue/profit exposure without review |
| `industry_context_pack` | demand, supply, price/margin mechanism, competition, company position or gaps | policy/cycle notes | industry context is used to prove company facts |
| `peer_comparison_pack` | peer selection method, peer set or gap, snapshot path or gap | peer financial/valuation context | peer data lacks `as_of_date` or source |
| `forecast_model_pack` | `2026E`/`2027E`/`2028E`, scenario status, assumptions or gaps | sensitivity, consensus comparison | real forecast values lack assumptions/source |
| `valuation_pack` | market snapshot or gap, peer context or gap, method applicability | SOTP/DCF/relative scenarios | market snapshot is missing but sample-quality is claimed |
| `technical_market_pack` | `as_of_date` for state language, MA fields or gaps | support/resistance observations | technical content becomes an action instruction |
| `sentiment_event_pack` | `as_of_date`, macro/industry/company sentiment or gaps, catalyst calendar or gaps | fund-flow or analyst-view sidecars | news/social clues prove financial facts |
| `risk_counterevidence_pack` | risks, counterevidence, falsification conditions, monitoring metrics or gaps | issue severity mapping | thesis has no risk/counterevidence path |

## Traceability fields

Material fields must carry at least one of:

```text
source_evidence_id
evidence_id
metric_id
claim_id
assumption_id
scenario_id
source_path
missing_reason
```

Use `source_evidence_id` for the disclosure or source record, `metric_id` for reviewed structured metrics, `claim_id` for reviewed claims, and `assumption_id` for forecast/valuation assumptions. If none exists, preserve `missing_reason` and add the item to `source_gap_register`.

## Claim type and uncertainty fields

Every material conclusion-bearing object should expose:

```yaml
claim_type: fact | estimate | inference | management_comment | analyst_view | opinion | unknown
confidence: high | medium | low | not_assessed | blocked
review_status: reviewed | candidate | TODO | MISSING | blocked
```

Facts require official disclosure or reviewed evidence. Estimates and assumptions require their model input or explicit TODO. Opinions and analyst views cannot be promoted into facts.

## R4 to R5 mapping

| R4 `stock_analysis_pack.yaml` field | R5 target |
|---|---|
| `metadata`, `company_identity` | `company_identity_pack`, `metadata` |
| `evidence_snapshot` | `evidence_snapshot_pack` |
| `financial_quality`, financial metric sidecars | `financial_history_pack` |
| `business_breakdown` | `business_breakdown_pack` |
| `linked_segments`, `segment_exposure.yaml` | `segment_exposure_pack` |
| `industry_context_card` | `industry_context_pack` |
| `peer_context`, peer snapshots | `peer_comparison_pack` |
| `forecast_assumptions`, `forecast_model.yaml` | `forecast_model_pack` |
| `valuation_context`, company-valuation outputs | `valuation_pack` |
| `technical_snapshot`, market snapshots | `technical_market_pack` |
| `sentiment_pack`, `catalyst_calendar` | `sentiment_event_pack` |
| `risk_counter_evidence` | `risk_counterevidence_pack` |
| `source_gap_requests`, open questions | `source_gap_register`, `report_composition_pack` |

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

Canonical external output labels:

```text
R5_sample_quality_ready
R5_research_draft
R5_source_gapped_draft
blocked
```

Mapping from pack state to external label:

| Condition | External label |
|---|---|
| all required subpacks ready, no high issues, no-advice passed | `R5_sample_quality_ready` |
| core identity/evidence are present but forecast/valuation/market gaps remain | `R5_research_draft` |
| key financial/business/evidence fields are missing but visible | `R5_source_gapped_draft` |
| identity/evidence/no-advice/source-gap visibility fails | `blocked` |

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

`source_gap_register` should include:

```yaml
source_gap_register:
  - gap_id: R5_GAP_001
    section: valuation
    missing_data: market_snapshot.current_price
    impact_on_conclusion: sample_quality_not_allowed
    fix_owner_skill: evidence-ingest
    next_action: register reviewed market snapshot or keep TODO_MARKET_DATA
```

## Market and trading-state boundary

`technical_market_pack` may support market state language only when it has an `as_of_date`. Market, peer, and technical context never prove business exposure.

The pack must not contain direct trading instructions, target-price instructions, position sizing, or guaranteed-return language.

## Quality-review handoff

Hand off these fields to `quality-review`:

```text
pack_path
pack_schema_version
allowed_report_level
r5_external_state
high_issue_count
medium_issue_count
source_gap_register
known_blockers
forecast_gap_status
valuation_gap_status
business_breakdown_gap_status
market_snapshot_gap_status
no_advice_gate_input
owner_next_actions
```

The handoff must say whether the run is `R5_sample_quality_ready`, `R5_research_draft`, `R5_source_gapped_draft`, or `blocked`. A high severity issue blocks `R5_sample_quality_ready`.

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
