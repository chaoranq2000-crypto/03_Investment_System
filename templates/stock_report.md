# <stock_code>_<company_slug> 个股深度报告

> 本报告为研究快照，用于证据管理与研究框架，不构成任何买入、卖出、持有或其他交易建议。

## Metadata

| Field | Value |
|---|---|
| report_id | stock_report_<stock_code>_<YYYY-MM-DD> |
| report_type | stock_report |
| company_id | <stock_code>_<company_slug> |
| stock_code | <code> |
| stock_name | <name> |
| linked_segments | <segment_id list> |
| report_date | <YYYY-MM-DD> |
| evidence_snapshot | <evidence_id list> |
| claim_ids | <claim_id list> |
| metric_ids | <metric_id list> |
| confidence | high / medium / low |
| status | current / needs_refresh / outdated / archived |

## Evidence Snapshot

| evidence_id | source_type | title | publish_date | reliability_rank | status | source_path |
|---|---|---|---|---|---|---|
| <evidence_id> | <type> | <title> | <date> | A/B/C/D | fresh/stale | <path> |

## 公司业务拆解

| Business line | Revenue / Profit metric | claim_type | evidence_id | confidence | Missing / Notes |
|---|---|---|---|---|---|
| <business> | <metric or MISSING> | fact / estimate / inference | <evidence_id> | <level> | <notes> |

## 细分方向暴露

| segment_id | exposure_type | exposure_score | revenue_pct | profit_pct | evidence_ids | confidence | notes |
|---|---|---:|---:|---:|---|---|---|
| <segment_id> | revenue/product/technology/customer/project/narrative/unknown | 0-5 | <pct or MISSING> | <pct or MISSING> | <ids> | high/medium/low | <notes> |

## 财务质量

| Metric | Period | Value | Unit | metric_id | source_evidence_id | calculation_method | is_estimate |
|---|---|---:|---|---|---|---|---|
| <metric> | <period> | <value> | <unit> | <metric_id> | <evidence_id> | <method> | true/false |

## 竞争优势

| Advantage | claim_type | Supporting evidence | Counter-evidence | confidence |
|---|---|---|---|---|
| <advantage> | fact/inference/opinion | <evidence_id / claim_id> | <evidence_id or TODO> | <level> |

## 客户与供应链

| Item | claim_type | Evidence | Reliability | Notes |
|---|---|---|---|---|
| <customer/supplier> | fact/management_comment/inference | <evidence_id> | A/B/C/D | <notes> |

## 治理与管理层

| Topic | claim_type | evidence_id | confidence | notes |
|---|---|---|---|---|
| <topic> | fact/management_comment/opinion | <evidence_id or TODO> | <level> | <notes> |

## 估值场景

| Scenario | Assumption type | Key assumptions | evidence_id / metric_id | confidence | Risk |
|---|---|---|---|---|---|
| base | estimate / inference | <assumptions> | <ids or TODO> | <level> | <risk> |

说明：估值场景只用于研究假设和敏感性分析，不构成目标价或交易指令。

## 催化剂

| Catalyst | claim_type | evidence_id | expected_window | confidence | notes |
|---|---|---|---|---|---|
| <catalyst> | fact/inference/unknown | <evidence_id or TODO> | <period> | <level> | <notes> |

## Risks / Counter-evidence

| Risk / Counter-evidence | Related claim_id | evidence_id | Impact | Follow-up |
|---|---|---|---|---|
| <risk> | <claim_id> | <evidence_id or TODO> | <impact> | <task> |

## 反证清单

- <counter-hypothesis>; evidence_id=<id or TODO>; confidence=<level>

## 跟踪指标

| Metric | Trigger | Evidence source | Review frequency | Notes |
|---|---|---|---|---|
| <metric> | <threshold/event> | <source> | <frequency> | <notes> |

## TODO / Missing Data

- TODO: 需要补充证据 - <item>
- MISSING: 暂无直接披露 - <item>
- LOW_CONFIDENCE: 当前证据质量不足 - <item>
- UNVERIFIED: 尚未核验 - <item>

## Evidence Map

| Claim / Section | evidence_id | claim_id | metric_id | source_path | status |
|---|---|---|---|---|---|
| <section> | <evidence_id> | <claim_id> | <metric_id> | <path> | fresh/stale |

## Refresh Status

- status: current / needs_refresh / outdated / archived
- next_review_date:
- refresh_log:
