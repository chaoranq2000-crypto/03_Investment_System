# R5 Report Composer Contract

## Purpose

`compose_r5_report_from_pack.py` converts a reviewed or fixture `R5_stock_research_pack.yaml` into a Markdown note skeleton. It is a translator, not an analyst.

## Inputs and outputs

```text
input:  R5_stock_research_pack.yaml
output: R5_stock_research_note.md
```

## Required behavior

1. Preserve `pack_status` and downgrade labels. If the pack is not `sample_quality_candidate`, the note must visibly say `research_draft`, `needs_fix`, or `blocked`.
2. Include sections: 前言、财务概览、业务拆分、行业分析、盈利预测、估值分析、技术分析、情绪分析、事件驱动、研究结论、Source Gap Appendix.
3. Preserve TODO / MISSING / UNVERIFIED tokens in Source Gap Appendix.
4. Do not add numbers that are absent from the input pack.
5. Do not emit direct trading action, rating, position sizing, target-price instruction, or guaranteed-return wording.

## Out of scope

- No live data.
- No company-knowledge completion.
- No forecast, valuation, event, or market-state calculation.
- No real stock report generation.
