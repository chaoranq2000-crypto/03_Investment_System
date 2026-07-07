# R5 Technical Market Pack Contract

## Purpose

`r5_technical_market_pack` carries dated market-state inputs for the R5 technical-analysis section. It does not create trading actions.

## Required fields

```yaml
artifact_type: R5_technical_market_pack
as_of_date:
current_price:
return_1m:
return_3m:
return_6m:
return_12m:
ytd_return:
52w_high:
52w_low:
MA5:
MA10:
MA20:
MA60:
turnover:
volume_percentile:
support_levels: []
resistance_levels: []
```

Each support/resistance row must contain `level`, `basis`, and `source_id_or_missing_reason`.

## Boundaries

- Missing `as_of_date` blocks market-state language.
- Missing numeric market fields must remain `TODO_MARKET_DATA`.
- Support/resistance rows are observations, not action instructions.
- No buy/sell/hold, stop-loss, position-sizing, or target-price instruction.
