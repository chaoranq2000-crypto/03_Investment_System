# R5 Patch 14 Format Guard Readout

status: `PASS`

## Scope

Patch 14 added a persistent R5 artifact format guard and its unit tests. It only checks file shape, parseability, Python compile status, Markdown heading density, and pytest collectability for a fixed R5 key-file list.

This patch does not change R5 business logic, does not call live APIs, does not modify research conclusions, and does not create any buy / sell / hold / position-sizing output.

## Files Added

```text
scripts/check_r5_artifact_format.py
tests/test_check_r5_artifact_format.py
reports/p1_6/r5_format_guard.json
reports/p1_6/R5_PATCH_14_FORMAT_GUARD_READOUT.md
```

## Files Modified

```text
None.
```

## Guard Rules Covered

- R5 YAML files must have real multi-line structure and must parse with `yaml.safe_load`.
- R5 Python files must have real multi-line structure and must pass `py_compile`.
- Shebang-only single-line scripts are rejected.
- Markdown templates/specs must have enough heading density for report structure.
- Pytest files must contain at least one `def test_` function or pytest-style `Test*` class.
- Large-scale literal `\n` blobs are rejected when they appear to replace real line breaks.
- `--strict` returns a non-zero exit code when any checked artifact fails.

## Commands Run

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m py_compile scripts/check_r5_artifact_format.py
```

exit_code: `0`

summary:

```text
check_r5_artifact_format.py compiled successfully.
```

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe scripts/check_r5_artifact_format.py --strict
```

exit_code: `0`

summary:

```text
status=pass checked=19 passed=19 failed=0
```

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m pytest -q tests/test_check_r5_artifact_format.py --tb=short
```

first_exit_code: `1`

first_stdout_or_stderr_summary:

```text
5 failed because the test helper loaded a dataclass module through importlib without inserting it into sys.modules first.
```

fix:

```text
tests/test_check_r5_artifact_format.py now registers the loaded module in sys.modules before exec_module().
```

rerun_exit_code: `0`

rerun_stdout_or_stderr_summary:

```text
5 passed in 0.15s
```

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe scripts/check_r5_artifact_format.py --json reports/p1_6/r5_format_guard.json
```

exit_code: `0`

summary:

```text
status=pass checked=19 passed=19 failed=0
```

## Output Artifact

```text
reports/p1_6/r5_format_guard.json
```

The JSON report records 19 checked artifacts, 19 passes, and 0 failures.

## Known TODOs

- Patch 14 intentionally does not reconcile whether Patch 1-12 are `claimed_complete` versus `validated_complete`; that belongs to Patch 15.
- The guard uses a fixed R5 key-file list. Future R5 artifacts should be added to this list when they become canonical workflow files.

## Next Recommended Patch

```text
R5_PATCH_15_PATCH_1_12_INVENTORY_RECONCILIATION.md
```
