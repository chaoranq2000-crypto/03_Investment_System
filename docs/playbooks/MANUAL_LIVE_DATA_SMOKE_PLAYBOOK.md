# Manual Live Data Smoke Playbook

> Purpose: verify the shared Tushare client and Tushare / Baostock adapter paths manually. This is the only active live-data smoke playbook and does not connect results to reports or databases.

## 1. Preconditions

| item | requirement |
|---|---|
| stage | shared infrastructure and P1.6 adapters |
| execution | manual only |
| CI | do not enable live network tests |
| output | temporary, isolated, reviewed before any commit |
| report usage | live smoke output is not report evidence by default |

## 2. Environment Variables

Keep the following keys in the Git-ignored `.env.local`; do not paste real values into a
command or this playbook:

```dotenv
TUSHARE_TOKEN=
TUSHARE_HTTP_URL=
TUSHARE_DISABLE_PROXY=false
```

`TUSHARE_HTTP_URL` is the only endpoint setting. The client rejects the retired
`TUSHARE_API_URL` alias, non-HTTPS endpoints, credentials in URLs, and malformed proxy
settings. Token length is provider-defined; the client validates unsafe characters but
does not assume the old 56-character format. It passes the token to one client instance
and never calls `ts.set_token()`.

Optional for diagnostics:

```powershell
$env:PYTHONIOENCODING="utf-8"
```

Safety checks:

```powershell
git status --short
git check-ignore -v .env.local
git check-ignore -v data/raw/live_smoke/
```

Token rules:

- Keep token values in the environment or `.env.local` only.
- Do not write token values into readouts, logs, manifests or command history notes.
- Adapter readouts may include `token_env: TUSHARE_TOKEN`; they must not include the token value.
- Default diagnostics are configuration-only. Run a real probe only after the user gives
  task-specific authorization, then add `--allow-network` explicitly.
- Use fake tokens for automated tests. Neither the client nor adapter tests open a network
  connection.
- Do not set `NO_PROXY=*`. When direct endpoint access is required, set
  `TUSHARE_DISABLE_PROXY=true`; the client adds only the configured endpoint host to
  `NO_PROXY` for the duration of each call and restores the prior environment.

Visibility boundary:

- An ordinary HTTPS forward proxy can see the destination host/IP, connection timing and
  traffic volume. It normally cannot read the token or request body unless it performs
  trusted TLS interception.
- The configured endpoint receives the token, API name, stock codes, date filters and the
  returned dataset. A third-party compatible endpoint therefore sees the full Tushare
  request even when the network proxy is bypassed.

## 3. Configuration And Fake-Token Checks

Configuration-only diagnostics do not import the SDK or make network calls:

```powershell
conda run -p .\.conda\investment-system python -m src.utils.tushare_diagnostics `
  --env-file .\.env.local `
  --profile research
```

Run the offline security and adapter tests with fake tokens:

```powershell
conda run -p .\.conda\investment-system python -m pytest -q -p no:cacheprovider `
  tests\test_tushare_client.py `
  tests\test_tushare_adapter_contract.py `
  tests\test_tushare_diagnostics.py
```

Only after explicit authorization, add the network flag for a bounded, read-only probe:

```powershell
conda run -p .\.conda\investment-system python -m src.utils.tushare_diagnostics `
  --env-file .\.env.local `
  --profile core `
  --allow-network
```

The separately guarded pytest smoke also requires an explicit process-local switch. Set
it only for an authorized manual run, then remove it from the shell afterward:

```powershell
$env:ENABLE_LIVE_DATA_TESTS="1"
conda run -p .\.conda\investment-system python -m pytest -q -p no:cacheprovider `
  tests\test_live_adapter_smoke.py
