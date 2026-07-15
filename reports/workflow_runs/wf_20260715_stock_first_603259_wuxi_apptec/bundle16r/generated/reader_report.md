# 药明康德（603259）真实公司回归研究稿

- information_cutoff: `2026-07-15`
- workflow_id: `wf_20260715_stock_first_603259_wuxi_apptec`
- status: `engineering_candidate / human_review_pending`
- boundary: 本稿为证据约束的研究候选，不构成买入、卖出、持有或仓位建议。

## 持续经营业务结构

化学业务是收入和毛利主轴，测试、生物学与其他业务提供补充，终止经营必须从未来基准中剔除。

2025年合并收入与持续经营收入之间的差额单独列为终止经营对账残差。 〔metric_603259_revenue_2025〕 〔metric_603259_continuing_revenue_2025〕 〔metric_603259_chem_revenue_2025〕 〔discontinued_operations〕

模型链接：`chemistry_crdmo`、`testing_and_biology`

## 订单转收入漏斗

在手订单提高可见度，却不能直接替代收入预测，模型需要显式保留履约和取消条件。

2025年末与2026年一季度末订单规模均较大，转化期限仍未按统一口径披露。 〔metric_603259_backlog_2025〕 〔metric_603259_q1_backlog_2026〕 〔claim_603259_backlog_not_revenue〕

模型链接：`assumption_603259_backlog_conversion`

## 项目阶段推进

项目总数和商业化项目数增加说明漏斗继续扩展，但项目价值、成功率和确认节奏并不均质。

项目数用于验证方向，不能用简单平均值制造未披露的单项目经济性。 〔metric_603259_pipeline_2025〕 〔metric_603259_commercial_2025〕 〔metric_603259_q1_pipeline_2026〕 〔metric_603259_q1_commercial_2026〕 〔claim_603259_funnel_progress〕

模型链接：`assumption_603259_pipeline`

## 高增长业务结构

TIDES业务的收入增长和订单增长支持化学业务结构改善，但高增速可持续性必须由后续确认收入验证。

D&M和TIDES规模显示后期及商业化服务的重要性，模型未把历史增速机械外推。 〔metric_603259_dm_revenue_2025〕 〔metric_603259_tides_revenue_2025〕 〔claim_603259_tides_mix〕

模型链接：`assumption_603259_tides_mix`

## 一季度经营更新

一季度收入、订单和项目数量提供同向更新，但仍缺少完整的订单转化与分部利润桥。

半年报应同时检查收入确认、订单增减和项目阶段，而不是只看单一总额。 〔metric_603259_q1_revenue_2026〕 〔metric_603259_q1_backlog_2026〕 〔event_603259_interim_conversion〕

模型链接：`chemistry_crdmo`

## 管理层目标边界

2026年收入目标仅用于校验基准情景，披露已明确其不是盈利预测或承诺。

若正式结果偏离目标，应回到订单转化、项目进度和汇率等驱动重新解释。 〔claim_603259_outlook〕 〔assumption_603259_management_outlook〕

模型链接：`assumption_603259_management_outlook`

## 三情景预测逻辑

三情景分别组合订单转化、项目推进和业务结构，不对未披露客户或单项目收入进行硬编码。

终止经营收入在所有未来情景中归零，避免用历史处置口径抬高持续经营增长。 〔assumption_603259_backlog_conversion〕 〔assumption_603259_pipeline〕 〔discontinued_operations〕

模型链接：`chemistry_crdmo`、`testing_and_biology`

## 风险与反证条件

客户项目取消或延期、监管约束、订单转化放缓、产能利用不足和汇率波动均可能推翻基准情景。

后续若订单增长未转化为收入和项目阶段提升，应下调转化假设而非延长叙事窗口。 〔claim_603259_backlog_not_revenue〕 〔event_603259_interim_conversion〕 〔event_603259_annual_pipeline〕

模型链接：`assumption_603259_backlog_conversion`

## 边界与复核状态

所有事实、管理层表述与估计均按来源类型区分；未披露分部经济性保持为 MISSING_DISCLOSURE。
外部人工复核尚未签署，因此 sample_quality_allowed=false，p2_allowed=false。
