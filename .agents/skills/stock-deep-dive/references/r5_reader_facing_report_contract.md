# R5 reader-facing report contract

## Purpose

The reader report is a Chinese research narrative for human readers. It is a separate product from the audit-oriented note and consumes validated section payloads rather than raw registries.

## Output pair

- `reader_report`: visible analysis, rounded display metrics and stable citations such as `[E1]`.
- `traceability_appendix`: raw evidence identifiers, source paths, methods, reviewer state, limitations, conflicts and staleness.

The visible report must contain the mandatory sections `executive_summary`, `company_context_and_scope`, `financial_history_and_cashflow_quality`, `business_breakdown_and_economics`, `industry_structure_and_competition`, `forecast_and_scenarios`, `valuation_and_market_expectations`, `risks_counterevidence_and_watchpoints`, and `research_conclusion`. Dated events are required when reviewed material events exist. Technical and sentiment sections remain optional.

## Metadata

Machine metadata records workflow ID, stock code/name, cutoff date, output level, input digest, appendix and scorecard paths, human-review status, and the fixed sample-quality/P2 flags. The prose renderer does not expose internal paths or identifiers.

## Section payload

Every major section has a one-sentence judgment, facts, calculations, causal chain, economic implications, counterpoints, uncertainties, watchpoints, display references and reader readiness. Unsupported causes fail closed; an inference must carry supporting facts and a limitation.

## Main-body exclusions

The executable gate blocks raw evidence/claim/metric or assumption IDs, workflow/registry paths, machine labels (`readiness`, `visible_gap`, `next_action`), raw gap tokens, method codes, repeated audit blocks, unrounded currency dumps, fabricated review acceptance, and direct buy/sell/hold or position instructions.

## Citation rule

Each visible citation must resolve exactly once in the appendix. Every material fact, estimate and inference must cite at least one display reference. The appendix record retains claim type, text digest, period, unit, raw evidence IDs, source path, method, confidence, limitation, reviewer state, and conflict/staleness state.

## Fixed boundary

`human_review_required=true`, `human_review_status=pending`, `sample_quality_report_allowed=false`, and `p2_allowed=false`. Human acceptance cannot be synthesized by this workflow.
