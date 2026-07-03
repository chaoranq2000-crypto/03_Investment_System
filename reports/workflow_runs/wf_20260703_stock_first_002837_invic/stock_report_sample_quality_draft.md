# 价值发现：002837 英维克

## 0. Metadata

| 字段 | 内容 |
|---|---|
| stock_code | 002837 |
| company_id | cn_002837_invic |
| report_date | 2026-07-03 |
| quality_target | R3_sample_quality_draft |
| evidence_snapshot | reports\workflow_runs\wf_20260703_stock_first_002837_invic\evidence_manifest_delta.csv |
| report_status | draft_for_quality_review |

## 前言

英维克的样例质量报告应围绕数据中心热管理/液冷产品暴露与公司层面财务兑现之间的证据差距展开。 当前可支持的事实是产品/业务线索与公司层面财务指标，最大的证据缺口是液冷收入占比和毛利率仍未完成表格化披露核验。

## 一、财务概览

公司层面财务数据已进入指标注册表，但这些指标只支持公司整体观察，不支持直接推导液冷业务收入。

| 指标 | 期间 | 数值 | 单位 | metric_id / evidence |
| --- | --- | --- | --- | --- |
| total_revenue | 20260331 | 1175329313.61 | CNY | metric_cn_002837_invic_total_revenue_20260331_d1f448 |
| n_income_attr_p | 20260331 | 8657602.27 | CNY | metric_cn_002837_invic_n_income_attr_p_20260331_530e7b |
| grossprofit_margin | 20260331 | 24.2935 | CNY | metric_cn_002837_invic_grossprofit_margin_20260331_963af8 |
| netprofit_margin | 20260331 | 1.2049 | CNY | metric_cn_002837_invic_netprofit_margin_20260331_6379be |
| debt_to_assets | 20260331 | 55.1085 | CNY | metric_cn_002837_invic_debt_to_assets_20260331_44170f |
| n_cashflow_act | 20260331 | -386363968.71 | CNY | metric_cn_002837_invic_n_cashflow_act_20260331_c16d8a |
| accounts_receiv | 20260331 | 3060887771.01 | CNY | metric_cn_002837_invic_accounts_receiv_20260331_153826 |
| inventories | 20260331 | 1181981088.85 | CNY | metric_cn_002837_invic_inventories_20260331_a0cd42 |

## 二、业务拆分

业务拆分的当前结论是：可以识别数据中心温控/液冷相关产品暴露，但收入、利润和客户订单贡献必须保持 MISSING，等待官方表格或公告补证。

| 业务 | 收入 | 占比 | 毛利率 | 增长驱动 | 证据 | 置信度 |
| --- | --- | --- | --- | --- | --- | --- |
| 数据中心/机房温控及液冷相关解决方案 | MISSING_DISCLOSURE | MISSING_DISCLOSURE | MISSING_DISCLOSURE | AI算力与数据中心热管理需求，仍需订单/分产品收入证据确认兑现强度。 | claim_cn_002837_invic_28149e07,claim_cn_002837_invic_e9580358,claim_cn_002837_invic_013e4cab,claim_cn_002837_invic_a430b6e8,claim_cn_002837_invic_80ee216e,claim_cn_002837_invic_33cd54f4,claim_cn_002837_invic_cb36fb00,claim_cn_002837_invic_0449cc90,claim_cn_002837_invic_7f197d50,claim_cn_002837_invic_9c6c3e3d,claim_cn_002837_invic_5e6afcf0,claim_cn_002837_invic_fcce4010,claim_cn_002837_invic_0771f4eb,claim_cn_002837_invic_9872a700,claim_cn_002837_invic_07f57e51,claim_cn_002837_invic_377c2029,claim_cn_002837_invic_a560164f | medium |

## 三、行业分析

AI算力密度提升使数据中心热管理成为需要跟踪的细分变量。公司处在价值链的位置暂按“数据中心/机房温控及液冷相关解决方案”处理，关键验证指标包括分业务收入、毛利率、订单和经营现金流。行业供给格局仍为 TODO_SOURCE_REQUIRED，不能用情绪线索替代事实。

## 四、盈利预测

以下预测是估计和情景模型，不是事实；模型基准来自公司整体历史收入，暂不把预测收入归因到液冷业务。

| 指标 | 2026E | 2027E | 2028E | 核心假设 | 证据/模型 |
| --- | --- | --- | --- | --- | --- |
| 收入 | 1269355658.7 | 1396291224.57 | 1535920347.03 | 估计值，基于公司层面历史收入，不归因到液冷业务 | metric_cn_002837_invic_revenue_20260331_4f7f22 |

## 五、估值分析

估值部分仅形成场景框架和同业表占位，不输出价格指令或交易动作。当前缺少实时 PE/PB/PS 等结构化行情字段，因此估值结论保持观察口径。

| 公司 | 代码 | 业务相关性 | PE TTM | 2026E PE | 2027E PE | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| 英维克 | 002837 | subject_company | TODO_MARKET_DATA | TODO_MODEL_INPUT | TODO_MODEL_INPUT | 估值表存在，但实时估值字段需结构化行情快照补齐。 |

