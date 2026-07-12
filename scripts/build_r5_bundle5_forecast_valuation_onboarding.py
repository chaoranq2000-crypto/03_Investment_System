#!/usr/bin/env python3
"""Build Bundle 5.4 reviewed forecast and valuation inputs."""
from __future__ import annotations

import argparse
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import yaml

WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
STOCK_CODE = "002837"
ANNUAL_EVIDENCE_ID = "ev_annual_report_002837_20260421_2cbfc5"
Q1_EVIDENCE_ID = "ev_quarterly_report_002837_20260421_2f00c7"
MARKET_EVIDENCE_ID = "ev_structured_market_data_002837_20260710_eb0c08"
MARKET_INPUT_ID = "r5_b5_market_002837_20260710"
PEER_INPUT_IDS = [
    f"r5_b5_peer_{code}_{metric}_20260710"
    for code in ("301018", "300499")
    for metric in ("pe_ttm", "pb", "ps_ttm")
]
BUSINESS_INPUT_IDS = [
    "r5_b5_business_2025_room_cooling_revenue",
    "r5_b5_business_2025_room_cooling_gross_margin",
    "r5_b5_business_2025_cabinet_cooling_revenue",
    "r5_b5_business_2025_cabinet_cooling_gross_margin",
    "r5_b5_business_2025_bus_air_conditioning_revenue",
    "r5_b5_business_2025_rail_air_conditioning_service_revenue",
    "r5_b5_business_2025_other_revenue",
    "r5_b5_business_2025_company_revenue",
    "r5_b5_business_2025_company_gross_margin",
]
SHARES = Decimal("1274349692")
CURRENT_PRICE = Decimal("73.54")
MARKET_CAP = Decimal("93715669584")


def _q(value: Decimal, places: str) -> float:
    return float(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))


def model_values() -> dict[str, dict[str, float]]:
    revenue_2025 = Decimal("6067759091.55")
    q1_revenue_2026 = Decimal("1175329313.61")
    q1_revenue_2025 = Decimal("932585781.26")
    revenue_growth_2026 = (q1_revenue_2026 / q1_revenue_2025 - 1) * 100
    revenue_2026 = revenue_2025 * (1 + revenue_growth_2026 / 100)
    revenue_2027 = revenue_2026 * Decimal("1.20")
    revenue_2028 = revenue_2027 * Decimal("1.15")

    q1_opex = Decimal("54265276.92") + Decimal("60111852.99") + Decimal("103436336.53")
    opex_ratio_2026 = q1_opex / q1_revenue_2026 * 100

    net_profit_2025 = Decimal("521914773.00")
    q1_profit_2025 = Decimal("48010475.41")
    q1_profit_2026 = Decimal("8657602.27")
    net_profit_2026 = q1_profit_2026 / (q1_profit_2025 / net_profit_2025)
    net_profit_2027 = revenue_2027 * Decimal("0.035")
    net_profit_2028 = revenue_2028 * Decimal("0.055")

    values = {
        "revenue_growth": {
            "2026E": _q(revenue_growth_2026, "0.0001"),
            "2027E": 20.0,
            "2028E": 15.0,
        },
        "gross_margin": {"2026E": 24.2935, "2027E": 25.5, "2028E": 26.5},
        "opex": {
            "2026E": _q(opex_ratio_2026, "0.0001"),
            "2027E": 17.5,
            "2028E": 16.5,
        },
        "revenue": {
            "2026E": _q(revenue_2026, "0.01"),
            "2027E": _q(revenue_2027, "0.01"),
            "2028E": _q(revenue_2028, "0.01"),
        },
        "net_profit": {
            "2026E": _q(net_profit_2026, "0.01"),
            "2027E": _q(net_profit_2027, "0.01"),
            "2028E": _q(net_profit_2028, "0.01"),
        },
        "eps": {
            "2026E": _q(net_profit_2026 / SHARES, "0.000001"),
            "2027E": _q(net_profit_2027 / SHARES, "0.000001"),
            "2028E": _q(net_profit_2028 / SHARES, "0.000001"),
        },
    }
    return values


