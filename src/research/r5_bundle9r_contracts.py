from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str
    message: str
    path: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Mapping) and isinstance(value.get("value"), (int, float)):
        return float(value["value"])
    return None


def _claim_type(value: Any) -> str | None:
    if isinstance(value, Mapping):
        raw = value.get("claim_type")
        return str(raw) if raw is not None else None
    return None


def _walk_strings(value: Any) -> Iterable[tuple[str, str]]:
    def walk(node: Any, path: str) -> Iterable[tuple[str, str]]:
        if isinstance(node, Mapping):
            for key, child in node.items():
                child_path = f"{path}.{key}" if path else str(key)
                yield from walk(child, child_path)
        elif isinstance(node, list):
            for index, child in enumerate(node):
                yield from walk(child, f"{path}[{index}]")
        elif isinstance(node, str):
            yield path, node
    yield from walk(value, "")


def validate_evidence_generation_lock(
    lock: Mapping[str, Any],
    *,
    expected_generation_id: str | None = None,
    expected_aggregate_sha256: str | None = None,
    required_consumer: str | None = None,
) -> list[Issue]:
    issues: list[Issue] = []
    generation_id = str(lock.get("generation_id") or "")
    aggregate = str(lock.get("aggregate_sha256") or "")
    if not generation_id:
        issues.append(Issue("missing_generation_id", "critical", "Evidence generation lock has no generation_id."))
    if expected_generation_id and generation_id != expected_generation_id:
        issues.append(Issue("generation_id_mismatch", "critical", f"Expected {expected_generation_id}, got {generation_id or '<missing>'}."))
    if expected_aggregate_sha256 and aggregate != expected_aggregate_sha256:
        issues.append(Issue("aggregate_hash_mismatch", "critical", "Evidence generation aggregate hash does not match the package binding."))
    if int(lock.get("missing_input_count") or 0) != 0:
        issues.append(Issue("generation_has_missing_inputs", "critical", "Evidence generation lock contains missing inputs."))
    if required_consumer and required_consumer not in list(lock.get("downstream_consumers") or []):
        issues.append(Issue("consumer_not_authorized", "critical", f"Generation lock does not authorize {required_consumer}."))
    return issues


def validate_generation_bound_artifact(
    artifact: Mapping[str, Any],
    *,
    current_generation_id: str,
    artifact_label: str,
) -> list[Issue]:
    recorded = str(artifact.get("input_evidence_generation_id") or "")
    if recorded != current_generation_id:
        return [Issue("stale_or_unbound_artifact", "critical", f"{artifact_label} records {recorded or '<missing>'}, expected {current_generation_id}.")]
    return []


