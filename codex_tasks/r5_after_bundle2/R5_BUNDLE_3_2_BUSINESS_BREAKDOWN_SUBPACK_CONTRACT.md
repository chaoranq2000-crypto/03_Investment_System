# R5 Bundle 3.2 — Business breakdown subpack contract and validator

## Background

Current R5 packs preserve business disclosure gaps, especially revenue percentage, gross margin and profit contribution. R5 needs a standalone business breakdown contract to prevent clue-only product exposure from becoming a factual business split.

## Goal

Add a business breakdown subpack contract, example YAML, validator and pytest coverage.

## Allowed files

- `.agents/skills/stock-deep-dive/references/r5_business_breakdown_pack_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_business_breakdown_pack.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_business_breakdown_pack.py`
- `tests/test_validate_r5_business_breakdown_pack.py`
- `.agents/skills/stock-deep-dive/SKILL.md` only for a minimal reference link
- `reports/p1_6/R5_BUNDLE_3_2_BUSINESS_BREAKDOWN_SUBPACK_READOUT.md`

## Forbidden scope

- Do not modify real workflow run artifacts.
- Do not infer undisclosed business revenue or margin.
- Do not turn product, customer, capacity or order clues into revenue exposure without reviewed metrics.
- Do not mark sample-quality ready.

## Required contract behavior

The business breakdown subpack must define:

```text
artifact_type
schema_version
status
as_of_date
stock_code
business_lines
profit_pool_summary
structural_contradictions
linked_segments
missing_items
source_gap_register
```

Each business line must support:

```text
business_name
role
revenue
revenue_pct
gross_margin
gross_profit
gross_profit_pct
products
customers
capacity
orders
pricing_driver
cost_driver
linked_segments
confidence
evidence_ids
missing_items
```

Validator rules:

- `business_lines` must be a non-empty list.
- Each core metric object must contain `value`, `unit` when applicable, `evidence_id` or `metric_id`, and `missing_reason` when value is null.
- Non-null revenue, margin or profit metrics require `evidence_id` or `metric_id`.
- Null revenue, margin or profit metrics require explicit `MISSING_DISCLOSURE` or `TODO_SOURCE_REQUIRED` reason.
- `confidence` must be present.
- `status: ready` requires no core business metric to be null unless marked `NOT_APPLICABLE` with evidence.
- Product clues alone cannot set `confidence: high`.

## Acceptance criteria

- Example YAML parses and validates as `accepted_with_todos` if missing disclosure is visible.
- Validator fails a business line that has a non-null revenue percentage without evidence or metric support.
- Validator fails `status: ready` with hidden missing disclosure.
- Pytest covers valid, TODO and invalid cases.

## Suggested tests

```bash
python -m py_compile .agents/skills/stock-deep-dive/scripts/validate_r5_business_breakdown_pack.py
python .agents/skills/stock-deep-dive/scripts/validate_r5_business_breakdown_pack.py --input .agents/skills/stock-deep-dive/assets/r5_business_breakdown_pack.example.yaml
python -m pytest -q tests/test_validate_r5_business_breakdown_pack.py --tb=short
git diff --check
```

## Output requirements

- List changed files.
- Include validator outcome.
- Include pytest result.
- Write the readout file.
