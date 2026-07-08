# R5 Patch 20 Single Smoke Command Readout

status: `PASS_TOOLING_ADDED_STRICT_SMOKE_BLOCKED_BY_KNOWN_GATES`

## Scope

Patch 20 added a single R5 MVP smoke wrapper command:

```text
python scripts/run_r5_mvp_smoke.py
```

The wrapper records each subcheck command, exit code, duration, stdout, stderr, and summary. It does not call live APIs, does not generate real stock research, and does not output buy / sell / hold / position-sizing language.

## Files Added

```text
scripts/run_r5_mvp_smoke.py
tests/test_run_r5_mvp_smoke.py
reports/p1_6/r5_mvp_smoke_result.json
reports/p1_6/R5_PATCH_20_SINGLE_SMOKE_COMMAND_READOUT.md
```

## Files Modified

```text
None.
```

## Artifact Evidence

```text
line_count run_r5_mvp_smoke.py: 158
line_count test_run_r5_mvp_smoke.py: 97
checked=6 smoke subchecks
```

## Subchecks

```text
r5_artifact_format_guard
r5_patch_inventory_check
r5_pack_validators
r5_composer_fixture_smoke
r5_quality_fixture_smoke
r5_readout_truthfulness_gate
```

## Commands Run

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m py_compile scripts/run_r5_mvp_smoke.py
```

exit_code: `0`

stdout_or_stderr_summary:

```text
run_r5_mvp_smoke.py compiled successfully.
```

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe scripts/run_r5_mvp_smoke.py --strict --json reports/p1_6/r5_mvp_smoke_result.json
```

exit_code: `1`

stdout_or_stderr_summary:

```text
r5_mvp_smoke_status=fail checked=6 failed=2
r5_artifact_format_guard: exit_code=0
r5_patch_inventory_check: exit_code=1
r5_pack_validators: exit_code=0, 46 passed
r5_composer_fixture_smoke: exit_code=0, 12 passed
r5_quality_fixture_smoke: exit_code=0, 5 passed
r5_readout_truthfulness_gate: exit_code=1
```

This non-zero strict result is expected while Patch 15 inventory remains `accepted: false` and historical readouts still fail Patch 19 truthfulness rules. The wrapper correctly propagates those failures.

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m pytest -q tests/test_run_r5_mvp_smoke.py --tb=short
```

exit_code: `0`

stdout_or_stderr_summary:

```text
5 passed in 0.09s
```

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe -c "import json, pathlib; data=json.loads(pathlib.Path('reports/p1_6/r5_mvp_smoke_result.json').read_text(encoding='utf-8')); print(data['status'], data['checked'], data['failed']); [print(r['name'], r['exit_code'], r['duration_seconds'], bool(r['command']), bool(r['summary'])) for r in data['results']]"
```

exit_code: `0`

stdout_or_stderr_summary:

```text
fail 6 2
r5_artifact_format_guard 0 <duration_seconds> True True
r5_patch_inventory_check 1 <duration_seconds> True True
r5_pack_validators 0 <duration_seconds> True True
r5_composer_fixture_smoke 0 <duration_seconds> True True
r5_quality_fixture_smoke 0 <duration_seconds> True True
r5_readout_truthfulness_gate 1 <duration_seconds> True True
```

## Known TODOs

- `r5_patch_inventory_check` fails in strict mode because Patch 4-12 expected artifacts/readouts are not fully reconciled.
- `r5_readout_truthfulness_gate` fails in strict mode because older R5 readouts still lack command / exit-code / stdout-or-stderr evidence.
- Patch 20 does not enter real-sample pilot or P2. The next patch remains a source-gapped controlled pilot.

## Next Recommended Patch

```text
R5_PATCH_21_SOURCE_GAPPED_002837_R5_PACK.md
```
