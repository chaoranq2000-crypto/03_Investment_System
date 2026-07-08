# R5 Patch 29 Smoke Trust Boundary Readout

status: `PASS`

## Summary

Smoke JSON includes generated_at, repo_root, python executable/version, platform, steps, stdout/stderr tails and artifact outputs.

## files_added

- `reports/p1_6/R5_PATCH_29_SMOKE_TRUST_BOUNDARY_READOUT.md`

## files_modified

- `scripts/run_r5_mvp_smoke.py`
- `tests/test_run_r5_mvp_smoke.py`
- `reports/p1_6/r5_mvp_smoke_result.json`

## commands_run

1. command: `C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m py_compile scripts/run_r5_mvp_smoke.py`
   exit_code: `0`
   duration_seconds: `0.054`

   stdout_or_stderr_summary:

```text
(no stdout/stderr)
```

2. command: `C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m pytest -q tests/test_run_r5_mvp_smoke.py --tb=short`
   exit_code: `0`
   duration_seconds: `0.444`

   stdout_or_stderr_summary:

```text
.....                                                                    [100%]
5 passed in 0.11s
```

3. command: `C:\Projects\03_Investment_System\.conda\investment-system\python.exe scripts/run_r5_mvp_smoke.py --strict --json reports/p1_6/r5_mvp_smoke_result.json`
   exit_code: `0`
   duration_seconds: `2.581`

   stdout_or_stderr_summary:

```text
r5_mvp_smoke_status=pass checked=6 failed=0
[r5_artifact_format_guard] exit_code=0 duration=0.529s
status=pass checked=24 passed=24 failed=0
[r5_patch_inventory_check] exit_code=0 duration=0.241s
inventory_status=validated_complete accepted=true patches_checked=12 artifact_failures=0
[r5_pack_validators] exit_code=0 duration=0.659s
..............................................                           [100%]
46 passed in 0.32s
[r5_composer_fixture_smoke] exit_code=0 duration=0.573s
............                                                             [100%]
12 passed in 0.24s
[r5_quality_fixture_smoke] exit_code=0 duration=0.4s
.....                                                                    [100%]
5 passed in 0.08s
[r5_readout_truthfulness_gate] exit_code=0 duration=0.08s
truthfulness_status=pass checked=28 failed=0
```

## artifact_evidence

| path | exists | line_count | sha256 |
|---|---:|---:|---|
| `scripts/run_r5_mvp_smoke.py` | yes | 196 | `b294d57b7566335f8d1c3420c7b2bb719973a8035e45e11b53b17b6faad81b2f` |
| `tests/test_run_r5_mvp_smoke.py` | yes | 103 | `1db24516da6247036939e965a443d4c930dc17d1982164958119fbb955e30d90` |
| `reports/p1_6/r5_mvp_smoke_result.json` | yes | 282 | `a812887d182e2c2b685e7702878a26dca8b54390de82fb903a03be6467262fb2` |

## known_todos

- Smoke verifies contracts only; it does not clear forecast/valuation/market/sentiment TODOs.

## next_recommended_patch

`R5_PATCH_30_READINESS_GATE_REBASE_ON_REAL_SMOKE`
