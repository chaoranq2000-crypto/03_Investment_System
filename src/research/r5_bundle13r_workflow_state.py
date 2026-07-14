from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any, Mapping


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def apply_bundle13r_result_to_state(
    state: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    generation_id: str,
    as_of: str | None = None,
) -> dict[str, Any]:
    out = deepcopy(dict(state))
    decision = str(result.get("decision", ""))
    stamp = as_of or date.today().isoformat()
    route = {
        "blocked_invalid_reviewed_backfill": (
            "R5_bundle13r_reviewed_backfill_fix",
            "evidence-ingest",
            "blocked",
        ),
        "backflow_execution_in_progress": (
            "R5_bundle13r_t1_t2_evidence_backflow",
            str(result.get("required_next_skill") or "evidence-ingest"),
            "in_progress",
        ),
        "ready_for_bundle12r_rerun": (
            "R5_bundle13r_rerun_bundle12r_operating_gate",
            "research-orchestrator",
            "in_progress",
        ),
        "operating_evidence_requalified": (
            "R5_bundle13r_rp6_valuation_eligibility_refresh",
            "company-valuation",
            "in_progress",
        ),
    }
    current_stage, next_skill, status = route.get(
        decision,
        ("R5_bundle13r_result_unrecognized", "research-orchestrator", "blocked"),
    )
    out.update(
        {
            "status": status,
            "updated_at": stamp,
            "current_stage": current_stage,
            "next_stage": current_stage,
            "active_skill": next_skill,
            "required_next_skill": next_skill,
            "quality_target": "R5_bundle13r_evidence_backflow_execution",
        }
    )
    out["bundle13r_backflow_execution"] = {
        "status": decision,
        "generation_id": generation_id,
        "source_bundle12r_generation_id": result.get("source_bundle12r_generation_id"),
        "resolved_t1_t2_item_count": result.get("resolved_t1_t2_item_count", 0),
        "unresolved_t1_t2_item_count": result.get("unresolved_t1_t2_item_count", 0),
        "valuation_backflow_allowed": bool(result.get("valuation_backflow_allowed")),
        "human_review_status": "pending",
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
    backflow = _mapping(out.get("quality_backflow"))
    backflow.update(
        {
            "current_first_route": next_skill,
            "current_first_stage": current_stage,
            "canonical_sample_quality_allowed": False,
            "canonical_p2_allowed": False,
        }
    )
    out["quality_backflow"] = backflow
    out["sample_quality_allowed"] = False
    out["p2_allowed"] = False
    return out
