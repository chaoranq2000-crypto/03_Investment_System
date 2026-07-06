# Report Production Profile — stock-deep-dive reference

## Positioning

This profile defines how `stock-deep-dive` turns reviewed evidence and data-layer context into a sample-quality stock research report.

It is not a global workflow.

```yaml
profile_id: stock_report_production
parent_workflow_type: stock_first_closed_loop
quality_target: R4_readiness_draft | R3_sample_quality_draft
entry_skill: research-orchestrator
primary_execution_skill: stock-deep-dive
quality_skill: quality-review
primary_subject: single_stock
```

Global workflow stages, workflow types, gate IDs, and backflow decisions are defined only in:

```text
docs/workflows/RESEARCH_WORKFLOW.md
```

## Current production route

```text
research-orchestrator
→ evidence-ingest
→ stock-deep-dive
→ segment-company-mapping
→ quality-review
→ research-orchestrator close readout
```

## Local production steps

These local step IDs are profile steps, not global stage IDs.

```text
RPP-0 Intake & Scope
RPP-1 Evidence Plan
RPP-2 Evidence Acquire & Parse
RPP-3 Candidate Generation
RPP-4 Candidate Review / Promotion
RPP-5 Analysis Pack Build
RPP-6 Forecast & Valuation Model
RPP-7 Technical / Sentiment / Event Pack
RPP-8 Report Draft
RPP-9 Quality Review Handoff
RPP-10 Backflow & Maintenance
RPP-11 Close Readout Inputs
```

## RPP-0 Intake & Scope

Expected input:

```yaml
stock_code:
stock_name:
exchange:
company_id:
report_quality_target: R1 | R2 | R3 | R4
linked_segments_hint: []
date_range:
existing_workflow_run:
```

Expected output:

```text
workflow_state.yaml
company_identity.yaml
scope_card.yaml
```

Must confirm:

- security code and company entity are unique;
- evidence snapshot exists or explicit TODO exists;
- segment exposure exists or linked segment discovery is required;
- target quality is R1/R2/R3/R4.

## RPP-1 Evidence Plan

`evidence-ingest` prepares `stock_evidence_plan.yaml`.

Minimum evidence package:

1. latest annual report PDF or explicit TODO;
2. latest interim / quarterly report or explicit TODO;
3. material announcements in the target date range;
4. financial statements and structured metrics;
5. market, valuation, and technical snapshots when available;
6. investor relations, company website, and news clues when needed;
7. industry source or mini industry context card, or explicit TODO.

Missing evidence must become `evidence_gap_request`:

```yaml
evidence_gap_request:
  gap_id:
  target_section:
  missing_claim_or_metric:
  required_source_type:
  preferred_source_name:
  search_hint:
  blocking_level: high | medium | low
  owner_skill: evidence-ingest
```

## RPP-2 Evidence Acquire & Parse

Official filings should flow through the repository's evidence-ingest and data-layer contracts.

Structured API data is metric/context only by default. It must not support business exposure claims without official disclosure evidence.

Market, sentiment, and event clues may enter:

```text
clue_log.csv
market_snapshot.csv
sentiment_snapshot.csv
event_candidates.csv
```

They must not directly become report facts.

## RPP-3 Candidate Generation

Generate candidates such as:

```text
claim_candidates.csv
metric_candidates.csv
table_inventory.csv
business_line_candidates.csv
segment_exposure_candidates.yaml
evidence_gap_requests.yaml
```

Priority extraction areas:

- MD&A / operating discussion;
- revenue by product / industry / region;
- production, sales, capacity, projects, fundraising projects;
- top customers / suppliers;
- major contracts and framework agreements;
- R&D projects, patents, technology routes;
- risk factors;
- management comments on industry and outlook.

## RPP-4 Candidate Review / Promotion

Candidate promotion rules:

```text
claim_candidates.csv -> reviewed_claims.csv / claims_registry.csv
metric_candidates.csv -> reviewed_metrics.csv / metrics_registry.csv
```

Promotion requires:

