# R5 Patch 2 Readout — R5 pack schema validator

## Result

Status: completed_validator_contract

This patch upgrades the R5 stock research pack validator to emit machine-readable JSON issue lists while keeping the earlier `validate_pack()` string-list API for legacy tests.

## Files changed

- `.agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py`
- `.agents/skills/stock-deep-dive/assets/r5_stock_research_pack.valid.example.yaml`
- `.agents/skills/stock-deep-dive/assets/r5_stock_research_pack.invalid.example.yaml`
- `.agents/skills/stock-deep-dive/assets/r5_stock_research_pack.example.yaml`
- `templates/r5_stock_research_pack.yaml`
- `tests/test_r5_stock_research_pack_schema.py`
- `reports/p1_6/R5_PATCH_2_R5_PACK_SCHEMA_VALIDATOR_READOUT.md`

## Diff summary

- Added `validate_pack_issues()` with issue objects containing `issue_id`, `severity`, `path`, `description`, and `next_action`.
- CLI now prints JSON with `decision` and `issues`.
- Added positive and negative fixtures.
- Added tests for missing core packs, source references, null missing reasons, `as_of_date`, forecast years, valuation market snapshot, no-advice readiness, and hidden TODO/source gaps.

## Tests

```bash
python -m py_compile .agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py
pytest tests/test_r5_stock_research_pack_schema.py
```

Result:

```text
py_compile passed
tests/test_r5_stock_research_pack_schema.py: 9 passed
tests/test_validate_r5_stock_research_pack.py: 7 passed (legacy regression)
```

## Source gaps and TODOs

- Validator is schema/contract only and uses fixture data.
- It does not acquire evidence, call live APIs, generate real forecast values, or calculate valuation.
