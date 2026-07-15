# 东阳光（600673）真实公司回归研究稿

- information_cutoff: `2026-07-15`
- workflow_id: `wf_20260715_stock_first_600673_hec_tech`
- status: `engineering_candidate / human_review_pending`
- boundary: 本稿为证据约束的研究候选，不构成买入、卖出、持有或仓位建议。

## 存量业务结构

高端铝箔收入规模较大但毛利率较低，化工新材料是更重要的毛利来源，电子材料提供第二条利润主线。

2025年分业务收入成本与合并口径完成对账，新项目没有被塞入历史分部。 〔metric_600673_revenue_2025〕 〔metric_600673_fluoro_revenue_2025〕 〔metric_600673_fluoro_margin_2025〕 〔metric_600673_electronic_revenue_2025〕 〔metric_600673_aluminum_revenue_2025〕 〔claim_600673_mix〕

模型链接：`fluorochemicals`、`electronic_materials`、`high_end_aluminum`

## 制冷剂量价成本方程

制冷剂配额约束供给，但配额、销量、实现价格和单位成本必须逐层区分。

约6万吨配额只作为经营约束，不直接写成销量或利润。 〔metric_600673_refrigerant_quota_2026〕 〔claim_600673_quota〕 〔assumption_600673_fluoro〕

模型链接：`fluorochemicals`

## 电子材料利用率与结构

电子元器件业务的关键是有效产能、利用率和产品结构，年报分部毛利只能作为合并起点。

未披露产品线级利用率时，模型仅做分部级敏感性，不制造单品经济性。 〔metric_600673_electronic_revenue_2025〕 〔electronic_materials〕 〔assumption_600673_electronics〕

模型链接：`electronic_materials`

## 一季度经营更新

2026年一季度收入、利润和经营现金流均有披露，但单季总量无法解释各业务的变化来源。

半年报需要恢复分部桥，检查化工、电子材料和铝箔的量价成本贡献。 〔metric_600673_q1_revenue_2026〕 〔metric_600673_q1_np_2026〕 〔metric_600673_q1_ocf_2026〕 〔event_600673_interim_segments〕

模型链接：`fluorochemicals`、`electronic_materials`

## 液冷与算力项目边界

IDC采购上限和算力服务合同总额均是合同条件，不是已确认收入；交付、验收、投运和结算才是模型入口。

在缺少验收和收入成本披露前，液冷及算力相关分部在预测中保持零收入。 〔metric_600673_idc_cost_ceiling_2026〕 〔metric_600673_compute_contract_low_2026〕 〔metric_600673_compute_contract_high_2026〕 〔claim_600673_idc_cost〕 〔claim_600673_compute_contract〕

模型链接：`liquid_cooling`、`idc_and_compute_infrastructure`、`assumption_600673_new_projects`

## 并购交割漏斗

交易作价与拟取得股权是草案条款，审批、注册、交割、融资及并表时点尚未完成。

所有预测情景都不提前并表，只有事件触发后才能增加合并口径。 〔metric_600673_ma_value_2026〕 〔claim_600673_ma_pending〕 〔event_600673_ma_approval〕

模型链接：`acquisition_consolidation`、`assumption_600673_ma`

## 分层情景预测

存量业务使用量价成本敏感性，新项目使用零基数事件门，并购使用交割门，三类路径不相互替代。

这种处理牺牲表面增长数字，却避免把合同金额和交易草案当成经营事实。 〔assumption_600673_fluoro〕 〔assumption_600673_electronics〕 〔assumption_600673_new_projects〕 〔assumption_600673_ma〕

模型链接：`fluorochemicals`、`electronic_materials`、`liquid_cooling`、`idc_and_compute_infrastructure`、`acquisition_consolidation`

## 风险与证伪条件

制冷剂价格回落、电子材料利用率下降、项目验收或回款延迟、IDC电力成本上升、并购审批失败与融资成本超预期均可能压低情景结果。

若后续披露仍无法形成新业务收入成本桥，应继续保留缺失状态而非用合同总额填补。 〔claim_600673_compute_contract〕 〔claim_600673_ma_pending〕 〔event_600673_compute_acceptance〕 〔event_600673_ma_approval〕

模型链接：`idc_and_compute_infrastructure`、`acquisition_consolidation`

## 边界与复核状态

所有事实、管理层表述与估计均按来源类型区分；未披露分部经济性保持为 MISSING_DISCLOSURE。
外部人工复核尚未签署，因此 sample_quality_allowed=false，p2_allowed=false。
