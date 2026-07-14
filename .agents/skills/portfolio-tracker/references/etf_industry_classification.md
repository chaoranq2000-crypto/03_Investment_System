# ETF holdings-driven industry classification

Use this reference whenever an ETF needs an industry label or industry exposure summary.

## Evidence priority

1. Use the latest exchange-disclosed daily creation/redemption basket: Tushare `etf_sh_cons` or `etf_sz_cons`.
2. Use the latest disclosed `fund_portfolio` holdings and `stk_mkv_ratio` when available; retain its `ann_date` and `end_date` and label it as quarterly disclosure rather than current holdings.
3. Use `etf_basic.index_code` and `index_name` only to corroborate a constituent-derived result or select a reviewed aggregation rule after holdings coverage passes.
4. Use the ETF name only as an explicitly labeled low-confidence fallback when no usable holdings source exists. Never call this fallback holdings-derived.

## Constituent normalization

- Exclude cash placeholders such as `申赎现金` from equity-industry weights.
- Preserve every constituent code, exchange, source date, raw industry, normalized level-1 industry, and weight method.
- For A-share constituents, use Tushare `stock_basic.industry` as the raw industry and map it through the reviewed portfolio taxonomy.
- For HK constituents, first try a reviewed structured company-profile source. The current runtime fallback is Eastmoney F10 `RPT_HKF10_INFO_ORGPROFILE.BELONG_INDUSTRY`, fetched in batches and source-labeled. If it is unavailable or blank, retain `UNVERIFIED_CONSTITUENT_INDUSTRY`; do not infer the industry from the company name alone.
- For same-date HK closes, try Tushare `hk_daily` only when permission is available, then use the source-labeled Sina `stock_hk_daily` adapter. A current price must not be substituted for the basket date's close.
- For other markets without a reviewed industry and same-currency price source, retain unverified coverage instead of forcing a label.
- Prefer disclosed market-value ratios. Otherwise calculate `quantity * same-date close` only when price, currency, and quantity coverage are comparable. Do not mix currencies or treat cash-substitution amounts as equity market values.
- A reviewed theme aggregation may use `index_name` only to select a machine-readable aggregation rule after holdings coverage passes. The selected rule must still meet its configured minimum share using constituent-derived industry weights; index or ETF text alone cannot satisfy the rule.

## Decision policy

Calculate weights over the usable equity basket and report both `classified_weight_coverage` and `constituent_count_coverage`.

- If classified weight coverage is below `70%`, output `未分类（ETF持仓覆盖不足）`.
- If the largest normalized level-1 industry is at least `80%`, assign it with `high` confidence.
- If it is at least `60%` but below `80%`, assign it with `medium` confidence and display the leading share.
- If it is below `60%`, output `跨行业ETF` and retain the top industry distribution instead of forcing one label.
- Treat results older than the configured freshness window as stale. Preserve the last result for display only with an explicit stale marker; do not refresh its confidence date.

Keep thresholds in machine-readable configuration when runtime support is added; do not scatter alternative thresholds through code or prompts.

For example, `portfolio_industry_v1` may aggregate reviewed internet-compatible industries only when the tracking index contains the configured `互联网` keyword and those constituent-derived industries total at least `80%`. Record `index_role=theme_aggregation_selector`; otherwise retain `index_role=corroboration_only`.

## Required output

Retain or emit:

```yaml
etf_code: 159892.SZ
classification: 未分类（ETF持仓覆盖不足）
classification_level: level_1
confidence: low
source_type: exchange_daily_basket
source_date: YYYYMMDD
weight_method: quantity_times_close
classified_weight_coverage: null
constituent_count_coverage: null
top_industries: []
unverified_constituents: []
corroborating_index_name: null
fallback_used: false
```

Batch public fallback requests where supported, preserve the upstream field name and endpoint in `industry_source`, and keep provider failure as an explicit coverage gap. Store private constituent evidence only under ignored `data/db/` paths. Never commit the user's ETF list or portfolio-derived classification cache.
