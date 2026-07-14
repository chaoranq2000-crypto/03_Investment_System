from __future__ import annotations

from typing import Any, Mapping


DEFAULT_WEIGHTS = {
    "business_definition_compatibility": 0.25,
    "revenue_purity": 0.20,
    "accounting_boundary_compatibility": 0.15,
    "period_consistency": 0.10,
    "forecast_date_consistency": 0.10,
    "capital_intensity_similarity": 0.10,
    "customer_and_revenue_recognition_similarity": 0.10,
}


def qualify_peers(
    peer_pack: Mapping[str, Any],
    *,
    minimum_score: float = 0.72,
    minimum_eligible_peers: int = 3,
    weights: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    weights = dict(weights or DEFAULT_WEIGHTS)
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError("peer eligibility weights must sum to 1.0")

    evaluated: list[dict[str, Any]] = []
    for peer in peer_pack.get("peers", []):
        dimensions = peer.get("dimensions", {})
        score = 0.0
        missing: list[str] = []
        for name, weight in weights.items():
            value = dimensions.get(name)
            if value is None:
                missing.append(name)
                numeric = 0.0
            else:
                numeric = max(0.0, min(1.0, float(value)))
            score += numeric * weight
        hard_blocks = list(peer.get("hard_blocks", []))
        eligible = score >= minimum_score and not hard_blocks and not missing
        evaluated.append(
            {
                "peer_id": peer.get("peer_id"),
                "peer_name": peer.get("peer_name"),
                "score": round(score, 6),
                "eligible": eligible,
                "missing_dimensions": missing,
                "hard_blocks": hard_blocks,
                "source_ids": list(peer.get("source_ids", [])),
                "notes": peer.get("notes"),
            }
        )

    eligible = [item for item in evaluated if item["eligible"]]
    method_requested = str(peer_pack.get("valuation_method_requested", "peer_multiples"))
    peer_method_eligible = len(eligible) >= minimum_eligible_peers
    if method_requested == "peer_multiples" and not peer_method_eligible:
        decision = "waive_peer_multiples_use_reverse_or_scenario_valuation"
    else:
        decision = "peer_method_qualified" if peer_method_eligible else "context_only"
    return {
        "schema_version": 1,
        "artifact_type": "r5_bundle11r_peer_eligibility",
        "decision": decision,
        "minimum_score": minimum_score,
        "minimum_eligible_peers": minimum_eligible_peers,
        "eligible_count": len(eligible),
        "peer_method_eligible": peer_method_eligible,
        "evaluated_peers": evaluated,
    }
