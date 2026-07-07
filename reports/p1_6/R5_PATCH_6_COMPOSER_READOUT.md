# R5 Patch 6 Readout — composer skeleton

## Result

Status: completed_composer_skeleton

This patch adds a lightweight composer that translates an R5 research pack fixture into a Markdown note skeleton. It does not generate a real stock report, read live data, use company knowledge outside the pack, create new numbers, hide TODO/source gaps, or output trading advice.

## Files changed

- `.agents/skills/stock-deep-dive/references/r5_report_composer_contract.md`
- `.agents/skills/stock-deep-dive/scripts/compose_r5_report_from_pack.py`
- `.agents/skills/stock-deep-dive/assets/r5_stock_research_note.fixture.md`
- `tests/test_compose_r5_report_from_pack.py`
- `reports/p1_6/R5_PATCH_6_COMPOSER_READOUT.md`

## Tests

```bash
python .agents/skills/stock-deep-dive/scripts/compose_r5_report_from_pack.py .agents/skills/stock-deep-dive/assets/r5_stock_research_pack.example.yaml .agents/skills/stock-deep-dive/assets/r5_stock_research_note.fixture.md
pytest tests/test_compose_r5_report_from_pack.py
```

Result:

```text
composer output: OK .agents/skills/stock-deep-dive/assets/r5_stock_research_note.fixture.md
tests/test_compose_r5_report_from_pack.py: 5 passed
```

## Downgrade behavior

When `pack_status` is not `sample_quality_candidate`, the generated note metadata marks the output as `research_draft`, `needs_fix`, or `blocked`. Source gaps remain visible in Source Gap Appendix.
