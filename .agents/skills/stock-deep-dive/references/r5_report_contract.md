# R5 Report Contract

## Purpose

`R5_stock_research_note.md` is a derived translation of reviewed R5 research assets. It is not a source of new facts, numbers, forecasts, valuation views, catalysts, or risks.

The report layer may only consume:

```text
R5_stock_research_pack.yaml
R5_quality_gate_report.yaml or issue list
R5_source_gap_report.md
R5_open_questions.md
reviewed valuation / market / sentiment sidecars
```

## Allowed report states

| State | Meaning | Report action |
|---|---|---|
| `R5_sample_quality_ready` | Pack passed R5 gate with no high issues and visible TODOs only where allowed. | Composer may produce sample-quality note. |
| `R5_research_draft` | Core facts are reviewable but sample-quality inputs are incomplete. | Composer may produce internal draft with visible limitations. |
| `R5_source_gapped_draft` | Major source gaps remain. | Composer may produce source-gap-first draft only. |
| `blocked` | Identity, evidence, quality, no-advice, or source-gap visibility failed. | No report prose should be generated. |

## Composition rules

1. Every material sentence must trace to `evidence_id`, `claim_id`, `metric_id`, `assumption_id`, scenario ID, or a visible `source_gap_register` row.
2. Facts, estimates, assumptions, inferences, management comments, analyst views, opinions, and unknowns must remain separated.
3. Forecast and valuation sections may translate reviewed `forecast_model_pack` and `valuation_pack`; they must not calculate new values.
4. Technical, sentiment, and event sections require `as_of_date` before state language is allowed.
5. Source gaps must remain visible in the body or Source Gap Appendix.
6. The report must not contain direct trading instructions, position sizing, guaranteed-return language, or target-price instructions.

## Required sections

```text
preface
financial_overview
business_breakdown
industry_analysis
forecast
valuation
technical_analysis
sentiment_analysis
catalyst_events
research_conclusion
source_gap_appendix
```

## Blocked composition triggers

- `company_identity_pack` or `evidence_snapshot_pack` is missing or contradictory.
- `source_gap_register` exists but is hidden from the report plan.
- High severity quality issue remains open.
- No-advice gate fails.
- Composer adds a number, source, event, valuation statement, or conclusion that is absent from the pack.
