# R5 After Patch48 Apply Order

Run the task cards in this order. Do not skip steps.

## Phase A: status hygiene before more work

1. `R5_PATCH_49_STATUS_INDEX_AND_TASK_HYGIENE.md`

## Phase B: reviewed-input intake contract

2. `R5_PATCH_50_REVIEWED_INPUT_DROPZONE_CONTRACT.md`
3. `R5_PATCH_51_REVIEWED_INPUT_DROPZONE_VALIDATORS.md`

## Phase C: 002837 controlled staging and promotion

4. `R5_PATCH_52_002837_REVIEWED_INPUT_STAGING_DRY_RUN.md`
5. `R5_PATCH_53_REGISTRY_PROMOTION_FROM_ACCEPTED_STAGING.md`

## Phase D: gate recheck and close

6. `R5_PATCH_54_PILOT_GATE_RECHECK_AND_DRAFT_PLUS_RENDER.md`
7. `R5_PATCH_55_CLOSE_READOUT_AND_NEXT_DECISION.md`

## Stop conditions

Stop and report if any of these occur:

- a validator promotes a TODO row as accepted;
- an accepted reviewed input lacks `source_evidence_id`, `as_of_date`, or reviewer/review status;
- a task attempts to use live API data;
- a task tries to generate sample-quality or P2 output without the explicit gate allowing it;
- a generated report contains direct trading advice.
