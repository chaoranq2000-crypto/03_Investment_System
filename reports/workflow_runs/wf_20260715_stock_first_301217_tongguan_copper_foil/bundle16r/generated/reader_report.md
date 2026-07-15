# 铜冠铜箔（301217）真实公司回归研究稿

- information_cutoff: `2026-07-15`
- workflow_id: `wf_20260715_stock_first_301217_tongguan_copper_foil`
- status: `engineering_candidate / human_review_pending`
- boundary: 本稿为证据约束的研究候选，不构成买入、卖出、持有或仓位建议。

## 业务边界与收入底盘

公司收入主要来自PCB铜箔和锂电池铜箔，不能把高端牌号的产量增速直接替代合并收入判断。

2025年两类铜箔合计构成绝大部分收入，其他业务仅用于完整对账。 〔metric_301217_revenue_2025〕 〔metric_301217_pcb_revenue_2025〕 〔metric_301217_lithium_revenue_2025〕 〔other_revenue〕

模型链接：`pcb_copper_foil`、`lithium_battery_copper_foil`

## 经营驱动方程

收入的核心方程是销量乘以铜价联动基价与加工费，利润更依赖加工费、产品结构和良率。

铜价加加工费的定价规则意味着铜价上涨可能抬高收入，却不必然等比例抬高单位毛利。 〔claim_301217_pricing〕 〔pcb_copper_foil〕 〔assumption_301217_margin〕

模型链接：`pcb_copper_foil`、`assumption_301217_margin`

## 高端产品代际验证

HVLP产量增长提供结构升级线索，但缺少牌号级收入和利润，当前只能作为转化漏斗的前置证据。

需要后续披露把认证、批量供货、加工费和毛利串成闭环。 〔claim_301217_hvlp_output〕 〔event_301217_capacity_conversion〕

模型链接：`pcb_copper_foil`

## 分产品毛利桥

PCB铜箔已有正毛利缓冲，锂电铜箔2025年接近盈亏平衡，二者对利润的弹性并不相同。

情景模型因此分别设置两条毛利路径，不用合并平均值掩盖分化。 〔metric_301217_pcb_margin_2025〕 〔metric_301217_lithium_margin_2025〕 〔claim_301217_margin_divergence〕

模型链接：`pcb_copper_foil`、`lithium_battery_copper_foil`

## 产能与产销约束

2025年销量接近8万吨年产能量级，新增增长需要由利用率、产品组合或新增有效能力解释。

产量与销量接近，但不能据此推定所有产能均处于稳定高良率状态。 〔metric_301217_output_2025〕 〔metric_301217_sales_2025〕 〔metric_301217_capacity_2025〕

模型链接：`assumption_301217_pcb_growth`

## 2026年一季度更新

一季度收入和利润提供正向更新，经营现金流为负则提示营运资金占用仍需复核。

单季度利润不能替代现金转化验证，后续需检查应收、存货和铜价变化。 〔metric_301217_q1_revenue_2026〕 〔metric_301217_q1_np_2026〕 〔metric_301217_q1_ocf_2026〕 〔claim_301217_q1_cash〕

模型链接：`assumption_301217_cash_conversion`

## 三情景预测边界

预测仅表示加工费和产品结构变化的敏感性，不将客户认证或高端牌号放量写成既定事实。

熊市情景保留锂电铜箔负毛利可能，基准与乐观情景要求后续分产品数据验证。 〔assumption_301217_lithium_growth〕 〔assumption_301217_margin〕 〔event_301217_interim_mix〕

模型链接：`lithium_battery_copper_foil`

## 风险与反证

铜价波动、加工费下行、客户认证延迟、良率不达预期和现金回收偏弱均可否定乐观情景。

当前最重要的缺口是高端产品牌号级经济性，而不是再增加无出处的行业叙事。 〔claim_301217_hvlp_output〕 〔claim_301217_pricing〕 〔claim_301217_q1_cash〕

模型链接：`event_301217_interim_mix`、`event_301217_capacity_conversion`

## 边界与复核状态

所有事实、管理层表述与估计均按来源类型区分；未披露分部经济性保持为 MISSING_DISCLOSURE。
外部人工复核尚未签署，因此 sample_quality_allowed=false，p2_allowed=false。
