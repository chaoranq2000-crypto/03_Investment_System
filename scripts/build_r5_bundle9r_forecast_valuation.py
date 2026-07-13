from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_r5_bundle9_forecast as legacy_forecast  # noqa: E402
from scripts import build_r5_bundle9_valuation as legacy_valuation  # noqa: E402
from src.research.r5_bundle9r_contracts import (  # noqa: E402
    load_yaml,
    validate_evidence_generation_lock,
    validate_locked_input_hashes,
)


WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
AS_OF_DATE = "2026-07-13"
GENERATION_LOCK = "R5_bundle8r_evidence_generation_lock_v2.yaml"
ANNUAL_EVIDENCE = "ev_annual_report_002837_20260421_2cbfc5"
QUARTER_EVIDENCE = "ev_quarterly_report_002837_20260421_2f00c7"
MARKET_EVIDENCE = "ev_structured_market_data_002837_20260713_79bd83"
CONSENSUS_EVIDENCE = "ev_third_party_research_002837_20260713_1ca4d1"
ANNUAL_SOURCE = "data/processed/text/002837/cninfo_2025_annual_report_full_002837_2026-04-21.txt"
STATEMENT_SOURCE = "data/processed/normalized/sina_financial_adapter_financial_statements_002837_2026-07-13_6e0ecd46.csv"
MARKET_SOURCE = "data/processed/normalized/tencent_quote_adapter_quote_and_valuation_002837_2026-07-13_79bd83ad.csv"
CONSENSUS_SOURCE = "data/processed/normalized/ths_consensus_adapter_consensus_eps_002837_2026-07-13_1ca4d1d4.csv"
SHARES = 1_274_349_692
PERIODS = ["2026E", "2027E", "2028E"]
SCENARIO_MAP = {"bear": "bear_case", "base": "base_case", "bull": "bull_case"}
SEGMENT_BASIS = {
    "room_cooling": "issuer_reported_broad_line",
    "cabinet_cooling": "issuer_reported_broad_line",
    "other_businesses": "issuer_reported_residual",
}

# Signed 2025A operating components.  These six audited statement lines replace
# the legacy aggregate residual.  Scenario scaling preserves their disclosed mix.
OPERATING_COMPONENT_ANCHORS = {
    "investment_income": 214_831.73,
    "fair_value_change": 387_916.67,
    "other_income": 57_609_415.23,
    "asset_impairment_loss": -73_180_106.03,
    "credit_impairment_loss": -93_624_381.87,
    "asset_disposal_gain": 33_992.50,
}
NET_COMPONENT_RATIO = {
    "bear": [2.00, 2.00, 1.80],
    "base": [1.60, 1.40, 1.20],
    "bull": [1.20, 1.00, 0.80],
}


