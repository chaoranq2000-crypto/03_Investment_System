# a-stock-data 作为证据与市场数据管线参考的边界说明

## 1. 定位

`a-stock-data` 不作为本项目的平级核心 skill，也不直接复制到 `.agents/skills/`。

它的正确定位是：

```text
A 股数据源目录 + adapter 经验库 + fallback 参考 + 限流/防封经验参考
```

不是：

```text
证据库 workflow
研究分析 workflow
报告生成 workflow
投资建议 workflow
```

## 2. 可借鉴内容

可借鉴：

```text
1. 数据源分层：行情、研报、信号、资金面、新闻、基础数据、公告、情绪互动等。
2. 数据源优先级：低风控源优先，东财等源限流，独有数据才使用。
3. 巨潮公告、互动易、东财、同花顺、腾讯、mootdx、新浪等源的接口线索。
4. 速率限制、fallback、字段漂移、接口失效记录方式。
5. 市场情绪、技术分析、事件驱动章节所需的数据候选。
```

## 3. 不能借鉴的工作流形态

不能照搬：

```text
- 单个超大 SKILL.md。
- 直接查数据后写估值结论。
- 直接把新闻/热榜/互动问答写成事实。
- 让数据工具绕过 evidence_manifest。
- 让 adapter 直接输出报告段落。
```

## 4. 本项目吸收方式

建议在 `evidence-ingest` 下吸收：

```text
.agents/skills/evidence-ingest/references/a_share_data_adapter_boundary.md
src/ingest/adapters/
  cninfo_adapter.py
  eastmoney_adapter.py
  tencent_quote_adapter.py
  tushare_adapter.py
  baostock_adapter.py
  market_sentiment_adapter.py
```

所有 adapter 输出必须进入：

```text
data/raw/
data/processed/
data/manifests/evidence_manifest.csv
data/processed/candidates/metric_candidates_*.csv
data/manifests/clue_log.csv
```

## 5. source 用途矩阵

| 来源类型 | 可支撑内容 | 不能支撑内容 | 默认等级 |
|---|---|---|---|
| 巨潮/交易所公告 | 公司事实、财务事实、业务披露 | 未披露的业务占比 | A |
| 年报 PDF | 业务拆分、财务、客户、风险 | 行业预测 | A |
| Tushare/Baostock | 财务指标、行情、估值、时间序列 | 业务暴露事实 | B |
| 东财/腾讯/新浪行情 | 价格、估值、资金线索 | 业务事实 | B/C |
| 互动易 | 管理层回应、待验证线索 | 已实现收入事实 | C |
| 券商研报 | 预测、观点、行业估算 | 公司已披露事实 | C |
| 新闻/热榜/社媒 | 情绪和 clue | material claim | D |

## 6. 进入报告的方式

```text
adapter output
  → evidence-ingest
  → metric_candidates / clue_log / event_candidates
  → quality-review
  → market_sentiment_pack / technical_snapshot / catalyst_calendar
  → stock-report-writer
```

不得：

```text
adapter output → stock-report-writer → final report
```

## 7. Codex 执行建议

先做轻量子集，不追求一口气复刻 40 个端点：

```text
P0 子集：
- Tushare / Baostock 财务指标与行情快照。
- 巨潮/交易所公告下载或登记。
- 腾讯/东财行情估值快照。

P1 子集：
- 融资余额 / 成交额 / 换手率。
- 公告事件日历。
- 互动易或新闻 clue。

P2 子集：
- 研报列表 / 一致预期。
- 主题热度 / 龙虎榜 / 资金流。
```
