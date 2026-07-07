# Valuation Subagent Handoff — stock-deep-dive reference

## 1. Purpose

This reference defines how `stock-deep-dive` calls `company-valuation` during valuation section writing.

`company-valuation` is a skill-local subagent/sub-skill for valuation context. It does not replace `stock-deep-dive`, `evidence-ingest`, `segment-company-mapping` or `quality-review`.

## 2. Call timing

Call `company-valuation` after:

```text
RP5 Analysis Pack Build
```

and before:

```text
RP8 Report Draft
```

Recommended insertion point:

```text
RP6 Forecast & Valuation Context
SDD-2.5 Valuation subagent handoff
```

## 3. Preconditions

`stock-deep-dive` should create `valuation_request.yaml` only after checking:

```text
- company identity is unambiguous;
- stock_analysis_pack.yaml exists;
- forecast_model.yaml exists or TODO_FORECAST_MODEL is explicit;
- financial_metric_pack.csv or reviewed_metrics exists, or TODO_STRUCTURED_FINANCIAL_DATA is explicit;
- market snapshot / valuation snapshot exists, or TODO_MARKET_DATA is explicit;
- peer_market_snapshot.csv exists, or TODO_PEER_DATA is explicit;
- no_advice_boundary is true.
```

If any precondition is missing, `stock-deep-dive` may still call `company-valuation`, but the subagent must output gap requests rather than deterministic valuation prose.

## 4. Handoff payload

Write:

```text
reports/workflow_runs/<workflow_id>/valuation_request.yaml
```

Schema:

```yaml
valuation_request:
  workflow_id:
  stock_code:
  company_id:
  stock_name:
  exchange:
  as_of_date:
  caller_skill: stock-deep-dive
  parent_stage: RP6
  quality_target: bridge | internal_draft | publishable_candidate
  no_advice_boundary: true
  input_paths:
    stock_analysis_pack:
    forecast_model:
    financial_metric_pack:
    reviewed_claims:
    reviewed_metrics:
    market_snapshot:
    peer_market_snapshot:
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
  known_gaps: []
```

Use template:

```text
.agents/skills/stock-deep-dive/assets/valuation_request_template.yaml
```

## 5. Expected subagent outputs

`company-valuation` should write:

```text
reports/workflow_runs/<workflow_id>/valuation/valuation_model.yaml
reports/workflow_runs/<workflow_id>/valuation/valuation_snapshot.yaml
reports/workflow_runs/<workflow_id>/valuation/peer_comparison.csv
reports/workflow_runs/<workflow_id>/valuation/sensitivity_table.csv
reports/workflow_runs/<workflow_id>/valuation/valuation_section_draft.md
reports/workflow_runs/<workflow_id>/valuation/valuation_gap_requests.yaml
reports/workflow_runs/<workflow_id>/valuation/valuation_quality_handoff.yaml
```

## 6. How stock-deep-dive consumes outputs

`stock-deep-dive` should:

```text
1. Load valuation_model.yaml into stock_analysis_pack.yaml#valuation_model.
2. Copy or reference valuation_section_draft.md when rendering “五、估值分析”.
3. Add valuation_gap_requests.yaml to source_gap_report.md / open_questions.md.
4. Add valuation_quality_handoff.yaml to quality-review handoff.
5. Preserve TODO_MARKET_DATA / TODO_PEER_DATA / TODO_FORECAST_MODEL in the report body when present.
```

`stock-deep-dive` must not use valuation outputs to update segment exposure. Market valuation and peer multiples cannot prove business exposure.

## 7. Failure handling

| Failure | Required handling |
|---|---|
| Missing market snapshot | show `TODO_MARKET_DATA`; do not write current multiple comparison as fact |
| Missing peer snapshot | show `TODO_PEER_DATA`; do not rank the company against peers |
| Missing forecast model | show `TODO_FORECAST_MODEL`; dynamic valuation section stays partial |
| Weak peer set | label `LOW_CONFIDENCE_PEER_SET` and write limitations |
| Missing segment disclosure | skip SOTP or label `TODO_SEGMENT_DISCLOSURE` |
| DCF assumptions unsupported | skip DCF or label low-confidence scenario |
| No-advice violation | quality-review G9 should block or needs_fix |

## 8. Quality-review handoff

Include valuation outputs in the `quality-review` handoff for:

```text
G1 Evidence Gate
G2 Claim Gate
G3 Metric Gate
G7 Stock Report Gate
G9 No Advice Gate
```

Optional skill-local checks:

```text
QR-VAL-1 valuation output exists or visible TODO
QR-VAL-2 every valuation metric has period/unit/source/as_of_date
QR-VAL-3 peer set has selection reasons and limitations
QR-VAL-4 scenarios are labeled estimate/inference and include sensitivity
QR-VAL-5 no direct trading advice or target-price instruction
```

Do not create new global G IDs.

## 9. Report writing boundary

The final report may say:

```text
公司当前估值处于同业中位数附近，但该判断依赖 peer_market_snapshot 的日期和 2026E 盈利预测，属于 estimate / inference。
```

The final report must not say:

```text
因此应买入 / 卖出 / 持有
目标价为 X
建议仓位 X%
确定性上涨 / 无风险
```