- existing `evidence_id`;
- traceable quote, excerpt, page number, or table cell locator;
- matching `source_rank` and `claim_type`;
- no material claim supported only by D-level clues;
- explicit `estimate` / `inference` labels.

## RPP-5 Analysis Pack Build

`stock-deep-dive` uses reviewed claims, reviewed metrics, accepted estimates, and data-layer context to produce:

```text
reports/workflow_runs/<workflow_id>/stock_analysis_pack.yaml
reports/workflow_runs/<workflow_id>/industry_context_card.yaml
reports/workflow_runs/<workflow_id>/business_breakdown.yaml
reports/workflow_runs/<workflow_id>/financial_quality.yaml
reports/workflow_runs/<workflow_id>/risk_counter_evidence.yaml
```

`stock_analysis_pack.yaml` is the only upstream source for report drafting.

Do not let report writing discover new material facts.

## RPP-6 Forecast & Valuation Model

Expected outputs:

```text
forecast_model.yaml
valuation_model.yaml
peer_comparison.csv
sensitivity_table.csv
```

Minimum requirements:

- 2026E / 2027E / 2028E assumptions or explicit TODO;
- revenue, gross margin, expense ratio, net profit, EPS assumptions;
- base / bull / bear scenario or explicit gap;
- most sensitive variable;
- peer valuation table;
- every forecast labeled `estimate` or `inference`.

## RPP-7 Technical / Sentiment / Event Pack

Expected outputs:

```text
technical_snapshot.yaml
market_sentiment_pack.yaml
catalyst_calendar.yaml
```

Required fields when data exists:

- data date;
- current price and valuation snapshot;
- moving average or trend indicator;
- support / resistance methodology;
- turnover, value traded, or flow data when available;
- industry / theme sentiment clues;
- next 1-3 month catalyst calendar.

If market data is missing, keep TODO. Do not write unsupported technical or sentiment conclusions.

## RPP-8 Report Draft

Use:

```text
stock_analysis_pack.yaml
assets/stock_deep_dive_report_template.md
references/report_style_guide.md
references/report_production_profile.md
```

Expected outputs:

```text
stock_deep_dive_draft.md
report_evidence_map.md
report_open_questions.md
writer_gap_requests.yaml
```

The draft should include:

1. metadata;
2. intro / core research line;
3. financial overview;
4. business breakdown;
5. industry context;
6. forecast assumptions;
7. valuation context;
8. technical context if supported;
9. sentiment context if supported;
10. catalyst calendar;
11. conclusion, risks, counter-evidence, tracking list;
12. evidence map;
13. open questions / evidence gaps.

No buy/sell/hold wording, no position sizing, no direct trading instruction.

## RPP-9 Quality Review Handoff

Hand off to `quality-review` using the global gates in `RESEARCH_WORKFLOW.md`.

Stock-report-specific checks should be represented as subchecks under the global stock report gate.

Suggested subchecks:

```yaml
- subcheck_id: G7-DL
  parent_gate_id: G7
  name: Data Layer Pack Check
- subcheck_id: G7-R4
  parent_gate_id: G7
  name: R4 Publishable Stock Report Check
```

Final quality outcomes:

```text
bridge_only
publishable_ready_with_disclosure_todos
publishable_ready
blocked
```

Any high severity issue blocks acceptance.

## RPP-10 Backflow & Maintenance

Backflow or no-backflow reason must be explicit.

Possible target files:

```text
segment_company_exposure.csv
claims_registry.csv
metrics_registry.csv
watchlist_notes.md
reports_to_refresh.yaml
refresh_log.md
```

Rules:

- exposure update requires reviewed claim, reviewed metric, or accepted TODO;
- forecast / valuation does not become a fact;
- clue-level data does not become a claim;
- report status and evidence status must be updated.

## RPP-11 Close Readout Inputs

The orchestrator close readout should be able to report:

```yaml
run_id:
stock_code:
quality_target:
final_status:
evidence_count:
reviewed_claims:
reviewed_metrics:
open_gaps:
high_issues:
medium_issues:
backflow_decision:
next_run_recommendation:
```
