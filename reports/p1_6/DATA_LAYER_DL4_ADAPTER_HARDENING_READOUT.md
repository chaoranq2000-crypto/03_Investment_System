# DATA_LAYER_DL4_ADAPTER_HARDENING_READOUT

date: 2026-07-03
scope: DL-4 Tushare / Baostock Live Adapter Hardening
status: PASS_WITH_MANUAL_LIVE_SMOKE_PENDING

## Code Changes

- `src/ingest/adapters/tushare_adapter.py`
  - Added `--mode fixture|dry-run|live`.
  - Added explicit `--allow-network` gate for live mode.
  - Live mode without network permission returns BLOCKED.
  - Live mode with network permission but without `TUSHARE_TOKEN` returns BLOCKED without storing token value.
  - Live mode with explicit permission and token fetches rows and routes them through `structured_api_pull`.
- `src/ingest/adapters/baostock_adapter.py`
  - Added `--mode fixture|dry-run|live`.
  - Added explicit `--allow-network` gate for live mode.
  - Added `--frequency` and `--adjustflag` parameters for future K-line live smoke.
  - Missing package or no network permission returns BLOCKED without failing CI.
  - Live mode uses login-query-logout and routes returned rows through `structured_api_pull`.

## Tests Added

- Tushare live mode requires explicit network flag.
- Tushare live mode with network flag requires token and does not write token value.
- Tushare mocked live success writes raw snapshot, normalized table, manifest row and metric candidates.
- Baostock live mode requires explicit network flag.
- Baostock mocked live success verifies login-query-logout and writes structured artifacts.
- Manual real-service live smoke tests are present and skipped by default unless `ENABLE_LIVE_DATA_TESTS=1`.
- Existing fixture and dry-run tests continue to pass.

## Verification

```text
python -m py_compile $(git ls-files '*.py')
PASS

python -m pytest -q tests/test_tushare_adapter_contract.py tests/test_baostock_adapter_contract.py
11 passed in 0.24s

python -m pytest -q tests/test_live_adapter_smoke.py tests/test_tushare_adapter_contract.py tests/test_baostock_adapter_contract.py
11 passed, 2 skipped in 0.23s

python -m pytest -q
66 passed, 2 skipped in 2.97s
```

Additional checks:

- Secret value pattern scan: PASS.
- Raw snapshot overwrite check: PASS.

## Live Smoke Status

Manual live smoke against real services was not executed in this run. The executable live path is covered with mocked adapters and remains gated behind `--mode live --allow-network` and the relevant external prerequisites:

- `TUSHARE_TOKEN`
- optional `ENABLE_LIVE_DATA_TESTS=1`
- available Baostock package/session

## Boundary Review

- No real Tushare or Baostock API call was made.
- No token value was written to tracked artifacts.
- Fixture mode remains supported.
- Dry-run/no-token behavior remains non-crashing.
- Structured data output remains evidence/metric-only and does not produce business exposure claims.
