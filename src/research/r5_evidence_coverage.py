"""R5 Bundle 8 evidence coverage matrix builder and validator.

The module is deliberately evidence-preserving.  It never discovers facts and
never turns an unreviewed clue into research support.  It only evaluates a
reviewed source catalog against explicit coverage requirements.
"""

from __future__ import annotations

import datetime as dt
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

import yaml


class CoverageError(ValueError):
    """Raised when a coverage input is structurally invalid."""


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise CoverageError(f"YAML root must be a mapping: {path}")
    return data


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple | set):
        return list(value)
    return [value]


def _strings(value: Any) -> list[str]:
    return [str(item).strip() for item in _as_list(value) if str(item).strip()]


def _parse_date(value: Any) -> dt.date | None:
    if value in (None, ""):
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _source_independence(source: dict[str, Any], policy: dict[str, Any]) -> str:
    explicit = str(source.get("independence", "")).strip().lower()
    if explicit in {"independent", "issuer", "unknown"}:
        return explicit
    owner_type = str(source.get("owner_type", "")).strip()
    if owner_type in set(_strings(policy.get("independent_owner_types"))):
        return "independent"
    if owner_type in set(_strings(policy.get("issuer_owner_types"))):
        return "issuer"
    return "unknown"


def normalize_source_catalog(
    source_catalog: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    """Normalize and validate source-catalog entries.

    ``underlying_source_id`` is the deduplication key. Multiple extracts, pages,
    or evidence cards from the same document therefore count once.
    """

    raw_sources = source_catalog.get("sources") or []
    if not isinstance(raw_sources, list):
        raise CoverageError("source catalog 'sources' must be a list")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_sources):
        if not isinstance(raw, dict):
            raise CoverageError(f"source catalog row {index} must be a mapping")
        source_id = str(raw.get("source_id", "")).strip()
        if not source_id:
            raise CoverageError(f"source catalog row {index} is missing source_id")
        if source_id in seen:
            raise CoverageError(f"duplicate source_id: {source_id}")
        seen.add(source_id)

        item = deepcopy(raw)
        item["source_id"] = source_id
        item["underlying_source_id"] = str(
            raw.get("underlying_source_id") or source_id
        ).strip()
        item["owner_type"] = str(raw.get("owner_type", "unknown")).strip()
        item["review_status"] = str(raw.get("review_status", "unknown")).strip()
        item["evidence_classes"] = sorted(set(_strings(raw.get("evidence_classes"))))
        item["sections"] = sorted(set(_strings(raw.get("sections"))))
        item["peer_ids"] = sorted(set(_strings(raw.get("peer_ids"))))
        peer_id = str(raw.get("peer_id") or raw.get("entity_id") or "").strip()
        if peer_id and item["owner_type"] == "peer_company":
            item["peer_ids"] = sorted(set(item["peer_ids"] + [peer_id]))
        item["counterevidence_for"] = sorted(
            set(_strings(raw.get("counterevidence_for")))
        )
        item["claim_ids"] = sorted(set(_strings(raw.get("claim_ids"))))
        item["metric_ids"] = sorted(set(_strings(raw.get("metric_ids"))))
        item["as_of_date"] = str(raw.get("as_of_date", "")).strip()
        item["independence"] = _source_independence(item, policy)
        normalized.append(item)
    return normalized


def _class_match(source_classes: set[str], requirement: dict[str, Any]) -> bool:
    required = set(_strings(requirement.get("required_evidence_classes")))
    if not required:
        return False
    mode = str(requirement.get("match_mode", "any")).lower()
    if mode == "all":
        return required.issubset(source_classes)
    if mode != "any":
        raise CoverageError(f"unsupported match_mode: {mode}")
    return bool(required & source_classes)


def _section_match(source: dict[str, Any], section: str) -> bool:
    source_sections = set(_strings(source.get("sections")))
    return not source_sections or section in source_sections or "all" in source_sections


def _reviewed(source: dict[str, Any], accepted: set[str]) -> bool:
    return str(source.get("review_status", "")) in accepted


