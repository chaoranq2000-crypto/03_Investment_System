# R5 Patch 47 - Composer Research Draft Plus Mode

## Goal

Add a composer mode between source-gapped draft and sample-quality: `reviewed_input_research_draft`. It can use reviewed sections, but must visibly preserve unresolved gaps.

## Background

Patch 35 keeps source-gapped output conservative. Once some reviewed inputs exist, the composer should be able to upgrade only the reviewed sections without upgrading the full report to sample-quality.

## Allowed files

- `src/report/stock_report_writer.py`
- `tests/test_r5_composer_research_draft_plus.py`
- `reports/p1_6/R5_PATCH_47_COMPOSER_RESEARCH_DRAFT_PLUS_MODE_READOUT.md`

## Required behavior

1. Add a mode: `reviewed_input_research_draft`.
2. Composer may render reviewed market/peer/forecast sections only if the corresponding gate says ready.
3. Composer must include a source-gap appendix and open questions when gaps remain.
4. Composer must not include:
   - buy/sell/hold language,
   - position or timing advice,
   - sample-quality label unless promotion gate allows it,
   - unsupported numbers.
5. Tests must prove mixed readiness sections render correctly.

## Tests

```bash
python -m py_compile src/report/stock_report_writer.py
python -m pytest -q tests/test_r5_composer_research_draft_plus.py tests/test_r5_report_composer_degradation.py --tb=short
```

## Readout

Add `reports/p1_6/R5_PATCH_47_COMPOSER_RESEARCH_DRAFT_PLUS_MODE_READOUT.md`.


## Global boundaries

- Do not call live APIs.
- Do not download unreviewed external files.
- Do not generate buy / sell / hold / position-size advice.
- Do not promote `TODO_*`, `MISSING_DISCLOSURE`, `LOW_CONFIDENCE_CLUE_ONLY`, or `evidence_id: null` into facts.
- Do not mark sample-quality or P2 ready unless the explicit readiness gate allows it.
- Do not rewrite historical legacy readouts; add canonical readouts only.
- Every patch must add a readout under `reports/p1_6/` with: files_added, files_modified, commands_run, exit_code, stdout/stderr summary, artifact_evidence, known_todos, and next_recommended_patch.
