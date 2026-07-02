# Baostock Adapter Notes

Baostock is a structured market-data fallback. It is useful for historical A-share quotes and basic valuation/trading fields.

## B1 handling

B1 should define and validate snapshot handling. Full production adapter implementation can come later.

## Expected flow

```text
login
→ query_history_k_data_plus or equivalent query
→ collect DataFrame
→ save raw CSV snapshot
→ compute file_hash and api_params_hash
→ write manifest row
→ generate metric candidates
→ logout
```

## Output boundary

- Source group: `structured_database_fallback`.
- Default material support: `metric_only`.
- Do not use Baostock to prove company business exposure, customer orders, revenue share or segment purity.

## Failure handling

- Login failure: `FAILED`.
- Empty result: `PARTIAL_SUCCESS` with issue.
- Missing fields: preserve raw result and mark metric candidates incomplete.
