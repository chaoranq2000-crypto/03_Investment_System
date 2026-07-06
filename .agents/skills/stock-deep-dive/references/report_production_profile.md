# Stock Report Production Profile — stock-deep-dive reference

本文件定义 `stock-deep-dive` 内部如何把 reviewed evidence、reviewed metrics、data-layer packs 和 analysis pack 转成接近样例质量的个股报告草稿。

它是 skill-local profile，不是平级 workflow。

```yaml
profile_id: stock_report_production
parent_workflow_type: stock_first_closed_loop
active_skill: stock-deep-dive
quality_skill: quality-review
quality_target: R4_readiness_draft | R3_sample_quality_draft
primary_subject: single_stock
```

全局 workflow type、global stage 和 global gate 以 `docs/workflows/RESEARCH_WORKFLOW.md` 为准。

## Profile step map

| profile_step_id | 对应全局阶段 | 目标 | 主要 owner |
|---|---|---|---|
| RP0 Intake & Scope | T0 | 确认股票、公司主体、报告质量目标和已有 run。 | `research-orchestrator` |
| RP1 Evidence Plan | T1 | 生成或检查 `stock_evidence_plan.yaml`。 | `evidence-ingest` |
| RP2 Evidence Acquire & Parse | T1 | 获取 / 登记 / 解析官方披露和结构化数据。 | `evidence-ingest` |
| RP3 Candidate Generation | T1-T2 | 生成 claim / metric / business-line / exposure candidates。 | `evidence-ingest` |
| RP4 Candidate Review | T2 | 晋升 reviewed claims / metrics。 | `quality-review` |
| RP5 Analysis Pack Build | T2-T7 | 生成 `stock_analysis_pack.yaml`。 | `stock-deep-dive` |
| RP6 Forecast & Valuation Context | T7 | 生成 forecast / valuation context，全部标记 estimate / inference。 | `stock-deep-dive` |
| RP7 Technical / Sentiment / Event Pack | T7 | 消费 data-layer packs，不足则保留 TODO。 | `stock-deep-dive` |
| RP8 Report Draft | T7 | 从 analysis pack 生成 report draft，不新增事实。 | `stock-deep-dive` |
| RP9 Quality Review | T9 | 执行 G1/G2/G3/G6/G7/G8/G9，必要时附加 QR-* 子检查。 | `quality-review` |
| RP10 Backflow & Maintenance | T8 | 回写 exposure / claims / metrics / refresh todo。 | `segment-company-mapping` |
| RP11 Close Readout | T10 | 输出 final readout 和状态。 | `research-orchestrator` |

## RP0 Intake & Scope

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

```text
workflow_state.yaml
company_identity.yaml
scope_card.yaml
```

必须确认：

- 证券代码和公司主体是否唯一。
- 是否已有 evidence snapshot。
- 是否已有 segment exposure。
- 报告目标是 R1、R2、R3 还是 R4 readiness。

## RP1 Evidence Plan

由 `evidence-ingest` 生成 `stock_evidence_plan.yaml`。

最低证据包：

1. 最近年度报告 PDF 或 explicit TODO。
2. 最近半年报 / 季报或 explicit TODO。
3. 近 12-24 个月重大公告。
4. 财务报表与财务指标结构化数据。
5. 行情、估值、技术指标快照。
6. 互动问答、投资者关系、公司官网、新闻线索。
7. 行业报告或权威数据，至少形成简版行业卡或 TODO。

缺失任何项都必须生成 evidence gap request：

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

## RP2 Evidence Acquire & Parse

### 官方 PDF

```text
data/raw/official_filings/<stock_code>/<file>.pdf
→ MinerU
→ data/processed/text/<doc_id>.md
→ data/processed/layout/<doc_id>_content.json
→ data/processed/tables/<doc_id>_tables.json
→ data/processed/page_maps/<doc_id>_page_map.yaml
→ data/processed/logs/<doc_id>_parse_log.json
```

### 结构化数据

Tushare / Baostock 输出：

```text
data/raw/structured_api/<stock_code>/*.csv|json
data/processed/normalized/<stock_code>/*.csv
data/processed/candidates/metric_candidates_<stock_code>.csv
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

## RP3 Candidate Generation

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

## RP4 Candidate Review

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

## RP5 Analysis Pack Build

由 `stock-deep-dive` 基于 reviewed claims / reviewed metrics / accepted estimates 输出分析包：

```text
reports/workflow_runs/<workflow_id>/stock_analysis_pack.yaml
reports/workflow_runs/<workflow_id>/industry_context_card.yaml
reports/workflow_runs/<workflow_id>/business_breakdown.yaml
reports/workflow_runs/<workflow_id>/financial_quality.yaml
reports/workflow_runs/<workflow_id>/risk_counter_evidence.yaml
```

`stock_analysis_pack.yaml` 是报告写作的唯一上游。不允许报告正文从未审查证据自由发挥。

## RP6 Forecast & Valuation Context

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

## RP7 Technical / Sentiment / Event Pack

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

## RP8 Report Draft

由 `stock-deep-dive` 将 analysis pack 转为报告草稿：

```text
stock_report_sample_quality_draft.md
report_evidence_map.md
report_open_questions.md
writer_gap_requests.yaml
```

报告草稿必须包含：

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

## RP9 Quality Review

由 `quality-review` 执行全局 gate 和局部 subchecks。

全局 gate 来自 `RESEARCH_WORKFLOW.md`：

```text
G1 Evidence Gate
G2 Claim Gate
G3 Metric Gate
G6 Exposure Gate
G7 Stock Report Gate
G8 Backflow Gate
G9 No Advice Gate
```

如为 R4 readiness，可追加 `QR-R4-*` 局部子检查；不得创建新的全局 G 编号。

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

## RP10 Backflow & Maintenance

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

## RP11 Close Readout

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
