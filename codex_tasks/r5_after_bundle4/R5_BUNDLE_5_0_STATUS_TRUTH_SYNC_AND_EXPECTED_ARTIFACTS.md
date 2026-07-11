# R5 Bundle 5.0 — Status truth sync and expected artifacts

## Background

README carries the long-lived P1.6 umbrella label, while the detailed execution state is maintained by R5 close readouts and the canonical index. Bundle 5 needs a stable baseline and artifact inventory before real inputs are touched.

## Goal

Create the Bundle 5 expected-artifact manifest, record a truthful baseline, and add a stable documentation pointer that distinguishes project phase from current Bundle state.

## Allowed files

- `README.md` only for a stable pointer to the canonical R5 state source
- `config/r5_bundle5_expected_artifacts.yaml`
- `reports/p1_6/R5_AFTER_BUNDLE4_STATUS_BASELINE_READOUT.md`
- `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md`
- `.github/workflows/ci.yml` only for deterministic warning hygiene with no semantic test reduction
- focused tests for the manifest and stage pointer

## Forbidden scope

- Do not change P1.6 project scope or P2 policy.
- Do not hard-code README as the authoritative gate state.
- Do not change workflow facts to match a task plan.
- Do not suppress CI warnings by removing tests or checks.
- Do not mutate real reviewed inputs or registries.

## Required work

1. Create `config/r5_bundle5_expected_artifacts.yaml` with:
   - base state and allowed target states;
   - real workflow ID and stock code;
   - required/optional input types;
   - expected card readouts, JSON/YAML results, tests and close artifacts;
   - real-workflow write boundary (`false` before Card 5.5);
   - sample-quality and P2 fixed to `false` for the whole bundle.
2. Add a README sentence stating that P1.6 is the umbrella phase and the latest canonical R5 close readout determines the current execution Bundle/gate.
3. Record the two current CI warnings. Resolve them only if the action/channel change is supported and the full CI command remains equivalent; otherwise record a non-blocking TODO.
4. Add manifest tests that fail on missing artifacts, duplicated physical ownership, undeclared real-workflow writes or a true sample-quality/P2 flag.

## Acceptance gate

- Baseline is reproducible from physical files.
- Manifest parses and all planned paths use existing repository placement rules.
- README pointer does not become a second workflow fact source.
- CI still compiles all Python files and runs the full pytest suite.

## Suggested commands

```bash
python - <<'PY'
from pathlib import Path
import yaml
p = Path('config/r5_bundle5_expected_artifacts.yaml')
assert isinstance(yaml.safe_load(p.read_text(encoding='utf-8')), dict)
print('bundle5_manifest_parse=pass')
PY
python -m pytest -q tests/test_r5_bundle5_status_baseline.py --tb=short -p no:cacheprovider
git diff --check
```

## Close artifact

`reports/p1_6/R5_AFTER_BUNDLE4_STATUS_BASELINE_READOUT.md`