估值结论：当前仅形成场景估值框架，不形成交易动作或价格指令。

## 六、技术分析

技术面只作为市场状态观察。数据日期为 2026-07-03；若缺少行情快照，则本节保持 TODO_MARKET_DATA，不影响基本面证据判断。

## 七、情绪分析

宏观、行业和公司情绪当前均为线索层信息，必须标注为 clue 或 TODO_SOURCE_REQUIRED，不能写成事实结论。

## 八、事件驱动

| 日期/窗口 | 事件 | 影响变量 | 超预期条件 | 低于预期风险 | 证据 |
|---|---|---|---|---|---|
| next_reporting_window | 下一期定期报告或经营更新 | 收入、毛利率、现金流、分业务披露 | 分业务或订单证据改善 | 收入兑现或现金流弱于模型 | claim_cn_002837_invic_28149e07,claim_cn_002837_invic_e9580358,claim_cn_002837_invic_013e4cab |

## 九、研究结论、风险与跟踪清单

研究状态：watch_for_evidence。事实层面，公司已具备数据中心温控/液冷相关产品线索和公司层面财务指标；推断层面，产品暴露值得继续跟踪，但收入暴露不能升级，直到分业务收入、订单或客户证据被审查。

### 风险与反证

分业务收入和液冷收入占比缺失，不能把公司整体收入归因到液冷。; 结构化财务指标来自公司整体，不能替代官方披露中的业务暴露证据。

### 后续跟踪指标

| 指标 | 为什么重要 | 频率 | 来源 | 触发动作 |
|---|---|---|---|---|
| 分业务收入/毛利率 | 验证产品暴露是否转化为财务贡献 | 定期报告 | annual_report / interim_report | 更新 analysis_pack |
| 订单/客户/产能公告 | 验证需求兑现 | 事件驱动 | announcement | 更新 evidence_gap |
| 经营现金流 | 验证利润质量 | 季度 | structured_financial_data | 更新 financial_quality |

## 附录 A：Evidence Map

| 结论 | claim_id / metric_id | evidence_id | 来源 | 日期 | 页码/表格 | 置信度 |
| --- | --- | --- | --- | --- | --- | --- |
| 业务/产品暴露候选 | claim_cn_002837_invic_28149e07 | 见 claims_registry | annual_report | 2026-07-03 | page locator | medium |
| 业务/产品暴露候选 | claim_cn_002837_invic_e9580358 | 见 claims_registry | annual_report | 2026-07-03 | page locator | medium |
| 业务/产品暴露候选 | claim_cn_002837_invic_013e4cab | 见 claims_registry | annual_report | 2026-07-03 | page locator | medium |
| 业务/产品暴露候选 | claim_cn_002837_invic_a430b6e8 | 见 claims_registry | annual_report | 2026-07-03 | page locator | medium |
| 业务/产品暴露候选 | claim_cn_002837_invic_80ee216e | 见 claims_registry | annual_report | 2026-07-03 | page locator | medium |
| 业务/产品暴露候选 | claim_cn_002837_invic_33cd54f4 | 见 claims_registry | annual_report | 2026-07-03 | page locator | medium |
| 业务/产品暴露候选 | claim_cn_002837_invic_cb36fb00 | 见 claims_registry | annual_report | 2026-07-03 | page locator | medium |
| 业务/产品暴露候选 | claim_cn_002837_invic_0449cc90 | 见 claims_registry | annual_report | 2026-07-03 | page locator | medium |
| 公司层面财务指标 | metric_cn_002837_invic_list_date_unknown_ffc7f4 | 见 metrics_registry | structured_data | 2026-07-03 | csv | medium |
| 公司层面财务指标 | metric_cn_002837_invic_total_revenue_20260331_d1f448 | 见 metrics_registry | structured_data | 2026-07-03 | csv | medium |
| 公司层面财务指标 | metric_cn_002837_invic_revenue_20260331_4f7f22 | 见 metrics_registry | structured_data | 2026-07-03 | csv | medium |
| 公司层面财务指标 | metric_cn_002837_invic_operate_profit_20260331_04da98 | 见 metrics_registry | structured_data | 2026-07-03 | csv | medium |
| 公司层面财务指标 | metric_cn_002837_invic_total_profit_20260331_3c4ba8 | 见 metrics_registry | structured_data | 2026-07-03 | csv | medium |
| 公司层面财务指标 | metric_cn_002837_invic_n_income_20260331_44819e | 见 metrics_registry | structured_data | 2026-07-03 | csv | medium |
| 公司层面财务指标 | metric_cn_002837_invic_n_income_attr_p_20260331_530e7b | 见 metrics_registry | structured_data | 2026-07-03 | csv | medium |
| 公司层面财务指标 | metric_cn_002837_invic_basic_eps_20260331_16e329 | 见 metrics_registry | structured_data | 2026-07-03 | csv | medium |

## 附录 B：Open Questions / Evidence Gaps

- gap_liquid_cooling_revenue_pct: 液冷收入占比和毛利率
