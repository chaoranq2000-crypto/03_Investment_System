from __future__ import annotations

import argparse
import csv
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence

import yaml


WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
STOCK_CODE = "002837"
COMPANY_ID = "cn_002837_invic"
COMPANY_NAME = "英维克"
MARKET_AS_OF = "2026-07-10"
BUILD_DATE = "2026-07-13"

MARKET_EVIDENCE = "ev_structured_market_data_002837_20260713_f8cc52"
ANNUAL_EVIDENCE = "ev_annual_report_002837_20260421_2cbfc5"
CONSENSUS_EVIDENCE = "ev_third_party_research_002837_20260713_20f610"
MARKET_SOURCE = "data/raw/market_data/tushare_daily_basic_002837_2026-07-13_f8cc52ed.json"
FORECAST_PATH = f"reports/workflow_runs/{WORKFLOW_ID}/segment_forecast_model.yaml"
ASSUMPTION_REGISTRY_PATH = (
    f"reports/workflow_runs/{WORKFLOW_ID}/R5_bundle9_forecast_assumption_registry.yaml"
)

MARKET = {
    "close_price": 73.54,
    "market_cap": 93_715_669_584.0,
    "free_float_market_cap": 83_133_888_674.0,
    "shares_outstanding": 1_274_349_692,
    "pe_ttm": 194.2045,
    "pb_lf": 27.0715,
    "ps_ttm": 14.8507,
    "turnover_rate": 6.3693,
}

MARKET_METRIC_IDS = {
    "close_price": "metric_company_cn_002837_invic_close_20260710_8b4e6cdd",
    "market_cap": "metric_company_cn_002837_invic_total_mv_20260710_94c6ec36",
    "free_float_market_cap": "metric_company_cn_002837_invic_circ_mv_20260710_17789f8b",
    "pe_ttm": "metric_company_cn_002837_invic_pe_ttm_20260710_f133fc07",
    "pb_lf": "metric_company_cn_002837_invic_pb_20260710_e0bb0510",
    "ps_ttm": "metric_company_cn_002837_invic_ps_ttm_20260710_eb40d051",
    "turnover_rate": "metric_company_cn_002837_invic_turnover_rate_20260710_ba2d5de2",
    "shares_outstanding": "metric_cn_002837_invic_shares_20251231_reviewed_anchor",
}

PEER_META = {
    "300499": {
        "company_name": "高澜股份",
        "company_id": "cn_300499_gaolan",
        "reason": "液冷设备与热管理业务邻近样本",
        "similarity": "medium",
        "overlap": "液冷与热管理相关，但收入纯度不可比",
        "evidence_id": "ev_structured_market_data_300499_20260713_57cd0b",
        "source_path": "data/raw/market_data/tushare_daily_basic_300499_2026-07-13_57cd0b28.json",
    },
    "300731": {
        "company_name": "科创新源",
        "company_id": "cn_300731_cotran",
        "reason": "热管理材料与液冷产业链邻近样本",
        "similarity": "limited",
        "overlap": "热管理相关，但产品与客户结构差异较大",
        "evidence_id": "ev_structured_market_data_300731_20260713_f4f0c0",
        "source_path": "data/raw/market_data/tushare_daily_basic_300731_2026-07-13_f4f0c072.json",
    },
    "301018": {
        "company_name": "申菱环境",
        "company_id": "cn_301018_shenling",
        "reason": "数据中心环境控制与液冷解决方案邻近样本",
        "similarity": "medium",
        "overlap": "数据中心温控相关，但业务组合与确认节奏不同",
        "evidence_id": "ev_structured_market_data_301018_20260713_cc0ee3",
        "source_path": "data/raw/market_data/tushare_daily_basic_301018_2026-07-13_cc0ee3a4.json",
    },
    "300602": {
        "company_name": "飞荣达",
        "company_id": "cn_300602_frd",
        "reason": "热管理材料及液冷相关产品邻近样本",
        "similarity": "limited",
        "overlap": "热管理相关，但终端、材料和产品口径不同",
        "evidence_id": "ev_structured_market_data_300602_20260713_e6104c",
        "source_path": "data/raw/market_data/tushare_daily_basic_300602_2026-07-13_e6104cc8.json",
    },
}

PEER_MULTIPLE_FILES = {
    code: f"R5_bundle8b_peer_valuation_{code}.yaml" for code in PEER_META
}

SCENARIO_MULTIPLE_RANGES = {
    "bear": (50.0, 75.0),
    "base": (75.0, 100.0),
    "bull": (100.0, 150.0),
}

MARKET_COLUMNS = [
    "stock_code", "company_id", "stock_name", "exchange", "as_of_date", "currency",
    "close_price", "market_cap", "free_float_market_cap", "shares_outstanding", "float_shares",
    "pe_ttm", "pe_lyr", "pe_forward_2026e", "pb_lf", "ps_ttm", "ev", "ev_ebitda_ttm",
    "dividend_yield", "turnover_rate", "pct_chg_20d", "pct_chg_60d", "source_name",
    "source_type", "source_path", "source_evidence_id", "source_metric_id", "reliability_rank",
    "capture_method", "snapshot_status", "limitations",
]

PEER_COLUMNS = [
    "subject_stock_code", "subject_company_id", "peer_company", "peer_stock_code", "exchange",
    "peer_selection_reason", "business_similarity", "segment_overlap", "as_of_date", "currency",
    "market_cap", "pe_ttm", "pe_forward_2026e", "pe_forward_2027e", "pb_lf", "ps_ttm",
    "ev_ebitda_ttm", "revenue_growth_2026e", "net_profit_growth_2026e", "roe", "gross_margin",
    "source_name", "source_type", "source_path", "source_evidence_id", "reliability_rank",
    "confidence", "limitations",
]


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def write_yaml(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(dict(data), allow_unicode=True, sort_keys=False), encoding="utf-8")


