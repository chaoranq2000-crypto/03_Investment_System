# R5 Patch 2 Readout — segment-company-mapping validator and examples

## Result

Status: completed_exposure_validator

This patch tightens the `segment_exposure.yaml` contract for R5 handoff use. It does not update a real global exposure registry, does not promote product clues into revenue exposure, does not generate a stock report, and does not call real APIs.

## Files changed

- `.agents/skills/segment-company-mapping/SKILL.md`
- `.agents/skills/segment-company-mapping/references/exposure_schema.md`
- `.agents/skills/segment-company-mapping/references/backflow_decision_rules.md`
- `.agents/skills/segment-company-mapping/assets/segment_exposure.example.yaml`
- `.agents/skills/segment-company-mapping/assets/segment_company_exposure.example.csv`
- `.agents/skills/segment-company-mapping/scripts/validate_segment_exposure.py`
- `tests/test_validate_segment_exposure.py`
- `reports/p1_6/R5_PATCH_2_SEGMENT_MAPPING_READOUT.md`

## Diff summary

- Aligned `exposure_type` with the R5 enum: `revenue`, `profit`, `product_line_clue`, `customer_clue`, `order_clue`, `capacity_clue`, `technology_reserve`, `project_clue`, and `narrative_only`.
- Added `needs_review` to the backflow decision contract.
- Enforced integer `exposure_score` in the 0-5 range.
- Enforced explicit `MISSING_DISCLOSURE` or `NOT_DISCLOSED` for missing `revenue_pct` / `profit_pct`.
- Kept product-line clues from becoming revenue exposure updates.
- Kept CLI compatibility with both positional path and `--input`.

## Tests

```bash
python .agents/skills/segment-company-mapping/scripts/validate_segment_exposure.py .agents/skills/segment-company-mapping/assets/segment_exposure.example.yaml
pytest tests/test_validate_segment_exposure.py
```

Result:

```text
validator outcome: accepted_with_todos
tests/test_validate_segment_exposure.py: 9 passed
```

## Remaining TODOs

- Real exposure registry updates remain out of scope.
- Product/customer/order/capacity clues remain clue-level until reviewed evidence supports stronger exposure.
