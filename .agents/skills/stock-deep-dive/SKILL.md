---
name: stock-deep-dive
description: A股个股深度研究统一入口；当用户要求个股研究、个股深度、股票分析、业务/财务/估值/风险/催化剂/linked_segments/segment_exposure/报告草稿时使用。不要用于完整细分研究或 P2 横向比较。
---

# Stock Deep Dive Skill

## Purpose

`stock-deep-dive` is the single active stock research entry point.

It turns machine-qualified evidence, machine-qualified metrics and data-layer
outputs into:

- `stock_analysis_pack.yaml`
- `R5_stock_research_pack.yaml` when running the R5-MVP research-pack path
- a valuation subagent handoff package when valuation context is required
- `valuation_model.yaml` / `valuation_section_draft.md` from `company-valuation` when valuation context is required
- a stock deep dive report draft
- `segment_exposure.yaml`
- `backflow_decision`
- a quality-review handoff package

Reports are derived artifacts, not the source of truth. This skill must preserve evidence gaps instead of smoothing them away.

## Canonical boundary

This skill does not redefine global workflow interfaces.

Canonical workflow type、global stage、global gate and backflow decision live in:

```text
docs/workflows/RESEARCH_WORKFLOW.md
```

The stock report production profile lives in:

```text
.agents/skills/stock-deep-dive/references/report_production_profile.md
```

## When to use

Use this skill when the user asks for:

- A-share stock deep dive or company research.
- Business breakdown, financial quality, forecast assumptions, valuation context, technical snapshot, sentiment, catalyst calendar, risks, or counter-evidence.
- `linked_segments`, `segment_exposure`, or stock-to-segment backflow.
- A stock report draft based on already registered evidence and metrics.

## Out of scope

Do not use this skill for:

- Full segment research.
- P2 segment or stock comparison.
- Evidence acquisition, web download, live API execution, or source adapter work.
- Claim promotion without quality-review.
- Scorecard / watchlist output as a trading signal.
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
- optional `valuation_request.yaml`
- optional `valuation_model.yaml`
- optional `valuation_snapshot.yaml`
- optional `peer_market_snapshot.csv`
- optional `sensitivity_table.csv`

## Local procedure

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

- Use structured data only as metric/context unless an official disclosure source also supports the business claim.
- Do not use Tushare / Baostock / API snapshots as business exposure proof.
- Do not infer customer, order, capacity, revenue exposure, or profit exposure from company-level financial metrics alone.
- Preserve `MISSING_DISCLOSURE`, `TODO_SOURCE_REQUIRED`, and source gaps.
- Material claims must carry `evidence_id`, `claim_id`, `metric_id`, or explicit TODO / missing reason.
- `reviewed`, `reviewed_claims` and `reviewed_metrics` in retained field or
  filename conventions mean machine-qualified; they never imply human approval.

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

- Estimates, assumptions and analyst views must be explicitly labeled.
- Management comments must not be promoted to facts unless supported by official disclosure or accepted claim review.
- Business line revenue, gross margin, customer, product, capacity and order fields may be `MISSING`; never invent them.

### Conditional R5 report capability

Use the R5 path only when the handoff explicitly requests an R5 research pack,
R5 report, or legacy sample-quality capability. Then read
`references/r5_stock_research_pack_contract.md`,
`references/r5_report_contract.md`, and only the R5 subpack references needed
by that request. Preserve visible gaps and send the resulting pack to
`quality-review` before composition. Ordinary stock runs do not load or require
R5 packs, Bundle generations, Reader artifacts, or legacy report states.

### SDD-2.5 Valuation subagent handoff

When the stock report requires a valuation section, create `valuation_request.yaml` from `assets/valuation_request_template.yaml` and call `company-valuation` as a sub-skill.

Rules:

- `company-valuation` may only consume machine-qualified evidence, claims and
  metrics, plus `forecast_model` and data-layer market / peer snapshots.
- It must not acquire new evidence, fetch live data, promote claims or write direct trading advice.
- Missing market, peer, forecast or official metric inputs must become `TODO_MARKET_DATA`, `TODO_PEER_DATA`, `TODO_FORECAST_MODEL` or `official_missing`.
- `stock-deep-dive` may use `valuation_section_draft.md` to assemble the report, but must not introduce new valuation facts during report writing.
- Valuation outputs do not prove business exposure and must not update `segment_exposure.yaml` by themselves.

Expected inputs:

