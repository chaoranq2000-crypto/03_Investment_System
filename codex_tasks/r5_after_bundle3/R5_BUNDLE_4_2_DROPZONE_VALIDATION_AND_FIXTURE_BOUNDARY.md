# R5 Bundle 4.2 — Dropzone validation and fixture boundary

## Background

The dropzone validator already requires core fields, evidence anchors, reviewed metadata, `no_live_api: true`, and rejects TODO tokens in accepted rows. It does not yet prove cross-file identity consistency, input-ID uniqueness, template/evidence separation or folder/type consistency.

## Goal

Harden the reviewed-input boundary so only internally consistent accepted rows can reach registry promotion.

## Allowed files

- `scripts/validate_r5_reviewed_input_dropzone.py`
- `tests/test_validate_r5_reviewed_input_dropzone.py`
- `tests/test_r5_bundle4_fixture_contract.py`
- Bundle 4 invalid fixture directories only when needed to test the validator
- `reports/p1_6/R5_BUNDLE_4_2_DROPZONE_VALIDATION_READOUT.md`

## Forbidden scope

- Do not implement registry writes in this card.
- Do not modify report composer, valuation logic or P2 gates.
- Do not loosen existing accepted-row evidence requirements.
- Do not reject unknown optional fields merely because they are new.

## Required behavior

The validator must additionally fail closed for:

1. duplicate non-empty `input_id` values across all files in the validated root;
2. multiple `workflow_id` values in one workflow dropzone;
3. multiple `stock_code` values in one workflow dropzone;
4. an accepted or accepted-degraded row with `template_only: true`;
5. an accepted or accepted-degraded row with `not_evidence: true`;
6. an accepted source evidence ID that is blank, TODO-like, MISSING-like or otherwise a placeholder;
7. an input file located under an allowed input-type directory that disagrees with the row's `input_type`;
8. malformed `as_of_date` or `reviewed_at` on accepted rows;
9. unsupported source ranks if the repository contract already defines a closed set.

Preserve existing behavior:

- pending rows may retain visible TODOs;
- accepted-degraded requires `sample_quality_allowed: false`;
- accepted rows require full reviewed metadata and `no_live_api: true`;
- accepted rows containing critical TODO/MISSING tokens fail;
- templates are not counted as accepted evidence.

Enhance the JSON result with deterministic summary fields such as unique workflow IDs, stock codes, duplicate IDs and counts by input type. Do not expose nondeterministic absolute temporary paths in snapshot assertions.

## Acceptance criteria

- All positive Bundle 4 fixtures pass.
- Each invalid fixture fails with a stable issue ID.
- Existing tests continue to pass.
- Validator output is deterministic across two runs.
- No promotion or workflow artifact changes.

## Suggested tests

```bash
python -m pytest -q   tests/test_validate_r5_reviewed_input_dropzone.py   tests/test_r5_bundle4_fixture_contract.py --tb=short
python scripts/validate_r5_reviewed_input_dropzone.py   --root tests/fixtures/r5_reviewed_inputs/accepted_core_complete   --json /tmp/r5_bundle4_dropzone_validation.json
git diff --check
```

## Output requirements

- List added issue IDs and their exact conditions.
- List compatibility decisions.
- List tests and results.
- State the next card.
