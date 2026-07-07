# R5 Patch 1 Readout — R5 pack validator and example

## Result

Status: completed_validator_and_example

This patch adds/updates the executable validator for `R5_stock_research_pack.yaml` and keeps the example pack as a source-gapped research draft. It does not create a real stock research pack, fetch data, calculate forecast/valuation, or write a real report.

## Modified files

- `.agents/skills/stock-deep-dive/references/r5_stock_research_pack_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_stock_research_pack.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py`
- `tests/test_validate_r5_stock_research_pack.py`
- `reports/p1_6/R5_PATCH_1_PACK_VALIDATOR_READOUT.md`

## Added files

- `.agents/skills/stock-deep-dive/assets/r5_stock_research_pack.valid.example.yaml`
- `.agents/skills/stock-deep-dive/assets/r5_stock_research_pack.invalid.example.yaml`
- `tests/test_r5_stock_research_pack_schema.py`

## Diff summary

- Validator now checks the official `pack_status` enum: `sample_quality_candidate`, `research_draft`, `blocked`, `needs_fix`.
- Validator checks the 12 required subpacks, visible TODO/MISSING source gaps, material source references, technical/sentiment `as_of_date`, forecast year coverage, valuation market snapshot gating, and no-advice scan.
- CLI emits JSON with `decision` and issue objects.
- Example pack remains `research_draft`, with forecast/valuation/business gaps visible.

## Tests

```bash
python .agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py .agents/skills/stock-deep-dive/assets/r5_stock_research_pack.example.yaml
pytest tests/test_validate_r5_stock_research_pack.py
```

Result:

```text
validator decision: accepted_with_todos
issues: []
tests/test_validate_r5_stock_research_pack.py: 9 passed
tests/test_r5_stock_research_pack_schema.py: 9 passed
```

## Remaining TODOs

- Forecast, valuation, technical, sentiment, and composer validators are intentionally not implemented in this patch.
- `sample_quality_candidate` remains blocked unless forecast, valuation, market snapshot, business breakdown, no-advice, and source-gap visibility gates pass.
