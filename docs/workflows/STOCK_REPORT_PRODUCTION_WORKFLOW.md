# Stock Report Production Workflow — 样例级个股报告生产流程

## 定位

本文件定义从一只股票生成“接近样例质量”的个股研究报告时，证据、分析、叙事、质量门和回写如何衔接。

它是 `stock_first_closed_loop` 的报告生产细化流程，服务 R4 readiness / R3 sample-quality draft，不是独立交易系统，也不输出买卖指令。

## 当前主路由

```text
research-orchestrator
→ evidence-ingest
→ stock-deep-dive
→ segment-company-mapping
→ quality-review
→ research-orchestrator close readout
```

历史拆分名称 `stock-research-analyst` 和 `stock-report-writer` 如仍存在，默认视为已合并到 `stock-deep-dive` 的待归档参考，不应作为默认路由入口。

## Workflow metadata

```yaml
workflow_type: stock_report_production
parent_workflow_type: stock_first_closed_loop
quality_target: R4_readiness_draft | R3_sample_quality_draft
entry_skill: research-orchestrator
primary_execution_skill: stock-deep-dive
quality_skill: quality-review
primary_subject: single_stock
```

## 阶段总览

```text
T0 Intake & Scope
T1 Evidence Plan
T2 Evidence Acquire & Parse
T3 Candidate Generation
T4 Candidate Review / Promotion
T5 Analysis Pack Build
T6 Forecast & Valuation Model
T7 Technical / Sentiment / Event Pack
T8 Report Draft
T9 Quality Review
T10 Backflow & Maintenance
T11 Close Readout
```

## T0 Intake & Scope

输入：

```yaml
stock_code:
stock_name:
exchange:
company_id:
report_quality_target: R1 | R2 | R3 | R4
linked_segments_hint: []
date_range:
existing_workflow_run:
```

输出：

```yaml
workflow_state.yaml
company_identity.yaml
scope_card.yaml
```

必须确认：

- 证券代码和公司主体是否唯一。
- 是否已有 evidence snapshot。
- 是否已有 segment exposure。
- 报告目标是 R1、R2、R3 还是 R4 readiness。

## T1 Evidence Plan

由 `evidence-ingest` 生成 `stock_evidence_plan.yaml`。

最低证据包：

1. 最近年度报告 PDF 或 explicit TODO。
2. 最近半年报 / 季报或 explicit TODO。
3. 近 12-24 个月重大公告。
4. 财务报表与财务指标结构化数据。
5. 行情、估值、技术指标快照。
6. 互动问答、投资者关系、公司官网、新闻线索。
7. 行业报告或权威数据，至少形成简版行业卡或 TODO。

缺失任何项都必须生成 evidence gap request。

```yaml
evidence_gap_request:
  gap_id:
  target_section:
  missing_claim_or_metric:
  required_source_type:
  preferred_source_name:
  search_hint:
  blocking_level: high | medium | low
  owner_skill: evidence-ingest
```

## T2 Evidence Acquire & Parse

### 官方 PDF

```text
data/raw/official_filings/<stock_code>/<file>.pdf
→ MinerU
→ data/processed/text/<file>.md
→ data/processed/layout/<file>_content.json
→ data/processed/tables/<file>_tables.json
→ data/processed/page_maps/<file>_page_map.yaml
→ data/processed/logs/<file>_parse_log.json
```

### 结构化数据

Tushare / Baostock 输出：

```text
data/raw/structured_api/<stock_code>/*.csv|json
data/processed/normalized/<stock_code>/*.csv
data/processed/candidates/metric_candidates_<run_id>.csv
```

结构化数据默认只生成 metric candidates，不生成业务暴露 claim。

### 市场、情绪、事件线索

可进入：

```text
clue_log.csv
market_snapshot.csv
sentiment_snapshot.csv
event_candidates.csv
```

不得直接进入报告正文。

## T3 Candidate Generation

从官方披露解析结果与结构化数据中生成：

```text
claim_candidates.csv
metric_candidates.csv
table_inventory.csv
business_line_candidates.csv
segment_exposure_candidates.yaml
evidence_gap_requests.yaml
```

重点抽取区域：

