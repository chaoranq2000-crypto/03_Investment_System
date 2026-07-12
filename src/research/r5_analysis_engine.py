"""R5 Bundle 8 structured analysis engine.

The engine validates analyst-authored reasoning units against reviewed evidence.
It does not write conclusions from scratch.  A unit can become ``complete`` only
when judgment, trend, mechanism, financial impact, counter-evidence,
falsification condition, and watch metrics form a traceable closed loop.
"""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

import yaml

from src.research.r5_evidence_coverage import (
    CoverageError,
    normalize_source_catalog,
)


class AnalysisError(ValueError):
    """Raised when analysis input or output is structurally invalid."""


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise AnalysisError(f"YAML root must be a mapping: {path}")
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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _compact(value: str) -> str:
    return re.sub(r"[\s，。；：、,.!?！？:;()（）\-—_]+", "", value).lower()


def _contains_missing_marker(text: str, markers: Iterable[str]) -> str | None:
    upper = text.upper()
    for marker in markers:
        marker_text = str(marker).strip()
        if marker_text and marker_text.upper() in upper:
            return marker_text
    return None


def _is_generic(text: str, phrases: Iterable[str]) -> str | None:
    compact = _compact(text)
    for phrase in phrases:
        phrase_compact = _compact(str(phrase))
        if not phrase_compact:
            continue
        if compact == phrase_compact:
            return str(phrase)
        if phrase_compact in compact and len(compact) <= len(phrase_compact) + 12:
            return str(phrase)
    return None


