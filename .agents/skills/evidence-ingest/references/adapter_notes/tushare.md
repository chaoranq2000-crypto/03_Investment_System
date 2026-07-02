# Tushare Adapter Notes

Tushare is the primary structured-data adapter for this workspace, not an official filing substitute.

## B1 handling

B1 should define the adapter contract and store snapshots. Full production adapters can be added later under `src/ingest/`.

## Required snapshot metadata

```json
{
  "source_name": "tushare",
  "api_name": "daily | income | balancesheet | cashflow | fina_indicator | ...",
  "params": {},
  "fields": [],
  "as_of_date": "YYYY-MM-DD",
  "retrieved_at": "YYYY-MM-DDTHH:MM:SSZ",
  "token_env": "TUSHARE_TOKEN",
  "permission_note": "points/frequency dependent",
  "api_params_hash": "sha256"
}
```

## Output boundary

- Save raw response under `data/raw/market_data/` or `data/raw/financial_data/`.
- Save normalized outputs under `data/processed/normalized/`.
- Generate `metric_candidates` only.
- Set `material_claim_allowed=metric_only`.
- Do not support revenue exposure claims without official filing evidence.

## Failure handling

- Missing token: `FAILED` or `PARTIAL_SUCCESS` with TODO.
- Permission/frequency limit: log issue and retry/backoff later.
- Empty response: write issue; do not invent metrics.
- Field drift: write issue and preserve raw snapshot.
