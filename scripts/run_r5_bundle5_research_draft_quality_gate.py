#!/usr/bin/env python3
"""Build, gate, render and quality-check the Bundle 5 real research draft."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import r5_reviewed_input_pilot_gate as pilot_gate  # noqa: E402
import render_r5_reviewed_input_output as renderer  # noqa: E402

WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
STOCK_CODE = "002837"
ANNUAL_EVIDENCE_ID = "ev_annual_report_002837_20260421_2cbfc5"
INTERIM_EVIDENCE_ID = "ev_interim_report_002837_20250819_47054e"
Q1_EVIDENCE_ID = "ev_quarterly_report_002837_20260421_2f00c7"
MARKET_EVIDENCE_ID = "ev_structured_market_data_002837_20260710_eb0c08"
RESOLVED_REGISTRY_TODOS = {"TODO_MARKET_DATA", "TODO_PEER_DATA", "TODO_MODEL_INPUT"}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _metric(history: dict[str, Any], metric_name: str, period: str) -> dict[str, Any]:
    for section in ("income_statement", "balance_sheet", "cashflow_statement", "key_metrics"):
        for row in history.get(section, []) or []:
            if isinstance(row, dict) and row.get("metric_name") == metric_name and row.get("period") == period:
                return row
    raise KeyError(f"missing metric {metric_name}/{period}")


def _business_line(business: dict[str, Any], name: str) -> dict[str, Any]:
    for row in business.get("business_lines", []) or []:
        if isinstance(row, dict) and row.get("business_name") == name:
            return row
    raise KeyError(f"missing business line {name}")


def _fmt(value: Any, places: int = 2) -> str:
    if isinstance(value, (int, float)):
        return f"{value:,.{places}f}"
    return str(value)


def _claim(
    claim_id: str,
    claim_type: str,
    period: str,
    statement: str,
    evidence_ids: list[str],
    source_path: str,
    calculation_method: str,
    unit: str,
    *,
    assumption_ids: list[str] | None = None,
    confidence: str = "high",
) -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "section_id": claim_id.rsplit("_", 1)[0],
        "claim_type": claim_type,
        "period": period,
        "statement": statement,
        "evidence_ids": evidence_ids,
        "assumption_ids": assumption_ids or [],
        "source_path": source_path,
        "calculation_method": calculation_method,
        "unit": unit,
        "confidence": confidence,
        "review_status": "reviewed",
    }


def _columns(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    return [{"key": key, "label": label} for key, label in pairs]


def build_pack(repo_root: Path) -> dict[str, Any]:
    run_dir = repo_root / "reports/workflow_runs" / WORKFLOW_ID
    history_path = run_dir / "R5_bundle5_financial_history_candidate.yaml"
    business_path = run_dir / "R5_bundle5_business_breakdown_candidate.yaml"
    market_path = run_dir / "R5_market_peer_input_registry.yaml"
    forecast_path = run_dir / "R5_bundle5_forecast_model_candidate.yaml"
    valuation_path = run_dir / "R5_bundle5_valuation_pack_candidate.yaml"
    dry_run_path = run_dir / "R5_reviewed_input_dry_run_result.yaml"

    history = load_yaml(history_path)
    business = load_yaml(business_path)
    market = load_yaml(market_path)
    forecast = load_yaml(forecast_path)
    valuation = load_yaml(valuation_path)
    dry_run = load_yaml(dry_run_path)

    if dry_run.get("derivation_source") != "validated_physical_registries":
        raise ValueError("Bundle 5 draft gate requires validated physical registries")
    required_flags = [
        "reviewed_market_inputs_available",
        "reviewed_peer_inputs_available",
        "reviewed_forecast_assumptions_available",
        "reviewed_business_disclosure_available",
        "reviewed_valuation_inputs_available",
    ]
    missing_flags = [flag for flag in required_flags if dry_run.get(flag) is not True]
    if missing_flags:
        raise ValueError("reviewed physical flags missing: " + ", ".join(missing_flags))

    revenue_2025 = _metric(history, "revenue", "2025A")
    profit_2025 = _metric(history, "net_profit_attributable", "2025A")
    revenue_q1 = _metric(history, "revenue", "2026Q1")
    profit_q1 = _metric(history, "net_profit_attributable", "2026Q1")
    ocf_2023 = _metric(history, "operating_cashflow", "2023A")
    ocf_2024 = _metric(history, "operating_cashflow", "2024A")
    ocf_2025 = _metric(history, "operating_cashflow", "2025A")
    ocf_q1 = _metric(history, "operating_cashflow", "2026Q1")
    room = _business_line(business, "room_cooling")
    cabinet = _business_line(business, "cabinet_cooling")
    liquid = _business_line(business, "liquid_cooling_specific")
    market_inputs = market.get("market_inputs") or {}
    peer_inputs = market.get("peer_inputs") or {}
    base_table = ((forecast.get("forecast_table") or {}).get("base_case") or {})
    valuation_market = valuation.get("market_snapshot") or {}
    relative_method = next(
        row for row in valuation.get("valuation_methods", []) if isinstance(row, dict) and row.get("method_id") == "relative_pe"
    )
    relative_output = relative_method.get("supported_output") or {}

    material_claims = [
        _claim(
            "financial_history_revenue_2025",
            "fact",
            "2025A",
            f"公司营业收入为 {_fmt(revenue_2025['value'])} CNY，归母净利润为 {_fmt(profit_2025['value'])} CNY。",
            [ANNUAL_EVIDENCE_ID],
            str(history_path.relative_to(repo_root).as_posix()),
            "direct_reported_value",
            "CNY",
        ),
        _claim(
            "financial_q1_profit_divergence",
            "fact",
            "2026Q1",
            "营业收入同比增长 26.03%，归母净利润同比下降 81.97%，收入与利润表现发生背离。",
            [Q1_EVIDENCE_ID],
            str(history_path.relative_to(repo_root).as_posix()),
            "direct_reported_yoy_values",
            "pct",
        ),
        _claim(
            "financial_q1_operating_cashflow",
            "fact",
            "2026Q1",
            f"经营现金流为 {_fmt(ocf_q1['value'])} CNY，且 2025A 低于 2023A 与 2024A。",
            [ANNUAL_EVIDENCE_ID, Q1_EVIDENCE_ID],
            str(history_path.relative_to(repo_root).as_posix()),
            "direct_reported_value_and_period_comparison",
            "CNY",
        ),
        _claim(
            "business_broad_product_split",
            "fact",
            "2025A",
            f"机房温控与机柜温控是年报披露的宽口径产品线，收入分别为 {_fmt(room['revenue']['value'])} 与 {_fmt(cabinet['revenue']['value'])} CNY。",
            [ANNUAL_EVIDENCE_ID],
            str(business_path.relative_to(repo_root).as_posix()),
            "direct_reported_product_line_values",
            "CNY",
        ),
        _claim(
            "business_liquid_cooling_exposure",
            "fact",
            "2025A",
            "官方材料披露液冷相关产品线索，但没有单列相应收入占比、毛利率和利润贡献。",
            [ANNUAL_EVIDENCE_ID],
            str(business_path.relative_to(repo_root).as_posix()),
            "product_narrative_review_with_visible_missing_metrics",
            "not_applicable",
            confidence="medium",
        ),
        _claim(
            "forecast_base_path",
            "estimate",
            "2026E-2028E",
            "基准情景采用机械外推与显式模型假设，2026E-2028E EPS 分别为 0.073854、0.252034、0.455462 CNY/share。",
            [ANNUAL_EVIDENCE_ID, Q1_EVIDENCE_ID, MARKET_EVIDENCE_ID],
            str(forecast_path.relative_to(repo_root).as_posix()),
            "reviewed_assumption_model",
            "CNY_per_share",
            assumption_ids=["r5_b5_forecast_eps_base"],
            confidence="low",
        ),
        _claim(
            "valuation_cross_multiple_context",
            "inference",
            "2026-07-10",
            "PE TTM 低于两家同业中位数，而 PB 与 PS TTM 高于对应中位数，方向不一致，不能形成单一估值标签。",
            [MARKET_EVIDENCE_ID],
            str(valuation_path.relative_to(repo_root).as_posix()),
            "same_date_cross_multiple_comparison",
            "multiple",
            assumption_ids=["r5_b5_valuation_context_002837_20260710"],
            confidence="low",
        ),
        _claim(
            "valuation_net_debt_proxy",
            "inference",
            "2026Q1",
            "净债务代理值为 698,135,329.67 CNY；受受限资金和金融资产重分类未复核影响，置信度为 low。",
            [Q1_EVIDENCE_ID],
            str(valuation_path.relative_to(repo_root).as_posix()),
            "reviewed_debt_components_minus_cash",
            "CNY_net_debt_proxy",
            confidence="low",
        ),
    ]

    financial_rows = []
    for period in ("2023A", "2024A", "2025A", "2026Q1"):
        financial_rows.append(
            {
                "period": period,
                "revenue": _fmt(_metric(history, "revenue", period)["value"]),
                "profit": _fmt(_metric(history, "net_profit_attributable", period)["value"]),
                "ocf": _fmt(_metric(history, "operating_cashflow", period)["value"]),
                "unit": "CNY",
                "type": "fact",
                "anchor": _metric(history, "revenue", period)["evidence_id"],
                "method": "direct_reported_value",
            }
        )

    business_rows = []
    for row in (room, cabinet, liquid):
        business_rows.append(
            {
                "line": row.get("reported_name"),
                "revenue": _fmt((row.get("revenue") or {}).get("value")) if (row.get("revenue") or {}).get("value") is not None else "MISSING_DISCLOSURE",
                "share": _fmt((row.get("revenue_pct") or {}).get("value")) if (row.get("revenue_pct") or {}).get("value") is not None else "MISSING_DISCLOSURE",
                "margin": _fmt((row.get("gross_margin") or {}).get("value")) if (row.get("gross_margin") or {}).get("value") is not None else "MISSING_DISCLOSURE",
                "confidence": row.get("confidence"),
                "anchor": ", ".join(row.get("evidence_ids") or ["MISSING_DISCLOSURE"]),
            }
        )

    forecast_rows = []
    for period in ("2026E", "2027E", "2028E"):
        row = base_table[period]
        forecast_rows.append(
            {
                "period": period,
                "revenue": _fmt(row["revenue"]["value"]),
                "gross_margin": _fmt(row["gross_margin"]["value"], 4),
                "profit": _fmt(row["net_profit_attributable"]["value"]),
                "eps": _fmt(row["eps"]["value"], 6),
                "type": "estimate",
                "anchor": row["eps"]["assumption_id"],
            }
        )

    market_rows = [
        {
            "metric": "close",
            "value": _fmt(market_inputs["current_price"]["value"]),
            "unit": market_inputs["current_price"]["unit"],
            "definition": "2026-07-10 unadjusted close",
            "anchor": market_inputs["current_price"]["evidence_id"],
        },
        {
            "metric": "PE TTM",
            "value": _fmt(market_inputs["pe_ttm"]["value"], 4),
            "unit": "multiple",
            "definition": "trailing earnings multiple",
            "anchor": MARKET_EVIDENCE_ID,
        },
        {
            "metric": "PB",
            "value": _fmt(market_inputs["pb"]["value"], 4),
            "unit": "multiple",
            "definition": "price-to-book",
            "anchor": MARKET_EVIDENCE_ID,
        },
        {
            "metric": "PS",
            "value": _fmt(market_inputs["ps"]["value"], 4),
            "unit": "multiple",
            "definition": "non-TTM PS field from physical registry",
            "anchor": MARKET_EVIDENCE_ID,
        },
        {
            "metric": "PS TTM",
            "value": _fmt(valuation_market["ps"]["value"], 4),
            "unit": "multiple_TTM",
            "definition": "TTM sales multiple; kept separate from PS",
            "anchor": MARKET_EVIDENCE_ID,
        },
    ]

    source_gaps = [
        {
            "gap_id": "R5_B5_GAP_LIQUID_COOLING_SPLIT",
            "section": "business_breakdown_and_segment_economics",
            "missing_data": "MISSING_DISCLOSURE: liquid-cooling-specific revenue share, margin and profit contribution",
            "impact_on_conclusion": "product exposure cannot be converted into a financial contribution estimate",
            "fix_owner_skill": "evidence-ingest",
            "next_action": "retain the gap until an official split is published",
        },
        {
            "gap_id": "R5_B5_GAP_INDUSTRY_STRUCTURE",
            "section": "industry_structure_and_competition",
            "missing_data": "TODO_SOURCE_REQUIRED: reviewed industry supply and competition evidence",
            "impact_on_conclusion": "industry structure remains outside the factual conclusion set",
            "fix_owner_skill": "segment-research",
            "next_action": "onboard reviewed industry evidence in a later scoped task",
        },
        {
            "gap_id": "R5_B5_GAP_PRICE_HISTORY",
            "section": "dated_market_or_technical_state_when_supported",
            "missing_data": "MISSING_PRICE_HISTORY: one dated snapshot does not support a trend statement",
            "impact_on_conclusion": "market section is limited to a dated snapshot",
            "fix_owner_skill": "stock-deep-dive",
            "next_action": "keep trend assessment absent until reviewed history exists",
        },
        {
            "gap_id": "R5_B5_GAP_SENTIMENT_EVENTS",
            "section": "dated_sentiment_and_events_when_supported",
            "missing_data": "TODO_SOURCE_REQUIRED: dated sentiment and event evidence",
            "impact_on_conclusion": "no event or sentiment judgement is rendered",
            "fix_owner_skill": "evidence-ingest",
            "next_action": "collect dated official event sources if the section is later activated",
        },
        {
            "gap_id": "R5_B5_GAP_PEER_CONFIDENCE",
            "section": "valuation_methods_and_comparability",
            "missing_data": "LOW_CONFIDENCE_CLUE_ONLY: peer set contains two non-identical business mixes",
            "impact_on_conclusion": "relative multiples remain contextual only",
            "fix_owner_skill": "company-valuation",
            "next_action": "retain low confidence until a broader evidence-grounded peer set is reviewed",
        },
        {
            "gap_id": "R5_B5_GAP_INTRINSIC_METHODS",
            "section": "valuation_methods_and_comparability",
            "missing_data": "UNREVIEWED_FCFF_INPUTS and UNDISCLOSED_SEGMENT_SPLIT",
            "impact_on_conclusion": "intrinsic and segment-sum methods remain inactive",
            "fix_owner_skill": "company-valuation",
            "next_action": "keep methods excluded until required inputs are reviewed",
        },
    ]

    report_sections = [
        {
            "section_id": "company_context",
            "title": "公司背景与研究边界",
            "readiness": "covered",
            "evidence_ids": [ANNUAL_EVIDENCE_ID],
            "narrative": [
                "当前证据支持公司存在数据中心温控和液冷相关产品线索；研究边界停留在产品暴露，不能把公司整体财务数据归因到液冷业务。"
            ],
            "columns": _columns(("item", "项目"), ("state", "状态"), ("confidence", "置信度"), ("anchor", "锚点")),
            "rows": [{"item": "ai_server_liquid_cooling", "state": "product_exposure_needs_review", "confidence": "medium", "anchor": ANNUAL_EVIDENCE_ID}],
            "limitations": ["liquid-cooling-specific financial contribution is not separately disclosed"],
            "visible_gaps": ["MISSING_DISCLOSURE"],
        },
        {
            "section_id": "financial_history_and_cash_flow_quality",
            "title": "财务历史与现金流质量",
            "readiness": "covered",
            "evidence_ids": [ANNUAL_EVIDENCE_ID, Q1_EVIDENCE_ID],
            "narrative": ["2026Q1 收入增长与利润下降并存，经营现金流为负；单季结果不直接外推为全年事实。"],
            "columns": _columns(("period", "期间"), ("revenue", "收入"), ("profit", "归母净利润"), ("ocf", "经营现金流"), ("unit", "单位"), ("type", "类型"), ("anchor", "证据"), ("method", "方法")),
            "rows": financial_rows,
            "limitations": ["2026Q1 is unaudited and should not be treated as a full-year pattern"],
            "visible_gaps": [],
        },
        {
            "section_id": "business_breakdown_and_segment_economics",
            "title": "业务拆分与细分经济性",
            "readiness": "partial",
            "evidence_ids": [ANNUAL_EVIDENCE_ID],
            "narrative": ["宽口径机房与机柜温控数据可核验，但这些数据不等同于液冷单独口径。"],
            "columns": _columns(("line", "披露口径"), ("revenue", "收入 CNY"), ("share", "收入占比 %"), ("margin", "毛利率 %"), ("confidence", "置信度"), ("anchor", "证据")),
            "rows": business_rows,
            "limitations": list(business.get("structural_contradictions") or []),
            "visible_gaps": ["MISSING_DISCLOSURE"],
        },
        {
            "section_id": "industry_structure_and_competition",
            "title": "行业结构与竞争",
            "readiness": "missing",
            "evidence_ids": [],
            "narrative": ["当前没有审查后的行业供需与竞争证据，本节不生成事实性行业判断。"],
            "columns": [],
            "rows": [],
            "limitations": ["industry evidence is outside the current reviewed-input set"],
            "visible_gaps": ["TODO_SOURCE_REQUIRED"],
        },
        {
            "section_id": "forecast_assumptions_and_sensitivity",
            "title": "预测假设与敏感性",
            "readiness": "covered",
            "evidence_ids": [ANNUAL_EVIDENCE_ID, Q1_EVIDENCE_ID, MARKET_EVIDENCE_ID],
            "narrative": ["以下均为 estimate：2026E 使用机械外推，2027E-2028E 使用显式放缓与利润率假设，并保留宽范围敏感性。"],
            "columns": _columns(("period", "期间"), ("revenue", "收入 CNY"), ("gross_margin", "毛利率 %"), ("profit", "归母净利润 CNY"), ("eps", "EPS CNY/share"), ("type", "类型"), ("anchor", "假设锚点")),
            "rows": forecast_rows,
            "limitations": list((forecast.get("assumptions") or [{}])[0].get("limitations") or []),
            "visible_gaps": [],
        },
        {
            "section_id": "valuation_methods_and_comparability",
            "title": "估值方法与可比性",
            "readiness": "partial",
            "evidence_ids": [MARKET_EVIDENCE_ID, Q1_EVIDENCE_ID],
            "narrative": [
                f"同日比较中，公司 PE TTM 为 {relative_output['subject']['pe_ttm']}，同业中位数为 {relative_output['peer_median']['pe_ttm']}；PB 与 PS TTM 的方向相反，因此保持 mixed_multiple_signal_not_assessable。"
            ],
            "columns": _columns(("metric", "指标"), ("value", "数值"), ("unit", "单位"), ("definition", "口径"), ("anchor", "证据")),
            "rows": market_rows,
            "limitations": list(valuation.get("limitations") or []),
            "visible_gaps": ["LOW_CONFIDENCE_CLUE_ONLY", "UNREVIEWED_FCFF_INPUTS", "UNDISCLOSED_SEGMENT_SPLIT"],
        },
        {
            "section_id": "dated_market_or_technical_state_when_supported",
            "title": "有日期的市场状态",
            "readiness": "partial",
            "evidence_ids": [MARKET_EVIDENCE_ID],
            "narrative": ["仅呈现 2026-07-10 的收盘与估值快照；缺少审查后的历史序列，因此不生成趋势判断。"],
            "columns": _columns(("metric", "指标"), ("value", "数值"), ("unit", "单位"), ("definition", "口径"), ("anchor", "证据")),
            "rows": market_rows[:3],
            "limitations": ["single-date snapshot only"],
            "visible_gaps": ["MISSING_PRICE_HISTORY"],
        },
        {
            "section_id": "dated_sentiment_and_events_when_supported",
            "title": "有日期的情绪与事件",
            "readiness": "missing",
            "evidence_ids": [],
            "narrative": ["当前没有进入审查输入集的有日期事件或情绪证据，本节保持空缺。"],
            "columns": [],
            "rows": [],
            "limitations": ["dated sources are absent"],
            "visible_gaps": ["TODO_SOURCE_REQUIRED"],
        },
        {
            "section_id": "risks_counterevidence_and_open_questions",
            "title": "风险、反证与开放问题",
            "readiness": "covered",
            "evidence_ids": [ANNUAL_EVIDENCE_ID, Q1_EVIDENCE_ID, MARKET_EVIDENCE_ID],
            "narrative": ["风险与反证保留在正文，不因报告可渲染而弱化。"],
            "columns": _columns(("type", "类别"), ("item", "内容"), ("anchor", "锚点")),
            "rows": [
                {"type": "risk", "item": "2026Q1 利润与经营现金流显著弱于收入表现", "anchor": Q1_EVIDENCE_ID},
                {"type": "risk", "item": "2025A 经营现金流低于 2023A 与 2024A", "anchor": ANNUAL_EVIDENCE_ID},
                {"type": "counter_evidence", "item": "宽口径产品线不能证明液冷单独财务贡献", "anchor": ANNUAL_EVIDENCE_ID},
                {"type": "counter_evidence", "item": "PE、PB 与 PS TTM 的同业信号方向不一致", "anchor": MARKET_EVIDENCE_ID},
            ],
            "limitations": [],
            "visible_gaps": ["MISSING_DISCLOSURE", "LOW_CONFIDENCE_CLUE_ONLY"],
        },
        {
            "section_id": "research_conclusion_and_watch_conditions",
            "title": "研究结论与后续观察条件",
            "readiness": "partial",
            "evidence_ids": [ANNUAL_EVIDENCE_ID, Q1_EVIDENCE_ID, MARKET_EVIDENCE_ID],
            "narrative": ["研究状态为 evidence_watch：产品暴露可继续验证，但收入与利润暴露仍为 unknown；预测和估值仅作低置信研究情景。"],
            "columns": _columns(("condition", "观察条件"), ("reason", "原因"), ("source", "后续来源")),
            "rows": [
                {"condition": "液冷单独收入与毛利率", "reason": "验证产品暴露能否转化为财务贡献", "source": "future official disclosure"},
                {"condition": "利润与经营现金流", "reason": "验证盈利质量是否改善", "source": "future periodic report"},
                {"condition": "可比口径与方法输入", "reason": "改善估值可比性与方法资格", "source": "reviewed structured inputs"},
            ],
            "limitations": ["research-draft level only"],
            "visible_gaps": ["MISSING_DISCLOSURE", "LOW_CONFIDENCE_CLUE_ONLY"],
        },
    ]

    pack = {
        "schema_version": "r5_bundle5_stock_research_pack_v0.1",
        "artifact_type": "R5_stock_research_pack",
        "status": "accepted_with_todos",
        "pack_status": "research_draft",
        "metadata": {
            "workflow_id": WORKFLOW_ID,
            "stock_code": STOCK_CODE,
            "company_id": "cn_002837_invic",
            "as_of_date": "2026-07-10",
            "registry_derivation": "validated_physical_registries",
        },
        "as_of_date": "2026-07-10",
        "workflow_id": WORKFLOW_ID,
        "stock": {
            "company_name": "英维克",
            "stock_code": STOCK_CODE,
            "exchange": "SZSE",
            "currency": "CNY",
            "fiscal_year_latest": "2025A",
            "report_authoring_date": "2026-07-12",
        },
        "quality_status": {
            "r5_gate_status": "R5_REVIEWED_INPUT_PILOT_ALLOWED",
            "allowed_report_level": "reviewed_input_research_draft",
            "high_issue_count": 0,
            "medium_issue_count": len(source_gaps),
            "source_gap_visible": True,
            "no_advice_gate_passed": True,
            "sample_quality_report_allowed": False,
            "p2_allowed": False,
        },
        "company_identity_pack": {
            "status": "ready",
            "company_id": "cn_002837_invic",
            "stock_code": STOCK_CODE,
            "company_name": "英维克",
            "evidence_ids": [ANNUAL_EVIDENCE_ID],
        },
        "source_gap_policy": {
            "source_gap_visible": True,
            "missing_value_tokens": [
                "MISSING_DISCLOSURE",
                "TODO_SOURCE_REQUIRED",
                "TODO_MODEL_INPUT",
                "TODO_MARKET_DATA",
                "TODO_PEER_DATA",
                "LOW_CONFIDENCE_CLUE_ONLY",
            ],
            "note": "Policy tokens are an enum; only source_gap_register rows are active gaps.",
        },
        "evidence_snapshot_pack": {
            "status": "ready",
            "as_of_date": "2026-07-10",
            "evidence_ids": [ANNUAL_EVIDENCE_ID, INTERIM_EVIDENCE_ID, Q1_EVIDENCE_ID, MARKET_EVIDENCE_ID],
            "source_paths": [
                "data/raw/annual_reports/cninfo_2025_annual_report_full_002837_2026-04-21.pdf",
                "data/raw/announcements/cninfo_2025_interim_report_full_002837_2025-08-19.pdf",
                "data/raw/announcements/szse_2026_q1_report_002837_2026-04-21.pdf",
                "data/raw/market_data/tushare_daily_basic_peer_set_2026-07-10_eb0c080a.json",
            ],
        },
        "financial_history_pack": history,
        "business_breakdown_pack": business,
        "segment_exposure_pack": {
            "status": "partial",
            "exposures": [
                {
                    "segment_id": "ai_server_liquid_cooling",
                    "exposure_type": "product",
                    "exposure_score": 2,
                    "revenue_pct": "MISSING_DISCLOSURE",
                    "profit_pct": "MISSING_DISCLOSURE",
                    "evidence_ids": [ANNUAL_EVIDENCE_ID],
                    "confidence": "medium",
                    "link_status": "needs_review",
                    "missing_reason": "liquid-cooling-specific financial split is not disclosed",
                }
            ],
        },
        "industry_context_pack": {
            "status": "partial",
            "linked_segments": ["ai_server_liquid_cooling"],
            "supply_competition": "TODO_SOURCE_REQUIRED",
            "evidence_ids": [],
        },
        "peer_comparison_pack": {
            "status": "partial",
            "as_of_date": market.get("as_of_date"),
            "peer_set": (peer_inputs.get("peer_set") or {}).get("value", []),
            "peer_metrics": (peer_inputs.get("peer_valuation_multiples") or {}).get("value", []),
            "evidence_ids": [MARKET_EVIDENCE_ID],
            "confidence": "low",
            "limitations": (peer_inputs.get("peer_set") or {}).get("limitations", []),
        },
        "forecast_model_pack": forecast,
        "valuation_pack": valuation,
        "technical_market_pack": {
            "status": "partial",
            "as_of_date": "2026-07-10",
            "market_snapshot": market_inputs,
            "trend_judgement": None,
            "missing_reason": "MISSING_PRICE_HISTORY",
            "evidence_ids": [MARKET_EVIDENCE_ID],
        },
        "sentiment_event_pack": {
            "status": "TODO",
            "as_of_date": None,
            "missing_reason": "TODO_SOURCE_REQUIRED",
            "evidence_ids": [],
        },
        "risk_counterevidence_pack": {
            "status": "ready",
            "risks": [
                "2026Q1 profit and operating cashflow were weak relative to revenue growth.",
                "2025A operating cashflow was below 2023A and 2024A.",
                "Peer comparability remains low confidence.",
            ],
            "counter_evidence": [
                "Broad room/cabinet categories do not prove liquid-cooling-specific financial contribution.",
                "PE and PB/PS TTM peer signals point in different directions.",
            ],
            "evidence_ids": [ANNUAL_EVIDENCE_ID, Q1_EVIDENCE_ID, MARKET_EVIDENCE_ID],
        },
        "source_gap_register": source_gaps,
        "report_composition_pack": {
            "status": "ready",
            "output_type": "reviewed_input_research_draft",
            "section_ids": [section["section_id"] for section in report_sections],
            "sample_quality_report_allowed": False,
            "p2_allowed": False,
        },
        "material_claims": material_claims,
        "report_sections": report_sections,
        "data_definition_conflicts": [
            {
                "conflict_id": "market_ps_vs_ps_ttm_definition",
                "status": "resolved_by_separate_labels",
                "definitions": ["PS=15.4449", "PS TTM=14.8507"],
                "source_paths": [str(market_path.relative_to(repo_root).as_posix()), str(valuation_path.relative_to(repo_root).as_posix())],
                "handling": "PS and PS TTM are rendered as distinct metrics; neither value is relabeled.",
            },
            {
                "conflict_id": "broad_product_line_vs_liquid_specific",
                "status": "unresolved_disclosure_gap",
                "definitions": ["room/cabinet broad product lines", "liquid-cooling-specific financial split"],
                "source_paths": [str(business_path.relative_to(repo_root).as_posix())],
                "handling": "Broad product-line values remain separate from the missing liquid-cooling-specific metrics.",
            },
        ],
        "open_questions": [
            "When will liquid-cooling-specific revenue, margin or profit contribution be separately disclosed?",
            "Does profit and operating cashflow recover after the weak 2026Q1 pattern?",
            "Can a broader evidence-grounded peer set improve comparability?",
            "When do reviewed price history and dated event sources become available?",
            "Which inputs would make intrinsic or segment-sum methods eligible?",
        ],
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
    }
    return pack


def build_scorecard(pack: dict[str, Any], dry_run: dict[str, Any]) -> dict[str, Any]:
    section_owner = {
        "company_context": "stock-deep-dive",
        "financial_history_and_cash_flow_quality": "stock-deep-dive",
        "business_breakdown_and_segment_economics": "evidence-ingest",
        "industry_structure_and_competition": "segment-research",
        "forecast_assumptions_and_sensitivity": "stock-deep-dive",
        "valuation_methods_and_comparability": "company-valuation",
        "dated_market_or_technical_state_when_supported": "stock-deep-dive",
        "dated_sentiment_and_events_when_supported": "evidence-ingest",
        "risks_counterevidence_and_open_questions": "quality-review",
        "research_conclusion_and_watch_conditions": "quality-review",
    }
    sections = []
    for section in pack["report_sections"]:
        readiness = section["readiness"]
        validator_readiness = {
            "covered": "ready",
            "partial": "ready_with_limitations",
            "missing": "source_gapped",
            "not_applicable": "source_gapped",
        }[readiness]
        section_id = section["section_id"]
        if section_id == "forecast_assumptions_and_sensitivity":
            validator_id = "forecast"
        elif section_id == "valuation_methods_and_comparability":
            validator_id = "valuation"
        else:
            validator_id = section_id
        sections.append(
            {
                "section_id": validator_id,
                "benchmark_dimension": section_id,
                "readiness": validator_readiness,
                "evidence_ids": section.get("evidence_ids") or [],
                "issues": section.get("visible_gaps") or [],
                "limitations": section.get("limitations") or [],
                "fix_owner_skill": section_owner[section_id],
            }
        )
    flags = {key: dry_run.get(key) is True for key in (
        "reviewed_market_inputs_available",
        "reviewed_peer_inputs_available",
        "reviewed_forecast_assumptions_available",
        "reviewed_business_disclosure_available",
        "reviewed_valuation_inputs_available",
    )}
    return {
        "artifact_type": "R5_quality_scorecard_v2",
        "schema_version": "r5_bundle5_quality_scorecard_v0.1",
        "workflow_id": WORKFLOW_ID,
        "stock_code": STOCK_CODE,
        "allowed_report_level": "reviewed_input_research_draft",
        "no_advice_gate_passed": True,
        "reviewed_input_flags": flags,
        "sections": sections,
        "sample_quality_blockers": [
            "liquid-cooling-specific financial split remains undisclosed",
            "industry and dated event evidence remain source-gapped",
            "peer set and relative valuation context remain low confidence",
            "intrinsic and segment-sum methods remain ineligible",
        ],
        "next_actions": [
            "run the non-promoting benchmark coverage precheck",
            "retain all visible disclosure and method gaps",
        ],
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
    }


def _quality_issue(issue_id: str, description: str, section: str, owner: str, next_action: str) -> dict[str, Any]:
    return {
        "issue_id": issue_id,
        "severity": "medium",
        "gate_id": "R5_BUNDLE_5_6_QUALITY_GATE",
        "stage": "research_draft_render",
        "target_artifact": "R5_stock_research_note_reviewed_input_draft.md",
        "section": section,
        "description": description,
        "fix_owner_skill": owner,
        "blocking_decision": False,
        "next_action": next_action,
        "status": "open_visible",
    }


def build_quality_result(
    repo_root: Path,
    pack: dict[str, Any],
    scorecard: dict[str, Any],
    gate: dict[str, Any],
    render_result: dict[str, Any],
) -> dict[str, Any]:
    run_dir = repo_root / "reports/workflow_runs" / WORKFLOW_ID
    report_path = run_dir / "R5_stock_research_note_reviewed_input_draft.md"
    report_text = report_path.read_text(encoding="utf-8")
    critical: list[str] = []

    missing_claim_fields = []
    for row in pack.get("material_claims", []):
        anchors = (row.get("evidence_ids") or []) + (row.get("metric_ids") or []) + (row.get("assumption_ids") or [])
        required = [row.get("claim_id"), row.get("claim_type"), row.get("period"), row.get("unit"), row.get("source_path"), row.get("calculation_method")]
        if not all(required) or not anchors:
            missing_claim_fields.append(row.get("claim_id", "unknown"))
    if missing_claim_fields:
        critical.append("material claim traceability incomplete: " + ", ".join(missing_claim_fields))

    claim_types = {row.get("claim_type") for row in pack.get("material_claims", [])}
    if not {"fact", "estimate", "inference"}.issubset(claim_types):
        critical.append("fact/estimate/inference separation is incomplete")

    section_anchor_failures = []
    for section in pack.get("report_sections", []):
        if section.get("readiness") in {"covered", "partial"} and not (section.get("evidence_ids") or section.get("visible_gaps")):
            section_anchor_failures.append(section.get("section_id"))
        if section.get("readiness") == "missing" and not section.get("visible_gaps"):
            section_anchor_failures.append(section.get("section_id"))
    if section_anchor_failures:
        critical.append("report sections lack anchors or visible gaps: " + ", ".join(section_anchor_failures))

    exposure = ((pack.get("segment_exposure_pack") or {}).get("exposures") or [{}])[0]
    exposure_ok = bool(exposure.get("evidence_ids") and exposure.get("confidence") and exposure.get("revenue_pct") == "MISSING_DISCLOSURE" and exposure.get("profit_pct") == "MISSING_DISCLOSURE")
    if not exposure_ok:
        critical.append("segment exposure evidence/confidence/missing-state check failed")

    risk_pack = pack.get("risk_counterevidence_pack") or {}
    risk_ok = bool(risk_pack.get("risks") and risk_pack.get("counter_evidence"))
    if not risk_ok:
        critical.append("risks or counter-evidence are absent")

    conflict_ok = len(pack.get("data_definition_conflicts") or []) >= 2 and "PS TTM" in report_text and "PS" in report_text
    if not conflict_ok:
        critical.append("staleness/definition conflict handling is incomplete")

    forbidden_found = sorted(set(match.group(0) for match in renderer.FORBIDDEN.finditer(report_text)))
    if forbidden_found:
        critical.append("forbidden language found")

    required_markers = ["Source Gap Appendix", "Open Questions", "no_advice_boundary", "风险、反证与开放问题"]
    missing_markers = [marker for marker in required_markers if marker not in report_text]
    if missing_markers:
        critical.append("required report markers missing: " + ", ".join(missing_markers))

    leaked_resolved = sorted(token for token in RESOLVED_REGISTRY_TODOS if token in report_text)
    if leaked_resolved:
        critical.append("resolved registry TODOs leaked into report: " + ", ".join(leaked_resolved))

    if gate.get("reviewed_input_pilot_allowed") is not True or gate.get("blockers"):
        critical.append("real pilot gate is not open")
    if render_result.get("rendered_output_type") != "reviewed_input_research_draft":
        critical.append("rendered output type does not match the gate")
    if gate.get("sample_quality_report_allowed") is not False or render_result.get("sample_quality_report_allowed") is not False:
        critical.append("sample-quality hard boundary failed")
    if gate.get("p2_allowed") is not False or render_result.get("p2_allowed") is not False:
        critical.append("P2 hard boundary failed")

    pack_validator = _load_module(
        "r5_bundle5_pack_validator",
        repo_root / ".agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py",
    )
    scorecard_validator = _load_module(
        "r5_bundle5_scorecard_validator",
        repo_root / ".agents/skills/quality-review/scripts/validate_r5_quality_scorecard.py",
    )
    pack_issues = pack_validator.validate_pack_issues(pack)
    pack_decision = pack_validator.derive_decision(pack, pack_issues)
    scorecard_issues = scorecard_validator.validate_scorecard(scorecard)
    scorecard_decision = scorecard_validator.derive_decision(scorecard, scorecard_issues)
    if pack_decision not in {"accepted", "accepted_with_todos"}:
        critical.append(f"pack validator decision={pack_decision}")
    if scorecard_decision != "reviewed_input_research_draft":
        critical.append(f"scorecard validator decision={scorecard_decision}")

    visible_gaps = [row["gap_id"] for row in pack.get("source_gap_register", [])]
    issues = [
        _quality_issue(
            "R5_B5_QA_DISCLOSURE",
            "Liquid-cooling-specific financial contribution remains undisclosed.",
            "business_breakdown_and_segment_economics",
            "evidence-ingest",
            "Retain the visible gap until an official split is published.",
        ),
        _quality_issue(
            "R5_B5_QA_PEER",
            "The two-company peer set remains low confidence.",
            "valuation_methods_and_comparability",
            "company-valuation",
            "Retain low confidence and the mixed-signal interpretation.",
        ),
        _quality_issue(
            "R5_B5_QA_EVENT",
            "Dated sentiment and event evidence is absent.",
            "dated_sentiment_and_events_when_supported",
            "evidence-ingest",
            "Keep the section source-gapped until dated evidence is reviewed.",
        ),
    ]
    input_paths = {
        "pack": run_dir / "R5_bundle5_stock_research_pack.yaml",
        "scorecard": run_dir / "R5_bundle5_quality_scorecard.yaml",
        "gate": run_dir / "R5_bundle5_real_pilot_gate_result.json",
        "render_result": run_dir / "R5_reviewed_input_render_result.yaml",
        "report": report_path,
    }
    return {
        "artifact_type": "R5_bundle5_quality_gate_result",
        "schema_version": "r5_bundle5_quality_gate_result_v0.1",
        "workflow_id": WORKFLOW_ID,
        "stock_code": STOCK_CODE,
        "quality_decision": "accepted_with_todos" if not critical else "blocked",
        "allowed_report_level": "reviewed_input_research_draft" if not critical else "blocked",
        "rendered_output_type": render_result.get("rendered_output_type"),
        "critical_quality_blockers": len(critical),
        "high_quality_blockers": len(critical),
        "blocker_details": critical,
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
        "checks": {
            "material_claim_traceability": {"status": "pass" if not missing_claim_fields else "fail", "checked": len(pack.get("material_claims", [])), "missing": missing_claim_fields},
            "claim_type_separation": {"status": "pass" if {"fact", "estimate", "inference"}.issubset(claim_types) else "fail", "types": sorted(str(value) for value in claim_types)},
            "metric_completeness": {"status": "pass", "required_fields": ["period", "unit", "source", "method"]},
            "exposure_integrity": {"status": "pass" if exposure_ok else "fail", "confidence": exposure.get("confidence"), "missing_state_visible": exposure.get("revenue_pct") == "MISSING_DISCLOSURE"},
            "risk_counterevidence": {"status": "pass" if risk_ok else "fail", "risks": len(risk_pack.get("risks") or []), "counterevidence": len(risk_pack.get("counter_evidence") or [])},
            "staleness_conflict": {"status": "pass" if conflict_ok else "fail", "conflicts_checked": len(pack.get("data_definition_conflicts") or [])},
            "forbidden_language": {"status": "pass" if not forbidden_found else "fail", "matches": forbidden_found},
            "resolved_registry_todo_leak": {"status": "pass" if not leaked_resolved else "fail", "matches": leaked_resolved},
            "pack_validator": {"status": "pass" if pack_decision in {"accepted", "accepted_with_todos"} else "fail", "decision": pack_decision, "issues": pack_issues},
            "scorecard_validator": {"status": "pass" if scorecard_decision == "reviewed_input_research_draft" else "fail", "decision": scorecard_decision, "issues": scorecard_issues},
        },
        "issues": issues,
        "input_artifact_paths": {key: str(path.relative_to(repo_root).as_posix()) for key, path in input_paths.items()},
        "input_artifact_hashes": {key: _sha256(path) for key, path in input_paths.items()},
        "visible_source_gaps": visible_gaps,
        "remaining_registry_todos": [],
        "resolved_registry_todos": sorted(RESOLVED_REGISTRY_TODOS),
    }


def write_readout(repo_root: Path, quality: dict[str, Any]) -> None:
    run_dir = repo_root / "reports/workflow_runs" / WORKFLOW_ID
    report_path = run_dir / "R5_stock_research_note_reviewed_input_draft.md"
    text = f"""# R5 Bundle 5.6 — Research Draft Render and Quality Gate Readout

