# R5 Bundle 3.6 — Close readout and next decision

## Background

Bundle 3 should close only after the four core subpack validators and the aggregate preflight gate are executable. This close card must freeze the true status and prevent accidental promotion to sample-quality or P2.

## Goal

Create the Bundle 3 close readout, run targeted tests, update the canonical R5 readout index if appropriate, and state the next decision.

## Allowed files

- `reports/p1_6/R5_BUNDLE_3_CORE_RESEARCH_ASSET_SUBPACKS_CLOSE_READOUT.md`
- `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md` only if the file already tracks R5 readouts and can be updated minimally
- `reports/p1_6/r5_core_asset_preflight_result.json`
- `tests/test_r5_bundle3_close.py`
- `config/r5_bundle3_expected_artifacts.yaml` only if needed to reconcile actual artifacts

## Forbidden scope

- Do not modify real workflow run artifacts.
- Do not render a stock report.
- Do not promote reviewed inputs.
- Do not change sample-quality or P2 gates to true.
- Do not hide TODOs or missing disclosure.

## Required close status

Unless Bundle 3 unexpectedly also receives reviewed inputs through a separate accepted path, close status should be:

```text
current_r5_state: R5_CORE_ASSET_SCHEMAS_EXECUTABLE_WITH_TODOS
sample_quality_report_allowed: false
p2_allowed: false
```

The readout must list:

- files added
- files modified
- commands run
- exit codes
- pytest result summary
- preflight JSON summary
- remaining TODOs
- blockers if any
- next recommended bundle

## Suggested final test commands

```bash
python - <<'PY'
import yaml
from pathlib import Path
for p in [
    '.agents/skills/stock-deep-dive/assets/r5_financial_history_pack.example.yaml',
    '.agents/skills/stock-deep-dive/assets/r5_business_breakdown_pack.example.yaml',
    '.agents/skills/stock-deep-dive/assets/r5_forecast_model_pack.example.yaml',
    '.agents/skills/stock-deep-dive/assets/r5_valuation_pack.example.yaml',
    'config/r5_bundle3_expected_artifacts.yaml',
]:
    with Path(p).open('r', encoding='utf-8') as f:
        yaml.safe_load(f)
print('bundle3 yaml ok')
PY

python -m py_compile \
  .agents/skills/stock-deep-dive/scripts/validate_r5_financial_history_pack.py \
  .agents/skills/stock-deep-dive/scripts/validate_r5_business_breakdown_pack.py \
  .agents/skills/stock-deep-dive/scripts/validate_r5_forecast_model_pack.py \
  .agents/skills/stock-deep-dive/scripts/validate_r5_valuation_pack.py \
  .agents/skills/stock-deep-dive/scripts/run_r5_core_asset_preflight.py

python .agents/skills/stock-deep-dive/scripts/run_r5_core_asset_preflight.py --json reports/p1_6/r5_core_asset_preflight_result.json

python -m pytest -q \
  tests/test_validate_r5_financial_history_pack.py \
  tests/test_validate_r5_business_breakdown_pack.py \
  tests/test_validate_r5_forecast_model_pack.py \
  tests/test_validate_r5_valuation_pack.py \
  tests/test_r5_core_asset_preflight.py \
  tests/test_r5_bundle3_close.py \
  --tb=short

git diff --check
```

If the repository has `scripts/check_r5_readout_truthfulness.py`, run it over the updated R5 readouts as well.

## Output requirements

- Produce the close readout.
- State whether Bundle 3 is accepted, accepted with TODOs, needs fix, or blocked.
- State the next recommended bundle without executing it.

## Next recommended bundle if Bundle 3 passes

`R5 Bundle 4 — Accepted reviewed input fixture and registry promotion smoke`.

Bundle 4 should use local, manually reviewed fixture inputs only. It should verify that accepted rows can promote registries and that pending or degraded rows cannot unlock sample-quality.