- 经营情况讨论与分析。
- 主营业务分产品 / 分行业 / 分地区。
- 产销量、产能、在建项目、募投项目。
- 前五大客户 / 供应商。
- 重大合同 / 订单 / 框架协议。
- 研发项目 / 专利 / 技术路线。
- 风险因素。
- 管理层对行业和未来的表述。

## T4 Candidate Review / Promotion

候选晋升规则：

```text
claim_candidates.csv → reviewed_claims.csv / claims_registry.csv
metric_candidates.csv → reviewed_metrics.csv / metrics_registry.csv
```

晋升条件：

- `evidence_id` 存在。
- `quote_or_excerpt`、`page_no` 或 `table_cell_locator` 可回溯。
- `source_rank` 与 `claim_type` 匹配。
- material claim 不来自 D 级来源。
- `estimate` / `inference` 显式标注。

## T5 Analysis Pack Build

由 `stock-deep-dive` 基于 reviewed claims / reviewed metrics / accepted estimates 输出分析包：

```text
reports/workflow_runs/<workflow_id>/stock_analysis_pack.yaml
reports/workflow_runs/<workflow_id>/industry_context_card.yaml
reports/workflow_runs/<workflow_id>/business_breakdown.yaml
reports/workflow_runs/<workflow_id>/financial_quality.yaml
reports/workflow_runs/<workflow_id>/risk_counter_evidence.yaml
```

`stock_analysis_pack.yaml` 是报告写作的唯一上游。不允许报告正文从未审查证据自由发挥。

## T6 Forecast & Valuation Model

由 `stock-deep-dive` 输出：

```text
forecast_model.yaml
valuation_model.yaml
peer_comparison.csv
sensitivity_table.csv
```

最低要求：

- 2026E / 2027E / 2028E 三年预测或 explicit TODO。
- 收入、毛利率、费用率、归母净利、EPS 的主假设。
- 至少一个 base / bull / bear 场景或保留缺口。
- 至少一个最敏感变量。
- 可比公司估值表。
- 所有预测必须标记为 `estimate` / `inference`。

## T7 Technical / Sentiment / Event Pack

由 `stock-deep-dive` 消费 data-layer packs 后输出：

```text
technical_snapshot.yaml
market_sentiment_pack.yaml
catalyst_calendar.yaml
```

最低要求：

- 数据日期。
- 当前价格和估值快照。
- 均线或趋势指标。
- 关键支撑 / 阻力口径。
- 成交额、换手率、资金流等可得市场指标。
- 行业 / 主题热度线索。
- 未来 1-3 个月事件日历。

缺 market data 时保留 TODO，不编写具体技术或情绪结论。

## T8 Report Draft

由 `stock-deep-dive` 将 analysis pack 转为报告草稿：

```text
stock_report_sample_quality_draft.md
report_evidence_map.md
report_open_questions.md
writer_gap_requests.yaml
```

必须包含：

1. Metadata。
2. 前言 / 核心主线。
3. 财务概览。
4. 业务拆分。
5. 行业分析。
6. 盈利预测。
7. 估值分析。
8. 技术分析。
9. 情绪分析。
10. 事件驱动。
11. 研究结论、风险、反证、跟踪清单。
12. Evidence Map。
13. Open Questions / Evidence Gaps。

## T9 Quality Review

由 `quality-review` 执行 gate：

```text
quality_issue_list.md
quality_gate_report.md
stock_report_acceptance_checklist.yaml
```

判定：

```text
accepted_sample_quality
accepted_with_todos
needs_fix
blocked
```

## T10 Backflow & Maintenance

必须回写或明确不回写：

```text
segment_company_exposure.csv
claims_registry.csv
metrics_registry.csv
watchlist_notes.md
reports_to_refresh.yaml
refresh_log.md
```

回写规则：

- Exposure update 必须有 reviewed claim、reviewed metric 或 accepted TODO。
- Forecast / valuation 不回写为事实，只回写为 model snapshot。
- Clue 不回写为 claim。
- 报告状态和证据状态必须更新。

## T11 Close Readout

最终 readout 必须说明：

```yaml
run_id:
stock_code:
quality_target:
final_status:
evidence_count:
reviewed_claims:
reviewed_metrics:
open_gaps:
high_issues:
medium_issues:
backflow_decision:
next_run_recommendation:
```
