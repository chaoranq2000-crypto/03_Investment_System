# 赤峰黄金（600988）真实公司回归研究稿

- information_cutoff: `2026-07-15`
- workflow_id: `wf_20260715_stock_first_600988_chifeng_gold`
- status: `engineering_candidate / human_review_pending`
- boundary: 本稿为证据约束的研究候选，不构成买入、卖出、持有或仓位建议。

## 黄金主业集中度

经营结果高度集中于黄金业务，研究模型应优先解释黄金价格、产量和单位成本，而非平均分配权重。

2025年黄金收入和毛利率显示主业集中度，其余业务保留完整对账和风险观察。 〔metric_600988_revenue_2025〕 〔metric_600988_gold_revenue_2025〕 〔metric_600988_gold_margin_2025〕 〔claim_600988_gold_concentration〕

模型链接：`gold_mining`

## 量价成本方程

黄金利润可拆为销量、实现价格与单位成本三条主线，AISC用于补充维持运营和资本强度约束。

2025年产销量与成本指标构成模型基准，但不等于未来稳定值。 〔metric_600988_gold_output_2025〕 〔metric_600988_gold_sales_2025〕 〔metric_600988_unit_cost_2025〕 〔metric_600988_aisc_2025〕

模型链接：`assumption_600988_gold_price`、`assumption_600988_gold_volume`、`assumption_600988_unit_cost`

## 一季度量价分化

一季度售价上升而产量下降，盈利变化首先体现价格弹性，尚不能证明生产端同步改善。

后续必须用半年和全年产量验证季度波动是否消失。 〔metric_600988_q1_price_2026〕 〔metric_600988_q1_output_2026〕 〔claim_600988_price_volume〕

模型链接：`gold_mining`、`event_600988_interim_actual`

## 成本与AISC约束

一季度单位成本和AISC高于2025年全年水平，价格高位不能替代对成本曲线的持续复核。

品位、回收率、剥采节奏和矿山组合都可能改变成本可比性。 〔metric_600988_q1_unit_cost_2026〕 〔metric_600988_q1_aisc_2026〕 〔claim_600988_cost_pressure〕

模型链接：`assumption_600988_unit_cost`

## 现金流与资本开支

2025年经营现金流较强，但矿业增长仍需与资本开支、建设进度和维持性投入共同评估。

单一现金流总额不能证明所有矿山项目具有相同回报和回收周期。 〔metric_600988_ocf_2025〕 〔copper_and_polymetallic〕

模型链接：`copper_and_polymetallic`、`event_600988_cost_recovery`

## 半年度业绩预告边界

17.0亿至17.8亿元是管理层未经审计估计，只能作为刷新锚点，不能重写为已实现事实。

预告解释指向黄金售价上升，仍需正式半年报补足产量和成本桥。 〔metric_600988_h1_np_low_2026〕 〔metric_600988_h1_np_high_2026〕 〔claim_600988_h1_guidance〕

模型链接：`assumption_600988_h1_anchor`

## 商品价格三情景

三情景只展示实现价格和成本组合的敏感性，不对黄金市场方向作确定判断。

熊市情景同时考虑价格回落与成本粘性，乐观情景也要求产量和成本证据跟进。 〔assumption_600988_gold_price〕 〔assumption_600988_gold_volume〕 〔assumption_600988_unit_cost〕

模型链接：`gold_mining`

## 风险与证伪条件

金价回落、产量持续下降、品位或回收率走弱、单位成本上升和资本开支失控均会压低情景结果。

正式半年报若无法确认预告并解释成本变化，模型应回流重估而不是维持旧叙事。 〔claim_600988_price_volume〕 〔claim_600988_cost_pressure〕 〔event_600988_interim_actual〕 〔event_600988_cost_recovery〕

模型链接：`gold_mining`

## 边界与复核状态

所有事实、管理层表述与估计均按来源类型区分；未披露分部经济性保持为 MISSING_DISCLOSURE。
外部人工复核尚未签署，因此 sample_quality_allowed=false，p2_allowed=false。
