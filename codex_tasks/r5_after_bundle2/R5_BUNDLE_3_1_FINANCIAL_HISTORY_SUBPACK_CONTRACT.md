# R5 Bundle 3.1 — Financial history subpack contract and validator

## Background

Bundle 2 locked the R5 foundation, but `financial_history_pack` is still only a broad placeholder. R5 cannot approach sample-quality until financial history, financial quality and adjusted-profit bridge fields are independently checkable.

## Goal

Add a standalone financial history subpack contract, example YAML, validator and pytest coverage.

## Allowed files

- `.agents/skills/stock-deep-dive/references/r5_financial_history_pack_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_financial_history_pack.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_financial_history_pack.py`
- `tests/test_validate_r5_financial_history_pack.py`
- `.agents/skills/stock-deep-dive/SKILL.md` only for a minimal reference link
- `reports/p1_6/R5_BUNDLE_3_1_FINANCIAL_HISTORY_SUBPACK_READOUT.md`

## Forbidden scope

- Do not modify real workflow run artifacts.
- Do not populate real company financial data.
- Do not call live APIs.
- Do not write a report.
- Do not mark sample-quality ready.

## Required contract behavior

The financial history subpack must define at least:

```text
artifact_type
schema_version
status
as_of_date
currency
periods
income_statement
balance_sheet
cashflow_statement
key_metrics
financial_quality
adjusted_profit_bridge
cashflow_quality
working_capital_flags
roe_roic_commentary
evidence_ids
missing_items
```

Metric rows must use a consistent shape such as:

```text
metric_name
period
value
unit
currency
evidence_id or metric_id
missing_reason
```

Validator rules:

- Root must be a mapping.
- `artifact_type` must identify the financial history subpack.
- `status` must be one of `TODO`, `partial`, `ready`, `blocked`.
- `periods` must be a list if present.
- A non-null numeric value requires `evidence_id` or `metric_id`.
- A null value requires `missing_reason` or inclusion in `missing_items`.
- `status: ready` is forbidden if required financial sections are empty.
- Hidden TODOs must not be allowed when `status: ready`.

## Acceptance criteria

- Example YAML parses.
- Validator outputs `accepted_with_todos` for the example if it intentionally contains TODO/missing fields.
- Validator returns nonzero for unsupported non-null metrics.
- Pytest covers valid, TODO and invalid cases.
- No direct trading instruction language is introduced.

## Suggested tests

```bash
python -m py_compile .agents/skills/stock-deep-dive/scripts/validate_r5_financial_history_pack.py
python .agents/skills/stock-deep-dive/scripts/validate_r5_financial_history_pack.py --input .agents/skills/stock-deep-dive/assets/r5_financial_history_pack.example.yaml
python -m pytest -q tests/test_validate_r5_financial_history_pack.py --tb=short
git diff --check
```

## Output requirements

- List changed files.
- Include validator outcome.
- Include pytest result.
- Write the readout file.