def build_forecast_records(reviewed_at: str) -> list[dict[str, Any]]:
    values = model_values()
    common = {
        "workflow_id": WORKFLOW_ID,
        "stock_code": STOCK_CODE,
        "input_type": "forecast_assumptions",
        "as_of_date": "2026-07-10",
        "source_rank": "B",
        "review_status": "accepted",
        "reviewer": "codex",
        "reviewed_at": reviewed_at,
        "capture_method": "codex_model_assumption_review_user_authorized",
        "no_live_api": True,
        "periods": ["2026E", "2027E", "2028E"],
        "scenario": "base",
        "claim_type": "estimate",
        "management_guidance_used": False,
        "metric_ids": [],
        "supporting_metric_ids": [],
        "sample_quality_allowed": False,
    }
    specs = {
        "revenue_growth": {
            "source": Q1_EVIDENCE_ID,
            "unit": "pct",
            "scope": "company",
            "formula": {
                "2026E": "2026Q1 revenue / 2025Q1 revenue - 1",
                "2027E": "model assumption: growth slows to 20%",
                "2028E": "model assumption: growth slows to 15%",
            },
            "range": {"2026E": {"low": 20.0, "high": 32.23}, "2027E": {"low": 12.0, "high": 25.0}, "2028E": {"low": 8.0, "high": 20.0}},
            "evidence": [ANNUAL_EVIDENCE_ID, Q1_EVIDENCE_ID],
            "dependencies": BUSINESS_INPUT_IDS,
            "rationale": "2026 uses the reported Q1 year-on-year rate as a mechanical carry-forward; later years are explicit slowing-growth model assumptions.",
        },
        "gross_margin": {
            "source": Q1_EVIDENCE_ID,
            "unit": "pct",
            "scope": "margin",
            "formula": {
                "2026E": "carry forward 2026Q1 derived gross margin",
                "2027E": "model assumption: partial recovery to 25.5%",
                "2028E": "model assumption: partial recovery to 26.5%, below 2025A 27.86%",
            },
            "range": {"2026E": {"low": 23.0, "high": 27.86}, "2027E": {"low": 23.5, "high": 27.86}, "2028E": {"low": 24.0, "high": 27.86}},
            "evidence": [ANNUAL_EVIDENCE_ID, Q1_EVIDENCE_ID],
            "dependencies": ["r5_b5_business_2025_company_gross_margin"],
            "rationale": "The base path starts from the reported Q1 cost/revenue ratio and only partially normalizes toward the 2025 annual level.",
        },
        "opex": {
            "source": Q1_EVIDENCE_ID,
            "unit": "pct_of_revenue",
            "scope": "opex",
            "formula": {
                "2026E": "(2026Q1 selling + administrative + R&D expenses) / 2026Q1 revenue",
                "2027E": "model assumption: normalize to 17.5%",
                "2028E": "model assumption: normalize to 16.5%, still above 2025A 15.5581%",
            },
            "range": {"2026E": {"low": 15.5581, "high": 19.5}, "2027E": {"low": 15.5581, "high": 18.5}, "2028E": {"low": 15.0, "high": 18.0}},
            "evidence": [ANNUAL_EVIDENCE_ID, Q1_EVIDENCE_ID],
            "dependencies": [],
            "rationale": "The expense ratio is a model input, not a reported full-year outcome; it begins at the Q1 ratio and gradually normalizes.",
        },
        "net_profit": {
            "source": Q1_EVIDENCE_ID,
            "unit": "CNY",
            "scope": "company",
            "formula": {
                "2026E": "2026Q1 attributable profit / (2025Q1 attributable profit / 2025A attributable profit)",
                "2027E": "2027E revenue * 3.5% model net margin",
                "2028E": "2028E revenue * 5.5% model net margin",
            },
            "range": {
                "2026E": {"low": 34_630_409.08, "high": 521_914_773.00},
                "2027E": {"low": 183_531_388.23, "high": 550_594_164.69},
                "2028E": {"low": 316_591_644.70, "high": 738_713_837.62},
            },
            "evidence": [ANNUAL_EVIDENCE_ID, Q1_EVIDENCE_ID],
            "dependencies": [],
            "rationale": "The 2026 base is a mechanical prior-year seasonality run-rate; 2027-2028 margins are explicit model assumptions with wide ranges.",
        },
        "eps": {
            "source": MARKET_EVIDENCE_ID,
            "unit": "CNY_per_share",
            "scope": "company",
            "formula": {year: f"{year} attributable profit / 1,274,349,692 reviewed shares" for year in ("2026E", "2027E", "2028E")},
            "range": {
                "2026E": {"low": 0.027175, "high": 0.409559},
                "2027E": {"low": 0.144020, "high": 0.432055},
                "2028E": {"low": 0.248424, "high": 0.579677},
            },
            "evidence": [ANNUAL_EVIDENCE_ID, Q1_EVIDENCE_ID, MARKET_EVIDENCE_ID],
            "dependencies": [MARKET_INPUT_ID, "r5_b5_forecast_net_profit_base"],
            "rationale": "EPS uses the reviewed same-date total-share count and the model net-profit path; dilution after the snapshot is not assumed.",
        },
    }
    records: list[dict[str, Any]] = []
    for driver, spec in specs.items():
        records.append(
            {
                **common,
                "input_id": f"r5_b5_forecast_{driver}_base",
                "assumption_id": f"r5_b5_forecast_{driver}_base",
                "driver": driver,
                "metric_name": driver,
                "source_evidence_id": spec["source"],
                "value": values[driver],
                "unit": spec["unit"],
                "scope": spec["scope"],
                "evidence_ids": spec["evidence"],
                "supporting_evidence_ids": spec["evidence"],
                "dependency_input_ids": spec["dependencies"],
                "formula_by_period": spec["formula"],
                "sensitivity_range_by_period": spec["range"],
                "rationale": spec["rationale"],
                "reviewer_note": "Reviewed as a transparent research estimate; reported facts remain in the financial-history pack.",
                "limitations": [
                    "The path is a mechanical research scenario, not management guidance or consensus.",
                    "2026Q1 profitability was unusually weak relative to 2025, so uncertainty is wide.",
                ],
            }
        )
    return records


