# R5 Patch 45 - R5 Pack Promotion Gate

## Goal

Create a promotion gate that decides whether an R5 pack may move from `source_gapped_research_draft` to `reviewed_input_research_draft` or `sample_quality_candidate`.

## Background

Current readiness says contracts are executable with TODOs. The next decision layer should evaluate specific pack sections and reviewed inputs rather than relying only on smoke status.

## Allowed files

- `scripts/r5_pack_promotion_gate.py`
- `config/r5_pack_promotion_rules.yaml`
- `tests/test_r5_pack_promotion_gate.py`
- `reports/p1_6/R5_PATCH_45_R5_PACK_PROMOTION_GATE_READOUT.md`

## Required behavior

Promotion levels:

1. `blocked`
2. `source_gapped_research_draft`
3. `reviewed_input_research_draft`
4. `sample_quality_candidate`

Gate checks:

- evidence completeness
- business disclosure gaps
- reviewed market snapshot
- reviewed peer snapshot
- reviewed forecast assumptions
- valuation input eligibility
- no-advice gate
- hidden TODO check
- source gap visibility

`sample_quality_candidate` must require all of the following:

- no high issues
- no hidden TODOs
- reviewed business/forecast/valuation/market/peer inputs
- source gaps visible if any remain
- no direct trading instructions

## Tests

```bash
python -m py_compile scripts/r5_pack_promotion_gate.py
python -m pytest -q tests/test_r5_pack_promotion_gate.py --tb=short
```

## Readout

Add `reports/p1_6/R5_PATCH_45_R5_PACK_PROMOTION_GATE_READOUT.md`.


## Global boundaries

- Do not call live APIs.
- Do not download unreviewed external files.
- Do not generate buy / sell / hold / position-size advice.
- Do not promote `TODO_*`, `MISSING_DISCLOSURE`, `LOW_CONFIDENCE_CLUE_ONLY`, or `evidence_id: null` into facts.
- Do not mark sample-quality or P2 ready unless the explicit readiness gate allows it.
- Do not rewrite historical legacy readouts; add canonical readouts only.
- Every patch must add a readout under `reports/p1_6/` with: files_added, files_modified, commands_run, exit_code, stdout/stderr summary, artifact_evidence, known_todos, and next_recommended_patch.
