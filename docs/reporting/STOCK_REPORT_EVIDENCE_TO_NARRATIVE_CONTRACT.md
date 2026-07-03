# Evidence-to-Narrative Contract — 从证据到研报叙事的转换契约

## 1. 目标

防止报告 writer 越过证据层直接生成貌似专业但不可追溯的叙事。

```text
evidence → candidate → reviewed claim / metric → analysis pack → narrative
```

任何报告段落都必须来自 analysis pack；任何 analysis pack 结论都必须来自 reviewed claim / reviewed metric / explicitly marked estimate / inference。

## 2. 实体类型

```yaml
entity_types:
  - company
  - security
  - business_line
  - segment
  - industry
  - customer
  - supplier
  - project
  - event
  - market
```

## 3. claim_type

```yaml
claim_type:
  fact:
    definition: 官方披露或权威来源直接支持的事实
    report_usage: 可以作为事实句
  management_comment:
    definition: 管理层或公司回复的表述
    report_usage: 只能写“公司表示/管理层称”
  analyst_view:
    definition: 券商、第三方机构、媒体观点
    report_usage: 只能写“某机构观点/市场观点”
  estimate:
    definition: 预测或测算
    report_usage: 必须标明假设和口径
  inference:
    definition: 由多个 fact/metric 推导出的判断
    report_usage: 必须给 supporting_claim_ids / supporting_metric_ids
  clue:
    definition: 低可靠来源线索
    report_usage: 只能进入 TODO 或待验证
```

## 4. 段落证据要求

| 报告部分 | 最低证据要求 | 不足时处理 |
|---|---|---|
| 财务概览 | reviewed metrics | 保留缺口，不写结论 |
| 业务拆分 | 年报/公告表格 claim + metric | 只写“未披露/待验证” |
| 行业分析 | 行业报告/权威数据/多源线索 | 简版行业卡，标注置信度 |
| 盈利预测 | 历史财务 + 业务假设 + estimate | 不给三年具体值，只列假设 |
| 估值分析 | 当前估值快照 + peers + forecast | 只写静态估值或 TODO |
| 技术分析 | 行情快照 | 不写关键价位 |
| 情绪分析 | 市场数据/资金/新闻/公告 | 只写定性观察或 TODO |
| 事件驱动 | 公告/日历/监管规则 | 只列待验证事件 |

## 5. narrative_binding

每个二级标题应有 `narrative_binding`：

```yaml
section_id: business_liquid_cooling
section_title: 液冷业务
required_inputs:
  claims:
    - claim_product_line
    - claim_revenue_breakdown
    - claim_capacity_or_project
  metrics:
    - metric_business_revenue
    - metric_business_gross_margin
  estimates:
    - estimate_growth_assumption
open_gaps:
  - gap_liquid_cooling_revenue_pct
allowed_language:
  - fact
  - inference_with_confidence
blocked_language:
  - precise revenue share without disclosure
```

## 6. 缺口回传

报告生成时发现缺证据，必须输出：

```yaml
evidence_gap_request:
  gap_id:
  discovered_by: stock-report-writer
  report_section:
  missing_input_type: claim | metric | estimate | market_snapshot
  blocking_level: high | medium | low
  recommended_source_type:
  recommended_query:
  recommended_parser: MinerU | Tushare | Baostock | manual_review | web_snapshot
```

## 7. 失败规则

以下情况直接 `needs_fix` 或 `blocked`：

```text
- 报告正文出现 material claim 但无 claim_id / metric_id。
- quote_or_excerpt 与正文结论不一致。
- 页码 / 表格 locator 为空但报告写成已披露。
- clue 被写成事实。
- forecast 变成确定性承诺。
- technical / sentiment 数据没有日期。
```
