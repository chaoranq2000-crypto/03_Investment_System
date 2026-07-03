# Stock Report Production Workflow — 样例质量个股报告生产流程

## 1. 工作流类型

```yaml
workflow_type: stock_report_production
quality_target: R3_sample_quality_draft
entry_skill: research-orchestrator
primary_subject: single_stock
```

本 workflow 用于从一只股票生成接近样例报告质量的个股研究报告。它不是行情交易系统，不直接生成买卖指令。

## 2. 阶段总览

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

## 3. T0 Intake & Scope

输入：

```yaml
stock_code:
stock_name:
exchange:
company_id:
report_quality_target: R1 | R2 | R3
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

```text
- 证券代码和公司主体是否唯一。
- 是否已有 evidence_snapshot。
- 是否已有 segment_exposure。
- 报告目标是 R1、R2 还是 R3。
```

## 4. T1 Evidence Plan

由 `evidence-ingest` 生成 `stock_evidence_plan.yaml`。

最低证据包：

```text
1. 最近年度报告 PDF。
2. 最近半年报 / 季报。
3. 近 12-24 个月重大公告。
4. 财务报表与财务指标结构化数据。
5. 行情、估值、技术指标快照。
6. 互动问答、投资者关系、公司官网、新闻线索。
7. 行业报告或权威数据，至少形成简版行业卡。
```

缺失任何项都必须生成：

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

## 5. T2 Evidence Acquire & Parse

### 5.1 官方 PDF

处理路径：

```text
data/raw/official_filings/<stock_code>/<evidence_id>.pdf
  → MinerU
  → data/processed/text/<evidence_id>.md
  → data/processed/layout/<evidence_id>_content.json
  → data/processed/tables/<evidence_id>_tables.json
  → data/processed/page_maps/<evidence_id>_page_map.yaml
  → data/processed/logs/<evidence_id>_parse_log.json
```

### 5.2 结构化数据

Tushare / Baostock 输出：

```text
data/raw/structured_api/<source>/<run_id>/*.csv|json
data/processed/normalized/<run_id>/*.csv
data/processed/candidates/metric_candidates_<run_id>.csv
```

默认只生成 metric candidates，不生成业务暴露 claim。

### 5.3 市场/情绪/事件线索

可参考 a-stock-data 的源覆盖，但输出必须进入：

```text
clue_log.csv
market_snapshot.csv
sentiment_snapshot.csv
event_candidates.csv
```

不得直接进入报告正文。

## 6. T3 Candidate Generation

从 MinerU 输出生成：

```text
claim_candidates.csv
metric_candidates.csv
table_inventory.csv
business_line_candidates.csv
segment_exposure_candidates.yaml
evidence_gap_requests.yaml
```

重点抽取区域：

```text
- 经营情况讨论与分析
- 主营业务分产品 / 分行业 / 分地区
- 产销量、产能、在建项目、募投项目
- 前五大客户 / 供应商
- 重大合同 / 订单 / 框架协议
- 研发项目 / 专利 / 技术路线
- 风险因素
- 管理层对行业和未来的表述
```

## 7. T4 Candidate Review / Promotion

候选晋升规则：

```text
claim_candidates.csv → reviewed_claims.csv / claims_registry.csv
metric_candidates.csv → reviewed_metrics.csv / metrics_registry.csv
```

晋升条件：

```text
- evidence_id 存在。
- quote_or_excerpt 或 table_cell_locator 可回溯。
- page_no_or_section 有效。
- source_rank 与 claim_type 匹配。
- material claim 不来自 D 级来源。
- estimate / inference 显式标注。
```

## 8. T5 Analysis Pack Build

由 `stock-research-analyst` 输出：

```text
reports/workflow_runs/<run_id>/stock_analysis_pack.yaml
reports/workflow_runs/<run_id>/industry_context_card.yaml
reports/workflow_runs/<run_id>/business_breakdown.yaml
reports/workflow_runs/<run_id>/financial_quality.yaml
reports/workflow_runs/<run_id>/risk_counter_evidence.yaml
```

`stock_analysis_pack.yaml` 是报告写作的唯一上游，不允许 report writer 直接从未审查证据自由发挥。

## 9. T6 Forecast & Valuation Model

输出：

```text
forecast_model.yaml
valuation_model.yaml
peer_comparison.csv
sensitivity_table.csv
```

最低要求：

```text
- 2026E / 2027E / 2028E 三年预测。
- 收入、毛利率、费用率、归母净利、EPS 的主假设。
- 至少一个 base / bull / bear 场景。
- 至少一个最敏感变量。
- 可比公司估值表。
- 所有预测必须标记 estimate / inference。
```

## 10. T7 Technical / Sentiment / Event Pack

输出：

```text
technical_snapshot.yaml
market_sentiment_pack.yaml
catalyst_calendar.yaml
```

最低要求：

```text
- 行情日期。
- 均线或趋势指标。
- 关键支撑 / 阻力口径。
- 融资余额、成交额、换手率、资金流等可得市场指标。
- 行业/主题热度线索。
- 未来 1-3 个月事件日历。
```

## 11. T8 Report Draft

由 `stock-report-writer` 生成：

```text
stock_report_sample_quality_draft.md
```

必须包含：

```text
0. Metadata
1. 前言 / 核心主线
2. 财务概览
3. 业务拆分
4. 行业分析
5. 盈利预测
6. 估值分析
7. 技术分析
8. 情绪分析
9. 事件驱动
10. 研究结论、风险、反证、跟踪清单
11. Evidence Map
12. Open Questions / Evidence Gaps
```

## 12. T9 Quality Review

由 `quality-review` 执行 v2 gate。

输出：

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

## 13. T10 Backflow & Maintenance

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

```text
- exposure update 必须有 reviewed claim 或 accepted TODO。
- forecast / valuation 不回写为事实，只回写为 model snapshot。
- clue 不回写为 claim。
- 报告状态和证据状态必须更新。
```

## 14. T11 Close Readout

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
