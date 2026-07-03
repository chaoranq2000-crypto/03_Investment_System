# Source Adapter Matrix — 数据源适配器矩阵

> 本文件用于指导 `evidence-ingest` 的数据层路由。它参考 a-stock-data 的分层思路，但不复制其代码；所有 adapter 输出必须回到本项目的 manifest / candidates / quality gates。

## 1. 分层矩阵

| layer | source_name | source_group | primary use | default rank | material claim | output kind | fallback |
|---|---|---|---|---|---|---|---|
| official_disclosure | cninfo | official_disclosure | 年报、半年报、季报、公告、问询回复 | A | requires extraction + review | raw file, claim candidates | sse/szse/bse |
| official_disclosure | sse | official_disclosure | 上交所公告与定期报告 | A | requires extraction + review | raw file, claim candidates | cninfo |
| official_disclosure | szse | official_disclosure | 深交所公告与定期报告 | A | requires extraction + review | raw file, claim candidates | cninfo |
| official_disclosure | bse | official_disclosure | 北交所公告与定期报告 | A | requires extraction + review | raw file, claim candidates | cninfo |
| structured_financial | tushare | structured_database | 财务三表、财务指标、主营构成、披露日、日行情、估值 | B | metric_only | metric candidates, normalized tables | baostock/manual fixture |
| structured_market | baostock | structured_database_fallback | 历史 K 线、基础行情、部分季度财务 fallback | B/C | metric_only | metric candidates, normalized tables | local fixture |
| market_context | mootdx | market_data_adapter | K 线、盘口、F10、行情快照 | B/C | metric_only | market metrics | baostock/tencent |
| market_context | tencent_finance | market_data_adapter | 实时价、PE/PB、市值、换手、涨跌停 | B/C | metric_only | valuation snapshot | tushare/daily_basic |
| market_context | baidu_kline | market_data_adapter | K 线与均线补充 | C | metric_only | technical snapshot | baostock |
| market_context | eastmoney_push2 | market_data_adapter | 板块、资金、两融、大宗、新闻、研报列表 | C/D | metric_only or clue_only | market metrics, clue_log | tencent/manual |
| market_context | ths | market_signal_adapter | 热点、北向、一致预期、题材归因 | C/D | clue_only except consensus estimate | clue_log, estimate candidates | eastmoney/manual |
| market_context | sina | market_data_adapter | 财报三表/ETF 期权/财经数据补充 | C | metric_only | metric candidates | tushare |
| research_context | brokerage_report | third_party_analysis | 预测、评级、行业观点 | C | false | analyst_view / estimate | none |
| clue | news_social | clue | 新闻、热榜、社媒、概念标签 | D | false | clue_log only | official verification |

## 2. 路由规则

### 2.1 公司事实

优先级：

```text
cninfo / exchange filing > company official disclosure > parsed annual report table > structured database > third-party research > news/social
```

结构化数据库不能证明：

```text
revenue exposure
customer order
capacity status
segment purity
business line profitability
```

### 2.2 财务指标

优先级：

```text
official report table if parsed
→ Tushare financial statements / fina_indicator
→ Baostock quarterly financial fallback
→ manual fixture with source note
```

如果多个源不一致：

```text
create reconciliation_issue
keep both values
promote only after review
```

### 2.3 行情和估值

优先级：

```text
Tushare daily_basic / pro_bar / daily
→ Tencent valuation snapshot
→ Baostock historical K line
→ local market fixture
```

必须记录：

```text
trade_date
as_of_date
adjustment policy
currency
unit
source endpoint
api_params_hash
```

### 2.4 情绪和市场线索

优先级不是可信度排序，而是用途分层：

```text
fund_flow / turnover / limit-up / sector move → market metric / signal
hotlist / concept hit / news → clue
research report / consensus EPS → analyst_view or estimate
```

不得从情绪层直接推出公司基本面结论。

## 3. Adapter status labels

| status | meaning |
|---|---|
| planned | 只有契约，未实现 |
| offline_fixture_supported | 可用本地 CSV/JSON fixture 登记 |
| api_supported_unverified | 已能调用 API，但未完成字段/频率/异常测试 |
| production_supported | 有测试、有失败处理、有 manifest/candidate/run log |
| deprecated | 接口不稳定或已下线 |
| blocked | 需要 token、网络、权限或人工输入 |

## 4. 首批落地顺序

```text
1. Tushare structured financial adapter
2. Baostock fallback market adapter
3. Official disclosure search/download hardening
4. Tencent/Tushare valuation snapshot
5. Baostock/Tushare K-line technical snapshot
6. Eastmoney/THS clue-only market sentiment snapshot
7. Research report metadata/PDF registration
```

## 5. 禁止路径

```text
❌ adapter → stock_report.md
❌ adapter → watchlist.yaml
❌ hotlist/news → company fact
❌ brokerage EPS → reported EPS
❌ structured snapshot → revenue exposure without official disclosure
```

正确路径：

```text
adapter → raw/processed snapshot → manifest → candidates → quality-review → registry/pack → report skill
```
