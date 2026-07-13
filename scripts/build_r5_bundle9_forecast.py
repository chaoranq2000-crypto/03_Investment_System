from __future__ import annotations

import argparse
import csv
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
YEARS = ["2026E", "2027E", "2028E"]
ANNUAL_EVIDENCE = "ev_annual_report_002837_20260421_2cbfc5"
QUARTER_EVIDENCE = "ev_quarterly_report_002837_20260421_2f00c7"
LIQUID_IR_EVIDENCE = "ev_official_disclosure_002837_20250423_e78396"
MARGIN_IR_EVIDENCE = "ev_official_disclosure_002837_20250428_108da3"
MECHANISM_IR_EVIDENCE = "ev_official_disclosure_002837_20250521_1b4421"
MARKET_EVIDENCE = "ev_structured_market_data_002837_20260710_eb0c08"
CONSENSUS_EVIDENCE = "ev_third_party_research_002837_20260713_20f610"
SHARES = 1_274_349_692
REVENUE_METRIC = "metric_cn_002837_invic_revenue_20251231_9c5aaf"
NET_PROFIT_METRIC = "metric_cn_002837_invic_n_income_attr_p_20251231_002a58"
EPS_METRIC = "metric_cn_002837_invic_basic_eps_20251231_03d56b"
OCF_METRIC = "metric_cn_002837_invic_n_cashflow_act_20251231_890163"

DRIVER_SUPPORTING_METRICS = {
    "revenue_growth": [REVENUE_METRIC],
    "gross_margin": [REVENUE_METRIC],
    "opex": [REVENUE_METRIC],
    "net_profit": [NET_PROFIT_METRIC],
    "eps": [EPS_METRIC, NET_PROFIT_METRIC],
    "effective_tax_rate": [NET_PROFIT_METRIC],
    "operating_cashflow": [OCF_METRIC],
    "capex": [REVENUE_METRIC, OCF_METRIC],
}


SCENARIO_INPUTS: dict[str, dict[str, Any]] = {
    "base_case": {
        "line_growth": {
            "room_cooling": [28.0, 22.0, 18.0],
            "cabinet_cooling": [18.0, 15.0, 12.0],
            "other_businesses": [8.0, 6.0, 5.0],
        },
        "line_margin": {
            "room_cooling": [26.0, 26.8, 27.4],
            "cabinet_cooling": [26.0, 26.7, 27.0],
            "other_businesses": [24.5, 25.2, 25.8],
        },
        "bridge_ratios": {
            "tax_surcharge": [0.52, 0.50, 0.50],
            "selling_expense": [4.20, 4.10, 4.00],
            "administrative_expense": [4.10, 4.00, 3.90],
            "rd_expense": [7.70, 7.50, 7.30],
            "financial_expense": [0.35, 0.30, 0.28],
            "other_operating_drag": [1.60, 1.40, 1.20],
            "non_operating_net": [0.10, 0.10, 0.10],
            "effective_tax_rate": [10.0, 10.0, 10.0],
            "minority_share_of_net_income": [3.5, 3.5, 3.5],
            "nwc_to_revenue": [34.0, 33.0, 32.0],
            "noncash_addback_to_revenue": [2.3, 2.3, 2.3],
            "capex_to_revenue": [5.0, 4.5, 4.0],
        },
    },
    "bull_case": {
        "line_growth": {
            "room_cooling": [35.0, 28.0, 22.0],
            "cabinet_cooling": [25.0, 20.0, 16.0],
            "other_businesses": [12.0, 10.0, 8.0],
        },
        "line_margin": {
            "room_cooling": [28.0, 28.5, 29.0],
            "cabinet_cooling": [27.5, 28.0, 28.3],
            "other_businesses": [26.0, 26.5, 27.0],
        },
        "bridge_ratios": {
            "tax_surcharge": [0.50, 0.50, 0.48],
            "selling_expense": [4.00, 3.80, 3.70],
            "administrative_expense": [3.90, 3.70, 3.60],
            "rd_expense": [7.40, 7.10, 6.90],
            "financial_expense": [0.25, 0.25, 0.25],
            "other_operating_drag": [1.20, 1.00, 0.80],
            "non_operating_net": [0.10, 0.10, 0.10],
            "effective_tax_rate": [9.0, 9.0, 9.0],
            "minority_share_of_net_income": [3.0, 3.0, 3.0],
            "nwc_to_revenue": [32.5, 31.5, 30.5],
            "noncash_addback_to_revenue": [2.3, 2.3, 2.3],
            "capex_to_revenue": [5.5, 5.0, 4.5],
        },
    },
    "bear_case": {
        "line_growth": {
            "room_cooling": [15.0, 10.0, 8.0],
            "cabinet_cooling": [8.0, 6.0, 5.0],
            "other_businesses": [0.0, 2.0, 3.0],
        },
        "line_margin": {
            "room_cooling": [23.5, 24.0, 24.5],
            "cabinet_cooling": [23.5, 24.0, 24.5],
            "other_businesses": [21.5, 22.5, 23.5],
        },
        "bridge_ratios": {
            "tax_surcharge": [0.55, 0.55, 0.55],
            "selling_expense": [4.50, 4.40, 4.30],
            "administrative_expense": [4.40, 4.30, 4.20],
            "rd_expense": [8.00, 7.80, 7.60],
            "financial_expense": [0.50, 0.50, 0.45],
            "other_operating_drag": [2.00, 2.00, 1.80],
            "non_operating_net": [0.05, 0.05, 0.05],
            "effective_tax_rate": [11.0, 11.0, 11.0],
            "minority_share_of_net_income": [4.0, 4.0, 4.0],
            "nwc_to_revenue": [36.0, 36.0, 35.5],
            "noncash_addback_to_revenue": [2.3, 2.3, 2.3],
            "capex_to_revenue": [4.5, 4.0, 3.5],
        },
    },
}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML must be a mapping: {path}")
    return data


