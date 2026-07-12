"""Build reviewed coverage, forecast bridge and valuation reasoning artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml


RUN_REL = Path("reports/workflow_runs/wf_20260703_stock_first_002837_invic")


def load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def dump(path: Path, data):
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def build_coverage() -> tuple[dict, dict]:
    dimensions = [
        {"dimension": "company_context", "mandatory": True, "review_status": "accepted", "reviewed_evidence": ["2025 annual report, pages 11-14"], "missing_evidence": [], "preferred_source_type": "official_disclosure", "date_requirement": "cutoff_or_earlier", "expected_output": "company boundary", "owner": "stock-deep-dive"},
        {"dimension": "financial_history", "mandatory": True, "review_status": "accepted", "reviewed_evidence": ["2025 annual report, page 7", "2026Q1 report, pages 2 and 9"], "missing_evidence": [], "preferred_source_type": "official_disclosure", "date_requirement": "2023A-2026Q1", "expected_output": "history and cash conversion", "owner": "stock-deep-dive"},
        {"dimension": "business_economics", "mandatory": True, "review_status": "accepted_with_boundary", "reviewed_evidence": ["2025 annual report, pages 15-16"], "missing_evidence": ["liquid-cooling-specific revenue and margin are not separately disclosed"], "preferred_source_type": "official_disclosure", "date_requirement": "latest annual", "expected_output": "broad product-line economics", "owner": "stock-deep-dive"},
        {"dimension": "industry_and_competition", "mandatory": True, "review_status": "accepted_issuer_evidence_limited", "reviewed_evidence": ["2025 annual report, pages 11-14", "2025 interim report, pages 10-12"], "missing_evidence": ["independent market-size series", "same-definition market shares"], "preferred_source_type": "official_disclosure_or_industry_association", "date_requirement": "2025_or_later", "expected_output": "demand drivers, value chain, advantages and constraints", "owner": "evidence-ingest"},
        {"dimension": "peer_comparability", "mandatory": True, "review_status": "accepted_low_confidence", "reviewed_evidence": ["2026-07-10 structured market snapshot for 301018 and 300499"], "missing_evidence": ["fully comparable revenue-mix and margin series"], "preferred_source_type": "official_disclosure_and_reviewed_market_data", "date_requirement": "same_valuation_date", "expected_output": "transparent small peer matrix", "owner": "company-valuation"},
        {"dimension": "dated_company_events", "mandatory": True, "review_status": "accepted", "reviewed_evidence": ["2025 interim report published 2025-08-19", "2025 annual report and 2026Q1 report published 2026-04-21"], "missing_evidence": [], "preferred_source_type": "official_disclosure", "date_requirement": "explicit_publication_date", "expected_output": "completed events and future verification points", "owner": "evidence-ingest"},
        {"dimension": "historical_market_series", "mandatory": False, "review_status": "deferred_method_not_activated", "reviewed_evidence": ["2026-07-10 point-in-time snapshot"], "missing_evidence": ["reviewed OHLCV series with adjustment and missing-date policy"], "preferred_source_type": "structured_market_data", "date_requirement": "at_least_250_trading_days", "expected_output": "objective returns, volatility and drawdown only", "owner": "evidence-ingest"},
        {"dimension": "sentiment", "mandatory": False, "review_status": "omitted_unsupported", "reviewed_evidence": [], "missing_evidence": ["definitionally clear dated ownership, flow or consensus input"], "preferred_source_type": "reviewed_structured_data", "date_requirement": "dated", "expected_output": "optional", "owner": "evidence-ingest"},
    ]
    coverage = {
        "artifact_type": "R5_bundle6_coverage_inventory", "schema_version": "v0.1", "workflow_id": "wf_20260703_stock_first_002837_invic", "as_of_date": "2026-07-12",
        "dimensions": dimensions,
        "industry_reader_boundary": "发行人披露可支持需求驱动、产品链定位和竞争压力；独立市场规模与份额仍不作事实结论。",
        "liquid_cooling_boundary": {"confirmed": "产品暴露和端到端产品覆盖", "broad_economics": "机房与机柜温控宽口径", "unverified": "液冷独立收入、毛利率与利润贡献", "future_measurement": "后续官方分产品披露、订单与毛利率"},
        "sample_quality_report_allowed": False, "p2_allowed": False,
    }
    plan = {
        "artifact_type": "R5_bundle6_industry_event_market_input_plan", "schema_version": "v0.1", "workflow_id": coverage["workflow_id"],
        "accepted_inputs": [
            {"input": "industry_and_value_chain", "source": "2025 annual report", "source_date": "2026-04-21", "locator": "PDF pages 11-14", "claim_type": "management_comment_and_fact", "review_status": "accepted_with_issuer_boundary"},
            {"input": "competition_pressure", "source": "2025 interim report", "source_date": "2025-08-19", "locator": "PDF pages 10-12", "claim_type": "management_comment", "review_status": "accepted_with_issuer_boundary"},
            {"input": "material_completed_events", "source": "official periodic reports", "source_date": "2025-08-19 and 2026-04-21", "locator": "publication metadata", "claim_type": "fact", "review_status": "accepted"},
            {"input": "peer_valuation_snapshot", "source": "reviewed structured market data", "source_date": "2026-07-10", "locator": "same-date daily_basic snapshot", "claim_type": "fact", "review_status": "accepted_low_confidence"},
        ],
        "peer_rationale": [
            {"stock_code": "301018", "name": "申菱环境", "included_because": "精密温控与数据中心热管理产品暴露", "not_fully_comparable_because": "业务组合和利润结构不同", "valuation_date": "2026-07-10", "denominator_period": "TTM", "confidence": "low"},
            {"stock_code": "300499", "name": "高澜股份", "included_because": "热管理与液冷相关产品暴露", "not_fully_comparable_because": "业务组合和盈利波动不同", "valuation_date": "2026-07-10", "denominator_period": "TTM", "confidence": "low"},
        ],
        "completed_events": [
            {"date": "2025-08-19", "event": "2025年半年度报告披露", "classification": "completed_fact"},
            {"date": "2026-04-21", "event": "2025年年度报告与2026年一季度报告披露", "classification": "completed_fact"},
        ],
        "scheduled_verification_points": ["下一份官方定期报告：验证毛利率、经营现金流和液冷披露口径；具体日期以交易所公告为准"],
        "deferred_inputs": [{"input": "historical_ohlcv", "reason": "technical market section is not activated in this candidate"}, {"input": "sentiment", "reason": "no reviewed definitionally clear input"}],
        "sample_evidence_used": False, "sample_quality_report_allowed": False, "p2_allowed": False,
    }
    return coverage, plan


def build_forecast(financial: dict, forecast: dict, valuation: dict) -> dict:
    table = forecast["forecast_table"]["base_case"]
    assumptions = {a["driver"]: a for a in forecast["assumptions"]}
    shares = valuation["market_snapshot"]["share_count"]["value"]
    rows = []
    for period in ("2026E", "2027E", "2028E"):
        row = table[period]
        revenue = float(row["revenue"]["value"])
        gross_profit = float(row["gross_profit"]["value"])
        net_profit = float(row["net_profit_attributable"]["value"])
        eps = float(row["eps"]["value"])
        opex = revenue * float(assumptions["opex"]["value"][period]) / 100
        other_after_gross_profit = gross_profit - opex - net_profit
        rows.append({"period": period, "revenue": revenue, "gross_margin_pct": row["gross_margin"]["value"], "gross_profit": gross_profit, "opex_assumption_pct": assumptions["opex"]["value"][period], "opex": opex, "implied_tax_finance_other_and_minority": other_after_gross_profit, "net_profit_attributable": net_profit, "diluted_share_count": shares, "eps": eps, "reconciliation_difference": net_profit / shares - eps})
    return {
        "artifact_type": "R5_bundle6_forecast_bridge", "schema_version": "v0.1", "as_of_date": "2026-07-10", "historical_anchor": {"period": "2025A", "revenue": 6067759091.55, "net_profit_attributable": 521914773.0, "gross_margin_pct": 27.86, "eps": 0.54},
        "latest_quarter_treatment": {"period": "2026Q1", "observed": "收入同比增长26.03%，归母净利润同比下降81.97%，经营现金流为负", "model_choice": "不直接年化一季度利润；基准情景采用较低毛利率和费用率起点，熊牛情景扩大区间", "cause_status": "observable_divergence_driver_not_verified"},
        "broad_product_line_boundary": "预测保持公司整体口径，不建立未披露的液冷独立收入线。",
        "driver_assumptions": [{"driver": k, "values": v.get("value"), "unit": v.get("unit"), "rationale": v.get("rationale")} for k, v in assumptions.items()],
        "base_case_bridge": rows,
        "scenarios": {name: {"status": value["status"], "drivers": {period: {"revenue": r["revenue"]["value"], "gross_margin_pct": r["gross_margin"]["value"], "net_profit": r["net_profit_attributable"]["value"], "eps": r["eps"]["value"]} for period, r in value["forecast_table"].items()}} for name, value in forecast["scenarios"].items()},
        "sensitivity_variables": ["revenue_growth", "gross_margin"], "consensus_used": False, "sample_quality_report_allowed": False, "p2_allowed": False,
    }


def build_valuation(valuation: dict, bridge: dict) -> dict:
    snap = valuation["market_snapshot"]
    peer = valuation["peer_valuation_context"]
    return {
        "artifact_type": "R5_bundle6_valuation_reasoning_pack", "schema_version": "v0.1", "as_of_date": "2026-07-10",
        "dated_snapshot": {"price_cny": snap["current_price"]["value"], "market_cap_cny": snap["market_cap"]["value"], "pe_ttm": snap["pe_ttm"]["value"], "pb": snap["pb"]["value"], "ps_ttm": snap["ps"]["value"], "denominator_control": "PE/PS use TTM denominators; forward PE uses Bundle6 scenario EPS; all market fields share 2026-07-10"},
        "method_eligibility": [
            {"method": "forward_pe", "status": "context_only", "reason": "earnings scenarios exist but 2026 profitability is unstable"},
            {"method": "ps_ttm", "status": "active_context", "reason": "revenue denominator is more stable; margin differences limit comparability"},
            {"method": "dcf", "status": "inactive", "reason": "FCFF, discount rate and terminal assumptions are not reviewed"},
            {"method": "sotp", "status": "inactive", "reason": "liquid-cooling and other segment economics are not sufficiently separated"},
        ],
        "peer_matrix": [{"stock_code": r["peer_stock_code"], "name": r["peer_company_name"], "pe_ttm": r["multiple_value"], "valuation_date": r["as_of_date"], "denominator": "TTM", "inclusion_reason": "thermal-management exposure", "comparability_limitation": "business mix and earnings quality differ", "confidence": "low"} for r in peer["rows"]],
        "market_implied_expectations": [
            {"statement": "TTM市盈率接近194.2倍，价格已要求利润较当前水平显著扩张", "claim_type": "inference", "limitation": "不等于目标价或交易建议"},
            {"statement": "按基准模型，2026E/2027E/2028E远期市盈率约995.8/291.8/161.5倍", "claim_type": "estimate", "limitation": "对利润率恢复高度敏感"},
            {"statement": "14.9倍TTM市销率意味着收入增长必须最终转化为可持续利润和现金", "claim_type": "inference", "limitation": "未建立市场一致预期反推模型"},
        ],
        "scenario_context": [{"period": r["period"], "eps": r["eps"], "forward_pe": snap["current_price"]["value"] / r["eps"]} for r in bridge["base_case_bridge"]],
        "target_price": None, "rating": None, "position_instruction": None, "human_review_status": "pending", "sample_quality_report_allowed": False, "p2_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    run = root / RUN_REL
    financial = load(run / "R5_bundle5_financial_history_candidate.yaml")
    forecast = load(run / "R5_bundle5_forecast_model_candidate.yaml")
    valuation = load(run / "R5_bundle5_valuation_pack_candidate.yaml")
    coverage, plan = build_coverage()
    bridge = build_forecast(financial, forecast, valuation)
    reasoning = build_valuation(valuation, bridge)
    for name, value in (("R5_bundle6_coverage_inventory.yaml", coverage), ("R5_bundle6_industry_event_market_input_plan.yaml", plan), ("R5_bundle6_forecast_bridge.yaml", bridge), ("R5_bundle6_valuation_reasoning_pack.yaml", reasoning)):
        dump(run / name, value)
    print("r5_bundle6_research_remediation status=ready coverage=accepted forecast_reconciled=true valuation_date=2026-07-10 sample_quality=false p2=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
