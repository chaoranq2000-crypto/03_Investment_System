"""Deterministic reader report and traceability appendix writer."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import yaml

from src.report.r5_metric_formatter import cny, eps, multiple, pct


def _section(payloads: dict[str, Any], section_id: str) -> dict[str, Any]:
    return next(x for x in payloads["sections"] if x["section_id"] == section_id)


def _paragraph(section: dict[str, Any], refs: str) -> str:
    return f"{section['one_sentence_judgment']} {refs}"


def build_reader_report(payloads: dict[str, Any], bridge: dict[str, Any], valuation: dict[str, Any]) -> str:
    calc = payloads["calculation_ledger"]
    financial = _section(payloads, "financial_history_and_cashflow_quality")
    facts = financial["material_facts"]
    revenues, profits, ocfs = facts[0], facts[1], facts[2]
    business = _section(payloads, "business_breakdown_and_economics")["trend_calculations"]
    by_name = {x["name"]: x for x in business}
    room = by_name["机房温控节能产品"]
    cabinet = by_name["机柜温控节能产品"]
    snap = valuation["dated_snapshot"]
    lines = [
        "# 英维克（002837）读者型研究报告候选稿",
        "",
        "**数据截止日：2026-07-10｜报告层级：研究候选稿｜人工复核：待进行**",
        "",
        "> 本文用于证据约束下的公司研究，不构成投资建议。事实、估计与推断在文中分别说明；完整来源与计算口径见配套追溯附录。",
        "",
        "## 一、核心研究观点",
        "",
        _paragraph(_section(payloads, "executive_summary"), "[E1][E2][E3][E8]"),
        "",
        "研究矛盾很清楚：一边是2023—2025年收入扩张和算力热管理产品覆盖，另一边是2026年一季度利润、毛利率与经营现金流承压。市场定价已经把相当一部分未来修复写入当前倍数，因此后续判断不能只看收入增长，还要同时验证毛利率、费用纪律和现金转换。",
        "",
        "## 二、公司背景与研究边界",
        "",
        _paragraph(_section(payloads, "company_context_and_scope"), "[E1][E4]"),
        "",
        "公司披露的产品链覆盖冷板、快速接头、分配单元、机柜、工质与冷源，并延伸至交付和服务环节。这个覆盖证明其进入了算力散热价值链，但年报的财务口径主要是机房温控、机柜温控等宽产品线。由于液冷业务没有单列收入、毛利率和利润贡献，本文不对其独立盈利规模作估算，也不把公司整体增长归因于液冷。",
        "",
        "## 三、财务历史与现金流质量",
        "",
        _paragraph(financial, "[E2][E3]"),
        "",
        "| 指标（亿元） | 2023A | 2024A | 2025A | 2026Q1 |",
        "|---|---:|---:|---:|---:|",
        f"| 营业收入 | {cny(revenues['2023A'])} | {cny(revenues['2024A'])} | {cny(revenues['2025A'])} | {cny(revenues['2026Q1'])} |",
        f"| 归母净利润 | {cny(profits['2023A'])} | {cny(profits['2024A'])} | {cny(profits['2025A'])} | {cny(profits['2026Q1'])} |",
        f"| 经营现金流 | {cny(ocfs['2023A'])} | {cny(ocfs['2024A'])} | {cny(ocfs['2025A'])} | {cny(ocfs['2026Q1'])} |",
        "",
        f"2023—2025年收入复合增速为{pct(calc['revenue_cagr_2023_2025_pct'])}，2024年和2025年收入分别增长{pct(calc['revenue_growth_2024_pct'])}和{pct(calc['revenue_growth_2025_pct'])}；同期归母净利润分别增长{pct(calc['net_profit_growth_2024_pct'])}和{pct(calc['net_profit_growth_2025_pct'])}。但经营现金流/归母净利润从2023年的{pct(calc['ocf_to_profit_pct']['2023A'])}降至2025年的{pct(calc['ocf_to_profit_pct']['2025A'])}。2026年一季度收入同比增长26.0%，归母净利润同比下降82.0%，经营现金流为负。背离是已确认事实，具体驱动尚无充分证据，不能简单归因于季节性或一次性因素。[E2][E3]",
        "",
        "这使下一阶段验证从“有没有增长”转向“增长能否形成利润和现金”。应重点跟踪毛利率、应收与存货、合同负债、经营现金流以及费用率；单季度可能受营运资金扰动，但在连续季度改善出现前，现金转化仍是反证。",
        "",
        "## 四、业务拆分与细分经济性",
        "",
        _paragraph(_section(payloads, "business_breakdown_and_economics"), "[E4]"),
        "",
        "| 2025年宽产品线 | 收入占比 | 毛利率 |",
        "|---|---:|---:|",
        f"| 机房温控节能产品 | {pct(room['revenue_share_pct'], 2)} | {pct(room['gross_margin_pct'], 2)} |",
        f"| 机柜温控节能产品 | {pct(cabinet['revenue_share_pct'], 2)} | {pct(cabinet['gross_margin_pct'], 2)} |",
        "",
        f"两条主产品线合计占收入{pct(room['revenue_share_pct'] + cabinet['revenue_share_pct'], 2)}，毛利率相差{pct(abs(room['gross_margin_pct'] - cabinet['gross_margin_pct']), 2)}。这说明公司当前利润基础仍由宽口径温控主业决定。液冷产品可能分布在这些口径中，但披露不足以把其中任何比例认定为液冷独立贡献；低占比产品的毛利率也没有完整单列。[E4]",
        "",
        "## 五、行业结构与竞争",
        "",
        _paragraph(_section(payloads, "industry_structure_and_competition"), "[E5][E6]"),
        "",
        "发行人年报将高功率芯片带来的热密度上升和能效要求列为液冷导入驱动，并披露从部件、系统到交付服务的链条覆盖。其经济含义是：链条完整度可能提高方案协同和客户交付能力，但也增加研发、制造和服务执行要求。与此同时，2025年中报披露竞争加剧导致机房温控毛利率同比下降，说明需求扩张并不自动等于利润扩张。[E5][E6]",
        "",
        "这部分证据主要来自发行人披露，能够支持需求逻辑、公司定位和竞争压力，但不能替代独立市场规模或份额统计。为避免混用定义，本文不采用口径不一致的市场规模估计。后续以同口径产品收入、毛利率、订单和同业披露验证竞争力。",
        "",
        "## 六、预测与情景",
        "",
        _paragraph(_section(payloads, "forecast_and_scenarios"), "[E7]"),
        "",
        "基准模型从2025年公司整体财务出发，以2026年一季度较低毛利率和较高费用率作为约束，随后只做渐进修复。模型不直接年化一季度利润，也不建立未披露的液冷收入线；股本暂按2026年7月10日快照保持不变。税负、财务收支、少数股东损益及其他项目合并为显式桥接项，避免把其误写成单一经营原因。",
        "",
        "| 基准情景 | 营业收入（亿元） | 收入增速 | 毛利率 | 归母净利润（亿元） | 每股收益（元） |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    prior = bridge["historical_anchor"]["revenue"]
    for row in bridge["base_case_bridge"]:
        growth = (row["revenue"] / prior - 1) * 100
        lines.append(f"| {row['period']} | {cny(row['revenue'])} | {pct(growth)} | {pct(row['gross_margin_pct'])} | {cny(row['net_profit_attributable'])} | {eps(row['eps'], 3)} |")
        prior = row["revenue"]
    lines += [
        "",
        "上行情景以更高收入增速和更快利润率恢复为核心，下行情景以较慢收入增长和较低毛利率为核心；最关键的两个敏感变量是收入增速与毛利率。由于一季度弱盈利的驱动尚未核实，三种情景的差距应被理解为模型不确定性，而不是结果概率。[E7]",
        "",
        "## 七、估值与市场预期",
        "",
        _paragraph(_section(payloads, "valuation_and_market_expectations"), "[E8][E9]"),
        "",
        f"截至2026年7月10日，收盘价为{snap['price_cny']:.2f}元，总市值约{cny(snap['market_cap_cny'])}亿元，市盈率为{multiple(snap['pe_ttm'])}，市净率为{multiple(snap['pb'])}，市销率为{multiple(snap['ps_ttm'])}。市盈率和市销率均使用滚动口径；远期市盈率使用本文基准情景每股收益，日期和分母不可互换。[E8]",
        "",
        "| 基准情景 | 每股收益（元） | 对应远期市盈率 |",
        "|---|---:|---:|",
    ]
    for row in valuation["scenario_context"]:
        lines.append(f"| {row['period']} | {eps(row['eps'], 3)} | {multiple(row['forward_pe'])} |")
    lines += [
        "",
        "当前滚动市盈率约194.2倍，而基准情景下2026—2028年远期市盈率仍约995.8倍、291.8倍和161.5倍。这意味着市场价格要求未来收入增长最终转化为显著的利润率和每股收益修复。两家产品暴露同业的业务组合与盈利波动不同，只能作为低置信度参照；现金流折现缺少已审阅的自由现金流、折现率和终值输入，分部估值又缺少液冷独立经济性，因此两种方法都不输出伪精确结果。[E8][E9]",
        "",
        "## 八、有日期的公司事件",
        "",
        "2025年半年度报告于2025年8月19日披露；2025年年度报告和2026年一季度报告于2026年4月21日披露。前者提供竞争与产品进展信息，后两者构成当前财务和业务口径的主要更新。下一份官方定期报告是验证毛利率、现金流和液冷披露口径的关键节点，具体发布日期以交易所公告为准。[E1][E3][E6]",
        "",
        "## 九、风险、反证与观察条件",
        "",
        _paragraph(_section(payloads, "risks_counterevidence_and_watchpoints"), "[E2][E3][E5][E8]"),
        "",
        "- 盈利质量：收入增长若继续伴随利润率和现金转换下降，增长含金量将削弱。[E2][E3]",
        "- 竞争压力：行业需求扩张可能被价格竞争、交付成本或产品结构变化抵消。[E5][E6]",
        "- 披露边界：液冷独立经济性未单列，产品覆盖不能替代收入和利润证据。[E1][E4]",
        "- 预期风险：当前倍数对盈利修复高度敏感，修复节奏低于模型会放大估值压力。[E8][E9]",
        "",
        "反证同样需要保留：公司宽口径收入仍保持较快增长，产品链覆盖较完整；若后续季度毛利率回升、经营现金流转正且分产品披露增强，当前谨慎判断应随证据更新。",
        "",
        "## 十、研究结论与跟踪清单",
        "",
        _paragraph(_section(payloads, "research_conclusion"), "[E1][E3][E4][E7][E8]"),
        "",
        "后续更新按以下顺序验证：第一，季度毛利率和费用率能否稳定；第二，经营现金流能否与利润重新匹配；第三，液冷是否出现可核验的独立收入、毛利率或订单口径；第四，实际结果与三种情景的偏差；第五，在同一日期和分母口径下复核估值。技术走势与情绪因缺少经过审阅的历史序列和清晰定义，本稿不作叙述。",
        "",
        "---",
        "",
        "人工复核仍待完成；本稿不进入样例质量或横向比较阶段。",
    ]
    return "\n".join(lines) + "\n"


def build_traceability_appendix() -> dict[str, Any]:
    annual = "ev_annual_report_002837_20260421_2cbfc5"
    interim = "ev_interim_report_002837_20250819_47054e"
    q1 = "ev_quarterly_report_002837_20260421_2f00c7"
    market = "ev_structured_market_data_002837_20260710_eb0c08"
    records = [
        ("E1", "fact_and_management_comment", "公司业务范围、液冷产品链与披露边界", "2025A", None, [annual], "data/processed/text/002837/cninfo_2025_annual_report_full_002837_2026-04-21.txt", "direct_review", "high", "竞争优势表述来自管理层，液冷独立经济性未单列", "accepted", "current"),
        ("E2", "fact_and_inference", "2023—2025年财务历史、现金转换与趋势计算", "2023A-2025A", "CNY/pct", [annual], "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_financial_history_candidate.yaml", "reported_values_and_arithmetic", "high", "公司整体口径，不归因于液冷", "accepted", "current"),
        ("E3", "fact_and_inference", "2026年一季度收入利润背离及现金流", "2026Q1", "CNY/pct", [q1], "data/processed/text/002837/szse_2026_q1_report_002837_2026-04-21.txt", "reported_values_and_arithmetic", "high", "背离原因尚未验证", "accepted", "current"),
        ("E4", "fact_and_inference", "2025年宽产品线收入占比、毛利率与液冷边界", "2025A", "CNY/pct", [annual], "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_business_breakdown_candidate.yaml", "reported_values_and_arithmetic", "high", "低占比产品毛利率及液冷独立口径未披露", "accepted", "current"),
        ("E5", "management_comment_and_fact", "热密度与能效驱动、端到端价值链定位", "2025A", None, [annual], "data/processed/text/002837/cninfo_2025_annual_report_full_002837_2026-04-21.txt", "issuer_disclosure_review", "medium", "缺少独立市场规模和份额交叉验证", "accepted_with_issuer_boundary", "current"),
        ("E6", "management_comment", "竞争加剧与机房温控毛利率压力", "2025H1", "pct", [interim], "data/processed/text/002837/cninfo_2025_interim_report_full_002837_2025-08-19.txt", "issuer_disclosure_review", "medium", "具体竞争强度和同业份额未独立验证", "accepted_with_issuer_boundary", "current"),
        ("E7", "estimate", "2026—2028年公司整体预测桥、情景与敏感性", "2026E-2028E", "CNY/pct", [annual, q1, market], "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle6_forecast_bridge.yaml", "scenario_model_with_reconciliation", "medium", "不是管理层指引或一致预期；一季度异常原因未验证", "accepted_model_input", "current"),
        ("E8", "fact_and_estimate", "2026年7月10日市场快照与远期倍数", "2026-07-10", "CNY/multiple", [market], "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle6_valuation_reasoning_pack.yaml", "same_date_denominator_control", "high_for_snapshot_medium_for_forward", "远期倍数依赖本文情景", "accepted", "current"),
        ("E9", "inference", "市场隐含预期、同业比较限制与方法适用性", "2026-07-10", "multiple", [market], "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle6_valuation_reasoning_pack.yaml", "method_eligibility_and_peer_context", "low_to_medium", "同业仅两家且业务结构不同；无目标价", "accepted_with_limitations", "current"),
    ]
    return {
        "artifact_type": "R5_stock_research_report_traceability_v2", "schema_version": "v0.1", "workflow_id": "wf_20260703_stock_first_002837_invic", "stock_code": "002837", "cutoff_date": "2026-07-10",
        "records": [{"display_reference_id": x[0], "claim_type": x[1], "claim_text_digest": hashlib.sha256(x[2].encode()).hexdigest(), "claim_summary": x[2], "period": x[3], "unit": x[4], "raw_evidence_ids": x[5], "source_path": x[6], "method": x[7], "confidence": x[8], "limitation": x[9], "reviewer_state": x[10], "conflict_or_staleness_status": x[11]} for x in records],
        "human_review_status": "pending", "sample_quality_report_allowed": False, "p2_allowed": False,
    }


def validate_citations(report: str, appendix: dict[str, Any]) -> list[str]:
    used = set(re.findall(r"\[(E[1-9][0-9]*)\]", report))
    counts: dict[str, int] = {}
    for record in appendix["records"]:
        ref = record["display_reference_id"]
        counts[ref] = counts.get(ref, 0) + 1
    return sorted(ref for ref in used if counts.get(ref) != 1) + sorted(ref for ref, count in counts.items() if count != 1)


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))
