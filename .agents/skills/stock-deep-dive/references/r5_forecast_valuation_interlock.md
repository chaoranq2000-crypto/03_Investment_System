# R5 Forecast Valuation Interlock

status: `contract`

Forecast and valuation outputs must distinguish historical metric anchors from
forward estimates.

Rules:

- Historical company-level revenue can be retained as an anchor.
- Without reviewed assumptions, `revenue_forecast`, margin forecast, net profit
  forecast, EPS forecast, and valuation inputs must remain TODO.
- Builders must not inject default 8%, 10%, or similar growth assumptions.
- Market and peer inputs are required before valuation context can move beyond
  TODO.
- This contract does not permit target prices, direct trading actions, position
  sizing, or sample-quality report promotion.