def _freshness(
    source: dict[str, Any],
    as_of_date: dt.date,
    max_days: int | None,
) -> tuple[bool, int | None]:
    source_date = _parse_date(source.get("as_of_date"))
    if source_date is None:
        return False, None
    age = (as_of_date - source_date).days
    if age < 0:
        return False, age
    if max_days is None or max_days < 0:
        return True, age
    return age <= max_days, age


def _dedupe_underlying(sources: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in sources:
        key = str(source["underlying_source_id"])
        if key in seen:
            continue
        seen.add(key)
        result.append(source)
    return result


def _counterevidence_sources(
    sources: Iterable[dict[str, Any]],
    coverage_id: str,
    section: str,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for source in sources:
        targets = set(_strings(source.get("counterevidence_for")))
        classes = set(_strings(source.get("evidence_classes")))
        if (
            coverage_id in targets
            or section in targets
            or "all" in targets
            or "risk_counterevidence" in classes
        ):
            matches.append(source)
    return _dedupe_underlying(matches)


def _evaluate_requirement(
    requirement: dict[str, Any],
    sources: list[dict[str, Any]],
    policy: dict[str, Any],
    as_of_date: dt.date,
) -> dict[str, Any]:
    coverage_id = str(requirement.get("coverage_id", "")).strip()
    section = str(requirement.get("section", "")).strip()
    if not coverage_id or not section:
        raise CoverageError("each requirement needs coverage_id and section")

    accepted = set(_strings(policy.get("accepted_review_statuses")))
    max_days_raw = requirement.get("freshness_max_days")
    max_days = int(max_days_raw) if max_days_raw not in (None, "") else None

    class_matches = [
        source
        for source in sources
        if _class_match(set(source["evidence_classes"]), requirement)
        and _section_match(source, section)
    ]
    reviewed_matches = [source for source in class_matches if _reviewed(source, accepted)]

    fresh_matches: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for source in class_matches:
        fresh, age = _freshness(source, as_of_date, max_days)
        reviewed = _reviewed(source, accepted)
        if reviewed and fresh:
            fresh_matches.append(source)
        else:
            reasons: list[str] = []
            if not reviewed:
                reasons.append("not_reviewed")
            if not fresh:
                reasons.append("missing_or_stale_as_of_date")
            excluded.append(
                {
                    "source_id": source["source_id"],
                    "underlying_source_id": source["underlying_source_id"],
                    "age_days": age,
                    "reasons": reasons,
                }
            )

    valid_underlying = _dedupe_underlying(fresh_matches)
    independent = _dedupe_underlying(
        source for source in fresh_matches if source["independence"] == "independent"
    )
    issuer = _dedupe_underlying(
        source for source in fresh_matches if source["independence"] == "issuer"
    )

    peer_ids = sorted(
        {
            peer_id
            for source in fresh_matches
            for peer_id in _strings(source.get("peer_ids"))
        }
    )
    counter_sources = _counterevidence_sources(
        [
            source
            for source in sources
            if _reviewed(source, accepted)
            and _freshness(source, as_of_date, max_days)[0]
        ],
        coverage_id,
        section,
    )

    checks = {
        "underlying_source_minimum": len(valid_underlying)
        >= int(requirement.get("min_underlying_sources", 0)),
        "independent_source_minimum": len(independent)
        >= int(requirement.get("min_independent_sources", 0)),
        "peer_minimum": len(peer_ids) >= int(requirement.get("min_peer_count", 0)),
        "counterevidence_present": (
            not bool(requirement.get("requires_counterevidence"))
            or bool(counter_sources)
        ),
    }

    reasons: list[str] = []
    if not class_matches:
        reasons.append("source_class_gap")
    elif not reviewed_matches:
        reasons.append("no_reviewed_source")
    elif not fresh_matches:
        reasons.append("freshness_gap")
    if not checks["underlying_source_minimum"]:
        reasons.append("underlying_source_below_minimum")
    if not checks["independent_source_minimum"]:
        reasons.append("independent_source_below_minimum")
    if not checks["peer_minimum"]:
        reasons.append("credible_peer_below_minimum")
    if not checks["counterevidence_present"]:
        reasons.append("counterevidence_missing")

    covered = all(checks.values()) and bool(fresh_matches)
    if covered:
        status = "covered"
        evidence_state = "complete"
    elif fresh_matches:
        status = "blocked" if requirement.get("blocking", True) else "partial"
        evidence_state = "partial"
    else:
        status = "blocked" if requirement.get("blocking", True) else "missing"
        evidence_state = "missing"

    return {
        "coverage_id": coverage_id,
        "section": section,
        "research_question": str(requirement.get("research_question", "")).strip(),
        "blocking": bool(requirement.get("blocking", True)),
        "owner_skill": str(requirement.get("owner_skill", "")).strip(),
        "target_artifacts": _strings(requirement.get("target_artifacts")),
        "required_evidence_classes": _strings(
            requirement.get("required_evidence_classes")
        ),
        "requirements": {
            "min_underlying_sources": int(
                requirement.get("min_underlying_sources", 0)
            ),
            "min_independent_sources": int(
                requirement.get("min_independent_sources", 0)
            ),
            "min_peer_count": int(requirement.get("min_peer_count", 0)),
            "freshness_max_days": max_days,
            "requires_counterevidence": bool(
                requirement.get("requires_counterevidence")
            ),
        },
        "source_ids": sorted(source["source_id"] for source in fresh_matches),
        "underlying_source_ids": sorted(
            source["underlying_source_id"] for source in valid_underlying
        ),
        "independent_underlying_source_ids": sorted(
            source["underlying_source_id"] for source in independent
        ),
        "issuer_underlying_source_ids": sorted(
            source["underlying_source_id"] for source in issuer
        ),
        "peer_ids": peer_ids,
        "counterevidence_source_ids": sorted(
            source["source_id"] for source in counter_sources
        ),
        "checks": checks,
        "status": status,
        "evidence_state": evidence_state,
        "reason_codes": sorted(set(reasons)),
        "excluded_sources": excluded,
    }


def build_coverage_matrix(
    config: dict[str, Any],
    source_catalog: dict[str, Any],
    *,
    workflow_id: str | None = None,
    as_of_date: str | None = None,
    source_catalog_path: str | None = None,
) -> dict[str, Any]:
    policy = config.get("source_policy") or {}
    gate = config.get("coverage_gate") or {}
    requirements = gate.get("requirements") or []
    if not isinstance(requirements, list) or not requirements:
        raise CoverageError("coverage_gate.requirements must be a non-empty list")

    effective_as_of = (
        as_of_date
        or str(source_catalog.get("as_of_date") or "").strip()
        or dt.date.today().isoformat()
    )
    as_of = _parse_date(effective_as_of)
    if as_of is None:
        raise CoverageError(f"invalid as_of_date: {effective_as_of}")

    sources = normalize_source_catalog(source_catalog, policy)
    rows = [
        _evaluate_requirement(requirement, sources, policy, as_of)
        for requirement in requirements
    ]

    covered = [row for row in rows if row["status"] == "covered"]
    open_blockers = [
        row for row in rows if row["blocking"] and row["status"] != "covered"
    ]
    accepted = set(_strings(policy.get("accepted_review_statuses")))
    globally_valid_sources = [
        source
        for source in sources
        if _reviewed(source, accepted)
        and (_parse_date(source.get("as_of_date")) or dt.date.min) <= as_of
        and _parse_date(source.get("as_of_date")) is not None
    ]
    all_underlying = sorted(
        {source["underlying_source_id"] for source in globally_valid_sources}
    )
    independent_underlying = sorted(
        {
            source["underlying_source_id"]
            for source in globally_valid_sources
            if source["independence"] == "independent"
        }
    )

    min_covered = int(gate.get("min_covered_requirements", len(rows)))
    min_total = int(gate.get("min_total_underlying_sources", 0))
    min_independent = int(gate.get("min_total_independent_underlying_sources", 0))
    require_all = bool(gate.get("require_all_blocking_requirements_covered", True))
    decision_pass = (
        len(covered) >= min_covered
        and len(all_underlying) >= min_total
        and len(independent_underlying) >= min_independent
        and (not require_all or not open_blockers)
    )

    decision = str(
        gate.get(
            "decision_pass" if decision_pass else "decision_fail",
            "evidence_inputs_ready" if decision_pass else "evidence_inputs_blocked",
        )
    )
    return {
        "artifact_type": "R5_evidence_coverage_matrix",
        "schema_version": "v0.1",
        "bundle_id": str(config.get("bundle_id", "R5_BUNDLE_8_RESEARCH_DEPTH")),
        "workflow_id": workflow_id or str(source_catalog.get("workflow_id", "")),
        "as_of_date": as_of.isoformat(),
        "source_catalog_path": source_catalog_path or "",
        "requirements": rows,
        "summary": {
            "decision": decision,
            "covered_requirements": len(covered),
            "total_requirements": len(rows),
            "blocking_requirements_open": len(open_blockers),
            "blocking_coverage_ids": [row["coverage_id"] for row in open_blockers],
            "total_underlying_sources": len(all_underlying),
            "independent_underlying_sources": len(independent_underlying),
            "min_covered_requirements": min_covered,
            "min_total_underlying_sources": min_total,
            "min_total_independent_underlying_sources": min_independent,
        },
        "notes": [
            "Counts use underlying_source_id, so multiple extracts from one document count once.",
            "Only accepted review statuses and fresh sources contribute to a requirement.",
            "Issuer-only industry material cannot satisfy independent-source thresholds.",
        ],
    }


def validate_coverage_matrix(
    matrix: dict[str, Any],
    config: dict[str, Any],
    source_catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a matrix independently from the builder and fail closed.

    When the source catalog is supplied, the matrix must be exactly
    reproducible from that catalog. This prevents hand-edited counts or status
    fields from turning an incomplete evidence set into a passing artifact.
    """

    errors: list[str] = []
    warnings: list[str] = []
    rows = matrix.get("requirements") or []
    if matrix.get("artifact_type") != "R5_evidence_coverage_matrix":
        errors.append("artifact_type_mismatch")
    if not isinstance(rows, list) or not rows:
        errors.append("requirements_missing")
        rows = []

    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            errors.append("requirement_row_not_mapping")
            continue
        coverage_id = str(row.get("coverage_id", ""))
        if not coverage_id:
            errors.append("coverage_id_missing")
        elif coverage_id in seen:
            errors.append(f"duplicate_coverage_id:{coverage_id}")
        seen.add(coverage_id)
        if row.get("status") not in {"covered", "blocked", "partial", "missing"}:
            errors.append(f"invalid_status:{coverage_id}")
        checks = row.get("checks") or {}
        if row.get("status") == "covered" and not checks:
            errors.append(f"covered_without_checks:{coverage_id}")
        if row.get("status") == "covered" and not all(bool(v) for v in checks.values()):
            errors.append(f"covered_with_failed_check:{coverage_id}")
        underlying = _strings(row.get("underlying_source_ids"))
        independent = _strings(row.get("independent_underlying_source_ids"))
        if len(underlying) != len(set(underlying)):
            errors.append(f"duplicate_underlying_source:{coverage_id}")
        if not set(independent).issubset(set(underlying)):
            errors.append(f"independent_not_subset:{coverage_id}")
        requirements = row.get("requirements") or {}
        if row.get("status") == "covered":
            if len(underlying) < int(requirements.get("min_underlying_sources", 0)):
                errors.append(f"underlying_threshold_not_met:{coverage_id}")
            if len(independent) < int(requirements.get("min_independent_sources", 0)):
                errors.append(f"independent_threshold_not_met:{coverage_id}")
            if len(_strings(row.get("peer_ids"))) < int(
                requirements.get("min_peer_count", 0)
            ):
                errors.append(f"peer_threshold_not_met:{coverage_id}")
            if requirements.get("requires_counterevidence") and not _strings(
                row.get("counterevidence_source_ids")
            ):
                errors.append(f"counterevidence_missing:{coverage_id}")

    gate = config.get("coverage_gate") or {}
    covered_count = sum(row.get("status") == "covered" for row in rows if isinstance(row, dict))
    blockers = [
        row
        for row in rows
        if isinstance(row, dict)
        and row.get("blocking")
        and row.get("status") != "covered"
    ]
    summary = matrix.get("summary") or {}
    if summary.get("covered_requirements") != covered_count:
        errors.append("summary_covered_count_mismatch")
    if summary.get("blocking_requirements_open") != len(blockers):
        errors.append("summary_blocker_count_mismatch")

    expected_pass = (
        covered_count >= int(gate.get("min_covered_requirements", len(rows)))
        and int(summary.get("total_underlying_sources", 0))
        >= int(gate.get("min_total_underlying_sources", 0))
        and int(summary.get("independent_underlying_sources", 0))
        >= int(gate.get("min_total_independent_underlying_sources", 0))
        and (
            not gate.get("require_all_blocking_requirements_covered", True)
            or not blockers
        )
    )
    expected_decision = gate.get(
        "decision_pass" if expected_pass else "decision_fail",
        "evidence_inputs_ready" if expected_pass else "evidence_inputs_blocked",
    )
    if summary.get("decision") != expected_decision:
        errors.append("summary_decision_mismatch")

    if source_catalog is not None:
        try:
            expected = build_coverage_matrix(
                config,
                source_catalog,
                workflow_id=str(matrix.get("workflow_id", "")),
                as_of_date=str(matrix.get("as_of_date", "")),
                source_catalog_path=str(matrix.get("source_catalog_path", "")),
            )
        except CoverageError as exc:
            errors.append(f"source_catalog_rebuild_failed:{exc}")
        else:
            if expected.get("requirements") != matrix.get("requirements"):
                errors.append("matrix_requirements_not_reproducible")
            if expected.get("summary") != matrix.get("summary"):
                errors.append("matrix_summary_not_reproducible")

    if not matrix.get("source_catalog_path"):
        warnings.append("source_catalog_path_empty")

    return {
        "gate_id": "R5_BUNDLE8_EVIDENCE_COVERAGE_GATE",
        "decision": "pass" if not errors and expected_pass else "fail",
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "stats": {
            "covered_requirements": covered_count,
            "total_requirements": len(rows),
            "open_blockers": len(blockers),
        },
    }


def build_evidence_packs(
    source_catalog: dict[str, Any],
    matrix: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Create source-only handoff packs without synthesizing new facts."""

    sources = normalize_source_catalog(source_catalog, config.get("source_policy") or {})
    coverage_lookup: dict[str, list[str]] = {}
    for row in matrix.get("requirements") or []:
        for source_id in _strings(row.get("source_ids")):
            coverage_lookup.setdefault(source_id, []).append(str(row.get("coverage_id")))

    def pack(name: str, predicate: Any) -> dict[str, Any]:
        selected: list[dict[str, Any]] = []
        for source in sources:
            if source["source_id"] not in coverage_lookup:
                continue
            if not predicate(source):
                continue
            item = deepcopy(source)
            item["coverage_ids"] = sorted(coverage_lookup.get(source["source_id"], []))
            selected.append(item)
        return {
            "artifact_type": name,
            "schema_version": "v0.1",
            "workflow_id": matrix.get("workflow_id", ""),
            "as_of_date": matrix.get("as_of_date", ""),
            "sources": selected,
            "source_count": len(selected),
            "underlying_source_count": len(
                {item["underlying_source_id"] for item in selected}
            ),
            "notes": [
                "This pack is a reviewed-source handoff, not a narrative conclusion.",
                "Missing fields remain explicit and must not be inferred from absence.",
            ],
        }

    return {
        "industry_evidence_pack": pack(
            "R5_industry_evidence_pack",
            lambda source: bool(
                set(source["evidence_classes"])
                & {"industry_demand", "industry_supply_competition"}
            ),
        ),
        "peer_operating_pack": pack(
            "R5_peer_operating_pack",
            lambda source: "peer_operating" in set(source["evidence_classes"]),
        ),
        "company_operating_evidence_pack": pack(
            "R5_company_operating_evidence_pack",
            lambda source: bool(
                set(source["evidence_classes"])
                & {
                    "issuer_financial",
                    "issuer_business_disclosure",
                    "company_operating",
                }
            ),
        ),
    }