def _forecast_metric(value: float, unit: str, assumption_id: str, evidence_id: str) -> dict[str, Any]:
    return {
        "value": value,
        "unit": unit,
        "assumption_id": assumption_id,
        "evidence_id": evidence_id,
        "metric_id": None,
        "claim_type": "estimate",
    }


def _scenario_table(
    revenue_growths: tuple[float, float, float],
    gross_margins: tuple[float, float, float],
    net_margins: tuple[float, float, float],
) -> dict[str, dict[str, dict[str, Any]]]:
    revenue = Decimal("6067759091.55")
    table: dict[str, dict[str, dict[str, Any]]] = {}
    for year, growth, margin, net_margin in zip(("2026E", "2027E", "2028E"), revenue_growths, gross_margins, net_margins, strict=True):
        revenue *= 1 + Decimal(str(growth)) / 100
        net_profit = revenue * Decimal(str(net_margin)) / 100
        table[year] = {
            "revenue": _forecast_metric(_q(revenue, "0.01"), "CNY", "scenario_revenue_growth", Q1_EVIDENCE_ID),
            "gross_margin": _forecast_metric(margin, "pct", "scenario_gross_margin", Q1_EVIDENCE_ID),
            "gross_profit": _forecast_metric(_q(revenue * Decimal(str(margin)) / 100, "0.01"), "CNY", "scenario_gross_margin", Q1_EVIDENCE_ID),
            "net_profit_attributable": _forecast_metric(_q(net_profit, "0.01"), "CNY", "scenario_net_margin", Q1_EVIDENCE_ID),
            "eps": _forecast_metric(_q(net_profit / SHARES, "0.000001"), "CNY_per_share", "scenario_net_margin", MARKET_EVIDENCE_ID),
        }
    return table


