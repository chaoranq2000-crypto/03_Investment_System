# R5 Patch 49 - Status index and task hygiene

## Goal

Consolidate the current Patch 43-48 state before adding more capability. This patch should make the task/readout inventory truthful and easy to inspect.

## Background

Patch 43-47 readouts exist. The reviewed-input pilot gate result also exists, but the task package README/APPLY_ORDER and canonical readout index may not fully reflect Patch 43-48. Before new reviewed-input intake work begins, the workspace needs a clean status matrix.

## Allowed files

- `codex_tasks/r5_after_patch36/README.md`
- `codex_tasks/r5_after_patch36/APPLY_ORDER.md`
- `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md`
- `reports/p1_6/r5_after_patch48_status_matrix.yaml`
- `reports/p1_6/R5_AFTER_PATCH48_STATUS_INDEX_READOUT.md`
- optional: `scripts/check_r5_task_readout_sync.py`
- optional: `tests/test_r5_task_readout_sync.py`

## Required behavior

1. Record Patch 43-47 as completed only if the readout file exists and includes command evidence.
2. Record Patch 48 as represented by `R5_AFTER_PATCH36_REVIEWED_INPUT_CLOSE_READOUT.md` and `r5_reviewed_input_pilot_gate_result.json` if those artifacts exist.
3. Do not rewrite historical readouts.
4. Do not claim sample-quality or P2 readiness.
5. If adding a sync checker, it must distinguish:
   - task card exists but readout missing,
   - readout exists but task card missing,
   - close readout exists under a non-patch filename,
   - canonical vs legacy evidence.
6. Output `r5_after_patch48_status_matrix.yaml` with at least:
   - patch_id,
   - task_card_path,
   - readout_path,
   - status,
   - blocking_for_next,
   - notes.

## Tests

```bash
python -m py_compile scripts/check_r5_task_readout_sync.py
python -m pytest -q tests/test_r5_task_readout_sync.py --tb=short
python scripts/check_r5_task_readout_sync.py --json reports/p1_6/r5_after_patch48_status_matrix.yaml
```

If no checker is added, run at minimum:

```bash
python - <<'PY'
from pathlib import Path
required = [
  'reports/p1_6/R5_PATCH_43_VALUATION_INPUT_REGISTRY_AND_INTERLOCK_READOUT.md',
  'reports/p1_6/R5_PATCH_44_002837_REVIEWED_INPUT_DRY_RUN_READOUT.md',
  'reports/p1_6/R5_PATCH_45_R5_PACK_PROMOTION_GATE_READOUT.md',
  'reports/p1_6/R5_PATCH_46_QUALITY_GATE_SCORECARD_V2_READOUT.md',
  'reports/p1_6/R5_PATCH_47_COMPOSER_RESEARCH_DRAFT_PLUS_MODE_READOUT.md',
  'reports/p1_6/R5_AFTER_PATCH36_REVIEWED_INPUT_CLOSE_READOUT.md',
]
missing = [p for p in required if not Path(p).exists()]
assert not missing, missing
print('patch43_48_inventory_ok')
PY
```

## Readout

Add `reports/p1_6/R5_AFTER_PATCH48_STATUS_INDEX_READOUT.md`.

The readout must include:

- files_added;
- files_modified;
- commands_run;
- exit_code;
- stdout/stderr summary;
- artifact_evidence;
- known_todos;
- next_recommended_patch.

## Global boundaries

- Do not call live APIs.
- Do not download unreviewed external files.
- Do not generate any stock report.
- Do not output direct trading advice.
- Do not mark sample-quality or P2 ready.