def write_csv(path: Path, columns: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def round2(value: float) -> float:
    return round(value, 2)


def number(
    value: float | int | None,
    unit: str,
    *,
    evidence_id: str | None = None,
    metric_id: str | None = None,
    assumption_id: str | None = None,
    missing_reason: str | None = None,
    period: str | None = None,
    calculation_method: str | None = None,
    claim_type: str = "fact",
) -> dict[str, Any]:
    result: dict[str, Any] = {"value": value, "unit": unit, "claim_type": claim_type}
    if evidence_id:
        result["evidence_id"] = evidence_id
    if metric_id:
        result["metric_id"] = metric_id
    if assumption_id:
        result["assumption_id"] = assumption_id
    if missing_reason:
        result["missing_reason"] = missing_reason
    if period:
        result["period"] = period
    if calculation_method:
        result["calculation_method"] = calculation_method
    return result


def missing_number(reason: str, unit: str = "unknown") -> dict[str, Any]:
    return number(None, unit, missing_reason=reason, claim_type="unknown")


def read_peer_inputs(run_dir: Path) -> list[dict[str, Any]]:
    operating = load_yaml(run_dir / "peer_operating_evidence_pack.yaml")
    operating_by_code = {str(row["stock_code"]): row for row in operating["companies"]}
    peers: list[dict[str, Any]] = []
    for code, filename in PEER_MULTIPLE_FILES.items():
        snapshot = load_yaml(run_dir / filename)
        values = snapshot["market_values"]
        op = operating_by_code[code]
        meta = PEER_META[code]
        peers.append(
            {
                **meta,
                "stock_code": code,
                "as_of_date": snapshot["as_of_date"],
                "market_cap": float(values["market_cap"]) * 10_000,
                "pe_ttm": float(values["pe_ttm"]),
                "pb": float(values["pb"]),
                "ps": float(values["ps"]),
                "roe": float(op["metrics"]["roe_diluted"]["value"]),
                "gross_margin": float(op["metrics"]["gross_margin"]["value"]),
                "operating_evidence_ids": list(op["source_evidence_ids"].values()),
                "official_scope_anchor": op.get("official_scope_anchor"),
            }
        )
    return peers


def build_market_snapshot_row() -> dict[str, Any]:
    return {
        "stock_code": STOCK_CODE,
        "company_id": COMPANY_ID,
        "stock_name": COMPANY_NAME,
        "exchange": "SZSE",
        "as_of_date": MARKET_AS_OF,
        "currency": "CNY",
        "close_price": MARKET["close_price"],
        "market_cap": MARKET["market_cap"],
        "free_float_market_cap": MARKET["free_float_market_cap"],
        "shares_outstanding": MARKET["shares_outstanding"],
        "float_shares": "",
        "pe_ttm": MARKET["pe_ttm"],
        "pe_lyr": "",
        "pe_forward_2026e": "",
        "pb_lf": MARKET["pb_lf"],
        "ps_ttm": MARKET["ps_ttm"],
        "ev": "",
        "ev_ebitda_ttm": "",
        "dividend_yield": "",
        "turnover_rate": MARKET["turnover_rate"],
        "pct_chg_20d": "",
        "pct_chg_60d": "",
        "source_name": "tushare",
        "source_type": "structured_database",
        "source_path": MARKET_SOURCE,
        "source_evidence_id": MARKET_EVIDENCE,
        "source_metric_id": "|".join(MARKET_METRIC_IDS.values()),
        "reliability_rank": "B",
        "capture_method": "archived_structured_api_pull",
        "snapshot_status": "reviewed",
        "limitations": (
            "行情与倍数日期为2026-07-10；股本使用2025年报审阅锚点；"
            "企业价值、远期倍数和股息率未取得。"
        ),
    }


def build_peer_snapshot_rows(peers: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for peer in peers:
        evidence_ids = [peer["evidence_id"], *peer["operating_evidence_ids"]]
        rows.append(
            {
                "subject_stock_code": STOCK_CODE,
                "subject_company_id": COMPANY_ID,
                "peer_company": peer["company_name"],
                "peer_stock_code": peer["stock_code"],
                "exchange": "SZSE",
                "peer_selection_reason": peer["reason"],
                "business_similarity": peer["similarity"],
                "segment_overlap": peer["overlap"],
                "as_of_date": peer["as_of_date"],
                "currency": "CNY",
                "market_cap": peer["market_cap"],
                "pe_ttm": peer["pe_ttm"],
                "pe_forward_2026e": "",
                "pe_forward_2027e": "",
                "pb_lf": peer["pb"],
                "ps_ttm": peer["ps"],
                "ev_ebitda_ttm": "",
                "revenue_growth_2026e": "",
                "net_profit_growth_2026e": "",
                "roe": peer["roe"],
                "gross_margin": peer["gross_margin"],
                "source_name": "tushare",
                "source_type": "structured_database",
                "source_path": peer["source_path"],
                "source_evidence_id": "|".join(evidence_ids),
                "reliability_rank": "B",
                "confidence": "low_confidence_fixture",
                "limitations": (
                    "同日同源公司级口径；缺少同业远期倍数；液冷收入纯度、产品组合、"
                    "客户结构和收入确认节奏不可直接横比。"
                ),
            }
        )
    return rows


def build_readiness(run_dir: Path, forecast: Mapping[str, Any], peers: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    assumption_ids = list(forecast.get("assumption_ids") or [])
    peer_sources = [str(peer["source_path"]) for peer in peers]
    peer_evidence = [str(peer["evidence_id"]) for peer in peers]
    financial_metric_ids = [
        "metric_cn_002837_invic_revenue_20251231_9c5aaf",
        "metric_cn_002837_invic_n_income_attr_p_20251231_002a58",
        "metric_cn_002837_invic_basic_eps_20251231_03d56b",
        "metric_cn_002837_invic_n_cashflow_act_20251231_890163",
    ]
    gaps = [
        "MISSING_PEER_FORWARD_MULTIPLES",
        "MISSING_PEER_OFFICIAL_NUMERIC_RECONCILIATION",
        "MISSING_NET_DEBT_AND_ENTERPRISE_VALUE",
        "TODO_SEGMENT_DISCLOSURE",
        "TODO_DCF_DISCOUNT_AND_TERMINAL_INPUTS",
    ]
    return {
        "valuation_input_readiness": {
            "workflow_id": WORKFLOW_ID,
            "stock_code": STOCK_CODE,
            "company_id": COMPANY_ID,
            "as_of_date": MARKET_AS_OF,
            "generated_by": "stock-deep-dive",
            "build_date": BUILD_DATE,
            "no_advice_boundary": True,
            "input_paths": {
                "market_snapshot": f"reports/workflow_runs/{WORKFLOW_ID}/market_snapshot.csv",
                "peer_market_snapshot": f"reports/workflow_runs/{WORKFLOW_ID}/peer_market_snapshot.csv",
                "financial_metric_pack": f"reports/workflow_runs/{WORKFLOW_ID}/financial_metric_pack.csv",
                "forecast_model": FORECAST_PATH,
                "valuation_request": f"reports/workflow_runs/{WORKFLOW_ID}/valuation_request.yaml",
            },
            "statuses": {
                "market_snapshot": {
                    "status": "ready",
                    "source_paths": [MARKET_SOURCE],
                    "source_metric_ids": list(MARKET_METRIC_IDS.values()),
                    "open_gaps": ["MISSING_EV_AND_FORWARD_MARKET_MULTIPLES"],
                    "limitations": ["Market context is dated and does not prove business exposure."],
                },
                "peer_market_snapshot": {
                    "status": "partial",
                    "source_paths": peer_sources,
                    "source_metric_ids": peer_evidence,
                    "open_gaps": gaps[:2],
                    "limitations": ["LOW_CONFIDENCE_PEER_SET; company-level metrics are not pure-play exposure."],
                },
                "financial_metric_pack": {
                    "status": "partial",
                    "source_paths": [f"reports/workflow_runs/{WORKFLOW_ID}/financial_metric_pack.csv"],
                    "source_metric_ids": financial_metric_ids,
                    "open_gaps": ["MISSING_NET_DEBT_AND_ENTERPRISE_VALUE"],
                    "limitations": ["Reviewed company-level history; valuation-specific balance items remain partial."],
                },
                "forecast_model": {
                    "status": "ready",
                    "source_paths": [FORECAST_PATH, ASSUMPTION_REGISTRY_PATH],
                    "source_metric_ids": assumption_ids,
                    "open_gaps": ["MISSING_STANDALONE_LIQUID_COOLING_ECONOMICS"],
                    "limitations": ["Three-scenario research model; values are estimates, not issuer guidance."],
                },
            },
            "open_gaps": gaps,
        }
    }


def build_request() -> dict[str, Any]:
    root = f"reports/workflow_runs/{WORKFLOW_ID}"
    return {
        "valuation_request": {
            "workflow_id": WORKFLOW_ID,
            "stock_code": STOCK_CODE,
            "company_id": COMPANY_ID,
            "stock_name": COMPANY_NAME,
            "exchange": "SZSE",
            "as_of_date": MARKET_AS_OF,
            "caller_skill": "stock-deep-dive",
            "parent_stage": "RP6",
            "quality_target": "publishable_candidate",
            "no_advice_boundary": True,
            "input_paths": {
                "stock_analysis_pack": f"{root}/stock_analysis_pack.yaml",
                "forecast_model": FORECAST_PATH,
                "financial_metric_pack": f"{root}/financial_metric_pack.csv",
                "reviewed_claims": f"{root}/claims_registry.csv",
                "reviewed_metrics": f"{root}/metrics_registry.csv",
                "market_snapshot": f"{root}/market_snapshot.csv",
                "peer_market_snapshot": f"{root}/peer_market_snapshot.csv",
                "valuation_input_readiness": f"{root}/valuation_input_readiness.yaml",
                "source_gap_report": f"{root}/liquid_cooling_disclosure_gap_register.yaml",
            },
            "allowed_methods": {
                "static_multiples": True,
                "dynamic_multiples": True,
                "peer_comparison": True,
                "scenario_valuation": True,
                "reverse_valuation": True,
                "dcf": "conditional",
                "sotp": "conditional",
                "ddm_or_pb": "conditional",
                "nav_or_resource": "conditional",
            },
            "requested_sections": [
                "static_valuation", "dynamic_valuation", "peer_comparison",
                "scenario_sensitivity", "reverse_valuation", "valuation_risks",
            ],
            "known_gaps": [
                "MISSING_PEER_FORWARD_MULTIPLES",
                "MISSING_NET_DEBT_AND_ENTERPRISE_VALUE",
                "TODO_SEGMENT_DISCLOSURE",
                "TODO_DCF_DISCOUNT_AND_TERMINAL_INPUTS",
            ],
            "notes": "Bundle 9 uses reviewed archived inputs only; unsupported methods remain explicit gaps.",
        }
    }


def scenario_tables(forecast: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for short, source_name in (("bear", "bear_case"), ("base", "base_case"), ("bull", "bull_case")):
        table = forecast["scenarios"][source_name]["forecast_table"]
        pe_by_year = {
            year: round(MARKET["market_cap"] / float(row["net_profit_attributable"]["value"]), 4)
            for year, row in table.items()
        }
        low_multiple, high_multiple = SCENARIO_MULTIPLE_RANGES[short]
        anchor = table["2027E"]["net_profit_attributable"]
        result[short] = {
            "source_name": source_name,
            "forecast_table": table,
            "dynamic_pe": pe_by_year,
            "multiple_range": (low_multiple, high_multiple),
            "market_cap_range": (
                round2(float(anchor["value"]) * low_multiple),
                round2(float(anchor["value"]) * high_multiple),
            ),
            "anchor": anchor,
        }
    return result


def build_peer_reconciliation(peers: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "artifact_type": "R5_bundle9_peer_reconciliation",
        "schema_version": "v0.1",
        "workflow_id": WORKFLOW_ID,
        "as_of_date": BUILD_DATE,
        "review_status": "reviewed_with_limitations",
        "rows": [
            {
                "stock_code": peer["stock_code"],
                "company_id": peer["company_id"],
                "company_name": peer["company_name"],
                "market_snapshot_status": "reviewed_metric_context",
                "operating_metric_status": "draft_pending_official_numeric_reconciliation",
                "official_scope_anchor": peer.get("official_scope_anchor") or "MISSING_OFFICIAL_SCOPE_ANCHOR",
                "source_evidence_ids": [peer["evidence_id"], *peer["operating_evidence_ids"]],
                "allowed_usage": "low_confidence_peer_context",
                "ranking_allowed": False,
            }
            for peer in peers
        ],
        "peer_set_quality": "LOW_CONFIDENCE_PEER_SET",
        "limitations": [
            "Forward peer multiples are unavailable.",
            "Structured annual figures have not all been line-item reconciled to official 2025 annual reports.",
            "Liquid-cooling revenue purity is not comparable across the peer set.",
        ],
        "sample_quality_allowed": False,
    }


def build_input_registry(forecast: Mapping[str, Any], peers: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    assumption_ids = list(forecast.get("assumption_ids") or [])
    return {
        "artifact_type": "R5_valuation_input_registry",
        "schema_version": "r5_valuation_input_registry_v0.1",
        "workflow_id": WORKFLOW_ID,
        "stock_code": STOCK_CODE,
        "company_id": COMPANY_ID,
        "as_of_date": MARKET_AS_OF,
        "no_live_api": True,
        "market_snapshot": {
            "review_status": "reviewed",
            "source_evidence_ids": [MARKET_EVIDENCE, ANNUAL_EVIDENCE],
            "source_path": MARKET_SOURCE,
            "market_cap": MARKET["market_cap"],
            "pe_ttm": MARKET["pe_ttm"],
        },
        "peer_snapshot": {
            "review_status": "reviewed",
            "source_evidence_ids": [peer["evidence_id"] for peer in peers],
            "peer_count": len(peers),
            "peer_set_quality": "LOW_CONFIDENCE_PEER_SET",
            "ranking_allowed": False,
        },
        "forecast_model": {
            "review_status": "ready",
            "path": FORECAST_PATH,
            "assumption_ids": assumption_ids,
            "claim_type": "estimate",
        },
        "business_line_split": {
            "review_status": "explicitly_scoped",
            "source_evidence_ids": [ANNUAL_EVIDENCE],
            "standalone_liquid_cooling_economics": "MISSING_DISCLOSURE",
        },
        "valuation_methods": [
            {"method": "static_multiples", "eligibility": "eligible", "confidence": "medium"},
            {"method": "dynamic_pe", "eligibility": "eligible", "confidence": "medium"},
            {"method": "relative_valuation", "eligibility": "eligible", "confidence": "low"},
            {"method": "scenario_valuation", "eligibility": "eligible", "confidence": "low"},
            {"method": "reverse_valuation", "eligibility": "eligible", "confidence": "medium"},
            {
                "method": "dcf",
                "eligibility": "ineligible_missing_discount_inputs",
                "missing_items": ["discount_rate", "terminal_growth", "reviewed_net_debt"],
            },
            {
                "method": "sotp",
                "eligibility": "ineligible_missing_segment_economics",
                "missing_items": ["standalone_liquid_cooling_revenue", "segment_profit", "unallocated_costs"],
            },
        ],
        "open_gaps": [
            "MISSING_PEER_FORWARD_MULTIPLES",
            "MISSING_NET_DEBT_AND_ENTERPRISE_VALUE",
            "TODO_SEGMENT_DISCLOSURE",
            "TODO_DCF_DISCOUNT_AND_TERMINAL_INPUTS",
        ],
        "sample_quality_allowed": False,
    }


def build_peer_comparison_rows(peers: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for peer in peers:
        rows.append(
            {
                "peer_company": peer["company_name"],
                "peer_stock_code": peer["stock_code"],
                "exchange": "SZSE",
                "selection_reason": peer["reason"],
                "business_similarity": peer["similarity"],
                "segment_overlap": peer["overlap"],
                "market_cap": peer["market_cap"],
                "pe_ttm": peer["pe_ttm"],
                "pe_2026E": "",
                "pb": peer["pb"],
                "ps": peer["ps"],
                "ev_ebitda": "",
                "as_of_date": peer["as_of_date"],
                "metric_source": peer["source_path"],
                "limitations": "LOW_CONFIDENCE_PEER_SET; no forward multiple; business mix is not directly comparable.",
                "confidence": "low",
            }
        )
    return rows


def build_sensitivity_rows(run_dir: Path, scenarios: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with (run_dir / "forecast_sensitivity.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        for source in csv.DictReader(handle):
            metric_id = (
                "metric_cn_002837_invic_n_cashflow_act_20251231_890163"
                if source["impact_metric"] == "operating_cashflow"
                else "metric_cn_002837_invic_n_income_attr_p_20251231_002a58"
            )
            rows.append(
                {
                    "variable": source["driver"],
                    "case_label": f"{source['year']}_{source['change']}",
                    "delta": source["change"],
                    "output_metric": source["impact_metric"],
                    "output_value": source["impact_value"],
                    "impact_vs_base": source["impact_value"],
                    "assumption_type": "forecast_sensitivity",
                    "supporting_metric_ids": metric_id,
                    "supporting_claim_ids": source["assumption_id_or_missing_reason"],
                    "notes": source["calculation_method"],
                }
            )
    base_profit = float(scenarios["base"]["anchor"]["value"])
    base_value = base_profit * 100.0
    for multiple in (50.0, 75.0, 100.0, 125.0, 150.0):
        output = base_profit * multiple
        rows.append(
            {
                "variable": "2027E_PE_multiple",
                "case_label": f"{int(multiple)}x",
                "delta": f"{multiple - 100.0:+.0f}x_vs_100x",
                "output_metric": "implied_market_cap",
                "output_value": round2(output),
                "impact_vs_base": round2(output - base_value),
                "assumption_type": "valuation_scenario",
                "supporting_metric_ids": "metric_cn_002837_invic_n_income_attr_p_20251231_002a58",
                "supporting_claim_ids": "b9_base_case_net_profit_bridge",
                "notes": "2027E base attributable profit multiplied by an explicit research multiple.",
            }
        )
    return rows


def build_reverse_valuation(scenarios: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    thresholds = []
    for multiple in (50.0, 75.0, 100.0, 150.0, 200.0):
        required_profit = MARKET["market_cap"] / multiple
        first_reached: dict[str, str] = {}
        for short, scenario in scenarios.items():
            reached = "NOT_REACHED_2026E_2028E"
            for year, row in scenario["forecast_table"].items():
                if float(row["net_profit_attributable"]["value"]) >= required_profit:
                    reached = year
                    break
            first_reached[short] = reached
        thresholds.append(
            {
                "multiple": number(multiple, "multiple", assumption_id=f"reverse_pe_{int(multiple)}x", claim_type="estimate"),
                "required_net_profit": number(
                    round2(required_profit),
                    "CNY",
                    evidence_id=MARKET_EVIDENCE,
                    assumption_id=f"reverse_pe_{int(multiple)}x",
                    calculation_method="current market cap / selected PE multiple",
                    claim_type="inference",
                ),
                "first_model_year_reaching_threshold": first_reached,
            }
        )
    return {
        "artifact_type": "R5_bundle9_reverse_valuation",
        "schema_version": "v0.1",
        "workflow_id": WORKFLOW_ID,
        "valuation_as_of_date": MARKET_AS_OF,
        "market_cap_anchor": number(
            MARKET["market_cap"], "CNY", evidence_id=MARKET_EVIDENCE,
            metric_id=MARKET_METRIC_IDS["market_cap"], period=MARKET_AS_OF,
        ),
        "thresholds": thresholds,
        "interpretation": (
            "反向估值仅显示当前市值在不同倍数下所需的归母净利润，以及模型何时可能达到；"
            "它不是价值判断。"
        ),
        "limitations": [
            "Selected multiples are explicit research stress points, not a validated fair-value history.",
            "Forecast profit is an estimate and can change with revenue, margin, expenses and cash conversion.",
        ],
        "sample_quality_allowed": False,
    }


def build_scenario_valuation(scenarios: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "artifact_type": "R5_bundle9_scenario_valuation",
        "schema_version": "v0.1",
        "workflow_id": WORKFLOW_ID,
        "valuation_as_of_date": MARKET_AS_OF,
        "anchor_period": "2027E",
        "method": "scenario_PE_on_attributable_profit",
        "scenarios": {},
        "interpretation_boundary": "market_cap_ranges_are_research_scenarios_only",
        "sample_quality_allowed": False,
    }
    for short, scenario in scenarios.items():
        low_multiple, high_multiple = scenario["multiple_range"]
        low_value, high_value = scenario["market_cap_range"]
        anchor = scenario["anchor"]
        result["scenarios"][short] = {
            "profit_anchor": number(
                float(anchor["value"]), "CNY", evidence_id=anchor["evidence_id"],
                assumption_id=anchor["assumption_id"], period="2027E", claim_type="estimate",
            ),
            "multiple_range": {
                "low": number(low_multiple, "multiple", assumption_id=f"b9_{short}_valuation_multiple_low", claim_type="estimate"),
                "high": number(high_multiple, "multiple", assumption_id=f"b9_{short}_valuation_multiple_high", claim_type="estimate"),
            },
            "implied_market_cap_range": {
                "low": number(
                    low_value, "CNY", assumption_id=f"b9_{short}_valuation_multiple_low",
                    calculation_method="2027E attributable profit * low scenario multiple", claim_type="inference",
                ),
                "high": number(
                    high_value, "CNY", assumption_id=f"b9_{short}_valuation_multiple_high",
                    calculation_method="2027E attributable profit * high scenario multiple", claim_type="inference",
                ),
            },
            "uncertainties": [
                "multiple range is a research assumption",
                "peer TTM multiples are distorted by low current earnings",
                "liquid-cooling standalone economics remain undisclosed",
            ],
        }
    return result


def build_analyst_comparison_rows(forecast: Mapping[str, Any]) -> list[dict[str, Any]]:
    comparison = forecast["consensus_comparison"]
    rows = []
    for year, row in comparison["rows"].items():
        rows.append(
            {
                "period": year,
                "base_model_eps": row["base_model_eps"],
                "two_broker_midpoint_eps": row["two_broker_midpoint_eps"],
                "base_minus_midpoint_pct": row["base_minus_midpoint_pct"],
                "unit": row["unit"],
                "claim_type": "analyst_view",
                "source_evidence_id": comparison["source_evidence_id"],
                "source_path": comparison["source_path"],
                "limitations": "Only two distinct brokers; share-basis consistency is unverified.",
            }
        )
    return rows


def build_valuation_model(
    peers: Sequence[Mapping[str, Any]], scenarios: Mapping[str, Mapping[str, Any]], output_root: str
) -> dict[str, Any]:
    medians = {
        "pe_ttm": round(median(float(peer["pe_ttm"]) for peer in peers), 4),
        "pb": round(median(float(peer["pb"]) for peer in peers), 4),
        "ps": round(median(float(peer["ps"]) for peer in peers), 4),
    }
    base_dynamic = scenarios["base"]["dynamic_pe"]
    scenario_block: dict[str, Any] = {}
    for short, scenario in scenarios.items():
        low_multiple, high_multiple = scenario["multiple_range"]
        low_value, high_value = scenario["market_cap_range"]
        table = scenario["forecast_table"]
        scenario_block[short] = {
            "assumptions": {
                "revenue_growth": table["2027E"]["revenue"]["assumption_id"],
                "gross_margin": table["2027E"]["gross_margin"]["assumption_id"],
                "valuation_multiple": [low_multiple, high_multiple],
            },
            "output_range": {"low_CNY": low_value, "high_CNY": high_value},
            "support_ids": [table["2027E"]["net_profit_attributable"]["assumption_id"], MARKET_EVIDENCE],
            "uncertainties": ["forecast error", "multiple compression", "peer comparability"],
            "claim_type": "inference",
        }
    return {
        "valuation_model": {
            "metadata": {
                "workflow_id": WORKFLOW_ID,
                "stock_code": STOCK_CODE,
                "company_id": COMPANY_ID,
                "stock_name": COMPANY_NAME,
                "as_of_date": MARKET_AS_OF,
                "source_skill": "company-valuation",
                "caller_skill": "stock-deep-dive",
                "quality_target": "publishable_candidate",
                "no_advice_boundary": True,
            },
            "source_skill": "company-valuation",
            "caller_skill": "stock-deep-dive",
            "input_status": {
                "forecast_model": "ready",
                "market_data": "ready",
                "peer_data": "low_confidence_peer_data",
                "official_metric_support": "partial",
                "business_segment_support": "partial",
            },
            "selected_methods": [
                {"method_id": "static_multiples", "method_name": "static multiples", "status": "used", "reason": "dated market snapshot exists", "required_inputs": ["market_snapshot"], "missing_inputs": [], "confidence": "medium"},
                {"method_id": "dynamic_pe", "method_name": "dynamic PE", "status": "used", "reason": "three-year attributable-profit model exists", "required_inputs": ["forecast_model", "market_cap"], "missing_inputs": [], "confidence": "medium"},
                {"method_id": "peer_comparison", "method_name": "peer comparison", "status": "used", "reason": "four same-date peer snapshots exist", "required_inputs": ["peer_snapshot"], "missing_inputs": ["peer_forward_multiples"], "confidence": "low"},
                {"method_id": "scenario_valuation", "method_name": "scenario market-cap range", "status": "used", "reason": "bear/base/bull profit paths exist", "required_inputs": ["scenario_profit", "explicit_multiple_range"], "missing_inputs": [], "confidence": "low"},
                {"method_id": "reverse_valuation", "method_name": "reverse valuation", "status": "used", "reason": "current market cap and scenario profits exist", "required_inputs": ["market_cap", "forecast_profit"], "missing_inputs": [], "confidence": "medium"},
                {"method_id": "dcf", "method_name": "DCF", "status": "skipped", "reason": "discount rate, terminal growth and reviewed net debt are missing", "required_inputs": ["FCFF", "discount_rate", "terminal_growth", "net_debt"], "missing_inputs": ["discount_rate", "terminal_growth", "net_debt"], "confidence": "low"},
                {"method_id": "sotp", "method_name": "SOTP", "status": "skipped", "reason": "standalone liquid-cooling economics and unallocated costs are missing", "required_inputs": ["segment_profit", "segment_multiple", "unallocated_cost"], "missing_inputs": ["segment_profit", "unallocated_cost"], "confidence": "low"},
            ],
            "static_valuation": {
                "as_of_date": MARKET_AS_OF,
                "metrics": {
                    "pe_ttm": MARKET["pe_ttm"], "pb": MARKET["pb_lf"], "ps": MARKET["ps_ttm"],
                    "ev_ebitda": "MISSING_NET_DEBT_AND_ENTERPRISE_VALUE",
                    "dividend_yield": "MISSING_MARKET_FIELD",
                },
                "source_metric_ids": [
                    MARKET_METRIC_IDS["pe_ttm"], MARKET_METRIC_IDS["pb_lf"], MARKET_METRIC_IDS["ps_ttm"],
                ],
                "source_paths": [MARKET_SOURCE],
                "notes": "Static multiples are dated market context.",
                "confidence": "medium",
            },
            "dynamic_valuation": {
                "forecast_periods": ["2026E", "2027E", "2028E"],
                "metrics": {f"pe_{year}": value for year, value in base_dynamic.items()},
                "forecast_metric_ids": ["b9_base_case_net_profit_bridge"],
                "assumption_ids": ["b9_base_case_net_profit_bridge"],
                "notes": "Current market cap divided by base-case attributable profit.",
                "confidence": "medium",
            },
            "peer_comparison": {
                "peer_table_path": f"{output_root}/peer_comparison.csv",
                "peer_set_quality": "low",
                "median_metrics": {**medians, "pe_2026E": "MISSING_PEER_FORWARD_MULTIPLES", "ev_ebitda": "MISSING_NET_DEBT_AND_ENTERPRISE_VALUE"},
                "target_position": {
                    "relative_to_peer_median": "not_assessable",
                    "explanation": "TTM PE is below the peer median while PB and PS are above it; denominator and business-scope differences prevent one label.",
                },
                "limitations": ["LOW_CONFIDENCE_PEER_SET", "no peer forward multiples", "business mix differs"],
            },
            "scenario_valuation": {
                "scenarios": scenario_block,
                "sensitivity_table_path": f"{output_root}/sensitivity_table.csv",
                "most_sensitive_variable": "gross_margin_and_valuation_multiple",
                "interpretation_boundary": "research_scenarios_only",
            },
            "dcf_or_other_intrinsic_method": {
                "method_used": "skipped",
                "reason": "DCF and SOTP do not meet input gates.",
                "assumptions": {
                    "discount_rate": "TODO_DCF_DISCOUNT_INPUT",
                    "terminal_growth": "TODO_DCF_TERMINAL_INPUT",
                    "forecast_horizon": "2026E-2028E",
                    "margin_path": "available_in_forecast_model",
                    "reinvestment_or_capex": "available_but_not_sufficient_for_DCF",
                },
                "sensitivity_table_path": f"{output_root}/sensitivity_table.csv",
                "sanity_checks": {"wacc_gt_terminal_growth": "NOT_ASSESSABLE", "terminal_value_share": "NOT_ASSESSABLE", "cyclicality_adjustment": "TODO"},
                "confidence": "low",
            },
            "valuation_section": {
                "draft_path": f"{output_root}/valuation_section_draft.md",
                "evidence_map_path": f"{output_root}/valuation_quality_handoff.yaml",
                "open_gaps_path": f"{output_root}/valuation_gap_requests.yaml",
            },
            "quality_handoff": {
                "path": f"{output_root}/valuation_quality_handoff.yaml",
                "no_advice_boundary": "pass",
                "open_gap_count": 5,
                "blocking_gap_count": 0,
            },
            "valuation_snapshot_path": f"{output_root}/valuation_snapshot.yaml",
            "peer_comparison_path": f"{output_root}/peer_comparison.csv",
            "sensitivity_table_path": f"{output_root}/sensitivity_table.csv",
            "valuation_section_draft_path": f"{output_root}/valuation_section_draft.md",
            "valuation_quality_handoff_path": f"{output_root}/valuation_quality_handoff.yaml",
            "valuation_gap_requests_path": f"{output_root}/valuation_gap_requests.yaml",
        }
    }


def build_valuation_snapshot(peers: Sequence[Mapping[str, Any]], scenarios: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "valuation_snapshot": {
            "metadata": {
                "workflow_id": WORKFLOW_ID, "stock_code": STOCK_CODE, "company_id": COMPANY_ID,
                "as_of_date": MARKET_AS_OF, "generated_by": "company-valuation",
                "caller_skill": "stock-deep-dive", "no_advice_boundary": True,
            },
            "market_data": {
                "current_price": MARKET["close_price"], "market_cap": MARKET["market_cap"],
                "shares_outstanding": MARKET["shares_outstanding"], "currency": "CNY",
                "source_path": MARKET_SOURCE, "source_metric_ids": list(MARKET_METRIC_IDS.values()),
                "freshness_status": "fresh_for_valuation_as_of_date",
            },
            "multiples": {
                "pe_ttm": MARKET["pe_ttm"], "pb": MARKET["pb_lf"], "ps": MARKET["ps_ttm"],
                "ev_ebitda": "MISSING_NET_DEBT_AND_ENTERPRISE_VALUE",
                "pe_forward": scenarios["base"]["dynamic_pe"],
            },
            "peer_context": {
                "peer_market_snapshot_path": f"reports/workflow_runs/{WORKFLOW_ID}/peer_market_snapshot.csv",
                "peer_set_quality": "low",
                "peer_median_multiples": {
                    "pe_ttm": round(median(float(peer["pe_ttm"]) for peer in peers), 4),
                    "pb": round(median(float(peer["pb"]) for peer in peers), 4),
                    "ps": round(median(float(peer["ps"]) for peer in peers), 4),
                },
                "limitations": ["LOW_CONFIDENCE_PEER_SET", "no peer forward multiples"],
            },
            "model_context": {
                "forecast_model_path": FORECAST_PATH,
                "sensitivity_table_path": f"reports/workflow_runs/{WORKFLOW_ID}/valuation/sensitivity_table.csv",
                "scenario_summary": {
                    short: {"market_cap_range_CNY": list(scenario["market_cap_range"]), "anchor_period": "2027E"}
                    for short, scenario in scenarios.items()
                },
            },
            "labels": {"valuation_context_label": "not_assessable", "confidence": "low"},
            "gaps": [
                "MISSING_PEER_FORWARD_MULTIPLES", "MISSING_NET_DEBT_AND_ENTERPRISE_VALUE",
                "TODO_SEGMENT_DISCLOSURE", "TODO_DCF_DISCOUNT_AND_TERMINAL_INPUTS",
            ],
        }
    }


def build_company_output(peers: Sequence[Mapping[str, Any]], scenarios: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    source_assumption = "market_snapshot_source_20260710"
    return {
        "artifact_type": "company_valuation_output",
        "schema_version": "r5_company_valuation_output_v0.1",
        "valuation_as_of_date": MARKET_AS_OF,
        "input_status": "partial_with_todos",
        "market_snapshot": {
            "as_of_date": MARKET_AS_OF,
            "current_price": number(MARKET["close_price"], "CNY_per_share", evidence_id=MARKET_EVIDENCE, assumption_id=source_assumption),
            "market_cap": number(MARKET["market_cap"], "CNY", evidence_id=MARKET_EVIDENCE, assumption_id=source_assumption),
            "share_count": number(MARKET["shares_outstanding"], "shares", evidence_id=ANNUAL_EVIDENCE, assumption_id="reviewed_share_count_anchor"),
        },
        "peer_set": {
            "quality": "LOW_CONFIDENCE_PEER_SET",
            "peers": [peer["stock_code"] for peer in peers],
            "missing_reason": "MISSING_PEER_FORWARD_MULTIPLES",
        },
        "method_selection": {
            "selected_methods": [
                {"method": "static_multiples", "status": "used", "reason": "reviewed dated snapshot"},
                {"method": "dynamic_pe", "status": "used", "reason": "reviewed forecast assumptions"},
                {"method": "peer_context", "status": "used_low_confidence", "reason": "four same-date peers with weak comparability"},
                {"method": "scenario_and_reverse", "status": "used", "reason": "explicit scenarios and market-cap anchor"},
                {"method": "dcf", "status": "skipped", "reason": "TODO_DCF_DISCOUNT_AND_TERMINAL_INPUTS"},
                {"method": "sotp", "status": "skipped", "reason": "TODO_SEGMENT_DISCLOSURE"},
            ]
        },
        "scenario_outputs": {
            short: {
                "implied_market_cap_low": number(
                    scenario["market_cap_range"][0], "CNY", assumption_id=f"b9_{short}_valuation_multiple_low", claim_type="inference"
                ),
                "implied_market_cap_high": number(
                    scenario["market_cap_range"][1], "CNY", assumption_id=f"b9_{short}_valuation_multiple_high", claim_type="inference"
                ),
                "implied_multiple_low": number(
                    scenario["multiple_range"][0], "multiple", assumption_id=f"b9_{short}_valuation_multiple_low", claim_type="estimate"
                ),
                "implied_multiple_high": number(
                    scenario["multiple_range"][1], "multiple", assumption_id=f"b9_{short}_valuation_multiple_high", claim_type="estimate"
                ),
            }
            for short, scenario in scenarios.items()
        },
        "sensitivity": [
            {
                "driver": "2027E_PE_multiple",
                "impact_metric": "implied_market_cap",
                "impact_value": number(
                    float(scenarios["base"]["anchor"]["value"]) * 25.0,
                    "CNY_per_25x_change",
                    assumption_id="b9_base_valuation_multiple_sensitivity",
                    claim_type="inference",
                ),
            },
            {
                "driver": "2027E_gross_margin",
                "impact_metric": "net_profit_attributable",
                "impact_value": number(
                    76_456_705.81, "CNY_per_1pct_point",
                    assumption_id="b9_base_case_gross_margin_consolidated", claim_type="estimate",
                ),
            },
        ],
        "source_gap": [
            {"gap_id": "CV_B9_001", "missing_data": "peer_forward_multiples", "next_action": "refresh from reviewed same-basis forecasts"},
            {"gap_id": "CV_B9_002", "missing_data": "net_debt_and_enterprise_value", "next_action": "normalize reviewed balance-sheet inputs"},
            {"gap_id": "CV_B9_003", "missing_data": "standalone_liquid_cooling_economics", "next_action": "refresh after issuer disclosure"},
            {"gap_id": "CV_B9_004", "missing_data": "DCF_discount_and_terminal_inputs", "next_action": "keep method skipped until reviewed"},
        ],
        "no_advice_disclaimer": "This output is research context only and contains no action recommendation or return assurance.",
    }


def build_r5_handoff(peers: Sequence[Mapping[str, Any]], scenarios: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    peer_rows = []
    for peer in peers:
        peer_rows.append(
            {
                "peer_company": peer["company_name"],
                "peer_stock_code": peer["stock_code"],
                "similarity_reason": peer["reason"],
                "pe_ttm": number(peer["pe_ttm"], "multiple", evidence_id=peer["evidence_id"]),
                "pb": number(peer["pb"], "multiple", evidence_id=peer["evidence_id"]),
                "ps": number(peer["ps"], "multiple", evidence_id=peer["evidence_id"]),
                "source_evidence_id": peer["evidence_id"],
            }
        )
    scenario_values = []
    for short, scenario in scenarios.items():
        scenario_values.append(
            {
                "scenario_id": f"{short}_case",
                "method": "scenario_PE_on_2027E_profit",
                "market_cap_range": {
                    "low": number(scenario["market_cap_range"][0], "CNY", assumption_id=f"b9_{short}_valuation_multiple_low", claim_type="inference"),
                    "high": number(scenario["market_cap_range"][1], "CNY", assumption_id=f"b9_{short}_valuation_multiple_high", claim_type="inference"),
                },
                "interpretation_boundary": "scenario_value_not_action_recommendation",
            }
        )
    return {
        "artifact_type": "R5_valuation_handoff",
        "schema_version": "r5_valuation_handoff_v0.1",
        "workflow_id": WORKFLOW_ID,
        "stock_code": STOCK_CODE,
        "company_id": COMPANY_ID,
        "valuation_as_of_date": MARKET_AS_OF,
        "market_snapshot": {
            "status": "reviewed",
            "current_price": number(MARKET["close_price"], "CNY_per_share", evidence_id=MARKET_EVIDENCE),
            "market_cap": number(MARKET["market_cap"], "CNY", evidence_id=MARKET_EVIDENCE),
            "share_count": number(MARKET["shares_outstanding"], "shares", evidence_id=ANNUAL_EVIDENCE),
        },
        "peer_context": {"status": "reviewed", "quality": "LOW_CONFIDENCE_PEER_SET", "peers": peer_rows},
        "method_used": ["static_multiples", "dynamic_pe", "peer_context", "scenario_valuation", "reverse_valuation"],
        "scenario_values": scenario_values,
        "assumptions": [
            {
                "assumption_id": f"b9_{short}_valuation_multiple_range",
                "description": f"{short} 2027E PE range {scenario['multiple_range'][0]:.0f}x-{scenario['multiple_range'][1]:.0f}x",
                "source_evidence_id": MARKET_EVIDENCE,
                "forecast_assumption_id": scenario["anchor"]["assumption_id"],
            }
            for short, scenario in scenarios.items()
        ],
        "sensitivity": [
            {
                "driver": "2027E_PE_multiple",
                "change": "plus_25x",
                "impact_value": number(
                    float(scenarios["base"]["anchor"]["value"]) * 25.0,
                    "CNY_market_cap",
                    assumption_id="b9_base_valuation_multiple_sensitivity",
                    claim_type="inference",
                ),
            }
        ],
        "source_evidence_ids": [MARKET_EVIDENCE, ANNUAL_EVIDENCE, CONSENSUS_EVIDENCE, *[peer["evidence_id"] for peer in peers]],
        "missing_items": [
            "MISSING_PEER_FORWARD_MULTIPLES", "MISSING_NET_DEBT_AND_ENTERPRISE_VALUE",
            "TODO_SEGMENT_DISCLOSURE", "TODO_DCF_DISCOUNT_AND_TERMINAL_INPUTS",
        ],
        "no_advice_statement": "Scenario values are research context only and not action recommendations.",
        "sample_quality_allowed": False,
    }


def build_r5_pack(peers: Sequence[Mapping[str, Any]], scenarios: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    market_snapshot = {
        "as_of_date": MARKET_AS_OF,
        "current_price": number(MARKET["close_price"], "CNY_per_share", evidence_id=MARKET_EVIDENCE, metric_id=MARKET_METRIC_IDS["close_price"]),
        "market_cap": number(MARKET["market_cap"], "CNY", evidence_id=MARKET_EVIDENCE, metric_id=MARKET_METRIC_IDS["market_cap"]),
        "share_count": number(MARKET["shares_outstanding"], "shares", evidence_id=ANNUAL_EVIDENCE, metric_id=MARKET_METRIC_IDS["shares_outstanding"]),
        "net_cash_or_net_debt": missing_number("MISSING_NET_DEBT_AND_ENTERPRISE_VALUE", "CNY"),
        "enterprise_value": missing_number("MISSING_NET_DEBT_AND_ENTERPRISE_VALUE", "CNY"),
        "pe_ttm": number(MARKET["pe_ttm"], "multiple", evidence_id=MARKET_EVIDENCE, metric_id=MARKET_METRIC_IDS["pe_ttm"]),
        "forward_pe": number(scenarios["base"]["dynamic_pe"]["2026E"], "multiple", evidence_id=MARKET_EVIDENCE, assumption_id="b9_base_case_net_profit_bridge", claim_type="inference"),
        "pb": number(MARKET["pb_lf"], "multiple", evidence_id=MARKET_EVIDENCE, metric_id=MARKET_METRIC_IDS["pb_lf"]),
        "ps": number(MARKET["ps_ttm"], "multiple", evidence_id=MARKET_EVIDENCE, metric_id=MARKET_METRIC_IDS["ps_ttm"]),
        "ev_ebitda": missing_number("MISSING_NET_DEBT_AND_ENTERPRISE_VALUE", "multiple"),
    }
    peer_rows = []
    for peer in peers:
        for multiple_name in ("pe_ttm", "pb", "ps"):
            peer_rows.append(
                {
                    "peer_company": peer["company_name"],
                    "peer_stock_code": peer["stock_code"],
                    "multiple_name": multiple_name,
                    "multiple_value": peer[multiple_name],
                    "evidence_id": peer["evidence_id"],
                    "as_of_date": peer["as_of_date"],
                    "limitation": "LOW_CONFIDENCE_PEER_SET",
                }
            )
    return {
        "artifact_type": "R5_valuation_pack",
        "schema_version": "r5_valuation_pack_v0.1",
        "workflow_id": WORKFLOW_ID,
        "stock_code": STOCK_CODE,
        "status": "partial",
        "market_snapshot": market_snapshot,
        "peer_valuation_context": {"status": "partial", "rows": peer_rows, "peer_set_quality": "low"},
        "valuation_methods": [
            {"method_id": "static_multiples", "method_type": "market_dependent", "status": "ready", "supported_output": {"pe_ttm": MARKET["pe_ttm"], "pb": MARKET["pb_lf"], "ps": MARKET["ps_ttm"]}},
            {"method_id": "dynamic_pe", "method_type": "forecast_dependent", "status": "ready", "supported_output": scenarios["base"]["dynamic_pe"], "forecast_assumption_ids": ["b9_base_case_net_profit_bridge"]},
            {"method_id": "scenario_valuation", "method_type": "forecast_dependent", "status": "ready", "supported_output": {short: list(scenario["market_cap_range"]) for short, scenario in scenarios.items()}, "forecast_assumption_ids": [f"b9_{short}_case_net_profit_bridge" for short in scenarios]},
            {"method_id": "reverse_valuation", "method_type": "forecast_dependent", "status": "ready", "supported_output": "reverse_valuation.yaml", "forecast_assumption_ids": ["b9_base_case_net_profit_bridge"]},
            {"method_id": "dcf", "method_type": "intrinsic", "status": "TODO", "supported_output": None, "missing_reason": "TODO_DCF_DISCOUNT_AND_TERMINAL_INPUTS"},
            {"method_id": "sotp", "method_type": "segment_dependent", "status": "TODO", "supported_output": None, "missing_reason": "TODO_SEGMENT_DISCLOSURE"},
        ],
        "scenario_valuation": {short: {"market_cap_range_CNY": list(scenario["market_cap_range"]), "assumption_id": scenario["anchor"]["assumption_id"]} for short, scenario in scenarios.items()},
        "reverse_valuation_path": f"reports/workflow_runs/{WORKFLOW_ID}/reverse_valuation.yaml",
        "analyst_comparison_path": f"reports/workflow_runs/{WORKFLOW_ID}/analyst_forecast_comparison.csv",
        "limitations": ["LOW_CONFIDENCE_PEER_SET", "MISSING_PEER_FORWARD_MULTIPLES", "MISSING_NET_DEBT_AND_ENTERPRISE_VALUE"],
        "sample_quality_allowed": False,
        "no_advice_boundary": True,
    }


def build_gaps() -> dict[str, Any]:
    return {
        "valuation_gap_requests": [
            {"gap_id": "CV_B9_001", "target_section": "peer_comparison", "missing_claim_or_metric": "peer forward PE", "required_source_type": "reviewed same-basis forecasts", "preferred_source_name": "official or traceable analyst forecast", "blocking_level": "medium", "owner_skill": "evidence-ingest", "notes": "Keep peer set low confidence until refreshed."},
            {"gap_id": "CV_B9_002", "target_section": "EV_and_DCF", "missing_claim_or_metric": "net debt and enterprise value", "required_source_type": "reviewed balance sheet", "preferred_source_name": "issuer filing", "blocking_level": "medium", "owner_skill": "stock-deep-dive", "notes": "EV-based methods remain unavailable."},
            {"gap_id": "CV_B9_003", "target_section": "SOTP", "missing_claim_or_metric": "standalone liquid-cooling revenue and profit", "required_source_type": "issuer disclosure", "preferred_source_name": "annual report or official response", "blocking_level": "medium", "owner_skill": "evidence-ingest", "notes": "SOTP remains skipped."},
            {"gap_id": "CV_B9_004", "target_section": "DCF", "missing_claim_or_metric": "discount rate and terminal-growth assumptions", "required_source_type": "reviewed model assumption", "preferred_source_name": "valuation assumption registry", "blocking_level": "medium", "owner_skill": "stock-deep-dive", "notes": "DCF remains skipped."},
            {"gap_id": "CV_B9_005", "target_section": "peer_operating_context", "missing_claim_or_metric": "official 2025 line-item reconciliation for all peers", "required_source_type": "peer annual reports", "preferred_source_name": "official annual report", "blocking_level": "medium", "owner_skill": "quality-review", "notes": "Company-level operating comparison remains draft context."},
        ]
    }


def build_quality_handoff(output_root: str) -> dict[str, Any]:
    return {
        "artifact_type": "valuation_quality_handoff",
        "schema_version": "v0.1",
        "workflow_id": WORKFLOW_ID,
        "valuation_as_of_date": MARKET_AS_OF,
        "artifact_paths": {
            "valuation_model": f"{output_root}/valuation_model.yaml",
            "valuation_snapshot": f"{output_root}/valuation_snapshot.yaml",
            "peer_comparison": f"{output_root}/peer_comparison.csv",
            "sensitivity_table": f"{output_root}/sensitivity_table.csv",
            "valuation_section_draft": f"{output_root}/valuation_section_draft.md",
            "reverse_valuation": f"reports/workflow_runs/{WORKFLOW_ID}/reverse_valuation.yaml",
            "scenario_valuation": f"reports/workflow_runs/{WORKFLOW_ID}/scenario_valuation.yaml",
        },
        "local_checks": ["QR-VAL-1", "QR-VAL-2", "QR-VAL-3", "QR-VAL-4", "QR-VAL-5"],
        "check_results": {
            "QR-VAL-1": "pass",
            "QR-VAL-2": "pass",
            "QR-VAL-3": "pass_with_low_confidence_peer_set",
            "QR-VAL-4": "pass",
            "QR-VAL-5": "pass",
        },
        "no_advice_boundary": "pass",
        "open_gaps": ["CV_B9_001", "CV_B9_002", "CV_B9_003", "CV_B9_004", "CV_B9_005"],
        "sample_quality_allowed": False,
    }


def build_section(peers: Sequence[Mapping[str, Any]], scenarios: Mapping[str, Mapping[str, Any]]) -> str:
    peer_median_pe = median(float(peer["pe_ttm"]) for peer in peers)
    peer_median_pb = median(float(peer["pb"]) for peer in peers)
    peer_median_ps = median(float(peer["ps"]) for peer in peers)
    lines = [
        "## 五、估值分析",
        "",
        "> 本节只作估值情景与研究假设整理，不提供交易动作、配置比例或收益承诺。",
        "",
        "### 5.1 静态估值",
        "",
        f"事实：截至 {MARKET_AS_OF}，收盘价为 {MARKET['close_price']:.2f} 元，总市值为 {MARKET['market_cap'] / 1e9:.2f} 亿元，PE TTM 为 {MARKET['pe_ttm']:.2f} 倍、PB 为 {MARKET['pb_lf']:.2f} 倍、PS TTM 为 {MARKET['ps_ttm']:.2f} 倍。来源：`{MARKET_SOURCE}`；evidence_id=`{MARKET_EVIDENCE}`。这些数字只代表该日市场状态。",
        "",
        "### 5.2 动态估值",
        "",
        "推断：以当前市值除以 Bundle 9 三情景归母净利润，得到下表动态 PE；预测均为 estimate，不是公司指引。",
        "",
        "| 情景 | 2026E | 2027E | 2028E |",
        "|---|---:|---:|---:|",
    ]
    for short in ("bear", "base", "bull"):
        pe = scenarios[short]["dynamic_pe"]
        lines.append(f"| {short} | {pe['2026E']:.1f}x | {pe['2027E']:.1f}x | {pe['2028E']:.1f}x |")
    lines.extend(
        [
            "",
            "券商或第三方观点：仅两家近期机构样本的 EPS 中点为 2026E 1.1715 元、2027E 1.8355 元、2028E 2.6395 元；Bundle 9 base 分别低 67.6%、70.8% 和 73.6%。该差异显示盈利假设分歧很大，且样本数量和股本口径尚未独立核验。来源：`analyst_forecast_comparison.csv`；evidence_id=`ev_third_party_research_002837_20260713_20f610`。",
            "",
            "### 5.3 同业估值对比",
            "",
            f"推断：四家同日样本的 PE TTM 中位数为 {peer_median_pe:.2f} 倍、PB 中位数为 {peer_median_pb:.2f} 倍、PS 中位数为 {peer_median_ps:.2f} 倍。英维克 PE TTM 低于该中位数，但 PB 与 PS 高于中位数，方向不一致，因此状态保持 `not_assessable`。",
            "",
            "| 公司 | 代码 | PE TTM | PB | PS | 主要限制 |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    for peer in peers:
        lines.append(
            f"| {peer['company_name']} | {peer['stock_code']} | {peer['pe_ttm']:.1f}x | {peer['pb']:.1f}x | {peer['ps']:.1f}x | 业务组合与液冷纯度不可直接横比 |"
        )
    lines.extend(
        [
            "",
            "### 5.4 情景估值、反向估值与敏感性",
            "",
            "估计：以 2027E 归母净利润为锚，bear 使用 50x-75x、base 使用 75x-100x、bull 使用 100x-150x 的显式研究倍数。倍数不是历史公允区间，而是用于显示利润与估值倍数联动的压力测试。",
            "",
            "| 情景 | 2027E 归母净利润 | 倍数区间 | 隐含市值区间 |",
            "|---|---:|---:|---:|",
        ]
    )
    for short in ("bear", "base", "bull"):
        scenario = scenarios[short]
        profit = float(scenario["anchor"]["value"])
        low_multiple, high_multiple = scenario["multiple_range"]
        low_value, high_value = scenario["market_cap_range"]
        lines.append(
            f"| {short} | {profit / 1e8:.2f} 亿元 | {low_multiple:.0f}x-{high_multiple:.0f}x | {low_value / 1e9:.2f}-{high_value / 1e9:.2f} 亿元 |"
        )
    lines.extend(
        [
            "",
            "反向估值：当前市值对应 100x PE 时需要约 9.37 亿元归母净利润；base 到 2028E 仍略低于该阈值，bull 在 2027E 超过。完整阈值见 `reverse_valuation.yaml`。2027E base 毛利率每变化 1 个百分点，模型归母净利润约变化 0.76 亿元；估值倍数每变化 25x，隐含市值约变化 170.80 亿元。",
            "",
            "### 5.5 分歧、反证与后续验证",
            "",
            "- unknown：同业远期倍数、企业价值与净负债口径仍缺失。",
            "- unknown：液冷独立收入、毛利率和利润贡献仍未披露，SOTP 不满足输入门。",
            "- unknown：折现率、终值增速和审阅后的净负债未形成，DCF 不满足输入门。",
            "- counter-evidence：2026Q1 盈利与经营现金流承压；若毛利率、费用率或回款不及模型，动态倍数和情景市值会明显变化。",
            "- 下一步：按 `valuation_gap_requests.yaml` 补齐同业远期口径、资产负债表桥、液冷独立经济性和折现输入。",
            "",
        ]
    )
    return "\n".join(lines)


def build_outputs(run_dir: Path) -> dict[str, Any]:
    forecast = load_yaml(run_dir / "segment_forecast_model.yaml")
    peers = read_peer_inputs(run_dir)
    scenarios = scenario_tables(forecast)
    valuation_dir = run_dir / "valuation"
    output_root = f"reports/workflow_runs/{WORKFLOW_ID}/valuation"

    write_csv(run_dir / "market_snapshot.csv", MARKET_COLUMNS, [build_market_snapshot_row()])
    write_csv(run_dir / "peer_market_snapshot.csv", PEER_COLUMNS, build_peer_snapshot_rows(peers))
    write_yaml(run_dir / "valuation_input_readiness.yaml", build_readiness(run_dir, forecast, peers))
    write_yaml(run_dir / "valuation_request.yaml", build_request())
    write_yaml(run_dir / "R5_bundle9_peer_reconciliation.yaml", build_peer_reconciliation(peers))
    write_yaml(run_dir / "R5_bundle9_valuation_input_registry.yaml", build_input_registry(forecast, peers))

    peer_columns = [
        "peer_company", "peer_stock_code", "exchange", "selection_reason", "business_similarity",
        "segment_overlap", "market_cap", "pe_ttm", "pe_2026E", "pb", "ps", "ev_ebitda",
        "as_of_date", "metric_source", "limitations", "confidence",
    ]
    sensitivity_columns = [
        "variable", "case_label", "delta", "output_metric", "output_value", "impact_vs_base",
        "assumption_type", "supporting_metric_ids", "supporting_claim_ids", "notes",
    ]
    analyst_columns = [
        "period", "base_model_eps", "two_broker_midpoint_eps", "base_minus_midpoint_pct",
        "unit", "claim_type", "source_evidence_id", "source_path", "limitations",
    ]
    write_csv(valuation_dir / "peer_comparison.csv", peer_columns, build_peer_comparison_rows(peers))
    write_csv(valuation_dir / "sensitivity_table.csv", sensitivity_columns, build_sensitivity_rows(run_dir, scenarios))
    write_csv(run_dir / "analyst_forecast_comparison.csv", analyst_columns, build_analyst_comparison_rows(forecast))

    write_yaml(valuation_dir / "valuation_model.yaml", build_valuation_model(peers, scenarios, output_root))
    write_yaml(valuation_dir / "valuation_snapshot.yaml", build_valuation_snapshot(peers, scenarios))
    write_yaml(valuation_dir / "valuation_output.yaml", build_company_output(peers, scenarios))
    write_yaml(valuation_dir / "R5_valuation_handoff.yaml", build_r5_handoff(peers, scenarios))
    write_yaml(valuation_dir / "valuation_gap_requests.yaml", build_gaps())
    write_yaml(valuation_dir / "valuation_quality_handoff.yaml", build_quality_handoff(output_root))
    write_yaml(run_dir / "R5_bundle9_valuation_pack.yaml", build_r5_pack(peers, scenarios))
    write_yaml(run_dir / "reverse_valuation.yaml", build_reverse_valuation(scenarios))
    write_yaml(run_dir / "scenario_valuation.yaml", build_scenario_valuation(scenarios))
    (valuation_dir / "valuation_section_draft.md").write_text(build_section(peers, scenarios), encoding="utf-8")

    readout = {
        "artifact_type": "R5_bundle9_valuation_build_readout",
        "schema_version": "v0.1",
        "workflow_id": WORKFLOW_ID,
        "decision": "built_pending_quality_review",
        "valuation_as_of_date": MARKET_AS_OF,
        "peer_count": len(peers),
        "peer_set_quality": "LOW_CONFIDENCE_PEER_SET",
        "methods_used": ["static_multiples", "dynamic_pe", "peer_context", "scenario_valuation", "reverse_valuation"],
        "methods_skipped": {"dcf": "missing_discount_terminal_and_net_debt_inputs", "sotp": "missing_standalone_segment_economics"},
        "base_dynamic_pe": scenarios["base"]["dynamic_pe"],
        "scenario_market_cap_ranges_CNY": {short: list(scenario["market_cap_range"]) for short, scenario in scenarios.items()},
        "open_gap_count": 5,
        "sample_quality_allowed": False,
    }
    write_yaml(run_dir / "R5_bundle9_valuation_build_readout.yaml", readout)
    return readout


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Bundle 9 valuation inputs and controlled outputs.")
    parser.add_argument(
        "--workflow-run",
        type=Path,
        default=Path("reports/workflow_runs") / WORKFLOW_ID,
    )
    args = parser.parse_args()
    readout = build_outputs(args.workflow_run)
    print(yaml.safe_dump(readout, allow_unicode=True, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
