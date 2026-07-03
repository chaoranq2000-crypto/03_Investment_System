# A-share Data Adapter Boundary

## 1. Purpose

This file defines how public A-share data adapters may be used inside `evidence-ingest`.

The project may reference ideas from `a-stock-data`, Tushare and Baostock, but all outputs must enter the evidence/metric/clue layer before any report uses them.

## 2. Adapter categories

```yaml
adapter_categories:
  official_disclosure:
    examples: [cninfo, sse, szse, bse]
    output: evidence + claim_candidates
  structured_financial:
    examples: [tushare, baostock]
    output: metric_candidates
  market_quote:
    examples: [tushare, baostock, tencent, eastmoney]
    output: market_snapshot + metric_candidates
  market_sentiment:
    examples: [eastmoney, tonghuashun, financing_margin, hot_rank]
    output: sentiment_snapshot + clue_log
  research_report:
    examples: [eastmoney_reportapi, iwencai]
    output: report_clues + estimate_candidates
  interactive_response:
    examples: [irm_cninfo, hudongyi]
    output: management_comment_candidates + clue_log
```

## 3. Hard boundary

```text
Adapters do not write final reports.
Adapters do not write segment exposure.
Adapters do not promote claims.
Adapters do not make research conclusions.
Adapters do not decide watchlist status.
```

## 4. Source-rank defaults

```yaml
source_rank_defaults:
  official_disclosure: A
  exchange_data: A
  structured_financial: B
  market_quote: B
  research_report: C
  management_interaction: C
  news_or_hot_rank: D
```

## 5. Output requirements

Every adapter run must produce:

```text
raw snapshot
normalized snapshot
metadata file
manifest row or clue row
candidate rows if applicable
ingest_log
```

## 6. Rate limit and failure metadata

Each adapter call should record:

```yaml
adapter_name:
endpoint:
query_params:
request_time:
response_status:
retry_count:
rate_limit_policy:
fallback_used:
field_list:
api_params_hash:
license_note:
```

## 7. Report use policy

| Adapter output | Report usage |
|---|---|
| official disclosure claim | Can support material fact after review |
| structured financial metric | Can support financial analysis after normalization |
| market quote snapshot | Can support technical/valuation section with date |
| sentiment clue | Can support emotion section only as clue, with date |
| research report estimate | Can support consensus/third-party view, not fact |
| interactive response | Can support management comment, not verified revenue |

## 8. Minimum useful adapters for R3 report

For target sample-quality report, Codex should implement or wrap at least:

```text
1. official_disclosure_pull: annual/interim/quarterly reports and announcements.
2. structured_api_pull: income, balance sheet, cashflow, fina_indicator, daily_basic.
3. market_snapshot_pull: price, market cap, PE/PB/PS, turnover, volume.
4. technical_snapshot_builder: MA5/10/20/60/120, recent high/low, volume trend.
5. event_candidate_builder: earnings preview windows, shareholder meetings, major announcements.
```