def build_forecast_pack(records: list[dict[str, Any]]) -> dict[str, Any]:
    values = model_values()
    by_driver = {row["driver"]: row for row in records}
    base_table: dict[str, dict[str, Any]] = {}
    for year in ("2026E", "2027E", "2028E"):
        revenue = values["revenue"][year]
        margin = values["gross_margin"][year]
        net_profit = values["net_profit"][year]
        base_table[year] = {
            "revenue": _forecast_metric(revenue, "CNY", by_driver["revenue_growth"]["assumption_id"], Q1_EVIDENCE_ID),
            "gross_margin": _forecast_metric(margin, "pct", by_driver["gross_margin"]["assumption_id"], Q1_EVIDENCE_ID),
            "gross_profit": _forecast_metric(round(revenue * margin / 100, 2), "CNY", by_driver["gross_margin"]["assumption_id"], Q1_EVIDENCE_ID),
            "net_profit_attributable": _forecast_metric(net_profit, "CNY", by_driver["net_profit"]["assumption_id"], Q1_EVIDENCE_ID),
            "eps": _forecast_metric(values["eps"][year], "CNY_per_share", by_driver["eps"]["assumption_id"], MARKET_EVIDENCE_ID),
        }
    return {
        "artifact_type": "R5_forecast_model_pack",
        "schema_version": "r5_forecast_model_pack_v0.1",
        "status": "ready",
        "as_of_date": "2026-07-10",
        "model_type": "reviewed_mechanical_base_with_sensitivity_scenarios",
        "forecast_years": ["2026E", "2027E", "2028E"],
        "required_metrics": ["revenue", "gross_margin", "gross_profit", "net_profit_attributable", "eps"],
        "assumptions": records,
        "forecast_table": {"base_case": base_table},
        "scenarios": {
            "base_case": {"status": "ready", "claim_type": "estimate", "forecast_table": base_table},
            "bull_case": {
                "status": "sensitivity_estimate",
                "claim_type": "estimate",
                "forecast_table": _scenario_table((32.23, 25.0, 20.0), (27.86, 27.5, 27.0), (3.0, 6.0, 8.0)),
                "limitations": ["Upper sensitivity path is not management guidance."],
            },
            "bear_case": {
                "status": "sensitivity_estimate",
                "claim_type": "estimate",
                "forecast_table": _scenario_table((20.0, 15.0, 10.0), (23.0, 24.0, 25.0), (0.5, 2.0, 4.0)),
                "limitations": ["Lower sensitivity path is a model stress case."],
            },
        },
        "sensitivity_tests": [
            {"driver": "revenue_growth", "range_by_period": by_driver["revenue_growth"]["sensitivity_range_by_period"], "claim_type": "estimate"},
            {"driver": "gross_margin", "range_by_period": by_driver["gross_margin"]["sensitivity_range_by_period"], "claim_type": "estimate"},
            {"driver": "net_profit", "range_by_period": by_driver["net_profit"]["sensitivity_range_by_period"], "claim_type": "estimate"},
        ],
        "consensus_comparison": {"status": "not_supplied", "note": "No consensus or third-party forecast was used."},
        "missing_items": [],
        "source_gap_register": [],
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }


