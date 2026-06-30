---
name: segment-company-mapping
description: Use when maintaining many-to-many exposure records between segments and companies. Do not use for writing full narrative reports, valuation, or direct trading instructions.
---

# Segment Company Mapping

## Goal

维护 `segment_company_exposure`，让一个公司可以映射到多个细分，一个细分可以对应多家公司。

## When to use

- 需要新增、更新或审查 segment-company exposure。
- 需要区分收入暴露、产品暴露、技术储备、客户、项目、市场叙事。
- 需要修正单一归属造成的研究混乱。

## Inputs

- segment_id、company_id、stock_code、stock_name。
- exposure evidence：evidence_id、claim_id、source_path。
- revenue_pct、profit_pct 或 MISSING 标记。

## Responsibilities

- 维护 exposure_type、exposure_score、confidence。
- 记录 evidence_ids、valid_from、valid_to、notes。
- 标记低置信度、叙事暴露和待补证据。
- 输出映射变更摘要。

## Out of scope

- 不写完整细分报告。
- 不写完整个股深度。
- 不做估值结论。
- 不把映射分数等同交易信号。
- 不静默改写历史映射；重要变化需记录刷新或变更说明。

## Outputs

- `reports/stocks/<stock_code>_<company_slug>/segment_exposure.yaml`
- `reports/segments/<segment_id>/company_universe.csv`
- exposure change note
- evidence gap list

## Workflow

1. 确认 segment 和 company 标识。
2. 检查已有 exposure 记录。
3. 对新增证据进行来源等级和 claim_type 标注。
4. 更新 exposure_type、score、confidence。
5. 标记 valid_from / valid_to。
6. 输出变化、反证和待复核项。

## Guardrails

- revenue_pct 和 profit_pct 不能猜；无披露写 MISSING。
- 只凭市场叙事不能给高 exposure_score。
- 技术储备、产能、订单、收入必须分开。
- 冲突证据必须并列呈现。

## Quality checklist

- [ ] segment_id、company_id、stock_code、stock_name 已填写。
- [ ] exposure_type 在允许枚举内。
- [ ] exposure_score 有证据或 TODO。
- [ ] evidence_ids 已填写或显式缺失。
- [ ] confidence 已标注。
- [ ] revenue_pct / profit_pct 缺失时标 MISSING。
- [ ] 变更需要 refresh log 时已记录。
