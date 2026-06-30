---
name: company-universe
description: Use when building or updating the A-share company universe for a segment, including exposure candidates and evidence gaps. Do not use for valuation, direct stock recommendations, or full stock deep dives.
---

# Company Universe

## Goal

为一个细分方向建立 A 股相关公司池，并标注暴露类型、证据质量和待核验项。

## When to use

- 用户需要某个 segment 的相关上市公司清单。
- 需要区分 revenue、product、technology、customer、project、narrative 暴露。
- 需要整理候选公司进入 `company_universe.csv`。

## Inputs

- segment_id 和 segment 定义。
- 已登记 evidence_id / claim_id。
- 候选 stock_code、stock_name 或筛选线索。

## Responsibilities

- 建立候选公司池。
- 记录 company_id、stock_code、stock_name、exchange。
- 初步标注 exposure_type、exposure_score、confidence。
- 标记收入占比、利润占比等缺失项。
- 输出后续核验证据清单。

## Out of scope

- 不做估值。
- 不输出买卖建议。
- 不替代 stock-deep-dive。
- 不把关键词命中直接写成高暴露。
- 不批量研究无关细分。

## Outputs

- `reports/segments/<segment_id>/company_universe.csv`
- exposure candidate table
- evidence gap list
- follow-up research queue

## Workflow

1. 读取 segment scope。
2. 收集候选公司线索。
3. 对每家公司记录 evidence_id 或 TODO。
4. 区分披露收入、产品、技术、客户、项目和叙事暴露。
5. 给出低成本复核任务。
6. 交给 segment-company-mapping 或 stock-deep-dive 深化。

## Guardrails

- 每个候选公司必须有证据、来源路径或 TODO。
- narrative 暴露默认低置信度。
- 不把 company universe 当成推荐名单。
- 不把 exposure_score 当作交易信号。

## Quality checklist

- [ ] segment_id 与 taxonomy 一致。
- [ ] 每家公司有 company_id / stock_code / stock_name。
- [ ] exposure_type 明确。
- [ ] evidence_ids 或 TODO 已填写。
- [ ] confidence 已标注。
- [ ] 缺失收入/利润占比已标记 MISSING。
- [ ] 未输出买卖建议。
