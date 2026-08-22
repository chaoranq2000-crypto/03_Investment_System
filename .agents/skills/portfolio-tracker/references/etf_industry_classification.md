# ETF industry classification

The portfolio dashboard uses a deliberately small, reviewed mapping. It does not calculate ETF industry exposure from constituents.

## Source of truth

`config/portfolio_industry_taxonomy.json` → `etf_overrides`

Every entry must contain:

```json
{
  "industry_name": "互联网",
  "index_code": "HSIII.HI",
  "index_name": "恒生互联网科技业",
  "reviewed_at": "YYYY-MM-DD",
  "evidence_source": "tushare.etf_basic"
}
```

## Runtime rule

1. Match by exact ETF `ts_code`.
2. If available, compare live `tushare.etf_basic` `index_code` and `index_name` with the reviewed entry.
3. A match uses the configured dashboard industry.
4. A mismatch or absent entry returns `未分类（ETF需复核映射）`.
5. If `etf_basic` is temporarily unavailable, the dated reviewed entry may still be displayed with `verification=reviewed_config`.

Do not fetch daily baskets, constituent industries, or constituent prices for this dashboard label. Do not infer from the ETF name. Wide or cross-industry ETFs should be explicitly mapped to `跨行业ETF` when reviewed.

When adding or changing an entry, record the new review date and add/update a focused unit test.
