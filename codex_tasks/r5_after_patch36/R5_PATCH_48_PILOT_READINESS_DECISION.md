# R5 Patch 48 - Pilot Readiness Decision

## Goal

Close Patch 37-47 with a canonical readiness decision that says whether 002837 may enter a reviewed-input pilot, while keeping sample-quality and P2 closed unless gates pass.

## Background

Current Patch 36 close gate forbids source-gapped real sample pilot, sample-quality report and P2. After the reviewed-input layer is added, the project needs a new close gate that distinguishes:

- no pilot allowed,
- reviewed-input pilot allowed,
- sample-quality candidate allowed,
- P2 allowed.

## Allowed files

- `scripts/r5_reviewed_input_pilot_gate.py`
- `config/r5_reviewed_input_pilot_gate_rules.yaml`
- `tests/test_r5_reviewed_input_pilot_gate.py`
- `reports/p1_6/R5_AFTER_PATCH36_REVIEWED_INPUT_CLOSE_READOUT.md`
- `reports/p1_6/r5_reviewed_input_pilot_gate_result.json`

## Required behavior

1. Gate consumes:
   - strict smoke result,
   - pack promotion gate result,
   - quality scorecard v2,
   - reviewed input dry-run result,
   - no-advice gate status.
2. Gate outputs:
   - `current_r5_state`
   - `reviewed_input_pilot_allowed`
   - `sample_quality_report_allowed`
   - `p2_allowed`
   - `blockers`
   - `non_blocking_todos`
   - `next_candidate_tasks`
3. If any critical TODO remains, sample-quality and P2 must remain false.
4. If reviewed market/peer/forecast inputs are absent, reviewed-input pilot must remain false.
5. Readout must be canonical and must include command evidence.

## Tests

```bash
python -m py_compile scripts/r5_reviewed_input_pilot_gate.py
python -m pytest -q tests/test_r5_reviewed_input_pilot_gate.py --tb=short
python scripts/r5_reviewed_input_pilot_gate.py --json reports/p1_6/r5_reviewed_input_pilot_gate_result.json
```

## Readout

Add `reports/p1_6/R5_AFTER_PATCH36_REVIEWED_INPUT_CLOSE_READOUT.md`.


## Global boundaries

- Do not call live APIs.
- Do not download unreviewed external files.
- Do not generate buy / sell / hold / position-size advice.
- Do not promote `TODO_*`, `MISSING_DISCLOSURE`, `LOW_CONFIDENCE_CLUE_ONLY`, or `evidence_id: null` into facts.
- Do not mark sample-quality or P2 ready unless the explicit readiness gate allows it.
- Do not rewrite historical legacy readouts; add canonical readouts only.
- Every patch must add a readout under `reports/p1_6/` with: files_added, files_modified, commands_run, exit_code, stdout/stderr summary, artifact_evidence, known_todos, and next_recommended_patch.
