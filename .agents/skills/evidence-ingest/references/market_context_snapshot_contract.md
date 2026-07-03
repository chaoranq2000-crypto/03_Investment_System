# Market Context Snapshot Contract — 行情、估值、技术、情绪快照契约

## 1. 目标

市场上下文层为样例质量个股报告提供以下输入：

```text
股价 / 市值 / PE / PB / PS / 换手率
区间涨跌幅 / 52 周高低 / 均线 / 成交量
板块归属 / 行业涨跌 / 主题热度
资金流 / 融资融券 / 大宗交易 / 龙虎榜
研报列表 / 一致预期 / EPS forecast
新闻线索 / 热榜 / 互动易问答
```

这些数据用于 market context、valuation、technical、sentiment、event sections。默认不能证明公司业务事实。

## 2. 数据产品

### 2.1 valuation_snapshot.yaml

```yaml
stock_code:
company_id:
as_of_date:
sources:
  - source_name:
    evidence_id:
    api_params_hash:
market_values:
  price:
  market_cap:
  float_market_cap:
  pe_ttm:
  pe_forward:
  pb:
  ps:
  turnover_rate:
  volume:
  amount:
notes:
missing_fields: []
```

### 2.2 technical_snapshot.yaml

```yaml
stock_code:
as_of_date:
price_series_source:
adjustment_policy: none | qfq | hfq | unknown
windows:
  daily:
    ma5:
    ma10:
    ma20:
    ma60:
    pct_chg_20d:
    pct_chg_60d:
    volume_ratio:
  weekly:
    ma5:
    ma10:
    ma20:
support_resistance:
  source_method: computed | manual | unknown
  levels: []
notes:
```

### 2.3 market_sentiment_pack.yaml

```yaml
stock_code:
as_of_date:
market_regime:
sector_context:
capital_flow:
  source_name:
  metrics: []
hotlist_and_concepts:
  clue_items: []
news_clues:
  clue_items: []
analyst_context:
  report_count:
  consensus_eps:
  target_price_range:
  note: analyst_view_only
limitations:
```

### 2.4 peer_market_snapshot.csv

必备字段：

```text
as_of_date, stock_code, company_name, peer_group, price, market_cap,
pe_ttm, pe_forward, pb, ps, revenue_ttm, net_profit_ttm,
source_name, evidence_id, notes
```

## 3. Source rank defaults

| endpoint class | examples | rank | material claim |
|---|---|---|---|
| exchange/official market data | exchange data, official quote if available | A/B | metric_only |
| structured market database | Tushare daily_basic, Baostock K line | B | metric_only |
| public HTTP market data | Tencent, mootdx, Sina, Baidu, Eastmoney push2 | B/C | metric_only |
| fund flow / hotlist / sector signal | Eastmoney, THS | C/D | clue_only unless numeric market metric |
| news / social / popularity | Eastmoney news, hotlists, social | D | clue_only |
| brokerage reports / consensus | Eastmoney reportapi, THS consensus | C | analyst_view / estimate |

## 4. a-stock-data-inspired routing principles

参考但不复制 a-stock-data 的做法：

1. 行情和估值优先选低风控、稳定源。
2. 东财类接口只用于独有数据或 fallback，并统一限流、重试、session reuse。
3. 每个 endpoint 的字段映射必须记录，避免错读字段。
4. 批量任务必须有 interval / jitter / retry policy。
5. 任何接口失效都应写入 adapter risk notes，而不是让报告静默缺数据。

## 5. 输出边界

允许：

```text
- 生成 market metric candidates。
- 生成 technical/valuation/sentiment packs。
- 为 stock-deep-dive 提供估值和情绪上下文。
- 为 compare-stocks 提供可比估值表。
```

禁止：

```text
- 由资金流推出公司基本面改善。
- 由热榜推出真实订单。
- 由研报评级推出事实结论。
- 由概念标签推出 segment revenue exposure。
- 由短期技术形态生成买卖建议。
```

## 6. Minimum freshness rules

| data kind | stale_after | refresh trigger |
|---|---|---|
| daily price / valuation | 1 trading day | every report run |
| technical snapshot | 1 trading day | every report run |
| fund flow / hotlist | same day | clue only |
| consensus EPS / report metadata | 30-90 days | new report or earnings period |
| sector membership | 30 days | sector change or report run |
| financial statements | until next periodic report | new filing |

## 7. Quality issues

| issue | severity | handling |
|---|---|---|
| missing price/date for valuation_snapshot | high if report uses valuation | block valuation section |
| source field mapping unknown | high | do not promote metric |
| no api_params_hash | medium | cannot accept as reproducible snapshot |
| hotlist/news used as fact | high | downgrade to clue or remove |
| stale valuation snapshot | medium | refresh or mark stale |
| no peer group source | medium | peer comparison TODO |
