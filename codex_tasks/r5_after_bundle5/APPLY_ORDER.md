# R5 Bundle 6 apply order

Execute the cards in order. Do not start a later card while an earlier card has unresolved critical blockers.

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

## Commit discipline

Prefer one commit per owner card. Each card must leave the repository testable and must record:

- files added;
- files modified;
- commands run;
- exit codes;
- concise stdout/stderr summary;
- known TODOs;
- output hashes where a report or scorecard is generated.

## Stop conditions

Stop and fail closed when any of the following occurs:

- main report contains unsupported factual prose;
- evidence references cannot be resolved in the traceability appendix;
- a source-gap token is silently converted into a fact;
- raw internal IDs or paths leak into the reader report;
- forecast arithmetic does not reconcile;
- valuation denominators, dates or share counts conflict;
- the new quality gate is bypassed;
- a generated artifact attempts to mark human review as accepted;
- sample-quality or P2 is opened.