def _source_lookup(
    source_catalog: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    try:
        sources = normalize_source_catalog(
            source_catalog,
            config.get("source_policy") or {},
        )
    except CoverageError as exc:
        raise AnalysisError(str(exc)) from exc
    return {source["source_id"]: source for source in sources}


def _accepted_source_ids(
    lookup: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> set[str]:
    accepted = set(
        _strings((config.get("source_policy") or {}).get("accepted_review_statuses"))
    )
    return {
        source_id
        for source_id, source in lookup.items()
        if str(source.get("review_status", "")) in accepted
    }


def _known_metric_ids(lookup: dict[str, dict[str, Any]]) -> set[str]:
    return {
        metric_id
        for source in lookup.values()
        for metric_id in _strings(source.get("metric_ids"))
    }


def _validate_watch_metrics(
    unit_id: str,
    watch_metrics: Any,
    source_lookup: dict[str, dict[str, Any]],
    known_metrics: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    normalized: list[dict[str, Any]] = []
    if not isinstance(watch_metrics, list):
        return [], [f"watch_metrics_not_list:{unit_id}"]

    for index, raw in enumerate(watch_metrics):
        prefix = f"{unit_id}:watch_metric:{index}"
        if not isinstance(raw, dict):
            errors.append(f"watch_metric_not_mapping:{prefix}")
            continue
        item = deepcopy(raw)
        name = _text(raw.get("metric_name"))
        direction = _text(raw.get("expected_direction"))
        threshold = _text(raw.get("threshold"))
        frequency = _text(raw.get("review_frequency"))
        metric_id = _text(raw.get("metric_id"))
        source_id = _text(raw.get("source_id"))
        if not name:
            errors.append(f"watch_metric_name_missing:{prefix}")
        if not direction and not threshold:
            errors.append(f"watch_metric_trigger_missing:{prefix}")
        if not frequency:
            errors.append(f"watch_metric_frequency_missing:{prefix}")
        if not metric_id and not source_id:
            errors.append(f"watch_metric_reference_missing:{prefix}")
        if metric_id and metric_id not in known_metrics:
            errors.append(f"watch_metric_unknown_metric:{prefix}:{metric_id}")
        if source_id and source_id not in source_lookup:
            errors.append(f"watch_metric_unknown_source:{prefix}:{source_id}")
        item["metric_name"] = name
        item["expected_direction"] = direction
        item["threshold"] = threshold
        item["review_frequency"] = frequency
        item["metric_id"] = metric_id
        item["source_id"] = source_id
        normalized.append(item)
    return normalized, errors


def _validate_dependencies(units: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    unit_ids = {str(unit.get("analysis_id", "")) for unit in units}
    graph: dict[str, list[str]] = {}
    for unit in units:
        unit_id = str(unit.get("analysis_id", ""))
        deps = _strings(unit.get("dependencies"))
        graph[unit_id] = deps
        for dep in deps:
            if dep not in unit_ids:
                errors.append(f"unknown_dependency:{unit_id}:{dep}")
            if dep == unit_id:
                errors.append(f"self_dependency:{unit_id}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visited or node not in graph:
            return
        if node in visiting:
            errors.append(f"dependency_cycle:{node}")
            return
        visiting.add(node)
        for child in graph[node]:
            visit(child)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)
    return errors


def _coverage_sections(matrix: dict[str, Any]) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for row in matrix.get("requirements") or []:
        if not isinstance(row, dict):
            continue
        section = _text(row.get("section"))
        covered = row.get("status") == "covered"
        result[section] = result.get(section, True) and covered
    return result


def _coverage_source_ids(matrix: dict[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for row in matrix.get("requirements") or []:
        if not isinstance(row, dict) or row.get("status") != "covered":
            continue
        section = _text(row.get("section"))
        result.setdefault(section, set()).update(_strings(row.get("source_ids")))
        result[section].update(_strings(row.get("counterevidence_source_ids")))
    return result


def _analysis_coverage_sections(section: str) -> list[str]:
    return {
        "core_thesis": ["business_driver", "risk_counterevidence"],
        "financial_quality": ["financial_quality", "risk_counterevidence"],
        "business_driver": ["business_driver", "risk_counterevidence"],
        "segment_economics": ["business_breakdown", "risk_counterevidence"],
        "industry_context": ["industry_context", "risk_counterevidence"],
        "competitive_position": [
            "competitive_position",
            "industry_context",
            "risk_counterevidence",
        ],
        "risk_counterevidence": ["risk_counterevidence"],
        "catalyst_watchpoints": [],
    }.get(section, [section])


def _unit_section_coverage_ok(section: str, coverage: dict[str, bool]) -> bool:
    mapping = {
        "core_thesis": ["business_driver", "risk_counterevidence"],
        "financial_quality": ["financial_quality"],
        "business_driver": ["business_driver"],
        "segment_economics": ["business_breakdown"],
        "industry_context": ["industry_context"],
        "competitive_position": ["competitive_position"],
        "risk_counterevidence": ["risk_counterevidence"],
        "catalyst_watchpoints": [],
    }
    required = mapping.get(section, [section])
    return all(coverage.get(item, False) for item in required)


def _evaluate_unit(
    raw: dict[str, Any],
    *,
    config: dict[str, Any],
    source_lookup: dict[str, dict[str, Any]],
    accepted_source_ids: set[str],
    known_metrics: set[str],
    coverage: dict[str, bool],
    coverage_sources: dict[str, set[str]],
    covered_source_ids: set[str],
) -> dict[str, Any]:
    gate = config.get("analysis_gate") or {}
    policy = config.get("source_policy") or {}
    unit = deepcopy(raw)
    unit_id = _text(raw.get("analysis_id"))
    section = _text(raw.get("section"))
    blockers: list[str] = []
    warnings: list[str] = []
    if not unit_id:
        blockers.append("analysis_id_missing")
    if not section:
        blockers.append(f"section_missing:{unit_id or 'unknown'}")

    required_sections = set(_strings(gate.get("required_sections")))
    optional_sections = set(_strings(gate.get("optional_sections")))
    if section and section not in required_sections | optional_sections:
        blockers.append(f"unsupported_section:{unit_id}:{section}")

    required_fields = _strings(gate.get("required_fields"))
    text_min = gate.get("text_min_chars") or {}
    missing_markers = _strings(policy.get("missing_markers"))
    generic_phrases = _strings(policy.get("generic_analysis_phrases"))
    normalized_text: dict[str, str] = {}

    for field in required_fields:
        if field in {
            "supporting_source_ids",
            "counter_evidence_source_ids",
            "watch_metrics",
        }:
            continue
        text = _text(raw.get(field))
        normalized_text[field] = text
        if not text:
            blockers.append(f"required_field_missing:{unit_id}:{field}")
            continue
        minimum = int(text_min.get(field, 1))
        if len(_compact(text)) < minimum:
            blockers.append(f"text_below_minimum:{unit_id}:{field}:{minimum}")
        marker = _contains_missing_marker(text, missing_markers)
        if marker and gate.get("reject_missing_markers_in_complete_units", True):
            blockers.append(f"missing_marker_in_unit:{unit_id}:{field}:{marker}")
        generic = _is_generic(text, generic_phrases)
        if generic:
            blockers.append(f"generic_analysis_text:{unit_id}:{field}:{generic}")

    judgment = normalized_text.get("judgment", _text(raw.get("judgment")))
    mechanism = normalized_text.get(
        "causal_mechanism", _text(raw.get("causal_mechanism"))
    )
    impact = normalized_text.get("financial_impact", _text(raw.get("financial_impact")))
    if judgment and mechanism and _compact(judgment) == _compact(mechanism):
        blockers.append(f"judgment_equals_mechanism:{unit_id}")
    if mechanism and impact and _compact(mechanism) == _compact(impact):
        blockers.append(f"mechanism_equals_financial_impact:{unit_id}")

    support_ids = sorted(set(_strings(raw.get("supporting_source_ids"))))
    counter_ids = sorted(set(_strings(raw.get("counter_evidence_source_ids"))))
    metric_ids = sorted(set(_strings(raw.get("supporting_metric_ids"))))
    min_support = int(gate.get("min_supporting_sources_per_unit", 1))
    min_counter = int(gate.get("min_counterevidence_sources_per_unit", 1))
    if len(support_ids) < min_support:
        blockers.append(f"supporting_source_below_minimum:{unit_id}")
    if len(counter_ids) < min_counter:
        blockers.append(f"counterevidence_source_below_minimum:{unit_id}")

    for source_id in support_ids:
        if source_id not in source_lookup:
            blockers.append(f"unknown_supporting_source:{unit_id}:{source_id}")
        elif source_id not in accepted_source_ids:
            blockers.append(f"unreviewed_supporting_source:{unit_id}:{source_id}")
        elif source_id not in covered_source_ids:
            blockers.append(f"supporting_source_not_coverage_valid:{unit_id}:{source_id}")
    for source_id in counter_ids:
        if source_id not in source_lookup:
            blockers.append(f"unknown_counterevidence_source:{unit_id}:{source_id}")
        elif source_id not in accepted_source_ids:
            blockers.append(f"unreviewed_counterevidence_source:{unit_id}:{source_id}")
        elif source_id not in covered_source_ids:
            blockers.append(
                f"counterevidence_source_not_coverage_valid:{unit_id}:{source_id}"
            )

    if section in set(_strings(gate.get("metric_required_sections"))):
        if not metric_ids:
            blockers.append(f"supporting_metric_missing:{unit_id}:{section}")
        for metric_id in metric_ids:
            if metric_id not in known_metrics:
                blockers.append(f"unknown_supporting_metric:{unit_id}:{metric_id}")

    referenced_sources = [
        source_lookup[source_id]
        for source_id in support_ids + counter_ids
        if source_id in source_lookup and source_id in accepted_source_ids
    ]
    if section in set(_strings(gate.get("independent_source_required_sections"))):
        if not any(source.get("independence") == "independent" for source in referenced_sources):
            blockers.append(f"independent_source_missing:{unit_id}:{section}")
    if section in set(_strings(gate.get("issuer_source_required_sections"))):
        if not any(source.get("independence") == "issuer" for source in referenced_sources):
            blockers.append(f"issuer_source_missing:{unit_id}:{section}")

    allowed_confidence = set(_strings(gate.get("allowed_confidence")))
    confidence = _text(raw.get("confidence"))
    if confidence not in allowed_confidence:
        blockers.append(f"invalid_confidence:{unit_id}:{confidence or 'missing'}")

    watch_metrics, watch_errors = _validate_watch_metrics(
        unit_id,
        raw.get("watch_metrics"),
        source_lookup,
        known_metrics,
    )
    blockers.extend(watch_errors)
    if len(watch_metrics) < int(gate.get("min_watch_metrics_per_unit", 1)):
        blockers.append(f"watch_metric_below_minimum:{unit_id}")

    if section and not _unit_section_coverage_ok(section, coverage):
        blockers.append(f"evidence_coverage_not_ready:{unit_id}:{section}")
    relevant_source_ids: set[str] = set()
    for coverage_section in _analysis_coverage_sections(section):
        relevant_source_ids.update(coverage_sources.get(coverage_section, set()))
    if relevant_source_ids and not (set(support_ids) & relevant_source_ids):
        blockers.append(f"supporting_source_not_in_covered_evidence:{unit_id}:{section}")
    if relevant_source_ids and not (set(counter_ids) & relevant_source_ids):
        blockers.append(f"counterevidence_not_in_covered_evidence:{unit_id}:{section}")

    unit.update(normalized_text)
    unit["analysis_id"] = unit_id
    unit["section"] = section
    unit["supporting_source_ids"] = support_ids
    unit["supporting_metric_ids"] = metric_ids
    unit["counter_evidence_source_ids"] = counter_ids
    unit["confidence"] = confidence
    unit["watch_metrics"] = watch_metrics
    unit["dependencies"] = sorted(set(_strings(raw.get("dependencies"))))
    unit["blockers"] = sorted(set(blockers))
    unit["warnings"] = sorted(set(warnings))
    unit["status"] = "complete" if not blockers else "blocked"
    return unit


def build_analysis_pack(
    config: dict[str, Any],
    source_catalog: dict[str, Any],
    coverage_matrix: dict[str, Any],
    analysis_inputs: dict[str, Any],
    *,
    source_catalog_path: str = "",
    coverage_matrix_path: str = "",
    analysis_inputs_path: str = "",
) -> dict[str, Any]:
    gate = config.get("analysis_gate") or {}
    raw_units = analysis_inputs.get("units") or []
    if not isinstance(raw_units, list):
        raise AnalysisError("analysis inputs 'units' must be a list")

    lookup = _source_lookup(source_catalog, config)
    accepted = _accepted_source_ids(lookup, config)
    known_metrics = _known_metric_ids(lookup)
    coverage = _coverage_sections(coverage_matrix)
    coverage_sources = _coverage_source_ids(coverage_matrix)
    covered_source_ids = {
        source_id
        for source_ids in coverage_sources.values()
        for source_id in source_ids
    }

    units: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    pack_blockers: list[str] = []
    for index, raw in enumerate(raw_units):
        if not isinstance(raw, dict):
            pack_blockers.append(f"analysis_unit_not_mapping:{index}")
            continue
        unit = _evaluate_unit(
            raw,
            config=config,
            source_lookup=lookup,
            accepted_source_ids=accepted,
            known_metrics=known_metrics,
            coverage=coverage,
            coverage_sources=coverage_sources,
            covered_source_ids=covered_source_ids,
        )
        unit_id = unit.get("analysis_id", "")
        if unit_id in seen_ids:
            unit["blockers"] = sorted(
                set(unit["blockers"] + [f"duplicate_analysis_id:{unit_id}"])
            )
            unit["status"] = "blocked"
        seen_ids.add(unit_id)
        units.append(unit)

    if gate.get("reject_duplicate_core_text", True):
        for field in ("judgment", "causal_mechanism", "financial_impact"):
            seen_text: dict[str, str] = {}
            for unit in units:
                compact = _compact(_text(unit.get(field)))
                if not compact:
                    continue
                prior_id = seen_text.get(compact)
                if prior_id:
                    blocker = f"duplicate_core_text:{field}:{prior_id}"
                    unit["blockers"] = sorted(set(unit["blockers"] + [blocker]))
                    unit["status"] = "blocked"
                else:
                    seen_text[compact] = str(unit.get("analysis_id"))

    dependency_errors = _validate_dependencies(units)
    pack_blockers.extend(dependency_errors)
    if dependency_errors:
        affected = {error.split(":")[1] for error in dependency_errors if ":" in error}
        for unit in units:
            if unit.get("analysis_id") in affected:
                unit["blockers"] = sorted(
                    set(unit["blockers"] + dependency_errors)
                )
                unit["status"] = "blocked"

    complete = [unit for unit in units if unit.get("status") == "complete"]
    blocked_units = [unit for unit in units if unit.get("status") == "blocked"]
    if blocked_units:
        pack_blockers.append(
            "blocked_analysis_units:"
            + ",".join(str(unit.get("analysis_id")) for unit in blocked_units)
        )
    complete_sections = {str(unit.get("section")) for unit in complete}
    required_sections = set(_strings(gate.get("required_sections")))
    missing_sections = sorted(required_sections - complete_sections)
    min_complete = int(gate.get("min_complete_units", len(required_sections)))
    if len(complete) < min_complete:
        pack_blockers.append(
            f"complete_unit_below_minimum:{len(complete)}:{min_complete}"
        )
    for section in missing_sections:
        pack_blockers.append(f"required_section_incomplete:{section}")

    evidence_ready = (
        (coverage_matrix.get("summary") or {}).get("decision")
        == (config.get("coverage_gate") or {}).get(
            "decision_pass", "evidence_inputs_ready"
        )
    )
    if not evidence_ready:
        pack_blockers.append("evidence_coverage_gate_not_passed")

    decision_pass = not pack_blockers and len(complete) >= min_complete and not missing_sections
    decision = gate.get(
        "decision_pass" if decision_pass else "decision_fail",
        "analysis_inputs_ready" if decision_pass else "analysis_inputs_blocked",
    )
    return {
        "artifact_type": "R5_analysis_pack_v2",
        "schema_version": "v0.1",
        "bundle_id": str(config.get("bundle_id", "R5_BUNDLE_8_RESEARCH_DEPTH")),
        "workflow_id": str(
            analysis_inputs.get("workflow_id")
            or coverage_matrix.get("workflow_id")
            or source_catalog.get("workflow_id")
            or ""
        ),
        "company_id": str(analysis_inputs.get("company_id", "")),
        "analysis_date": str(
            analysis_inputs.get("analysis_date")
            or coverage_matrix.get("as_of_date")
            or ""
        ),
        "source_catalog_path": source_catalog_path,
        "coverage_matrix_path": coverage_matrix_path,
        "analysis_inputs_path": analysis_inputs_path,
        "analysis_units": units,
        "summary": {
            "decision": decision,
            "complete_units": len(complete),
            "total_units": len(units),
            "required_complete_units": min_complete,
            "complete_sections": sorted(complete_sections),
            "missing_required_sections": missing_sections,
            "blocker_count": len(set(pack_blockers))
            + sum(len(unit.get("blockers") or []) for unit in units),
            "pack_blockers": sorted(set(pack_blockers)),
        },
        "notes": [
            "The engine validates analyst-authored reasoning; it does not invent facts.",
            "A complete unit needs evidence, mechanism, counter-evidence, "
            "falsification, and watch metrics.",
            "Incomplete evidence coverage blocks dependent analysis sections.",
        ],
    }


def validate_analysis_pack(
    pack: dict[str, Any],
    config: dict[str, Any],
    source_catalog: dict[str, Any] | None = None,
    coverage_matrix: dict[str, Any] | None = None,
    analysis_inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if pack.get("artifact_type") != "R5_analysis_pack_v2":
        errors.append("artifact_type_mismatch")
    units = pack.get("analysis_units") or []
    if not isinstance(units, list):
        errors.append("analysis_units_not_list")
        units = []

    seen: set[str] = set()
    complete_units = 0
    complete_sections: set[str] = set()
    for unit in units:
        if not isinstance(unit, dict):
            errors.append("analysis_unit_not_mapping")
            continue
        unit_id = _text(unit.get("analysis_id"))
        if not unit_id:
            errors.append("analysis_id_missing")
        elif unit_id in seen:
            errors.append(f"duplicate_analysis_id:{unit_id}")
        seen.add(unit_id)
        blockers = _strings(unit.get("blockers"))
        status = unit.get("status")
        if status not in {"complete", "blocked"}:
            errors.append(f"invalid_unit_status:{unit_id}")
        if status == "complete" and blockers:
            errors.append(f"complete_unit_has_blockers:{unit_id}")
        if status == "blocked" and not blockers:
            errors.append(f"blocked_unit_without_blocker:{unit_id}")
        if status == "complete":
            complete_units += 1
            complete_sections.add(_text(unit.get("section")))

    gate = config.get("analysis_gate") or {}
    policy = config.get("source_policy") or {}
    required_fields = _strings(gate.get("required_fields"))
    text_min = gate.get("text_min_chars") or {}
    missing_markers = _strings(policy.get("missing_markers"))
    generic_phrases = _strings(policy.get("generic_analysis_phrases"))
    complete_text_seen: dict[str, dict[str, str]] = {
        "judgment": {},
        "causal_mechanism": {},
        "financial_impact": {},
    }
    for unit in units:
        if not isinstance(unit, dict) or unit.get("status") != "complete":
            continue
        unit_id = _text(unit.get("analysis_id"))
        for field in required_fields:
            if field in {
                "supporting_source_ids",
                "counter_evidence_source_ids",
                "watch_metrics",
            }:
                continue
            value = _text(unit.get(field))
            if not value:
                errors.append(f"complete_required_field_missing:{unit_id}:{field}")
                continue
            minimum = int(text_min.get(field, 1))
            if len(_compact(value)) < minimum:
                errors.append(f"complete_text_below_minimum:{unit_id}:{field}")
            marker = _contains_missing_marker(value, missing_markers)
            if marker:
                errors.append(f"complete_missing_marker:{unit_id}:{field}:{marker}")
            generic = _is_generic(value, generic_phrases)
            if generic:
                errors.append(f"complete_generic_text:{unit_id}:{field}:{generic}")

        support_ids = _strings(unit.get("supporting_source_ids"))
        counter_ids = _strings(unit.get("counter_evidence_source_ids"))
        if len(set(support_ids)) < int(gate.get("min_supporting_sources_per_unit", 1)):
            errors.append(f"complete_support_below_minimum:{unit_id}")
        if len(set(counter_ids)) < int(gate.get("min_counterevidence_sources_per_unit", 1)):
            errors.append(f"complete_counterevidence_below_minimum:{unit_id}")
        confidence = _text(unit.get("confidence"))
        if confidence not in set(_strings(gate.get("allowed_confidence"))):
            errors.append(f"complete_invalid_confidence:{unit_id}:{confidence or 'missing'}")
        watch_metrics = unit.get("watch_metrics")
        if not isinstance(watch_metrics, list):
            errors.append(f"complete_watch_metrics_not_list:{unit_id}")
        elif len(watch_metrics) < int(gate.get("min_watch_metrics_per_unit", 1)):
            errors.append(f"complete_watch_metrics_below_minimum:{unit_id}")
        else:
            for index, watch in enumerate(watch_metrics):
                if not isinstance(watch, dict):
                    errors.append(f"complete_watch_metric_not_mapping:{unit_id}:{index}")
                    continue
                if not _text(watch.get("metric_name")):
                    errors.append(f"complete_watch_metric_name_missing:{unit_id}:{index}")
                if not (
                    _text(watch.get("expected_direction"))
                    or _text(watch.get("threshold"))
                ):
                    errors.append(f"complete_watch_metric_trigger_missing:{unit_id}:{index}")
                if not _text(watch.get("review_frequency")):
                    errors.append(f"complete_watch_metric_frequency_missing:{unit_id}:{index}")
                if not (
                    _text(watch.get("metric_id"))
                    or _text(watch.get("source_id"))
                ):
                    errors.append(f"complete_watch_metric_reference_missing:{unit_id}:{index}")

        for field, seen_text in complete_text_seen.items():
            compact = _compact(_text(unit.get(field)))
            if not compact:
                continue
            prior_id = seen_text.get(compact)
            if prior_id:
                errors.append(f"complete_duplicate_core_text:{field}:{prior_id}:{unit_id}")
            else:
                seen_text[compact] = unit_id

    required_sections = set(_strings(gate.get("required_sections")))
    missing_sections = sorted(required_sections - complete_sections)
    min_complete = int(gate.get("min_complete_units", len(required_sections)))
    summary = pack.get("summary") or {}
    pack_blockers = _strings(summary.get("pack_blockers"))
    expected_pass = (
        complete_units >= min_complete
        and not missing_sections
        and not pack_blockers
    )
    if summary.get("complete_units") != complete_units:
        errors.append("summary_complete_count_mismatch")
    if sorted(_strings(summary.get("missing_required_sections"))) != missing_sections:
        errors.append("summary_missing_sections_mismatch")
    expected_decision = gate.get(
        "decision_pass" if expected_pass else "decision_fail",
        "analysis_inputs_ready" if expected_pass else "analysis_inputs_blocked",
    )
    if summary.get("decision") != expected_decision:
        errors.append("summary_decision_mismatch")

    rebuild_inputs = (source_catalog, coverage_matrix, analysis_inputs)
    if any(item is not None for item in rebuild_inputs):
        if not all(item is not None for item in rebuild_inputs):
            errors.append("analysis_rebuild_inputs_incomplete")
        else:
            try:
                expected = build_analysis_pack(
                    config,
                    source_catalog or {},
                    coverage_matrix or {},
                    analysis_inputs or {},
                    source_catalog_path=str(pack.get("source_catalog_path", "")),
                    coverage_matrix_path=str(pack.get("coverage_matrix_path", "")),
                    analysis_inputs_path=str(pack.get("analysis_inputs_path", "")),
                )
            except AnalysisError as exc:
                errors.append(f"analysis_inputs_rebuild_failed:{exc}")
            else:
                if expected.get("analysis_units") != pack.get("analysis_units"):
                    errors.append("analysis_units_not_reproducible")
                if expected.get("summary") != pack.get("summary"):
                    errors.append("analysis_summary_not_reproducible")

    if not pack.get("source_catalog_path"):
        warnings.append("source_catalog_path_empty")
    if not pack.get("coverage_matrix_path"):
        warnings.append("coverage_matrix_path_empty")

    return {
        "gate_id": "R5_BUNDLE8_ANALYSIS_PACK_GATE",
        "decision": "pass" if expected_pass and not errors else "fail",
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "stats": {
            "complete_units": complete_units,
            "total_units": len(units),
            "missing_required_sections": missing_sections,
        },
    }


def build_analysis_subpacks(pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Split complete units into deterministic downstream research assets."""

    complete = [
        deepcopy(unit)
        for unit in pack.get("analysis_units") or []
        if isinstance(unit, dict) and unit.get("status") == "complete"
    ]
    by_section: dict[str, list[dict[str, Any]]] = {}
    for unit in complete:
        by_section.setdefault(str(unit.get("section", "")), []).append(unit)

    def artifact(artifact_type: str, sections: list[str]) -> dict[str, Any]:
        units = [unit for section in sections for unit in by_section.get(section, [])]
        return {
            "artifact_type": artifact_type,
            "schema_version": "v0.1",
            "workflow_id": pack.get("workflow_id", ""),
            "company_id": pack.get("company_id", ""),
            "analysis_date": pack.get("analysis_date", ""),
            "analysis_units": units,
            "unit_count": len(units),
            "source_analysis_pack": pack.get("analysis_inputs_path", ""),
            "notes": [
                "Derived only from complete R5_analysis_pack_v2 units.",
                "No additional facts or conclusions are introduced here.",
            ],
        }

    return {
        "thesis_tree": artifact(
            "R5_thesis_tree",
            ["core_thesis", "risk_counterevidence"],
        ),
        "business_driver_tree": artifact(
            "R5_business_driver_tree",
            ["business_driver", "financial_quality"],
        ),
        "segment_economics": artifact(
            "R5_segment_economics",
            ["segment_economics"],
        ),
        "competitive_position_matrix": artifact(
            "R5_competitive_position_matrix",
            ["industry_context", "competitive_position"],
        ),
        "risk_counterevidence_pack": artifact(
            "R5_risk_counterevidence_pack",
            ["risk_counterevidence"],
        ),
    }