Remove-Item Env:ENABLE_LIVE_DATA_TESTS
```

Profiles report row counts, schema and sanitized errors only. `research` adds
`daily_basic` and `income`; `portfolio` checks the required price/adjustment path and
labels convertible-bond/minute endpoints optional. Investment Review has no direct
Tushare dependency in `main`.

## 4. Temporary Output Directory

Use a run-scoped directory that is ignored or treated as local-only until reviewed:

```powershell
$runId="manual_live_smoke_20260703_002837"
$out="data/raw/live_smoke/$runId"
New-Item -ItemType Directory -Force $out
```

Before running, confirm the path:

```powershell
git check-ignore -v $out
git status --short
```

If `git check-ignore` does not ignore the directory, stop and add an explicit local-only plan before running live smoke.

## 5. Tushare daily_basic Smoke

```powershell
conda run -p .\.conda\investment-system python -m src.ingest.adapters.tushare_adapter `
  --repo-root . `
  --api-name daily_basic `
  --stock-code 002837 `
  --company-id cn_002837_invic `
  --mode live `
  --allow-network `
  --as-of-date 2026-07-01 `
  --publish-date 2026-07-01 `
  --raw-dir data/raw/live_smoke/manual_live_smoke_20260703_002837/tushare_daily_basic/raw `
  --normalized-dir data/raw/live_smoke/manual_live_smoke_20260703_002837/tushare_daily_basic/normalized `
  --manifest-path data/raw/live_smoke/manual_live_smoke_20260703_002837/tushare_daily_basic/evidence_manifest.csv `
  --metrics-path data/raw/live_smoke/manual_live_smoke_20260703_002837/tushare_daily_basic/metrics_draft.csv `
  --ingest-runs-path data/raw/live_smoke/manual_live_smoke_20260703_002837/tushare_daily_basic/ingest_runs.csv `
  --readout-output data/raw/live_smoke/manual_live_smoke_20260703_002837/tushare_daily_basic/readout.json
```

## 6. Tushare Financial Statement Smoke

Run each endpoint separately so failures stay isolated:

```powershell
conda run -p .\.conda\investment-system python -m src.ingest.adapters.tushare_adapter `
  --repo-root . `
  --api-name income `
  --stock-code 002837 `
  --company-id cn_002837_invic `
  --mode live `
  --allow-network `
  --start-date 20250101 `
  --end-date 20260701 `
  --as-of-date 2026-07-01 `
  --fields ts_code,ann_date,f_ann_date,end_date,report_type,comp_type,total_revenue,revenue,n_income_attr_p,basic_eps `
  --raw-dir data/raw/live_smoke/manual_live_smoke_20260703_002837/tushare_income/raw `
  --normalized-dir data/raw/live_smoke/manual_live_smoke_20260703_002837/tushare_income/normalized `
  --manifest-path data/raw/live_smoke/manual_live_smoke_20260703_002837/tushare_income/evidence_manifest.csv `
  --metrics-path data/raw/live_smoke/manual_live_smoke_20260703_002837/tushare_income/metrics_draft.csv `
  --ingest-runs-path data/raw/live_smoke/manual_live_smoke_20260703_002837/tushare_income/ingest_runs.csv `
  --readout-output data/raw/live_smoke/manual_live_smoke_20260703_002837/tushare_income/readout.json
```

Repeat with `--api-name balancesheet`, `--api-name cashflow`, and `--api-name fina_indicator`, changing `--fields` to the reviewed field list for each endpoint.

## 7. Baostock K-line Smoke

```powershell
conda run -p .\.conda\investment-system python src\ingest\adapters\baostock_adapter.py `
  --repo-root . `
  --api-name query_history_k_data_plus `
  --stock-code 002837 `
  --company-id cn_002837_invic `
  --mode live `
  --allow-network `
  --start-date 2026-06-01 `
  --end-date 2026-07-01 `
  --as-of-date 2026-07-01 `
  --fields date,code,open,high,low,close,volume,amount,adjustflag `
  --raw-dir data/raw/live_smoke/manual_live_smoke_20260703_002837/baostock_kline/raw `
  --normalized-dir data/raw/live_smoke/manual_live_smoke_20260703_002837/baostock_kline/normalized `
  --manifest-path data/raw/live_smoke/manual_live_smoke_20260703_002837/baostock_kline/evidence_manifest.csv `
  --metrics-path data/raw/live_smoke/manual_live_smoke_20260703_002837/baostock_kline/metrics_draft.csv `
  --ingest-runs-path data/raw/live_smoke/manual_live_smoke_20260703_002837/baostock_kline/ingest_runs.csv `
  --readout-output data/raw/live_smoke/manual_live_smoke_20260703_002837/baostock_kline/readout.json
