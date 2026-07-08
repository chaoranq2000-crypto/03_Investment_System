# R5 Patch 27 Inventory V2 Readout

status: `PASS_VALIDATED_COMPLETE`

## Summary

Inventory v2 reconciled old file names to current artifacts using superseded_by and strict inventory accepted with artifact_failures=0.

## files_added

- `reports/p1_6/R5_PATCH_27_INVENTORY_V2_READOUT.md`

## files_modified

- `config/r5_patch_1_12_expected_artifacts.yaml`
- `scripts/r5_patch_inventory_check.py`
- `tests/test_r5_patch_inventory_check.py`
- `reports/p1_6/r5_patch_1_12_inventory_status.yaml`

## commands_run

1. command: `C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m py_compile scripts/r5_patch_inventory_check.py`
   exit_code: `0`
   duration_seconds: `0.05`

   stdout_or_stderr_summary:

```text
(no stdout/stderr)
```

2. command: `C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m pytest -q tests/test_r5_patch_inventory_check.py --tb=short`
   exit_code: `0`
   duration_seconds: `0.386`

   stdout_or_stderr_summary:

```text
.....                                                                    [100%]
5 passed in 0.06s
```

3. command: `C:\Projects\03_Investment_System\.conda\investment-system\python.exe scripts/r5_patch_inventory_check.py --config config/r5_patch_1_12_expected_artifacts.yaml --out reports/p1_6/r5_patch_1_12_inventory_status.yaml --strict`
   exit_code: `0`
   duration_seconds: `0.238`

   stdout_or_stderr_summary:

```text
inventory_status=validated_complete accepted=true patches_checked=12 artifact_failures=0
```

## artifact_evidence

| path | exists | line_count | sha256 |
|---|---:|---:|---|
| `config/r5_patch_1_12_expected_artifacts.yaml` | yes | 298 | `58c37de3949958792446388b107fab2353512a09544463c9b613daca30ad6489` |
| `scripts/r5_patch_inventory_check.py` | yes | 253 | `9e4ccff1723b6a3a7092ed221e1c83b2323e1b9b67de23c4a85efc50fcf2e77d` |
| `tests/test_r5_patch_inventory_check.py` | yes | 135 | `6cb3ef41807abf3796fa2a93c9573a395f165b442cdcf94d5879cfcc56957de2` |
| `reports/p1_6/r5_patch_1_12_inventory_status.yaml` | yes | 982 | `9ad7c5bd0ef75ed139f948d499644c75e694acaf636198edaa5de0ab047d0cb9` |

## known_todos

- Superseded historical names remain visible through superseded_by fields; no missing_required remains in strict inventory.

## next_recommended_patch

`R5_PATCH_28_TRUTHFULNESS_CANONICAL_READOUTS`
