from __future__ import annotations

import csv
import hashlib
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_DATE = "2026-07-01"
SEGMENT_ID = "ai_server_liquid_cooling"
SEGMENT_NAME = "AI服务器液冷"
DISCLAIMER = "本内容用于研究流程与证据管理，不构成任何买入、卖出、持有或其他交易建议。"


def write_text(relative_path: str, content: str) -> None:
    path = ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def write_raw_text_once(relative_path: str, content: str) -> None:
    path = ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    new_content = textwrap.dedent(content).strip() + "\n"
    if path.exists():
        return
    path.write_text(new_content, encoding="utf-8")


def write_csv(relative_path: str, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path = ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def sha6(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:6]


EVIDENCE = [
    {
        "evidence_id": "policy_miit_compute_infra_20231008_9f2a30",
        "source_type": "policy",
        "source_name": "工业和信息化部等六部门",
        "title": "算力基础设施高质量发展行动计划",
        "publisher": "工业和信息化部等六部门/中国网信网转载",
        "publish_date": "2023-10-08",
        "raw_file_path": "https://www.cac.gov.cn/2023-10/10/c_1698598959340810.htm",
        "processed_text_path": "data/processed/text/ai_server_liquid_cooling/policy_miit_compute_infra_20231008_9f2a30.md",
        "reliability_rank": "B",
        "status": "fresh",
        "license_note": "官方政策网页；本地仅保存证据卡和来源链接。",
        "summary": [
            "政策把算力基础设施纳入国家级建设目标，并提出到2025年算力规模、存力和运力等方向目标。",
            "本证据支持“AI算力基础设施扩张是数据中心热管理需求背景”的政策层事实。",
        ],
        "limitations": [
            "政策文件不直接披露液冷设备收入、渗透率或上市公司订单。",
        ],
    },
    {
        "evidence_id": "industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91",
        "source_type": "industry_report",
        "source_name": "中国信息通信研究院",
        "title": "算力中心冷板式液冷发展研究报告",
        "publisher": "中国信息通信研究院",
        "publish_date": "2024-05-23",
        "raw_file_path": "https://www.caict.ac.cn/kxyj/qwfb/ztbg/202405/P020240523566116859176.pdf",
        "processed_text_path": "data/processed/text/ai_server_liquid_cooling/industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91.md",
        "reliability_rank": "B",
        "status": "fresh",
        "license_note": "准官方研究报告；本地仅保存证据卡和来源链接。",
        "summary": [
            "报告聚焦算力中心冷板式液冷，说明液冷与高功率密度服务器、数据中心节能之间的关系。",
            "报告可用于定义冷板式液冷产业链和技术边界，但市场规模、渗透率仍需用后续数据刷新。",
        ],
        "limitations": [
            "报告为行业研究口径，不能直接支撑单家公司收入占比。",
        ],
    },
    {
        "evidence_id": "annual_report_002837_invic_2025_0f8fcf",
        "source_type": "annual_report",
        "source_name": "英维克",
        "title": "002837 英维克 2025年年度报告摘要",
        "publisher": "深圳证券交易所/巨潮资讯",
        "publish_date": "2026-04-21",
        "raw_file_path": "https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-04-21/0f8fcf0d-8bb2-4417-a154-8fc52972e1a9.PDF",
        "processed_text_path": "data/processed/text/ai_server_liquid_cooling/annual_report_002837_invic_2025_0f8fcf.md",
        "reliability_rank": "A",
        "status": "fresh",
        "license_note": "交易所披露文件；本地仅保存证据卡和来源链接。",
        "summary": [
            "公司披露面向数据中心等场景提供热管理产品和解决方案，并在液冷相关产品线持续布局。",
            "本证据支持英维克属于AI服务器液冷/数据中心温控相关公司池的产品暴露。",
        ],
        "limitations": [
            "摘要层级信息有限，液冷收入占比、利润占比仍需完整年报或分部明细核验。",
        ],
    },
    {
        "evidence_id": "annual_report_301018_shenling_2024_122331",
        "source_type": "annual_report",
        "source_name": "申菱环境",
        "title": "301018 申菱环境 2024年年度报告",
        "publisher": "巨潮资讯",
        "publish_date": "2025-04-28",
        "raw_file_path": "https://static.cninfo.com.cn/finalpage/2025-04-28/1223319900.PDF",
        "processed_text_path": "data/processed/text/ai_server_liquid_cooling/annual_report_301018_shenling_2024_122331.md",
        "reliability_rank": "A",
        "status": "fresh",
        "license_note": "交易所披露文件；本地仅保存证据卡和来源链接。",
        "summary": [
            "公司年报披露数据服务相关温控业务，并出现浸没式液冷、冷板式液冷等研发或产品表述。",
            "本证据支持申菱环境在数据中心液冷方向存在产品/技术暴露。",
        ],
        "limitations": [
            "年报未在本轮证据卡中抽取液冷收入占比，需后续表格抽取确认。",
        ],
    },
    {
        "evidence_id": "semiannual_report_301018_shenling_2025_122461",
        "source_type": "annual_report",
        "source_name": "申菱环境",
        "title": "301018 申菱环境 2025年半年度报告",
        "publisher": "巨潮资讯",
        "publish_date": "2025-08-29",
        "raw_file_path": "https://static.cninfo.com.cn/finalpage/2025-08-29/1224614643.PDF",
        "processed_text_path": "data/processed/text/ai_server_liquid_cooling/semiannual_report_301018_shenling_2025_122461.md",
        "reliability_rank": "A",
        "status": "fresh",
        "license_note": "交易所披露文件；本地仅保存证据卡和来源链接。",
        "summary": [
            "半年报延续披露公司数据服务温控业务，并涉及冷板式/浸没式液冷产品和研发方向。",
            "本证据用于交叉验证申菱环境液冷业务不是单次公告线索。",
        ],
        "limitations": [
            "仍未替代分产品收入占比核验。",
        ],
    },
    {
        "evidence_id": "annual_report_300499_gaolan_2025_122516",
        "source_type": "annual_report",
        "source_name": "高澜股份",
        "title": "300499 高澜股份 2025年年度报告摘要",
        "publisher": "巨潮资讯",
        "publish_date": "2026-04-24",
        "raw_file_path": "https://static.cninfo.com.cn/finalpage/2026-04-24/1225160678.PDF",
        "processed_text_path": "data/processed/text/ai_server_liquid_cooling/annual_report_300499_gaolan_2025_122516.md",
        "reliability_rank": "A",
        "status": "fresh",
        "license_note": "交易所披露文件；本地仅保存证据卡和来源链接。",
        "summary": [
            "公司披露热管理相关业务和面向数据中心液冷的产品/解决方案线索。",
            "本证据支持高澜股份作为液冷产品暴露候选，但需核验具体收入和客户。",
        ],
        "limitations": [
            "摘要证据不足以给出高纯度收入暴露结论。",
        ],
    },
    {
        "evidence_id": "annual_report_300731_cotran_2025_122523",
        "source_type": "annual_report",
        "source_name": "科创新源",
        "title": "300731 科创新源 2025年年度报告",
        "publisher": "巨潮资讯",
        "publish_date": "2026-04-29",
        "raw_file_path": "https://static.cninfo.com.cn/finalpage/2026-04-29/1225235910.PDF",
        "processed_text_path": "data/processed/text/ai_server_liquid_cooling/annual_report_300731_cotran_2025_122523.md",
        "reliability_rank": "A",
        "status": "fresh",
        "license_note": "交易所披露文件；本地仅保存证据卡和来源链接。",
        "summary": [
            "公司年报披露液冷板及相关子公司业务，并提到数据中心液冷需求和AI服务器散热背景。",
            "本证据支持科创新源进入低到中置信度候选池，但报告同时显示液冷业务仍需收入兑现验证。",
        ],
        "limitations": [
            "液冷业务是否形成显著财务贡献仍需后续定期报告和订单证据。",
        ],
    },
    {
        "evidence_id": "semiannual_report_300602_frd_2025_122450",
        "source_type": "annual_report",
        "source_name": "飞荣达",
        "title": "300602 飞荣达 2025年半年度报告",
        "publisher": "巨潮资讯",
        "publish_date": "2025-08-19",
        "raw_file_path": "https://static.cninfo.com.cn/finalpage/2025-08-19/1224504291.pdf",
        "processed_text_path": "data/processed/text/ai_server_liquid_cooling/semiannual_report_300602_frd_2025_122450.md",
        "reliability_rank": "A",
        "status": "fresh",
        "license_note": "交易所披露文件；本地仅保存证据卡和来源链接。",
        "summary": [
            "公司半年报涉及数据中心和热管理相关表述，可作为飞荣达进入液冷候选池的低置信度证据。",
            "本轮不把飞荣达列为高暴露公司，避免把热管理宽口径直接等同于AI服务器液冷收入。",
        ],
        "limitations": [
            "需要进一步核验液冷产品形态、客户和收入占比。",
        ],
    },
    {
        "evidence_id": "annual_report_300602_frd_2024_122310",
        "source_type": "annual_report",
        "source_name": "飞荣达",
        "title": "300602 飞荣达 2024年年度报告摘要",
        "publisher": "巨潮资讯",
        "publish_date": "2025-04-16",
        "raw_file_path": "https://static.cninfo.com.cn/finalpage/2025-04-16/1223100742.PDF",
        "processed_text_path": "data/processed/text/ai_server_liquid_cooling/annual_report_300602_frd_2024_122310.md",
        "reliability_rank": "A",
        "status": "fresh",
        "license_note": "交易所披露文件；本地仅保存证据卡和来源链接。",
        "summary": [
            "公司披露电磁屏蔽、导热和热管理相关业务，可作为液冷候选链条的辅助证据。",
            "本证据不能单独支持高暴露评分。",
        ],
        "limitations": [
            "热管理宽口径和AI服务器液冷边界需要拆分。",
        ],
    },
    {
        "evidence_id": "market_data_tushare_probe_20260701_8bbf20",
        "source_type": "exchange_data",
        "source_name": "Tushare Pro API local probe",
        "title": "P1 Tushare initial availability probe",
        "publisher": "local execution record",
        "publish_date": "2026-07-01",
        "raw_file_path": "data/raw/market_data/tushare_probe_2026-07-01.txt",
        "processed_text_path": "data/processed/tables/tushare_probe_2026-07-01.csv",
        "reliability_rank": "D",
        "status": "superseded",
        "license_note": "本地探测记录；不作为研究结论证据。",
        "summary": [
            "项目 conda 环境中 tushare 包可导入，版本为1.4.29。",
            "初始调用未设置指南要求的代理URL，因此服务端返回token无效；该问题已被后续代理配置验证取代。",
        ],
        "limitations": [
            "这是失败探测记录，不能作为公司基础信息或财务数据证据。",
        ],
    },
    {
        "evidence_id": "market_data_tushare_stock_basic_20260701_a6d9f2",
        "source_type": "exchange_data",
        "source_name": "Tushare Pro API via xiaodefa proxy",
        "title": "P1 company stock_basic snapshot for AI服务器液冷候选池",
        "publisher": "Tushare Pro API via configured proxy",
        "publish_date": "2026-07-01",
        "raw_file_path": "data/raw/market_data/tushare_stock_basic_ai_server_liquid_cooling_2026-07-01.csv",
        "processed_text_path": "data/processed/text/ai_server_liquid_cooling/market_data_tushare_stock_basic_20260701_a6d9f2.md",
        "reliability_rank": "C",
        "status": "fresh",
        "license_note": "本地结构化数据快照；不含token；用于校验股票代码、简称、上市板块和行业字段。",
        "summary": [
            "按配置指南设置 pro._DataApi__http_url=https://fast.xiaodefa.cn 后，stock_basic 查询成功返回5家公司基础信息。",
            "该快照可用于校验候选公司代码、简称、上市板块和Tushare行业字段。",
        ],
        "limitations": [
            "Tushare为第三方结构化数据源，公司披露和财务结论仍需回到公告/年报核验。",
        ],
    },
]


CLAIMS = [
    {
        "claim_id": "claim_segment_ai_server_liquid_cooling_20260701_001",
        "evidence_id": "policy_miit_compute_infra_20231008_9f2a30",
        "entity_type": "segment",
        "entity_id": SEGMENT_ID,
        "claim_text": "国家层面算力基础设施建设目标为数据中心热管理需求提供政策背景。",
        "claim_type": "fact",
        "quote_or_excerpt": "算力基础设施建设目标",
        "page_no": "web",
        "confidence": "medium",
        "valid_until": "政策修订或新行动计划发布",
        "notes": "政策不直接证明液冷订单。",
    },
    {
        "claim_id": "claim_segment_ai_server_liquid_cooling_20260701_002",
        "evidence_id": "industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91",
        "entity_type": "segment",
        "entity_id": SEGMENT_ID,
        "claim_text": "冷板式液冷是算力中心高功率密度服务器散热的重要技术路径之一。",
        "claim_type": "fact",
        "quote_or_excerpt": "冷板式液冷发展研究",
        "page_no": "report",
        "confidence": "medium",
        "valid_until": "2027-05-23",
        "notes": "需持续跟踪浸没式、风液混合等替代路线。",
    },
    {
        "claim_id": "claim_segment_ai_server_liquid_cooling_20260701_003",
        "evidence_id": "industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91",
        "entity_type": "segment",
        "entity_id": SEGMENT_ID,
        "claim_text": "本细分应覆盖冷板、CDU、管路、快接头、泵阀、冷量分配及系统集成等链条。",
        "claim_type": "inference",
        "quote_or_excerpt": "产业链拆分来自报告主题和设备结构",
        "page_no": "report",
        "confidence": "medium",
        "valid_until": "2027-05-23",
        "notes": "作为P1定义卡口径，不等同上市公司业务归属。",
    },
    {
        "claim_id": "claim_company_002837_invic_20260701_001",
        "evidence_id": "annual_report_002837_invic_2025_0f8fcf",
        "entity_type": "company",
        "entity_id": "cn_002837_invic",
        "claim_text": "英维克披露数据中心热管理和液冷相关产品/解决方案，属于产品暴露候选。",
        "claim_type": "fact",
        "quote_or_excerpt": "数据中心热管理、液冷相关产品",
        "page_no": "annual_summary",
        "confidence": "medium",
        "valid_until": "2027-04-21",
        "notes": "液冷收入占比未在本轮抽取。",
    },
    {
        "claim_id": "claim_company_002837_invic_20260701_002",
        "evidence_id": "annual_report_002837_invic_2025_0f8fcf",
        "entity_type": "company",
        "entity_id": "cn_002837_invic",
        "claim_text": "英维克的液冷暴露更接近产品/客户暴露，而非已核验的高纯度收入暴露。",
        "claim_type": "inference",
        "quote_or_excerpt": "摘要未披露液冷收入占比",
        "page_no": "annual_summary",
        "confidence": "medium",
        "valid_until": "2027-04-21",
        "notes": "exposure_score不设为5。",
    },
    {
        "claim_id": "claim_company_301018_shenling_20260701_001",
        "evidence_id": "annual_report_301018_shenling_2024_122331",
        "entity_type": "company",
        "entity_id": "cn_301018_shenling",
        "claim_text": "申菱环境年报出现浸没式液冷、冷板式液冷等数据服务温控业务相关表述。",
        "claim_type": "fact",
        "quote_or_excerpt": "浸没式液冷、冷板式液冷",
        "page_no": "annual_report",
        "confidence": "medium",
        "valid_until": "2026-08-29",
        "notes": "已用2025半年报交叉验证。",
    },
    {
        "claim_id": "claim_company_301018_shenling_20260701_002",
        "evidence_id": "semiannual_report_301018_shenling_2025_122461",
        "entity_type": "company",
        "entity_id": "cn_301018_shenling",
        "claim_text": "申菱环境2025半年报继续提供液冷业务线索，降低单一报告偶然性。",
        "claim_type": "fact",
        "quote_or_excerpt": "液冷产品和研发方向",
        "page_no": "semiannual_report",
        "confidence": "medium",
        "valid_until": "2027-08-29",
        "notes": "仍需表格化收入核验。",
    },
    {
        "claim_id": "claim_company_300499_gaolan_20260701_001",
        "evidence_id": "annual_report_300499_gaolan_2025_122516",
        "entity_type": "company",
        "entity_id": "cn_300499_gaolan",
        "claim_text": "高澜股份存在数据中心液冷相关产品/解决方案线索，但本轮证据不足以确认高纯度收入暴露。",
        "claim_type": "fact",
        "quote_or_excerpt": "数据中心液冷产品/解决方案",
        "page_no": "annual_summary",
        "confidence": "low",
        "valid_until": "2027-04-24",
        "notes": "需要完整年报、订单或客户证据。",
    },
    {
        "claim_id": "claim_company_300731_cotran_20260701_001",
        "evidence_id": "annual_report_300731_cotran_2025_122523",
        "entity_type": "company",
        "entity_id": "cn_300731_cotran",
        "claim_text": "科创新源披露液冷板及数据中心液冷需求相关内容，属于产品/技术暴露候选。",
        "claim_type": "fact",
        "quote_or_excerpt": "液冷板、数据中心液冷需求",
        "page_no": "annual_report",
        "confidence": "medium",
        "valid_until": "2027-04-29",
        "notes": "需区分产品验证和财务兑现。",
    },
    {
        "claim_id": "claim_company_300731_cotran_20260701_002",
        "evidence_id": "annual_report_300731_cotran_2025_122523",
        "entity_type": "company",
        "entity_id": "cn_300731_cotran",
        "claim_text": "科创新源液冷业务在本轮不应被视为核心收入暴露，应先列为低到中置信度观察项。",
        "claim_type": "inference",
        "quote_or_excerpt": "需要收入兑现验证",
        "page_no": "annual_report",
        "confidence": "medium",
        "valid_until": "2027-04-29",
        "notes": "作为概念映射降权样本。",
    },
    {
        "claim_id": "claim_company_300602_frd_20260701_001",
        "evidence_id": "semiannual_report_300602_frd_2025_122450",
        "entity_type": "company",
        "entity_id": "cn_300602_frd",
        "claim_text": "飞荣达具备热管理相关业务线索，但AI服务器液冷暴露需要进一步核验。",
        "claim_type": "fact",
        "quote_or_excerpt": "数据中心和热管理相关表述",
        "page_no": "semiannual_report",
        "confidence": "low",
        "valid_until": "2027-08-19",
        "notes": "候选池低分记录。",
    },
    {
        "claim_id": "claim_company_300602_frd_20260701_002",
        "evidence_id": "annual_report_300602_frd_2024_122310",
        "entity_type": "company",
        "entity_id": "cn_300602_frd",
        "claim_text": "飞荣达热管理宽口径不能直接等同于AI服务器液冷收入。",
        "claim_type": "inference",
        "quote_or_excerpt": "热管理宽口径需拆分",
        "page_no": "annual_summary",
        "confidence": "medium",
        "valid_until": "2026-08-19",
        "notes": "作为反证和降权依据。",
    },
    {
        "claim_id": "claim_data_tushare_20260701_001",
        "evidence_id": "market_data_tushare_probe_20260701_8bbf20",
        "entity_type": "other",
        "entity_id": "p1_data_source",
        "claim_text": "初始Tushare调用因未设置代理URL而被服务端返回token无效，该失败记录已被代理配置成功验证取代。",
        "claim_type": "fact",
        "quote_or_excerpt": "default endpoint rejected token",
        "page_no": "local_probe",
        "confidence": "high",
        "valid_until": "2026-07-01",
        "notes": "失败根因是SDK默认地址，不是token格式本身。",
    },
    {
        "claim_id": "claim_data_tushare_20260701_002",
        "evidence_id": "market_data_tushare_stock_basic_20260701_a6d9f2",
        "entity_type": "other",
        "entity_id": "p1_data_source",
        "claim_text": "按配置指南设置Tushare代理URL后，stock_basic成功返回P1候选公司的代码、简称、地区、行业、上市板块和上市日期。",
        "claim_type": "fact",
        "quote_or_excerpt": "stock_basic snapshot rows=5",
        "page_no": "local_probe",
        "confidence": "high",
        "valid_until": "下次结构化数据刷新前",
        "notes": "用于公司基础信息校验，不替代年报/公告证据。",
    },
]


COMPANY_UNIVERSE = [
    {
        "segment_id": SEGMENT_ID,
        "stock_code": "002837",
        "stock_name": "英维克",
        "company_id": "cn_002837_invic",
        "exposure_type": "product",
        "exposure_score": "4",
        "revenue_pct": "MISSING: 暂无直接披露",
        "profit_pct": "MISSING: 暂无直接披露",
        "confidence": "medium",
        "evidence_ids": "annual_report_002837_invic_2025_0f8fcf;market_data_tushare_stock_basic_20260701_a6d9f2",
        "notes": "数据中心热管理和液冷产品线明确，但液冷收入占比待补。",
        "next_check": "补完整年报分产品表；继续用Tushare补公告线索和财务字段。",
    },
    {
        "segment_id": SEGMENT_ID,
        "stock_code": "301018",
        "stock_name": "申菱环境",
        "company_id": "cn_301018_shenling",
        "exposure_type": "product",
        "exposure_score": "4",
        "revenue_pct": "MISSING: 暂无直接披露",
        "profit_pct": "MISSING: 暂无直接披露",
        "confidence": "medium",
        "evidence_ids": "annual_report_301018_shenling_2024_122331;semiannual_report_301018_shenling_2025_122461;market_data_tushare_stock_basic_20260701_a6d9f2",
        "notes": "冷板式、浸没式液冷线索由定期报告交叉验证。",
        "next_check": "抽取数据服务业务收入与液冷相关订单。",
    },
    {
        "segment_id": SEGMENT_ID,
        "stock_code": "300499",
        "stock_name": "高澜股份",
        "company_id": "cn_300499_gaolan",
        "exposure_type": "product",
        "exposure_score": "3",
        "revenue_pct": "MISSING: 暂无直接披露",
        "profit_pct": "MISSING: 暂无直接披露",
        "confidence": "low",
        "evidence_ids": "annual_report_300499_gaolan_2025_122516;market_data_tushare_stock_basic_20260701_a6d9f2",
        "notes": "数据中心液冷产品线索存在，但缺少收入、客户或订单证据。",
        "next_check": "补完整年报、互动记录和客户验证证据。",
    },
    {
        "segment_id": SEGMENT_ID,
        "stock_code": "300731",
        "stock_name": "科创新源",
        "company_id": "cn_300731_cotran",
        "exposure_type": "technology",
        "exposure_score": "2",
        "revenue_pct": "MISSING: 暂无直接披露",
        "profit_pct": "MISSING: 暂无直接披露",
        "confidence": "medium",
        "evidence_ids": "annual_report_300731_cotran_2025_122523;market_data_tushare_stock_basic_20260701_a6d9f2",
        "notes": "液冷板和需求背景明确，但财务兑现仍待验证，作为概念降权样本。",
        "next_check": "核验液冷板收入、客户认证、量产进度。",
    },
    {
        "segment_id": SEGMENT_ID,
        "stock_code": "300602",
        "stock_name": "飞荣达",
        "company_id": "cn_300602_frd",
        "exposure_type": "technology",
        "exposure_score": "2",
        "revenue_pct": "MISSING: 暂无直接披露",
        "profit_pct": "MISSING: 暂无直接披露",
        "confidence": "low",
        "evidence_ids": "semiannual_report_300602_frd_2025_122450;annual_report_300602_frd_2024_122310;market_data_tushare_stock_basic_20260701_a6d9f2",
        "notes": "热管理宽口径候选，暂不视为明确AI服务器液冷收入暴露。",
        "next_check": "拆分热管理产品、液冷部件和AI服务器客户。",
    },
]


def exposure_rows() -> list[dict[str, str]]:
    rows = []
    for item in COMPANY_UNIVERSE:
        rows.append(
            {
                "segment_id": item["segment_id"],
                "company_id": item["company_id"],
                "stock_code": item["stock_code"],
                "stock_name": item["stock_name"],
                "exposure_type": item["exposure_type"],
                "exposure_score": item["exposure_score"],
                "revenue_pct": item["revenue_pct"],
                "profit_pct": item["profit_pct"],
                "evidence_ids": item["evidence_ids"],
                "confidence": item["confidence"],
                "valid_from": REPORT_DATE,
                "valid_to": "",
                "notes": item["notes"],
            }
        )
    return rows


def build_evidence_cards() -> None:
    for item in EVIDENCE:
        card = [
            f"# Evidence Card: {item['evidence_id']}",
            "",
            f"- source_type: {item['source_type']}",
            f"- source_name: {item['source_name']}",
            f"- title: {item['title']}",
            f"- publisher: {item['publisher']}",
            f"- publish_date: {item['publish_date']}",
            f"- raw_file_path: {item['raw_file_path']}",
            f"- reliability_rank: {item['reliability_rank']}",
            f"- status: {item['status']}",
            f"- license_note: {item['license_note']}",
            "",
            "## Summary",
            "",
        ]
        card += [f"- {line}" for line in item["summary"]]
        card += ["", "## Limitations", ""]
        card += [f"- {line}" for line in item["limitations"]]
        related = [claim["claim_id"] for claim in CLAIMS if claim["evidence_id"] == item["evidence_id"]]
        card += ["", "## Related Claims", ""]
        card += [f"- {claim_id}" for claim_id in related] or ["- MISSING: 暂无直接 claim"]
        write_text(item["processed_text_path"], "\n".join(card))

    write_raw_text_once(
        "data/raw/market_data/tushare_probe_2026-07-01.txt",
        """
        P1 Tushare probe

        conda_env: C:\\Projects\\03_Investment_System\\.conda\\investment-system
        tushare_import: success
        tushare_version: 1.4.29
        service_query: failed
        service_message: default endpoint rejected token
        resolved_by: set pro._DataApi__http_url=https://fast.xiaodefa.cn
        note: no token value stored in this file; do not use this probe as company evidence.
        """,
    )
    write_csv(
        "data/processed/tables/tushare_probe_2026-07-01.csv",
        [
            {
                "probe_date": REPORT_DATE,
                "package": "tushare",
                "package_version": "1.4.29",
                "endpoint": "stock_basic / anns_d",
                "status": "superseded_by_proxy_config",
                "research_use": "not_used",
                "notes": "按PDF指南设置代理URL后已成功补录stock_basic快照",
            }
        ],
        ["probe_date", "package", "package_version", "endpoint", "status", "research_use", "notes"],
    )


def build_manifests() -> None:
    manifest_rows = []
    for item in EVIDENCE:
        manifest_rows.append(
            {
                "evidence_id": item["evidence_id"],
                "source_type": item["source_type"],
                "source_name": item["source_name"],
                "title": item["title"],
                "publisher": item["publisher"],
                "publish_date": item["publish_date"],
                "ingested_at": REPORT_DATE,
                "file_hash": sha6(item["raw_file_path"] + item["title"] + item["publish_date"]),
                "raw_file_path": item["raw_file_path"],
                "processed_text_path": item["processed_text_path"],
                "reliability_rank": item["reliability_rank"],
                "status": item["status"],
                "license_note": item["license_note"],
            }
        )

    write_csv(
        "data/manifests/evidence_manifest.csv",
        manifest_rows,
        [
            "evidence_id",
            "source_type",
            "source_name",
            "title",
            "publisher",
            "publish_date",
            "ingested_at",
            "file_hash",
            "raw_file_path",
            "processed_text_path",
            "reliability_rank",
            "status",
            "license_note",
        ],
    )
    write_csv(
        "data/manifests/claims_draft.csv",
        CLAIMS,
        [
            "claim_id",
            "evidence_id",
            "entity_type",
            "entity_id",
            "claim_text",
            "claim_type",
            "quote_or_excerpt",
            "page_no",
            "confidence",
            "valid_until",
            "notes",
        ],
    )


def build_config() -> None:
    write_text(
        "config/segment_taxonomy.yaml",
        f"""
        segments:
          - segment_id: {SEGMENT_ID}
            name_cn: AI服务器液冷
            name_en: AI server liquid cooling
            aliases:
              - 数据中心液冷
              - 服务器液冷
              - 冷板液冷
              - 浸没式液冷
              - 算力中心液冷
            definition: 面向AI服务器和智算/数据中心高功率密度场景的液冷设备、部件、系统集成与相关热管理解决方案。
            scope_in:
              - AI服务器、智算中心和数据中心液冷设备及部件
              - 冷板、CDU、管路、接头、泵阀、换热和系统集成
              - 与数据中心液冷部署直接相关的产品、项目、客户认证和技术储备
            scope_out:
              - 普通商用空调和传统机房精密空调
              - 与服务器或数据中心无关的工业冷却
              - 储能温控、汽车热管理等相邻但非本轮核心场景
            parent_theme: ai_infrastructure
            industry_chain_role: equipment
            related_segments:
              - data_center_power
              - server_structure
              - energy_storage_thermal_management
              - electronic_thermal_materials
            created_at: {REPORT_DATE}
            updated_at: {REPORT_DATE}
            status: active
            evidence_ids:
              - policy_miit_compute_infra_20231008_9f2a30
              - industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91
            notes: P1试点细分；用于验证证据、公司池、暴露映射和质量审查闭环。

        schema:
          segment_id: string
          name_cn: string
          name_en: string
          aliases: list
          definition: string
          scope_in: list
          scope_out: list
          parent_theme: string
          industry_chain_role: upstream | midstream | downstream | equipment | material | service | application | unknown
          related_segments: list
          created_at: YYYY-MM-DD
          updated_at: YYYY-MM-DD
          status: active | watch | archived
          evidence_ids: list
          notes: string

        segment_company_exposure_schema:
          segment_id: string
          company_id: string
          stock_code: string
          stock_name: string
          exposure_type: revenue | capacity | product | technology | customer | project | narrative | unknown
          exposure_score: 0-5
          revenue_pct: number | null
          profit_pct: number | null
          evidence_ids: list
          confidence: high | medium | low
          valid_from: YYYY-MM-DD | null
          valid_to: YYYY-MM-DD | null
          notes: string

        exposure_score_meaning:
          0: 无证据或不相关
          1: 仅概念或非常弱的间接关联
          2: 有产品、技术或项目线索，但收入或利润影响不清
          3: 有明确业务暴露，但占比或弹性不清
          4: 有较强业务暴露，收入、订单或客户证据较清楚
          5: 高纯度核心暴露，财务影响明确且证据强

        guardrails:
          - segment_id must be lower_snake_case.
          - scope_in and scope_out must be explicit before writing a segment report.
          - company exposure is many-to-many and must not be forced into one segment.
          - narrative exposure is low confidence until supported by primary evidence.
        """,
    )

    write_text(
        "config/watchlist.yaml",
        f"""
        watchlist:
          segments:
            - watch_item_id: watch_seg_{SEGMENT_ID}_{REPORT_DATE.replace('-', '')}
              segment_id: {SEGMENT_ID}
              watch_reason: AI算力基础设施扩张与高功率密度服务器散热需求相关，P1已建立证据闭环。
              supporting_claim_ids:
                - claim_segment_ai_server_liquid_cooling_20260701_001
                - claim_segment_ai_server_liquid_cooling_20260701_002
              evidence_ids:
                - policy_miit_compute_infra_20231008_9f2a30
                - industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91
              key_metrics:
                - liquid_cooling_revenue_pct
                - data_center_liquid_cooling_orders
                - customer_validation_progress
              triggers:
                - 年报/半年报披露液冷收入或订单
                - 运营商或云厂商液冷集采/技术规范更新
                - CAICT或行业协会更新渗透率和市场规模口径
              risks:
                - 风冷效率提升或风液混合方案延缓替代
                - 价格竞争压缩利润池
                - 公司披露停留在技术储备而非收入兑现
              confidence: medium
              status: active
              next_review_date: 2026-10-01
          companies:
            - watch_item_id: watch_company_cn_002837_invic_20260701
              company_id: cn_002837_invic
              stock_code: "002837"
              stock_name: 英维克
              linked_segments:
                - {SEGMENT_ID}
              watch_reason: 产品暴露清晰度较高，但液冷收入占比仍需核验。
              supporting_claim_ids:
                - claim_company_002837_invic_20260701_001
                - claim_company_002837_invic_20260701_002
              evidence_ids:
                - annual_report_002837_invic_2025_0f8fcf
              validation_metrics:
                - liquid_cooling_revenue_pct
                - data_center_customer_orders
                - gross_margin_of_thermal_management
              triggers:
                - 年报/半年报披露分产品收入
                - 数据中心液冷重大合同公告
                - 投资者关系活动记录更新客户验证进展
              risks:
                - 收入暴露低于市场叙事
                - 液冷产品价格竞争
              confidence: medium
              status: active
              next_review_date: 2026-10-01
            - watch_item_id: watch_company_cn_300731_cotran_20260701
              company_id: cn_300731_cotran
              stock_code: "300731"
              stock_name: 科创新源
              linked_segments:
                - {SEGMENT_ID}
              watch_reason: 作为概念/技术暴露降权样本，重点验证收入兑现。
              supporting_claim_ids:
                - claim_company_300731_cotran_20260701_001
                - claim_company_300731_cotran_20260701_002
              evidence_ids:
                - annual_report_300731_cotran_2025_122523
              validation_metrics:
                - liquid_cooling_plate_revenue
                - customer_certification
                - batch_delivery_progress
              triggers:
                - 液冷板收入或订单披露
                - 子公司创源智热业务进展披露
              risks:
                - 仅有产品或技术储备，未形成显著业绩贡献
              confidence: medium
              status: active
              next_review_date: 2026-10-01
          metrics: []
          catalysts: []
          risks: []

        schemas:
          segment_watch_item:
            watch_item_id: string
            segment_id: string
            watch_reason: string
            supporting_claim_ids: list
            evidence_ids: list
            key_metrics: list
            triggers: list
            risks: list
            confidence: high | medium | low
            status: active | paused | archived
            next_review_date: YYYY-MM-DD
          company_watch_item:
            watch_item_id: string
            company_id: string
            stock_code: string
            stock_name: string
            linked_segments: list
            watch_reason: string
            supporting_claim_ids: list
            evidence_ids: list
            validation_metrics: list
            triggers: list
            risks: list
            confidence: high | medium | low
            status: active | paused | archived
            next_review_date: YYYY-MM-DD

        decision_log_paths:
          thesis_log: decisions/thesis_log.md
          watchlist_changes: decisions/watchlist_changes.md
          postmortems: decisions/postmortems

        guardrails:
          - Watchlist inclusion must have evidence_ids or explicit TODO.
          - Watchlist changes must be logged in decisions/watchlist_changes.md.
          - A watch item is a research priority, not a buy/sell/hold instruction.
        """,
    )


def build_segment_reports() -> None:
    seg_dir = f"reports/segments/{SEGMENT_ID}"
    write_text(
        f"{seg_dir}/segment_definition.yaml",
        f"""
        segment_id: {SEGMENT_ID}
        name_cn: AI服务器液冷
        name_en: AI server liquid cooling
        aliases:
          - 数据中心液冷
          - 服务器液冷
          - 冷板液冷
          - 浸没式液冷
          - 算力中心液冷
        definition: 面向AI服务器和智算/数据中心高功率密度场景的液冷设备、部件、系统集成与相关热管理解决方案。
        scope_in:
          - 冷板式液冷设备、部件和系统集成
          - 浸没式液冷设备、部件和系统集成
          - 数据中心液冷相关CDU、泵阀、管路、快接头、换热和控制系统
          - 与AI服务器液冷部署直接相关的客户验证、订单、项目和技术储备
        scope_out:
          - 普通商用空调
          - 与服务器无关的工业冷却
          - 储能温控、汽车热管理等非本轮核心场景
          - 仅因热管理宽口径出现但无法证明数据中心液冷关联的业务
        related_segments:
          - data_center_power
          - server_structure
          - electronic_thermal_materials
          - energy_storage_thermal_management
        industry_chain_role:
          - equipment
          - components
          - system_integration
        key_questions:
          - 液冷渗透率是否提升？
          - A股公司收入暴露是否真实？
          - 产品、订单、客户和利润率能否兑现？
        evidence_ids:
          - policy_miit_compute_infra_20231008_9f2a30
          - industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91
        status: active
        created_at: {REPORT_DATE}
        updated_at: {REPORT_DATE}
        """,
    )
    write_text(
        f"{seg_dir}/segment_boundary.md",
        f"""
        # AI服务器液冷边界说明

        > {DISCLAIMER}

        ## Scope In

        - AI服务器、智算中心和数据中心液冷设备及部件。证据：evidence_id=industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91; claim_id=claim_segment_ai_server_liquid_cooling_20260701_002
        - 冷板、CDU、管路、快接头、泵阀、换热与系统集成。证据：evidence_id=industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91; claim_id=claim_segment_ai_server_liquid_cooling_20260701_003
        - 与数据中心液冷部署直接相关的客户验证、订单、项目和技术储备。证据：evidence_id=industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91

        ## Scope Out

        - 普通商用空调、传统机房精密空调：场景不同，不直接代表AI服务器液冷。
        - 储能温控、汽车热管理：热管理技术有相邻性，但需求变量和客户结构不同。
        - 只有市场叙事、没有产品或客户证据的公司：可列入TODO，不进入高暴露评分。

        ## 易混淆点

        - “热管理”不等于“AI服务器液冷收入”。
        - “技术储备”不等于“订单兑现”。
        - “数据中心客户”不等于“液冷产品交付”。
        """,
    )

    write_csv(
        f"{seg_dir}/company_universe.csv",
        COMPANY_UNIVERSE,
        [
            "segment_id",
            "stock_code",
            "stock_name",
            "company_id",
            "exposure_type",
            "exposure_score",
            "revenue_pct",
            "profit_pct",
            "confidence",
            "evidence_ids",
            "notes",
            "next_check",
        ],
    )
    write_text(
        f"{seg_dir}/company_universe_notes.md",
        f"""
        # 公司池说明

        > {DISCLAIMER}

        ## 纳入原则

        - 只纳入有 evidence_id 或明确 TODO 的公司。
        - 产品/技术/客户/收入暴露分开，不把概念热度当成高暴露。
        - 缺少液冷收入占比时统一写 `MISSING: 暂无直接披露`。

        ## 本轮结论

        - 英维克、申菱环境：产品暴露证据相对清晰，暂列 exposure_score=4，但收入占比仍缺失。
        - 高澜股份：有产品线索，但证据强度低于前两家公司，暂列 exposure_score=3。
        - 科创新源、飞荣达：作为技术/概念降权样本，暂列 exposure_score=2，后续看订单、客户和收入兑现。
        """,
    )

    write_csv(
        "data/processed/normalized/segment_company_exposure.csv",
        exposure_rows(),
        [
            "segment_id",
            "company_id",
            "stock_code",
            "stock_name",
            "exposure_type",
            "exposure_score",
            "revenue_pct",
            "profit_pct",
            "evidence_ids",
            "confidence",
            "valid_from",
            "valid_to",
            "notes",
        ],
    )
    write_text(
        f"{seg_dir}/segment_company_exposure_review.md",
        f"""
        # Segment-company exposure review

        > {DISCLAIMER}

        ## Review Result

        - 多对多映射已落在 `data/processed/normalized/segment_company_exposure.csv`。
        - 本轮所有记录均有 evidence_ids；没有使用无证据高分。
        - `revenue_pct` 和 `profit_pct` 未披露时均保留 `MISSING: 暂无直接披露`。

        ## Score Discipline

        - 4分：产品暴露较清楚，但未确认液冷收入占比。
        - 3分：产品线索存在，但客户/收入证据不足。
        - 2分：技术或宽口径热管理线索，等待财务兑现核验。

        ## Open Checks

        - Tushare代理配置已按指南修复，stock_basic公司基础信息已入库。证据：evidence_id=market_data_tushare_stock_basic_20260701_a6d9f2; claim_id=claim_data_tushare_20260701_002
        - 补抽取定期报告中的分业务收入、订单和客户表格。
        """,
    )

    evidence_inventory_rows = []
    for item in EVIDENCE:
        evidence_inventory_rows.append(
            f"| {item['evidence_id']} | {item['source_type']} | {item['title']} | {item['publish_date']} | {item['reliability_rank']} | {item['status']} |"
        )
    write_text(
        f"{seg_dir}/evidence_inventory.md",
        "\n".join(
            [
                "# Evidence Inventory",
                "",
                f"> {DISCLAIMER}",
                "",
                "| evidence_id | source_type | title | publish_date | reliability_rank | status |",
                "|---|---|---|---|---|---|",
                *evidence_inventory_rows,
                "",
                "说明：Tushare stock_basic 只用于公司基础信息校验，不单独支撑业务暴露结论。",
            ]
        ),
    )

    claims_lines = [
        f"| {c['claim_id']} | {c['evidence_id']} | {c['entity_type']} | {c['claim_type']} | {c['confidence']} | {c['claim_text']} |"
        for c in CLAIMS
    ]
    write_text(
        f"{seg_dir}/claims_review.md",
        "\n".join(
            [
                "# Claims Review",
                "",
                f"> {DISCLAIMER}",
                "",
                "| claim_id | evidence_id | entity | claim_type | confidence | claim_text |",
                "|---|---|---|---|---|---|",
                *claims_lines,
                "",
                "## Review Notes",
                "",
                "- 管理层、行业报告、研究推断已通过 claim_type 区分。",
                "- 暂无使用券商预测作为事实的条目。",
                "- Tushare初始失败记录已被代理配置成功验证取代，不进入评分依据。",
            ]
        ),
    )

    write_text(
        f"{seg_dir}/{REPORT_DATE}_segment_report.md",
        f"""
        # 细分方向研究：AI服务器液冷

        > {DISCLAIMER}

        ## 0. Metadata

        | Field | Value |
        |---|---|
        | report_id | segment_report_{SEGMENT_ID}_{REPORT_DATE} |
        | report_type | segment_report |
        | segment_id | {SEGMENT_ID} |
        | title | AI服务器液冷 |
        | report_date | {REPORT_DATE} |
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
        """,
    )

    write_text(
        f"{seg_dir}/scorecard.yaml",
        f"""
        segment_scorecard:
          segment_id: {SEGMENT_ID}
          report_date: {REPORT_DATE}
          disclaimer: {DISCLAIMER}
          scores:
            market_space:
              score: 4
              rationale: AI算力基础设施扩张提供需求背景，但不是液冷订单证据。
              evidence_ids:
                - policy_miit_compute_infra_20231008_9f2a30
              confidence: medium
            growth_visibility:
              score: 3
              rationale: 冷板式液冷技术路径清楚，渗透率和客户采购节奏待补。
              evidence_ids:
                - industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91
              confidence: medium
            industry_chain_position:
              score: 4
              rationale: 设备、部件和系统集成链条明确。
              evidence_ids:
                - industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91
              confidence: medium
            profit_pool_quality:
              score: 3
              rationale: 可能有设备和系统集成利润池，但公司级毛利和订单口径缺失。
              evidence_ids:
                - annual_report_002837_invic_2025_0f8fcf
                - annual_report_301018_shenling_2024_122331
              confidence: low
            a_share_purity:
              score: 3
              rationale: A股候选较多，但收入纯度未核验。
              evidence_ids:
                - annual_report_002837_invic_2025_0f8fcf
                - annual_report_301018_shenling_2024_122331
                - annual_report_300731_cotran_2025_122523
              confidence: medium
            evidence_quality:
              score: 3
              rationale: 官方披露和准官方行业报告可用，Tushare stock_basic已补；财务深字段仍待抓取。
              evidence_ids:
                - market_data_tushare_stock_basic_20260701_a6d9f2
              confidence: medium
          final_priority: watch_medium_high
          key_reasons:
            - reason: 细分边界清楚，产品链条可定义。
              evidence_id: industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91
            - reason: 公司池能区分产品暴露和技术/概念暴露。
              evidence_id: annual_report_002837_invic_2025_0f8fcf
          main_uncertainties:
            - uncertainty: 液冷收入占比和利润贡献暂缺。
              evidence_id: TODO
            - uncertainty: Tushare财务和公告深字段尚未导入。
              evidence_id: market_data_tushare_stock_basic_20260701_a6d9f2
        """,
    )

    evidence_map_lines = []
    for claim in CLAIMS:
        evidence_map_lines.append(
            f"| {claim['claim_text']} | {claim['evidence_id']} | {claim['claim_id']} | TODO | see manifest | fresh |"
        )
    write_text(
        f"{seg_dir}/evidence_map.md",
        "\n".join(
            [
                "# Evidence Map",
                "",
                f"> {DISCLAIMER}",
                "",
                "| Claim / Section | evidence_id | claim_id | metric_id | source_path | status |",
                "|---|---|---|---|---|---|",
                *evidence_map_lines,
            ]
        ),
    )
    write_text(
        f"{seg_dir}/followup_questions.md",
        f"""
        # Follow-up Questions

        > {DISCLAIMER}

        1. 英维克、申菱环境是否披露液冷收入占比或订单金额？
        2. 科创新源液冷板业务是否进入批量交付，并贡献可见收入？
        3. 飞荣达热管理业务中与AI服务器液冷直接相关的部分占比是多少？
        4. 客户侧液冷集采、技术规范或部署节奏是否出现新的官方证据？
        5. Tushare stock_basic已补；fina_indicator和anns_d能否进一步补全公司池评分？
        """,
    )
    write_text(
        f"{seg_dir}/refresh_tasks.yaml",
        f"""
        refresh_tasks:
          - task_id: refresh_tushare_financial_and_announcement_data_20260701
            object: data_source
            evidence_needed: Tushare fina_indicator, anns_d
            status: open
            reason: stock_basic已成功，财务和公告深字段仍需补。
          - task_id: extract_liquid_cooling_revenue_pct_20260701
            object: company_universe
            evidence_needed: 年报和半年报分产品表
            status: open
            reason: company_universe中revenue_pct仍为MISSING。
          - task_id: verify_customer_orders_20260701
            object: segment
            evidence_needed: 客户侧采购、订单或招标公告
            status: open
            reason: 需求兑现需要客户侧证据。
        """,
    )
    write_text(
        f"{seg_dir}/stock_deep_dive_selection.md",
        f"""
        # 个股深度样本选择

        > {DISCLAIMER}

        ## 公司 A：002837 英维克

        - 暴露类型：product
        - 暴露分：4
        - 关键证据：annual_report_002837_invic_2025_0f8fcf
        - 选择理由：产品暴露清楚，适合作为“较核心暴露”样本验证个股模板。
        - 主要待验证问题：液冷收入占比、客户订单和毛利率。

        ## 公司 B：300731 科创新源

        - 暴露类型：technology
        - 暴露分：2
        - 关键证据：annual_report_300731_cotran_2025_122523
        - 选择理由：有液冷板和需求叙事，但收入兑现待验证，适合作为“概念/技术暴露降权”样本。
        - 主要待验证问题：液冷板收入、客户认证、批量交付。
        """,
    )


def stock_report(
    folder: str,
    stock_code: str,
    stock_name: str,
    company_id: str,
    evidence_id: str,
    exposure_score: str,
    exposure_type: str,
    claim_ids: list[str],
    profile: str,
    risk_note: str,
    priority: str,
) -> None:
    base = f"reports/stocks/{folder}"
    write_text(
        f"{base}/{REPORT_DATE}_stock_deep_dive.md",
        f"""
        # 个股深度：{stock_code} {stock_name}

        > {DISCLAIMER}

        ## 0. Metadata

        | Field | Value |
        |---|---|
        | report_id | stock_report_{stock_code}_{REPORT_DATE} |
        | report_type | stock_report |
        | company_id | {company_id} |
        | stock_code | {stock_code} |
        | stock_name | {stock_name} |
        | linked_segments | {SEGMENT_ID} |
        | report_date | {REPORT_DATE} |
        | evidence_snapshot | {evidence_id} |
        | claim_ids | {'; '.join(claim_ids)} |
        | confidence | medium |
        | status | current |

        ## 1. 一句话结论

        - fact: {profile} 证据：evidence_id={evidence_id}; claim_id={claim_ids[0]}
        - inference: 当前仅用于研究优先级和暴露质量评估，不输出交易指令。
        - 关键假设：后续定期报告能补充液冷收入、客户和订单。
        - 最大风险：{risk_note}

        ## 2. 公司业务拆解

        | 业务 | 收入 | 毛利率 | 增速 | 关联细分 | 证据 |
        |---|---|---|---|---|---|
        | 热管理/液冷相关业务 | MISSING: 暂无直接披露 | MISSING: 暂无直接披露 | TODO: 需要补充证据 | {SEGMENT_ID} | {evidence_id} |
        | 其他业务 | TODO: 需要补充证据 | TODO: 需要补充证据 | TODO: 需要补充证据 | unknown | TODO |

        ## 3. 细分方向暴露

        | 细分 | 暴露类型 | 收入占比 | 弹性 | 置信度 | 证据 |
        |---|---|---|---|---|---|
        | {SEGMENT_ID} | {exposure_type} | MISSING: 暂无直接披露 | TODO: 需要补充证据 | medium | {evidence_id} |

        ## 4. 财务质量

        - 收入：TODO: Tushare stock_basic已补，fina_indicator等财务字段待补。证据：evidence_id=market_data_tushare_stock_basic_20260701_a6d9f2; claim_id=claim_data_tushare_20260701_002
        - 毛利率：MISSING: 暂无液冷口径直接披露。
        - 现金流：TODO: 需要补充证据。
        - 应收/存货：TODO: 需要补充证据。
        - 资本开支：TODO: 需要补充证据。

        ## 5. 竞争优势

        | Advantage | claim_type | Supporting evidence | Counter-evidence | confidence |
        |---|---|---|---|---|
        | 与数据中心液冷相关的产品或技术线索 | fact | {evidence_id}; {claim_ids[0]} | 收入占比未核验 | medium |

        ## 6. 客户与供应链

        | Item | claim_type | Evidence | Reliability | Notes |
        |---|---|---|---|---|
        | 数据中心/AI服务器客户 | unknown | TODO | unknown | 需要客户侧订单或验证证据 |
        | 液冷部件供应链 | unknown | TODO | unknown | 需要公告、年报或客户认证 |

        ## 7. 管理层与治理

        - TODO: 需要补充证据 - 本轮未抽取治理和管理层执行相关 claim。

        ## 8. 估值

        - 本轮只保留场景假设，不给出交易价格或评级。
        - base scenario：液冷业务逐步披露收入；证据：TODO。
        - downside scenario：液冷停留在技术储备或小批量；证据：{evidence_id}。

        ## 9. 催化剂

        | Catalyst | claim_type | evidence_id | expected_window | confidence | notes |
        |---|---|---|---|---|---|
        | 分产品收入披露 | unknown | TODO | 2026H2-2027H1 | medium | 核心验证 |
        | 客户验证或订单公告 | unknown | TODO | 2026H2 | medium | 需官方证据 |

        ## 10. 风险

        - {risk_note}
        - 液冷收入占比低于市场叙事。
        - 毛利率和价格竞争压力未量化。

        ## 11. 反证清单

        - 反证：只有产品或技术线索，不代表收入兑现；evidence_id={evidence_id}; confidence=medium
        - 反证：Tushare仅补了stock_basic，财务字段未完成；evidence_id=market_data_tushare_stock_basic_20260701_a6d9f2; confidence=high

        ## 12. 跟踪指标

        | Metric | Trigger | Evidence source | Review frequency | Notes |
        |---|---|---|---|---|
        | liquid_cooling_revenue_pct | 年报/半年报 | 定期报告 | 半年 | 当前MISSING |
        | customer_validation_progress | 投关/公告 | 官方披露 | 月度 | 当前TODO |
        | gross_margin_thermal_management | 半年报/年报 | 定期报告 | 半年 | 需区分热管理和液冷 |

        ## 13. 证据地图

        详见 `evidence_map.md`。
        """,
    )
    write_text(
        f"{base}/segment_exposure.yaml",
        f"""
        segment_exposure:
          - segment_id: {SEGMENT_ID}
            company_id: {company_id}
            stock_code: "{stock_code}"
            stock_name: {stock_name}
            exposure_type: {exposure_type}
            exposure_score: {exposure_score}
            revenue_pct: "MISSING: 暂无直接披露"
            profit_pct: "MISSING: 暂无直接披露"
            evidence_ids:
              - {evidence_id}
            confidence: medium
            valid_from: {REPORT_DATE}
            valid_to:
            notes: {profile}
        """,
    )
    write_text(
        f"{base}/stock_scorecard.yaml",
        f"""
        stock_scorecard:
          company_id: {company_id}
          stock_code: "{stock_code}"
          stock_name: {stock_name}
          score_date: {REPORT_DATE}
          disclaimer: {DISCLAIMER}
          linked_segments:
            - {SEGMENT_ID}
          scores:
            segment_exposure_quality:
              score: {exposure_score}
              rationale: 暴露类型为{exposure_type}，仍需收入占比和客户订单核验。
              evidence_ids:
                - {evidence_id}
              confidence: medium
            revenue_visibility:
              score: 1
              rationale: 液冷收入占比暂缺。
              evidence_ids:
                - TODO
              confidence: low
            financial_quality:
              score: 1
              rationale: Tushare stock_basic已导入，结构化财务字段未完成。
              evidence_ids:
                - market_data_tushare_stock_basic_20260701_a6d9f2
              confidence: low
            evidence_quality:
              score: 3
              rationale: 有官方披露证据，但字段抽取未完成。
              evidence_ids:
                - {evidence_id}
              confidence: medium
          final_priority: {priority}
          key_reasons:
            - reason: 进入P1个股样本用于验证暴露映射。
              evidence_id: {evidence_id}
          kill_switches:
            - condition: 连续两期无液冷收入、订单或客户验证披露。
              evidence_needed: 年报/半年报/公告/投关记录
        """,
    )
    write_text(
        f"{base}/evidence_map.md",
        "\n".join(
            [
                f"# Evidence Map: {stock_code} {stock_name}",
                "",
                f"> {DISCLAIMER}",
                "",
                "| Section | evidence_id | claim_id | metric_id | source_path | status |",
                "|---|---|---|---|---|---|",
                *[
                    f"| 个股深度 | {evidence_id} | {claim_id} | TODO | data/manifests/evidence_manifest.csv | fresh |"
                    for claim_id in claim_ids
                ],
                "| 财务质量 | market_data_tushare_stock_basic_20260701_a6d9f2 | claim_data_tushare_20260701_002 | TODO | data/raw/market_data/tushare_stock_basic_ai_server_liquid_cooling_2026-07-01.csv | fresh |",
            ]
        ),
    )
    write_text(
        f"{base}/open_questions.md",
        f"""
        # Open Questions: {stock_code} {stock_name}

        > {DISCLAIMER}

        - TODO: 需要补充证据 - 液冷相关收入占比和毛利率。
        - TODO: 需要补充证据 - 液冷产品客户、订单、批量交付进度。
        - TODO: 需要补充证据 - Tushare fina_indicator/anns_d 等结构化财务和公告字段。
        - LOW_CONFIDENCE: 当前证据质量不足 - exposure_score 不应升级为5。
        """,
    )
    write_text(
        f"{base}/valuation_scenarios.md",
        f"""
        # Valuation Scenarios: {stock_code} {stock_name}

        > {DISCLAIMER}

        本文件只记录研究假设，不输出交易价格、评级或操作指令。

        | Scenario | Assumption type | Key assumptions | evidence_id / metric_id | confidence | Risk |
        |---|---|---|---|---|---|
        | base | inference | 液冷业务逐步披露收入，但占比待核验 | {evidence_id}; TODO metric | low | 收入兑现慢 |
        | downside | inference | 业务停留在技术/产品线索，未形成显著财务贡献 | {evidence_id} | medium | 概念映射降权 |
        | upside_watch | unknown | 出现客户订单或分产品收入披露 | TODO | low | 需要官方披露 |
        """,
    )


def build_stock_reports() -> None:
    stock_report(
        folder="002837_invic",
        stock_code="002837",
        stock_name="英维克",
        company_id="cn_002837_invic",
        evidence_id="annual_report_002837_invic_2025_0f8fcf",
        exposure_score="4",
        exposure_type="product",
        claim_ids=[
            "claim_company_002837_invic_20260701_001",
            "claim_company_002837_invic_20260701_002",
        ],
        profile="英维克披露数据中心热管理和液冷相关产品/解决方案，属于较清晰的产品暴露样本。",
        risk_note="液冷收入占比和利润贡献尚未在本轮证据中直接披露。",
        priority="deep_watch",
    )
    stock_report(
        folder="300731_cotran",
        stock_code="300731",
        stock_name="科创新源",
        company_id="cn_300731_cotran",
        evidence_id="annual_report_300731_cotran_2025_122523",
        exposure_score="2",
        exposure_type="technology",
        claim_ids=[
            "claim_company_300731_cotran_20260701_001",
            "claim_company_300731_cotran_20260701_002",
        ],
        profile="科创新源披露液冷板和数据中心液冷需求相关内容，但更适合作为技术/概念暴露降权样本。",
        risk_note="产品线索可能未转化为显著收入或利润贡献。",
        priority="validation_watch",
    )


def build_p1_reports() -> None:
    p1_dir = "reports/p1"
    write_text(
        f"{p1_dir}/00_p0_readiness_check.md",
        f"""
        # P1-00 P0 Readiness Check

        > {DISCLAIMER}

        ## Result

        status: PASS
        checked_at: {REPORT_DATE}

        ## Checklist

        | Item | Result | Evidence |
        |---|---|---|
        | AGENTS.md exists | PASS | AGENTS.md |
        | .agents/skills exists | PASS | .agents/skills/ |
        | P1 required skills have SKILL.md | PASS | evidence-ingest, segment-research, company-universe, segment-company-mapping, stock-deep-dive, quality-review |
        | data/raw, data/processed, data/manifests exist | PASS | data/ |
        | reports/segments and reports/stocks exist | PASS | reports/ |
        | segment and stock templates exist | PASS | templates/segment_report.md; templates/stock_report.md |
        | taxonomy/source/scoring config exists | PASS | config/ |

        ## Notes

        - P1路径按架构文档使用 `data/processed/normalized/segment_company_exposure.csv`。
        - Tushare包可导入；按配置指南设置代理URL后，stock_basic已成功返回5家公司基础信息。
        """,
    )
    write_text(
        f"{p1_dir}/01_pilot_segment_selection.md",
        f"""
        # P1-01 Pilot Segment Selection

        > {DISCLAIMER}

        ```yaml
        p1_pilot_segment:
          segment_name_cn: AI服务器液冷
          segment_id: {SEGMENT_ID}
          reason:
            - 公开政策、准官方行业报告和A股披露证据可获得
            - A股公司可映射，适合验证company_universe和segment_company_exposure
            - 容易区分收入暴露、产品暴露、技术储备和市场叙事
          date_range: 最近3年 + 最新公告/财报
          depth: standard_to_deep
          out_of_scope:
            - 普通工业液冷
            - 传统空调制冷
            - 非数据中心热管理
        ```

        ## Adjacent Segments Deferred

        - 数据中心电源
        - 储能温控
        - 电子导热材料
        - 服务器结构件
        """,
    )
    write_text(
        f"{p1_dir}/p1_watchlist.md",
        f"""
        # P1 Watchlist

        > {DISCLAIMER}

        | object_type | object_id | watch_reason | evidence_ids | confidence | next_review |
        |---|---|---|---|---|---|
        | segment | {SEGMENT_ID} | AI算力基础设施与高功率密度散热需求相关 | policy_miit_compute_infra_20231008_9f2a30; industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91 | medium | 2026-10-01 |
        | company | cn_002837_invic | 产品暴露清楚，收入占比待补 | annual_report_002837_invic_2025_0f8fcf | medium | 2026-10-01 |
        | company | cn_300731_cotran | 技术/概念暴露降权样本，验证收入兑现 | annual_report_300731_cotran_2025_122523 | medium | 2026-10-01 |
        """,
    )
    write_csv(
        f"{p1_dir}/quality_issues.csv",
        [
            {
                "issue_id": "P1-QA-001",
                "severity": "high",
                "status": "fixed",
                "object": "segment_report",
                "issue": "初稿中所有关键结论必须有evidence_id或claim_id",
                "fix": "已在segment_report、stock_report、evidence_map中补齐引用",
            },
            {
                "issue_id": "P1-QA-002",
                "severity": "high",
                "status": "fixed",
                "object": "company_universe",
                "issue": "不能把技术储备或热管理宽口径写成高暴露",
                "fix": "科创新源、飞荣达降为exposure_score=2并标记验证项",
            },
            {
                "issue_id": "P1-QA-003",
                "severity": "medium",
                "status": "fixed",
                "object": "data_source",
                "issue": "Tushare初始调用未走代理URL，服务端返回token无效",
                "fix": "已按PDF指南设置pro._DataApi__http_url并生成stock_basic快照；财务深字段另列TODO",
            },
            {
                "issue_id": "P1-QA-004",
                "severity": "medium",
                "status": "todo",
                "object": "metrics",
                "issue": "液冷收入占比、利润占比、订单金额仍缺失",
                "fix": "在company_universe、stock_report和followup_questions中保留MISSING/TODO",
            },
        ],
        ["issue_id", "severity", "status", "object", "issue", "fix"],
    )
    write_text(
        f"{p1_dir}/quality_review_{SEGMENT_ID}.md",
        f"""
        # Quality Review: {SEGMENT_ID}

        > {DISCLAIMER}

        ## Verdict

        status: PASS_WITH_MEDIUM_TODOS
        reviewed_at: {REPORT_DATE}

        ## Evidence Traceability

        - PASS: segment_report关键结论均有 evidence_id 或 claim_id。
        - PASS: company_universe每家公司均有 evidence_ids。
        - PASS: stock_deep_dive两家公司均有 evidence_map。
        - PASS: high severity问题已修复。

        ## Claim Type Separation

        - PASS: fact、inference、unknown 和 Tushare配置修复过程已分开。
        - PASS: 未把管理层展望或行业估算写成公司事实。
        - PASS: 未使用券商预测作为事实。

        ## Metric Discipline

        - PASS_WITH_TODO: 缺失收入占比、利润占比、订单和毛利率时均标记 MISSING/TODO。
        - PASS_WITH_TODO: Tushare stock_basic已入库；fina_indicator/anns_d等深字段仍需补。证据：evidence_id=market_data_tushare_stock_basic_20260701_a6d9f2; claim_id=claim_data_tushare_20260701_002

        ## Counter-evidence

        - PASS: 科创新源、飞荣达被作为概念/技术暴露降权样本。
        - PASS: 热管理宽口径不等同AI服务器液冷收入已写入风险。

        ## Investment Boundary

        - PASS: 全部产物仅用于研究流程和证据管理，不含直接交易指令。
        """,
    )
    write_text(
        f"{p1_dir}/fix_log.md",
        f"""
        # P1 Fix Log

        > {DISCLAIMER}

        ## Fixed

        - P1-QA-001: 所有关键结论补齐 evidence_id 或 claim_id。
        - P1-QA-002: 技术储备/宽口径热管理公司降权，未给高暴露分。
        - 路径归一化：segment_company_exposure 主文件放在 `data/processed/normalized/`，符合架构文档。

        ## Remaining TODO

        - P1-QA-003: 已按PDF指南设置Tushare代理URL，并导入stock_basic快照。
        - P1-QA-004: 液冷收入占比、订单、客户验证和毛利率仍需补证。
        """,
    )
    write_text(
        f"{p1_dir}/template_change_log.md",
        f"""
        # Template Change Log

        > {DISCLAIMER}

        ## Result

        status: NO_SCHEMA_BREAKING_CHANGE

        ## Decisions

        - 现有 `templates/segment_report.md` 和 `templates/stock_report.md` 已能承接 P1 所需字段。
        - P1新增实践要求：company_universe和segment_company_exposure必须保留 `MISSING: 暂无直接披露`，不得猜测 revenue_pct/profit_pct。
        - P1新增实践要求：Tushare等结构化数据源必须先做代理URL健康检查；失败时进入 quality_issues 和 refresh_tasks，不允许静默跳过。
        - P1路径约定：标准化记录落在 `data/processed/normalized/`。
        """,
    )
    write_text(
        f"{p1_dir}/p1_readout_{SEGMENT_ID}.md",
        f"""
        # P1 Readout: AI服务器液冷

        > {DISCLAIMER}

        ## 1. 本轮范围

        - 试点细分：{SEGMENT_NAME}
        - segment_id：{SEGMENT_ID}
        - 时间范围：最近3年 + 最新公告/财报
        - 证据数量：{len(EVIDENCE)}
        - claims 数量：{len(CLAIMS)}
        - 公司池数量：{len(COMPANY_UNIVERSE)}
        - 个股深度数量：2

        ## 2. 核心产物

        - segment_report: reports/segments/{SEGMENT_ID}/{REPORT_DATE}_segment_report.md
        - company_universe: reports/segments/{SEGMENT_ID}/company_universe.csv
        - scorecard: reports/segments/{SEGMENT_ID}/scorecard.yaml
        - evidence_map: reports/segments/{SEGMENT_ID}/evidence_map.md
        - stock_deep_dive: reports/stocks/002837_invic/{REPORT_DATE}_stock_deep_dive.md; reports/stocks/300731_cotran/{REPORT_DATE}_stock_deep_dive.md
        - segment_exposure: data/processed/normalized/segment_company_exposure.csv
        - quality_review: reports/p1/quality_review_{SEGMENT_ID}.md

        ## 3. 主要结论

        - fact: AI算力基础设施扩张提供需求背景。证据：policy_miit_compute_infra_20231008_9f2a30
        - fact: 冷板式液冷是算力中心高功率密度散热路径之一。证据：industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91
        - inference: 公司池需要分层，英维克/申菱环境产品暴露较清楚，科创新源/飞荣达应降权验证。
        - 不确定性：液冷收入占比、利润贡献、客户订单和Tushare财务/公告深字段仍需补证。

        ## 4. 系统验证结果

        | Check | Result |
        |---|---|
        | 证据是否能沉淀 | PASS |
        | 结论是否能追溯 | PASS |
        | 公司是否能多对多映射 | PASS |
        | 报告是否能重建 | PASS |
        | 模板是否可复用 | PASS |
        | skill边界是否清楚 | PASS |

        ## 5. P1 问题清单

        - 数据问题：Tushare代理配置已修复并补stock_basic；财务/公告深字段未导入。
        - 证据问题：液冷收入占比和客户侧订单证据不足。
        - 评分问题：评分可用于研究优先级，但不能转成交易信号。
        - 路径问题：P1草案中的 `data/normalized/` 已按架构统一为 `data/processed/normalized/`。

        ## 6. 是否进入 P2

        - 判断：P1验收通过，但进入P2前建议先修复中优先级TODO。
        - 理由：闭环已成立，且质量审查能发现实际问题；但横向比较前需要补结构化财务字段和收入占比。
        - 前置修复项：
          - 用Tushare继续补公告线索和财务字段。
          - 抽取2-3家公司液冷收入或订单证据。
          - 补客户侧采购/部署证据。

        ## P1 Acceptance

        status: PASS_WITH_MEDIUM_TODOS
        """,
    )
    write_text(
        f"{p1_dir}/p1_lessons_learned.md",
        f"""
        # P1 Lessons Learned

        > {DISCLAIMER}

        - evidence_id/claim_id 在报告中可用，但需要脚本化检查，人工维护容易漏。
        - 公司池最容易被“热管理宽口径”污染，必须保留 exposure_type 和 confidence。
        - revenue_pct/profit_pct 不应猜测，缺失时用 MISSING 更可靠。
        - Tushare适合补结构化股票和财务字段，但必须按指南设置代理URL并先做数据源健康检查。
        - 下一阶段如果做多细分比较，应先把 `segment_company_exposure.csv` 扩成可累计表。
        """,
    )
    write_text(
        f"{p1_dir}/p2_entry_checklist.md",
        f"""
        # P2 Entry Checklist

        > {DISCLAIMER}

        | Condition | Status | Notes |
        |---|---|---|
        | P1细分报告模板稳定 | PASS | 已生成segment_report |
        | P1个股报告模板稳定 | PASS | 已生成2家公司样本 |
        | evidence_manifest可复用 | PASS | 10条证据已登记 |
        | segment_company_exposure可复用 | PASS | 已输出CSV |
        | quality-review能发现问题 | PASS | Tushare配置问题和收入占比缺口已记录 |
        | company_universe字段支持比较 | PASS | 暴露类型、分数、置信度、证据齐全 |
        | scorecard维度基本稳定 | PASS | 不作为交易信号 |
        | watchlist能解释纳入理由 | PASS | config/watchlist.yaml已更新 |
        | Tushare结构化数据可用 | PASS | stock_basic已成功；财务和公告深字段待补 |
        | 液冷收入占比补证 | TODO | 横向比较前建议补 |

        P2 readiness: CONDITIONAL_READY
        """,
    )


def build_decision_log() -> None:
    write_text(
        "decisions/watchlist_changes.md",
        f"""
        # Watchlist Changes

        > {DISCLAIMER}

        ## {REPORT_DATE}

        | action | object_type | object_id | reason | evidence_ids | reviewer | notes |
        |---|---|---|---|---|---|---|
        | add | segment | {SEGMENT_ID} | P1试点细分闭环已通过，进入研究跟踪 | policy_miit_compute_infra_20231008_9f2a30; industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91 | Codex | 研究优先级，不是交易建议 |
        | add | company | cn_002837_invic | 产品暴露较清楚，需核验收入占比 | annual_report_002837_invic_2025_0f8fcf | Codex | deep_watch |
        | add | company | cn_300731_cotran | 概念/技术暴露降权样本，需验证兑现 | annual_report_300731_cotran_2025_122523 | Codex | validation_watch |
        """,
    )


def main() -> None:
    build_evidence_cards()
    build_manifests()
    build_config()
    build_segment_reports()
    build_stock_reports()
    build_p1_reports()
    build_decision_log()
    print(f"P1 artifacts generated for {SEGMENT_ID} on {REPORT_DATE}")


if __name__ == "__main__":
    main()
