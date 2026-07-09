# R5 Patch 55 - Close readout and next decision

## Goal

Close the Patch 49-54 reviewed-input activation bundle with a truthful final status. The close readout must state whether the workspace is still source-gapped, allowed for reviewed-input pilot, allowed for sample-quality candidate, or allowed for P2.

## Background

The project should only advance when gates allow it. This patch freezes the state after reviewed-input dropzone, validation, staging, promotion and render recheck.

## Allowed files

- `reports/p1_6/R5_AFTER_PATCH55_REVIEWED_INPUT_ACTIVATION_CLOSE_READOUT.md`
- `reports/p1_6/r5_after_patch55_decision.json`
- `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md`
- `reports/p1_6/r5_mvp_smoke_result.json`
- optional: `config/r5_patch_49_55_expected_artifacts.yaml`
- optional: `tests/test_r5_after_patch55_close.py`

## Required behavior

1. Run strict smoke and relevant new tests.
2. Collect results from:

```text
R5_AFTER_PATCH48_STATUS_INDEX_READOUT.md
R5_PATCH_50_REVIEWED_INPUT_DROPZONE_CONTRACT_READOUT.md
R5_PATCH_51_REVIEWED_INPUT_DROPZONE_VALIDATORS_READOUT.md
R5_PATCH_52_002837_REVIEWED_INPUT_STAGING_DRY_RUN_READOUT.md
R5_PATCH_53_REGISTRY_PROMOTION_FROM_ACCEPTED_STAGING_READOUT.md
R5_PATCH_54_PILOT_GATE_RECHECK_AND_DRAFT_PLUS_RENDER_READOUT.md
r5_reviewed_input_pilot_gate_result.json
R5_reviewed_input_render_result.yaml
```

3. Output `r5_after_patch55_decision.json` with:

```text
current_r5_state
reviewed_input_pilot_allowed
sample_quality_report_allowed
p2_allowed
strict_smoke_status
pack_promotion_level
rendered_output_type
blockers
non_blocking_todos
known_todos
next_recommended_patch
```

4. If reviewed inputs are still absent, the correct state must remain blocked/source-gapped.
5. If reviewed inputs are partially accepted, the correct state may be reviewed-input draft only, not sample-quality.
6. If any critical TODO remains, sample-quality and P2 must remain false.

## Tests

```bash
python -m pytest -q tests/test_r5_after_patch55_close.py tests/test_r5_pilot_gate_recheck_and_render.py tests/test_r5_reviewed_input_registry_promotion.py --tb=short
python scripts/run_r5_mvp_smoke.py --strict --json reports/p1_6/r5_mvp_smoke_result.json
python scripts/r5_reviewed_input_pilot_gate.py --json reports/p1_6/r5_reviewed_input_pilot_gate_result.json
```

If `tests/test_r5_after_patch55_close.py` is not added, the readout must explain why and list the exact commands that were run instead.

## Readout

Add `reports/p1_6/R5_AFTER_PATCH55_REVIEWED_INPUT_ACTIVATION_CLOSE_READOUT.md`.

## Global boundaries

- Do not call live APIs.
- Do not download unreviewed external files.
- Do not output direct trading advice.
- Do not mark sample-quality or P2 ready unless the explicit gates allow it.
- Do not hide TODOs or source gaps.
