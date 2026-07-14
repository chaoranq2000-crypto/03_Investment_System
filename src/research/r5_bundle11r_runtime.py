from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from src.quality.semantic_research_gate import run_semantic_gate
from src.research.backflow_router import route_issues
from src.research.economic_archetypes import load_registry, load_yaml, validate_segment_plan
from src.research.operating_driver_engine import build_operating_driver_pack
from src.research.peer_eligibility import qualify_peers
from src.research.research_question_planner import build_research_question_matrix


def run_runtime(
    *,
    registry_path: str | Path,
    runtime_contract_path: str | Path,
    segment_plan_path: str | Path,
    evidence_status_path: str | Path,
    peer_pack_path: str | Path,
    semantic_payload_path: str | Path,
    semantic_config_path: str | Path,
) -> dict[str, Any]:
    registry = load_registry(registry_path)
    contract = load_yaml(runtime_contract_path)
    plan = load_yaml(segment_plan_path)
    evidence_status = load_yaml(evidence_status_path)
    peer_pack_input = load_yaml(peer_pack_path)
    semantic_payload = load_yaml(semantic_payload_path)
    semantic_config = load_yaml(semantic_config_path)

    periods = [str(x) for x in contract.get("periods", [])]
    scenarios = [str(x) for x in contract.get("scenarios", [])]
    plan_issues = validate_segment_plan(plan, registry, periods=periods, scenarios=scenarios)
    question_matrix = build_research_question_matrix(plan, registry, evidence_status.get("evidence_status", evidence_status))
    driver_pack = build_operating_driver_pack(
        plan,
        registry,
        periods=periods,
        scenarios=scenarios,
        maximum_proxy_revenue_share=float(contract.get("maximum_proxy_revenue_share", 0.45)),
        reconciliation_tolerance=float(contract.get("reconciliation_tolerance", 1e-6)),
    )
    peer_result = qualify_peers(
        peer_pack_input,
        minimum_score=float(contract.get("minimum_peer_score", 0.72)),
        minimum_eligible_peers=int(contract.get("minimum_eligible_peers", 3)),
    )

    base_row = next(
        (row for row in driver_pack.get("consolidated", []) if row.get("scenario") == "base" and row.get("period") == periods[0]),
        {},
    )
    semantic_payload = dict(semantic_payload)
    semantic_payload["model_summary"] = {**semantic_payload.get("model_summary", {}), "proxy_revenue_share": base_row.get("proxy_revenue_share", 0.0)}
    semantic_payload["peer_summary"] = {
        **semantic_payload.get("peer_summary", {}),
        "eligible_count": peer_result.get("eligible_count", 0),
        "peer_multiples_used": peer_pack_input.get("valuation_method_requested") == "peer_multiples",
    }
    semantic_result = run_semantic_gate(semantic_payload, semantic_config)

    issues: list[dict[str, Any]] = []
    issues.extend(plan_issues)
    issues.extend(driver_pack.get("issues", []))
    issues.extend(semantic_result.get("issues", []))
    if question_matrix.get("summary", {}).get("critical_open", 0):
        issues.append({"code": "QUESTION_CRITICAL_OPEN", "severity": "high", "scope": "research_questions", "message": str(question_matrix["summary"]["critical_open"])})
    if not peer_result.get("peer_method_eligible") and peer_pack_input.get("valuation_method_requested") == "peer_multiples":
        issues.append({"code": "PEER_SET_INELIGIBLE", "severity": "high", "scope": "valuation", "message": peer_result.get("decision")})
    backflow = route_issues(issues)
    blocked = any(issue.get("severity") in {"critical", "high"} for issue in issues)
    return {
        "schema_version": 1,
        "artifact_type": "r5_bundle11r_runtime_result",
        "decision": "needs_research_backflow" if blocked else "candidate_inputs_ready",
        "fixed_boundaries": {"sample_quality_allowed": False, "p2_allowed": False},
        "research_question_matrix": question_matrix,
        "operating_driver_pack": driver_pack,
        "peer_eligibility": peer_result,
        "semantic_quality": semantic_result,
        "backflow_plan": backflow,
        "all_issues": issues,
    }


def write_yaml(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(dict(payload), allow_unicode=True, sort_keys=False), encoding="utf-8")
