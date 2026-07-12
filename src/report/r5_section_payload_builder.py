"""Build deterministic analytical payloads from reviewed R5 Bundle 5 assets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Inputs:
    financial: dict[str, Any]
    business: dict[str, Any]
    forecast: dict[str, Any]
    valuation: dict[str, Any]
    coverage: dict[str, Any]
    forecast_bridge: dict[str, Any]
    valuation_reasoning: dict[str, Any]


def _load(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_inputs(run_dir: Path) -> Inputs:
    names = {
        "financial": "R5_bundle5_financial_history_candidate.yaml",
        "business": "R5_bundle5_business_breakdown_candidate.yaml",
        "forecast": "R5_bundle5_forecast_model_candidate.yaml",
        "valuation": "R5_bundle5_valuation_pack_candidate.yaml",
        "coverage": "R5_bundle6_coverage_inventory.yaml",
        "forecast_bridge": "R5_bundle6_forecast_bridge.yaml",
        "valuation_reasoning": "R5_bundle6_valuation_reasoning_pack.yaml",
    }
    return Inputs(**{key: _load(run_dir / name) for key, name in names.items()})


def _metric(rows: list[dict[str, Any]], name: str, period: str) -> float:
    for row in rows:
        if row.get("metric_name") == name and row.get("period") == period:
            return float(row["value"])
    raise KeyError(f"metric not found: {name}/{period}")


def _growth(current: float, previous: float) -> float:
    return (current / previous - 1.0) * 100.0


def _payload(section_id: str, title: str, judgment: str, refs: list[str], **kwargs: Any) -> dict[str, Any]:
    payload = {
        "section_id": section_id,
        "title": title,
        "one_sentence_judgment": judgment,
        "material_facts": kwargs.get("material_facts", []),
        "trend_calculations": kwargs.get("trend_calculations", []),
        "causal_chain": kwargs.get("causal_chain", []),
        "economic_implications": kwargs.get("economic_implications", []),
        "counterpoints": kwargs.get("counterpoints", []),
        "uncertainties": kwargs.get("uncertainties", []),
        "watchpoints": kwargs.get("watchpoints", []),
        "display_references": refs,
        "readiness_for_reader_report": "ready",
    }
    required = [payload["one_sentence_judgment"], payload["material_facts"], payload["economic_implications"], payload["uncertainties"], payload["watchpoints"], refs]
    if any(not value for value in required):
        raise ValueError(f"section {section_id} is not analytically complete")
    return payload


def build_payloads(inputs: Inputs) -> dict[str, Any]:
    income = inputs.financial["income_statement"]
    cashflow = inputs.financial["cashflow_statement"]
    revenue = {p: _metric(income, "revenue", p) for p in ("2023A", "2024A", "2025A", "2026Q1")}
    profit = {p: _metric(income, "net_profit_attributable", p) for p in revenue}
    ocf = {p: _metric(cashflow, "operating_cashflow", p) for p in revenue}
    calc = {
        "revenue_cagr_2023_2025_pct": (revenue["2025A"] / revenue["2023A"]) ** 0.5 * 100 - 100,
        "revenue_growth_2024_pct": _growth(revenue["2024A"], revenue["2023A"]),
        "revenue_growth_2025_pct": _growth(revenue["2025A"], revenue["2024A"]),
        "net_profit_growth_2024_pct": _growth(profit["2024A"], profit["2023A"]),
        "net_profit_growth_2025_pct": _growth(profit["2025A"], profit["2024A"]),
        "net_margin_pct": {p: profit[p] / revenue[p] * 100 for p in revenue},
        "ocf_to_profit_pct": {p: ocf[p] / profit[p] * 100 for p in revenue},
        "ocf_to_revenue_pct": {p: ocf[p] / revenue[p] * 100 for p in revenue},
        "q1_revenue_yoy_pct": 26.03,
        "q1_profit_yoy_pct": -81.97,
    }
    lines = inputs.business["business_lines"]
    broad = [line for line in lines if line.get("revenue", {}).get("value") is not None]
    business_calc = [{"name": x["reported_name"], "revenue_share_pct": x["revenue_pct"]["value"], "gross_margin_pct": x["gross_margin"]["value"]} for x in broad]
    forecast_table = inputs.forecast["forecast_table"]["base_case"]
    forecast_calc = []
    prior_revenue = revenue["2025A"]
    prior_eps = _metric(inputs.financial["key_metrics"], "basic_eps", "2025A")
    for period in ("2026E", "2027E", "2028E"):
        row = forecast_table[period]
        forecast_calc.append({
            "period": period,
            "revenue": row["revenue"]["value"],
            "revenue_growth_pct": _growth(row["revenue"]["value"], prior_revenue),
            "gross_margin_pct": row["gross_margin"]["value"],
            "net_profit": row["net_profit_attributable"]["value"],
            "eps": row["eps"]["value"],
            "eps_change_pct": _growth(row["eps"]["value"], prior_eps),
        })
        prior_revenue, prior_eps = row["revenue"]["value"], row["eps"]["value"]

    sections = [
        _payload("executive_summary", "核心研究观点", "公司宽口径温控业务已实现较快扩张，但盈利与现金流在最新季度明显承压，当前估值反映了较强的后续修复预期。", ["E1", "E2", "E3", "E8"], material_facts=["2023—2025年收入连续增长", "2026年一季度收入增长而利润显著下滑", "当前市盈率与市销率均处高位"], causal_chain=["算力密度提升扩大热管理需求；公司披露端到端产品覆盖；但最新季度成本费用与现金流压力尚未解释清楚"], economic_implications=["研究重点应从收入增长转向利润率、现金转换和产品结构的共同验证"], counterpoints=["液冷单独盈利口径尚未披露"], uncertainties=["一季度利润异常的持续性和原因仍待后续定期报告验证"], watchpoints=["后续季度毛利率、经营现金流和宽口径产品线收入增速"]),
        _payload("company_context_and_scope", "公司背景与研究边界", "英维克覆盖数据中心、算力设备和储能等精密温控场景，但本文只把液冷视为已确认的产品暴露，不把公司整体业绩等同于液冷业绩。", ["E1", "E4"], material_facts=["公司披露风冷与液冷产品以及端到端交付能力"], causal_chain=["产品覆盖扩大可服务价值链，但披露口径仍停留在宽产品线"], economic_implications=["商业兑现需由分产品收入、毛利率和订单继续验证"], counterpoints=["公司对竞争优势的描述属于管理层陈述"], uncertainties=["液冷独立收入和利润贡献未单列"], watchpoints=["未来官方披露是否增加液冷收入、毛利率或订单口径"]),
        _payload("financial_history_and_cashflow_quality", "财务历史与现金流质量", "2023—2025年收入与利润增长，但现金流转化持续走弱；2026年一季度出现收入与利润、现金流的显著背离。", ["E2", "E3"], material_facts=[revenue, profit, ocf], trend_calculations=[calc], causal_chain=["背离是可观察事实；当前已审阅材料不足以确认具体驱动"], economic_implications=["若利润率和现金转化不能恢复，收入增长的含金量将下降"], counterpoints=["单季度现金流可能受季节性和营运资金扰动"], uncertainties=["尚无已审阅的一次性项目或季度季节性序列用于归因"], watchpoints=["应收、存货、合同负债、毛利率及经营现金流的季度变化"]),
        _payload("business_breakdown_and_economics", "业务拆分与细分经济性", "2025年机房与机柜温控合计贡献近九成收入，毛利率接近；这证明宽口径温控主业集中度高，但不能推导液冷独立经济性。", ["E4"], material_facts=business_calc, trend_calculations=business_calc, causal_chain=["宽口径主业集中使数据中心与算力需求对公司更重要，但产品结构变化仍需单独披露"], economic_implications=["机房与机柜温控的增长和毛利率决定短期盈利基础"], counterpoints=["低占比业务未完整披露毛利率"], uncertainties=["液冷收入、毛利率与利润贡献没有独立口径"], watchpoints=["两大产品线收入占比、毛利率差异和新增订单"]),
        _payload("industry_structure_and_competition", "行业结构与竞争", "高热密度与能效要求推动液冷导入，公司覆盖冷板、连接件、分配单元、机柜、工质和冷源等环节；优势在于链条完整，约束在于竞争加剧及独立盈利数据不足。", ["E5", "E6"], material_facts=["发行人2025年年报披露高热密度和高能效要求推动液冷导入", "公司披露端到端液冷产品覆盖", "2025年中报披露竞争加剧使机房温控毛利率同比下降"], causal_chain=["芯片功率密度提升→散热与能效约束增强→液冷导入；同时供应竞争加剧→价格与毛利率承压"], economic_implications=["需求增长能否转化为利润取决于产品结构、交付质量和定价能力"], counterpoints=["需求驱动与竞争优势主要来自发行人披露，缺少独立行业统计交叉验证"], uncertainties=["市场规模和同业份额未采用口径不一致的第三方估计"], watchpoints=["机房温控毛利率、液冷产品披露、同业同口径收入和利润率"]),
        _payload("forecast_and_scenarios", "预测与情景", "模型以2026年一季度弱盈利为约束，不假设液冷独立收入，并通过收入增速、毛利率和净利率形成三种显式情景。", ["E7"], material_facts=forecast_calc, trend_calculations=forecast_calc, causal_chain=["收入增速与毛利率决定毛利额，费用和税负假设形成归母净利润，再由固定股本桥接至每股收益"], economic_implications=["盈利修复对毛利率和费用纪律高度敏感"], counterpoints=["基准情景不是管理层指引或市场一致预期"], uncertainties=["一季度弱利润原因未验证，因此情景区间保持较宽"], watchpoints=["实际收入增速、毛利率、费用率、税率与股本变化"]),
        _payload("valuation_and_market_expectations", "估值与市场预期", "截至2026年7月10日，市场定价要求未来利润显著修复；在盈利不稳定阶段，市销率与远期市盈率应结合使用，不能给出单一确定价值结论。", ["E8", "E9"], material_facts=[inputs.valuation_reasoning["dated_snapshot"], inputs.valuation_reasoning["peer_matrix"]], trend_calculations=inputs.valuation_reasoning["market_implied_expectations"], causal_chain=["较高市销率和远期市盈率→价格对增长与利润率修复敏感→任何修复不及预期都会放大估值风险"], economic_implications=["估值判断的核心不是点目标价，而是检验收入增长和利润率恢复能否兑现"], counterpoints=["两家可比公司业务结构差异较大，横向倍数仅作低置信度背景"], uncertainties=["现金流折现和分部估值的必要输入尚未满足"], watchpoints=["收入增速、净利率、盈利预测修订与同口径估值变化"]),
        _payload("risks_counterevidence_and_watchpoints", "风险、反证与观察条件", "核心风险是增长未能转化为利润与现金、竞争压低毛利率，以及市场预期领先于基本面兑现。", ["E2", "E3", "E5", "E8"], material_facts=["2026年一季度利润与经营现金流承压", "发行人披露竞争加剧影响毛利率"], causal_chain=["竞争或成本压力→毛利率下降→利润修复落后于收入→高估值消化困难"], economic_implications=["需要以连续季度数据而非单次叙事验证经营改善"], counterpoints=["公司产品链条完整且收入仍在增长"], uncertainties=["液冷单独经济性和一季度异常原因未得到独立验证"], watchpoints=["毛利率恢复、经营现金流转正、液冷独立披露、同业竞争强度"]),
        _payload("research_conclusion", "研究结论与跟踪清单", "现有证据支持公司具备算力热管理与液冷产品暴露，但尚不足以证明液冷独立盈利贡献；报告候选应保持观察型结论，等待利润率、现金流和披露质量共同改善。", ["E1", "E3", "E4", "E7", "E8"], material_facts=["宽口径主业增长", "最新季度利润和现金流承压", "液冷独立经济性未披露"], causal_chain=["产品暴露提供增长选择权；财务兑现与估值吸收决定研究结论能否增强"], economic_implications=["后续更新应优先处理可验证经营指标，而非扩大未经核验的行业叙事"], counterpoints=["若后续利润率与现金流恢复，当前谨慎判断需要上调"], uncertainties=["模型和估值均依赖未来披露验证"], watchpoints=["季度毛利率、经营现金流、液冷口径、预测偏差和估值日期"]),
    ]
    return {
        "artifact_type": "R5_reader_section_payloads",
        "schema_version": "r5_reader_section_payloads_v0.1",
        "workflow_id": "wf_20260703_stock_first_002837_invic",
        "stock_code": "002837",
        "stock_name": "英维克",
        "calculation_ledger": calc,
        "sections": sections,
        "human_review_status": "pending",
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
    }
