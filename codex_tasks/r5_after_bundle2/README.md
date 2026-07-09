# R5 After Bundle2 core research asset subpack task package

This package is the next task-card bundle after the workspace reached the Patch 55 plus Bundle 1/2 state.

Current state to preserve:

- R5 reviewed-input intake path exists and is executable.
- Patch 55 closed in `R5_REVIEWED_INPUT_PILOT_BLOCKED_SOURCE_GAPPED` because accepted reviewed market, peer, forecast and valuation inputs are absent.
- Bundle 1 structural gate hardening is accepted with TODOs.
- Bundle 2 recovery executable gates are accepted with TODOs.
- The current 002837 output must remain a source-gapped research draft unless explicit gates pass.
- Sample-quality report and P2 must stay closed unless explicit gates pass.

This package does not implement code directly. It adds small Codex task cards that Codex can execute one by one.

## Included task cards

1. `R5_BUNDLE_3_0_STATUS_BASELINE_AND_EXPECTED_ARTIFACTS.md`
2. `R5_BUNDLE_3_1_FINANCIAL_HISTORY_SUBPACK_CONTRACT.md`
3. `R5_BUNDLE_3_2_BUSINESS_BREAKDOWN_SUBPACK_CONTRACT.md`
4. `R5_BUNDLE_3_3_FORECAST_MODEL_SUBPACK_CONTRACT.md`
5. `R5_BUNDLE_3_4_VALUATION_SUBPACK_CONTRACT.md`
6. `R5_BUNDLE_3_5_CORE_ASSET_PREFLIGHT_GATE.md`
7. `R5_BUNDLE_3_6_CLOSE_READOUT_AND_NEXT_DECISION.md`

## Boundaries

- Do not call live APIs.
- Do not download external files.
- Do not generate a real stock report.
- Do not enter P2.
- Do not promote TODO, MISSING, null evidence, clue-only or pending rows into facts.
- Do not add direct trading instruction language.
- Do not modify `reports/workflow_runs/**`, `data/raw/**`, `data/processed/**`, or `data/manifests/**` in this bundle.

## Intended outcome

After these tasks, the project should have executable standalone contracts, examples, validators and tests for these R5 core research asset subpacks:

```text
financial_history_pack
business_breakdown_pack
forecast_model_pack
valuation_pack
```

The bundle should also have a core-asset preflight gate that fails closed and keeps sample-quality/P2 unavailable when core subpacks are still TODO or source-gapped.

Expected close state if no reviewed inputs are supplied:

```text
R5_CORE_ASSET_SCHEMAS_EXECUTABLE_WITH_TODOS
sample_quality_report_allowed = false
p2_allowed = false
```