```text
reports/workflow_runs/<workflow_id>/valuation_request.yaml
reports/workflow_runs/<workflow_id>/stock_analysis_pack.yaml
reports/workflow_runs/<workflow_id>/forecast_model.yaml
reports/workflow_runs/<workflow_id>/financial_metric_pack.csv
reports/workflow_runs/<workflow_id>/peer_market_snapshot.csv or TODO_PEER_DATA
reports/workflow_runs/<workflow_id>/market_snapshot.csv or TODO_MARKET_DATA
```

Expected outputs:

```text
reports/workflow_runs/<workflow_id>/valuation/valuation_model.yaml
reports/workflow_runs/<workflow_id>/valuation/valuation_snapshot.yaml
reports/workflow_runs/<workflow_id>/valuation/peer_comparison.csv
reports/workflow_runs/<workflow_id>/valuation/sensitivity_table.csv
reports/workflow_runs/<workflow_id>/valuation/valuation_section_draft.md
reports/workflow_runs/<workflow_id>/valuation/valuation_gap_requests.yaml
reports/workflow_runs/<workflow_id>/valuation/valuation_quality_handoff.yaml
```

After the sub-skill returns, `stock-deep-dive` must collect and reconcile:

- `valuation_model.yaml`
- `valuation_snapshot.yaml`
- `peer_comparison.csv`
- `sensitivity_table.csv`
- `valuation_section_draft.md`
- `valuation_gap_requests.yaml`
- `valuation_quality_handoff.yaml`

These files are consumed as derived valuation artifacts for report assembly and quality-review handoff. They do not create new facts, stock recommendations, exposure proof, target-price instructions, or position-sizing language.

### SDD-3 Report drafting

Use:

- `assets/stock_deep_dive_report_template.md`
- `references/report_style_guide.md`
- `references/report_production_profile.md`

Read `references/legacy_stock_skill_rules.md` only when an explicit legacy
split-workflow compatibility handoff requires it.

Produce an R4 / stock deep dive draft from `stock_analysis_pack.yaml`.

Rules:

- Do not discover new facts during writing.
- Do not hide evidence gaps.
- Keep fact / estimate / inference / opinion separated.
- Include risks, counter-evidence, open questions, evidence map and source gaps.
- For valuation writing, consume `valuation_section_draft.md` and `valuation_model.yaml` produced by `company-valuation`; do not create new valuation facts in the prose layer.
- No buy/sell/hold, no position sizing, no direct trading instruction.

### SDD-3.5 Final-report review handoff

After the final report bytes are written and automatic report quality has been
computed, hand the report path and machine SHA-256 to the orchestrator. The
only active human boundary is:

```text
final_report_review_status:
  not_requested | pending | approved | changes_requested
```

`pending` binds a repo-relative report path and current machine SHA-256 without
reviewer, time, notes or `change_scope`. `approved|changes_requested` require a
real non-machine reviewer, ISO time and non-empty notes; `decision` equals the
top-level status. `change_scope` is
`automated_quality_defect|report_revision` only for `changes_requested`.

Report byte changes invalidate the old decision. `not_requested|pending` does
not block the automatic workflow or `system_v1_complete`, but
`sample_quality_ready=false`. A valid current `approved` review and all
necessary automated quality conditions are required, but not by themselves
automatically sufficient, for `sample_quality_ready=true`.

Do not request or record human approval for evidence, claims, metrics, fields,
candidates, calculations, research packs, generation locks or receipts. Their
hashes are machine-integrity checks. Historical Bundle/Night/Reader reviewer
authority and exact-hash decisions are read-only and cannot approve this
report.

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
- `product_line_clue` must not be promoted into revenue exposure or profit exposure.
- `revenue_pct` and `profit_pct` must be `MISSING_DISCLOSURE` unless directly
  disclosed or machine-qualified by `quality-review` from an official source.
- Customer, order, capacity, or project clues must remain clue-level unless
  the source and machine-validation status allow a stronger claim.
- A scorecard dimension supported only by placeholder states defined in
  `config/scoring_frameworks.yaml` uses `score: null` and
  `score_type: unscored`; a numeric score is an evidence-bounded
  `analyst_judgment`, never a substitute value for missing disclosure.
- Missing disclosure may open an evidence refresh and reassessment task; it
  does not automatically lower a score, weaken a thesis or invalidate a thesis.
  If it changes confidence, score or thesis strength, state the relevant time
  expectation, disclosure boundary and evidence coverage. Never present absence
  of disclosure as evidence that the business does not exist.

### SDD-5 Quality-review handoff

