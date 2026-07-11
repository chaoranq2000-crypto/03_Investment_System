# R5 Bundle 4.5 — End-to-end reviewed-input fixture smoke gate

## Background

Bundle 4 needs one deterministic command that exercises the entire local activation chain and proves both the positive path and fail-closed boundaries.

## Goal

Create and test an isolated end-to-end smoke runner covering validation, promotion, registry validation, post-promotion dry-run reconstruction and gate decisions.

## Allowed files

- `scripts/run_r5_bundle4_reviewed_input_smoke.py`
- `config/r5_bundle4_smoke_rules.yaml` if needed
- `tests/test_r5_bundle4_reviewed_input_smoke.py`
- `scripts/r5_reviewed_input_pilot_gate.py` only for a minimal fixture-mode safety interlock or injectable paths
- `reports/p1_6/r5_bundle4_reviewed_input_smoke_result.json`
- `reports/p1_6/R5_BUNDLE_4_5_END_TO_END_FIXTURE_SMOKE_READOUT.md`

## Forbidden scope

- Do not call network services.
- Do not write fixture values into real workflow directories.
- Do not render or publish a real stock report.
- Do not let fixture completeness set sample-quality or P2 true.
- Do not ignore a failed substep.

## Required scenarios

Run each scenario in a fresh disposable directory:

1. **empty or pending only**
   - no registry facts promoted
   - source-gapped
   - all reviewed flags false

2. **accepted core complete**
   - market, peer, forecast and valuation flags true
   - business disclosure false
   - maximum allowed level `reviewed_input_research_draft`
   - sample-quality false
   - P2 false

3. **accepted all complete**
   - all five reviewed flags true
   - fixture completeness recorded
   - external allowed level still capped at `reviewed_input_research_draft`
   - sample-quality false
   - P2 false

4. **mixed status**
   - only accepted rows activate flags
   - limitations preserve accepted-degraded information

5. **invalid input**
   - validation or promotion blocked
   - no registry target changes

6. **idempotent rerun**
   - second run writes zero changed registries
   - stable hashes and decisions

## Smoke result schema

The JSON result must include:

- artifact type and schema version
- fixture mode
- base and temporary workflow identifiers
- scenario-level status
- command/function step results
- registry actions and hashes
- reviewed flags
- remaining TODOs
- sample-quality and P2 decisions
- blockers
- overall status

Overall status is pass only when every positive and negative expectation is met.

Recommended close state for this smoke:

```text
R5_REVIEWED_INPUT_FIXTURE_PROMOTION_SMOKE_PASSED
```

This state must coexist with:

```text
real_002837_reviewed_input_pilot_allowed = false
sample_quality_report_allowed = false
p2_allowed = false
```

## Acceptance criteria

- One command runs all scenarios without network access.
- Smoke result is deterministic except for explicitly normalized temporary paths.
- Invalid scenario proves no partial writes.
- Second-run scenario proves idempotency.
- Existing reviewed-input pilot tests still pass.
- The real 002837 gate result remains unchanged and source-gapped.

## Suggested commands

```bash
python scripts/run_r5_bundle4_reviewed_input_smoke.py   --fixture-root tests/fixtures/r5_reviewed_inputs   --json reports/p1_6/r5_bundle4_reviewed_input_smoke_result.json
python -m pytest -q   tests/test_r5_bundle4_reviewed_input_smoke.py   tests/test_r5_reviewed_input_pilot_gate.py   tests/test_r5_after_patch55_close.py   tests/test_r5_bundle3_close.py --tb=short
git diff --check
```

## Output requirements

- List scenario decisions.
- List commands and exit codes.
- Explicitly state whether the real 002837 workflow changed.
- State the next card.
