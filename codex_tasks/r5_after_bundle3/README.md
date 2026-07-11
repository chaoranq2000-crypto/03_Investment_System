# R5 After Bundle 3 — Bundle 4 reviewed-input activation task package

Base snapshot used to prepare this package: `5ef3026a608a457e91206e2f59ec8e4a10f52a1b` (`Add R5 core asset subpack validators`).

## Current state to preserve

- Bundle 3 closed as `R5_CORE_ASSET_SCHEMAS_EXECUTABLE_WITH_TODOS`.
- The four core subpack schemas and validators are executable.
- Bundle 3 supplied no accepted reviewed inputs.
- The real workflow `wf_20260703_stock_first_002837_invic` remains source-gapped.
- Sample-quality report generation remains closed.
- P2 remains closed.

## Bundle 4 objective

Prove, with synthetic test-only fixtures, that accepted reviewed inputs can pass the dropzone boundary, be materially written into canonical registries, survive registry validation, rebuild reviewed-input readiness from those registries, and pass an isolated end-to-end smoke without contaminating the real 002837 workflow.

The implementation gap to close is not merely producing a promotion result. `registries_changed` must describe actual filesystem changes, and the generated registries must be valid, provenance-preserving, atomic and idempotent.

## Included cards

1. `R5_AFTER_BUNDLE3_COMPLETION_REVIEW.md`
2. `R5_BUNDLE_4_0_STATUS_BASELINE_AND_EXPECTED_ARTIFACTS.md`
3. `R5_BUNDLE_4_1_ACCEPTED_REVIEWED_INPUT_FIXTURE_SET.md`
4. `R5_BUNDLE_4_2_DROPZONE_VALIDATION_AND_FIXTURE_BOUNDARY.md`
5. `R5_BUNDLE_4_3_REGISTRY_PROMOTION_WRITE_AND_IDEMPOTENCY.md`
6. `R5_BUNDLE_4_4_POST_PROMOTION_DRY_RUN_FROM_REGISTRIES.md`
7. `R5_BUNDLE_4_5_END_TO_END_FIXTURE_SMOKE_GATE.md`
8. `R5_BUNDLE_4_6_CLOSE_READOUT_AND_REAL_INPUT_NEXT_DECISION.md`

## Hard boundaries

- Do not call live APIs or download external files.
- Do not use synthetic fixtures as research evidence.
- Do not copy fixture rows into `data/reviewed_inputs/**`.
- Do not mutate the committed real run directory for `wf_20260703_stock_first_002837_invic` during fixture tests.
- Do not replace accepted registry values with invented real-company facts.
- Do not generate or promote a real stock report in this bundle.
- Do not allow fixture mode to open sample-quality or P2.
- Do not introduce direct trading instruction language.
- Do not hide TODO, MISSING, null-evidence, pending or rejected states.

## Intended close state

If all cards pass, Bundle 4 may close as:

```text
R5_REVIEWED_INPUT_FIXTURE_PROMOTION_SMOKE_PASSED
fixture_pipeline_executable = true
real_002837_reviewed_inputs_supplied = false
real_002837_reviewed_input_pilot_allowed = false
sample_quality_report_allowed = false
p2_allowed = false
```

The next bundle should then onboard real, locally reviewed evidence for 002837; it must not infer that fixture success makes the real report sample-quality ready.
