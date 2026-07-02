# Structured API Pull Runner Contract

## Purpose

`structured_api_pull` acquires structured market or financial data snapshots from approved adapters or local fixtures and registers them as evidence-layer metric snapshots.

It is metric-only by default.

## Supported first-pass APIs

```text
stock_basic
income
balancesheet
cashflow
fina_indicator
daily_basic optional
```

## Inputs

```text
source_name: tushare | baostock | local_fixture
api_name:
stock_code:
ts_code:
date_range:
fields:
input_csv or input_json for offline/debug mode
```

## Required metadata

```text
api_name
api_params_hash
fields
retrieved_at
as_of_date
source_name
source_type
stock_code
raw_file_path
processed_table_path
```

## Outputs

```text
data/raw/market_data/<snapshot>.csv|json
data/processed/normalized/<snapshot>.csv
data/manifests/evidence_manifest.csv
data/manifests/metrics_draft.csv
data/processed/logs/<evidence_id>__ingest_log.json
```

## Guardrails

- Structured snapshots do not replace official filings for business-exposure claims.
- Structured snapshots should generate `metric_candidates`, not `claim_candidates`, unless a separate reviewed rule explicitly allows a non-material operational claim.
- Missing token, missing permission, rate limit, empty DataFrame and field drift must be recorded as TODO or PARTIAL_SUCCESS, not hidden.
- API response parameters must be hashed and recorded in `api_params_hash`.
- Always keep a raw snapshot even if a normalized table is also created.

## Offline-first implementation

The first implementation should support local CSV/JSON fixtures so tests can run without external network or API tokens.

Real adapters can be added later behind the same output contract.
