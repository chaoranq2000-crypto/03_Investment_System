# 细分方向研究：AI服务器液冷

> 本内容用于研究流程与证据管理，不构成任何买入、卖出、持有或其他交易建议。

## 0. Metadata

| Field | Value |
|---|---|
| report_id | segment_report_ai_server_liquid_cooling_2026-07-01 |
| report_type | segment_report |
| segment_id | ai_server_liquid_cooling |
| title | AI服务器液冷 |
| report_date | 2026-07-01 |
| evidence_snapshot | policy_miit_compute_infra_20231008_9f2a30; industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91; annual_report_002837_invic_2025_0f8fcf; annual_report_301018_shenling_2024_122331; semiannual_report_301018_shenling_2025_122461; annual_report_300499_gaolan_2025_122516; annual_report_300731_cotran_2025_122523; semiannual_report_300602_frd_2025_122450; annual_report_300602_frd_2024_122310; market_data_tushare_stock_basic_20260701_a6d9f2 |
| confidence | medium |
| status | current |

## 1. 一句话结论

- fact: AI算力基础设施建设提供需求背景，但政策本身不等同液冷订单。证据：evidence_id=policy_miit_compute_infra_20231008_9f2a30; claim_id=claim_segment_ai_server_liquid_cooling_20260701_001
- fact: 冷板式液冷是算力中心高功率密度场景的重要散热路径之一。证据：evidence_id=industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91; claim_id=claim_segment_ai_server_liquid_cooling_20260701_002
- inference: 本轮A股公司池应按产品/技术/客户/收入暴露分层，不能只按“液冷概念”纳入。证据：claim_id=claim_segment_ai_server_liquid_cooling_20260701_003
- 主要不确定性：液冷收入占比、客户量产进度、价格竞争和技术路线替代仍需补证。

## 2. 细分定义与边界

### 2.1 包含什么

- AI服务器、智算中心、数据中心液冷设备与部件。证据：evidence_id=industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91
- 冷板、CDU、泵阀、管路、快接头、换热和系统集成。证据：claim_id=claim_segment_ai_server_liquid_cooling_20260701_003

### 2.2 不包含什么

- 普通商用空调、传统机房精密空调、储能温控和汽车热管理。
- 仅有市场叙事但没有产品、项目、客户或收入证据的公司。

### 2.3 相邻细分

- 数据中心电源、服务器结构件、电子导热材料、储能温控。

## 3. 产业链位置

| 环节 | 说明 | 关键对象 | evidence_id | confidence |
|---|---|---|---|---|
| upstream | 冷板、管路、泵阀、快接头、导热材料 | 组件供应商 | industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91 | medium |
| midstream | CDU、换热、控制系统、液冷机柜 | 设备厂商/集成商 | industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91 | medium |
| downstream | 云厂商、运营商、IDC、AI服务器部署方 | 数据中心客户 | policy_miit_compute_infra_20231008_9f2a30 | medium |

## 4. 需求驱动

| Driver | claim_type | Evidence | Confidence | Notes |
|---|---|---|---|---|
| AI算力基础设施扩张 | fact | policy_miit_compute_infra_20231008_9f2a30; claim_segment_ai_server_liquid_cooling_20260701_001 | medium | 政策背景，不直接等同订单 |
| 高功率密度服务器散热约束 | fact | industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91; claim_segment_ai_server_liquid_cooling_20260701_002 | medium | 需跟踪具体渗透率 |
| PUE/节能压力 | inference | industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91 | medium | 需补官方或客户侧指标 |

## 5. 供给与竞争格局

| 维度 | 事实 | 推断 | evidence_id | 风险/反证 |
|---|---|---|---|---|
| 产品侧 | 英维克、申菱环境等公司披露液冷相关产品线索 | 产品清晰度高于财务兑现清晰度 | annual_report_002837_invic_2025_0f8fcf; annual_report_301018_shenling_2024_122331 | 收入占比未披露 |
| 技术侧 | 科创新源、飞荣达有热管理/液冷线索 | 先列为技术或低置信度观察项 | annual_report_300731_cotran_2025_122523; semiannual_report_300602_frd_2025_122450 | 可能只是概念映射 |
| 竞争侧 | 供给端涉及设备、部件和系统集成 | 利润池可能分散 | industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91 | 价格竞争和客户议价 |

## 6. 利润池分析

