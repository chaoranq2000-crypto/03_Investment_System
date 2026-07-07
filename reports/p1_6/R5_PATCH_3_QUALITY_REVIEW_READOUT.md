# R5 Patch 3 Readout — quality-review R5 issue validator

## Result

Status: completed_quality_issue_validator

This patch makes the R5 issue-list schema executable. It does not generate a real quality-review conclusion, does not modify historical workflow runs, does not hide TODO/source gaps, and does not output trading advice.

## Files changed

- `.agents/skills/quality-review/SKILL.md`
- `.agents/skills/quality-review/references/issue_schema.md`
- `.agents/skills/quality-review/references/r5_quality_gate.md`
- `.agents/skills/quality-review/assets/r5_quality_issues.example.csv`
- `.agents/skills/quality-review/scripts/validate_quality_issues.py`
- `tests/test_validate_quality_issues.py`
- `reports/p1_6/R5_PATCH_3_QUALITY_REVIEW_READOUT.md`

## Diff summary

- Added `stage` and `target_artifact` to the compact R5 issue schema.
- Added severity enum support for `critical`, `high`, `medium`, and `low`.
- Required R5-G1 through R5-G11 coverage, including R5-G10 No-Advice Gate.
- Required issue status enum: `open`, `resolved`, `accepted_todo`, and `waived_with_reason`.
- Kept high/critical issues from producing `accepted`.
- Preserved CLI compatibility with positional path, `--issues`, `--expected-decision`, and legacy `--outcome`.

## Tests

```bash
python .agents/skills/quality-review/scripts/validate_quality_issues.py .agents/skills/quality-review/assets/r5_quality_issues.example.csv --expected-decision accepted_with_todos
pytest tests/test_validate_quality_issues.py
```

Result:

```text
validator outcome: accepted_with_todos
tests/test_validate_quality_issues.py: 11 passed
tests/test_r5_foundation_assets.py: 6 passed
```

## High Issue Blocking Logic

Any active `critical` or `high` issue prevents `accepted`. Active high issues produce `needs_fix`; active critical issues produce `blocked`. Medium/low TODOs can only produce `accepted_with_todos` when they remain visible.