def validate_locked_input_hashes(lock: Mapping[str, Any], repo_root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for row in lock.get("inputs") or []:
        if not isinstance(row, Mapping):
            issues.append(Issue("invalid_lock_input_row", "critical", "Generation lock input row is not a mapping."))
            continue
        rel = str(row.get("path") or "")
        expected = str(row.get("sha256") or "")
        path = repo_root / rel
        if not path.exists():
            issues.append(Issue("locked_input_missing", "critical", f"Locked input is missing: {rel}", rel))
            continue
        actual = sha256_file(path)
        if expected and actual != expected:
            issues.append(Issue("locked_input_hash_changed", "critical", f"Locked input hash changed: {rel}", rel))
    return issues


def validate_model_pack(model: Mapping[str, Any], contract: Mapping[str, Any], *, expected_generation_id: str) -> list[Issue]:
    issues: list[Issue] = []
    issues.extend(validate_generation_bound_artifact(model, current_generation_id=expected_generation_id, artifact_label="model pack"))

    periods = [str(x) for x in contract.get("periods") or []]
    scenario_names = [str(x) for x in contract.get("scenarios") or []]
    model_periods = [str(x) for x in model.get("periods") or []]
    if model_periods != periods:
        issues.append(Issue("period_contract_mismatch", "critical", f"Model periods {model_periods} do not equal contract periods {periods}."))

    scenarios = model.get("scenarios")
    if not isinstance(scenarios, Mapping):
        issues.append(Issue("scenarios_missing", "critical", "Model pack must contain a scenarios mapping."))
        scenarios = {}

    minimum_segments = int(contract.get("minimum_segment_count") or 0)
    required_segment_ids = set(str(x) for x in contract.get("required_segment_ids") or [])
    allowed_basis = set(str(x) for x in contract.get("allowed_disclosure_basis") or [])
    required_bridge = [str(x) for x in contract.get("required_bridge_fields") or []]
    component_fields = [str(x) for x in contract.get("other_operating_component_fields") or []]
    prohibited_plugs = set(str(x).lower() for x in contract.get("prohibited_plug_fields") or [])
    tol = contract.get("numeric_tolerances") or {}
    revenue_tol = float(tol.get("segment_revenue_sum_abs_cny") or 1.0)
    gross_profit_tol = float(tol.get("segment_gross_profit_sum_abs_cny") or 1.0)
    bridge_tol = float(tol.get("bridge_arithmetic_abs_cny") or 1.0)
    eps_tol = float(tol.get("eps_abs_per_share") or 0.000001)

    scenario_metrics: dict[str, dict[str, dict[str, float]]] = {}
    for scenario_name in scenario_names:
        scenario = scenarios.get(scenario_name)
        if not isinstance(scenario, Mapping):
            issues.append(Issue("scenario_missing", "critical", f"Missing scenario: {scenario_name}."))
            continue
        years = scenario.get("periods")
        if not isinstance(years, Mapping):
            issues.append(Issue("scenario_periods_missing", "critical", f"Scenario {scenario_name} has no periods mapping."))
            continue
        scenario_metrics[scenario_name] = {}
        for period in periods:
            year = years.get(period)
            if not isinstance(year, Mapping):
                issues.append(Issue("period_missing", "critical", f"Scenario {scenario_name} is missing {period}."))
                continue
            segments = year.get("segments")
            if not isinstance(segments, Mapping):
                issues.append(Issue("segments_missing", "critical", f"{scenario_name}/{period} has no segments mapping."))
                segments = {}
            if len(segments) < minimum_segments:
                issues.append(Issue("segment_count_too_low", "critical", f"{scenario_name}/{period} has {len(segments)} segments; contract requires at least {minimum_segments}."))
            missing_ids = required_segment_ids - set(str(x) for x in segments)
            if missing_ids:
                issues.append(Issue("required_segments_missing", "critical", f"{scenario_name}/{period} missing segments: {sorted(missing_ids)}."))

            segment_revenue = 0.0
            segment_gp = 0.0
            for segment_id, segment in segments.items():
                if not isinstance(segment, Mapping):
                    issues.append(Issue("invalid_segment", "critical", f"{scenario_name}/{period}/{segment_id} is not a mapping."))
                    continue
                basis = str(segment.get("disclosure_basis") or "")
                if basis not in allowed_basis:
                    issues.append(Issue("invalid_disclosure_basis", "critical", f"{segment_id} has invalid disclosure_basis={basis or '<missing>'}."))
                revenue = _num(segment.get("revenue"))
                margin = _num(segment.get("gross_margin"))
                gp = _num(segment.get("gross_profit"))
                if revenue is None or margin is None or gp is None:
                    issues.append(Issue("segment_numeric_missing", "critical", f"{scenario_name}/{period}/{segment_id} requires revenue, gross_margin and gross_profit."))
                    continue
                if abs(gp - revenue * margin / 100.0) > max(1.0, abs(revenue) * 1e-8):
                    issues.append(Issue("segment_gross_profit_formula_error", "critical", f"Gross-profit arithmetic fails for {scenario_name}/{period}/{segment_id}."))
                lower_id = str(segment_id).lower()
                additive_to_company_total = True
                if "liquid" in lower_id or "液冷" in lower_id:
                    boundary = contract.get("liquid_cooling_boundary") or {}
                    if not bool(boundary.get("issuer_disclosed_standalone_economics")):
                        if basis != "analytical_estimate":
                            issues.append(Issue("liquid_cooling_boundary_violation", "critical", "Standalone liquid-cooling economics are not issuer-disclosed and must be analytical_estimate."))
                        if _claim_type(segment.get("revenue")) != str(boundary.get("required_claim_type") or "estimate"):
                            issues.append(Issue("liquid_cooling_claim_type_violation", "critical", "Liquid-cooling standalone revenue must be marked estimate."))
                        if str(segment.get("gap_id") or "") != str(boundary.get("required_gap_id") or ""):
                            issues.append(Issue("liquid_cooling_gap_not_linked", "critical", "Liquid-cooling estimate must link the issuer nondisclosure gap ID."))
                        required_overlap = str(boundary.get("required_overlap_control") or "")
                        expected_additive = bool(boundary.get("additive_to_company_total"))
                        if (
                            str(segment.get("overlap_control") or "") != required_overlap
                            or bool(segment.get("additive_to_company_total", True)) != expected_additive
                        ):
                            issues.append(Issue("liquid_cooling_double_count_risk", "critical", "Standalone liquid-cooling analytical estimates must be explicitly non-additive to disclosed company totals."))
                        else:
                            additive_to_company_total = expected_additive
                if additive_to_company_total:
                    segment_revenue += revenue
                    segment_gp += gp

            bridge = year.get("bridge")
            if not isinstance(bridge, Mapping):
                issues.append(Issue("bridge_missing", "critical", f"{scenario_name}/{period} has no bridge mapping."))
                continue
            for key in required_bridge:
                if _num(bridge.get(key)) is None:
                    issues.append(Issue("bridge_field_missing", "critical", f"{scenario_name}/{period} bridge missing numeric field {key}."))
            for key in component_fields:
                if _num(bridge.get(key)) is None:
                    issues.append(Issue("operating_component_missing", "critical", f"{scenario_name}/{period} bridge missing explicit operating component {key}."))

            def inspect_keys(node: Any, prefix: str = "") -> None:
                if isinstance(node, Mapping):
                    for raw_key, child in node.items():
                        key = str(raw_key)
                        path = f"{prefix}.{key}" if prefix else key
                        if key.lower() in prohibited_plugs:
                            issues.append(Issue("prohibited_plug_field", "critical", f"{scenario_name}/{period} uses prohibited plug field {path}."))
                        inspect_keys(child, path)
                elif isinstance(node, list):
                    for index, child in enumerate(node):
                        inspect_keys(child, f"{prefix}[{index}]")

            inspect_keys(bridge)
            bridge_revenue = _num(bridge.get("revenue"))
            bridge_gp = _num(bridge.get("gross_profit"))
            if bridge_revenue is not None and abs(segment_revenue - bridge_revenue) > revenue_tol:
                issues.append(Issue("segment_revenue_does_not_reconcile", "critical", f"{scenario_name}/{period} segment revenue differs from bridge by {segment_revenue - bridge_revenue:.2f}."))
            if bridge_gp is not None and abs(segment_gp - bridge_gp) > gross_profit_tol:
                issues.append(Issue("segment_gp_does_not_reconcile", "critical", f"{scenario_name}/{period} segment gross profit differs from bridge by {segment_gp - bridge_gp:.2f}."))

            expense_keys = (
                "tax_surcharge",
                "selling_expense",
                "administrative_expense",
                "rd_expense",
                "financial_expense",
            )
            expense_values = [_num(bridge.get(key)) for key in expense_keys]
            component_values = [_num(bridge.get(key)) for key in component_fields]
            operating_profit = _num(bridge.get("operating_profit"))
            if bridge_gp is not None and operating_profit is not None and None not in expense_values and None not in component_values:
                expected_operating_profit = bridge_gp - sum(float(x) for x in expense_values) + sum(float(x) for x in component_values)
                if abs(operating_profit - expected_operating_profit) > bridge_tol:
                    issues.append(Issue("operating_profit_bridge_error", "critical", f"{scenario_name}/{period} operating-profit bridge does not reconcile."))
            non_operating_net = _num(bridge.get("non_operating_net"))
            pretax_profit = _num(bridge.get("pretax_profit"))
            if operating_profit is not None and non_operating_net is not None and pretax_profit is not None:
                if abs(pretax_profit - operating_profit - non_operating_net) > bridge_tol:
                    issues.append(Issue("pretax_profit_bridge_error", "critical", f"{scenario_name}/{period} pretax-profit bridge does not reconcile."))
            income_tax = _num(bridge.get("income_tax"))
            minority_interest = _num(bridge.get("minority_interest"))
            nonrecurring_items = _num(bridge.get("nonrecurring_items"))
            attributable_profit = _num(bridge.get("attributable_net_profit"))
            if None not in (pretax_profit, income_tax, minority_interest, nonrecurring_items, attributable_profit):
                expected_attributable = pretax_profit - income_tax - minority_interest + nonrecurring_items
                if abs(attributable_profit - expected_attributable) > bridge_tol:
                    issues.append(Issue("attributable_profit_bridge_error", "critical", f"{scenario_name}/{period} attributable-profit bridge does not reconcile."))
            shares = _num(bridge.get("shares_outstanding"))
            eps = _num(bridge.get("eps"))
            if attributable_profit is not None and shares is not None and shares > 0 and eps is not None:
                if abs(eps - attributable_profit / shares) > eps_tol:
                    issues.append(Issue("eps_bridge_error", "critical", f"{scenario_name}/{period} EPS does not reconcile to attributable profit / shares."))
            operating_cash_flow = _num(bridge.get("operating_cash_flow"))
            capex = _num(bridge.get("capex"))
            free_cash_flow = _num(bridge.get("free_cash_flow"))
            if None not in (operating_cash_flow, capex, free_cash_flow):
                if abs(free_cash_flow - (operating_cash_flow - capex)) > bridge_tol:
                    issues.append(Issue("free_cash_flow_bridge_error", "critical", f"{scenario_name}/{period} free-cash-flow bridge does not reconcile."))
            scenario_metrics[scenario_name][period] = {
                "revenue": float(bridge_revenue or 0.0),
                "attributable_net_profit": float(_num(bridge.get("attributable_net_profit")) or 0.0),
            }

    for period in periods:
        if all(name in scenario_metrics and period in scenario_metrics[name] for name in ("bear", "base", "bull")):
            for metric in ("revenue", "attributable_net_profit"):
                bear = scenario_metrics["bear"][period][metric]
                base = scenario_metrics["base"][period][metric]
                bull = scenario_metrics["bull"][period][metric]
                if not (bear <= base <= bull):
                    issues.append(Issue("scenario_monotonicity_failure", "critical", f"{period} {metric} is not bear <= base <= bull."))

    consensus = model.get("consensus_comparison")
    if not isinstance(consensus, Mapping):
        issues.append(Issue("consensus_comparison_missing", "high", "Consensus comparison is required even when unavailable."))
    else:
        required_claim = str((contract.get("consensus_boundary") or {}).get("allowed_claim_type") or "analyst_view")
        if str(consensus.get("claim_type") or "") != required_claim:
            issues.append(Issue("consensus_claim_boundary_violation", "critical", f"Consensus must be labeled {required_claim}."))
        minimum_count = int((contract.get("consensus_boundary") or {}).get("minimum_institution_count_for_consensus_label") or 0)
        observed_count = _num(consensus.get("minimum_institution_count"))
        if observed_count is None or observed_count < minimum_count:
            issues.append(Issue("consensus_institution_count_too_low", "critical", f"Consensus label requires at least {minimum_count} institutions."))

    valuation = model.get("valuation")
    if not isinstance(valuation, Mapping):
        issues.append(Issue("valuation_missing", "critical", "Model pack must contain valuation."))
    else:
        market = valuation.get("market_snapshot") or {}
        close_price = _num(market.get("close_price"))
        shares = _num(market.get("shares_outstanding"))
        market_cap = _num(market.get("market_cap"))
        if None in (close_price, shares, market_cap):
            issues.append(Issue("market_snapshot_incomplete", "critical", "Valuation market snapshot requires close_price, shares_outstanding and market_cap."))
        elif market_cap:
            relative = abs(market_cap - close_price * shares) / abs(market_cap)
            max_relative = float((contract.get("numeric_tolerances") or {}).get("market_cap_relative") or 0.005)
            if relative > max_relative:
                issues.append(Issue("market_cap_share_price_mismatch", "critical", f"Market cap differs from close*shares by {relative:.2%}."))

        peer_set = valuation.get("peer_set") or {}
        peer_quality = str(peer_set.get("quality") or "")
        low_labels = set(str(x) for x in (contract.get("peer_boundary") or {}).get("low_confidence_labels") or [])
        if peer_quality in low_labels and bool(peer_set.get("ranking_allowed")):
            issues.append(Issue("low_confidence_peer_ranking_enabled", "critical", "Low-confidence peer set cannot enable ranking."))

        methods = valuation.get("methods") or {}
        for method in (contract.get("valuation_requirements") or {}).get("required_methods") or []:
            row = methods.get(method)
            if not isinstance(row, Mapping) or not bool(row.get("eligible")):
                issues.append(Issue("required_valuation_method_missing", "critical", f"Required valuation method {method} is not eligible/present."))

        equity = valuation.get("scenario_equity_values") or {}
        bear_value = _num(equity.get("bear"))
        base_value = _num(equity.get("base"))
        bull_value = _num(equity.get("bull"))
        if None in (bear_value, base_value, bull_value):
            issues.append(Issue("scenario_equity_values_missing", "critical", "Valuation requires bear/base/bull equity values."))
        elif not (bear_value <= base_value <= bull_value):
            issues.append(Issue("valuation_scenario_monotonicity_failure", "critical", "Equity values are not bear <= base <= bull."))

    for path, text in _walk_strings(model):
        for token in contract.get("prohibited_action_language") or []:
            if str(token) and str(token) in text:
                issues.append(Issue("prohibited_action_language", "critical", f"Prohibited action language '{token}' at {path}.", path))
    return issues


def decision_from_issues(issues: Sequence[Issue]) -> str:
    return "needs_fix" if any(issue.severity in {"critical", "high"} for issue in issues) else "pass"


def issues_payload(issues: Sequence[Issue]) -> list[dict[str, str]]:
    return [issue.to_dict() for issue in issues]


def stable_aggregate(rows: Sequence[Mapping[str, str]]) -> str:
    payload = json.dumps(list(rows), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
