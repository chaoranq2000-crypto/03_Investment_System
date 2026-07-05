# Stock Report Quality Upgrade Plan — 对齐样例质量的四段式完善计划

> 本计划用于把当前 `stock_first_closed_loop` 从 debug MVP 升级为可生成高质量个股研究报告的生产型 workflow。它不是交易系统，也不直接生成买卖指令；最终报告应达到样例报告的研究深度、结构完整度和表达质量，但输出口径应保持“研究结论 / 观察清单 / 风险收益结构 / 可证伪条件”，避免无证据荐股。

## 1. 目标状态

当前个股闭环已经能跑通：证据登记、指标候选、报告草案、细分暴露、质量门和 readout。但它仍属于 debug 产物，无法达到样例报告的成品标准。目标是升级为以下链路：

```text
股票输入
  ↓
证据搜集与处理
  ↓
claims / metrics / clues / gaps
  ↓
研究分析与建模
  ↓
stock_analysis_pack.yaml
  ↓
研报生成与表达
  ↓
stock_report_sample_quality.md
  ↓
质量审查
  ↓
claims / metrics / exposure / report / watchlist 回写维护
```

最终报告至少覆盖：

```text
前言 / 核心主线
财务概览
业务拆分
行业分析
盈利预测
估值分析
技术分析
情绪分析
事件驱动
研究结论、风险、反证、后续跟踪
```

## 2. 四个建设模块

### 2.1 模块一：证据搜集与处理

目标：把 PDF、公告、财务结构化数据、行情数据、互动问答、研报线索和新闻线索变成可追溯的 evidence / claim / metric / clue / gap。

可用资源：

```text
1. 本地 MinerU：处理年报、半年报、公告 PDF，生成 markdown / json / layout / table 输出。
2. Tushare / Baostock：拉取财务报表、财务指标、行情、估值和部分市场数据。
3. a-stock-data：作为 A 股数据源目录、接口 fallback 和限流/防封经验参考，不直接成为主 workflow。
```

关键原则：

```text
- 官方披露优先于第三方数据。
- Tushare / Baostock 默认只能生成 metric_candidates，不能替代年报证明业务暴露。
- a-stock-data 只能作为 adapter 参考或 clue/market-data 线索来源，不能绕过 evidence-ingest。
- 所有 PDF 解析都必须输出 page_map / table_map / parse_log。
- 所有 material claim 必须有 evidence_id + page/table locator + quote_or_excerpt。
- 缺证据时，不允许补写；必须生成 evidence_gap_request。
```

### 2.2 模块二：研究分析与建模

目标：从候选证据生成 `stock_analysis_pack.yaml`，不是直接写报告。

分析层必须完成：

```text
1. 公司身份与业务主线识别。
2. 财务质量分析。
3. 分业务收入、毛利率、利润贡献、成长性和现金流质量拆解。
4. linked_segments 和 segment_exposure 初步判定。
5. 简版行业研究卡：需求、供给、竞争、价格/利润池、关键指标。
6. 三年盈利预测。
7. 估值场景与同业比较。
8. 技术面 / 情绪面 / 事件面数据整理。
9. 风险、反证、可证伪条件。
10. 证据缺口回传给 evidence-ingest。
```

行业研究可以先做轻量版，但必须至少回答：

```text
- 这个细分为什么重要？
- 当前需求驱动是什么？
- 供给和竞争格局是什么？
- 公司处在价值链什么位置？
- 哪些指标能验证景气度和公司兑现？
```

### 2.3 模块三：研报生成与表达

目标：用 `stock_analysis_pack.yaml` 生成接近样例报告表达质量的报告。

报告写作只能使用已审查或明确标注为 draft 的结构化输入：

```text
claims_registry / reviewed_claim_candidates
metrics_registry / reviewed_metric_candidates
segment_exposure.yaml
industry_context_card.yaml
forecast_model.yaml
valuation_model.yaml
market_sentiment_pack.yaml
catalyst_calendar.yaml
risk_counter_evidence.yaml
```

报告可以有叙事，但叙事必须来自可追溯的事实、指标、假设和推断。禁止为了像样例而自动编造大段行业数据、目标价、仓位建议、机构观点或未核验事件。

### 2.4 模块四：质量审查与回写维护

目标：把质量门从“是否有报告”升级为“报告是否达到样例级研究闭环”。

质量门必须覆盖：

```text
G1 Evidence Completeness Gate
G2 Claim Locator Gate
G3 Metric Normalization Gate
G4 Business Breakdown Gate
G5 Segment Exposure Gate
G6 Forecast Model Gate
G7 Valuation Gate
G8 Technical / Sentiment / Event Gate
G9 Report Expression Gate
G10 No Unsupported Advice Gate
G11 Backflow & Registry Gate
```

通过后才能进入：

```text
accepted_with_todos
accepted_sample_quality
```

不能因为报告写得流畅就跳过证据、口径和回写。

## 3. 质量等级

| 等级 | 名称 | 用途 | 允许缺口 |
|---|---|---|---|
| R0 | debug_mvp | 验证 workflow 是否跑通 | 大量 TODO，不能作为研究报告 |
| R1 | evidence_complete | 年报/公告/财务数据已处理 | 行业和估值可简略 |
| R2 | analysis_complete | 业务拆解、暴露、财务、初步预测完成 | 技术/情绪/事件可较简 |
| R3 | sample_quality_draft | 接近样例报告结构和表达 | 少量非阻塞 TODO |
| R4 | maintained_report | 可更新、可回写、可复盘 | 无 high issue，关键结论可追溯 |

当前 002837 应先从 R0 升到 R1，再升 R2/R3。

## 4. 工作流入口

当前已合并为一个下层 skill：

```text
stock-deep-dive
    负责研究分析、建模和研报草稿生成，输出 stock_analysis_pack.yaml 与 sample-quality draft。
```

保留：

```text
evidence-ingest
quality-review
segment-company-mapping
research-orchestrator
```

`stock-deep-dive` 可以继续作为旧入口或轻量 wrapper，但目标流程应逐步拆成：

```text
research-orchestrator
  → evidence-ingest
  → stock-deep-dive
  → quality-review
  → segment-company-mapping / refresh-research
```

## 5. Codex 执行顺序

```text
Step 1. 接入 MinerU PDF 处理规范，不急着联网抓取。
Step 2. 将 002837 年报 PDF 解析为 text / table / page_map / parse_log。
Step 3. 生成 claim_candidates，并人工或质量门晋升关键 claims。
Step 4. 标准化 Tushare / Baostock metric candidates。
Step 5. 生成 stock_analysis_pack.yaml。
Step 6. 使用 stock-deep-dive 生成样例质量报告草案。
Step 7. 运行 quality-review v2。
Step 8. 对 002837 做 regression run。
Step 9. 再扩展到第二只样本股。
```

## 6. 暂停条件

出现以下情况，不进入 R3：

```text
- 年报 PDF 未解析出 page_map / table_map。
- 核心业务结论没有 claim_id。
- 分业务收入或毛利率未披露但报告写成确定事实。
- 结构化财务指标被直接归因到某细分业务。
- segment_exposure 没有证据却被回写。
- 盈利预测没有假设表。
- 估值没有可比公司或场景说明。
- 技术/情绪/事件数据没有来源日期。
- 报告出现无来源目标价、仓位建议或买卖指令。
```