def net_debt_bridge() -> dict[str, Any]:
    components = {
        "cash": Decimal("917139183.43"),
        "short_term_borrowings": Decimal("939000000.00"),
        "current_noncurrent_liabilities": Decimal("246338651.34"),
        "long_term_borrowings": Decimal("351026719.14"),
        "lease_liabilities": Decimal("78909142.62"),
    }
    gross_debt = sum((value for key, value in components.items() if key != "cash"), Decimal("0"))
    net_debt = gross_debt - components["cash"]
    return {
        "as_of_date": "2026-03-31",
        "currency": "CNY",
        "components": {key: _q(value, "0.01") for key, value in components.items()},
        "gross_debt": _q(gross_debt, "0.01"),
        "net_debt_proxy": _q(net_debt, "0.01"),
        "evidence_id": Q1_EVIDENCE_ID,
        "page_or_table_locator": "2026Q1 report PDF pages 6-8; consolidated balance sheet",
        "calculation_method": "short-term borrowings + current non-current liabilities + long-term borrowings + lease liabilities - cash",
        "claim_type": "inference",
        "confidence": "low",
        "limitations": [
            "Current non-current liabilities are used as one disclosed aggregate; detailed debt/lease composition is not reallocated.",
            "Restricted cash and the cash-equivalent treatment of trading financial assets were not reviewed, so this is a proxy rather than a precise net-debt fact.",
        ],
    }


def build_valuation_record(reviewed_at: str, forecast_records: list[dict[str, Any]]) -> dict[str, Any]:
    bridge = net_debt_bridge()
    return {
        "input_id": "r5_b5_valuation_context_002837_20260710",
        "valuation_input_id": "r5_b5_valuation_context_002837_20260710",
        "workflow_id": WORKFLOW_ID,
        "stock_code": STOCK_CODE,
        "input_type": "valuation_inputs",
        "as_of_date": "2026-07-10",
        "valuation_date": "2026-07-10",
        "source_evidence_id": MARKET_EVIDENCE_ID,
        "source_rank": "B",
        "review_status": "accepted",
        "reviewer": "codex",
        "reviewed_at": reviewed_at,
        "capture_method": "company_valuation_subskill_method_review_user_authorized",
        "no_live_api": True,
        "currency": "CNY",
        "share_count_basis": "reviewed daily_basic total_share on valuation date",
        "shares_outstanding": int(SHARES),
        "net_debt_cash_bridge": bridge,
        "requested_methods": ["relative_pe"],
        "method_eligibility": {
            "relative_pe": {"status": "eligible_low_confidence_context_only", "reason": "same-date PE TTM exists for two exposure-grounded peers; business mixes differ and PB/PS comparisons point in the opposite direction"},
            "dcf": {"status": "excluded", "reason": "tax, capex, working-capital, discount-rate and terminal assumptions are not sufficiently reviewed"},
            "sotp": {"status": "excluded", "reason": "liquid-cooling-specific revenue and profit splits are not separately disclosed"},
        },
        "market_input_ids": [MARKET_INPUT_ID],
        "peer_input_ids": PEER_INPUT_IDS,
        "forecast_assumption_ids": [row["assumption_id"] for row in forecast_records],
        "business_disclosure_input_ids": BUSINESS_INPUT_IDS,
        "supporting_evidence_ids": [ANNUAL_EVIDENCE_ID, Q1_EVIDENCE_ID, MARKET_EVIDENCE_ID],
        "accounting_basis": "PE TTM on 2026-07-10; model EPS for 2026E-2028E; CNY consolidated company basis",
        "scenario_output_boundary": "relative multiple context and forward-PE sensitivity only; no price output",
        "cross_multiple_context": {
            "subject": {"pe_ttm": 194.2045, "pb": 27.0715, "ps_ttm": 14.8507},
            "peer_median": {"pe_ttm": 310.1249, "pb": 12.33865, "ps_ttm": 11.32265},
            "label": "mixed_multiple_signal_not_assessable",
        },
        "limitations": [
            "The peer set has two companies and remains low confidence.",
            "Trailing PE is affected by the subject's weak 2026Q1 attributable profit.",
            "Forecast values are model estimates rather than reported facts or management guidance.",
        ],
        "no_advice_boundary": True,
        "sample_quality_allowed": False,
    }


