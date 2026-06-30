# Claims Review

> 本内容用于研究流程与证据管理，不构成任何买入、卖出、持有或其他交易建议。

| claim_id | evidence_id | entity | claim_type | confidence | claim_text |
|---|---|---|---|---|---|
| claim_segment_ai_server_liquid_cooling_20260701_001 | policy_miit_compute_infra_20231008_9f2a30 | segment | fact | medium | 国家层面算力基础设施建设目标为数据中心热管理需求提供政策背景。 |
| claim_segment_ai_server_liquid_cooling_20260701_002 | industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91 | segment | fact | medium | 冷板式液冷是算力中心高功率密度服务器散热的重要技术路径之一。 |
| claim_segment_ai_server_liquid_cooling_20260701_003 | industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91 | segment | inference | medium | 本细分应覆盖冷板、CDU、管路、快接头、泵阀、冷量分配及系统集成等链条。 |
| claim_company_002837_invic_20260701_001 | annual_report_002837_invic_2025_0f8fcf | company | fact | medium | 英维克披露数据中心热管理和液冷相关产品/解决方案，属于产品暴露候选。 |
| claim_company_002837_invic_20260701_002 | annual_report_002837_invic_2025_0f8fcf | company | inference | medium | 英维克的液冷暴露更接近产品/客户暴露，而非已核验的高纯度收入暴露。 |
| claim_company_301018_shenling_20260701_001 | annual_report_301018_shenling_2024_122331 | company | fact | medium | 申菱环境年报出现浸没式液冷、冷板式液冷等数据服务温控业务相关表述。 |
| claim_company_301018_shenling_20260701_002 | semiannual_report_301018_shenling_2025_122461 | company | fact | medium | 申菱环境2025半年报继续提供液冷业务线索，降低单一报告偶然性。 |
| claim_company_300499_gaolan_20260701_001 | annual_report_300499_gaolan_2025_122516 | company | fact | low | 高澜股份存在数据中心液冷相关产品/解决方案线索，但本轮证据不足以确认高纯度收入暴露。 |
| claim_company_300731_cotran_20260701_001 | annual_report_300731_cotran_2025_122523 | company | fact | medium | 科创新源披露液冷板及数据中心液冷需求相关内容，属于产品/技术暴露候选。 |
| claim_company_300731_cotran_20260701_002 | annual_report_300731_cotran_2025_122523 | company | inference | medium | 科创新源液冷业务在本轮不应被视为核心收入暴露，应先列为低到中置信度观察项。 |
| claim_company_300602_frd_20260701_001 | semiannual_report_300602_frd_2025_122450 | company | fact | low | 飞荣达具备热管理相关业务线索，但AI服务器液冷暴露需要进一步核验。 |
| claim_company_300602_frd_20260701_002 | annual_report_300602_frd_2024_122310 | company | inference | medium | 飞荣达热管理宽口径不能直接等同于AI服务器液冷收入。 |
| claim_data_tushare_20260701_001 | market_data_tushare_probe_20260701_8bbf20 | other | fact | high | 初始Tushare调用因未设置代理URL而被服务端返回token无效，该失败记录已被代理配置成功验证取代。 |
| claim_data_tushare_20260701_002 | market_data_tushare_stock_basic_20260701_a6d9f2 | other | fact | high | 按配置指南设置Tushare代理URL后，stock_basic成功返回P1候选公司的代码、简称、地区、行业、上市板块和上市日期。 |

## Review Notes

- 管理层、行业报告、研究推断已通过 claim_type 区分。
- 暂无使用券商预测作为事实的条目。
- Tushare初始失败记录已被代理配置成功验证取代，不进入评分依据。
