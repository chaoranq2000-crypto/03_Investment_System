# R5 Bundle 3.0 — Status baseline and expected artifacts

## Background

The workspace has completed Patch 55 and Bundle 1/2. The correct current state is still source-gapped. This card creates a small baseline readout and expected-artifact manifest before implementing the Bundle 3 subpack validators.

## Goal

Create a status baseline so later Bundle 3 close checks can verify that all expected contracts, examples, validators and tests were added.

## Allowed files

- `config/r5_bundle3_expected_artifacts.yaml`
- `reports/p1_6/R5_AFTER_BUNDLE2_STATUS_BASELINE_READOUT.md`
- `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md` only if the file already tracks R5 readouts and can be updated minimally

## Forbidden scope

- Do not modify `reports/workflow_runs/**`.
- Do not modify `data/raw/**`, `data/processed/**`, or `data/manifests/**`.
- Do not implement validators in this card.
- Do not generate any stock report.
- Do not change sample-quality or P2 gates.

## Required content

`config/r5_bundle3_expected_artifacts.yaml` must list the intended Bundle 3 artifacts for:

- financial history subpack contract, example, validator and test
- business breakdown subpack contract, example, validator and test
- forecast model subpack contract, example, validator and test
- valuation subpack contract, example, validator and test
- core asset preflight gate, test, JSON result and close readout

`R5_AFTER_BUNDLE2_STATUS_BASELINE_READOUT.md` must state:

- current state: `R5_REVIEWED_INPUT_PILOT_BLOCKED_SOURCE_GAPPED`
- Patch 55 close status is blocked/source-gapped
- Bundle 1 status is accepted with TODOs
- Bundle 2 status is accepted with TODOs
- reviewed-input pilot is not allowed
- sample-quality report is not allowed
- P2 is not allowed
- Bundle 3 does not supply reviewed inputs

## Acceptance criteria

- YAML parses successfully.
- Baseline readout is physically readable and not compressed into one line.
- No forbidden scope files are changed.
- No direct trading instruction language is introduced.

## Suggested tests

```bash
python - <<'PY'
import yaml
from pathlib import Path
p = Path('config/r5_bundle3_expected_artifacts.yaml')
with p.open('r', encoding='utf-8') as f:
    data = yaml.safe_load(f)
assert isinstance(data, dict)
assert data.get('bundle') == 'R5_BUNDLE_3_CORE_RESEARCH_ASSET_SUBPACKS'
print('bundle3 expected artifacts yaml ok')
PY

git diff --check
```

## Output requirements

- List changed files.
- List test commands and results.
- State the next card to execute.
