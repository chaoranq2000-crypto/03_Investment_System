---
name: compare-stocks
description: Use when comparing multiple listed companies within or across segments using consistent evidence, exposure, metrics, scorecards, and risks. Do not use to replace individual evidence review or issue direct trading instructions.
---

# Compare Stocks

## Goal

用统一口径比较多个公司，明确差异、证据质量、风险和后续核验任务。

## When to use

- 用户要求比较多家公司或同一 segment 下的公司。
- 需要构建 stock_score_matrix。
- 需要比较收入暴露、财务质量、客户质量、订单可见度、估值场景风险等。

## Inputs

- stock_code / company_id list。
- linked_segments。
- 个股报告、segment_exposure、metrics、evidence_map。
- 比较维度和评分口径。

## Responsibilities

- 确认可比公司和 linked_segments。
- 统一财务、业务、估值场景和 exposure 口径。
- 输出评分矩阵、差异解释、风险和反证。
- 标记证据缺口和后续 deep dive 任务。

## Out of scope

- 不替代单个公司的证据复核。
- 不输出买入、卖出、持有建议。
- 不把评分等同仓位或交易信号。
- 不把估值场景写成目标价指令。

## Outputs

- `reports/comparisons/<date>_stock_comparison.md`
- `reports/comparisons/<date>_stock_score_matrix.csv`
- evidence gap list
- follow-up stock research queue

## Workflow

1. 确认公司列表和可比范围。
2. 读取 segment_exposure 和 evidence_map。
3. 统一指标、单位、周期和估值场景假设。
4. 建立比较矩阵。
5. 标记风险、反证和 TODO。
6. 输出后续核验任务。
7. 执行 quality-review。

## Guardrails

- 不同会计口径、业务口径或估值口径必须说明。
- narrative exposure 不能直接提高比较结论。
- 缺失数据不得用猜测填充。
- 评分不是交易信号。

## Quality checklist

- [ ] 公司标识和 linked_segments 正确。
- [ ] exposure 数据有 evidence_id 或 TODO。
- [ ] 指标口径、单位、周期一致。
- [ ] 评分有证据支撑。
- [ ] 风险和反证已列出。
- [ ] 未输出买卖建议。
