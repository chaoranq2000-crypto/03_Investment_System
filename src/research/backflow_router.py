from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping


DEFAULT_ROUTES: dict[str, tuple[str, str]] = {
    "REQUIRED_DRIVER_MISSING": ("RP2_operating_evidence", "evidence-ingest"),
    "SEGMENT_EVALUATION_FAILED": ("RP4_operating_model", "stock-deep-dive"),
    "PROXY_REVENUE_SHARE_EXCEEDED": ("RP2_operating_evidence", "evidence-ingest"),
    "QUESTION_CRITICAL_OPEN": ("RP2_operating_evidence", "evidence-ingest"),
    "PEER_SET_INELIGIBLE": ("RP5_peer_valuation", "compare-stocks"),
    "SECTION_GENERIC": ("RP6_analysis_synthesis", "stock-deep-dive"),
    "SECTION_NO_MODEL_LINK": ("RP4_operating_model", "stock-deep-dive"),
    "INSIGHT_DUPLICATED": ("RP7_report_planning", "memo-writer"),
    "WATCHPOINT_NOT_FALSIFIABLE": ("RP6_analysis_synthesis", "stock-deep-dive"),
    "GENERATION_BINDING_FAILED": ("T0_orchestration", "research-orchestrator"),
    "DIRECT_TRADING_LANGUAGE": ("RP8_quality_review", "quality-review"),
}


def route_issues(
    issues: Iterable[Mapping[str, Any]],
    routes: Mapping[str, tuple[str, str]] | None = None,
) -> dict[str, Any]:
    routes = dict(routes or DEFAULT_ROUTES)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    unrouted: list[dict[str, Any]] = []
    for issue in issues:
        code = str(issue.get("code", ""))
        if code in routes:
            stage, skill = routes[code]
            enriched = dict(issue)
            enriched["required_next_stage"] = stage
            enriched["required_next_skill"] = skill
            grouped[(stage, skill)].append(enriched)
        else:
            unrouted.append(dict(issue))

    tasks = []
    for (stage, skill), items in sorted(grouped.items()):
        tasks.append(
            {
                "required_next_stage": stage,
                "required_next_skill": skill,
                "issue_count": len(items),
                "blocking": any(item.get("severity") in {"critical", "high"} for item in items),
                "issues": items,
            }
        )
    return {
        "schema_version": 1,
        "artifact_type": "r5_bundle11r_backflow_plan",
        "decision": "backflow_required" if tasks or unrouted else "no_backflow",
        "tasks": tasks,
        "unrouted_issues": unrouted,
    }
