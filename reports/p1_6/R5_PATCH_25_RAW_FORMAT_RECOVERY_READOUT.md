# R5 Patch 25 Raw Format Recovery Readout

status: `PASS_VERIFIED_NO_LINE_REWRITE_REQUIRED`

## Summary

Physical LF/multiline checks passed for gate scripts, templates, benchmark and tests. No sample-quality or P2 action was taken.

## files_added

- `reports/p1_6/R5_PATCH_25_RAW_FORMAT_RECOVERY_READOUT.md`

## files_modified

- `reports/p1_6/r5_format_guard.json`

## commands_run

1. command: `C:\Projects\03_Investment_System\.conda\investment-system\python.exe -m py_compile scripts/check_r5_artifact_format.py scripts/r5_patch_inventory_check.py scripts/check_r5_readout_truthfulness.py scripts/run_r5_mvp_smoke.py scripts/r5_readiness_gate.py`
   exit_code: `0`
   duration_seconds: `0.055`

   stdout_or_stderr_summary:

```text
(no stdout/stderr)
```

2. command: `C:\Projects\03_Investment_System\.conda\investment-system\python.exe -c
from pathlib import Path
paths = [
  'scripts/check_r5_artifact_format.py',
  'scripts/r5_patch_inventory_check.py',
  'scripts/check_r5_readout_truthfulness.py',
  'scripts/run_r5_mvp_smoke.py',
  'scripts/r5_readiness_gate.py',
  'templates/r5_stock_research_pack.yaml',
  'benchmarks/r5_report_quality_rubric.yaml',
  'tests/test_validate_r5_stock_research_pack.py',
  'tests/test_r5_readiness_gate.py',
]
for p in paths:
    text = Path(p).read_text(encoding='utf-8')
    lines = text.splitlines()
    assert len(lines) >= 8, (p, len(lines))
    assert not (lines and lines[0].startswith('#!') and 'from __future__' in lines[0]), p
    assert text.count('\\n') < max(20, len(lines)), p
print('physical format recovery ok')
`
   exit_code: `0`
   duration_seconds: `0.036`

   stdout_or_stderr_summary:

```text
physical format recovery ok
```

3. command: `C:\Projects\03_Investment_System\.conda\investment-system\python.exe scripts/check_r5_artifact_format.py --strict --json reports/p1_6/r5_format_guard.json`
   exit_code: `0`
   duration_seconds: `0.529`

   stdout_or_stderr_summary:

```text
status=pass checked=24 passed=24 failed=0
```

## artifact_evidence

| path | exists | line_count | sha256 |
|---|---:|---:|---|
| `scripts/check_r5_artifact_format.py` | yes | 262 | `d387b558b89156b9a70228474cfdf7446f4046d096e6c63eae68ebc5cb457023` |
| `scripts/r5_patch_inventory_check.py` | yes | 253 | `9e4ccff1723b6a3a7092ed221e1c83b2323e1b9b67de23c4a85efc50fcf2e77d` |
| `scripts/check_r5_readout_truthfulness.py` | yes | 182 | `75f66e24596d28c0c92c460da696706a6b8aede21715f6a1cf686b599cdcbbb4` |
| `scripts/run_r5_mvp_smoke.py` | yes | 196 | `b294d57b7566335f8d1c3420c7b2bb719973a8035e45e11b53b17b6faad81b2f` |
| `scripts/r5_readiness_gate.py` | yes | 191 | `8b18565d15373dce3e9a72886099c6d3644be128931c39d8028ff1be4b245ea2` |
| `reports/p1_6/r5_format_guard.json` | yes | 181 | `914e3e7ecdb783bcfaf7e19939b2c56a6b47d78db0b8a4cd9bd65e714e646216` |

## known_todos

- No semantic research TODO changed; source-gapped R5 TODOs remain visible.

## next_recommended_patch

`R5_PATCH_26_EXECUTABLE_GUARD_OF_GUARDS`
