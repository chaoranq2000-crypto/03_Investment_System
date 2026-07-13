from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import yaml

ALLOWED_DECISIONS = {"adopt_core", "adopt_enhancement", "adapt_clue_only", "defer_out_of_scope"}
READY_IMPLEMENTATION_STATUSES = {
    "operational_verified",
    "approved_independent_alternative",
}


def load_catalog(path: str | Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("capability catalog root must be a mapping")
    return payload


def validate_catalog(catalog: Mapping[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    caps = catalog.get("capabilities")
    if not isinstance(caps, list):
        return [{"issue_id": "CAPABILITY_LIST_INVALID", "severity": "critical", "message": "capabilities must be a list"}]
    ids: list[str] = []
    primary = 0
    fallback = 0
    for index, item in enumerate(caps):
        if not isinstance(item, Mapping):
            issues.append({"issue_id": "CAPABILITY_RECORD_INVALID", "severity": "high", "message": f"record {index} is not a mapping"})
            continue
        cap_id = str(item.get("capability_id", ""))
        ids.append(cap_id)
        layer = item.get("upstream_layer")
        if layer == "fallback":
            fallback += 1
        else:
            primary += 1
        decision = str(item.get("adoption_decision", ""))
        if decision not in ALLOWED_DECISIONS:
            issues.append({"issue_id": "ADOPTION_DECISION_INVALID", "severity": "high", "capability_id": cap_id, "message": decision})
        required = bool(item.get("required_for_bundle8r_close", False))
        if required and decision != "adopt_core":
            issues.append({"issue_id": "CLOSE_REQUIREMENT_DECISION_MISMATCH", "severity": "high", "capability_id": cap_id, "message": "only adopt_core may block Bundle 8R close"})
        if not item.get("claim_boundary"):
            issues.append({"issue_id": "CLAIM_BOUNDARY_MISSING", "severity": "high", "capability_id": cap_id, "message": "claim boundary is required"})
        if decision != "defer_out_of_scope" and not item.get("target_adapter"):
            issues.append({"issue_id": "TARGET_ADAPTER_MISSING", "severity": "medium", "capability_id": cap_id, "message": "adopted capability needs a target adapter"})
        status = str(item.get("current_implementation_status", ""))
        if required and status in READY_IMPLEMENTATION_STATUSES:
            resolution = item.get("operational_resolution")
            if not isinstance(resolution, Mapping):
                issues.append({"issue_id": "OPERATIONAL_RESOLUTION_MISSING", "severity": "high", "capability_id": cap_id, "message": "ready core capability requires operational_resolution"})
            else:
                proof_paths = resolution.get("proof_paths")
                if not isinstance(proof_paths, list) or not proof_paths:
                    issues.append({"issue_id": "CAPABILITY_PROOF_PATH_MISSING", "severity": "high", "capability_id": cap_id, "message": "ready core capability requires proof_paths"})
                if status == "approved_independent_alternative":
                    alternatives = resolution.get("approved_alternatives")
                    if not isinstance(alternatives, list) or not alternatives:
                        issues.append({"issue_id": "INDEPENDENT_ALTERNATIVE_MISSING", "severity": "high", "capability_id": cap_id, "message": "alternative resolution requires approved_alternatives"})
    duplicates = sorted({item for item in ids if item and ids.count(item) > 1})
    for cap_id in duplicates:
        issues.append({"issue_id": "CAPABILITY_ID_DUPLICATE", "severity": "critical", "capability_id": cap_id, "message": "duplicate ID"})
    upstream = catalog.get("upstream", {})
    declared_primary = int(upstream.get("declared_primary_endpoint_groups", -1)) if isinstance(upstream, Mapping) else -1
    declared_fallback = int(upstream.get("declared_official_fallback_groups", -1)) if isinstance(upstream, Mapping) else -1
    if primary != declared_primary or fallback != declared_fallback:
        issues.append({"issue_id": "UPSTREAM_COUNT_MISMATCH", "severity": "critical", "message": f"primary={primary}/{declared_primary}, fallback={fallback}/{declared_fallback}"})
    if len(caps) != 43:
        issues.append({"issue_id": "TOTAL_CAPABILITY_COUNT_MISMATCH", "severity": "critical", "message": f"found {len(caps)}, expected 43"})
    return issues


def build_coverage_report(catalog: Mapping[str, Any]) -> dict[str, Any]:
    issues = validate_catalog(catalog)
    caps = [item for item in catalog.get("capabilities", []) if isinstance(item, Mapping)]
    decision_counts = Counter(str(item.get("adoption_decision", "")) for item in caps)
    status_counts = Counter(str(item.get("current_implementation_status", "")) for item in caps)
    core = [item for item in caps if bool(item.get("required_for_bundle8r_close", False))]
    core_ready = [item for item in core if str(item.get("current_implementation_status")) in READY_IMPLEMENTATION_STATUSES]
    core_blockers = [
        {
            "capability_id": item.get("capability_id"),
            "current_implementation_status": item.get("current_implementation_status"),
            "target_adapter": item.get("target_adapter"),
        }
        for item in core
        if str(item.get("current_implementation_status")) not in READY_IMPLEMENTATION_STATUSES
    ]
    blocking_schema = [item for item in issues if item.get("severity") in {"critical", "high"}]
    decision = "pass" if not blocking_schema and not core_blockers else "needs_fix"
    return {
        "schema_version": 1,
        "decision": decision,
        "mode": "forward_requalification_not_rollback",
        "capability_count": len(caps),
        "primary_capability_count": sum(item.get("upstream_layer") != "fallback" for item in caps),
        "fallback_capability_count": sum(item.get("upstream_layer") == "fallback" for item in caps),
        "decision_counts": dict(sorted(decision_counts.items())),
        "implementation_status_counts": dict(sorted(status_counts.items())),
        "bundle8r_core_count": len(core),
        "bundle8r_core_operational_count": len(core_ready),
        "bundle8r_core_direct_operational_count": sum(
            str(item.get("current_implementation_status")) == "operational_verified"
            for item in core
        ),
        "bundle8r_core_alternative_count": sum(
            str(item.get("current_implementation_status")) == "approved_independent_alternative"
            for item in core
        ),
        "bundle8r_core_blocker_count": len(core_blockers),
        "bundle8r_core_blockers": core_blockers,
        "catalog_issues": issues,
    }