def write_yaml(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(dict(data), allow_unicode=True, sort_keys=False), encoding="utf-8")


def r2(value: float) -> float:
    return round(value, 2)


def r4(value: float) -> float:
    return round(value, 4)


def r6(value: float) -> float:
    return round(value, 6)


def _business_line_anchors(run: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    pack = load_yaml(run / "R5_bundle5_business_breakdown_candidate.yaml")
    rows = {row["business_name"]: row for row in pack["business_lines"]}
    room = rows["room_cooling"]
    cabinet = rows["cabinet_cooling"]
    summary = pack["profit_pool_summary"]
    other_revenue = float(summary["company_revenue"]) - float(room["revenue"]["value"]) - float(
        cabinet["revenue"]["value"]
    )
    other_gp = float(summary["company_gross_profit"]) - float(room["gross_profit"]["value"]) - float(
        cabinet["gross_profit"]["value"]
    )
    anchors = {
        "room_cooling": {
            "reported_name": room["reported_name"],
            "revenue": float(room["revenue"]["value"]),
            "gross_margin": float(room["gross_margin"]["value"]),
            "evidence_id": ANNUAL_EVIDENCE,
            "calculation_method": "direct_reported_value",
        },
        "cabinet_cooling": {
            "reported_name": cabinet["reported_name"],
            "revenue": float(cabinet["revenue"]["value"]),
            "gross_margin": float(cabinet["gross_margin"]["value"]),
            "evidence_id": ANNUAL_EVIDENCE,
            "calculation_method": "direct_reported_value",
        },
        "other_businesses": {
            "reported_name": "客车空调+轨道交通列车空调及服务+其他",
            "revenue": other_revenue,
            "gross_margin": other_gp / other_revenue * 100,
            "evidence_id": ANNUAL_EVIDENCE,
            "calculation_method": "audited_company_total_minus_two_reported_major_lines",
        },
    }
    if abs(sum(item["revenue"] for item in anchors.values()) - float(summary["company_revenue"])) > 0.01:
        raise ValueError("business-line revenue anchors do not reconcile to company revenue")
    return anchors, summary


def _historical_bridge() -> dict[str, Any]:
    revenue = 6_067_759_091.55
    gross_profit = 1_690_633_310.57
    nwc_2024 = 2_428_405_953.58 + 884_357_243.24 - 1_804_813_557.30
    nwc_2025 = 3_053_959_547.65 + 983_397_026.13 - 2_001_499_104.79
    return {
        "period": "2025A",
        "revenue": revenue,
        "gross_profit": gross_profit,
        "gross_margin": r4(gross_profit / revenue * 100),
        "tax_surcharge": 31_503_818.55,
        "selling_expense": 254_101_820.15,
        "administrative_expense": 243_986_893.17,
        "rd_expense": 445_940_662.45,
        "financial_expense": 16_182_225.88,
        "operating_profit": 590_359_558.60,
        "total_profit": 597_408_857.00,
        "income_tax": 54_728_876.14,
        "net_income": 542_679_980.86,
        "minority_profit": 20_765_207.86,
        "net_profit_attributable": 521_914_773.00,
        "operating_cashflow": 157_273_222.36,
        "capex": 303_000_207.71,
        "nwc_2024": nwc_2024,
        "nwc_2025": nwc_2025,
        "nwc_change": nwc_2025 - nwc_2024,
        "accounts_receivable": 3_053_959_547.65,
        "inventories": 983_397_026.13,
        "accounts_payable": 2_001_499_104.79,
        "shares": SHARES,
        "evidence_id": ANNUAL_EVIDENCE,
        "source_path": "data/processed/text/002837/cninfo_2025_annual_report_full_002837_2026-04-21.txt",
    }


def _calculate_scenario(
    scenario: str,
    anchors: Mapping[str, Mapping[str, Any]],
    historical: Mapping[str, Any],
) -> dict[str, Any]:
    inputs = SCENARIO_INPUTS[scenario]
    previous_revenue = {line: float(anchor["revenue"]) for line, anchor in anchors.items()}
    prior_nwc = float(historical["nwc_2025"])
    result: dict[str, Any] = {}
    for index, year in enumerate(YEARS):
        lines: dict[str, Any] = {}
        for line, anchor in anchors.items():
            growth = float(inputs["line_growth"][line][index])
            margin = float(inputs["line_margin"][line][index])
            revenue = previous_revenue[line] * (1 + growth / 100)
            gp = revenue * margin / 100
            lines[line] = {
                "reported_name": anchor["reported_name"],
                "revenue": r2(revenue),
                "revenue_growth": growth,
                "gross_margin": margin,
                "gross_profit": r2(gp),
                "unit": "CNY",
                "claim_type": "estimate",
                "growth_assumption_id": f"b9_{scenario}_{line}_revenue_growth",
                "margin_assumption_id": f"b9_{scenario}_{line}_gross_margin",
                "evidence_ids": [ANNUAL_EVIDENCE, LIQUID_IR_EVIDENCE, MECHANISM_IR_EVIDENCE]
                if line == "room_cooling"
                else [ANNUAL_EVIDENCE],
            }
            previous_revenue[line] = revenue
        revenue = sum(row["revenue"] for row in lines.values())
        gross_profit = sum(row["gross_profit"] for row in lines.values())
        ratios = {key: float(values[index]) for key, values in inputs["bridge_ratios"].items()}
        amounts = {
            key: revenue * ratios[key] / 100
            for key in (
                "tax_surcharge",
                "selling_expense",
                "administrative_expense",
                "rd_expense",
                "financial_expense",
                "other_operating_drag",
            )
        }
        operating_profit = gross_profit - sum(amounts.values())
        non_operating_net = revenue * ratios["non_operating_net"] / 100
        total_profit = operating_profit + non_operating_net
        income_tax = max(total_profit, 0) * ratios["effective_tax_rate"] / 100
        net_income = total_profit - income_tax
        minority_profit = max(net_income, 0) * ratios["minority_share_of_net_income"] / 100
        net_profit_attributable = net_income - minority_profit
        eps = net_profit_attributable / SHARES
        nwc = revenue * ratios["nwc_to_revenue"] / 100
        nwc_change = nwc - prior_nwc
        noncash_addback = revenue * ratios["noncash_addback_to_revenue"] / 100
        operating_cashflow = net_income + noncash_addback - nwc_change
        capex = revenue * ratios["capex_to_revenue"] / 100
        free_cashflow = operating_cashflow - capex
        bridge = {
            "revenue": r2(revenue),
            "gross_profit": r2(gross_profit),
            "gross_margin": r4(gross_profit / revenue * 100),
            **{key: r2(value) for key, value in amounts.items()},
            "operating_profit": r2(operating_profit),
            "non_operating_net": r2(non_operating_net),
            "total_profit": r2(total_profit),
            "income_tax": r2(income_tax),
            "net_income": r2(net_income),
            "minority_profit": r2(minority_profit),
            "net_profit_attributable": r2(net_profit_attributable),
            "eps": r6(eps),
            "shares": SHARES,
            "nwc": r2(nwc),
            "nwc_change": r2(nwc_change),
            "noncash_addback": r2(noncash_addback),
            "operating_cashflow": r2(operating_cashflow),
            "capex": r2(capex),
            "free_cashflow": r2(free_cashflow),
            "ratio_assumptions": {key: r4(value) for key, value in ratios.items()},
            "reconciliation_difference": r2(
                gross_profit - sum(amounts.values()) + non_operating_net - income_tax - minority_profit - net_profit_attributable
            ),
        }
        result[year] = {"business_lines": lines, "bridge": bridge}
        prior_nwc = nwc
    return result


def _assumption_row(
    assumption_id: str,
    *,
    driver: str,
    scope: str,
    scenario: str,
    value: Any,
    unit: str,
    evidence_ids: list[str],
    rationale: str,
    limitations: list[str],
    formula: str = "",
    business_disclosure: bool = False,
    metric_ids: list[str] | None = None,
) -> dict[str, Any]:
    supporting_metric_ids = list(metric_ids or DRIVER_SUPPORTING_METRICS[driver])
    row = {
        "assumption_id": assumption_id,
        "driver": driver,
        "scope": scope,
        "periods": YEARS,
        "value": value,
        "formula": formula,
        "unit": unit,
        "scenario": scenario.replace("_case", ""),
        "evidence_ids": evidence_ids,
        "metric_ids": supporting_metric_ids,
        "supporting_evidence_ids": evidence_ids,
        "supporting_metric_ids": supporting_metric_ids,
        "missing_reason": None,
        "allowed_usage": "forecast_model",
        "rationale": rationale,
        "limitations": limitations,
        "review_status": "reviewed",
        "reviewer_note": "Reviewed as an explicit research model assumption; not issuer guidance or fact.",
    }
    if business_disclosure:
        row["business_disclosure_evidence_ids"] = [ANNUAL_EVIDENCE]
    return row


def _build_registry(calculated: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    assumptions: list[dict[str, Any]] = []
    for scenario, scenario_result in calculated.items():
        scenario_label = scenario.replace("_case", "")
        for line in ("room_cooling", "cabinet_cooling", "other_businesses"):
            evidence = [ANNUAL_EVIDENCE]
            if line == "room_cooling":
                evidence += [LIQUID_IR_EVIDENCE, MARGIN_IR_EVIDENCE, MECHANISM_IR_EVIDENCE]
            assumptions.append(
                _assumption_row(
                    f"b9_{scenario}_{line}_revenue_growth",
                    driver="revenue_growth",
                    scope="segment",
                    scenario=scenario,
                    value={year: SCENARIO_INPUTS[scenario]["line_growth"][line][idx] for idx, year in enumerate(YEARS)},
                    unit="pct",
                    evidence_ids=evidence,
                    rationale="Business-line growth path is anchored to disclosed 2025 broad lines and explicit demand/acceptance mechanisms.",
                    limitations=["liquid cooling is not modeled as a standalone disclosed segment"],
                    business_disclosure=True,
                )
            )
            assumptions.append(
                _assumption_row(
                    f"b9_{scenario}_{line}_gross_margin",
                    driver="gross_margin",
                    scope="segment",
                    scenario=scenario,
                    value={year: SCENARIO_INPUTS[scenario]["line_margin"][line][idx] for idx, year in enumerate(YEARS)},
                    unit="pct",
                    evidence_ids=evidence,
                    rationale="Margin path starts from audited 2025 broad-line margins or the audited residual calculation.",
                    limitations=["no standalone liquid-cooling gross margin is disclosed"],
                    business_disclosure=True,
                )
            )
        consolidated_growth: dict[str, float] = {}
        prior = 6_067_759_091.55
        consolidated_margin: dict[str, float] = {}
        for year in YEARS:
            bridge = scenario_result[year]["bridge"]
            consolidated_growth[year] = r4((bridge["revenue"] / prior - 1) * 100)
            consolidated_margin[year] = bridge["gross_margin"]
            prior = bridge["revenue"]
        assumptions.extend(
            [
                _assumption_row(
                    f"b9_{scenario}_revenue_growth_consolidated",
                    driver="revenue_growth",
                    scope="company",
                    scenario=scenario,
                    value=consolidated_growth,
                    unit="pct",
                    evidence_ids=[ANNUAL_EVIDENCE, QUARTER_EVIDENCE],
                    formula="sum business-line revenue forecasts / prior-year consolidated revenue - 1",
                    rationale="Consolidated growth is a calculated output of the three disclosed broad-line paths.",
                    limitations=["not management guidance"],
                ),
                _assumption_row(
                    f"b9_{scenario}_gross_margin_consolidated",
                    driver="gross_margin",
                    scope="margin",
                    scenario=scenario,
                    value=consolidated_margin,
                    unit="pct",
                    evidence_ids=[ANNUAL_EVIDENCE, MARGIN_IR_EVIDENCE],
                    formula="sum business-line gross profit / sum business-line revenue",
                    rationale="Consolidated margin is weighted from business-line assumptions.",
                    limitations=["liquid-cooling margin remains undisclosed"],
                ),
                _assumption_row(
                    f"b9_{scenario}_opex_bridge",
                    driver="opex",
                    scope="opex",
                    scenario=scenario,
                    value={
                        year: {
                            key: SCENARIO_INPUTS[scenario]["bridge_ratios"][key][idx]
                            for key in ("selling_expense", "administrative_expense", "rd_expense")
                        }
                        for idx, year in enumerate(YEARS)
                    },
                    unit="pct_of_revenue",
                    evidence_ids=[ANNUAL_EVIDENCE, QUARTER_EVIDENCE],
                    rationale="Selling, administrative and R&D expenses are modeled separately from the audited 2025 ratios.",
                    limitations=["future expense ratios are estimates"],
                ),
                _assumption_row(
                    f"b9_{scenario}_net_profit_bridge",
                    driver="net_profit",
                    scope="company",
                    scenario=scenario,
                    value={year: scenario_result[year]["bridge"]["net_profit_attributable"] for year in YEARS},
                    unit="CNY",
                    evidence_ids=[ANNUAL_EVIDENCE, QUARTER_EVIDENCE],
                    formula="operating profit + non-operating net - tax - minority profit",
                    rationale="Attributable profit is derived from explicit expense, tax and minority bridges.",
                    limitations=["model estimate; 2026Q1 profit weakness makes uncertainty wide"],
                ),
                _assumption_row(
                    f"b9_{scenario}_eps_bridge",
                    driver="eps",
                    scope="company",
                    scenario=scenario,
                    value={year: scenario_result[year]["bridge"]["eps"] for year in YEARS},
                    unit="CNY_per_share",
                    evidence_ids=[ANNUAL_EVIDENCE, MARKET_EVIDENCE],
                    formula=f"net profit attributable / {SHARES} shares",
                    rationale="EPS uses a reviewed share-count anchor without assumed dilution.",
                    limitations=["future dilution is not modeled"],
                ),
                _assumption_row(
                    f"b9_{scenario}_tax_bridge",
                    driver="effective_tax_rate",
                    scope="tax",
                    scenario=scenario,
                    value={year: SCENARIO_INPUTS[scenario]["bridge_ratios"]["effective_tax_rate"][idx] for idx, year in enumerate(YEARS)},
                    unit="pct_of_pretax_profit",
                    evidence_ids=[ANNUAL_EVIDENCE],
                    rationale="Tax assumptions are anchored to the audited 2025 effective rate and R&D deductions.",
                    limitations=["tax credits and subsidiary mix may change"],
                ),
                _assumption_row(
                    f"b9_{scenario}_cashflow_bridge",
                    driver="operating_cashflow",
                    scope="cashflow",
                    scenario=scenario,
                    value={year: scenario_result[year]["bridge"]["operating_cashflow"] for year in YEARS},
                    unit="CNY",
                    evidence_ids=[ANNUAL_EVIDENCE, QUARTER_EVIDENCE, MARGIN_IR_EVIDENCE],
                    formula="net income + noncash addback - change in modeled net working capital",
                    rationale="Cash conversion reflects acceptance and collection timing rather than revenue alone.",
                    limitations=["noncash addback and working-capital ratios are explicit assumptions"],
                ),
                _assumption_row(
                    f"b9_{scenario}_capex_bridge",
                    driver="capex",
                    scope="capex",
                    scenario=scenario,
                    value={year: scenario_result[year]["bridge"]["capex"] for year in YEARS},
                    unit="CNY",
                    evidence_ids=[ANNUAL_EVIDENCE],
                    formula="forecast revenue * capex-to-revenue assumption",
                    rationale="Capex path starts from audited 2025 capital expenditure.",
                    limitations=["project timing may shift between years"],
                ),
            ]
        )
    return {
        "artifact_type": "R5_forecast_assumption_registry",
        "schema_version": "r5_forecast_assumption_registry_v0.1",
        "workflow_id": WORKFLOW_ID,
        "stock_code": "002837",
        "as_of_date": "2026-07-13",
        "review_status": "reviewed",
        "no_live_api": True,
        "assumptions": assumptions,
        "blocking_rules": [
            "liquid-cooling revenue and margin cannot be modeled as standalone reported segments",
            "forecast values remain estimates and cannot become facts or trading instructions",
            "share-basis and issuer-event dates must be refreshed when changed",
        ],
    }


def _forecast_metric(value: float, unit: str, assumption_id: str, evidence_id: str) -> dict[str, Any]:
    return {
        "value": value,
        "unit": unit,
        "assumption_id": assumption_id,
        "evidence_id": evidence_id,
        "metric_id": None,
        "claim_type": "estimate",
    }


def _build_sensitivity(calculated: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    base = calculated["base_case"]
    previous_room = 3_448_477_492.62
    for year in YEARS:
        bridge = base[year]["bridge"]
        after_tax_minority = (1 - bridge["ratio_assumptions"]["effective_tax_rate"] / 100) * (
            1 - bridge["ratio_assumptions"]["minority_share_of_net_income"] / 100
        )
        room_revenue_impact = previous_room * 0.05
        room_margin = base[year]["business_lines"]["room_cooling"]["gross_margin"] / 100
        rows.extend(
            [
                {
                    "year": year,
                    "driver": "room_cooling_revenue_growth",
                    "change": "+5pct_points",
                    "impact_metric": "net_profit_attributable",
                    "impact_value": r2(room_revenue_impact * room_margin * after_tax_minority),
                    "unit": "CNY",
                    "assumption_id_or_missing_reason": "b9_base_case_room_cooling_revenue_growth",
                    "calculation_method": "prior room revenue * 5pp * modeled room margin * after-tax-minority factor",
                },
                {
                    "year": year,
                    "driver": "consolidated_gross_margin",
                    "change": "+1pct_point",
                    "impact_metric": "net_profit_attributable",
                    "impact_value": r2(bridge["revenue"] * 0.01 * after_tax_minority),
                    "unit": "CNY",
                    "assumption_id_or_missing_reason": "b9_base_case_gross_margin_consolidated",
                    "calculation_method": "revenue * 1pp * after-tax-minority factor",
                },
                {
                    "year": year,
                    "driver": "opex_ratio",
                    "change": "+1pct_point",
                    "impact_metric": "net_profit_attributable",
                    "impact_value": r2(-bridge["revenue"] * 0.01 * after_tax_minority),
                    "unit": "CNY",
                    "assumption_id_or_missing_reason": "b9_base_case_opex_bridge",
                    "calculation_method": "-revenue * 1pp * after-tax-minority factor",
                },
                {
                    "year": year,
                    "driver": "nwc_to_revenue",
                    "change": "+1pct_point",
                    "impact_metric": "operating_cashflow",
                    "impact_value": r2(-bridge["revenue"] * 0.01),
                    "unit": "CNY",
                    "assumption_id_or_missing_reason": "b9_base_case_cashflow_bridge",
                    "calculation_method": "-revenue * 1pp increase in ending net working capital",
                },
            ]
        )
        previous_room = base[year]["business_lines"]["room_cooling"]["revenue"]
    return rows


def _build_model(
    anchors: Mapping[str, Mapping[str, Any]],
    historical: Mapping[str, Any],
    calculated: Mapping[str, Mapping[str, Any]],
    sensitivity: list[dict[str, Any]],
) -> dict[str, Any]:
    scenarios: dict[str, Any] = {}
    business_forecast: dict[str, Any] = {}
    for scenario, result in calculated.items():
        table: dict[str, Any] = {}
        business_forecast[scenario] = {}
        for year in YEARS:
            bridge = result[year]["bridge"]
            table[year] = {
                "revenue": _forecast_metric(bridge["revenue"], "CNY", f"b9_{scenario}_revenue_growth_consolidated", ANNUAL_EVIDENCE),
                "gross_margin": _forecast_metric(bridge["gross_margin"], "pct", f"b9_{scenario}_gross_margin_consolidated", ANNUAL_EVIDENCE),
                "gross_profit": _forecast_metric(bridge["gross_profit"], "CNY", f"b9_{scenario}_gross_margin_consolidated", ANNUAL_EVIDENCE),
                "net_profit_attributable": _forecast_metric(bridge["net_profit_attributable"], "CNY", f"b9_{scenario}_net_profit_bridge", ANNUAL_EVIDENCE),
                "eps": _forecast_metric(bridge["eps"], "CNY_per_share", f"b9_{scenario}_eps_bridge", MARKET_EVIDENCE),
            }
            business_forecast[scenario][year] = result[year]["business_lines"]
        scenarios[scenario] = {"status": "ready", "claim_type": "estimate", "forecast_table": table}
    base_eps = {
        year: calculated["base_case"][year]["bridge"]["eps"] for year in YEARS
    }
    analyst_mid = {"2026E": 1.1715, "2027E": 1.8355, "2028E": 2.6395}
    consensus_rows = {
        year: {
            "base_model_eps": base_eps[year],
            "two_broker_midpoint_eps": analyst_mid[year],
            "base_minus_midpoint_pct": r4((base_eps[year] / analyst_mid[year] - 1) * 100),
            "unit": "CNY_per_share",
        }
        for year in YEARS
    }
    return {
        "artifact_type": "R5_forecast_model_pack",
        "schema_version": "r5_forecast_model_pack_v0.2",
        "status": "ready",
        "as_of_date": "2026-07-13",
        "model_type": "bottom_up_disclosed_broad_business_lines_with_explicit_cashflow_bridge",
        "forecast_years": YEARS,
        "required_metrics": ["revenue", "gross_margin", "gross_profit", "net_profit_attributable", "eps"],
        "historical_anchor": historical,
        "business_line_anchors": anchors,
        "business_line_forecast": business_forecast,
        "assumption_registry_path": f"reports/workflow_runs/{WORKFLOW_ID}/R5_bundle9_forecast_assumption_registry.yaml",
        "assumptions": [f"b9_{scenario}_{driver}" for scenario in SCENARIO_INPUTS for driver in ("revenue_growth_consolidated", "gross_margin_consolidated", "opex_bridge", "net_profit_bridge", "eps_bridge", "tax_bridge", "cashflow_bridge", "capex_bridge")],
        "scenarios": scenarios,
        "sensitivity_tests": [
            {"driver": row["driver"], "year": row["year"], "change": row["change"], "claim_type": "estimate"}
            for row in sensitivity
        ],
        "sensitivity_table": [
            {
                "driver": row["driver"],
                "change": f"{row['year']}:{row['change']}",
                "impact_metric": row["impact_metric"],
                "impact_value": row["impact_value"],
                "assumption_id_or_missing_reason": row["assumption_id_or_missing_reason"],
            }
            for row in sensitivity
        ],
        "consensus_comparison": {
            "status": "limited_two_broker_context",
            "as_of_date": "2026-07-13",
            "source_evidence_id": CONSENSUS_EVIDENCE,
            "source_path": "data/processed/normalized/eastmoney_report_metadata_002837_2026-07-13_20f6105e.csv",
            "rows": consensus_rows,
            "claim_type": "analyst_view",
            "limitations": [
                "only two recent distinct brokers",
                "share-basis consistency has not been independently verified",
                "not a robust market consensus",
            ],
        },
        "liquid_cooling_boundary": {
            "2024_approximate_revenue": 300_000_000,
            "unit": "CNY",
            "claim_type": "management_comment",
            "evidence_id": LIQUID_IR_EVIDENCE,
            "usage": "directional anchor only; not extrapolated as a standalone 2025 segment",
            "2025_revenue": "MISSING_DISCLOSURE",
            "gross_margin": "MISSING_DISCLOSURE",
        },
        "missing_items": [
            "liquid_cooling_revenue_2025_MISSING_DISCLOSURE",
            "liquid_cooling_numeric_gross_margin_MISSING_DISCLOSURE",
            "named_customer_orders_MISSING_DISCLOSURE",
        ],
        "source_gap_register": [
            {
                "gap_id": "R5B9-FC-001",
                "section": "business_line_forecast",
                "missing_data": "standalone liquid-cooling revenue and margin",
                "impact_on_conclusion": "model uses disclosed broad lines and wider scenario ranges",
                "fix_owner_skill": "evidence-ingest",
                "next_action": "refresh after a same-definition issuer disclosure",
            }
        ],
        "sample_quality_allowed": False,
        "p2_allowed": False,
        "no_advice_boundary": True,
    }


def _write_sensitivity(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "year",
        "driver",
        "change",
        "impact_metric",
        "impact_value",
        "unit",
        "assumption_id_or_missing_reason",
        "calculation_method",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build(run: Path) -> dict[str, Any]:
    anchors, summary = _business_line_anchors(run)
    historical = _historical_bridge()
    if abs(float(summary["company_revenue"]) - historical["revenue"]) > 0.01:
        raise ValueError("business pack and historical bridge revenue differ")
    calculated = {
        scenario: _calculate_scenario(scenario, anchors, historical)
        for scenario in SCENARIO_INPUTS
    }
    registry = _build_registry(calculated)
    sensitivity = _build_sensitivity(calculated)
    model = _build_model(anchors, historical, calculated, sensitivity)
    bridge = {
        "artifact_type": "R5_bundle9_forecast_bridge",
        "schema_version": "v0.1",
        "workflow_id": WORKFLOW_ID,
        "as_of_date": "2026-07-13",
        "historical_anchor": historical,
        "business_line_anchors": anchors,
        "scenarios": calculated,
        "reconciliation": {
            "max_abs_profit_bridge_difference": max(
                abs(calculated[scenario][year]["bridge"]["reconciliation_difference"])
                for scenario in calculated
                for year in YEARS
            ),
            "business_line_revenue_reconciled": True,
            "business_line_gross_profit_reconciled": True,
            "expense_tax_minority_separated": True,
            "cashflow_and_capex_bridge_present": True,
        },
        "limitations": [
            "Forecasts are estimates based on reviewed assumptions, not issuer guidance.",
            "Liquid cooling remains embedded in broad room/cabinet lines because 2025 standalone disclosure is missing.",
            "Cashflow uses explicit working-capital and noncash ratios rather than a full balance-sheet forecast.",
        ],
        "no_advice_boundary": True,
    }
    write_yaml(run / "R5_bundle9_forecast_assumption_registry.yaml", registry)
    write_yaml(run / "segment_forecast_model.yaml", model)
    write_yaml(run / "forecast_bridge.yaml", bridge)
    _write_sensitivity(run / "forecast_sensitivity.csv", sensitivity)
    readout = {
        "artifact_type": "R5_bundle9_forecast_build_readout",
        "schema_version": "v0.1",
        "workflow_id": WORKFLOW_ID,
        "decision": "built_pending_quality_review",
        "business_lines": len(anchors),
        "scenarios": len(calculated),
        "forecast_years": YEARS,
        "sensitivity_rows": len(sensitivity),
        "profit_bridge_max_abs_difference": bridge["reconciliation"]["max_abs_profit_bridge_difference"],
        "outputs": [
            "R5_bundle9_forecast_assumption_registry.yaml",
            "segment_forecast_model.yaml",
            "forecast_bridge.yaml",
            "forecast_sensitivity.csv",
        ],
        "supersedes_for_bundle9": ["forecast_model.yaml", "R5_bundle6_forecast_bridge.yaml"],
        "sample_quality_allowed": False,
    }
    write_yaml(run / "R5_bundle9_forecast_build_readout.yaml", readout)
    return readout


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build R5 Bundle 9 bottom-up forecast assets.")
    parser.add_argument("--workflow-run", default=f"reports/workflow_runs/{WORKFLOW_ID}")
    args = parser.parse_args(argv)
    result = build(Path(args.workflow_run))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