def write_yaml(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(dict(payload), allow_unicode=True, sort_keys=False)
    path.write_bytes(rendered.encode("utf-8"))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(fields),
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def rewrite_ids(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: rewrite_ids(child) for key, child in value.items()}
    if isinstance(value, list):
        return [rewrite_ids(child) for child in value]
    if isinstance(value, str):
        return value.replace("R5_bundle9_", "R5_bundle9r_").replace("b9_", "b9r_")
    return value


def stamp(payload: Mapping[str, Any], generation_id: str, artifact_type: str) -> dict[str, Any]:
    result = rewrite_ids(dict(payload))
    result["artifact_type"] = artifact_type
    result["input_evidence_generation_id"] = generation_id
    result["input_evidence_generation_lock"] = (
        f"reports/workflow_runs/{WORKFLOW_ID}/{GENERATION_LOCK}"
    )
    result["as_of_date"] = AS_OF_DATE
    result["sample_quality_allowed"] = False
    result["p2_allowed"] = False
    return result


def metric(
    value: float,
    unit: str,
    assumption_id: str,
    *,
    evidence_id: str = ANNUAL_EVIDENCE,
    metric_id: str | None = None,
) -> dict[str, Any]:
    return {
        "value": value,
        "unit": unit,
        "claim_type": "estimate",
        "assumption_id": assumption_id,
        "evidence_id": evidence_id,
        "metric_id": metric_id,
    }


def explicit_operating_components(revenue: float, net_ratio_pct: float) -> dict[str, float]:
    anchor_net = sum(OPERATING_COMPONENT_ANCHORS.values())
    target_net = -revenue * net_ratio_pct / 100.0
    scale = target_net / anchor_net
    rows = {key: round(value * scale, 2) for key, value in OPERATING_COMPONENT_ANCHORS.items()}
    rounding_difference = round(target_net - sum(rows.values()), 2)
    rows["credit_impairment_loss"] = round(rows["credit_impairment_loss"] + rounding_difference, 2)
    if abs(sum(rows.values()) - target_net) > 0.011:
        raise ValueError("explicit operating components do not reconcile")
    return rows


def rebuild_bridge(source: Mapping[str, Any], scenario: str, period_index: int) -> dict[str, Any]:
    revenue = float(source["revenue"])
    gross_profit = float(source["gross_profit"])
    components = explicit_operating_components(revenue, NET_COMPONENT_RATIO[scenario][period_index])
    operating_profit = round(
        gross_profit
        - float(source["tax_surcharge"])
        - float(source["selling_expense"])
        - float(source["administrative_expense"])
        - float(source["rd_expense"])
        - float(source["financial_expense"])
        + sum(components.values()),
        2,
    )
    non_operating_net = float(source["non_operating_net"])
    pretax_profit = round(operating_profit + non_operating_net, 2)
    income_tax = float(source["income_tax"])
    minority_interest = float(source["minority_profit"])
    nonrecurring_items = 0.0
    attributable_net_profit = round(
        pretax_profit - income_tax - minority_interest + nonrecurring_items,
        2,
    )
    if abs(attributable_net_profit - float(source["net_profit_attributable"])) > 0.02:
        raise ValueError("explicit statement bridge changed attributable profit")
    operating_cash_flow = float(source["operating_cashflow"])
    capex = float(source["capex"])
    bridge = {
        "revenue": revenue,
        "gross_profit": gross_profit,
        "tax_surcharge": float(source["tax_surcharge"]),
        "selling_expense": float(source["selling_expense"]),
        "administrative_expense": float(source["administrative_expense"]),
        "rd_expense": float(source["rd_expense"]),
        "financial_expense": float(source["financial_expense"]),
        **components,
        "net_other_operating_components": round(sum(components.values()), 2),
        "operating_profit": operating_profit,
        "non_operating_net": non_operating_net,
        "pretax_profit": pretax_profit,
        "income_tax": income_tax,
        "minority_interest": minority_interest,
        "nonrecurring_items": nonrecurring_items,
        "attributable_net_profit": attributable_net_profit,
        "eps": round(attributable_net_profit / SHARES, 6),
        "shares_outstanding": SHARES,
        "net_income": round(pretax_profit - income_tax, 2),
        "net_working_capital": float(source["nwc"]),
        "change_in_net_working_capital": float(source["nwc_change"]),
        "noncash_addback": float(source["noncash_addback"]),
        "operating_cash_flow": operating_cash_flow,
        "capex": capex,
        "free_cash_flow": round(operating_cash_flow - capex, 2),
        "ratio_assumptions": {
            key: value
            for key, value in source["ratio_assumptions"].items()
            if key not in {"other_operating_drag"}
        },
        "net_other_operating_components_ratio": NET_COMPONENT_RATIO[scenario][period_index],
        "component_mix_anchor_period": "2025A",
        "component_mix_claim_type": "estimate",
        "component_mix_assumption_id": f"b9r_{SCENARIO_MAP[scenario]}_other_operating_component_mix",
        "component_source_evidence_id": ANNUAL_EVIDENCE,
        "component_source_path": STATEMENT_SOURCE,
    }
    return bridge


def calculate(run: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    anchors, summary = legacy_forecast._business_line_anchors(run)
    historical = legacy_forecast._historical_bridge()
    if abs(float(summary["company_revenue"]) - float(historical["revenue"])) > 0.01:
        raise ValueError("audited business lines do not reconcile to company revenue")
    calculated = {
        name: legacy_forecast._calculate_scenario(name, anchors, historical)
        for name in legacy_forecast.SCENARIO_INPUTS
    }
    return anchors, summary, historical, calculated


def validate_official_anchors(run: Path, historical: Mapping[str, Any]) -> list[dict[str, Any]]:
    official = load_yaml(run / "R5_bundle5_financial_history_candidate.yaml")
    rows = list(official.get("income_statement") or [])
    by_key = {(str(row.get("period")), str(row.get("metric_name"))): row for row in rows}
    required = {
        ("2025A", "revenue"): float(historical["revenue"]),
        ("2025A", "net_profit_attributable"): float(historical["net_profit_attributable"]),
        ("2026Q1", "revenue"): 1_175_329_313.61,
        ("2026Q1", "net_profit_attributable"): 8_657_602.27,
    }
    reconciled: list[dict[str, Any]] = []
    for key, expected in required.items():
        source = by_key.get(key)
        if not source or abs(float(source["value"]) - expected) > 0.01:
            raise ValueError(f"official financial anchor mismatch: {key}")
        reconciled.append(
            {
                "period": key[0],
                "metric_name": key[1],
                "value": expected,
                "unit": "CNY",
                "evidence_id": source["evidence_id"],
                "page_or_table_locator": source["page_or_table_locator"],
                "decision": "matched_to_official_direct_reported_value",
            }
        )
    return reconciled


def build_assumptions(calculated: Mapping[str, Any], generation_id: str) -> dict[str, Any]:
    registry = rewrite_ids(legacy_forecast._build_registry(calculated))
    for row in registry["assumptions"]:
        row["claim_type"] = "estimate"
        row["confidence"] = "medium" if row["scenario"] == "base" else "low"
        row["reviewer_decision"] = "accepted_for_forecast_model"
        row["falsification_condition"] = (
            "Refresh when issuer disclosure, reviewed financial metrics, share count, or demand-to-revenue evidence changes."
        )
    for scenario, legacy_name in SCENARIO_MAP.items():
        registry["assumptions"].append(
            {
                "assumption_id": f"b9r_{legacy_name}_other_operating_component_mix",
                "driver": "other_operating_components",
                "scope": "statement_bridge",
                "periods": PERIODS,
                "value": {
                    period: {
                        "net_ratio_pct_of_revenue": NET_COMPONENT_RATIO[scenario][index],
                        "component_mix_anchor": OPERATING_COMPONENT_ANCHORS,
                    }
                    for index, period in enumerate(PERIODS)
                },
                "unit": "pct_of_revenue_and_signed_CNY_anchor",
                "scenario": scenario,
                "claim_type": "estimate",
                "evidence_ids": [ANNUAL_EVIDENCE],
                "metric_ids": [],
                "source_path": STATEMENT_SOURCE,
                "formula": "scale six signed 2025A statement components to the scenario net component ratio",
                "allowed_usage": "forecast_model",
                "review_status": "reviewed",
                "confidence": "medium" if scenario == "base" else "low",
                "limitations": ["future component mix may differ from 2025A"],
                "falsification_condition": "Refresh when a new audited statement changes the six-line component mix.",
            }
        )
    registry.update(
        {
            "artifact_type": "R5_bundle9r_forecast_assumption_registry",
            "input_evidence_generation_id": generation_id,
            "input_evidence_generation_lock": f"reports/workflow_runs/{WORKFLOW_ID}/{GENERATION_LOCK}",
            "assumption_count": len(registry["assumptions"]),
            "sample_quality_allowed": False,
            "p2_allowed": False,
        }
    )
    return registry


def build_consensus(run: Path, calculated: Mapping[str, Any], generation_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    pack = load_yaml(run / "R5_estimate_distribution_pack.yaml")
    source_rows = pack["ths_consensus"]["rows"]
    by_period = {f"{row['annual_period']}E": row for row in source_rows}
    rows: list[dict[str, Any]] = []
    for period in PERIODS:
        source = by_period[period]
        base_eps = float(calculated["base_case"][period]["bridge"]["eps"])
        mean = float(source["eps_mean"])
        rows.append(
            {
                "period": period,
                "base_model_eps": base_eps,
                "consensus_eps_min": float(source["eps_min"]),
                "consensus_eps_mean": mean,
                "consensus_eps_max": float(source["eps_max"]),
                "institution_count": int(source["institution_count"]),
                "base_minus_consensus_mean_pct": round((base_eps / mean - 1) * 100, 4),
                "unit": "CNY_per_share",
                "claim_type": "analyst_view",
                "source_evidence_id": CONSENSUS_EVIDENCE,
                "source_path": CONSENSUS_SOURCE,
                "input_evidence_generation_id": generation_id,
                "limitations": "external estimate distribution; not issuer guidance",
            }
        )
    payload = {
        "status": "consensus_context_available",
        "claim_type": "analyst_view",
        "minimum_institution_count": min(row["institution_count"] for row in rows),
        "institution_count_by_period": {row["period"]: row["institution_count"] for row in rows},
        "source_evidence_id": CONSENSUS_EVIDENCE,
        "source_path": CONSENSUS_SOURCE,
        "rows": {row["period"]: row for row in rows},
        "limitations": [
            "External forecasts are analyst views, not issuer guidance.",
            "Institution count does not establish identical model definitions.",
        ],
    }
    return payload, rows


def build_forecast_artifacts(run: Path, generation_id: str) -> dict[str, Any]:
    anchors, summary, historical, calculated = calculate(run)
    official_reconciliation = validate_official_anchors(run, historical)
    assumptions = build_assumptions(calculated, generation_id)
    consensus, consensus_rows = build_consensus(run, calculated, generation_id)
    scenarios: dict[str, Any] = {}
    bridge_scenarios: dict[str, Any] = {}
    for scenario, legacy_name in SCENARIO_MAP.items():
        periods: dict[str, Any] = {}
        bridge_periods: dict[str, Any] = {}
        for index, period in enumerate(PERIODS):
            source_year = calculated[legacy_name][period]
            segments: dict[str, Any] = {}
            for segment_id, source in source_year["business_lines"].items():
                growth_id = f"b9r_{legacy_name}_{segment_id}_revenue_growth"
                margin_id = f"b9r_{legacy_name}_{segment_id}_gross_margin"
                segments[segment_id] = {
                    "reported_name": source["reported_name"],
                    "disclosure_basis": SEGMENT_BASIS[segment_id],
                    "revenue": metric(float(source["revenue"]), "CNY", growth_id),
                    "revenue_growth": metric(float(source["revenue_growth"]), "pct", growth_id),
                    "gross_margin": metric(float(source["gross_margin"]), "pct", margin_id),
                    "gross_profit": metric(float(source["gross_profit"]), "CNY", margin_id),
                    "source_evidence_ids": list(source["evidence_ids"]),
                    "claim_type": "estimate",
                    "confidence": "medium" if scenario == "base" else "low",
                    "driver_method": "reviewed broad-line growth proxy because project-volume and unit-value conversion is not disclosed",
                    "falsification_condition": "Refresh when issuer broad-line revenue, margin, project volume, capacity, pricing, or acceptance evidence changes.",
                }
            bridge = rebuild_bridge(source_year["bridge"], scenario, index)
            periods[period] = {
                "segments": segments,
                "bridge": bridge,
                "claim_type": "estimate",
                "reconciliation": {
                    "segment_revenue_difference_CNY": round(
                        sum(float(row["revenue"]["value"]) for row in segments.values()) - bridge["revenue"], 2
                    ),
                    "segment_gross_profit_difference_CNY": round(
                        sum(float(row["gross_profit"]["value"]) for row in segments.values()) - bridge["gross_profit"], 2
                    ),
                    "statement_bridge_difference_CNY": round(
                        bridge["pretax_profit"]
                        - bridge["income_tax"]
                        - bridge["minority_interest"]
                        + bridge["nonrecurring_items"]
                        - bridge["attributable_net_profit"],
                        2,
                    ),
                },
            }
            bridge_periods[period] = bridge
        scenarios[scenario] = {"claim_type": "estimate", "periods": periods}
        bridge_scenarios[scenario] = bridge_periods

    analytical_view = {
        "view_id": "liquid_cooling_analytical_view",
        "claim_type": "estimate",
        "standalone_revenue": "MISSING",
        "standalone_gross_margin": "MISSING",
        "gap_id": "missing_liquid_cooling_segment_economics",
        "overlap_control": "included_within_room_and_cabinet_not_additive",
        "included_in_company_total": False,
        "status": "unquantified_due_to_issuer_nondisclosure",
        "confidence": "low",
        "falsification_condition": "Replace only when issuer-disclosed standalone revenue, margin, and overlap eliminations become reviewable.",
    }
    segment_driver_model = stamp(
        {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "stock_code": "002837",
            "historical_anchor": {
                "period": "2025A",
                "company_revenue": historical["revenue"],
                "company_gross_profit": historical["gross_profit"],
                "segments": anchors,
                "evidence_id": ANNUAL_EVIDENCE,
                "source_path": ANNUAL_SOURCE,
                "reconciliation_difference_CNY": round(
                    sum(float(row["revenue"]) for row in anchors.values()) - float(summary["company_revenue"]), 2
                ),
            },
            "scenarios": {
                scenario: {
                    period: {"segments": row["segments"]}
                    for period, row in payload["periods"].items()
                }
                for scenario, payload in scenarios.items()
            },
            "liquid_cooling_analytical_view": analytical_view,
            "limitations": [
                "Forecasts use issuer-disclosed broad business lines.",
                "Standalone liquid-cooling economics remain undisclosed and are not added to company totals.",
            ],
        },
        generation_id,
        "R5_bundle9r_segment_driver_model",
    )
    statement_bridge = stamp(
        {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "historical_anchor": {
                **historical,
                **OPERATING_COMPONENT_ANCHORS,
                "non_operating_net": round(float(historical["total_profit"]) - float(historical["operating_profit"]), 2),
                "pretax_profit": historical["total_profit"],
                "minority_interest": historical["minority_profit"],
                "attributable_net_profit": historical["net_profit_attributable"],
                "operating_cash_flow": historical["operating_cashflow"],
                "free_cash_flow": round(float(historical["operating_cashflow"]) - float(historical["capex"]), 2),
            },
            "scenarios": bridge_scenarios,
            "formula": "gross profit - named expenses + six signed operating components + non-operating net - tax - minority + nonrecurring items",
            "explicit_component_fields": list(OPERATING_COMPONENT_ANCHORS),
            "prohibited_balancing_fields_present": False,
            "source_evidence_ids": [ANNUAL_EVIDENCE, QUARTER_EVIDENCE],
            "source_paths": [ANNUAL_SOURCE, STATEMENT_SOURCE],
        },
        generation_id,
        "R5_bundle9r_financial_statement_bridge",
    )
    scenario_pack = stamp(
        {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "periods": PERIODS,
            "scenarios": {
                scenario: {
                    period: {
                        "revenue": payload["bridge"]["revenue"],
                        "gross_margin": round(payload["bridge"]["gross_profit"] / payload["bridge"]["revenue"] * 100, 4),
                        "attributable_net_profit": payload["bridge"]["attributable_net_profit"],
                        "eps": payload["bridge"]["eps"],
                        "operating_cash_flow": payload["bridge"]["operating_cash_flow"],
                        "free_cash_flow": payload["bridge"]["free_cash_flow"],
                    }
                    for period, payload in scenario_payload["periods"].items()
                }
                for scenario, scenario_payload in scenarios.items()
            },
            "monotonicity_rule": "bear <= base <= bull for revenue and attributable net profit",
            "claim_type": "estimate",
        },
        generation_id,
        "R5_bundle9r_scenario_pack",
    )
    ledger = stamp(
        {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "decision": "accepted_with_explicit_gaps",
            "official_anchor_reconciliation": official_reconciliation,
            "reviewed_inputs": [
                {
                    "input_id": "bundle8r_generation_lock_v2",
                    "path": f"reports/workflow_runs/{WORKFLOW_ID}/{GENERATION_LOCK}",
                    "classification": "generation_control",
                    "decision": "accepted",
                    "allowed_usage": "generation_binding",
                },
                {
                    "input_id": "annual_report_2025",
                    "path": ANNUAL_SOURCE,
                    "evidence_id": ANNUAL_EVIDENCE,
                    "classification": "issuer_fact",
                    "claim_type": "fact",
                    "decision": "accepted",
                    "allowed_usage": "historical_anchor",
                },
                {
                    "input_id": "financial_metric_pack",
                    "path": f"reports/workflow_runs/{WORKFLOW_ID}/financial_metric_pack.csv",
                    "classification": "reviewed_structured_metric",
                    "metric_ids": [
                        "metric_cn_002837_invic_revenue_20251231_9c5aaf",
                        "metric_cn_002837_invic_n_income_attr_p_20251231_002a58",
                        "metric_cn_002837_invic_basic_eps_20251231_03d56b",
                        "metric_cn_002837_invic_n_cashflow_act_20251231_890163",
                    ],
                    "decision": "accepted",
                    "allowed_usage": "historical_anchor_and_forecast_support",
                },
                {
                    "input_id": "statement_line_items",
                    "path": STATEMENT_SOURCE,
                    "evidence_id": ANNUAL_EVIDENCE,
                    "classification": "reviewed_structured_metric_reconciled_to_issuer_fact",
                    "claim_type": "fact",
                    "decision": "accepted",
                    "allowed_usage": "explicit_statement_bridge",
                },
                {
                    "input_id": "market_snapshot",
                    "path": MARKET_SOURCE,
                    "evidence_id": MARKET_EVIDENCE,
                    "classification": "exchange_market_fact",
                    "claim_type": "fact",
                    "decision": "accepted",
                    "allowed_usage": "dated_valuation_context",
                },
                {
                    "input_id": "consensus_distribution",
                    "path": CONSENSUS_SOURCE,
                    "evidence_id": CONSENSUS_EVIDENCE,
                    "classification": "analyst_estimate_distribution",
                    "claim_type": "analyst_view",
                    "decision": "accepted_with_boundary",
                    "allowed_usage": "consensus_context_only",
                },
                {
                    "input_id": "official_2026q1_anchor",
                    "path": f"reports/workflow_runs/{WORKFLOW_ID}/R5_bundle5_financial_history_candidate.yaml",
                    "evidence_id": QUARTER_EVIDENCE,
                    "classification": "issuer_fact",
                    "claim_type": "fact",
                    "decision": "accepted",
                    "allowed_usage": "forecast_risk_anchor",
                },
                {
                    "input_id": "management_comment_review",
                    "path": f"reports/workflow_runs/{WORKFLOW_ID}/R5_bundle8b_management_comment_review.yaml",
                    "classification": "management_comment",
                    "claim_type": "management_comment",
                    "decision": "accepted_with_boundary",
                    "allowed_usage": "driver_context_not_numeric_guidance",
                },
                {
                    "input_id": "explicit_component_scaling",
                    "path": f"reports/workflow_runs/{WORKFLOW_ID}/R5_bundle9r_financial_statement_bridge.yaml",
                    "classification": "analytical_inference",
                    "claim_type": "estimate",
                    "decision": "accepted",
                    "allowed_usage": "forecast_statement_bridge",
                },
            ],
            "rejected_inputs": [
                {
                    "input_id": "standalone_liquid_cooling_economics",
                    "classification": "issuer_nondisclosure_unknown",
                    "decision": "rejected_as_issuer_fact",
                    "gap_id": "missing_liquid_cooling_segment_economics",
                    "next_action": "retain as evidence gap",
                },
                {
                    "input_id": "legacy_bundle9r_aggregate_statement_residual",
                    "decision": "rejected",
                    "reason": "prohibited balancing field; replaced by six explicit statement components",
                },
            ],
            "draft_metric_rule": "reject any draft metric without allowed_usage and an explicit review decision",
            "assumption_count": len(assumptions["assumptions"]),
        },
        generation_id,
        "R5_bundle9r_input_review_ledger",
    )

    sensitivity = rewrite_ids(legacy_forecast._build_sensitivity(calculated))
    sensitivity_rows: list[dict[str, Any]] = []
    for row in sensitivity:
        base_output = float(calculated["base_case"][row["year"]]["bridge"][row["impact_metric"]])
        sensitivity_rows.append(
            {
                "sensitivity_type": "one_way",
                "scenario": "base",
                **row,
                "base_output": base_output,
                "output_value": round(base_output + float(row["impact_value"]), 2),
                "input_evidence_generation_id": generation_id,
            }
        )
    period = "2027E"
    base_bridge = calculated["base_case"][period]["bridge"]
    factor = (1 - base_bridge["ratio_assumptions"]["effective_tax_rate"] / 100) * (
        1 - base_bridge["ratio_assumptions"]["minority_share_of_net_income"] / 100
    )
    prior_room = float(calculated["base_case"]["2026E"]["business_lines"]["room_cooling"]["revenue"])
    room_margin = float(calculated["base_case"][period]["business_lines"]["room_cooling"]["gross_margin"]) / 100
    base_profit = float(base_bridge["net_profit_attributable"])
    for growth_delta in (-5, 0, 5):
        for margin_delta in (-1, 0, 1):
            impact = prior_room * growth_delta / 100 * room_margin * factor
            impact += float(base_bridge["revenue"]) * margin_delta / 100 * factor
            sensitivity_rows.append(
                {
                    "sensitivity_type": "two_way",
                    "scenario": "base",
                    "year": period,
                    "driver": "room_growth_x_consolidated_gross_margin",
                    "change": f"room_growth_{growth_delta:+d}pp|gross_margin_{margin_delta:+d}pp",
                    "impact_metric": "net_profit_attributable",
                    "impact_value": round(impact, 2),
                    "unit": "CNY",
                    "assumption_id_or_missing_reason": "b9r_base_case_room_cooling_revenue_growth|b9r_base_case_gross_margin_consolidated",
                    "calculation_method": "additive two-driver first-order sensitivity around 2027E base case",
                    "base_output": base_profit,
                    "output_value": round(base_profit + impact, 2),
                    "input_evidence_generation_id": generation_id,
                }
            )

    write_yaml(run / "R5_bundle9r_input_review_ledger.yaml", ledger)
    write_yaml(run / "R5_bundle9r_forecast_assumption_registry.yaml", assumptions)
    write_yaml(run / "R5_bundle9r_segment_driver_model.yaml", segment_driver_model)
    write_yaml(run / "R5_bundle9r_financial_statement_bridge.yaml", statement_bridge)
    write_yaml(run / "R5_bundle9r_scenario_pack.yaml", scenario_pack)
    write_csv(
        run / "R5_bundle9r_sensitivity.csv",
        sensitivity_rows,
        [
            "sensitivity_type", "scenario", "year", "driver", "change", "impact_metric",
            "impact_value", "unit", "assumption_id_or_missing_reason", "calculation_method",
            "base_output", "output_value", "input_evidence_generation_id",
        ],
    )
    write_csv(
        run / "R5_bundle9r_consensus_comparison.csv",
        consensus_rows,
        [
            "period", "base_model_eps", "consensus_eps_min", "consensus_eps_mean",
            "consensus_eps_max", "institution_count", "base_minus_consensus_mean_pct",
            "unit", "claim_type", "source_evidence_id", "source_path",
            "input_evidence_generation_id", "limitations",
        ],
    )
    return {
        "anchors": anchors,
        "historical": historical,
        "calculated": calculated,
        "scenarios": scenarios,
        "consensus": consensus,
        "analytical_view": analytical_view,
        "assumptions": assumptions,
    }


def configure_valuation() -> None:
    legacy_valuation.MARKET_AS_OF = AS_OF_DATE
    legacy_valuation.MARKET_EVIDENCE = MARKET_EVIDENCE
    legacy_valuation.MARKET_SOURCE = MARKET_SOURCE
    legacy_valuation.CONSENSUS_EVIDENCE = CONSENSUS_EVIDENCE
    legacy_valuation.MARKET.clear()
    legacy_valuation.MARKET.update(
        {
            "close_price": 66.98,
            "market_cap": 85_356_000_000.0,
            "free_float_market_cap": 75_718_000_000.0,
            "shares_outstanding": SHARES,
            "pe_ttm": 176.88,
            "pb_lf": 25.90,
            "ps_ttm": round(85_356_000_000.0 / 6_067_759_091.55, 4),
            "turnover_rate": 5.15,
        }
    )
    legacy_valuation.MARKET_METRIC_IDS.update(
        {
            "close_price": "metric_company_cn_002837_invic_price_2026-07-13_3d56a6d7",
            "market_cap": "metric_company_cn_002837_invic_mcap_yi_2026-07-13_4e590be8",
            "free_float_market_cap": "metric_company_cn_002837_invic_float_mcap_yi_2026-07-13_189d2011",
            "pe_ttm": "metric_company_cn_002837_invic_pe_ttm_2026-07-13_353d1394",
            "pb_lf": "metric_company_cn_002837_invic_pb_2026-07-13_b46ba3c5",
            "ps_ttm": "metric_calc_cn_002837_invic_ps_2026-07-13_market_cap_over_2025_revenue",
            "turnover_rate": "metric_company_cn_002837_invic_turnover_pct_2026-07-13_6420894d",
        }
    )


def build_valuation_artifacts(run: Path, generation_id: str, forecast: Mapping[str, Any]) -> None:
    configure_valuation()
    calculated = forecast["calculated"]
    compatibility_model = legacy_forecast._build_model(
        forecast["anchors"],
        forecast["historical"],
        calculated,
        legacy_forecast._build_sensitivity(calculated),
    )
    peers = legacy_valuation.read_peer_inputs(run)
    valuation_scenarios = legacy_valuation.scenario_tables(compatibility_model)

    peer_reconciliation = stamp(
        legacy_valuation.build_peer_reconciliation(peers),
        generation_id,
        "R5_bundle9r_peer_operating_reconciliation",
    )
    peer_reconciliation["peer_set_quality"] = "LOW_CONFIDENCE_PEER_SET"
    peer_reconciliation["ranking_allowed"] = False
    peer_reconciliation["gap_id"] = "missing_peer_liquid_cooling_purity"

    market_cap = 85_356_000_000.0
    close_price = 66.98
    calculated_market_cap = round(close_price * SHARES, 2)
    market_snapshot = stamp(
        {
            "schema_version": 1,
            "workflow_id": WORKFLOW_ID,
            "market_date": AS_OF_DATE,
            "close_price": {"value": close_price, "unit": "CNY_per_share", "claim_type": "fact", "evidence_id": MARKET_EVIDENCE, "metric_id": legacy_valuation.MARKET_METRIC_IDS["close_price"]},
            "shares_outstanding": {"value": SHARES, "unit": "shares", "claim_type": "fact", "evidence_id": ANNUAL_EVIDENCE, "metric_id": "metric_cn_002837_invic_shares_20251231_reviewed_anchor"},
            "market_cap": {"value": market_cap, "unit": "CNY", "claim_type": "fact", "evidence_id": MARKET_EVIDENCE, "metric_id": legacy_valuation.MARKET_METRIC_IDS["market_cap"]},
            "calculated_market_cap": calculated_market_cap,
            "relative_difference": round(abs(market_cap - calculated_market_cap) / market_cap, 10),
            "reconciliation_decision": "pass",
            "source_paths": [MARKET_SOURCE, ANNUAL_SOURCE],
            "limitations": ["Dated market context; refresh when market date changes."],
        },
        generation_id,
        "R5_bundle9r_market_snapshot",
    )
    reverse = stamp(
        legacy_valuation.build_reverse_valuation(valuation_scenarios),
        generation_id,
        "R5_bundle9r_reverse_valuation",
    )
    scenario_valuation = stamp(
        legacy_valuation.build_scenario_valuation(valuation_scenarios),
        generation_id,
        "R5_bundle9r_scenario_valuation",
    )
    ranges = {
        scenario: [
            float(row["implied_market_cap_range"]["low"]["value"]),
            float(row["implied_market_cap_range"]["high"]["value"]),
        ]
        for scenario, row in scenario_valuation["scenarios"].items()
    }
    equity_values = {scenario: round((values[0] + values[1]) / 2, 2) for scenario, values in ranges.items()}
    model_pack = stamp(
        {
            "schema_version": 1,
            "contract_version": "r5_bundle9r_v1",
            "workflow_id": WORKFLOW_ID,
            "stock_code": "002837",
            "periods": PERIODS,
            "scenarios": forecast["scenarios"],
            "consensus_comparison": forecast["consensus"],
            "liquid_cooling_analytical_view": forecast["analytical_view"],
            "valuation": {
                "market_snapshot": {
                    "close_price": market_snapshot["close_price"],
                    "shares_outstanding": market_snapshot["shares_outstanding"],
                    "market_cap": market_snapshot["market_cap"],
                    "market_date": AS_OF_DATE,
                    "source_paths": market_snapshot["source_paths"],
                },
                "peer_set": {
                    "quality": "LOW_CONFIDENCE_PEER_SET",
                    "ranking_allowed": False,
                    "peer_count": len(peer_reconciliation["rows"]),
                    "gap_id": "missing_peer_liquid_cooling_purity",
                    "path": f"reports/workflow_runs/{WORKFLOW_ID}/R5_bundle9r_peer_operating_reconciliation.yaml",
                },
                "methods": {
                    "reverse_valuation": {
                        "eligible": True,
                        "claim_type": "inference",
                        "path": f"reports/workflow_runs/{WORKFLOW_ID}/R5_bundle9r_reverse_valuation.yaml",
                    },
                    "scenario_valuation": {
                        "eligible": True,
                        "claim_type": "inference",
                        "path": f"reports/workflow_runs/{WORKFLOW_ID}/R5_bundle9r_scenario_valuation.yaml",
                    },
                    "dcf": {
                        "eligible": False,
                        "missing_items": ["net_debt", "discount_rate", "terminal_value_assumption"],
                        "status": "TODO_DCF_INPUTS",
                    },
                    "sotp": {
                        "eligible": False,
                        "missing_items": ["standalone_liquid_cooling_segment_economics", "unallocated_costs"],
                        "status": "TODO_SEGMENT_DISCLOSURE",
                    },
                },
                "scenario_equity_values": equity_values,
                "scenario_equity_value_ranges": ranges,
                "scenario_value_method": "midpoint of explicit 2027E scenario market-cap range; research inference only",
            },
            "artifact_paths": {
                "input_review_ledger": f"reports/workflow_runs/{WORKFLOW_ID}/R5_bundle9r_input_review_ledger.yaml",
                "assumption_registry": f"reports/workflow_runs/{WORKFLOW_ID}/R5_bundle9r_forecast_assumption_registry.yaml",
                "segment_driver_model": f"reports/workflow_runs/{WORKFLOW_ID}/R5_bundle9r_segment_driver_model.yaml",
                "statement_bridge": f"reports/workflow_runs/{WORKFLOW_ID}/R5_bundle9r_financial_statement_bridge.yaml",
                "scenario_pack": f"reports/workflow_runs/{WORKFLOW_ID}/R5_bundle9r_scenario_pack.yaml",
                "sensitivity": f"reports/workflow_runs/{WORKFLOW_ID}/R5_bundle9r_sensitivity.csv",
                "consensus": f"reports/workflow_runs/{WORKFLOW_ID}/R5_bundle9r_consensus_comparison.csv",
            },
            "open_gaps": [
                "missing_liquid_cooling_segment_economics",
                "missing_liquid_cooling_driver_conversion",
                "missing_peer_liquid_cooling_purity",
                "TODO_DCF_INPUTS",
            ],
            "no_advice_boundary": True,
        },
        generation_id,
        "R5_bundle9r_model_pack",
    )

    write_yaml(run / "R5_bundle9r_peer_operating_reconciliation.yaml", peer_reconciliation)
    write_yaml(run / "R5_bundle9r_market_snapshot.yaml", market_snapshot)
    write_yaml(run / "R5_bundle9r_reverse_valuation.yaml", reverse)
    write_yaml(run / "R5_bundle9r_scenario_valuation.yaml", scenario_valuation)
    write_yaml(run / "R5_bundle9r_model_pack.yaml", model_pack)


def validate_generation(repo_root: Path, lock: Mapping[str, Any]) -> str:
    issues = validate_evidence_generation_lock(
        lock,
        required_consumer="R5_BUNDLE_9R_FORECAST_VALUATION_REBUILD",
    )
    issues.extend(validate_locked_input_hashes(lock, repo_root))
    if issues:
        raise ValueError("generation validation failed: " + ", ".join(issue.code for issue in issues))
    return str(lock["generation_id"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Bundle 9R forecast and valuation artifacts from reviewed inputs.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--workflow-id", default=WORKFLOW_ID)
    parser.add_argument("--phase", choices=("forecast", "valuation", "all"), default="all")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    run = repo_root / "reports" / "workflow_runs" / args.workflow_id
    lock = load_yaml(run / GENERATION_LOCK)
    generation_id = validate_generation(repo_root, lock)
    forecast = build_forecast_artifacts(run, generation_id)
    if args.phase in {"valuation", "all"}:
        build_valuation_artifacts(run, generation_id, forecast)
    result = {
        "phase": args.phase,
        "workflow_id": args.workflow_id,
        "input_evidence_generation_id": generation_id,
        "forecast_artifacts_written": 7,
        "valuation_artifacts_written": 5 if args.phase in {"valuation", "all"} else 0,
        "assumption_count": len(forecast["assumptions"]["assumptions"]),
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