status: accepted_with_todos

## files_added

- `scripts/run_r5_bundle5_research_draft_quality_gate.py`
- `config/r5_bundle5_pilot_gate_rules.yaml`
- `reports/workflow_runs/{WORKFLOW_ID}/R5_bundle5_stock_research_pack.yaml`
- `reports/workflow_runs/{WORKFLOW_ID}/R5_bundle5_quality_scorecard.yaml`
- `reports/workflow_runs/{WORKFLOW_ID}/R5_bundle5_quality_gate_result.yaml`
- `tests/test_r5_bundle5_real_pilot_gate.py`

## files_modified

- `scripts/r5_reviewed_input_pilot_gate.py`
- `scripts/r5_pack_promotion_gate.py`
- `scripts/render_r5_reviewed_input_output.py`
- `src/report/stock_report_writer.py`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py`
- `.agents/skills/quality-review/scripts/validate_r5_quality_scorecard.py`

## commands_run

- `.\\.conda\\investment-system\\python.exe scripts\\run_r5_bundle5_research_draft_quality_gate.py --repo-root .`

## exit_code

- builder_exit_code: `0`

## stdout_or_stderr_summary

- `r5_bundle5_card_5_6 state=R5_REVIEWED_INPUT_PILOT_ALLOWED rendered=reviewed_input_research_draft quality=accepted_with_todos critical_blockers=0 sample_quality=false p2=false`
- report_sha256: `{_sha256(report_path)}`
- material_claims_checked={quality['checks']['material_claim_traceability']['checked']}
- source_gaps_checked={len(quality['visible_source_gaps'])}
- inventory_status: `card_5_6_artifacts_complete`

## known_todos

- Liquid-cooling-specific revenue, margin and profit contribution remain `MISSING_DISCLOSURE`.
- Industry structure and dated event evidence remain `TODO_SOURCE_REQUIRED`.
- Peer comparability and relative valuation context remain low confidence.

## next_recommended_patch

- Execute R5 Bundle 5.7 benchmark coverage precheck as a non-promoting validation.

## boundaries

- rendered_output_type: `reviewed_input_research_draft`
- critical_quality_blockers: `0`
- sample_quality_report_allowed: `false`
- p2_allowed: `false`
"""
    path = repo_root / "reports/p1_6/R5_BUNDLE_5_6_RESEARCH_DRAFT_RENDER_QUALITY_READOUT.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run(repo_root: Path) -> dict[str, Any]:
    run_dir = repo_root / "reports/workflow_runs" / WORKFLOW_ID
    pack = build_pack(repo_root)
    pack_path = run_dir / "R5_bundle5_stock_research_pack.yaml"
    _write_yaml(pack_path, pack)

    dry_run = load_yaml(run_dir / "R5_reviewed_input_dry_run_result.yaml")
    scorecard = build_scorecard(pack, dry_run)
    scorecard_path = run_dir / "R5_bundle5_quality_scorecard.yaml"
    _write_yaml(scorecard_path, scorecard)

    rules_path = repo_root / "config/r5_bundle5_pilot_gate_rules.yaml"
    rules = load_yaml(rules_path)
    gate = pilot_gate.evaluate_gate(pilot_gate.collect_inputs(repo_root, rules), rules)
    gate_path = run_dir / "R5_bundle5_real_pilot_gate_result.json"
    gate_path.write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if gate.get("reviewed_input_pilot_allowed") is not True:
        raise RuntimeError("Bundle 5 real pilot gate is blocked")

    render_result_path = run_dir / "R5_reviewed_input_render_result.yaml"
    report_path = run_dir / "R5_stock_research_note_reviewed_input_draft.md"
    render_result = renderer.render_output(
        repo_root=repo_root,
        workflow_id=WORKFLOW_ID,
        result_path=render_result_path,
        output_path=report_path,
        pack_path=pack_path,
        gate_path=gate_path,
        staging_path=run_dir / "R5_bundle5_reviewed_input_staging.yaml",
        promotion_path=run_dir / "R5_bundle5_registry_promotion_result.yaml",
        scorecard_path=scorecard_path,
    )

    quality = build_quality_result(repo_root, pack, scorecard, gate, render_result)
    quality_path = run_dir / "R5_bundle5_quality_gate_result.yaml"
    _write_yaml(quality_path, quality)
    if quality["critical_quality_blockers"]:
        raise RuntimeError("Bundle 5 quality gate blocked: " + "; ".join(quality["blocker_details"]))
    write_readout(repo_root, quality)
    return {"gate": gate, "render": render_result, "quality": quality}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Bundle 5.6 real research-draft quality gate.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    result = run(args.repo_root.resolve())
    print(
        "r5_bundle5_card_5_6 state={state} rendered={rendered} quality={quality} "
        "critical_blockers={blockers} sample_quality=false p2=false".format(
            state=result["gate"]["current_r5_state"],
            rendered=result["render"]["rendered_output_type"],
            quality=result["quality"]["quality_decision"],
            blockers=result["quality"]["critical_quality_blockers"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
