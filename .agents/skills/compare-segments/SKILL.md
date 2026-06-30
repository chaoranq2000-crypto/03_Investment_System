---
name: compare-segments
description: Use when comparing multiple segments with consistent dimensions, evidence quality, score matrices, risks, and research priorities. Do not use for direct trading instructions or single-company deep dives.
---

# Compare Segments

## Goal

用统一口径横向比较多个细分方向，形成研究优先级、证据差距和后续队列。

## When to use

- 用户要求比较多个 segment。
- 需要构建 segment_score_matrix。
- 需要对市场空间、增速、A 股纯度、催化剂、风险、证据质量进行统一评分。

## Inputs

- segment_id list。
- 各 segment 的报告、scorecard、evidence_map。
- 可比维度和评分口径。

## Responsibilities

- 确认可比对象和 scope。
- 统一评分维度和证据要求。
- 输出比较矩阵和关键分歧。
- 列出反证、不确定性和后续研究队列。

## Out of scope

- 不输出买卖建议。
- 不把细分评分等同投资组合权重。
- 不做单一个股深度。
- 不使用不同口径数据直接比较。

## Outputs

- `reports/comparisons/<date>_segment_comparison.md`
- `reports/comparisons/<date>_segment_score_matrix.csv`
- evidence gap list
- research queue

## Workflow

1. 确认 segment 列表和可比范围。
2. 读取每个 segment 的 evidence map。
3. 统一维度、单位、周期和评分方法。
4. 填写比较矩阵。
5. 标记证据质量、风险和反证。
6. 输出后续研究优先级。
7. 执行 quality-review。

## Guardrails

- 不同口径必须先标准化或标注不可比。
- 没有证据的评分必须写 TODO。
- 评分只代表研究优先级，不是交易信号。
- 冲突证据必须保留。

## Quality checklist

- [ ] 所有 segment_id 稳定且定义清楚。
- [ ] 比较维度统一。
- [ ] 每个评分有 evidence_id / claim_id 或 TODO。
- [ ] 关键不确定性和反证已列出。
- [ ] 研究队列不包含交易指令。