Hand off to `quality-review` for relevant global gates from `RESEARCH_WORKFLOW.md`:

- G1 Evidence Gate
- G2 Claim Gate
- G3 Metric Gate
- G6 Exposure Gate
- G7 Stock Report Gate
- G8 Backflow Gate
- G9 No Advice Gate

The stock-report capability label must be one of:

- `bridge_only`
- `publishable_ready_with_disclosure_todos`
- `publishable_ready`
- `blocked`

This label does not write canonical `workflow_state.status`. Each issue must
carry `impact_scope`、`active_disposition`、`affected_capabilities` and
`blocks_current_goal`; severity alone never blocks acceptance. Visible TODOs
may be accepted only when they are not used as facts and do not alter the
report's truthfulness.

These labels describe automatic report-production capability and remain
separate from final human review. None of them, including
`publishable_ready`, can by itself yield `R5_sample_quality_ready`.
`not_requested|pending` may leave the automatic workflow accepted or
accepted-with-todos, but sample quality remains false.

## Must-read references

Read these current references before executing an ordinary stock run:

- `references/data_layer_pack_consumption.md`
- `references/publishable_stock_report_gate.md`
- `references/analysis_pack_contract.md`
- `references/business_breakdown_contract.md`
- `references/forecast_valuation_contract.md`
- `references/market_sentiment_event_contract.md`
- `references/report_style_guide.md`
- `references/report_production_profile.md`
- `references/valuation_subagent_handoff.md`

Read these only when the handoff explicitly requests the corresponding
capability:

- R5 pack or report: `references/r5_stock_research_pack_contract.md`,
  `references/r5_report_contract.md`, and the required R5 subpack contracts.
- Legacy operating-evidence or sample-quality evaluation:
  `references/operating_evidence_profile.md` and the relevant retained R5
  evaluator reference.
- Legacy split-workflow compatibility:
  `references/legacy_stock_skill_rules.md`.

If a reference is missing, record a TODO rather than inventing its content.

## Outputs

Write workflow-run artifacts to:

```text
reports/workflow_runs/<workflow_id>/
```

Expected artifacts:

- `stock_analysis_pack.yaml`
- `R5_stock_research_pack.yaml` for R5-MVP runs
- `stock_deep_dive_draft.md` or `R4_stock_deep_dive_v*.md`
- `segment_exposure.yaml`
- `evidence_map.md`
- `source_gap_report.md`
- `open_questions.md`
- `quality_gate_report.md`
- `workflow_readout.md`
- `valuation/valuation_model.yaml`
- `valuation/valuation_snapshot.yaml`
- `valuation/valuation_section_draft.md`
- `valuation/valuation_gap_requests.yaml`
- `valuation/valuation_quality_handoff.yaml`

If the workflow allows canonical stock output, also write:

```text
reports/stocks/<stock_code>/<date>_stock_deep_dive.md
reports/stocks/<stock_code>/segment_exposure.yaml
reports/stocks/<stock_code>/evidence_map.md
```

## Quality checklist

Before closing a run, confirm:

- Company identity is unambiguous.
- Evidence and data-layer inputs are registered.
- `stock_analysis_pack.yaml` exists.
- R5-MVP runs validate `R5_stock_research_pack.yaml` before report composition.
- Report draft does not introduce uncited material claims.
- `segment_exposure.yaml` exists or a blocked / no_backflow explanation is written.
- `backflow_decision` is explicit.
- `MISSING_DISCLOSURE` and `TODO_SOURCE_REQUIRED` are visible.
- No issue decision is derived from severity alone; current-goal scope and
  actual dependency are recorded.
- Valuation section either consumes `company-valuation` outputs or shows visible valuation TODOs.
- No valuation output contains direct buy/sell/hold, target-price instruction, position sizing or guaranteed return.
- There is no buy/sell/hold, rating instruction, position sizing, or direct trading instruction.
- Quality-review status is recorded.
- Intermediate `reviewed` objects are machine-qualified, not human-approved.
- Final report review state and hash binding are valid; pending/not requested
  leaves `sample_quality_ready=false` without blocking automatic close.

## Explicit legacy capability evaluators

If the handoff explicitly requests a retained Bundle/R5 capability evaluator,
read only the corresponding reference and return its capability-local result
to `quality-review`. Otherwise proceed through SDD-0–SDD-5 without loading the
legacy evaluator. Historical reviewer, receipt, generation-lock and local
pass/fail records remain read-only and cannot decide the canonical outcome.
