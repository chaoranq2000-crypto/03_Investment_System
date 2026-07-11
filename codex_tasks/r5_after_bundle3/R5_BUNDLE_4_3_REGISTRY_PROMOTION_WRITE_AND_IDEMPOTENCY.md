# R5 Bundle 4.3 — Material registry promotion, atomicity and idempotency

## Background

The existing promoter can classify accepted rows and emit a promotion-result artifact, but Bundle 4 requires physical, validated registry materialization. A boolean named `registries_changed` must reflect actual file changes rather than the mere presence of accepted rows.

## Goal

Implement a deterministic, all-or-nothing writer that promotes accepted reviewed inputs into canonical run registries in an isolated output directory.

## Allowed files

- `scripts/promote_r5_reviewed_inputs_to_registries.py`
- `scripts/r5_reviewed_input_registry_io.py` if a small focused helper is needed
- `tests/test_r5_reviewed_input_registry_promotion.py`
- `tests/test_r5_bundle4_registry_promotion.py`
- `tests/test_r5_bundle4_registry_idempotency.py`
- existing registry validators only for minimal compatibility fixes proven necessary by tests
- `reports/p1_6/R5_BUNDLE_4_3_REGISTRY_PROMOTION_READOUT.md`

## Forbidden scope

- Do not write fixture data to the committed real 002837 run directory.
- Do not fetch data or infer missing values.
- Do not promote pending, rejected or accepted-degraded rows as fully reviewed facts.
- Do not partially replace registries if any candidate registry fails validation.
- Do not allow fixture mode to open sample-quality or P2.

## Required CLI and isolation

Add an explicit output/run-directory override suitable for tests, for example:

```text
--output-run-dir <path>
--fixture-mode
--dry-run
```

Requirements:

- `--fixture-mode` must reject the real workflow ID and real committed run directory.
- Fixture tests must write only under `tmp_path` or another disposable test directory.
- Stock code and workflow ID must be derived from validated rows and checked against CLI values; remove hard-coded `002837` from generic promotion logic.

## Registries to materialize

At minimum, produce or update:

- `R5_market_peer_input_registry.yaml`
- `R5_forecast_assumption_registry.yaml`
- `R5_valuation_input_registry.yaml`
- `R5_evidence_request_review_ledger.yaml`

Use existing contracts and validators as the source of truth. The writer must map:

- market and peer snapshots into the market/peer registry;
- forecast assumptions into the forecast assumption registry;
- market, peer, forecast and business review references into the valuation input registry;
- every intake decision and its evidence/reviewer provenance into the evidence review ledger.

Do not make valuation methods eligible merely because a valuation-input row exists. Eligibility must follow existing market, peer, forecast and business readiness rules.

## Provenance and merge rules

Every promoted value or row must retain enough provenance to trace it to:

- `input_id`
- `source_evidence_id`
- source rank
- as-of date
- reviewer and reviewed timestamp
- limitations

Merge behavior must be deterministic:

- preserve unrelated valid existing rows;
- replace the same logical record only under an explicit stable key;
- deduplicate by `input_id` and semantic key;
- sort stable lists deterministically;
- never silently overwrite conflicting accepted records with different evidence or values;
- surface conflicts as blockers.

## Atomicity

Build all candidate registries in memory or temporary files, run all relevant validators, and replace target files only after every candidate passes. If any validation fails, the filesystem must remain byte-for-byte unchanged.

## Truthful result artifact

The promotion result must report per registry:

- target path
- action: `created`, `updated`, `unchanged`, `blocked`
- before and after hash where applicable
- promoted input IDs
- validation decision

`registries_changed` is true only if at least one target file was physically created or its bytes changed. On a second identical run it must be false, with all actions `unchanged`.

## Acceptance criteria

- Accepted core fixtures create valid registries in a temporary run directory.
- Pending/rejected rows do not become reviewed facts.
- Accepted-degraded rows remain limited and do not activate sample-quality.
- Invalid input causes zero target-file changes.
- Identical second run produces no diff and stable hashes.
- Existing no-accepted and invalid-input tests continue to pass.

## Suggested tests

```bash
python -m pytest -q   tests/test_r5_reviewed_input_registry_promotion.py   tests/test_r5_bundle4_registry_promotion.py   tests/test_r5_bundle4_registry_idempotency.py --tb=short
git diff --check
```

## Output requirements

- List materialized registries and mapping rules.
- Show first-run and second-run summaries.
- Show rollback/atomicity test result.
- State the next card.
