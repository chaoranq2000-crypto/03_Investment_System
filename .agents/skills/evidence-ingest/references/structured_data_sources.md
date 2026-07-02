# Structured Data Sources

## Positioning

Tushare and Baostock are structured data sources. They are useful for market data, financial statements, indicators and historical quotes, but they do not replace official annual reports, announcements or exchange filings for company business-exposure claims.

## Tushare default role

- Source group: `structured_database`
- Default rank: B
- Default material support: `metric_only`
- Typical outputs: raw API snapshot, normalized metrics, metric candidates, API parameter hash.
- Common categories: A-share daily/weekly/monthly data, adjusted bars, daily basic indicators, moneyflow, margin, block trades, holders, income statement, balance sheet, cash flow, forecast, express, dividend, financial indicators, business composition, index/macro/fund/futures/options data depending on permission.
- Operational constraints: token, points, permission and frequency limits.

## Baostock default role

- Source group: `structured_database_fallback`
- Default rank: B/C depending on use.
- Default material support: `metric_only`.
- Typical outputs: historical K-line DataFrame, valuation/trading fields, raw CSV snapshot.
- Common fields include open/high/low/close, volume, amount, adjust flag, turnover, trade status, pct change, PE/PB/PS/PCF and ST flag where available.

## API snapshot requirements

Every `structured_api_pull` must record:

- `source_name`;
- `api_name`;
- full input params;
- requested fields;
- date range/as-of date;
- retrieval time;
- raw file path;
- `api_params_hash`;
- metric candidate output path;
- limitations such as frequency, permission or missing fields.

## Forbidden inference

Do not infer segment revenue exposure from total revenue, total profit, market cap, price changes or financial ratios.
