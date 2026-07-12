# R5 After Bundle 5 — Bundle 6 reader-facing report quality remediation

Observed repository head when this task package was prepared: `aeb846b`.
The operational base is defined by the Bundle 5 close readout rather than by a hard-coded commit hash.

## Current state to preserve

- Bundle 5 closed as `accepted_with_todos`.
- Real reviewed inputs for `002837` were supplied and promoted.
- The real reviewed-input research draft was rendered.
- The current output level remains `reviewed_input_research_draft`.
- `sample_quality_report_allowed = false`.
- `p2_allowed = false`.
- Evidence, claim, metric, limitation and no-advice controls remain mandatory.

## Why Bundle 6 exists

Bundle 5 proved that the evidence pipeline is executable and truthful. It did not prove that the output is a good reader-facing research report.

The current draft is dominated by raw evidence IDs, internal paths, readiness tokens, source-gap markers, unrounded CNY values and repeated audit blocks. Important sections are either missing or structurally thin. The current top-level composer mainly wraps the legacy note with a gate surface; it does not yet build a research narrative from section-level analytical payloads.

Bundle 6 therefore changes the unit of success from:

```text
traceable research note that can be rendered
```

to:

```text
reader-facing research report candidate
+ separate traceability appendix
+ reproducible quality scorecard
+ explicit human review gate
```

## Bundle 6 objective

Build and validate a second-generation reader-facing report path for `002837 英维克` that:

1. preserves evidence discipline;
2. separates the main report from machine audit metadata;
3. normalizes metrics into investor-readable units;
4. turns facts into causal analysis rather than raw data dumps;
5. fills the material coverage gaps that can be filled with reviewed evidence;
6. strengthens forecast and valuation reasoning without fabricating unavailable segment data;
7. introduces a reader-quality gate with negative tests; and
8. renders an `R5_002837_READER_FACING_REPORT_V2_CANDIDATE` for human review.

## Included cards

1. `R5_AFTER_BUNDLE5_COMPLETION_REVIEW.md`
2. `R5_BUNDLE_6_0_STATUS_AND_READER_QUALITY_BASELINE.md`
3. `R5_BUNDLE_6_1_READER_FACING_REPORT_CONTRACT.md`
4. `R5_BUNDLE_6_2_SECTION_PAYLOAD_AND_METRIC_NORMALIZATION.md`
5. `R5_BUNDLE_6_3_NARRATIVE_COMPOSER_AND_TRACEABILITY_SPLIT.md`
6. `R5_BUNDLE_6_4_RESEARCH_COVERAGE_REMEDIATION.md`
7. `R5_BUNDLE_6_5_FORECAST_AND_VALUATION_REMEDIATION.md`
8. `R5_BUNDLE_6_6_READER_QUALITY_GATE_AND_NEGATIVE_TESTS.md`
9. `R5_BUNDLE_6_7_002837_V2_RENDER_AND_HUMAN_REVIEW.md`
10. `R5_BUNDLE_6_8_CLOSE_READOUT_AND_NEXT_DECISION.md`

## Hard boundaries

- User-supplied sample reports are style and coverage references only. They are not evidence.
- Do not import facts, forecasts, prices, events, citations, ratings, target prices or trade instructions from the samples.
- Do not fabricate liquid-cooling-specific revenue, margin or profit contribution.
- Do not hide material uncertainty merely to improve prose.
- Do not expose raw evidence IDs, registry paths, workflow paths or machine readiness tokens in the main reader report.
- Do not remove the underlying audit trail; move it to a separate appendix.
- Do not generate direct buy/sell/hold, position-sizing, trade-timing or guaranteed-return language.
- Do not set `sample_quality_report_allowed = true` in this bundle.
- Do not open P2.
- Do not fabricate a human reviewer, review timestamp or acceptance decision.

## Intended successful close state

```text
current_r5_state = R5_002837_READER_FACING_REPORT_V2_CANDIDATE_READY
reader_report_candidate_rendered = true
traceability_appendix_rendered = true
reader_quality_gate_passed = true
human_review_required = true
human_review_status = pending
sample_quality_report_allowed = false
p2_allowed = false
```

A later explicit human acceptance may authorize a narrowly scoped promotion task. Bundle 6 itself must not self-promote.
