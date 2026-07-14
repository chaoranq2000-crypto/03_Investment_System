from __future__ import annotations

import hashlib
from typing import Any, Mapping

from .economic_archetypes import ArchetypeRegistry, ContractError


_STATUS_ORDER = {"confirmed": 0, "bounded_estimate": 1, "missing": 2, "conflicting": 3}


def build_research_question_matrix(
    segment_plan: Mapping[str, Any],
    registry: ArchetypeRegistry,
    evidence_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate economically specific research questions from business-line drivers."""
    evidence_status = evidence_status or {}
    questions: list[dict[str, Any]] = []
    for segment in segment_plan.get("segments", []):
        segment_id = str(segment.get("segment_id", "")).strip()
        archetype_id = str(segment.get("archetype_id", "")).strip()
        if not segment_id or not archetype_id:
            continue
        spec = registry.get(archetype_id)
        critical_drivers = set(segment.get("thesis_critical_drivers", []))
        for driver in spec.drivers:
            evidence_key = f"{segment_id}.{driver.driver_id}"
            state_raw = evidence_status.get(evidence_key, {})
            if isinstance(state_raw, str):
                state_raw = {"status": state_raw}
            status = str(state_raw.get("status", "missing"))
            if status not in _STATUS_ORDER:
                raise ContractError(f"invalid evidence status for {evidence_key}: {status}")
            criticality = "critical" if driver.driver_id in critical_drivers or driver.required else "supporting"
            questions.append(
                {
                    "question_id": _stable_id(segment_id, driver.driver_id),
                    "segment_id": segment_id,
                    "archetype_id": archetype_id,
                    "driver_id": driver.driver_id,
                    "question": _question_text(segment_id, driver.driver_id, driver.unit),
                    "required_unit": driver.unit,
                    "criticality": criticality,
                    "status": status,
                    "evidence_ids": list(state_raw.get("evidence_ids", [])),
                    "range": state_raw.get("range"),
                    "period": state_raw.get("period"),
                    "confidence": state_raw.get("confidence", "low" if status == "missing" else "medium"),
                    "owner_skill": "evidence-ingest" if status in {"missing", "conflicting"} else "stock-deep-dive",
                    "backflow_stage": "RP2_operating_evidence" if status in {"missing", "conflicting"} else None,
                    "proxy_allowed": bool(segment.get("allow_proxy", False)),
                    "replacement_signal": _replacement_signal(segment_id, driver.driver_id),
                }
            )

    questions.sort(key=lambda item: (_STATUS_ORDER[item["status"]], item["segment_id"], item["driver_id"]))
    summary = {
        "total": len(questions),
        "confirmed": sum(q["status"] == "confirmed" for q in questions),
        "bounded_estimate": sum(q["status"] == "bounded_estimate" for q in questions),
        "missing": sum(q["status"] == "missing" for q in questions),
        "conflicting": sum(q["status"] == "conflicting" for q in questions),
        "critical_open": sum(q["criticality"] == "critical" and q["status"] in {"missing", "conflicting"} for q in questions),
    }
    decision = "complete" if summary["critical_open"] == 0 else "research_backflow_required"
    return {
        "schema_version": 1,
        "artifact_type": "r5_bundle11r_research_question_matrix",
        "decision": decision,
        "summary": summary,
        "questions": questions,
    }


def _stable_id(segment_id: str, driver_id: str) -> str:
    digest = hashlib.sha256(f"{segment_id}:{driver_id}".encode("utf-8")).hexdigest()[:10]
    return f"rq_{segment_id}_{driver_id}_{digest}"


def _question_text(segment_id: str, driver_id: str, unit: str) -> str:
    return f"{segment_id} 的 {driver_id} 在目标期间的可核验数值或区间是多少（单位：{unit}），其来源、口径和确认时点是什么？"


def _replacement_signal(segment_id: str, driver_id: str) -> str:
    return f"获得可追溯的 {segment_id}.{driver_id} 后，替换对应 proxy 并重算分部收入、毛利与现金流。"