| 利润池位置 | 指标 | 口径 | metric_id | evidence_id | TODO/MISSING |
|---|---|---|---|---|---|
| 设备/系统集成 | 液冷项目收入 | 公司披露口径 | TODO | annual_report_002837_invic_2025_0f8fcf | MISSING: 暂无直接披露 |
| 部件 | 液冷板/快接头收入 | 分产品口径 | TODO | annual_report_300731_cotran_2025_122523 | MISSING: 暂无直接披露 |
| 客户侧 | 液冷部署规模 | 云厂商/运营商采购口径 | TODO | industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91 | TODO: 需要补充证据 |

## 7. A股公司池

| 股票代码 | 公司 | 暴露类型 | 暴露分 | 证据 | 置信度 | 备注 |
|---|---|---:|---:|---|---|---|
| 002837 | 英维克 | product | 4 | annual_report_002837_invic_2025_0f8fcf | medium | 产品暴露清楚，收入占比待补 |
| 301018 | 申菱环境 | product | 4 | annual_report_301018_shenling_2024_122331; semiannual_report_301018_shenling_2025_122461 | medium | 液冷线索由两期报告交叉验证 |
| 300499 | 高澜股份 | product | 3 | annual_report_300499_gaolan_2025_122516 | low | 产品线索存在，收入/客户待补 |
| 300731 | 科创新源 | technology | 2 | annual_report_300731_cotran_2025_122523 | medium | 概念降权样本，验证收入兑现 |
| 300602 | 飞荣达 | technology | 2 | semiannual_report_300602_frd_2025_122450; annual_report_300602_frd_2024_122310 | low | 热管理宽口径，液冷需拆分 |

## 8. 关键指标体系

| 指标 | 粒度 | 频率 | 来源 | 解释 |
|---|---|---|---|---|
| liquid_cooling_revenue_pct | company | 半年/年度 | 定期报告 | 液冷收入占总收入比例，当前MISSING |
| data_center_liquid_cooling_orders | company | 事件 | 公告/投关 | 液冷订单或客户验证，当前TODO |
| liquid_cooling_penetration_rate | segment | 半年/年度 | 行业报告/客户采购 | 液冷渗透率，当前TODO |
| gross_margin_thermal_management | company | 半年/年度 | 定期报告 | 热管理业务毛利率，需避免和液冷混用 |

## 9. 催化剂

| Catalyst | claim_type | evidence_id | expected_window | confidence | notes |
|---|---|---|---|---|---|
| 年报/半年报披露液冷收入 | unknown | TODO | 2026H2-2027H1 | medium | 关键验证项 |
| 运营商或云厂商液冷采购更新 | unknown | TODO | 2026H2 | medium | 需补客户侧证据 |
| CAICT/行业报告更新渗透率 | inference | industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91 | 2026-2027 | medium | 支撑行业层刷新 |

## 10. 风险与反证

| 风险/反证 | Related claim_id | evidence_id | Impact | Follow-up |
|---|---|---|---|---|
| 热管理宽口径不能证明AI服务器液冷收入 | claim_company_300602_frd_20260701_002 | annual_report_300602_frd_2024_122310 | 高 | 拆分产品和客户 |
| 技术储备可能未转化为订单 | claim_company_300731_cotran_20260701_002 | annual_report_300731_cotran_2025_122523 | 中 | 跟踪订单和收入 |
| Tushare已可用但尚未补财务深字段 | claim_data_tushare_20260701_002 | market_data_tushare_stock_basic_20260701_a6d9f2 | 中 | 继续抓取fina_indicator/anns_d |

## 11. 评分卡

| Dimension | Score 0-5 | Rationale | evidence_ids | confidence |
|---|---:|---|---|---|
| market_space | 4 | AI算力基础设施扩张提供需求背景 | policy_miit_compute_infra_20231008_9f2a30 | medium |
| growth_visibility | 3 | 技术路径明确，但渗透率数据待补 | industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91 | medium |
| a_share_purity | 3 | 有若干A股产品暴露，但收入占比缺失 | annual_report_002837_invic_2025_0f8fcf; annual_report_301018_shenling_2024_122331 | medium |
| evidence_quality | 3 | 官方披露充足，财务字段不完整 | evidence_manifest | medium |

说明：评分只表示研究优先级和证据质量，不是交易信号。

## 12. 后续跟踪清单

| Task | Object | Evidence needed | Owner | Due date | Status |
|---|---|---|---|---|---|
| 用Tushare补财务和公告线索 | data_source | Tushare fina_indicator/anns_d | Codex | 2026-07-15 | open |
| 抽取液冷收入占比 | 002837/301018/300731 | 年报分产品表 | Codex | 2026-07-31 | open |
| 补客户侧采购证据 | segment | 运营商/云厂商招标或技术规范 | Codex | 2026-08-15 | open |

## 13. 证据地图

详见 `evidence_map.md`。
