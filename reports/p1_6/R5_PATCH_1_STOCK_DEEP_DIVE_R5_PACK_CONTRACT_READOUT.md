# R5 Patch 1 Readout — stock-deep-dive R5 pack contract

## Result

Status: completed_contract_only

This patch adds the stock-deep-dive R5 local contract layer. It does not claim R5 is complete, does not generate a real stock report, and does not add evidence acquisition, live API, forecast calculation, or valuation calculation responsibilities to `stock-deep-dive`.

## Files changed

- `.agents/skills/stock-deep-dive/SKILL.md`
- `.agents/skills/stock-deep-dive/references/r5_stock_research_pack_contract.md`
- `.agents/skills/stock-deep-dive/references/r5_report_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_stock_research_pack_template.yaml`
- `.agents/skills/stock-deep-dive/assets/r5_source_gap_report_template.md`
- `reports/p1_6/R5_PATCH_1_STOCK_DEEP_DIVE_R5_PACK_CONTRACT_READOUT.md`

## Diff summary

- Added `SDD-R5-0` to `SDD-R5-5` local procedure steps.
- Expanded the R5 research pack contract with the 12 subpack list, required/optional/blocked fields, traceability fields, R4-to-R5 mapping, downgrade states, and quality-review handoff fields.
- Added report-composition rules that keep writer/composer layers from creating new facts.
- Added R5 pack and source-gap templates with visible TODO and missing-data placeholders.

## Tests

Pending in this readout until Batch A validation step:

```bash
python - <<'PY'
from pathlib import Path
required = [
    '.agents/skills/stock-deep-dive/references/r5_stock_research_pack_contract.md',
    '.agents/skills/stock-deep-dive/references/r5_report_contract.md',
    '.agents/skills/stock-deep-dive/assets/r5_stock_research_pack_template.yaml',
]
for p in required:
    assert Path(p).exists(), p
print('r5 stock-deep-dive contract files exist')
PY
```

## Source gaps and TODOs

- R5 remains contract-level only after this patch.
- Real forecast, valuation, market, technical, sentiment, and event data remain TODO unless supplied by reviewed upstream assets.
- Quality-review gate, schema validator, financial/business validator, and evidence snapshot validator are handled by later Batch A patches.
