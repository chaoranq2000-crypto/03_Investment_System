---
name: company-valuation
description: A-share Research OS valuation sub-skill used by stock-deep-dive when drafting valuation context, peer comparison, scenario valuation, sensitivity analysis, and valuation section text from reviewed evidence, reviewed metrics, forecast_model and data-layer valuation snapshots. Use only as a stock-deep-dive subagent/sub-skill. Do not use as a standalone price target, buy/sell/hold, live data acquisition, or trading advice skill.
---

# Company Valuation Skill

## Purpose

`company-valuation` converts already-reviewed stock research inputs into a valuation model package and a Chinese valuation-section draft for `stock-deep-dive`.

It is a **sub-skill** of `stock-deep-dive`, not a top-level workflow. It exists to make the valuation section more structured, auditable and reusable.

Expected output:

```text
valuation_model.yaml
valuation_snapshot.yaml
peer_comparison.csv
sensitivity_table.csv
valuation_section_draft.md
valuation_gap_requests.yaml
valuation_quality_handoff.yaml
```

Reports remain derived artifacts. Evidence, claims, metrics and model snapshots remain the source of truth.

## Canonical boundary

Follow these project rules first:

```text
AGENTS.md
docs/workflows/RESEARCH_WORKFLOW.md
docs/policies/EVIDENCE_AND_CITATION_POLICY.md
docs/policies/QUALITY_GUARDRAILS.md
.agents/skills/stock-deep-dive/references/forecast_valuation_contract.md
.agents/skills/stock-deep-dive/references/valuation_subagent_handoff.md
```

This skill must not redefine global workflow types, global gate IDs or backflow decisions.

## When to use

Use this skill when `stock-deep-dive` needs to write or refresh the valuation part of a single-stock research draft, including:

```text
- static valuation context
- dynamic valuation context
- peer valuation comparison
- DCF / DDM / NAV / SOTP scenario context
- WACC / terminal growth / margin / revenue sensitivity
- valuation gap requests
- valuation section draft for the stock report
```

The normal trigger is internal:

```text
stock-deep-dive RP6 / SDD-2.5 → company-valuation → stock-deep-dive report assembly
```

## Out of scope

Do not use this skill for:

```text
- evidence acquisition, web search, API download, yfinance / AkShare / Tushare / Baostock execution
- claim promotion or metric review
- business exposure proof
- segment-company mapping
- complete stock report assembly
- quality gate final decision
- P2 stock comparison
- direct buy / sell / hold / rating / position sizing / target-price instruction
```

If market, peer, forecast or official disclosure inputs are missing, output `TODO_*` / `MISSING_*` gap requests. Do not fill gaps by guessing.

## Inputs

Expected input paths under one workflow run:

```text
reports/workflow_runs/<workflow_id>/stock_analysis_pack.yaml
reports/workflow_runs/<workflow_id>/forecast_model.yaml
reports/workflow_runs/<workflow_id>/financial_metric_pack.csv
reports/workflow_runs/<workflow_id>/valuation_request.yaml
reports/workflow_runs/<workflow_id>/market_snapshot.csv              # optional; else TODO_MARKET_DATA
reports/workflow_runs/<workflow_id>/valuation_snapshot.yaml          # optional existing snapshot
reports/workflow_runs/<workflow_id>/peer_market_snapshot.csv         # optional; else TODO_PEER_DATA
reports/workflow_runs/<workflow_id>/source_gap_report.md             # optional
```

The caller may also pass:

```text
reviewed_claims.csv
reviewed_metrics.csv
claims_registry.csv
metrics_registry.csv
segment_exposure.yaml
business_breakdown.yaml
industry_context_card.yaml
```

## Local procedure

### CV-0 Handoff validation

Read `valuation_request.yaml` and verify:

```text
workflow_id
stock_code
company_id
as_of_date
quality_target
forecast_model_path
financial_metric_pack_path
allowed_methods
requested_sections
no_advice_boundary: true
```

If identity or paths conflict with `stock_analysis_pack.yaml`, stop and output `valuation_gap_requests.yaml` with `blocking_level: high`.

### CV-1 Input sufficiency classification

Classify valuation readiness:

```yaml
valuation_input_status:
  market_data: ready | todo_market_data | stale_market_data
  peer_data: ready | todo_peer_data | low_confidence_peer_data
  forecast_model: ready | partial | todo_forecast_model
  official_metric_support: ready | partial | official_missing
  business_segment_support: ready | partial | missing_disclosure
```

Do not proceed to deterministic valuation writing if a blocking item is missing. In that case, create a visible gap section.

### CV-2 Method selection

Select methods using `references/method_selection.md`.

Default A-share internal research order:

```text
1. Static and dynamic multiple context
2. Peer comparison
3. Scenario valuation from forecast model
4. SOTP only when segment economics are disclosed or reviewed
5. DCF only when FCFF assumptions are supportable
6. DDM / P/B / NAV / EV-resource methods for banks, insurers, REIT-like, resources or asset-heavy companies when appropriate
```

