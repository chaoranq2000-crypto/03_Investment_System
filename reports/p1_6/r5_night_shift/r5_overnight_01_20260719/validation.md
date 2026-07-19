# Night-shift validation record

- Run ID: `r5_overnight_01_20260719`
- Task ID: `ns01_t70_regression_determinism`
- Terminal status: `passed`
- Receipt: `.local/night_shift/receipts/full_regression.json`

| Exit | Command | Output summary |
|---:|---|---|
| 0 | `python -m pytest -q tests/test_r5_bundle17r_backflow_execution.py tests/test_r5_bundle17r_backflow_execution_cli.py tests/test_r5_bundle17r_backflow_execution_determinism.py tests/test_r5_bundle17r_backflow_execution_fail_closed.py` | 9 passed in 0.69s |
| 0 | `python -m pytest -q tests/test_r5_bundle17r_verified_result_materializer.py tests/test_r5_bundle17r_verified_result_materializer_cli.py` | 12 passed in 4.05s |
| 0 | `python scripts/run_source_route_quality_gate.py --import-check --output reports/quality/ci_source_route_quality_report.yaml` | decision=pass capabilities=17 blocking=0 |
| 0 | `python -m pytest -q tests/test_r5_night_shift_contract.py tests/test_r5_night_shift_runner.py tests/test_r5_night_shift_lock.py tests/test_r5_night_shift_receipts.py tests/test_r5_night_shift_bf2_seed.py tests/test_r5_night_shift_determinism.py tests/test_r5_night_shift_readout.py` | 26 passed in 0.72s |
| 0 | `git diff --check` |  |
| 0 | `python -m pytest -q` | 959 passed, 2 skipped in 42.81s |
| 0 | `python scripts/run_r5_night_shift.py compare-files --pair .local/night_shift/seeded_queue.yaml .local/night_shift/seeded_queue_run_b.yaml --pair .local/night_shift/bf2_inventory.json .local/night_shift/bf2_inventory_run_b.json --pair .local/night_shift/bf2_seed_receipt.json .local/night_shift/bf2_seed_receipt_run_b.json --receipt .local/night_shift/receipts/determinism.json` | OK: comparisons=3 equal=True |

All command bodies are represented by exit code, byte length and SHA-256 in the receipt.
