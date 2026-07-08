# R5 Patch 15 Inventory Reconciliation Readout

status: `PASS_TOOLING_ADDED_INVENTORY_NOT_ACCEPTED`

## Scope

Patch 15 added an inventory reconciliation tool for R5 Patch 1-12. The tool distinguishes `claimed_complete` from `validated_complete` by checking expected files, format state, YAML parse status, Python compile status, pytest collectability, and related readout presence.

This patch does not generate research conclusions, does not call live APIs, does not modify historical workflow-run research outputs, and does not create any buy / sell / hold / position-sizing output.

## Files Added

```text
scripts/r5_patch_inventory_check.py
config/r5_patch_1_12_expected_artifacts.yaml
tests/test_r5_patch_inventory_check.py
reports/p1_6/r5_patch_1_12_inventory_status.yaml
reports/p1_6/R5_PATCH_15_INVENTORY_RECONCILIATION_READOUT.md
```

## Files Modified

```text
None.
```

## Path Note

The task card suggested `configs/r5_patch_1_12_expected_artifacts.yaml`, but this repository already uses the top-level `config/` directory. To follow `AGENTS.md` placement rules and avoid an ad hoc top-level folder, the config was added at:

```text
config/r5_patch_1_12_expected_artifacts.yaml
```

## Commands Run

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m py_compile scripts/r5_patch_inventory_check.py
```

exit_code: `0`

summary:

```text
r5_patch_inventory_check.py compiled successfully.
```

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe scripts/r5_patch_inventory_check.py --config config/r5_patch_1_12_expected_artifacts.yaml --out reports/p1_6/r5_patch_1_12_inventory_status.yaml
```

exit_code: `0`

stdout_or_stderr_summary:

```text
inventory_status=claimed_complete_but_validation_failed accepted=false patches_checked=12 artifact_failures=35
```

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m pytest -q tests/test_r5_patch_inventory_check.py --tb=short
```

exit_code: `0`

stdout_or_stderr_summary:

```text
4 passed in 0.09s
```

## Inventory Result

```yaml
inventory_status: claimed_complete_but_validation_failed
accepted: false
summary:
  patches_checked: 12
  blocking_patch_failures: 9
  artifacts_checked: 69
  artifact_failures: 35
  artifact_warnings: 0
```

Validated complete:

```text
R5_PATCH_1
R5_PATCH_2
R5_PATCH_3
```

Validation failed:

```text
R5_PATCH_4
R5_PATCH_5
R5_PATCH_6
R5_PATCH_7
R5_PATCH_8
R5_PATCH_9
R5_PATCH_10
R5_PATCH_11
R5_PATCH_12
```

## Failure Summary

R5_PATCH_4:

```text
missing financial/business pack contracts, examples, validator, test, and task-card-named readout.
```

R5_PATCH_5:

```text
missing forecast model pack contract, example, validator, test, and task-card-named readout.
```

R5_PATCH_6:

```text
missing company-valuation R5 handoff contract, task-card-named valuation pack test, and task-card-named readout.
```

R5_PATCH_7:

```text
missing task-card-named technical market pack test and readout.
```

R5_PATCH_8:

```text
missing task-card-named sentiment event pack test and readout.
```

R5_PATCH_9:

```text
missing risk/counterevidence contract, example, validator, test, and task-card-named readout.
```

R5_PATCH_10:

```text
missing R5 issue schema, quality-gate validator, quality-gate test, and task-card-named readout.
```

R5_PATCH_11:

```text
missing report planner contract, outline fixture, thesis stack fixture, plan validator, planner/composer test, and task-card-named readout.
```

R5_PATCH_12:

```text
missing task-card-named sample benchmark regression readout.
```

The full artifact-level status is written to:

```text
reports/p1_6/r5_patch_1_12_inventory_status.yaml
```

## Known TODOs

- Decide whether the current shorter readout names should be treated as compatibility aliases or whether task-card-named readouts should be added.
- Reconcile renamed validator/test files before claiming Patch 4-12 are `validated_complete`.
- Do not enter P2 while `reports/p1_6/r5_patch_1_12_inventory_status.yaml` remains `accepted: false`.

## Next Recommended Patch

```text
R5_PATCH_16_R5_VALIDATOR_SEMANTIC_HARDENING.md
```

However, Patch 16 should not be used to silently paper over Patch 15 failures. It should either consume this inventory status as a blocking input or explicitly create follow-up repair tasks for the missing Patch 4-12 artifacts.