def _valuation_metric(value: Any, unit: str, evidence_id: str | None, *, missing_reason: str | None = None, method: str = "direct") -> dict[str, Any]:
    result = {"value": value, "unit": unit, "evidence_id": evidence_id, "metric_id": None, "calculation_method": method}
    if value is None:
        result["missing_reason"] = missing_reason
    return result


def build_valuation_pack(forecast_records: list[dict[str, Any]]) -> dict[str, Any]:
    values = model_values()
    bridge = net_debt_bridge()
    enterprise_value = _q(MARKET_CAP + Decimal(str(bridge["net_debt_proxy"])), "0.01")
    forward_pe = {year: _q(CURRENT_PRICE / Decimal(str(values["eps"][year])), "0.01") for year in ("2026E", "2027E", "2028E")}
    peer_rows = [
        {"peer_stock_code": "301018", "peer_company_name": "申菱环境", "metric_name": "pe_ttm", "multiple_value": 234.3524, "unit": "multiple", "as_of_date": "2026-07-10", "evidence_id": MARKET_EVIDENCE_ID, "input_id": "r5_b5_peer_301018_pe_ttm_20260710"},
        {"peer_stock_code": "300499", "peer_company_name": "高澜股份", "metric_name": "pe_ttm", "multiple_value": 385.8974, "unit": "multiple", "as_of_date": "2026-07-10", "evidence_id": MARKET_EVIDENCE_ID, "input_id": "r5_b5_peer_300499_pe_ttm_20260710"},
    ]
    return {
        "artifact_type": "R5_valuation_pack",
        "schema_version": "r5_valuation_pack_v0.2",
        "status": "partial",
        "as_of_date": "2026-07-10",
        "market_snapshot": {
            "as_of_date": "2026-07-10",
            "current_price": _valuation_metric(73.54, "CNY_per_share", MARKET_EVIDENCE_ID),
            "market_cap": _valuation_metric(93_715_669_584, "CNY", MARKET_EVIDENCE_ID, method="daily_basic total_mv x 10000"),
            "share_count": _valuation_metric(1_274_349_692, "shares", MARKET_EVIDENCE_ID, method="daily_basic total_share x 10000"),
            "net_cash_or_net_debt": _valuation_metric(bridge["net_debt_proxy"], "CNY_net_debt_proxy", Q1_EVIDENCE_ID, method=bridge["calculation_method"]),
            "enterprise_value": _valuation_metric(enterprise_value, "CNY", MARKET_EVIDENCE_ID, method="market_cap + reviewed_Q1_net_debt_bridge"),
            "pe_ttm": _valuation_metric(194.2045, "multiple", MARKET_EVIDENCE_ID),
            "forward_pe": _valuation_metric(forward_pe, "multiple", MARKET_EVIDENCE_ID, method="current_price / reviewed model EPS"),
            "pb": _valuation_metric(27.0715, "multiple", MARKET_EVIDENCE_ID),
            "ps": _valuation_metric(14.8507, "multiple_TTM", MARKET_EVIDENCE_ID),
            "ev_ebitda": _valuation_metric(None, "multiple", None, missing_reason="METHOD_NOT_ELIGIBLE_WITHOUT_REVIEWED_EBITDA"),
        },
        "peer_valuation_context": {
            "status": "reviewed_low_confidence",
            "rows": peer_rows,
            "peer_set_quality": "low",
            "peer_median_pe_ttm": 310.1249,
            "limitations": ["Only two product-exposure peers; business mixes and disclosure quality differ."],
        },
        "valuation_methods": [
            {
                "method_id": "relative_pe",
                "method_type": "relative",
                "status": "ready",
                "supported_output": {
                    "metric": "cross_multiple_relative_context",
                    "subject": {"pe_ttm": 194.2045, "pb": 27.0715, "ps_ttm": 14.8507},
                    "peer_median": {"pe_ttm": 310.1249, "pb": 12.33865, "ps_ttm": 11.32265},
                    "label": "mixed_multiple_signal_not_assessable",
                },
                "source_ids_or_missing_reason": [MARKET_EVIDENCE_ID, *PEER_INPUT_IDS],
                "confidence": "low",
            },
            {
                "method_id": "dcf",
                "method_type": "forecast_dependent",
                "status": "skipped",
                "supported_output": None,
                "forecast_assumption_ids": [row["assumption_id"] for row in forecast_records],
                "forecast_metric_ids": [],
                "source_ids_or_missing_reason": "METHOD_EXCLUDED_UNREVIEWED_FCFF_AND_DISCOUNT_INPUTS",
            },
            {
                "method_id": "sotp",
                "method_type": "segment_dependent",
                "status": "skipped",
                "supported_output": None,
                "source_ids_or_missing_reason": "METHOD_EXCLUDED_UNDISCLOSED_LIQUID_COOLING_SPLIT",
            },
        ],
        "valuation_scenarios": [
            {"scenario_id": "bear", "status": "research_estimate", "method_id": "relative_pe", "output_metric": "reference_pe_multiple", "output_value": 234.3524, "unit": "multiple", "source_ids_or_missing_reason": MARKET_EVIDENCE_ID},
            {"scenario_id": "base", "status": "research_estimate", "method_id": "relative_pe", "output_metric": "reference_pe_multiple", "output_value": 310.1249, "unit": "multiple", "source_ids_or_missing_reason": MARKET_EVIDENCE_ID},
            {"scenario_id": "bull", "status": "research_estimate", "method_id": "relative_pe", "output_metric": "reference_pe_multiple", "output_value": 385.8974, "unit": "multiple", "source_ids_or_missing_reason": MARKET_EVIDENCE_ID},
        ],
        "valuation_sensitivity": {
            "status": "reviewed_estimate",
            "rows": [
                {"period": year, "model_eps": values["eps"][year], "current_price": 73.54, "forward_pe": forward_pe[year], "unit": "multiple", "assumption_id": f"r5_b5_forecast_eps_base", "evidence_id": MARKET_EVIDENCE_ID}
                for year in ("2026E", "2027E", "2028E")
            ],
            "interpretation_boundary": "Sensitivity holds the dated market price constant and varies only the reviewed model EPS path.",
        },
        "limitations": [
            "Relative PE is low confidence because only two exposure-grounded peers are available.",
            "PE is below the peer median while PB and PS TTM are above their peer medians; no single valuation label is supportable.",
            "No intrinsic or segment-sum method is active.",
            "Scenario multiples are research context, not price outputs.",
        ],
        "missing_items": [
            {"item": "ev_ebitda", "reason": "METHOD_NOT_ELIGIBLE_WITHOUT_REVIEWED_EBITDA"},
            {"item": "dcf", "reason": "METHOD_EXCLUDED_UNREVIEWED_FCFF_AND_DISCOUNT_INPUTS"},
            {"item": "sotp", "reason": "METHOD_EXCLUDED_UNDISCLOSED_LIQUID_COOLING_SPLIT"},
        ],
        "source_gap_register": [
            {"gap_id": "R5_B5_DCF_METHOD_GAP", "token": "UNREVIEWED_FCFF_INPUTS"},
            {"gap_id": "R5_B5_SOTP_METHOD_GAP", "token": "UNDISCLOSED_SEGMENT_SPLIT"},
        ],
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def write_readout(path: Path, reviewed_at: str, values: dict[str, dict[str, float]]) -> None:
    text = f"""# R5 Bundle 5.4 — Forecast and Valuation Input Readout

status: accepted_reviewed_input_research_draft

## result

- workflow_id: `{WORKFLOW_ID}`
- stock_code: `{STOCK_CODE}`
- reviewer: `codex`
- reviewed_at: `{reviewed_at}`
- accepted_forecast_assumptions: `5`
- accepted_valuation_inputs: `1`
- forecast_periods: `2026E, 2027E, 2028E`
- canonical_registry_changed: `false`
- sample_quality_report_allowed: `false`
- p2_allowed: `false`

## base_case_estimates

| metric | 2026E | 2027E | 2028E | type |
|---|---:|---:|---:|---|
| revenue growth | {values['revenue_growth']['2026E']:.4f}% | {values['revenue_growth']['2027E']:.2f}% | {values['revenue_growth']['2028E']:.2f}% | estimate |
| gross margin | {values['gross_margin']['2026E']:.4f}% | {values['gross_margin']['2027E']:.2f}% | {values['gross_margin']['2028E']:.2f}% | estimate |
| attributable profit | {values['net_profit']['2026E']:.2f} | {values['net_profit']['2027E']:.2f} | {values['net_profit']['2028E']:.2f} | estimate, CNY |
| EPS | {values['eps']['2026E']:.6f} | {values['eps']['2027E']:.6f} | {values['eps']['2028E']:.6f} | estimate, CNY/share |

The 2026 path is a mechanical Q1 carry-forward and prior-year seasonality calculation. The 2027-2028 path is an explicit model assumption with visible sensitivity ranges. None of these values is a reported fact, management guidance or consensus.

## method_eligibility

- `relative_pe`: eligible only as low-confidence context; two same-date exposure-grounded peers are available.
- `dcf`: excluded because FCFF, tax, capex, working-capital, discount-rate and terminal inputs are not sufficiently reviewed.
- `sotp`: excluded because liquid-cooling-specific revenue and profit splits are not separately disclosed.
- The valuation candidate contains relative-multiple context and forward-PE sensitivity only; it contains no price output.

## net_debt_bridge

- Q1 cash: `917,139,183.43 CNY`.
- Gross debt and lease-related components: `1,615,274,513.10 CNY`.
- Derived net-debt proxy: `698,135,329.67 CNY`, low confidence because restricted cash and trading financial assets were not reclassified.
- Source: `{Q1_EVIDENCE_ID}`, consolidated balance sheet.

## next_card

Cards 5.2-5.4 now have accepted reviewed inputs. Proceed to Card 5.5 only after full dropzone validation, pre-hash inventory, backups, dry-run and hard-boundary fixes pass.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_outputs(repo_root: Path, reviewed_at: str) -> dict[str, Any]:
    datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
    forecast_records = build_forecast_records(reviewed_at)
    valuation_record = build_valuation_record(reviewed_at, forecast_records)
    dropzone = repo_root / "data/reviewed_inputs" / WORKFLOW_ID
    _write_yaml(dropzone / "forecast_assumptions/reviewed_model_assumptions.yaml", {"records": forecast_records})
    _write_yaml(dropzone / "valuation_inputs/reviewed_valuation_context.yaml", {"records": [valuation_record]})
    run_dir = repo_root / "reports/workflow_runs" / WORKFLOW_ID
    _write_yaml(run_dir / "R5_bundle5_forecast_model_candidate.yaml", build_forecast_pack(forecast_records))
    _write_yaml(run_dir / "R5_bundle5_valuation_pack_candidate.yaml", build_valuation_pack(forecast_records))
    write_readout(repo_root / "reports/p1_6/R5_BUNDLE_5_4_FORECAST_VALUATION_INPUT_READOUT.md", reviewed_at, model_values())
    return {"forecast_records": len(forecast_records), "valuation_records": 1}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build R5 Bundle 5.4 forecast and valuation onboarding outputs.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--reviewed-at", required=True)
    args = parser.parse_args(argv)
    result = build_outputs(args.repo_root.resolve(), args.reviewed_at)
    print(
        "r5_bundle5_card_5_4 status=accepted "
        f"forecast={result['forecast_records']} valuation={result['valuation_records']} "
        "promotion_allowed=false sample_quality=false p2=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
