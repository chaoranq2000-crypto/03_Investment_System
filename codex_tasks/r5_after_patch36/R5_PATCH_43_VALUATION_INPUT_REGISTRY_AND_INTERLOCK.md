# R5 Patch 43 - Valuation Input Registry and Interlock

## Goal

Create a valuation input registry that combines reviewed market snapshot, peer snapshot, forecast outputs and limitations. It must block valuation outputs when any required reviewed input is missing.

## Background

Current readiness gate blocks sample-quality due valuation TODOs. Valuation should not be produced merely because forecast or market stubs exist.

## Allowed files

- `.agents/skills/stock-deep-dive/references/r5_valuation_input_registry_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_valuation_input_registry.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_valuation_inputs.py`
- `tests/test_validate_r5_valuation_inputs.py`
- `reports/p1_6/R5_PATCH_43_VALUATION_INPUT_REGISTRY_AND_INTERLOCK_READOUT.md`

## Required behavior

1. Registry must reference:
   - reviewed market snapshot path / evidence IDs,
   - reviewed peer snapshot path / evidence IDs,
   - forecast model path / assumption IDs,
   - valuation method eligibility.
2. Relative PE / PB / PS valuation may become eligible only when peer data and market snapshot are reviewed.
3. SOTP may become eligible only when business-line split is reviewed or explicitly scoped.
4. DCF may become eligible only when forecast cashflow assumptions are reviewed.
5. If inputs are TODO, validator must return `source_gapped_research_draft` or `blocked_for_sample_quality`, not pass sample-quality.

## Tests

```bash
python -m py_compile .agents/skills/stock-deep-dive/scripts/validate_r5_valuation_inputs.py
python -m pytest -q tests/test_validate_r5_valuation_inputs.py --tb=short
```

## Readout

Add `reports/p1_6/R5_PATCH_43_VALUATION_INPUT_REGISTRY_AND_INTERLOCK_READOUT.md`.


## Global boundaries

- Do not call live APIs.
- Do not download unreviewed external files.
- Do not generate buy / sell / hold / position-size advice.
- Do not promote `TODO_*`, `MISSING_DISCLOSURE`, `LOW_CONFIDENCE_CLUE_ONLY`, or `evidence_id: null` into facts.
- Do not mark sample-quality or P2 ready unless the explicit readiness gate allows it.
- Do not rewrite historical legacy readouts; add canonical readouts only.
- Every patch must add a readout under `reports/p1_6/` with: files_added, files_modified, commands_run, exit_code, stdout/stderr summary, artifact_evidence, known_todos, and next_recommended_patch.
