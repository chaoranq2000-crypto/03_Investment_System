# R5 Bundle 3.5 — Core asset preflight gate

## Background

After the four core subpack validators exist, R5 needs one aggregate preflight gate that summarizes whether the core research asset layer is usable, still source-gapped, needs fix, or blocked.

## Goal

Add an executable R5 core asset preflight gate that consumes the four standalone subpack examples or paths supplied on the CLI and writes a JSON result.

## Allowed files

- `.agents/skills/stock-deep-dive/scripts/run_r5_core_asset_preflight.py`
- `tests/test_r5_core_asset_preflight.py`
- `reports/p1_6/r5_core_asset_preflight_result.json`
- `reports/p1_6/R5_BUNDLE_3_5_CORE_ASSET_PREFLIGHT_GATE_READOUT.md`
- Existing Bundle 3 subpack validators only if small import or CLI compatibility fixes are needed

## Forbidden scope

- Do not modify real workflow run artifacts.
- Do not fetch or create real stock data.
- Do not render a report.
- Do not set sample-quality allowed when any core subpack is TODO or source-gapped.
- Do not enter P2.

## Required behavior

CLI should support either explicit paths or defaults to the Bundle 3 example assets, for example:

```bash
python .agents/skills/stock-deep-dive/scripts/run_r5_core_asset_preflight.py \
  --financial .agents/skills/stock-deep-dive/assets/r5_financial_history_pack.example.yaml \
  --business .agents/skills/stock-deep-dive/assets/r5_business_breakdown_pack.example.yaml \
  --forecast .agents/skills/stock-deep-dive/assets/r5_forecast_model_pack.example.yaml \
  --valuation .agents/skills/stock-deep-dive/assets/r5_valuation_pack.example.yaml \
  --json reports/p1_6/r5_core_asset_preflight_result.json
```

JSON result must include:

```text
artifact_type
schema_version
core_asset_state
financial_history_status
business_breakdown_status
forecast_model_status
valuation_status
sample_quality_report_allowed
p2_allowed
blockers
non_blocking_todos
known_todos
next_candidate_tasks
```

State rules:

- Any validator error must produce `blocked` or `needs_fix`.
- Valid examples with visible TODOs must produce `R5_CORE_ASSET_SCHEMAS_EXECUTABLE_WITH_TODOS`.
- `sample_quality_report_allowed` must be false unless business, forecast and valuation subpacks are all ready and no blocker exists.
- `p2_allowed` must remain false in this bundle.
- The gate must fail closed on missing files or malformed YAML.

## Acceptance criteria

- Script compiles.
- Script writes JSON result.
- Example TODO assets produce `R5_CORE_ASSET_SCHEMAS_EXECUTABLE_WITH_TODOS` and keep sample-quality/P2 false.
- Tests cover success-with-TODOs and malformed/missing input cases.
- No direct trading instruction language is introduced.

## Suggested tests

```bash
python -m py_compile .agents/skills/stock-deep-dive/scripts/run_r5_core_asset_preflight.py
python .agents/skills/stock-deep-dive/scripts/run_r5_core_asset_preflight.py --json reports/p1_6/r5_core_asset_preflight_result.json
python -m pytest -q tests/test_r5_core_asset_preflight.py --tb=short
git diff --check
```

## Output requirements

- List changed files.
- Include JSON summary.
- Include pytest result.
- Write the readout file.
