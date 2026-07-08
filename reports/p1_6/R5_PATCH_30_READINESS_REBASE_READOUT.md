# R5 Patch 30 Readiness Rebase Readout

status: `PASS_CONTRACTS_EXECUTABLE_WITH_TODOS_ONLY`

## Summary

Readiness now reads real smoke, inventory, truthfulness, source-gap and no-advice evidence. Decision is R5_CONTRACTS_EXECUTABLE_WITH_TODOS_ONLY.

## files_added

- `reports/p1_6/R5_PATCH_30_READINESS_REBASE_READOUT.md`

## files_modified

- `reports/p1_6/r5_mvp_smoke_result.json`
- `reports/p1_6/r5_readiness_gate_result.json`

## commands_run

1. command: `C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m py_compile scripts/r5_readiness_gate.py`
   exit_code: `0`
   duration_seconds: `0.046`

   stdout_or_stderr_summary:

```text
(no stdout/stderr)
```

2. command: `C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m pytest -q tests/test_r5_readiness_gate.py --tb=short`
   exit_code: `0`
   duration_seconds: `0.356`

   stdout_or_stderr_summary:

```text
....                                                                     [100%]
4 passed in 0.04s
```

3. command: `C:\Projects\03_Investment_System\.conda\investment-system\python.exe scripts/run_r5_mvp_smoke.py --strict --json reports/p1_6/r5_mvp_smoke_result.json`
   exit_code: `0`
   duration_seconds: `2.576`

   stdout_or_stderr_summary:

```text
r5_mvp_smoke_status=pass checked=6 failed=0
[r5_artifact_format_guard] exit_code=0 duration=0.539s
status=pass checked=24 passed=24 failed=0
[r5_patch_inventory_check] exit_code=0 duration=0.239s
inventory_status=validated_complete accepted=true patches_checked=12 artifact_failures=0
[r5_pack_validators] exit_code=0 duration=0.648s
..............................................                           [100%]
46 passed in 0.32s
[r5_composer_fixture_smoke] exit_code=0 duration=0.561s
............                                                             [100%]
12 passed in 0.23s
[r5_quality_fixture_smoke] exit_code=0 duration=0.405s
.....                                                                    [100%]
5 passed in 0.08s
[r5_readout_truthfulness_gate] exit_code=0 duration=0.083s
truthfulness_status=pass checked=28 failed=0
```

4. command: `C:\Projects\03_Investment_System\.conda\investment-system\python.exe scripts/r5_readiness_gate.py --json reports/p1_6/r5_readiness_gate_result.json`
   exit_code: `0`
   duration_seconds: `0.144`

   stdout_or_stderr_summary:

```text
r5_readiness_decision=R5_CONTRACTS_EXECUTABLE_WITH_TODOS_ONLY can_enter_source_gapped_real_sample_pilot=false sample_quality_report_allowed=false p2_allowed=false blockers=0
```

## artifact_evidence

| path | exists | line_count | sha256 |
|---|---:|---:|---|
| `scripts/r5_readiness_gate.py` | yes | 191 | `8b18565d15373dce3e9a72886099c6d3644be128931c39d8028ff1be4b245ea2` |
| `tests/test_r5_readiness_gate.py` | yes | 78 | `d32f58d0b9feb5c066ad388b1d8e37238927455be1ec89bf7bd185eafa23da83` |
| `reports/p1_6/r5_mvp_smoke_result.json` | yes | 282 | `a812887d182e2c2b685e7702878a26dca8b54390de82fb903a03be6467262fb2` |
| `reports/p1_6/r5_readiness_gate_result.json` | yes | 28 | `e8eec0a1df352f06c463ffe8cc18605e593f4ad70178db41e13076b904d635a4` |

## known_todos

- Readiness remains limited to contracts executable with TODOs; source-gapped pilot, sample-quality and P2 are not opened.

## next_recommended_patch

`R5_PATCH_31_SOURCE_GAPPED_002837_PACK_NORMALIZATION`
