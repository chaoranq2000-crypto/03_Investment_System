# Comparison Matrix

> 本矩阵用于研究对象横向比较，不构成任何买入、卖出、持有或其他交易建议。

## Metadata

| Field | Value |
|---|---|
| report_id | comparison_<object_type>_<YYYY-MM-DD> |
| report_type | segment_comparison / stock_comparison |
| object_type | segment / company |
| objects | <object_id list> |
| report_date | <YYYY-MM-DD> |
| evidence_snapshot | <evidence_id list> |
| claim_ids | <claim_id list> |
| confidence | high / medium / low |
| status | current / needs_refresh / outdated / archived |

## Evidence Snapshot

| evidence_id | source_type | title | publish_date | reliability_rank | status | source_path |
|---|---|---|---|---|---|---|
| <evidence_id> | <type> | <title> | <date> | A/B/C/D | fresh/stale | <path> |

## 可比对象定义

| object_id | name | scope_in | scope_out | evidence_id | notes |
|---|---|---|---|---|---|
| <object_id> | <name> | <scope> | <scope> | <evidence_id> | <notes> |

## Facts

| Object | Fact | evidence_id | claim_id | confidence |
|---|---|---|---|---|
| <object_id> | <fact> | <evidence_id> | <claim_id> | <level> |

## Estimates / Inferences

| Object | Estimate / Inference | Method | evidence_id / metric_id | confidence |
|---|---|---|---|---|
| <object_id> | <estimate> | <method> | <id> | <level> |

## 评分矩阵

| Object | Dimension | Score 0-5 | Rationale | evidence_ids | claim_ids | confidence |
|---|---|---:|---|---|---|---|
| <object_id> | <dimension> | <score> | <reason> | <ids or TODO> | <ids> | <level> |

说明：评分只表达研究比较，不是交易信号。

## 关键分歧

| Difference | Object A | Object B | Evidence | Interpretation | Uncertainty |
|---|---|---|---|---|---|
| <difference> | <object_id> | <object_id> | <evidence_id> | <inference> | <uncertainty> |

## Risks / Counter-evidence

| Object | Risk / Counter-evidence | evidence_id | Impact | Follow-up |
|---|---|---|---|---|
| <object_id> | <risk> | <evidence_id or TODO> | <impact> | <task> |

## TODO / Missing Data

- TODO: 需要补充证据 - <item>
- MISSING: 暂无直接披露 - <item>
- LOW_CONFIDENCE: 当前证据质量不足 - <item>
- UNVERIFIED: 尚未核验 - <item>

## Evidence Map

| Claim / Matrix cell | evidence_id | claim_id | metric_id | source_path | status |
|---|---|---|---|---|---|
| <cell> | <evidence_id> | <claim_id> | <metric_id> | <path> | fresh/stale |

## 后续研究队列

| Priority | Object | Question | Evidence needed | Owner | Status |
|---|---|---|---|---|---|
| <priority> | <object_id> | <question> | <evidence> | <owner> | open |
