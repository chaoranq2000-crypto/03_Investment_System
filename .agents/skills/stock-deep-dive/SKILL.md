---
name: stock-deep-dive
description: Use when analyzing one listed company across business lines, segment exposure, financial quality, customers, supply chain, governance, scenarios, risks, and evidence map. Do not use for multi-segment ranking or direct buy/sell/hold advice.
---

# Stock Deep Dive

## Goal

产出一个与多个细分方向联动、证据可追溯的个股深度研究包。

## When to use

- 用户要求研究单一 A 股公司或股票代码。
- 需要拆解业务、财务质量、客户供应链、治理和 linked_segments。
- 需要输出 `segment_exposure.yaml` 和 evidence map。

## Inputs

- stock_code、stock_name、company_id。
- linked_segments。
- 年报、公告、财务数据、纪要、行业证据。
- 已有 claim_id、metric_id 或 evidence_id。

## Responsibilities

- 确认公司主体和证券代码。
- 拆解业务结构和财务指标。
- 标注多个细分方向暴露。
- 区分事实、管理层表述、估计、推断和观点。
- 输出风险、反证、估值场景和跟踪指标。

## Out of scope

- 不做多个个股横向排序。
- 不把估值场景写成目标价指令。
- 不输出买入、卖出、持有建议。
- 不用单一新闻支撑关键财务结论。
- 不静默覆盖旧报告。

## Outputs

- `reports/stocks/<stock_code>_<company_slug>/<date>_stock_deep_dive.md`
- `reports/stocks/<stock_code>_<company_slug>/segment_exposure.yaml`
- `reports/stocks/<stock_code>_<company_slug>/evidence_map.md`
- `reports/stocks/<stock_code>_<company_slug>/valuation_scenarios.*`

## Workflow

1. 确认公司和证券标识。
2. 收集并登记证据。
3. 拆解业务与财务质量。
4. 标注 linked_segments 和 exposure 记录。
5. 构建 metrics 和 claim table。
6. 设计估值场景但不输出交易指令。
7. 列出风险、反证和 TODO。
8. 执行 quality-review。

## Guardrails

- 个股报告必须包含 evidence snapshot 和 evidence map。
- 管理层展望不能写成事实。
- 估值场景只表达假设和敏感性。
- scorecard 或 scenario 不能直接变成交易建议。

## Quality checklist

- [ ] company_id、stock_code、stock_name 正确。
- [ ] linked_segments 使用多对多 exposure。
- [ ] 关键业务和财务 claim 有 evidence_id / claim_id。
- [ ] metric 口径、单位、周期明确。
- [ ] 风险和反证已列出。
- [ ] TODO/MISSING 已显式标记。
- [ ] 未输出买卖建议。
