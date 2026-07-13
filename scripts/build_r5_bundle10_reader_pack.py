from __future__ import annotations

import argparse
import csv
import math
from datetime import date
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence

import yaml


DEFAULT_WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
BUILD_DATE = "2026-07-13"
TECHNICAL_EVIDENCE = "ev_structured_market_data_002837_20260713_3145e0"
MARKET_EVIDENCE = "ev_structured_market_data_002837_20260713_f8cc52"
ANNUAL_EVIDENCE = "ev_annual_report_002837_20260421_2cbfc5"
Q1_EVIDENCE = "ev_quarterly_report_002837_20260421_2f00c7"


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def write_yaml(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(dict(data), allow_unicode=True, sort_keys=False), encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def money_100m(value: float | int) -> str:
    return f"{float(value) / 100_000_000:.2f}"


def pct(value: float | int, digits: int = 1) -> str:
    return f"{float(value):.{digits}f}%"


def multiple(value: float | int, digits: int = 1) -> str:
    return f"{float(value):.{digits}f}x"


def metric_index(rows: Sequence[Mapping[str, Any]], metric_name: str) -> dict[str, float]:
    return {
        str(row["period"]): float(row["value"])
        for row in rows
        if row.get("metric_name") == metric_name and row.get("value") is not None
    }


def number(value: float | int | None, unit: str, source_id: str | None = None, missing_reason: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"value": value, "unit": unit}
    if source_id:
        result["source_id"] = source_id
    if missing_reason:
        result["missing_reason"] = missing_reason
    return result


def return_over_window(rows: Sequence[Mapping[str, str]], sessions: int) -> float | None:
    if len(rows) <= sessions:
        return None
    latest = float(rows[-1]["close"])
    base = float(rows[-sessions - 1]["close"])
    return round((latest / base - 1) * 100, 4)


def build_technical_pack(repo_root: Path, run: Path) -> dict[str, Any]:
    source = load_yaml(run / "R5_bundle8b_technical_snapshot.yaml")
    series_path = repo_root / str(source["price_series_source"])
    rows = [row for row in read_csv(series_path) if row.get("tradestatus") == "1"]
    rows.sort(key=lambda row: row["date"])
    if len(rows) < 200:
        raise ValueError("technical pack requires at least 200 dated trading rows")
    current = rows[-1]
    current_close = float(current["close"])
    current_volume = float(current["volume"])
    volumes = sorted(float(row["volume"]) for row in rows)
    percentile = 100 * sum(value <= current_volume for value in volumes) / len(volumes)
    year_start_candidates = [row for row in rows if row["date"] < "2026-01-01"]
    ytd_base = float(year_start_candidates[-1]["close"]) if year_start_candidates else None
    ytd_return = round((current_close / ytd_base - 1) * 100, 4) if ytd_base else None
    high_52w = max(float(row["high"]) for row in rows)
    low_52w = min(float(row["low"]) for row in rows)
    daily = source["windows"]["daily"]
    support = float(source["support"])
    resistance = float(source["resistance"])
    judgement = (
        f"截至{source['as_of_date']}，收盘价略高于MA5，但低于MA10、MA20和MA60；"
        f"近20个交易日上涨{daily['pct_chg_20d']:.1f}%，近60个交易日下降{abs(daily['pct_chg_60d']):.1f}%，"
        "短期反弹与中期压力并存。该结论只描述市场状态。"
    )
    pack = {
        "artifact_type": "R5_technical_market_pack",
        "schema_version": "r5_technical_market_v0.2",
        "status": "ready_with_todos",
        "as_of_date": source["as_of_date"],
        "source_path": source["price_series_source"],
        "current_price": number(current_close, "CNY_per_share", TECHNICAL_EVIDENCE),
        "return_1m": number(return_over_window(rows, 21), "pct", TECHNICAL_EVIDENCE),
        "return_3m": number(return_over_window(rows, 63), "pct", TECHNICAL_EVIDENCE),
        "return_6m": number(return_over_window(rows, 126), "pct", TECHNICAL_EVIDENCE),
        "return_12m": number(return_over_window(rows, min(249, len(rows) - 1)), "pct", TECHNICAL_EVIDENCE),
        "ytd_return": number(ytd_return, "pct", TECHNICAL_EVIDENCE, "INSUFFICIENT_YEAR_START" if ytd_return is None else None),
        "52w_high": number(round(high_52w, 4), "CNY_per_share", TECHNICAL_EVIDENCE),
        "52w_low": number(round(low_52w, 4), "CNY_per_share", TECHNICAL_EVIDENCE),
        "MA5": number(float(daily["ma5"]), "CNY_per_share", TECHNICAL_EVIDENCE),
        "MA10": number(float(daily["ma10"]), "CNY_per_share", TECHNICAL_EVIDENCE),
        "MA20": number(float(daily["ma20"]), "CNY_per_share", TECHNICAL_EVIDENCE),
        "MA60": number(float(daily["ma60"]), "CNY_per_share", TECHNICAL_EVIDENCE),
        "turnover": number(float(current["turn"]), "pct", TECHNICAL_EVIDENCE),
        "volume_percentile": number(round(percentile, 2), "pct_of_250_sessions", TECHNICAL_EVIDENCE),
        "support_levels": [
            {"level": support, "basis": "recent_range_computed_support", "source_id_or_missing_reason": TECHNICAL_EVIDENCE}
        ],
        "resistance_levels": [
            {"level": resistance, "basis": "recent_range_computed_resistance", "source_id_or_missing_reason": TECHNICAL_EVIDENCE}
        ],
        "market_state_judgement": judgement,
        "limitations": [
            "Unadjusted daily series; corporate-action impact has not been independently normalized.",
            "Support and resistance are descriptive range statistics, not action levels.",
        ],
        "no_advice_boundary": True,
    }
    write_yaml(run / "R5_bundle10_technical_market_pack.yaml", pack)
    return pack


def build_sentiment_event_pack(run: Path, technical: Mapping[str, Any]) -> dict[str, Any]:
    event = load_yaml(run / "market_event_pack.yaml")
    future = event["future_event_calendar"][0]
    analyst = event["analyst_estimate_context"]["latest_2026_reports"]
    company_summary = (
        "公司情绪只能以低置信预期差描述：两家近期机构的每股收益中点显著高于内部基准模型，"
        "同时近20日与近60日收益方向相反，说明短期交易热度和中期基本面预期并不一致。"
    )
    pack = {
        "artifact_type": "R5_sentiment_event_pack",
        "schema_version": "r5_sentiment_event_v0.3",
        "status": "ready_with_todos",
        "as_of_date": technical["as_of_date"],
        "information_cutoff_date": technical["as_of_date"],
        "retrieved_at": event["as_of_date"],
        "generated_at": BUILD_DATE,
        "macro_sentiment": [
            {
                "summary": "宏观情绪缺少同日、可审阅且与公司传导路径一致的结构化指标，因此不作方向判断。",
                "missing_reason": "TODO_SOURCE_REQUIRED",
                "claim_type": "unknown",
            }
        ],
        "industry_sentiment": [
            {
                "summary": "行业需求基础有独立技术与政策证据，但这些材料不是市场情绪指标；行业情绪保持未定。",
                "source_id": "industry_report_caict_green_computing_2025_59947f",
                "claim_type": "inference",
            }
        ],
        "company_sentiment": [
            {
                "summary": company_summary,
                "source_id": event["analyst_estimate_context"]["source_evidence_id"],
                "claim_type": "analyst_view_and_inference",
                "technical_source_id": TECHNICAL_EVIDENCE,
                "two_broker_eps_midpoint": {
                    period: values["eps_midpoint"] for period, values in analyst["forecast_years"].items()
                },
            }
        ],
        "catalyst_calendar": [
            {
                "event_date": future["planned_date"],
                "event_name": "2026年半年度报告计划披露窗口",
                "impact_path": "分业务收入和产品组合披露将影响增长归因，毛利率与费用率影响盈利桥，应收、存货和经营现金流影响现金转化判断。",
                "verification_metric": "宽口径业务收入、任何同定义液冷收入更新、毛利率、应收、存货与经营现金流",
                "counterevidence_condition": "若正式公告日期变化，或收入增长未伴随毛利率与现金流改善，则当前基准情景需要下修并重新估值。",
                "source_id_or_missing_reason": future["source_evidence_id"],
                "date_status": future["status"],
                "claim_type": future["claim_type"],
            }
        ],
        "event_scenario_matrix": {
            "base": {
                "status": "宽口径收入按模型增长，毛利率和现金流逐步改善，液冷独立口径仍未披露。",
                "source_id_or_missing_reason": "b9_base_case_net_profit_bridge",
            },
            "upside": {
                "status": "分业务披露增强且毛利率、回款同时改善，需要上修业务线假设。",
                "source_id_or_missing_reason": "b9_bull_case_net_profit_bridge",
            },
            "downside": {
                "status": "竞争、项目验收或回款压力使利润与现金流低于基准，需要转入下行情景。",
                "source_id_or_missing_reason": "b9_bear_case_net_profit_bridge",
            },
        },
        "technical_context": {
            "as_of_date": technical["as_of_date"],
            "market_state_judgement": technical["market_state_judgement"],
        },
        "no_advice_boundary": True,
    }
    write_yaml(run / "R5_bundle10_sentiment_event_pack.yaml", pack)
    return pack


def build_gate_forecast(forecast: Mapping[str, Any], bridge: Mapping[str, Any]) -> dict[str, Any]:
    base_rows = []
    for period, row in bridge["scenarios"]["base_case"].items():
        values = dict(row["bridge"])
        values["period"] = period
        values["gross_margin_pct"] = values["gross_margin"]
        base_rows.append(values)
    drivers = [
        "business_line_room_cooling_revenue_growth",
        "business_line_cabinet_cooling_revenue_growth",
        "business_line_other_revenue_growth",
        "business_line_gross_margin",
        "sales_expense_ratio",
        "admin_expense_ratio",
        "r&d_expense_ratio",
        "finance_expense_ratio",
        "tax_rate",
        "minority_profit_share",
        "nwc_to_revenue",
        "capex_to_revenue",
    ]
    return {
        "artifact_type": "R5_bundle10_reader_gate_forecast_adapter",
        "schema_version": "v0.1",
        "base_case_bridge": base_rows,
        "scenarios": {name: {"status": row["status"]} for name, row in forecast["scenarios"].items()},
        "driver_assumptions": [{"driver": driver} for driver in drivers],
        "consensus_used": True,
        "source_forecast_model": "segment_forecast_model.yaml",
        "source_forecast_bridge": "forecast_bridge.yaml",
    }


def build_gate_valuation(run: Path, forecast: Mapping[str, Any]) -> dict[str, Any]:
    pack = load_yaml(run / "R5_bundle9_valuation_pack.yaml")
    peer_rows = read_csv(run / "peer_market_snapshot.csv")
    peer_matrix = [
        {
            "stock_code": row["peer_stock_code"],
            "name": row["peer_company"],
            "pe_ttm": float(row["pe_ttm"]),
            "valuation_date": row["as_of_date"],
            "denominator": "TTM",
            "selection_reason": row["peer_selection_reason"],
            "comparability_limitation": row["limitations"],
            "confidence": "low",
            "source_status": "reviewed",
        }
        for row in peer_rows
    ]
    base_table = forecast["scenarios"]["base_case"]["forecast_table"]
    scenario_context = [
        {
            "period": period,
            "eps": row["eps"]["value"],
            "forward_pe": round(pack["market_snapshot"]["market_cap"]["value"] / row["net_profit_attributable"]["value"], 4),
        }
        for period, row in base_table.items()
    ]
    market = pack["market_snapshot"]
    return {
        "artifact_type": "R5_bundle10_reader_gate_valuation_adapter",
        "schema_version": "v0.1",
        "as_of_date": market["as_of_date"],
        "dated_snapshot": {
            "price_cny": market["current_price"]["value"],
            "market_cap_cny": market["market_cap"]["value"],
            "pe_ttm": market["pe_ttm"]["value"],
            "pb": market["pb"]["value"],
            "ps_ttm": market["ps"]["value"],
            "denominator_control": "PE and PS use TTM denominators; forward PE uses dated market cap and Bundle 9 scenario profit.",
        },
        "peer_matrix": peer_matrix,
        "scenario_context": scenario_context,
        "method_eligibility": [
            {"method": "static_multiples", "status": "active"},
            {"method": "dynamic_pe", "status": "active"},
            {"method": "peer_context", "status": "active_with_comparability_limits"},
            {"method": "reverse_valuation", "status": "active"},
            {"method": "scenario_valuation", "status": "active"},
            {"method": "dcf", "status": "inactive", "reason": "discount and terminal inputs unavailable"},
            {"method": "sotp", "status": "inactive", "reason": "standalone segment economics unavailable"},
        ],
        "reverse_valuation": load_yaml(run / "reverse_valuation.yaml"),
        "scenario_valuation": load_yaml(run / "scenario_valuation.yaml"),
    }


def paragraph(text: str, refs: Sequence[str]) -> dict[str, Any]:
    return {"type": "paragraph", "text": text, "refs": list(refs)}


def bullets(items: Sequence[tuple[str, Sequence[str]]]) -> dict[str, Any]:
    return {
        "type": "bullets",
        "items": [{"text": text, "refs": list(refs)} for text, refs in items],
    }


def table(headers: Sequence[str], rows: Sequence[Sequence[Any]], note: str, refs: Sequence[str]) -> dict[str, Any]:
    return {
        "type": "table",
        "headers": list(headers),
        "rows": [list(row) for row in rows],
        "note": note,
        "refs": list(refs),
    }


def analysis_units(analysis: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(row["section"]): row
        for row in analysis.get("analysis_units") or []
        if isinstance(row, Mapping)
    }


def build_traceability_records(run: Path) -> list[dict[str, Any]]:
    return [
        {
            "display_reference_id": "E1", "claim_type": "fact_and_management_comment",
            "claim_summary": "公司业务范围、2025年度财务与宽口径产品披露", "period": "2025A", "unit": "CNY/pct",
            "raw_evidence_ids": [ANNUAL_EVIDENCE], "source_category": "issuer",
            "source_path": "data/processed/text/002837/cninfo_2025_annual_report_full_002837_2026-04-21.txt",
            "method": "direct_review_and_arithmetic", "confidence": "high",
            "limitation": "公司整体与宽口径产品线不能替代液冷独立经济性", "reviewer_state": "accepted", "conflict_or_staleness_status": "current",
        },
        {
            "display_reference_id": "E2", "claim_type": "fact_and_inference",
            "claim_summary": "2026年一季度财务、利润率与现金流背离", "period": "2026Q1", "unit": "CNY/pct",
            "raw_evidence_ids": [Q1_EVIDENCE], "source_category": "issuer",
            "source_path": "data/processed/text/002837/szse_2026_q1_report_002837_2026-04-21.txt",
            "method": "direct_review_and_arithmetic", "confidence": "high",
            "limitation": "背离原因尚未由连续季度或附注明确解释", "reviewer_state": "accepted", "conflict_or_staleness_status": "current",
        },
        {
            "display_reference_id": "E3", "claim_type": "fact_and_inference",
            "claim_summary": "2025年宽产品线收入、毛利与集中度", "period": "2025A", "unit": "CNY/pct",
            "raw_evidence_ids": [ANNUAL_EVIDENCE], "source_category": "issuer",
            "source_path": f"reports/workflow_runs/{run.name}/R5_bundle5_business_breakdown_candidate.yaml",
            "method": "reported_values_and_residual_reconciliation", "confidence": "high",
            "limitation": "液冷没有独立分项", "reviewer_state": "accepted", "conflict_or_staleness_status": "current",
        },
        {
            "display_reference_id": "E4", "claim_type": "management_comment",
            "claim_summary": "2024年液冷技术相关收入约三亿元及累计交付口径", "period": "2024A/2025-03", "unit": "CNY/GW",
            "raw_evidence_ids": ["ev_official_disclosure_002837_20250423_e78396"], "source_category": "company_operating",
            "source_path": "data/processed/text/ev_official_disclosure_002837_20250423_e78396.md",
            "method": "official_IR_review", "confidence": "medium",
            "limitation": "近似管理层口径，不是审计分部数据", "reviewer_state": "accepted_with_boundary", "conflict_or_staleness_status": "current",
        },
        {
            "display_reference_id": "E5", "claim_type": "management_comment",
            "claim_summary": "项目验收、收入确认、毛利与回款机制", "period": "2025-04", "unit": None,
            "raw_evidence_ids": ["ev_official_disclosure_002837_20250428_108da3"], "source_category": "company_operating",
            "source_path": "data/processed/text/ev_official_disclosure_002837_20250428_108da3.md",
            "method": "official_IR_review", "confidence": "medium",
            "limitation": "回款周期为公司宽口径平均评论，不能替代液冷项目现金数据", "reviewer_state": "accepted_with_boundary", "conflict_or_staleness_status": "current",
        },
        {
            "display_reference_id": "E6", "claim_type": "management_comment",
            "claim_summary": "项目验收周期、需求机制与经营风险", "period": "2025-05", "unit": None,
            "raw_evidence_ids": ["ev_official_disclosure_002837_20250521_1b4421"], "source_category": "company_operating",
            "source_path": "data/processed/text/ev_official_disclosure_002837_20250521_1b4421.md",
            "method": "official_IR_review", "confidence": "medium",
            "limitation": "管理层评论需由实际交付和回款验证", "reviewer_state": "accepted_with_boundary", "conflict_or_staleness_status": "current",
        },
        {
            "display_reference_id": "E7", "claim_type": "analyst_view",
            "claim_summary": "高密度算力与多技术路线的行业研究观点", "period": "2024-2025", "unit": None,
            "raw_evidence_ids": ["industry_report_caict_green_computing_2025_59947f"], "source_category": "industry",
            "source_path": "data/raw/industry_reports/industry_report_caict_green_computing_2025_59947f.pdf",
            "method": "independent_industry_review", "confidence": "medium",
            "limitation": "行业证据不能证明单一公司收入或份额", "reviewer_state": "accepted", "conflict_or_staleness_status": "current",
        },
        {
            "display_reference_id": "E8", "claim_type": "fact",
            "claim_summary": "数据中心PUE政策约束与替代制冷路线", "period": "2024-2025", "unit": "PUE",
            "raw_evidence_ids": ["policy_ndrc_green_data_center_20240723_30d310"], "source_category": "industry",
            "source_path": "data/raw/regulator_policy/policy_ndrc_green_data_center_20240723_30d310.pdf",
            "method": "policy_document_review", "confidence": "high",
            "limitation": "政策支持多种高效制冷方案", "reviewer_state": "accepted", "conflict_or_staleness_status": "current",
        },
        {
            "display_reference_id": "E9", "claim_type": "fact_and_inference",
            "claim_summary": "四家同业经营范围与业务可比性边界", "period": "2025A", "unit": "CNY/pct",
            "raw_evidence_ids": [
                "annual_report_300499_gaolan_2025_122516", "annual_report_300731_cotran_2025_122523",
                "semiannual_report_301018_shenling_2025_122461", "semiannual_report_300602_frd_2025_122450",
            ],
            "source_category": "peer", "source_path": f"reports/workflow_runs/{run.name}/peer_operating_evidence_pack.yaml",
            "method": "same_period_peer_context_with_scope_limits", "confidence": "low_for_comparability",
            "limitation": "液冷纯度、产品组合、客户与确认节奏不同，不形成排名", "reviewer_state": "accepted_with_limitations", "conflict_or_staleness_status": "current",
        },
        {
            "display_reference_id": "E10", "claim_type": "estimate",
            "claim_summary": "2026E至2028E业务线预测与利润现金流桥", "period": "2026E-2028E", "unit": "CNY/pct",
            "raw_evidence_ids": [ANNUAL_EVIDENCE, Q1_EVIDENCE], "source_category": "issuer",
            "source_path": f"reports/workflow_runs/{run.name}/forecast_bridge.yaml",
            "method": "bottom_up_three_scenario_model", "confidence": "medium",
            "limitation": "模型估计，不是发行人指引；液冷不单列", "reviewer_state": "accepted_model_input", "conflict_or_staleness_status": "current",
        },
        {
            "display_reference_id": "E11", "claim_type": "fact_and_inference",
            "claim_summary": "2026年7月10日价格与250日技术状态", "period": "2026-07-10", "unit": "CNY/pct",
            "raw_evidence_ids": [TECHNICAL_EVIDENCE], "source_category": "market",
            "source_path": f"reports/workflow_runs/{run.name}/R5_bundle10_technical_market_pack.yaml",
            "method": "dated_market_snapshot_and_descriptive_statistics", "confidence": "medium",
            "limitation": "未复权序列只描述市场状态", "reviewer_state": "accepted_with_limitations", "conflict_or_staleness_status": "current",
        },
        {
            "display_reference_id": "E12", "claim_type": "analyst_view",
            "claim_summary": "两家近期机构每股收益中点与内部基准差异", "period": "2026E-2028E", "unit": "CNY_per_share",
            "raw_evidence_ids": ["ev_third_party_research_002837_20260713_20f610"], "source_category": "consensus",
            "source_path": "data/processed/normalized/eastmoney_report_metadata_002837_2026-07-13_20f6105e.csv",
            "method": "two_distinct_broker_midpoint", "confidence": "low",
            "limitation": "样本仅两家且股本口径未独立核验", "reviewer_state": "accepted_with_limitations", "conflict_or_staleness_status": "current",
        },
        {
            "display_reference_id": "E13", "claim_type": "estimate",
            "claim_summary": "2026年半年度报告计划披露窗口与验证指标", "period": "2026-08-25", "unit": None,
            "raw_evidence_ids": ["ev_structured_financial_data_002837_20260713_a177f1"], "source_category": "other",
            "source_path": "data/processed/normalized/tushare_disclosure_date_002837_2026-07-13_a177f1cf.csv",
            "method": "scheduled_date_snapshot", "confidence": "medium",
            "limitation": "计划日期需由发行人或交易所公告确认", "reviewer_state": "accepted_as_estimate", "conflict_or_staleness_status": "current",
        },
        {
            "display_reference_id": "E14", "claim_type": "inference",
            "claim_summary": "动态、情景与反向估值及方法适用性", "period": "2026-07-10/2027E", "unit": "CNY/multiple",
            "raw_evidence_ids": [MARKET_EVIDENCE, ANNUAL_EVIDENCE], "source_category": "market",
            "source_path": f"reports/workflow_runs/{run.name}/R5_bundle9_valuation_pack.yaml",
            "method": "dated_market_cap_scenario_and_reverse_valuation", "confidence": "low_to_medium",
            "limitation": "倍数为压力测试；内在价值方法输入不足", "reviewer_state": "accepted_with_limitations", "conflict_or_staleness_status": "current",
        },
        {
            "display_reference_id": "E15", "claim_type": "metric_statement",
            "claim_summary": "四家同业2026年7月10日PE、PB与PS快照", "period": "2026-07-10", "unit": "multiple",
            "raw_evidence_ids": [
                "ev_structured_market_data_300499_20260713_57cd0b",
                "ev_structured_market_data_300731_20260713_f4f0c0",
                "ev_structured_market_data_301018_20260713_cc0ee3",
                "ev_structured_market_data_300602_20260713_e6104c",
            ],
            "source_category": "market", "source_path": f"reports/workflow_runs/{run.name}/R5_bundle9_valuation_pack.yaml",
            "method": "same_date_peer_market_snapshot", "confidence": "low_for_comparability",
            "limitation": "结构化市场快照仅支持公司级倍数；业务纯度不足以形成排名", "reviewer_state": "accepted_with_limitations", "conflict_or_staleness_status": "current",
        },
        {
            "display_reference_id": "E16", "claim_type": "metric_statement",
            "claim_summary": "中国信通院报告中的标准机架数量与单机柜功率密度", "period": "2024", "unit": "rack/kW",
            "raw_evidence_ids": ["industry_report_caict_green_computing_2025_59947f"], "source_category": "industry",
            "source_path": "data/raw/industry_reports/industry_report_caict_green_computing_2025_59947f.pdf",
            "method": "independent_industry_metric_review", "confidence": "medium",
            "limitation": "第三方研究报告口径，不是官方统计或公司经营事实", "reviewer_state": "accepted_with_boundary", "conflict_or_staleness_status": "current",
        },
        {
            "display_reference_id": "E17", "claim_type": "estimate",
            "claim_summary": "预测毛利率与营运资本敏感性", "period": "2026E-2028E", "unit": "CNY/pct",
            "raw_evidence_ids": [ANNUAL_EVIDENCE, Q1_EVIDENCE], "source_category": "issuer",
            "source_path": f"reports/workflow_runs/{run.name}/forecast_sensitivity.csv",
            "method": "one_factor_forecast_sensitivity", "confidence": "medium",
            "limitation": "单变量压力测试，不表示情景概率", "reviewer_state": "accepted_model_input", "conflict_or_staleness_status": "current",
        },
        {
            "display_reference_id": "E18", "claim_type": "metric_statement",
            "claim_summary": "英维克2026年7月10日价格、市值与静态估值快照", "period": "2026-07-10", "unit": "CNY/multiple",
            "raw_evidence_ids": [MARKET_EVIDENCE], "source_category": "market",
            "source_path": f"reports/workflow_runs/{run.name}/R5_bundle9_valuation_pack.yaml",
            "method": "same_date_subject_market_snapshot", "confidence": "medium",
            "limitation": "静态倍数与内部预测分母不可混用", "reviewer_state": "accepted_with_limitations", "conflict_or_staleness_status": "current",
        },
    ]


def build_reader_pack(
    run: Path,
    technical: Mapping[str, Any],
    sentiment: Mapping[str, Any],
) -> dict[str, Any]:
    stock = load_yaml(run / "stock_analysis_pack.yaml")["metadata"]
    analysis = load_yaml(run / "analysis_pack_v2.yaml")
    units = analysis_units(analysis)
    history = load_yaml(run / "R5_bundle5_financial_history_candidate.yaml")
    business = load_yaml(run / "R5_bundle5_business_breakdown_candidate.yaml")
    forecast = load_yaml(run / "segment_forecast_model.yaml")
    valuation = load_yaml(run / "R5_bundle9_valuation_pack.yaml")
    scenario_valuation = load_yaml(run / "scenario_valuation.yaml")
    reverse = load_yaml(run / "reverse_valuation.yaml")
    peer_rows = read_csv(run / "peer_market_snapshot.csv")

    revenue = metric_index(history["income_statement"], "revenue")
    profit = metric_index(history["income_statement"], "net_profit_attributable")
    ocf = metric_index(history["cashflow_statement"], "operating_cashflow")
    key_gm = metric_index(history["key_metrics"], "gross_margin")
    financial_rows = [
        [period, money_100m(revenue[period]), money_100m(profit[period]), money_100m(ocf[period]), pct(key_gm[period], 1) if period in key_gm else "未单列"]
        for period in ("2023A", "2024A", "2025A", "2026Q1")
    ]
    business_rows = [
        [
            row["reported_name"], money_100m(row["revenue"]["value"]), pct(row["revenue_pct"]["value"], 2),
            pct(row["gross_margin"]["value"], 2) if row["gross_margin"]["value"] is not None else "未单列",
        ]
        for row in business["business_lines"]
        if row.get("revenue", {}).get("value") is not None
    ]
    base = forecast["scenarios"]["base_case"]["forecast_table"]
    forecast_rows = [
        [period, money_100m(row["revenue"]["value"]), pct(row["gross_margin"]["value"], 1), money_100m(row["net_profit_attributable"]["value"]), f"{row['eps']['value']:.3f}"]
        for period, row in base.items()
    ]
    dynamic = {
        period: valuation["market_snapshot"]["market_cap"]["value"] / row["net_profit_attributable"]["value"]
        for period, row in base.items()
    }
    peer_table_rows = [
        [row["peer_company"], row["peer_stock_code"], multiple(float(row["pe_ttm"])), multiple(float(row["pb_lf"])), multiple(float(row["ps_ttm"])), "业务结构和液冷纯度不可直接横比"]
        for row in peer_rows
    ]
    scenario_rows = []
    for name in ("bear", "base", "bull"):
        row = scenario_valuation["scenarios"][name]
        profit_anchor = row["profit_anchor"]["value"]
        low_m = row["multiple_range"]["low"]["value"]
        high_m = row["multiple_range"]["high"]["value"]
        low_cap = row["implied_market_cap_range"]["low"]["value"]
        high_cap = row["implied_market_cap_range"]["high"]["value"]
        scenario_rows.append([name, money_100m(profit_anchor), f"{low_m:.0f}x-{high_m:.0f}x", f"{money_100m(low_cap)}-{money_100m(high_cap)}"])

    core = units["core_thesis"]
    financial = units["financial_quality"]
    driver = units["business_driver"]
    economics = units["segment_economics"]
    industry = units["industry_context"]
    competition = units["competitive_position"]
    risk = units["risk_counterevidence"]

    market = valuation["market_snapshot"]
    t = technical
    event = sentiment["catalyst_calendar"][0]
    sections = [
        {
            "section_id": "executive_summary",
            "judgment": core["judgment"],
            "judgment_refs": ["E1", "E4"],
            "blocks": [
                paragraph(financial["trend"], ["E1", "E2"]),
                paragraph(
                    "核心矛盾是产品平台与需求证据在增强，但利润率、现金转化和液冷独立披露尚未同步。"
                    "这意味着研究判断不能只看收入增长：若后续毛利率与经营现金流不能改善，估值所要求的盈利修复就缺少财务支撑；"
                    "若宽口径业务增长、分项披露和回款同时改善，当前谨慎判断才有条件上调。",
                    ["E2", "E4", "E10", "E14"],
                ),
                paragraph(
                    "后续观察重点依次为半年度报告中的产品与收入口径、毛利率和费用率、应收与存货、经营现金流、"
                    "实际结果相对三情景模型的偏差，以及同日估值变化。任何一个环节出现反证，都应触发模型重估。",
                    ["E10", "E13", "E14", "E18"],
                ),
            ],
        },
        {
            "section_id": "company_context_and_scope",
            "judgment": (
                "公司的可验证边界是数据中心温控及端到端液冷产品能力，尚不能延伸到液冷独立收入、毛利或公司增长归因；"
                "本节仅讨论已披露产品、管理层近似口径与后续证伪条件。"
            ),
            "judgment_refs": ["E1", "E3"],
            "blocks": [
                paragraph(core["trend"], ["E1", "E4"]),
                paragraph(
                    "机柜功率密度突破30kW后，冷却方案需要处理芯片级换热、流体分配、连接可靠性、控制和现场服务，"
                    "客户验证可能提高供应商切换成本；若英维克的多部件平台通过验证并进入批量交付，单项目可覆盖的价值量和服务环节可能增加。",
                    ["E1", "E6", "E7", "E16"],
                ),
                paragraph(
                    "管理层表述显示，2024年数据中心机房及算力设备液冷技术相关收入约3亿元，且截至2025年3月液冷链条累计交付约1.2GW。"
                    "两者分别是近似收入和累计交付口径，不是审计分部收入、在手订单或产能。液冷2025年收入、数值毛利率、客户订单金额和项目回款仍未单列，"
                    "因此公司整体增长不能被直接归因为液冷。",
                    ["E4", "E5", "E6"],
                ),
                paragraph(core["falsification_condition"], ["E1", "E4"]),
            ],
        },
        {
            "section_id": "financial_history_and_cashflow_quality",
            "judgment": financial["judgment"],
            "judgment_refs": ["E1", "E2"],
            "blocks": [
                table(["期间", "收入（亿元）", "归母净利润（亿元）", "经营现金流（亿元）", "毛利率"], financial_rows, "年度数据来自审计年报，2026Q1为季度口径；单季度不作全年外推。", ["E1", "E2", "E3"]),
                paragraph(
                    f"2023A至2025A，收入由{money_100m(revenue['2023A'])}亿元增至{money_100m(revenue['2025A'])}亿元，"
                    f"归母净利润由{money_100m(profit['2023A'])}亿元增至{money_100m(profit['2025A'])}亿元，"
                    f"但经营现金流由{money_100m(ocf['2023A'])}亿元降至{money_100m(ocf['2025A'])}亿元，规模扩张与现金转换方向分化。",
                    ["E1", "E2"],
                ),
                paragraph(
                    "收入扩张快于利润增长，可能与产品结构、区域组合、价格或费用投入变化有关，但现有披露不足以识别主因；"
                    "同时应收账款约30.61亿元、存货约11.82亿元和负经营现金流表明资金占用上升，增长兑现需要跨期回款和库存消化配合。",
                    ["E1", "E2", "E5"],
                ),
                paragraph(financial["financial_impact"], ["E1", "E2", "E10"]),
                paragraph(
                    "反证是单季度现金流可能受验收与营运资金节奏扰动，不能仅凭一个季度认定长期恶化；但在连续季度毛利率恢复、"
                    "经营现金流转正且应收与存货增速低于收入增速之前，现金转换仍是关键约束。后续每季验证毛利率、费用率、"
                    "应收、存货、合同负债和经营现金流，并记录实际值相对模型的偏差。",
                    ["E2", "E5", "E10"],
                ),
            ],
        },
        {
            "section_id": "business_breakdown_and_economics",
            "judgment": economics["judgment"],
            "judgment_refs": ["E1", "E3", "E4"],
            "blocks": [
                table(["2025年宽产品线", "收入（亿元）", "收入占比", "毛利率"], business_rows, "年报宽产品线完整对上公司收入；未单列字段保持未披露。", ["E1", "E3", "E4"]),
                paragraph(driver["trend"], ["E1", "E4", "E6"]),
                paragraph(economics["causal_mechanism"], ["E3", "E5", "E6"]),
                paragraph(economics["financial_impact"], ["E1", "E2", "E5"]),
                paragraph(
                    "公司披露液冷系统多个部件与交付能力，说明其进入了相关价值链；但竞争报价、定制开发、项目验收和服务成本可能抵消平台广度。"
                    "因而观察条件不是产品名称数量，而是机房与机柜温控收入增速、毛利率、项目验收、应收与存货变化，以及是否首次出现可复算的液冷分项。"
                    "若库存和应收持续快于收入增长而现金流没有改善，平台驱动应被视为未兑现。",
                    ["E3", "E4", "E5", "E6"],
                ),
            ],
        },
        {
            "section_id": "industry_structure_and_competition",
            "judgment": industry["judgment"],
            "judgment_refs": ["E7", "E8"],
            "blocks": [
                paragraph(
                    "中国信通院报告称，截至2024年底全国在用数据中心标准机架超过900万，单机柜功率密度已突破30kW；"
                    "政策要求到2025年底全国平均PUE不高于1.5，新建大型数据中心不高于1.25、国家枢纽项目不高于1.2。",
                    ["E16", "E8"],
                ),
                paragraph(
                    "AI服务器提高单机柜热流密度，传统风冷的换热和能效边界收紧，同时PUE硬约束要求数据中心降低非IT能耗，"
                    "因而可能推动冷板液冷、浸没式液冷以及蒸发冷却、热管和氟泵等路线采用；具体速度仍取决于可靠性、成本和客户标准。",
                    ["E7", "E8"],
                ),
                paragraph(industry["financial_impact"], ["E7", "E8", "E1"]),
                paragraph(competition["judgment"], ["E1", "E7", "E9"]),
                paragraph(competition["causal_mechanism"], ["E7", "E9"]),
                paragraph(
                    "反证来自两方面：政策并列支持液冷、蒸发冷却、热管和氟泵等路线，需求增长并不保证单一路线获益；"
                    "四家同业也有热管理或液冷经营线索，产品结构、客户结构和确认节奏不同。后续应以同期间、同口径的收入、毛利、"
                    "批量客户与回款验证竞争位置；在分部口径齐备前，不形成市场份额或优劣排名。",
                    ["E7", "E8", "E9"],
                ),
                paragraph(competition["falsification_condition"], ["E9"]),
            ],
        },
        {
            "section_id": "forecast_and_scenarios",
            "judgment": "预测采用2025年审计宽产品线为基期，分别建模收入、毛利、费用、税率、少数股东损益、营运资本和资本开支；三种情景均为估计。",
            "judgment_refs": ["E1", "E2", "E10"],
            "blocks": [
                paragraph(
                    "基准假设中，机房温控、机柜温控和其他业务分别设置收入增速与毛利率；销售、管理、研发、财务费用、税费、其他经营拖累、"
                    "有效税率和少数股东损益单独桥接。经营现金流由净利润、非现金加回和营运资本变化形成，再扣除资本开支得到自由现金流。"
                    "九个情景年度的利润桥勾稽差额为零。",
                    ["E1", "E2", "E5", "E10"],
                ),
                table(["基准情景", "收入（亿元）", "毛利率", "归母净利润（亿元）", "每股收益（元）"], forecast_rows, "模型不把液冷设为未披露的独立分部，所有结果均受收入增速、毛利率和费用纪律约束。", ["E1", "E2", "E10"]),
                paragraph(
                    "下行情景假设需求、毛利率和费用吸收弱于基准；上行情景假设机房与机柜业务增长更快、毛利率和费用效率改善。"
                    "敏感性显示，2027E综合毛利率每变化1个百分点，归母净利润约变化0.76亿元；营运资本占收入比每上升1个百分点，"
                    "经营现金流约减少0.88亿元。因一季度弱盈利原因尚未核实，情景差距表示不确定性而非概率。",
                    ["E2", "E5", "E10", "E17"],
                ),
                paragraph(
                    "内部基准每股收益较两家近期机构的中点低约68%至74%。这不是稳健一致预期，"
                    "而是市场预期差线索：若后续实际利润接近机构区间，基准假设需上修；若毛利率、费用率和现金流不改善，"
                    "则应维持或下调基准并记录预测偏差。",
                    ["E10", "E12"],
                ),
            ],
        },
        {
            "section_id": "valuation_and_market_expectations",
            "judgment": "截至2026年7月10日，静态倍数与三情景盈利之间存在明显张力；同业PE、PB和PS方向不一致，估值状态不能用单一高低标签概括。",
            "judgment_refs": ["E15", "E18", "E14"],
            "blocks": [
                paragraph(
                    f"事实：收盘价为{market['current_price']['value']:.2f}元，总市值约{money_100m(market['market_cap']['value'])}亿元，"
                    f"PE TTM为{multiple(market['pe_ttm']['value'])}、PB为{multiple(market['pb']['value'])}、PS TTM为{multiple(market['ps']['value'])}。"
                    "市场快照使用同一日期；远期PE则使用同日市值除以内部情景归母净利润，分母不能混用。",
                    ["E18", "E14"],
                ),
                table(["基准情景", "2026E", "2027E", "2028E"], [["动态PE", multiple(dynamic["2026E"]), multiple(dynamic["2027E"]), multiple(dynamic["2028E"])]], "动态倍数依赖内部估计，实际盈利变化会直接改变结果。", ["E10", "E18", "E14"]),
                table(["同业", "代码", "PE TTM", "PB", "PS", "限制"], peer_table_rows, "四家公司只提供同日市场与公司级经营上下文，业务纯度不足以支持确定排名。", ["E9", "E15"]),
                table(["情景", "2027E归母净利润（亿元）", "研究倍数", "隐含市值（亿元）"], scenario_rows, "倍数为显式压力测试，不是历史公允区间。", ["E10", "E14"]),
                paragraph(
                    f"反向估值显示，当前市值在100x PE下需要约{money_100m(reverse['thresholds'][2]['required_net_profit']['value'])}亿元归母净利润；"
                    "基准到2028E仍略低于该阈值，上行情景在2027E超过。这个反推用于暴露市场隐含利润要求，而不是价值结论。"
                    "同业TTM PE中位数较高，主要受低基期利润影响；本公司PE低于同业中位数，但PB与PS更高，口径冲突本身就是风险。",
                    ["E9", "E10", "E14", "E15", "E18"],
                ),
                paragraph(
                    "现金流折现虽然已有短期现金流桥，但缺少审阅后的折现率、终值增速和净负债；分部估值又缺少液冷独立收入、利润和未分配成本。"
                    "因此两种方法保持停用。后续关注实际利润相对情景的偏差、同业远期口径、净负债桥和液冷分项披露；"
                    "若任一核心假设失效，应重新计算动态、情景和反向估值。",
                    ["E4", "E10", "E14"],
                ),
            ],
        },
        {
            "section_id": "dated_events",
            "judgment": "未来最明确的验证窗口是2026年半年度报告计划披露日；技术状态与公司情绪只提供事件前市场背景，不能替代经营证据。",
            "judgment_refs": ["E11", "E12", "E13"],
            "blocks": [
                paragraph(
                    f"技术状态：截至{technical['as_of_date']}，收盘价{t['current_price']['value']:.2f}元，MA5/MA10/MA20/MA60分别为"
                    f"{t['MA5']['value']:.2f}/{t['MA10']['value']:.2f}/{t['MA20']['value']:.2f}/{t['MA60']['value']:.2f}元；"
                    f"近1个月收益{pct(t['return_1m']['value'])}，近3个月收益{pct(t['return_3m']['value'])}，近6个月收益{pct(t['return_6m']['value'])}。"
                    "价格略高于MA5但低于其余均线，说明短期反弹与中期压力并存。支撑和阻力只作区间统计。",
                    ["E11"],
                ),
                paragraph(
                    "宏观情绪缺少可审阅同日指标，保持未定；行业情绪有需求与政策基础，但并非市场风险偏好指标；公司情绪来自两家机构预期差、"
                    "换手率与不同窗口收益，属于低置信线索。三层情绪不能写成事实，更不能覆盖财务、披露与回款证据。",
                    ["E7", "E8", "E11", "E12"],
                ),
                paragraph(
                    f"未来事件：计划于{event['event_date']}披露2026年半年度报告，但日期仍需发行人或交易所确认。影响路径是分业务收入和产品组合先改变增长归因，"
                    "毛利率与费用率再影响盈利桥，应收、存货和经营现金流决定现金转化。验证指标包括宽口径业务收入、任何同定义液冷收入更新、"
                    "毛利率、费用率、应收、存货与经营现金流。",
                    ["E5", "E6", "E13"],
                ),
                paragraph(
                    "上行条件是分业务披露增强且毛利率、利润和回款同步改善；基准条件是宽口径业务按模型增长但液冷仍未单列；"
                    "反证条件是正式日期变化、利润与现金流低于基准，或收入增长继续伴随毛利率下滑。事件发生后应按实际数据重跑预测、估值和证据缺口。",
                    ["E2", "E10", "E13", "E14"],
                ),
            ],
        },
        {
            "section_id": "risks_counterevidence_and_watchpoints",
            "judgment": risk["judgment"],
            "judgment_refs": ["E2", "E7", "E8"],
            "blocks": [
                paragraph(risk["trend"], ["E2", "E4", "E7"]),
                paragraph(risk["causal_mechanism"], ["E5", "E6", "E7", "E8"]),
                bullets(
                    [
                        ("财务反证：收入增长若继续伴随毛利率、净利率和经营现金流下降，增长质量判断触发降级。", ["E1", "E2"]),
                        ("业务反证：产品验证若未转化为批量交付、验收与回款，平台覆盖不能支持盈利贡献。", ["E4", "E5", "E6"]),
                        ("行业反证：替代制冷路线、价格竞争或客户标准变化可能削弱液冷需求对单一公司的传导。", ["E7", "E8", "E9"]),
                        ("估值反证：实际利润若持续低于基准，动态倍数与情景市值需要重新计算。", ["E10", "E11", "E14"]),
                    ]
                ),
                paragraph(
                    "观察条件是连续两个可比报告期毛利率不再同比下降、经营现金流为正、应收与存货增速低于收入增速，并出现可复算的液冷分项。"
                    "若这些条件满足且独立行业与客户证据仍支持批量采用，风险约束可下调；若条件未满足，应保留谨慎结论并扩大情景差异。",
                    ["E2", "E4", "E7", "E10"],
                ),
            ],
        },
        {
            "section_id": "research_conclusion",
            "judgment": "现有证据支持公司具备算力热管理与液冷产品平台，但财务兑现仍由宽口径温控业务、利润率和现金流决定；研究状态应保持证据观察。",
            "judgment_refs": ["E1", "E2", "E4", "E10"],
            "blocks": [
                paragraph(
                    "基准判断依赖三项假设：高密度算力与能效约束继续推动高效散热需求；公司多部件平台能够通过验证进入交付；"
                    "毛利率、费用纪律和回款随规模扩大而逐步改善。前两项有产品、行业和管理层证据，第三项尚需半年度及后续季度数据验证。",
                    ["E4", "E6", "E7", "E8", "E10"],
                ),
                paragraph(
                    "结论的主要反证是液冷独立经济性长期缺失、2026Q1利润和现金流承压、替代路线与同业竞争，以及当前市值对盈利修复要求较高。"
                    "若后续实际毛利率、费用率、现金流或分业务收入低于基准，模型与估值应触发降级；若分项披露、利润和回款共同改善，"
                    "当前谨慎判断才有证据上调。",
                    ["E2", "E4", "E7", "E9", "E14"],
                ),
                paragraph(
                    "跟踪顺序为：第一，核对2026年半年度报告正式日期与分业务口径；第二，比较实际收入、毛利率、费用率、利润和现金流相对三情景的偏差；"
                    "第三，验证液冷订单、验收与回款；第四，更新同业与分析师口径；第五，在同一日期和分母下重算动态、情景和反向估值。"
                    "外部人工复核签署前，报告只保持候选状态。",
                    ["E5", "E10", "E11", "E12", "E13", "E14"],
                ),
            ],
        },
    ]
    return {
        "artifact_type": "R5_reader_report_pack",
        "schema_version": "r5_reader_report_pack_v0.2",
        "metadata": {
            "workflow_id": run.name,
            "company_id": stock["company_id"],
            "company_name": stock["stock_name"],
            "stock_code": str(stock["stock_code"]),
            "cutoff_date": market["as_of_date"],
            "build_date": BUILD_DATE,
            "report_level": "研究候选稿",
            "human_review_status": "pending",
            "sample_quality_report_allowed": False,
            "p2_allowed": False,
        },
        "source_pack_paths": {
            "analysis_pack": "analysis_pack_v2.yaml",
            "forecast_model": "segment_forecast_model.yaml",
            "valuation_pack": "R5_bundle9_valuation_pack.yaml",
            "technical_pack": "R5_bundle10_technical_market_pack.yaml",
            "sentiment_event_pack": "R5_bundle10_sentiment_event_pack.yaml",
        },
        "sections": sections,
        "traceability_records": build_traceability_records(run),
        "footer": "外部人工复核仍待完成；在签署前，本稿不获得样例质量或横向比较许可。",
        "no_advice_boundary": True,
    }


def build_bundle10(repo_root: Path, run: Path) -> dict[str, Any]:
    technical = build_technical_pack(repo_root, run)
    sentiment = build_sentiment_event_pack(run, technical)
    forecast = load_yaml(run / "segment_forecast_model.yaml")
    bridge = load_yaml(run / "forecast_bridge.yaml")
    write_yaml(run / "R5_bundle10_reader_gate_forecast.yaml", build_gate_forecast(forecast, bridge))
    write_yaml(run / "R5_bundle10_reader_gate_valuation.yaml", build_gate_valuation(run, forecast))
    reader_pack = build_reader_pack(run, technical, sentiment)
    write_yaml(run / "R5_bundle10_reader_pack.yaml", reader_pack)
    readout = {
        "artifact_type": "R5_bundle10_reader_pack_build_readout",
        "schema_version": "v0.1",
        "workflow_id": run.name,
        "decision": "built_pending_reader_gate",
        "section_count": len(reader_pack["sections"]),
        "traceability_record_count": len(reader_pack["traceability_records"]),
        "technical_as_of_date": technical["as_of_date"],
        "sentiment_event_status": sentiment["status"],
        "human_review_status": "pending",
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
    }
    write_yaml(run / "R5_bundle10_reader_pack_build_readout.yaml", readout)
    return readout


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Bundle 10 technical, event and reader packs.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--workflow-run", default=f"reports/workflow_runs/{DEFAULT_WORKFLOW_ID}")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    run = Path(args.workflow_run)
    if not run.is_absolute():
        run = repo_root / run
    readout = build_bundle10(repo_root, run)
    print(yaml.safe_dump(readout, allow_unicode=True, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
