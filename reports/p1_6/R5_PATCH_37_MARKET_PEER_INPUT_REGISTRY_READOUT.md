# R5 Patch 37 Market Peer Input Registry Readout

status: accepted_with_todos

## files_added

- `.agents/skills/stock-deep-dive/references/r5_market_peer_input_registry_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_market_peer_input_registry.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_market_peer_input_registry.py`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_market_peer_input_registry.yaml`
- `tests/test_validate_r5_market_peer_input_registry.py`
- `reports/p1_6/R5_PATCH_37_MARKET_PEER_INPUT_REGISTRY_READOUT.md`

## files_modified

- none

## commands_run

- `.\\.conda\\investment-system\\python.exe -m py_compile .agents\\skills\\stock-deep-dive\\scripts\\validate_r5_market_peer_input_registry.py .agents\\skills\\stock-deep-dive\\scripts\\validate_r5_forecast_assumption_registry.py .agents\\skills\\evidence-ingest\\scripts\\build_r5_evidence_request_review_ledger.py .agents\\skills\\evidence-ingest\\scripts\\validate_r5_evidence_request_review_ledger.py`
- `.\\.conda\\investment-system\\python.exe -m pytest -q tests\\test_validate_r5_market_peer_input_registry.py tests\\test_validate_r5_forecast_assumption_registry.py tests\\test_build_r5_evidence_request_review_ledger.py tests\\test_validate_r5_evidence_request_review_ledger.py --tb=short`
- `.\\.conda\\investment-system\\python.exe .agents\\skills\\stock-deep-dive\\scripts\\validate_r5_market_peer_input_registry.py reports\\workflow_runs\\wf_20260703_stock_first_002837_invic\\R5_market_peer_input_registry.yaml`

## exit_code

- py_compile: 0
- pytest: 0
- market peer registry validator: 0

## stdout_or_stderr_summary

- pytest: `13 passed in 0.14s`
- validator: `decision=accepted_with_todos`, `issues=[]`

## artifact_evidence

- checked=6 declared Patch 37 files.
- The run registry keeps `review_status: pending` and preserves `TODO_MARKET_DATA` / `TODO_PEER_DATA`.
- `sample_quality_report_allowed: false` and `p2_allowed: false` remain explicit.

## known_todos

- 本 patch 不提供真实市场/同业数据；market 和 peer 输入仍待 reviewed evidence。

## next_recommended_patch

- R5 Patch 38 - Forecast Assumption Registry
