# <segment_id> 细分研究报告

> 本报告为研究快照，用于证据管理与研究框架，不构成任何买入、卖出、持有或其他交易建议。

## Metadata

| Field | Value |
|---|---|
| report_id | segment_report_<segment_id>_<YYYY-MM-DD> |
| report_type | segment_report |
| segment_id | <lower_snake_case> |
| title | <中文标题> |
| report_date | <YYYY-MM-DD> |
| author/reviewer | <name> |
| evidence_snapshot | <evidence_id list> |
| claim_ids | <claim_id list> |
| metric_ids | <metric_id list> |
| confidence | high / medium / low |
| status | current / needs_refresh / outdated / archived |

## Evidence Snapshot

| evidence_id | source_type | title | publish_date | reliability_rank | status | source_path |
|---|---|---|---|---|---|---|
| <evidence_id> | <type> | <title> | <date> | A/B/C/D | fresh/stale | <path> |

## 一句话结论

- fact: <事实结论；证据：evidence_id=<id>; claim_id=<id>>
- estimate: <估计或预测；证据：evidence_id=<id>; claim_id=<id>; method=<method>>
- inference: <研究推断；证据：evidence_id=<id>; confidence=<level>>
- opinion: <研究观点；说明证据边界和不确定性>

## 细分定义与边界

### Definition

- segment_id: `<segment_id>`
- name_cn:
- name_en:
- parent_theme:
- industry_chain_role:

### Scope In

- <纳入范围；证据：evidence_id=<id> 或 TODO: 需要补充证据>

### Scope Out

- <排除范围；说明原因和相邻细分>

## 产业链位置

| 环节 | 说明 | 关键公司/对象 | evidence_id | confidence |
|---|---|---|---|---|
| upstream/midstream/downstream | <说明> | <对象> | <evidence_id> | high/medium/low |

## 需求驱动

| Driver | claim_type | Evidence | Confidence | Notes |
|---|---|---|---|---|
| <driver> | fact / estimate / inference | <evidence_id / claim_id> | <level> | <notes> |

## 供给与竞争格局

| 维度 | 事实 | 推断 | evidence_id | 风险/反证 |
|---|---|---|---|---|
| 供给 | <fact> | <inference> | <evidence_id> | <counter_evidence> |

## 利润池分析

| 利润池位置 | 指标 | 口径 | metric_id | evidence_id | TODO/MISSING |
|---|---|---|---|---|---|
| <position> | <metric> | <definition> | <metric_id> | <evidence_id> | MISSING: 暂无直接披露 |

## A股公司池

| stock_code | stock_name | company_id | exposure_type | exposure_score | revenue_pct | profit_pct | evidence_ids | confidence | notes |
|---|---|---|---|---:|---:|---:|---|---|---|
| <code> | <name> | <company_id> | revenue/product/technology/narrative/unknown | 0-5 | <pct or MISSING> | <pct or MISSING> | <ids> | high/medium/low | <notes> |

## 关键指标体系

| metric_name | entity_type | period | unit | source_evidence_id | calculation_method | is_estimate | confidence |
|---|---|---|---|---|---|---|---|
| <metric> | segment/company | <period> | <unit> | <evidence_id> | <method> | true/false | <level> |

## 催化剂

| Catalyst | claim_type | evidence_id | expected_window | confidence | notes |
|---|---|---|---|---|---|
| <catalyst> | fact/inference/unknown | <evidence_id or TODO> | <period> | <level> | <notes> |

## Risks / Counter-evidence

| Risk / Counter-evidence | Related claim_id | evidence_id | Impact | Follow-up |
|---|---|---|---|---|
| <risk> | <claim_id> | <evidence_id or TODO> | <impact> | <task> |

## 评分卡

| Dimension | Score 0-5 | Rationale | evidence_ids | confidence |
|---|---:|---|---|---|
| market_space | <0-5> | <reason> | <ids or TODO> | <level> |

说明：评分只表示研究比较框架，不是交易信号。

## TODO / Missing Data

- TODO: 需要补充证据 - <item>
- MISSING: 暂无直接披露 - <item>
- LOW_CONFIDENCE: 当前证据质量不足 - <item>
- UNVERIFIED: 尚未核验 - <item>

## 后续跟踪清单

| Task | Object | Evidence needed | Owner | Due date | Status |
|---|---|---|---|---|---|
| <task> | <segment/company/metric> | <evidence type> | <owner> | <date> | open |

## Evidence Map

| Claim / Section | evidence_id | claim_id | metric_id | source_path | status |
|---|---|---|---|---|---|
| <section> | <evidence_id> | <claim_id> | <metric_id> | <path> | fresh/stale |

## Refresh Status

- status: current / needs_refresh / outdated / archived
- next_review_date:
- reports_to_regenerate:
- refresh_log:
