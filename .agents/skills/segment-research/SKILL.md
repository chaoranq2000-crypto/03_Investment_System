---
name: segment-research
description: Use when researching one A-share segment or industry-chain node, including definition, scope, drivers, supply, company universe, scorecard, evidence map, and refresh tasks. Do not use for a single-stock deep dive or direct trading instructions.
---

# Segment Research

## Goal

产出一个可追溯、可比较、可更新的细分方向研究包。

## When to use

- 用户要求研究一个细分、产业链环节、主题、产品或工艺。
- 需要定义 `segment_id`、scope_in、scope_out。
- 需要建立 A 股公司池、评分卡、证据地图和后续跟踪任务。

## Inputs

- segment_name 或 segment_id。
- 研究深度：quick / standard / deep。
- 已有 evidence_id、claim_id、metric_id 或待补证据清单。
- 关注维度：需求、供给、利润池、公司池、风险等。

## Responsibilities

- 标准化 `segment_id`。
- 定义细分边界、产业链位置和相邻细分。
- 梳理需求驱动、供给格局、利润池和关键指标。
- 建立 A 股公司池候选。
- 使用多对多逻辑标注 segment-company exposure。
- 输出 scorecard、evidence_map、refresh_tasks。

## Out of scope

- 不做单一个股完整深度报告。
- 不自动覆盖旧报告。
- 不把评分解释成买卖信号。
- 不用无证据市场热词提高 exposure_score。
- 不实现全市场批量扫描。

## Outputs

- `reports/segments/<segment_id>/<date>_segment_report.md`
- `reports/segments/<segment_id>/company_universe.csv`
- `reports/segments/<segment_id>/scorecard.yaml`
- `reports/segments/<segment_id>/evidence_map.md`
- `reports/segments/<segment_id>/refresh_tasks.yaml`

## Workflow

1. 确认 segment_id 和研究范围。
2. 建立 scope_in / scope_out。
3. 收集并登记证据；缺失时标记 TODO。
4. 拆分 facts、estimates、inferences、opinions。
5. 建立公司池和 exposure 候选。
6. 输出指标体系和 scorecard。
7. 列出风险、反证和 missing data。
8. 执行或请求 quality-review。

## Guardrails

- Material claim 必须有 `evidence_id`、`claim_id`、`metric_id` 或显式 TODO。
- segment-company exposure 是多对多，不得强行单归属。
- 管理层表述和券商预测不能写成事实。
- 报告是 snapshot，后续更新必须产出 refresh log。

## Quality checklist

- [ ] 细分定义和边界清楚。
- [ ] scope_in / scope_out 已写明。
- [ ] A 股公司池有证据或 TODO。
- [ ] exposure_type、exposure_score、confidence 已标注。
- [ ] 事实、估计、推断、观点已分离。
- [ ] 风险和反证已列出。
- [ ] 评分不是交易信号。
- [ ] 未输出买卖建议。
