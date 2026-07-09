# R5 After Patch48 reviewed-input activation task package

This package is the next task-card bundle after the workspace has reached the Patch 47/48 state.

Current state to preserve:

- R5 contracts, validators, scorecard and composer degradation are executable.
- The current 002837 pack remains `source_gapped_research_draft`.
- Reviewed market, peer, forecast and valuation inputs are still absent.
- Sample-quality report and P2 must remain closed unless explicit gates pass.

This package does not implement code directly. It adds small Codex task cards that Codex can execute one by one.

## Included task cards

1. `R5_PATCH_49_STATUS_INDEX_AND_TASK_HYGIENE.md`
2. `R5_PATCH_50_REVIEWED_INPUT_DROPZONE_CONTRACT.md`
3. `R5_PATCH_51_REVIEWED_INPUT_DROPZONE_VALIDATORS.md`
4. `R5_PATCH_52_002837_REVIEWED_INPUT_STAGING_DRY_RUN.md`
5. `R5_PATCH_53_REGISTRY_PROMOTION_FROM_ACCEPTED_STAGING.md`
6. `R5_PATCH_54_PILOT_GATE_RECHECK_AND_DRAFT_PLUS_RENDER.md`
7. `R5_PATCH_55_CLOSE_READOUT_AND_NEXT_DECISION.md`

## Boundaries

- Do not call live APIs.
- Do not download unreviewed external files.
- Do not generate a sample-quality report in this package.
- Do not enter P2 in this package.
- Do not convert `TODO_*`, `MISSING_DISCLOSURE`, `LOW_CONFIDENCE_CLUE_ONLY`, or `evidence_id: null` into facts.
- Do not output buy, sell, hold, target-price, timing, position-size, or guaranteed-return language.

## Intended outcome

After these tasks, the project should have a durable reviewed-input intake path:

```text
manual reviewed input dropzone
→ validator
→ staging dry run
→ accepted-only registry promotion
→ pilot gate recheck
→ draft-plus render only when gates allow
→ close readout
```

If no accepted reviewed inputs are supplied, the correct final state remains blocked/source-gapped.
