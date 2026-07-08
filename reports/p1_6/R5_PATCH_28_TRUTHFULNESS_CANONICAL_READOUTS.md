# R5 Patch 28 Truthfulness Canonical Readouts

status: `PASS_LEGACY_BOUNDARY_DEFINED`

## Summary

Truthfulness gate now treats canonical readouts as blocking and historical readouts as legacy_noncanonical archive entries.

## files_added

- `config/r5_readout_canonical_index.yaml`
- `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md`
- `reports/p1_6/R5_PATCH_28_TRUTHFULNESS_CANONICAL_READOUTS.md`

## files_modified

- `config/r5_readout_truthfulness_rules.yaml`
- `scripts/check_r5_readout_truthfulness.py`
- `tests/test_r5_readout_truthfulness.py`
- `reports/p1_6/r5_readout_truthfulness_result.json`

## commands_run

1. command: `C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m py_compile scripts/check_r5_readout_truthfulness.py`
   exit_code: `0`
   duration_seconds: `0.053`

   stdout_or_stderr_summary:

```text
(no stdout/stderr)
```

2. command: `C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m pytest -q tests/test_r5_readout_truthfulness.py --tb=short`
   exit_code: `0`
   duration_seconds: `0.376`

   stdout_or_stderr_summary:

```text
.....                                                                    [100%]
5 passed in 0.05s
```

3. command: `C:\Projects\03_Investment_System\.conda\investment-system\python.exe scripts/check_r5_readout_truthfulness.py --rules config/r5_readout_truthfulness_rules.yaml --glob reports/p1_6/R5_PATCH_*_READOUT.md --strict --json reports/p1_6/r5_readout_truthfulness_result.json`
   exit_code: `0`
   duration_seconds: `0.08`

   stdout_or_stderr_summary:

```text
truthfulness_status=pass checked=28 failed=0
```

## artifact_evidence

| path | exists | line_count | sha256 |
|---|---:|---:|---|
| `config/r5_readout_canonical_index.yaml` | yes | 226 | `cb6a95e86aa0f74c575568b08da514c139ae7b73334ba1274685622d0fb3205a` |
| `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md` | yes | 47 | `81d0d1654e89645ef67c8c1449a4dd79f0da8aa3529388f294a18afac4389e3c` |
| `scripts/check_r5_readout_truthfulness.py` | yes | 182 | `75f66e24596d28c0c92c460da696706a6b8aede21715f6a1cf686b599cdcbbb4` |
| `reports/p1_6/r5_readout_truthfulness_result.json` | yes | 262 | `31ba294cd59630499b1eb83a82c5e0d08bfda51297a7e86c412f2c5b3b9e59c0` |

## known_todos

- Legacy readouts are not rewritten and cannot be used as strict evidence.

## next_recommended_patch

`R5_PATCH_29_SMOKE_RESULT_TRUST_BOUNDARY`
