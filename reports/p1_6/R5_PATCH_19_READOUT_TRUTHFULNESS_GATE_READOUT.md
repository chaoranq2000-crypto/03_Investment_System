# R5 Patch 19 Readout Truthfulness Gate Readout

status: `PASS_TOOLING_ADDED_HISTORICAL_READOUTS_FAIL`

## Scope

Patch 19 added a readout truthfulness gate for R5 patch readouts. It checks whether readouts contain auditable command evidence instead of bare claims like `pytest passed`.

This patch does not generate research conclusions, call live APIs, alter historical workflow-run conclusions, or output buy / sell / hold / position-sizing language.

## Files Added

```text
scripts/check_r5_readout_truthfulness.py
config/r5_readout_truthfulness_rules.yaml
tests/test_r5_readout_truthfulness.py
reports/p1_6/R5_PATCH_19_READOUT_TRUTHFULNESS_GATE_READOUT.md
```

## Files Modified

```text
reports/p1_6/R5_PATCH_13_FORMAT_SYNTAX_RECOVERY_READOUT.md
reports/p1_6/R5_PATCH_16_VALIDATOR_SEMANTIC_HARDENING_READOUT.md
reports/p1_6/R5_PATCH_17_COMPOSER_REPAIR_READOUT.md
reports/p1_6/R5_PATCH_18_REPRODUCIBLE_FIXTURE_SMOKE_READOUT.md
```

Those readout edits only added missing audit evidence fields; they did not change the recorded outcomes.

## Path Note

The task card suggested `configs/r5_readout_truthfulness_rules.yaml`, but this repository already uses the top-level `config/` directory. To follow `AGENTS.md` placement rules and avoid an ad hoc top-level folder, the rules file was added at:

```text
config/r5_readout_truthfulness_rules.yaml
```

## Artifact Evidence

```text
line_count check_r5_readout_truthfulness.py: 119
line_count test_r5_readout_truthfulness.py: 90
checked=22 R5_PATCH_*_READOUT.md files
```

## Commands Run

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m py_compile scripts/check_r5_readout_truthfulness.py
```

exit_code: `0`

stdout_or_stderr_summary:

```text
check_r5_readout_truthfulness.py compiled successfully.
```

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe scripts/check_r5_readout_truthfulness.py --rules config/r5_readout_truthfulness_rules.yaml --glob 'reports/p1_6/R5_PATCH_*_READOUT.md'
```

first_exit_code: `0`

first_stdout_or_stderr_summary:

```text
truthfulness_status=fail checked=22 failed=20
```

fix:

```text
Added missing stdout_or_stderr_summary / artifact evidence fields to Patch 13 and Patch 16-18 readouts.
```

rerun_exit_code: `0`

rerun_stdout_or_stderr_summary:

```text
truthfulness_status=fail checked=22 failed=16
```

The remaining 16 failures are historical readouts from earlier R5 work. Patch 19 reports them as truthfulness failures but does not silently rewrite them.

```text
C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m pytest -q tests/test_r5_readout_truthfulness.py --tb=short
```

exit_code: `0`

stdout_or_stderr_summary:

```text
4 passed in 0.08s
```

## Known TODOs

- Historical readouts `R5_PATCH_0A` and `R5_PATCH_1` through `R5_PATCH_12` still fail the truthfulness gate because they lack command / exit-code / stdout-or-stderr evidence.
- If those older readouts must become canonical, add compatibility evidence readouts instead of rewriting conclusions silently.
- Patch 15 inventory remains `accepted: false`; Patch 19 does not override it.

## Next Recommended Patch

```text
R5_PATCH_20_R5_SINGLE_SMOKE_COMMAND.md
```
