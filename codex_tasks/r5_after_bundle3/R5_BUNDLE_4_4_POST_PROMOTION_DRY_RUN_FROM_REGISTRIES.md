# R5 Bundle 4.4 — Post-promotion dry run derived from registries

## Background

Readiness must not be inferred solely from the presence of accepted dropzone rows. After promotion, the physical registries and their validators must become the source of truth for reviewed flags and remaining gaps.

## Goal

Build a post-promotion reviewed-input dry-run artifact from validated registry contents and provenance, with fail-closed behavior for missing or invalid registries.

## Allowed files

- `scripts/build_r5_reviewed_input_dry_run_from_registries.py`
- `scripts/build_r5_reviewed_input_staging.py` only for a minimal interlock or shared helper
- `scripts/r5_reviewed_input_registry_io.py` only if introduced by Card 4.3
- `tests/test_r5_bundle4_post_promotion_dry_run.py`
- `tests/test_r5_002837_reviewed_input_staging.py` only for compatibility assertions
- `reports/p1_6/R5_BUNDLE_4_4_POST_PROMOTION_DRY_RUN_READOUT.md`

## Forbidden scope

- Do not infer readiness from unvalidated files.
- Do not mutate the real 002837 dry-run result.
- Do not remove a TODO unless the corresponding reviewed registry value and evidence anchor actually resolve it.
- Do not generate a report.

## Required inputs

The builder must accept an explicit run directory and read:

- market/peer registry
- forecast assumption registry
- valuation input registry
- evidence request review ledger
- promotion result, when available

It must run or call the existing validators and record their decisions.

## Required reviewed flags

Derive flags from physical registry state:

- `reviewed_market_inputs_available`
- `reviewed_peer_inputs_available`
- `reviewed_forecast_assumptions_available`
- `reviewed_valuation_inputs_available`
- `reviewed_business_disclosure_available`

A flag may be true only when the relevant registry section is reviewed, evidence-anchored and validator-accepted. Accepted-degraded or explicitly degraded rows may be represented in limitations but must not satisfy a full reviewed flag unless the existing gate contract explicitly permits it; default to false.

## Remaining TODO reconciliation

Recompute `remaining_todos` from current registry and ledger contents. Do not copy a stale TODO list from a previous dry run. Maintain a trace table showing, for each critical token:

- status: resolved or remaining
- resolving input IDs, if resolved
- registry path and field
- evidence IDs
- reason if still remaining

Critical tokens include at least:

- `TODO_MARKET_DATA`
- `TODO_PEER_DATA`
- `TODO_MODEL_INPUT`
- `MISSING_DISCLOSURE`
- `TODO_SOURCE_REQUIRED`

Resolving market data must not automatically resolve peer, model, disclosure or generic source gaps.

## Fixture-mode cap

The output must carry `fixture_mode: true` when invoked for fixtures. In fixture mode:

- `sample_quality_report_allowed: false`
- `p2_allowed: false`
- maximum externally allowed report level is `reviewed_input_research_draft`

The artifact may separately record an internal completeness signal, but it must not call a fixture a real sample-quality candidate.

## Provenance and reproducibility

Include:

- source registry paths
- registry hashes
- validator decisions
- promoted input IDs by readiness flag
- fixture mode
- deterministic ordering

## Acceptance criteria

- Empty or pending registries remain source-gapped.
- Core-complete fixture yields the four required pilot flags true and business disclosure false.
- All-complete fixture yields all five flags true, but sample-quality and P2 remain false in fixture mode.
- A tampered or invalid registry turns the affected flag false and records a blocker.
- Repeated builds are byte-stable after path normalization.

## Suggested tests

```bash
python -m pytest -q   tests/test_r5_bundle4_post_promotion_dry_run.py   tests/test_r5_002837_reviewed_input_staging.py --tb=short
git diff --check
```

## Output requirements

- List readiness derivation rules.
- Show core-complete and all-complete fixture decisions.
- Show invalid-registry fail-closed result.
- State the next card.
