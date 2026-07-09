# R5 Patch 51 - Reviewed input dropzone validators

## Goal

Add validators that can reject invalid reviewed-input dropzone files before any registry promotion is attempted.

## Background

A manual dropzone only helps if accepted rows cannot carry TODOs, missing evidence IDs, missing dates, or unreviewed status. This patch should enforce that boundary.

## Allowed files

- `scripts/validate_r5_reviewed_input_dropzone.py`
- `tests/test_validate_r5_reviewed_input_dropzone.py`
- `tests/fixtures/r5_reviewed_inputs/valid_pending/`
- `tests/fixtures/r5_reviewed_inputs/valid_accepted_degraded/`
- `tests/fixtures/r5_reviewed_inputs/invalid_accepted_todo/`
- `tests/fixtures/r5_reviewed_inputs/invalid_missing_evidence/`
- `reports/p1_6/R5_PATCH_51_REVIEWED_INPUT_DROPZONE_VALIDATORS_READOUT.md`

## Required behavior

1. The validator must read CSV and YAML inputs from a provided root path.
2. It must return a JSON summary with:

```text
status
checked_files
accepted_count
accepted_degraded_count
pending_count
rejected_count
failed_count
issues
```

3. Accepted rows must require:

```text
source_evidence_id
source_rank
as_of_date
review_status
reviewer
reviewed_at
limitations
```

4. Accepted rows must fail if they contain any of:

```text
TODO_MARKET_DATA
TODO_PEER_DATA
TODO_MODEL_INPUT
TODO_SOURCE_REQUIRED
MISSING_DISCLOSURE
LOW_CONFIDENCE_CLUE_ONLY
```

5. Pending and rejected rows may contain TODOs, but they must not unblock any gate.
6. `accepted_degraded` must have `sample_quality_allowed: false` or equivalent limitation metadata.
7. The validator should be usable both as a CLI and from tests.

## Tests

```bash
python -m py_compile scripts/validate_r5_reviewed_input_dropzone.py
python -m pytest -q tests/test_validate_r5_reviewed_input_dropzone.py --tb=short
python scripts/validate_r5_reviewed_input_dropzone.py --root tests/fixtures/r5_reviewed_inputs/valid_pending --json reports/p1_6/r5_reviewed_input_dropzone_valid_pending.json
```

## Readout

Add `reports/p1_6/R5_PATCH_51_REVIEWED_INPUT_DROPZONE_VALIDATORS_READOUT.md`.

## Global boundaries

- Do not call live APIs.
- Do not use external downloads.
- Do not modify real 002837 registries yet.
- Do not mark sample-quality or P2 ready.
