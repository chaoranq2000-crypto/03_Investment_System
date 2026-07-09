# R5 Patch 46 - Quality Gate Scorecard V2

## Goal

Extend quality-review from pass/fail issue list to an R5 section scorecard that can explain why the output is not sample-quality.

## Background

R5 needs more than structural validation. It needs section-level readiness: financial, business, industry, forecast, valuation, technical, sentiment/event, risk/counterevidence, narrative coherence and no-advice.

## Allowed files

- `.agents/skills/quality-review/references/r5_quality_scorecard_v2.md`
- `.agents/skills/quality-review/assets/r5_quality_scorecard.example.yaml`
- `.agents/skills/quality-review/scripts/validate_r5_quality_scorecard.py`
- `tests/test_validate_r5_quality_scorecard.py`
- `reports/p1_6/R5_PATCH_46_QUALITY_GATE_SCORECARD_V2_READOUT.md`

## Required behavior

1. Define section readiness states:
   - `ready`
   - `ready_with_limitations`
   - `source_gapped`
   - `blocked`
2. Each section score must include:
   - `section_id`
   - `readiness`
   - `evidence_ids`
   - `issues`
   - `limitations`
   - `fix_owner_skill`
3. Overall output must include:
   - `allowed_report_level`
   - `sample_quality_blockers`
   - `next_actions`
4. Validator must reject any scorecard that marks forecast or valuation ready without reviewed assumptions/market/peer inputs.

## Tests

```bash
python -m py_compile .agents/skills/quality-review/scripts/validate_r5_quality_scorecard.py
python -m pytest -q tests/test_validate_r5_quality_scorecard.py --tb=short
```

## Readout

Add `reports/p1_6/R5_PATCH_46_QUALITY_GATE_SCORECARD_V2_READOUT.md`.


## Global boundaries

- Do not call live APIs.
- Do not download unreviewed external files.
- Do not generate buy / sell / hold / position-size advice.
- Do not promote `TODO_*`, `MISSING_DISCLOSURE`, `LOW_CONFIDENCE_CLUE_ONLY`, or `evidence_id: null` into facts.
- Do not mark sample-quality or P2 ready unless the explicit readiness gate allows it.
- Do not rewrite historical legacy readouts; add canonical readouts only.
- Every patch must add a readout under `reports/p1_6/` with: files_added, files_modified, commands_run, exit_code, stdout/stderr summary, artifact_evidence, known_todos, and next_recommended_patch.
