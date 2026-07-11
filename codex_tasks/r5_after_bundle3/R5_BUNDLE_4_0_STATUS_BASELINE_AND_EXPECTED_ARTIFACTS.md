# R5 Bundle 4.0 — Status baseline and expected artifacts

## Background

Bundle 4 must prove reviewed-input activation without allowing test fixtures to contaminate the real 002837 workflow. A baseline and expected-artifact manifest are required before implementation.

## Goal

Create a fail-closed Bundle 4 manifest and baseline readout that distinguish fixture-pipeline readiness from real reviewed-input readiness.

## Allowed files

- `config/r5_bundle4_expected_artifacts.yaml`
- `reports/p1_6/R5_AFTER_BUNDLE3_STATUS_BASELINE_READOUT.md`
- `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md` only for a minimal index update

## Forbidden scope

- Do not modify `reports/workflow_runs/**`.
- Do not modify `data/reviewed_inputs/**`, `data/raw/**`, `data/processed/**` or `data/manifests/**`.
- Do not implement fixture, validator, promotion or smoke code in this card.
- Do not change sample-quality or P2 gates.

## Required content

`config/r5_bundle4_expected_artifacts.yaml` must identify expected artifacts for:

- accepted core-complete fixture set
- accepted all-complete fixture set
- mixed-status and invalid fixture cases
- dropzone validation hardening and tests
- material registry writer and idempotency tests
- post-promotion registry-derived dry-run builder and tests
- end-to-end Bundle 4 fixture smoke runner, JSON result and test
- per-card readouts and canonical close readout

The baseline readout must state:

- base state: `R5_CORE_ASSET_SCHEMAS_EXECUTABLE_WITH_TODOS`
- real workflow: `wf_20260703_stock_first_002837_invic`
- real reviewed-input pilot: closed
- real accepted reviewed inputs: absent
- sample-quality report: closed
- P2: closed
- fixture mode may never by itself open sample-quality or P2

## Acceptance criteria

- Manifest YAML parses.
- Expected artifacts are grouped by card and use repository-relative paths.
- Baseline clearly separates fixture results from real-workflow decisions.
- No forbidden files change.

## Suggested tests

```bash
python - <<'PYCODE'
from pathlib import Path
import yaml
p = Path('config/r5_bundle4_expected_artifacts.yaml')
data = yaml.safe_load(p.read_text(encoding='utf-8'))
assert isinstance(data, dict)
assert data.get('bundle') == 'R5_BUNDLE_4_REVIEWED_INPUT_FIXTURE_PROMOTION_SMOKE'
assert data.get('fixture_mode_sample_quality_allowed') is False
assert data.get('p2_allowed') is False
print('bundle4 expected artifacts yaml ok')
PYCODE
git diff --check
```

## Output requirements

- List changed files.
- List commands and results.
- State the next card.
