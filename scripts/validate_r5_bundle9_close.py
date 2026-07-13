from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


DEFAULT_WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
FORBIDDEN = ("买入", "卖出", "持有", "目标价", "仓位", "保证收益")


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def number_value(value: Any) -> float:
    if not isinstance(value, Mapping) or value.get("value") is None:
        raise ValueError(f"expected traced number object, got {value!r}")
    return float(value["value"])


def close_enough(left: float, right: float, tolerance: float = 0.01) -> bool:
    return abs(left - right) <= tolerance


def validate_bundle9(repo_root: Path, workflow_id: str) -> dict[str, Any]:
    run = repo_root / "reports/workflow_runs" / workflow_id
    errors: list[str] = []
    checks: dict[str, Any] = {}
    required = [
        "R5_bundle9_forecast_assumption_registry.yaml",
        "segment_forecast_model.yaml",
        "forecast_bridge.yaml",
        "forecast_sensitivity.csv",
        "market_snapshot.csv",
        "peer_market_snapshot.csv",
        "valuation_input_readiness.yaml",
        "valuation_request.yaml",
        "R5_bundle9_valuation_input_registry.yaml",
        "R5_bundle9_peer_reconciliation.yaml",
        "R5_bundle9_valuation_pack.yaml",
        "reverse_valuation.yaml",
        "scenario_valuation.yaml",
        "analyst_forecast_comparison.csv",
        "valuation/valuation_model.yaml",
        "valuation/valuation_snapshot.yaml",
        "valuation/peer_comparison.csv",
        "valuation/sensitivity_table.csv",
        "valuation/valuation_section_draft.md",
        "valuation/valuation_gap_requests.yaml",
        "valuation/valuation_quality_handoff.yaml",
        "valuation/valuation_output.yaml",
        "valuation/R5_valuation_handoff.yaml",
    ]
    missing = [name for name in required if not (run / name).exists()]
    if missing:
        errors.extend(f"missing required artifact: {name}" for name in missing)
    checks["required_artifacts"] = {"count": len(required), "missing": missing}
    if missing:
        return {
            "artifact_type": "R5_bundle9_close_input_validation",
            "schema_version": "v0.1",
            "workflow_id": workflow_id,
            "decision": "fail",
            "checks": checks,
            "errors": errors,
        }

    registry = load_yaml(run / "R5_bundle9_forecast_assumption_registry.yaml")
    assumptions = registry.get("assumptions") or []
    if registry.get("review_status") != "reviewed" or len(assumptions) != 42:
        errors.append("forecast assumption registry must contain 42 reviewed assumptions")
    missing_trace = [
        row.get("assumption_id", "UNKNOWN")
        for row in assumptions
        if not row.get("supporting_evidence_ids") or not row.get("supporting_metric_ids")
    ]
    if missing_trace:
        errors.append(f"forecast assumptions missing dual trace: {missing_trace}")
    checks["forecast_assumptions"] = {"rows": len(assumptions), "missing_dual_trace": len(missing_trace)}

    forecast = load_yaml(run / "segment_forecast_model.yaml")
    if forecast.get("status") != "ready":
        errors.append("segment forecast model status is not ready")
    expected_scenarios = {"bear_case", "base_case", "bull_case"}
    actual_scenarios = set((forecast.get("scenarios") or {}).keys())
    if actual_scenarios != expected_scenarios:
        errors.append(f"forecast scenarios mismatch: {actual_scenarios}")
    reconciliation_max = 0.0
    for scenario_name, scenario in (forecast.get("scenarios") or {}).items():
        table = scenario.get("forecast_table") or {}
        if set(table) != {"2026E", "2027E", "2028E"}:
            errors.append(f"{scenario_name} forecast years mismatch")
        for year, row in table.items():
            for metric in ("revenue", "gross_margin", "gross_profit", "net_profit_attributable", "eps"):
                metric_obj = row.get(metric)
                if not isinstance(metric_obj, Mapping) or metric_obj.get("value") is None or not metric_obj.get("assumption_id"):
                    errors.append(f"{scenario_name}.{year}.{metric} lacks traced value")
    bridge = load_yaml(run / "forecast_bridge.yaml")
    for scenario in (bridge.get("scenarios") or {}).values():
        for row in scenario.values():
            bridge_row = row.get("bridge") if isinstance(row, Mapping) else None
            if not isinstance(bridge_row, Mapping) or "reconciliation_difference" not in bridge_row:
                errors.append("forecast bridge row lacks reconciliation_difference")
                continue
            difference = abs(float(bridge_row["reconciliation_difference"]))
            reconciliation_max = max(reconciliation_max, difference)
            if difference > 0.01:
                errors.append("forecast profit bridge reconciliation exceeds 0.01 CNY")
    checks["forecast_model"] = {
        "scenarios": len(actual_scenarios),
        "years_per_scenario": 3,
        "profit_bridge_max_abs_difference": reconciliation_max,
    }

    market_rows = read_csv(run / "market_snapshot.csv")
    peer_rows = read_csv(run / "peer_market_snapshot.csv")
    if len(market_rows) != 1 or market_rows[0].get("snapshot_status") != "reviewed":
        errors.append("market snapshot must contain one reviewed row")
    if len(peer_rows) != 4:
        errors.append("peer market snapshot must contain four rows")
    if any(row.get("confidence") != "low_confidence_fixture" for row in peer_rows):
        errors.append("all peer rows must retain low-confidence labels")
    if any(row.get("pe_forward_2026e") for row in peer_rows):
        errors.append("peer forward PE must remain missing rather than guessed")
    checks["normalized_inputs"] = {
        "market_rows": len(market_rows),
        "peer_rows": len(peer_rows),
        "peer_forward_values": sum(bool(row.get("pe_forward_2026e")) for row in peer_rows),
    }

    scenarios = load_yaml(run / "scenario_valuation.yaml")
    scenario_checks = 0
    for scenario_name, row in scenarios.get("scenarios", {}).items():
        profit = number_value(row["profit_anchor"])
        low_multiple = number_value(row["multiple_range"]["low"])
        high_multiple = number_value(row["multiple_range"]["high"])
        low_value = number_value(row["implied_market_cap_range"]["low"])
        high_value = number_value(row["implied_market_cap_range"]["high"])
        if not close_enough(low_value, profit * low_multiple):
            errors.append(f"{scenario_name} low scenario value does not reconcile")
        if not close_enough(high_value, profit * high_multiple):
            errors.append(f"{scenario_name} high scenario value does not reconcile")
        scenario_checks += 2
    reverse = load_yaml(run / "reverse_valuation.yaml")
    market_cap = number_value(reverse["market_cap_anchor"])
    reverse_checks = 0
    for row in reverse.get("thresholds", []):
        multiple = number_value(row["multiple"])
        required_profit = number_value(row["required_net_profit"])
        if not close_enough(required_profit, market_cap / multiple):
            errors.append(f"reverse threshold {multiple}x does not reconcile")
        reverse_checks += 1
    checks["valuation_math"] = {"scenario_checks": scenario_checks, "reverse_checks": reverse_checks}

    pack = load_yaml(run / "R5_bundle9_valuation_pack.yaml")
    handoff = load_yaml(run / "valuation/R5_valuation_handoff.yaml")
    company_output = load_yaml(run / "valuation/valuation_output.yaml")
    if pack.get("status") != "partial" or pack.get("sample_quality_allowed") is not False:
        errors.append("valuation pack must remain partial and sample_quality_allowed=false")
    if handoff.get("sample_quality_allowed") is not False:
        errors.append("valuation handoff must not allow sample quality")
    if company_output.get("input_status") != "partial_with_todos":
        errors.append("company valuation output must preserve partial_with_todos")
    method_status = {row.get("method_id"): row.get("status") for row in pack.get("valuation_methods", [])}
    if method_status.get("dcf") != "TODO" or method_status.get("sotp") != "TODO":
        errors.append("DCF and SOTP must stay explicitly unsupported")
    checks["valuation_boundary"] = {
        "pack_status": pack.get("status"),
        "company_output_status": company_output.get("input_status"),
        "dcf": method_status.get("dcf"),
        "sotp": method_status.get("sotp"),
        "sample_quality_allowed": pack.get("sample_quality_allowed"),
    }

    analyst_rows = read_csv(run / "analyst_forecast_comparison.csv")
    if len(analyst_rows) != 3 or any(row.get("claim_type") != "analyst_view" for row in analyst_rows):
        errors.append("analyst comparison must contain three analyst_view rows")
    if any(row.get("source_evidence_id") != "ev_third_party_research_002837_20260713_20f610" for row in analyst_rows):
        errors.append("analyst comparison evidence id mismatch")
    checks["analyst_comparison"] = {"rows": len(analyst_rows), "claim_type": "analyst_view"}

    scan_paths = [
        run / "R5_bundle9_forecast_assumption_registry.yaml",
        run / "segment_forecast_model.yaml",
        run / "R5_bundle9_valuation_input_registry.yaml",
        run / "R5_bundle9_valuation_pack.yaml",
        run / "reverse_valuation.yaml",
        run / "scenario_valuation.yaml",
        run / "valuation/valuation_output.yaml",
        run / "valuation/R5_valuation_handoff.yaml",
        run / "valuation/valuation_section_draft.md",
    ]
    violations: list[str] = []
    for path in scan_paths:
        text = path.read_text(encoding="utf-8")
        for phrase in FORBIDDEN:
            if phrase in text:
                violations.append(f"{path.name}:{phrase}")
    if violations:
        errors.append(f"no-advice scan violations: {violations}")
    checks["no_advice_scan"] = {"files": len(scan_paths), "violations": violations}

    return {
        "artifact_type": "R5_bundle9_close_input_validation",
        "schema_version": "v0.1",
        "workflow_id": workflow_id,
        "decision": "pass" if not errors else "fail",
        "checks": checks,
        "errors": errors,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Bundle 9 forecast and valuation close inputs.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--workflow-id", default=DEFAULT_WORKFLOW_ID)
    parser.add_argument("--output", default="")
    args = parser.parse_args(argv)
    payload = validate_bundle9(Path(args.repo_root), args.workflow_id)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
