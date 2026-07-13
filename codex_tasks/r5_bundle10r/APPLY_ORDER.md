# R5 Bundle 10R — Apply order

Bundle 10R is a forward Reader rebuild from model generation `model_gen_r5_bundle9r_1cd42241e6a38fb3`. It preserves all historical Bundle 10 outputs and never silently overwrites the old Reader v3, scorecard, traceability appendix, or human-review records.

Execute in order:

1. `R5_BUNDLE_10R_0_BASELINE_AND_MODEL_BINDING.md`
2. `R5_BUNDLE_10R_1_READER_INPUT_AND_CLAIM_CONTRACT.md`
3. `R5_BUNDLE_10R_2_DYNAMIC_ANALYSIS_PAYLOAD.md`
4. `R5_BUNDLE_10R_3_GENERIC_WRITER_AND_TRACEABILITY.md`
5. `R5_BUNDLE_10R_4_MARKET_EVENT_CONTEXT.md`
6. `R5_BUNDLE_10R_5_NON_COMPENSATING_QUALITY_GATE.md`
7. `R5_BUNDLE_10R_6_REGRESSION_AND_NEGATIVE_TESTS.md`
8. `R5_BUNDLE_10R_7_HUMAN_REVIEW_AND_STATE_SYNC.md`
9. `R5_BUNDLE_10R_8_CLOSE_AND_READER_GENERATION_LOCK.md`

Stop on any model-generation mismatch, unresolved citation, core-section failure, claim-boundary violation, stale market/event date, direct action language, or fabricated human-review status. Do not weaken a gate to make the Reader pass.
