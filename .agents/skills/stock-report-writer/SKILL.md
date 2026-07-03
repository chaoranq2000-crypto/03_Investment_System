---
name: stock-report-writer
description: 个股研报生成与表达。当 stock-research-analyst 已输出 stock_analysis_pack、forecast_model、valuation_model、sentiment/event packs 后，用于生成接近样例报告质量的 Markdown 研报草案。不得自行下载证据、发明数据、越过质量门或输出直接买卖指令。
---

# Stock Report Writer Skill

## Goal

Generate a polished, sample-quality stock research report from structured analysis inputs.

The writer is a translator from analysis pack to narrative. It does not create new evidence or unsupported conclusions.

## Inputs

Required:

```yaml
stock_analysis_pack:
financial_quality:
business_breakdown:
industry_context_card:
forecast_model:
valuation_model:
risk_counter_evidence:
```

Optional:

```yaml
technical_snapshot:
market_sentiment_pack:
catalyst_calendar:
evidence_map:
style_target: sample_quality
```

## Responsibilities

1. Convert structured analysis into coherent report prose.
2. Preserve fact / inference / estimate distinctions.
3. Surface evidence gaps instead of hiding them.
4. Use sample-like structure and narrative strength.
5. Produce evidence map and open questions.
6. Avoid unsupported advice, target-price instructions or position sizing.

## Out of scope

Do not:

```text
- Download evidence.
- Parse PDFs.
- Promote claims or metrics.
- Add facts not in stock_analysis_pack.
- Make buy/sell/hold recommendations.
- Write target price as instruction.
- Hide TODOs.
```

## Standard sections

```text
0. Metadata
前言
一、财务概览
二、业务拆分
三、行业分析
四、盈利预测
五、估值分析
六、技术分析
七、情绪分析
八、事件驱动
九、研究结论、风险与跟踪清单
附录：Evidence Map / Open Questions
```

## Output contract

```text
reports/workflow_runs/<run_id>/stock_report_sample_quality_draft.md
reports/workflow_runs/<run_id>/report_evidence_map.md
reports/workflow_runs/<run_id>/report_open_questions.md
reports/workflow_runs/<run_id>/writer_gap_requests.yaml
```

## Style rules

- Start each major section with a conclusion sentence.
- Avoid list-only writing; combine data and interpretation.
- Make the core contradiction explicit.
- Explain why the evidence matters.
- Include risks and counter-evidence in the main body, not only at the end.
- Use Markdown tables for financials, business lines, valuation and catalysts.

## Quality checklist

- [ ] Every material paragraph is traceable to analysis pack ids.
- [ ] Missing evidence appears in Open Questions.
- [ ] Forecast and valuation are labeled as estimates/inferences.
- [ ] No direct trading instruction.
- [ ] Evidence Map exists.
- [ ] Report can be reviewed by `quality-review` without hidden inputs.
