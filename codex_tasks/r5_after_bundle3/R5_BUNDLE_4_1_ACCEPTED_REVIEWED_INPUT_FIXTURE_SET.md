# R5 Bundle 4.1 — Accepted reviewed-input fixture set

## Background

The current test fixtures cover pending, accepted-degraded and a small number of invalid accepted rows. Bundle 4 needs a complete synthetic fixture matrix to exercise the positive promotion path without pretending that fixtures are real evidence.

## Goal

Add deterministic, test-only reviewed-input fixtures for the positive, degraded, mixed and invalid paths.

## Allowed files

- `tests/fixtures/r5_reviewed_inputs/accepted_core_complete/**`
- `tests/fixtures/r5_reviewed_inputs/accepted_all_complete/**`
- `tests/fixtures/r5_reviewed_inputs/mixed_status/**`
- `tests/fixtures/r5_reviewed_inputs/invalid_duplicate_input_id/**`
- `tests/fixtures/r5_reviewed_inputs/invalid_cross_workflow/**`
- `tests/fixtures/r5_reviewed_inputs/invalid_cross_stock/**`
- `tests/fixtures/r5_reviewed_inputs/invalid_template_as_evidence/**`
- `tests/fixtures/r5_reviewed_inputs/invalid_folder_type_mismatch/**`
- `tests/fixtures/r5_reviewed_inputs/README.md`
- `tests/test_r5_bundle4_fixture_contract.py`
- `reports/p1_6/R5_BUNDLE_4_1_ACCEPTED_FIXTURE_SET_READOUT.md`

## Forbidden scope

- Do not place fixtures under `data/reviewed_inputs/**`.
- Do not modify the real 002837 workflow-run directory.
- Do not use real-company prices, forecasts, peer values or business claims.
- Do not use `002837` as the fixture stock code.
- Do not set `sample_quality_allowed: true` in any fixture row.

## Required fixture matrix

### `accepted_core_complete`

Provide one or more valid `review_status: accepted` rows for:

- `market_snapshot`
- `peer_snapshot`
- `forecast_assumptions`
- `valuation_inputs`

Business disclosure must be absent. Expected maximum report level in non-fixture semantics is `reviewed_input_research_draft`.

### `accepted_all_complete`

Provide valid accepted rows for all five readiness types:

- market
- peer
- forecast assumptions
- valuation inputs
- business disclosure

Even when internally complete, fixture mode must cap sample-quality and P2 to false.

### `mixed_status`

Include accepted, accepted-degraded, pending and rejected rows. Only accepted rows may activate reviewed flags. Accepted-degraded rows must preserve limitations and keep `sample_quality_allowed: false`.

### Invalid cases

Include at least one deterministic case for each of:

- duplicate `input_id`
- mixed `workflow_id` values in one workflow dropzone
- mixed `stock_code` values
- accepted row marked `template_only: true` or `not_evidence: true`
- folder name inconsistent with `input_type`

Retain the existing invalid missing-evidence and accepted-TODO cases.

## Fixture metadata rules

Use a clearly synthetic workflow such as `wf_fixture_r5_bundle4` and a non-security stock code such as `000000`. Evidence IDs must be fixture IDs such as `ev_fixture_*`. Every accepted row must still satisfy the normal metadata contract:

- source evidence ID
- source rank
- as-of date
- reviewer
- reviewed timestamp
- limitations
- `no_live_api: true`

The limitations field must say that the row is synthetic test data and not research evidence. Keep a human-readable fixture boundary in `tests/fixtures/r5_reviewed_inputs/README.md`.

## Acceptance criteria

- Positive fixtures parse and contain no TODO/MISSING tokens in accepted rows.
- Fixture values are deterministic and visibly synthetic.
- Invalid fixtures fail for the intended single reason where practical.
- No fixture file is present under the real reviewed-input dropzone.
- Test asserts all fixture rows use the fixture workflow and synthetic stock code unless the fixture intentionally tests a mismatch.

## Suggested tests

```bash
python -m pytest -q tests/test_r5_bundle4_fixture_contract.py tests/test_validate_r5_reviewed_input_dropzone.py --tb=short
git diff --check
```

## Output requirements

- List fixture directories and intended scenario.
- List tests and results.
- Confirm no real-workflow or real-evidence file changed.
- State the next card.