```

## 8. Baostock Financial Smoke

Run one endpoint at a time:

```powershell
conda run -p .\.conda\investment-system python src\ingest\adapters\baostock_adapter.py `
  --repo-root . `
  --api-name query_profit_data `
  --stock-code 002837 `
  --company-id cn_002837_invic `
  --mode live `
  --allow-network `
  --end-date 2026-06-30 `
  --as-of-date 2026-06-30 `
  --raw-dir data/raw/live_smoke/manual_live_smoke_20260703_002837/baostock_profit/raw `
  --normalized-dir data/raw/live_smoke/manual_live_smoke_20260703_002837/baostock_profit/normalized `
  --manifest-path data/raw/live_smoke/manual_live_smoke_20260703_002837/baostock_profit/evidence_manifest.csv `
  --metrics-path data/raw/live_smoke/manual_live_smoke_20260703_002837/baostock_profit/metrics_draft.csv `
  --ingest-runs-path data/raw/live_smoke/manual_live_smoke_20260703_002837/baostock_profit/ingest_runs.csv `
  --readout-output data/raw/live_smoke/manual_live_smoke_20260703_002837/baostock_profit/readout.json
```

Repeat with `query_balance_data`, `query_cash_flow_data`, and `query_dupont_data` only if the prior endpoint finishes and writes a clean readout.

## 9. Output Review

For each endpoint, inspect:

```powershell
Get-Content data/raw/live_smoke/manual_live_smoke_20260703_002837/<endpoint>/readout.json
Get-Content data/raw/live_smoke/manual_live_smoke_20260703_002837/<endpoint>/evidence_manifest.csv
Get-Content data/raw/live_smoke/manual_live_smoke_20260703_002837/<endpoint>/metrics_draft.csv
```

Check:

- `result` is `SUCCESS` or explicitly blocked with reason.
- `api_params_hash` exists.
- token value is absent.
- raw snapshot exists.
- normalized table exists.
- metric candidates are metric-only.
- no report artifact changed.

## 10. Git Safety Check

```powershell
git status --short
git diff --check
git grep -n "token_value"
git grep -n "TUSHARE_API_URL" -- .env.example src\ingest src\utils scripts
```

Do not commit live raw responses unless they are reviewed, desensitized if needed, and explicitly approved.

## 11. Cleanup Or Isolation

Preferred default: keep the temporary directory ignored and local-only until the user reviews it.

If a single accidental file must be removed, remove one explicit file path at a time:

```powershell
Remove-Item "C:\Projects\03_Investment_System\data\raw\live_smoke\manual_live_smoke_20260703_002837\example\readout.json"
```

Do not use recursive deletion. If many files or directories need cleanup, stop and ask the user to delete them manually.

## 12. Failure Handling

| failure | action |
|---|---|
| missing token | stop Tushare smoke and keep blocked readout only |
| package missing | stop that adapter and keep blocked readout only |
| canonical endpoint missing / invalid | stop; update private `TUSHARE_HTTP_URL`; do not add a fallback |
| permission / rate limit | stop that endpoint and record issue |
| empty response | record partial/blocked readout; do not invent rows |
| token appears in output | stop immediately; do not commit; ask for manual cleanup |
| report file changed | stop and inspect diff before any further command |

## 13. Outputs Not To Commit By Default

- live raw response CSV / JSON
- endpoint readout containing environment-specific details
- temporary manifests under `data/raw/live_smoke/`
- any file containing token values or private account information
- any report generated from live smoke without a separate evidence review step
