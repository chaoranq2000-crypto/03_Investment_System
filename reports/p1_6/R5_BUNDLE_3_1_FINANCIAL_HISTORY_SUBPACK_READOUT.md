# R5 Bundle 3.1 Financial History Subpack Readout

status: accepted_with_todos

## files_added

- `.agents/skills/stock-deep-dive/references/r5_financial_history_pack_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_financial_history_pack.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_financial_history_pack.py`
- `tests/test_validate_r5_financial_history_pack.py`
- `reports/p1_6/R5_BUNDLE_3_1_FINANCIAL_HISTORY_SUBPACK_READOUT.md`

## files_modified

- `.agents/skills/stock-deep-dive/SKILL.md`

## commands_run

- `.\\.conda\\investment-system\\python.exe -m py_compile .agents\\skills\\stock-deep-dive\\scripts\\validate_r5_financial_history_pack.py .agents\\skills\\stock-deep-dive\\scripts\\validate_r5_business_breakdown_pack.py`
- `.\\.conda\\investment-system\\python.exe .agents\\skills\\stock-deep-dive\\scripts\\validate_r5_financial_history_pack.py --input .agents\\skills\\stock-deep-dive\\assets\\r5_financial_history_pack.example.yaml`
- `.\\.conda\\investment-system\\python.exe -m pytest -q tests\\test_validate_r5_financial_history_pack.py tests\\test_validate_r5_business_breakdown_pack.py --tb=short`

## exit_code

- py_compile: 0
- validator CLI: 0
- pytest subset: 0

## stdout_or_stderr_summary

- validator CLI: `outcome: accepted_with_todos`
- pytest subset: `8 passed in 0.11s`
- stderr: none observed

## artifact_evidence

- critical_evidence: checked=5 declared Bundle 3.1 artifacts.
- Example YAML preserves `TODO_MODEL_INPUT` and does not include real company financial values.
- Validator rejects non-null metrics without `evidence_id` or `metric_id`.
- Validator rejects `status: ready` with hidden TODO or missing markers.

## known_todos

- Financial history values remain TODO in the example asset.
- Sample-quality and P2 remain unavailable.

## next_recommended_patch

- R5 Bundle 3.2 - Business Breakdown Subpack Contract
