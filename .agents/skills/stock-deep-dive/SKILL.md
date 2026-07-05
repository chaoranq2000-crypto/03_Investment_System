---
name: stock-deep-dive
description: A股个股深度研究统一入口；当用户要求个股研究、个股深度、股票分析、业务/财务/估值/风险/催化剂/linked_segments/segment_exposure/报告草稿时使用。不要用于完整细分研究或 P2 横向比较。
---

# Stock Deep Dive Skill

## Goal

`stock-deep-dive` is the single active stock research entry point.
It consolidates the former analysis-pack layer and report-writing layer into one
workflow that turns reviewed evidence and data-layer outputs into:

- `stock_analysis_pack.yaml`
- a stock deep dive report draft
- `segment_exposure.yaml`
- `backflow_decision`
- a quality-review handoff package

The skill is evidence-first. Reports are derived artifacts, not the source of
truth. It must preserve evidence gaps instead of smoothing them away.

## Use when

Use this skill when the user asks for:

- A-share stock deep dive or company research.
- Business breakdown, financial quality, forecast assumptions, valuation context,
  technical snapshot, sentiment, catalyst calendar, risks, or counter-evidence.
- `linked_segments`, `segment_exposure`, or stock-to-segment backflow.
- A stock report draft based on already registered evidence and metrics.

## Do not use when

Do not use this skill for:

- Full segment research.
- P2 segment or stock comparison.
- Evidence acquisition, web download, live API execution, or source adapter work.
- Claim promotion without quality-review.
- Scorecard/watchlist output as a trading signal.
- Any buy/sell/hold/rating instruction, position sizing, or direct trading action.

## Inputs

Expected inputs may include:

- `stock_code`, `company_name`, `company_id`, `exchange`
- `workflow_id`
- `evidence_manifest` rows
- `claim_candidates` or `claims_registry`
- `metric_candidates` or `metrics_registry`
- data-layer packs
- optional `linked_segments`
- optional prior `segment_exposure.yaml`
- optional report depth: `bridge`, `internal_draft`, `publishable_candidate`

## Integrated workflow

### SDD-0 Company identity gate

Confirm:

- `stock_code`
- `company_id`
- `company_name`
- `exchange`
- report object and workflow object

Block the run if identity is ambiguous, duplicated, or inconsistent across inputs.

### SDD-1 Evidence and data-layer gate

Consume evidence-ingest and data-layer outputs.

Rules:

- Use structured data only as metric/context unless an official disclosure source
  also supports the business claim.
- Do not use Tushare/Baostock/API snapshots as business exposure proof.
- Do not infer customer, order, capacity, revenue exposure, or profit exposure
  from company-level financial metrics alone.
- Preserve `MISSING_DISCLOSURE`, `TODO_SOURCE_REQUIRED`, and source gaps.
- Material claims must carry `evidence_id`, `claim_id`, `metric_id`, or explicit
  TODO / missing reason.

### SDD-2 Analysis pack build

Produce `stock_analysis_pack.yaml`.

The pack should include:

- `metadata`
- `company_identity`
- `evidence_snapshot`
- `financial_quality`
- `business_breakdown`
- `linked_segments`
- `industry_context_card`
- `forecast_assumptions`
- `valuation_context`
- `peer_context`
- `technical_snapshot`
- `sentiment_pack`
- `catalyst_calendar`
- `risk_counter_evidence`
- `source_gap_requests`

Rules:

- Estimates, assumptions, and analyst views must be explicitly labeled.
- Management comments must not be promoted to facts unless supported by official
  disclosure or accepted claim review.
- Business line revenue, gross margin, customer, product, capacity, and order
  fields may be `MISSING`; never invent them.

### SDD-3 Report drafting

Use:

- `assets/stock_deep_dive_report_template.md`
- `references/report_style_guide.md`

Produce an R4 / stock deep dive draft from `stock_analysis_pack.yaml`.

Rules:

- Do not discover new facts during writing.
- Do not hide evidence gaps.
- Keep fact / estimate / inference / opinion separated.
- Include risks, counter-evidence, open questions, evidence map, and source gaps.
- no buy/sell/hold, no position sizing, no direct trading instruction.

### SDD-4 Segment exposure and backflow

Produce or update `segment_exposure.yaml`.

Generate exactly one `backflow_decision` for each material segment issue:

- `update_exposure`
- `update_company_universe`
- `update_segment_taxonomy`
- `update_scorecard`
- `no_backflow_needed`
- `blocked`

Exposure rules:

- `product_line_clue` may update product exposure only.
- `product_line_clue` must not be promoted into revenue exposure or profit
  exposure.
- `revenue_pct` and `profit_pct` must be `MISSING_DISCLOSURE` unless directly
  disclosed or accepted by quality-review from an official source.
- Customer, order, capacity, or project clues must remain clue-level unless the
  source and review status allow a stronger claim.

### SDD-5 Quality-review handoff

Hand off to `quality-review` for at least:

- G1 Evidence Gate
- G2 Claim Gate
- G3 Metric Gate
- G6 Exposure Gate
- G7 Stock Report Gate
- G8 Backflow Gate
- G9 No Advice Gate

The final gate status must be one of:

- `bridge_only`
- `publishable_ready_with_disclosure_todos`
- `publishable_ready`
- `blocked`

Any high severity issue blocks acceptance. Medium TODOs may be accepted only if
they remain visible and do not alter the report's truthfulness.

## Must-read references

Read these references before executing a stock run:

- `references/data_layer_pack_consumption.md`
- `references/publishable_stock_report_gate.md`
- `references/analysis_pack_contract.md`
- `references/business_breakdown_contract.md`
- `references/forecast_valuation_contract.md`
- `references/market_sentiment_event_contract.md`
- `references/report_style_guide.md`

## Outputs

Write workflow-run artifacts to:

```text
reports/workflow_runs/<workflow_id>/
```

Expected artifacts:

- `stock_analysis_pack.yaml`
- `stock_deep_dive_draft.md` or `R4_stock_deep_dive_v*.md`
- `segment_exposure.yaml`
- `evidence_map.md`
- `source_gap_report.md`
- `open_questions.md`
- `quality_gate_report.md`
- `workflow_readout.md`

If the workflow allows canonical stock output, also write:

```text
reports/stocks/<stock_code>_<company_name>/<date>_stock_deep_dive.md
reports/stocks/<stock_code>_<company_name>/segment_exposure.yaml
reports/stocks/<stock_code>_<company_name>/evidence_map.md
```

## Acceptance checklist

Before closing a run, confirm:

- Company identity is unambiguous.
- Evidence and data-layer inputs are registered.
- `stock_analysis_pack.yaml` exists.
- Report draft does not introduce uncited material claims.
- `segment_exposure.yaml` exists or a blocked/no_backflow explanation is written.
- `backflow_decision` is explicit.
- `MISSING_DISCLOSURE` and `TODO_SOURCE_REQUIRED` are visible.
- There is no buy/sell/hold, rating instruction, position sizing, or direct
  trading instruction.
- Quality-review status is recorded.