Do not force all methods. Unsupported methods should be skipped with a reason.

### CV-3 Normalize valuation metrics

For every valuation metric, record:

```yaml
metric_name:
period:
value:
unit:
currency:
source_metric_id:
source_evidence_id:
source_path:
as_of_date:
calculation_method:
claim_type: fact | estimate | inference | analyst_view | opinion | unknown
confidence: high | medium | low
```

Market snapshots and peer multiples are market context, not proof of business exposure.

### CV-4 Peer comparison

Build `peer_comparison.csv` only if peer data exists or if a TODO table is explicitly allowed.

Each peer row must include:

```text
peer_company
peer_stock_code
exchange
peer_selection_reason
business_similarity
segment_overlap
market_cap
pe_ttm
pe_forward_period
pb
ps
ev_ebitda
metric_source
as_of_date
limitations
```

If peer comparability is weak, label it `LOW_CONFIDENCE_PEER_SET`.

### CV-5 Scenario and sensitivity

Generate bear / base / bull only as scenarios, not recommendations.

Required scenario fields:

```yaml
scenario_name:
core_assumptions:
  revenue_growth:
  gross_margin:
  net_margin:
  valuation_multiple:
  discount_rate:
  terminal_growth:
output_metrics:
  implied_market_cap_range:
  implied_multiple_range:
  eps_or_profit_anchor:
claim_type: estimate | inference | analyst_view
supporting_metric_ids: []
supporting_claim_ids: []
uncertainties: []
counter_evidence: []
```

Sensitivity tables should identify the most important variable and its impact range. Do not imply a trading action.

### CV-6 Write valuation section draft

Use `assets/valuation_section_template.md`.

The section should normally include:

```text
5.1 静态估值
5.2 动态估值
5.3 同业估值对比
5.4 情景估值与敏感性
5.5 估值分歧、反证与后续验证
```

The writing must separate:

```text
fact
estimate
inference
analyst_view
opinion
unknown
```

Unsupported details must remain as `TODO_*` or `MISSING_*`.

### CV-7 Quality handoff

Create `valuation_quality_handoff.yaml` for `quality-review`.

Include:

```yaml
artifact_paths:
  valuation_model:
  valuation_snapshot:
  peer_comparison:
  sensitivity_table:
  valuation_section_draft:
local_checks:
  - QR-VAL-1
  - QR-VAL-2
  - QR-VAL-3
  - QR-VAL-4
  - QR-VAL-5
no_advice_boundary: pass | needs_review | fail
open_gaps: []
```

## Outputs

Write outputs to:

```text
reports/workflow_runs/<workflow_id>/valuation/
```

Expected files:

```text
valuation_model.yaml
valuation_snapshot.yaml
peer_comparison.csv
sensitivity_table.csv
valuation_section_draft.md
valuation_gap_requests.yaml
valuation_quality_handoff.yaml
```

The caller `stock-deep-dive` may copy or reference these outputs when assembling:

```text
stock_analysis_pack.yaml
stock_deep_dive_draft.md
report_evidence_map.md
quality_gate_report.md
```

## Must-read references

Read before running:

```text
references/valuation_model_contract.md
references/method_selection.md
references/output_writing_rules.md
assets/valuation_request_template.yaml
assets/valuation_snapshot_template.yaml
assets/valuation_section_template.md
.agents/skills/stock-deep-dive/references/valuation_subagent_handoff.md
.agents/skills/stock-deep-dive/references/forecast_valuation_contract.md
```

If a reference is missing, record `TODO_REFERENCE_MISSING` and do not invent its content.

## Prohibited output language

Do not output:

```text
买入
卖出
持有
强烈推荐
目标价指令
仓位建议
止盈
止损
无风险
确定收益
必须上涨
```

Avoid English equivalents:

```text
buy / sell / hold / price target instruction / position sizing / guaranteed return
```

You may output:

```text
估值情景
估值分布
敏感性变量
同业倍数位置
风险与反证
后续验证指标
研究结论边界
```

## Quality checklist

Before closing, confirm:

```text
- inputs came from stock-deep-dive / reviewed artifacts
- no new evidence was acquired inside this skill
- all material assumptions have claim_id / metric_id / source_path / TODO
- peer set selection reason is documented
- unsupported methods are skipped with reasons
- valuation section does not contain direct trading advice
- valuation gaps are visible
- valuation_quality_handoff.yaml exists
```

<!-- BEGIN R5_BUNDLE12R_OPERATING_EVIDENCE_PROFILE -->
## Bundle 12R valuation-method eligibility

Before using peer multiples, DCF or SOTP for a Bundle 12R workflow, read
`references/bundle12r_valuation_eligibility.md` and consume
`R5_bundle12r_valuation_eligibility.yaml`. Method eligibility is independent and
non-compensating; reverse/scenario valuation remains the fallback when a method
is not eligible.
<!-- END R5_BUNDLE12R_OPERATING_EVIDENCE_PROFILE -->
