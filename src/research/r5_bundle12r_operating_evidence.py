from __future__ import annotations

import csv
import hashlib
import json
import math
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml

ALLOWED_OBSERVATION_STATUSES = {
    "confirmed",
    "bounded_estimate",
    "missing",
    "conflicting",
}
ALLOWED_OVERLAP_RELATIONS = {"disjoint", "contains", "overlaps", "unknown"}
ALLOWED_MATERIALITY = {"material", "non_material"}
SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return payload


def _as_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(str(value).replace(",", ""))
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def _non_empty_list(value: object) -> list[object]:
    return [item.strip() for item in value if isinstance(item, str) and item.strip()] if isinstance(value, list) else []


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _issue(
    code: str,
    severity: str,
    message: str,
    *,
    segment_id: str = "",
    driver_id: str = "",
    target_stage: str = "",
    owner_skill: str = "",
    target_artifact: str = "",
) -> dict[str, str]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "segment_id": segment_id,
        "driver_id": driver_id,
        "target_stage": target_stage,
        "owner_skill": owner_skill,
        "target_artifact": target_artifact,
    }


def _thresholds(contract: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(contract.get("thresholds"))


def _source_tier_allowed(contract: Mapping[str, Any], tier: object, *, bounded: bool) -> bool:
    source_tiers = _mapping(contract.get("source_tiers"))
    rule = _mapping(source_tiers.get(str(tier)))
    key = "eligible_for_bounded_estimate" if bounded else "eligible_for_confirmed"
    return rule.get(key) is True


def observation_qualified(
    observation: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> tuple[bool, str]:
    status = str(observation.get("status", ""))
    thresholds = _thresholds(contract)
    confidence = _as_float(observation.get("confidence"))
    unit = str(observation.get("unit", "")).strip()
    period = str(observation.get("period", "")).strip()
    evidence_ids = _non_empty_list(observation.get("evidence_ids"))
    source_tier = observation.get("source_tier")

    if status == "confirmed":
        minimum = _as_float(thresholds.get("confirmed_min_confidence")) or 0.70
        if _as_float(observation.get("value")) is None:
            return False, "confirmed observation requires numeric value"
        if not unit or not period:
            return False, "confirmed observation requires unit and period"
        if not evidence_ids:
            return False, "confirmed observation requires evidence_ids"
        if confidence is None or confidence < minimum:
            return False, f"confirmed observation confidence must be >= {minimum:.2f}"
        if not _source_tier_allowed(contract, source_tier, bounded=False):
            return False, "source tier is not eligible for confirmed status"
        return True, "qualified confirmed observation"

    if status == "bounded_estimate":
        minimum = _as_float(thresholds.get("bounded_estimate_min_confidence")) or 0.50
        lower = _as_float(observation.get("lower_bound"))
        upper = _as_float(observation.get("upper_bound"))
        methodology = str(observation.get("methodology", "")).strip()
        if lower is None or upper is None or lower > upper:
            return False, "bounded estimate requires ordered numeric lower_bound and upper_bound"
        if not unit or not period:
            return False, "bounded estimate requires unit and period"
        if not evidence_ids and not methodology:
            return False, "bounded estimate requires evidence_ids or methodology"
        if confidence is None or confidence < minimum:
            return False, f"bounded estimate confidence must be >= {minimum:.2f}"
        if not _source_tier_allowed(contract, source_tier, bounded=True):
            return False, "source tier is not eligible for bounded estimate"
        return True, "qualified bounded estimate"

    if status in {"missing", "conflicting"}:
        return False, status
    return False, f"unsupported observation status: {status or '<blank>'}"


def observation_point(observation: Mapping[str, Any]) -> float | None:
    if str(observation.get("status")) == "confirmed":
        return _as_float(observation.get("value"))
    if str(observation.get("status")) == "bounded_estimate":
        lower = _as_float(observation.get("lower_bound"))
        upper = _as_float(observation.get("upper_bound"))
        if lower is not None and upper is not None:
            return (lower + upper) / 2.0
    return None


def observation_interval(observation: Mapping[str, Any]) -> tuple[float, float] | None:
    if str(observation.get("status")) == "confirmed":
        value = _as_float(observation.get("value"))
        return (value, value) if value is not None else None
    if str(observation.get("status")) == "bounded_estimate":
        lower = _as_float(observation.get("lower_bound"))
        upper = _as_float(observation.get("upper_bound"))
        if lower is not None and upper is not None and lower <= upper:
            return lower, upper
    return None


def _archetypes(contract: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(contract.get("archetypes"))


def validate_contract(contract: Mapping[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    archetypes = _archetypes(contract)
    if not archetypes:
        issues.append(_issue("CONTRACT_ARCHETYPES_MISSING", "critical", "No archetypes defined"))
    for archetype_id, raw in archetypes.items():
        item = _mapping(raw)
        drivers = item.get("essential_drivers")
        if not isinstance(drivers, list) or not drivers:
            issues.append(
                _issue(
                    "CONTRACT_ESSENTIAL_DRIVERS_MISSING",
                    "critical",
                    f"Archetype {archetype_id} has no essential_drivers",
                )
            )
            continue
        seen: set[str] = set()
        for driver in drivers:
            driver_map = _mapping(driver)
            driver_id = str(driver_map.get("driver_id", "")).strip()
            if not driver_id:
                issues.append(
                    _issue(
                        "CONTRACT_DRIVER_ID_MISSING",
                        "critical",
                        f"Archetype {archetype_id} has a driver without driver_id",
                    )
                )
            elif driver_id in seen:
                issues.append(
                    _issue(
                        "CONTRACT_DRIVER_DUPLICATE",
                        "critical",
                        f"Archetype {archetype_id} repeats driver {driver_id}",
                    )
                )
            else:
                seen.add(driver_id)
    return issues


def validate_input(payload: Mapping[str, Any], contract: Mapping[str, Any]) -> list[dict[str, str]]:
    issues = validate_contract(contract)
    if payload.get("artifact_type") != "R5_bundle12r_operating_evidence_input":
        issues.append(
            _issue(
                "INPUT_ARTIFACT_TYPE_INVALID",
                "critical",
                "artifact_type must be R5_bundle12r_operating_evidence_input",
                target_stage="T0",
                owner_skill="research-orchestrator",
            )
        )
    if payload.get("schema_version") != 1:
        issues.append(
            _issue(
                "INPUT_SCHEMA_VERSION_INVALID",
                "critical",
                "schema_version must be 1",
                target_stage="T0",
                owner_skill="research-orchestrator",
            )
        )
    if not str(payload.get("workflow_id", "")).strip():
        issues.append(
            _issue(
                "INPUT_WORKFLOW_ID_MISSING",
                "critical",
                "workflow_id is required",
                target_stage="T0",
                owner_skill="research-orchestrator",
            )
        )
    issuer = _mapping(payload.get("issuer"))
    if not str(issuer.get("stock_code", "")).strip() or not str(issuer.get("company_name", "")).strip():
        issues.append(
            _issue(
                "INPUT_ISSUER_IDENTITY_MISSING",
                "critical",
                "issuer.stock_code and issuer.company_name are required",
                target_stage="T0",
                owner_skill="research-orchestrator",
            )
        )

    segments = payload.get("segments")
    if not isinstance(segments, list) or not segments:
        issues.append(
            _issue(
                "INPUT_SEGMENTS_MISSING",
                "critical",
                "At least one segment is required",
                target_stage="T2",
                owner_skill="stock-deep-dive",
            )
        )
        return issues

    seen_segments: set[str] = set()
    archetypes = _archetypes(contract)
    for raw_segment in segments:
        segment = _mapping(raw_segment)
        segment_id = str(segment.get("segment_id", "")).strip()
        if not segment_id:
            issues.append(
                _issue(
                    "SEGMENT_ID_MISSING",
                    "critical",
                    "Every segment requires segment_id",
                    target_stage="T2",
                    owner_skill="stock-deep-dive",
                )
            )
            continue
        if segment_id in seen_segments:
            issues.append(
                _issue(
                    "SEGMENT_ID_DUPLICATE",
                    "critical",
                    f"Duplicate segment_id: {segment_id}",
                    segment_id=segment_id,
                    target_stage="T2",
                    owner_skill="stock-deep-dive",
                )
            )
        seen_segments.add(segment_id)
        materiality = str(segment.get("materiality", ""))
        if materiality not in ALLOWED_MATERIALITY:
            issues.append(
                _issue(
                    "SEGMENT_MATERIALITY_INVALID",
                    "high",
                    f"Segment {segment_id} materiality must be material or non_material",
                    segment_id=segment_id,
                    target_stage="T2",
                    owner_skill="stock-deep-dive",
                )
            )
        archetype_id = str(segment.get("archetype_id", "")).strip()
        if archetype_id not in archetypes:
            issues.append(
                _issue(
                    "SEGMENT_ARCHETYPE_UNKNOWN",
                    "high",
                    f"Segment {segment_id} uses unknown archetype {archetype_id or '<blank>'}",
                    segment_id=segment_id,
                    target_stage="T2",
                    owner_skill="stock-deep-dive",
                )
            )
        drivers = segment.get("drivers")
        if not isinstance(drivers, list):
            issues.append(
                _issue(
                    "SEGMENT_DRIVERS_INVALID",
                    "high",
                    f"Segment {segment_id} drivers must be a list",
                    segment_id=segment_id,
                    target_stage="T2",
                    owner_skill="stock-deep-dive",
                )
            )
            continue
        seen_drivers: set[str] = set()
        for raw_driver in drivers:
            driver = _mapping(raw_driver)
            driver_id = str(driver.get("driver_id", "")).strip()
            if not driver_id:
                issues.append(
                    _issue(
                        "DRIVER_ID_MISSING",
                        "high",
                        f"Segment {segment_id} has a driver without driver_id",
                        segment_id=segment_id,
                        target_stage="T2",
                        owner_skill="stock-deep-dive",
                    )
                )
            elif driver_id in seen_drivers:
                issues.append(
                    _issue(
                        "DRIVER_ID_DUPLICATE",
                        "high",
                        f"Segment {segment_id} repeats driver {driver_id}",
                        segment_id=segment_id,
                        driver_id=driver_id,
                        target_stage="T2",
                        owner_skill="stock-deep-dive",
                    )
                )
            else:
                seen_drivers.add(driver_id)
            status = str(driver.get("status", ""))
            if status not in ALLOWED_OBSERVATION_STATUSES:
                issues.append(
                    _issue(
                        "DRIVER_STATUS_INVALID",
                        "high",
                        f"Driver {segment_id}/{driver_id} has invalid status {status or '<blank>'}",
                        segment_id=segment_id,
                        driver_id=driver_id,
                        target_stage="T1",
                        owner_skill="evidence-ingest",
                    )
                )

    overlaps = payload.get("overlaps", [])
    if not isinstance(overlaps, list):
        issues.append(
            _issue(
                "OVERLAPS_INVALID",
                "critical",
                "overlaps must be a list",
                target_stage="T2",
                owner_skill="stock-deep-dive",
            )
        )
    else:
        for raw_overlap in overlaps:
            overlap = _mapping(raw_overlap)
            left = str(overlap.get("left_segment_id", "")).strip()
            right = str(overlap.get("right_segment_id", "")).strip()
            relation = str(overlap.get("relation", "")).strip()
            if left not in seen_segments or right not in seen_segments or left == right:
                issues.append(
                    _issue(
                        "OVERLAP_SEGMENT_REFERENCE_INVALID",
                        "high",
                        f"Invalid overlap pair {left}/{right}",
                        target_stage="T2",
                        owner_skill="stock-deep-dive",
                    )
                )
            if relation not in ALLOWED_OVERLAP_RELATIONS:
                issues.append(
                    _issue(
                        "OVERLAP_RELATION_INVALID",
                        "high",
                        f"Invalid overlap relation for {left}/{right}: {relation or '<blank>'}",
                        target_stage="T2",
                        owner_skill="stock-deep-dive",
                    )
                )
    return issues


def _required_drivers(archetype_id: str, contract: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    archetype = _mapping(_archetypes(contract).get(archetype_id))
    raw = archetype.get("essential_drivers")
    return [_mapping(item) for item in raw] if isinstance(raw, list) else []


def _segment_by_id(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    segments = payload.get("segments", [])
    return {
        str(_mapping(item).get("segment_id")): _mapping(item)
        for item in segments
        if isinstance(item, Mapping) and str(item.get("segment_id", "")).strip()
    }


def _driver_map(segment: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    drivers = segment.get("drivers", [])
    return {
        str(_mapping(item).get("driver_id")): _mapping(item)
        for item in drivers
        if isinstance(item, Mapping) and str(item.get("driver_id", "")).strip()
    }


def _qualified_history_count(rows: object, contract: Mapping[str, Any]) -> int:
    return len(_qualified_history_profile(rows, contract))


def _qualified_history_profile(rows: object, contract: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(rows, list):
        return {}
    profile: dict[str, str] = {}
    conflicting_periods: set[str] = set()
    for row in rows:
        observation = _mapping(row)
        if not observation_qualified(observation, contract)[0]:
            continue
        period = str(observation.get("period", "")).strip()
        unit = str(observation.get("unit", "")).strip()
        if period in profile and profile[period] != unit:
            conflicting_periods.add(period)
            continue
        profile[period] = unit
    for period in conflicting_periods:
        profile.pop(period, None)
    return profile


def _financial_coverage(
    payload: Mapping[str, Any],
    contract: Mapping[str, Any],
    field: str,
    overlaps: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    totals = _mapping(payload.get("financial_totals"))
    total_observation = _mapping(totals.get(field))
    total_qualified, total_reason = observation_qualified(total_observation, contract)
    total_value = observation_point(total_observation) if total_qualified else None
    total_period = str(total_observation.get("period", "")).strip()
    total_unit = str(total_observation.get("unit", "")).strip()

    segment_values: dict[str, float] = {}
    incompatible_observations: list[dict[str, str]] = []
    for segment_id, segment in _segment_by_id(payload).items():
        observation = _mapping(segment.get(field))
        qualified, _ = observation_qualified(observation, contract)
        point = observation_point(observation) if qualified else None
        if point is not None:
            observation_period = str(observation.get("period", "")).strip()
            observation_unit = str(observation.get("unit", "")).strip()
            if total_qualified and observation_period != total_period:
                incompatible_observations.append(
                    {
                        "subject": segment_id,
                        "observation_type": "segment",
                        "mismatch": "period",
                        "observed": observation_period,
                        "required": total_period,
                    }
                )
                continue
            if total_qualified and observation_unit != total_unit:
                incompatible_observations.append(
                    {
                        "subject": segment_id,
                        "observation_type": "segment",
                        "mismatch": "unit",
                        "observed": observation_unit,
                        "required": total_unit,
                    }
                )
                continue
            segment_values[segment_id] = point

    deduction = 0.0
    unresolved_pairs: list[str] = []
    for overlap in overlaps:
        relation = str(overlap.get("relation", ""))
        left = str(overlap.get("left_segment_id", ""))
        right = str(overlap.get("right_segment_id", ""))
        pair = f"{left}/{right}"
        if relation == "unknown":
            unresolved_pairs.append(pair)
            continue
        if relation in {"contains", "overlaps"}:
            adjustment = _mapping(overlap.get(f"{field}_adjustment"))
            qualified, _ = observation_qualified(adjustment, contract)
            amount = observation_point(adjustment) if qualified else None
            if amount is None:
                unresolved_pairs.append(pair)
            else:
                adjustment_period = str(adjustment.get("period", "")).strip()
                adjustment_unit = str(adjustment.get("unit", "")).strip()
                if total_qualified and adjustment_period != total_period:
                    incompatible_observations.append(
                        {
                            "subject": pair,
                            "observation_type": "overlap_adjustment",
                            "mismatch": "period",
                            "observed": adjustment_period,
                            "required": total_period,
                        }
                    )
                    unresolved_pairs.append(pair)
                    continue
                if total_qualified and adjustment_unit != total_unit:
                    incompatible_observations.append(
                        {
                            "subject": pair,
                            "observation_type": "overlap_adjustment",
                            "mismatch": "unit",
                            "observed": adjustment_unit,
                            "required": total_unit,
                        }
                    )
                    unresolved_pairs.append(pair)
                    continue
                deduction += amount

    attributed = sum(segment_values.values()) - deduction
    ratio = None
    residual_share = None
    overcoverage_share = None
    if total_value is not None and total_value > 0:
        ratio = min(max(attributed, 0.0), total_value) / total_value
        residual_share = max(total_value - attributed, 0.0) / total_value
        overcoverage_share = max(attributed - total_value, 0.0) / total_value

    return {
        "field": field,
        "total_qualified": total_qualified,
        "total_reason": total_reason,
        "total_value": total_value,
        "qualified_segment_count": len(segment_values),
        "qualified_segment_values": segment_values,
        "overlap_deduction": round(deduction, 8),
        "attributed_value": round(attributed, 8),
        "coverage_ratio": None if ratio is None else round(ratio, 8),
        "residual_share": None if residual_share is None else round(residual_share, 8),
        "overcoverage_share": None if overcoverage_share is None else round(overcoverage_share, 8),
        "unresolved_overlap_pairs": unresolved_pairs,
        "incompatible_observations": incompatible_observations,
    }


def evaluate_operating_coverage(
    payload: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    segments = _segment_by_id(payload)
    essential_total = 0
    essential_qualified = 0
    segment_results: list[dict[str, Any]] = []

    for segment_id, segment in segments.items():
        materiality = str(segment.get("materiality", ""))
        archetype_id = str(segment.get("archetype_id", ""))
        drivers = _driver_map(segment)
        required = _required_drivers(archetype_id, contract)
        qualified_ids: list[str] = []
        missing_ids: list[str] = []
        for spec in required:
            driver_id = str(spec.get("driver_id", ""))
            essential_total += 1 if materiality == "material" else 0
            observation = drivers.get(driver_id, {})
            qualified, reason = observation_qualified(observation, contract)
            if qualified:
                qualified_ids.append(driver_id)
                essential_qualified += 1 if materiality == "material" else 0
            else:
                missing_ids.append(driver_id)
                if materiality == "material":
                    issues.append(
                        _issue(
                            "ESSENTIAL_DRIVER_NOT_QUALIFIED",
                            "high",
                            f"Material segment {segment_id} driver {driver_id} is not qualified: {reason}",
                            segment_id=segment_id,
                            driver_id=driver_id,
                            target_stage="T1",
                            owner_skill="evidence-ingest",
                            target_artifact="R5_bundle12r_operating_evidence_input.yaml",
                        )
                    )

        exposure = _mapping(segment.get("independent_exposure"))
        exposure_qualified, exposure_reason = observation_qualified(exposure, contract)
        metric_ids = _non_empty_list(exposure.get("quantitative_metric_ids"))
        independent_exposure_qualified = exposure_qualified and bool(metric_ids)
        if materiality == "material" and not independent_exposure_qualified:
            issues.append(
                _issue(
                    "INDEPENDENT_EXPOSURE_NOT_QUALIFIED",
                    "high",
                    f"Material segment {segment_id} lacks qualified independent quantitative exposure: {exposure_reason}",
                    segment_id=segment_id,
                    target_stage="T2",
                    owner_skill="stock-deep-dive",
                    target_artifact="R5_bundle12r_operating_evidence_input.yaml",
                )
            )

        segment_results.append(
            {
                "segment_id": segment_id,
                "materiality": materiality,
                "archetype_id": archetype_id,
                "required_driver_count": len(required),
                "qualified_driver_ids": qualified_ids,
                "unqualified_driver_ids": missing_ids,
                "independent_exposure_qualified": independent_exposure_qualified,
            }
        )

    overlaps_raw = payload.get("overlaps", [])
    overlaps = [_mapping(item) for item in overlaps_raw] if isinstance(overlaps_raw, list) else []
    declared_pairs: set[tuple[str, str]] = set()
    for overlap in overlaps:
        relation = str(overlap.get("relation", ""))
        left = str(overlap.get("left_segment_id", ""))
        right = str(overlap.get("right_segment_id", ""))
        pair_key = tuple(sorted((left, right)))
        if left in segments and right in segments and left != right:
            if pair_key in declared_pairs:
                issues.append(
                    _issue(
                        "OPERATING_OVERLAP_PAIR_DUPLICATE",
                        "high",
                        f"Overlap pair is declared more than once for {left}/{right}",
                        target_stage="T2",
                        owner_skill="stock-deep-dive",
                        target_artifact="R5_bundle12r_overlap_reconciliation.yaml",
                    )
                )
            declared_pairs.add(pair_key)
        if relation == "unknown":
            issues.append(
                _issue(
                    "OPERATING_OVERLAP_UNRESOLVED",
                    "high",
                    f"Overlap relation is unknown for {left}/{right}",
                    target_stage="T2",
                    owner_skill="stock-deep-dive",
                    target_artifact="R5_bundle12r_overlap_reconciliation.yaml",
                )
            )
        elif relation in {"contains", "overlaps"}:
            method = str(overlap.get("allocation_method", "")).strip()
            if not method:
                issues.append(
                    _issue(
                        "OPERATING_OVERLAP_ALLOCATION_MISSING",
                        "high",
                        f"Overlap {left}/{right} requires allocation_method",
                        target_stage="T2",
                        owner_skill="stock-deep-dive",
                        target_artifact="R5_bundle12r_overlap_reconciliation.yaml",
                    )
                )

    for left, right in combinations(sorted(segments), 2):
        if (left, right) not in declared_pairs:
            issues.append(
                _issue(
                    "OPERATING_OVERLAP_PAIR_MISSING",
                    "high",
                    f"Every business-definition pair requires an overlap declaration; missing {left}/{right}",
                    target_stage="T2",
                    owner_skill="stock-deep-dive",
                    target_artifact="R5_bundle12r_overlap_reconciliation.yaml",
                )
            )

    revenue = _financial_coverage(payload, contract, "revenue", overlaps)
    gross_profit = _financial_coverage(payload, contract, "gross_profit", overlaps)
    thresholds = _thresholds(contract)
    revenue_min = _as_float(thresholds.get("revenue_coverage_min")) or 0.80
    gp_min = _as_float(thresholds.get("gross_profit_coverage_min")) or 0.70
    driver_min = _as_float(thresholds.get("essential_driver_coverage_min")) or 0.80
    residual_max = _as_float(thresholds.get("max_residual_share")) or 0.20
    overcoverage_max = _as_float(thresholds.get("max_overcoverage_share")) or 0.02

    essential_ratio = essential_qualified / essential_total if essential_total else 0.0
    if revenue["coverage_ratio"] is None:
        issues.append(
            _issue(
                "REVENUE_COVERAGE_DENOMINATOR_MISSING",
                "high",
                "Qualified total revenue is required to measure operating coverage",
                target_stage="T1",
                owner_skill="evidence-ingest",
            )
        )
    elif float(revenue["coverage_ratio"]) < revenue_min:
        issues.append(
            _issue(
                "REVENUE_COVERAGE_BELOW_THRESHOLD",
                "high",
                f"Revenue coverage {revenue['coverage_ratio']:.2%} is below {revenue_min:.2%}",
                target_stage="T2",
                owner_skill="stock-deep-dive",
            )
        )
    if gross_profit["coverage_ratio"] is None:
        issues.append(
            _issue(
                "GROSS_PROFIT_COVERAGE_DENOMINATOR_MISSING",
                "high",
                "Qualified total gross profit is required to measure operating coverage",
                target_stage="T1",
                owner_skill="evidence-ingest",
            )
        )
    elif float(gross_profit["coverage_ratio"]) < gp_min:
        issues.append(
            _issue(
                "GROSS_PROFIT_COVERAGE_BELOW_THRESHOLD",
                "high",
                f"Gross-profit coverage {gross_profit['coverage_ratio']:.2%} is below {gp_min:.2%}",
                target_stage="T2",
                owner_skill="stock-deep-dive",
            )
        )
    if essential_ratio < driver_min:
        issues.append(
            _issue(
                "ESSENTIAL_DRIVER_COVERAGE_BELOW_THRESHOLD",
                "high",
                f"Essential-driver coverage {essential_ratio:.2%} is below {driver_min:.2%}",
                target_stage="T2",
                owner_skill="stock-deep-dive",
            )
        )

    for field_result in (revenue, gross_profit):
        residual_share = field_result.get("residual_share")
        overcoverage_share = field_result.get("overcoverage_share")
        if residual_share is not None and float(residual_share) > residual_max:
            issues.append(
                _issue(
                    "FINANCIAL_RESIDUAL_ABOVE_THRESHOLD",
                    "high",
                    f"{field_result['field']} residual {float(residual_share):.2%} exceeds {residual_max:.2%}",
                    target_stage="T2",
                    owner_skill="stock-deep-dive",
                )
            )
        if overcoverage_share is not None and float(overcoverage_share) > overcoverage_max:
            issues.append(
                _issue(
                    "FINANCIAL_OVER_COVERAGE_DETECTED",
                    "high",
                    f"{field_result['field']} overcoverage {float(overcoverage_share):.2%} indicates double counting",
                    target_stage="T2",
                    owner_skill="stock-deep-dive",
                )
            )
        for pair in field_result.get("unresolved_overlap_pairs", []):
            issues.append(
                _issue(
                    "FINANCIAL_OVERLAP_ADJUSTMENT_MISSING",
                    "high",
                    f"{field_result['field']} overlap adjustment missing for {pair}",
                    target_stage="T2",
                    owner_skill="stock-deep-dive",
                )
            )
        for mismatch in field_result.get("incompatible_observations", []):
            mismatch_type = str(_mapping(mismatch).get("mismatch", "")).upper() or "UNKNOWN"
            subject = str(_mapping(mismatch).get("subject", ""))
            observed = str(_mapping(mismatch).get("observed", ""))
            required = str(_mapping(mismatch).get("required", ""))
            issues.append(
                _issue(
                    f"FINANCIAL_{mismatch_type}_MISMATCH",
                    "high",
                    f"{field_result['field']} observation {subject} uses {observed!r}; required {required!r}",
                    segment_id=subject if "/" not in subject else "",
                    target_stage="T2",
                    owner_skill="stock-deep-dive",
                    target_artifact="R5_bundle12r_operating_evidence_input.yaml",
                )
            )

    coverage = {
        "local_gate_id": "RP-12R-OE",
        "segment_results": segment_results,
        "essential_driver_qualified": essential_qualified,
        "essential_driver_total": essential_total,
        "essential_driver_coverage_ratio": round(essential_ratio, 8),
        "revenue_coverage": revenue,
        "gross_profit_coverage": gross_profit,
        "thresholds": {
            "revenue_coverage_min": revenue_min,
            "gross_profit_coverage_min": gp_min,
            "essential_driver_coverage_min": driver_min,
            "max_residual_share": residual_max,
            "max_overcoverage_share": overcoverage_max,
        },
        "blocking_issue_codes": [
            str(issue.get("code"))
            for issue in issues
            if str(issue.get("severity")) in {"critical", "high"}
        ],
    }
    coverage["operating_gate_passed"] = not coverage["blocking_issue_codes"]
    return coverage, issues


def evaluate_valuation_eligibility(
    payload: Mapping[str, Any],
    contract: Mapping[str, Any],
    coverage: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    valuation = _mapping(payload.get("valuation_inputs"))
    thresholds = _thresholds(contract)
    min_peers = int(_as_float(thresholds.get("min_comparable_peers")) or 3)
    min_history = int(_as_float(thresholds.get("min_cashflow_periods")) or 3)
    peer_confidence_min = _as_float(thresholds.get("peer_min_confidence")) or 0.70
    input_gate_ok = coverage.get("input_gate_passed") is True

    qualified_peers: list[str] = []
    seen_peer_ids: set[str] = set()
    peers = valuation.get("peers", [])
    if isinstance(peers, list):
        for raw_peer in peers:
            peer = _mapping(raw_peer)
            peer_id = str(peer.get("peer_id", "")).strip()
            confidence = _as_float(peer.get("confidence")) or 0.0
            source_ok = _source_tier_allowed(contract, peer.get("source_tier"), bounded=False)
            evidence_ok = bool(_non_empty_list(peer.get("operating_metric_evidence_ids")))
            if (
                bool(peer_id)
                and peer_id not in seen_peer_ids
                and peer.get("business_definition_match") is True
                and peer.get("period_match") is True
                and peer.get("metric_definition_match") is True
                and confidence >= peer_confidence_min
                and source_ok
                and evidence_ok
            ):
                qualified_peers.append(peer_id)
                seen_peer_ids.add(peer_id)
    peer_eligible = input_gate_ok and len(qualified_peers) >= min_peers
    if not peer_eligible:
        peer_message = (
            "Peer method requires input validation without critical/high issues; "
            f"{len(qualified_peers)} source-qualified peers observed"
            if not input_gate_ok
            else f"Only {len(qualified_peers)} qualified peers; {min_peers} required"
        )
        issues.append(
            _issue(
                "PEER_METHOD_NOT_ELIGIBLE",
                "medium",
                peer_message,
                target_stage="RP6",
                owner_skill="company-valuation",
                target_artifact="peer_operating_evidence_pack.yaml",
            )
        )

    totals = _mapping(payload.get("financial_totals"))
    ocf_profile = _qualified_history_profile(totals.get("operating_cash_flow_history"), contract)
    capex_profile = _qualified_history_profile(totals.get("capex_history"), contract)
    ocf_periods = len(ocf_profile)
    capex_periods = len(capex_profile)
    paired_cashflow_periods = sorted(
        period
        for period in set(ocf_profile).intersection(capex_profile)
        if ocf_profile[period] == capex_profile[period]
    )
    paired_cashflow_units = {ocf_profile[period] for period in paired_cashflow_periods}
    cashflow_history_ok = len(paired_cashflow_periods) >= min_history and len(paired_cashflow_units) == 1
    working_capital = _mapping(totals.get("working_capital_bridge"))
    working_capital_observation_ok = observation_qualified(working_capital, contract)[0]
    working_capital_ok = (
        working_capital_observation_ok
        and cashflow_history_ok
        and str(working_capital.get("period", "")).strip() in paired_cashflow_periods
        and str(working_capital.get("unit", "")).strip() in paired_cashflow_units
    )
    dcf = _mapping(valuation.get("dcf"))
    tax_observation = _mapping(dcf.get("tax_rate"))
    wacc_observation = _mapping(dcf.get("wacc"))
    growth_observation = _mapping(dcf.get("terminal_growth"))
    tax_interval = observation_interval(tax_observation)
    wacc_interval = observation_interval(wacc_observation)
    growth_interval = observation_interval(growth_observation)
    tax_ok = (
        observation_qualified(tax_observation, contract)[0]
        and str(tax_observation.get("unit", "")).strip() == "ratio"
        and tax_interval is not None
        and 0.0 <= tax_interval[0] <= tax_interval[1] <= 1.0
    )
    wacc_ok = (
        observation_qualified(wacc_observation, contract)[0]
        and str(wacc_observation.get("unit", "")).strip() == "ratio"
        and wacc_interval is not None
        and 0.0 < wacc_interval[0] <= wacc_interval[1] <= 1.0
    )
    growth_ok = (
        observation_qualified(growth_observation, contract)[0]
        and str(growth_observation.get("unit", "")).strip() == "ratio"
        and growth_interval is not None
        and -1.0 < growth_interval[0] <= growth_interval[1] < 1.0
    )
    discount_spread_ok = bool(
        wacc_ok
        and growth_ok
        and wacc_interval is not None
        and growth_interval is not None
        and wacc_interval[0] > growth_interval[1]
    )
    dcf_inputs_ok = tax_ok and wacc_ok and growth_ok and discount_spread_ok
    # The operating gate is non-compensating: unresolved overlaps, independent-exposure
    # failures, residual/overcoverage failures and missing drivers must block DCF/SOTP
    # even when the three headline ratios happen to exceed their thresholds.
    operating_gate_ok = bool(coverage.get("operating_gate_passed")) and not _coverage_issues_from_snapshot(coverage)
    # Recheck headline thresholds defensively for callers that construct a snapshot directly.
    threshold_map = _mapping(coverage.get("thresholds"))
    revenue_ratio = _as_float(_mapping(coverage.get("revenue_coverage")).get("coverage_ratio"))
    gp_ratio = _as_float(_mapping(coverage.get("gross_profit_coverage")).get("coverage_ratio"))
    driver_ratio = _as_float(coverage.get("essential_driver_coverage_ratio"))
    operating_gate_ok = operating_gate_ok and all(
        (
            revenue_ratio is not None
            and revenue_ratio >= (_as_float(threshold_map.get("revenue_coverage_min")) or 0.80),
            gp_ratio is not None
            and gp_ratio >= (_as_float(threshold_map.get("gross_profit_coverage_min")) or 0.70),
            driver_ratio is not None
            and driver_ratio >= (_as_float(threshold_map.get("essential_driver_coverage_min")) or 0.80),
        )
    )
    dcf_eligible = (
        operating_gate_ok
        and cashflow_history_ok
        and working_capital_ok
        and dcf_inputs_ok
    )
    if not dcf_eligible:
        issues.append(
            _issue(
                "DCF_METHOD_NOT_ELIGIBLE",
                "medium",
                "DCF requires passed operating coverage, three aligned same-unit OCF/capex periods, a compatible working-capital bridge, tax, WACC and terminal growth",
                target_stage="RP6",
                owner_skill="company-valuation",
                target_artifact="dcf_eligibility_pack.yaml",
            )
        )

    material_segments = {
        segment_id: segment
        for segment_id, segment in _segment_by_id(payload).items()
        if str(segment.get("materiality")) == "material"
    }
    sotp = _mapping(valuation.get("sotp"))
    components_raw = sotp.get("components", [])
    components = {
        str(_mapping(component).get("segment_id")): _mapping(component)
        for component in components_raw
        if isinstance(components_raw, list) and isinstance(component, Mapping)
    }
    segment_result_map = {
        str(_mapping(row).get("segment_id")): _mapping(row)
        for row in coverage.get("segment_results", [])
        if isinstance(row, Mapping)
    }
    sotp_component_failures: list[str] = []
    for segment_id in material_segments:
        component = components.get(segment_id, {})
        result = segment_result_map.get(segment_id, {})
        segment = material_segments[segment_id]
        revenue_ok = observation_qualified(_mapping(segment.get("revenue")), contract)[0]
        gp_ok = observation_qualified(_mapping(segment.get("gross_profit")), contract)[0]
        if not (
            str(component.get("method", "")).strip()
            and component.get("overlap_resolved") is True
            and bool(result.get("independent_exposure_qualified"))
            and (revenue_ok or gp_ok)
        ):
            sotp_component_failures.append(segment_id)
    sotp_eligible = operating_gate_ok and not sotp_component_failures and bool(material_segments)
    if not sotp_eligible:
        issues.append(
            _issue(
                "SOTP_METHOD_NOT_ELIGIBLE",
                "medium",
                "SOTP requires every material segment to have independent quantitative exposure, qualified financials, a method and resolved overlap; failures="
                + ",".join(sotp_component_failures or ["operating_gate"]),
                target_stage="RP6",
                owner_skill="company-valuation",
                target_artifact="sotp_eligibility_pack.yaml",
            )
        )

    result = {
        "peer_method": {
            "eligible": peer_eligible,
            "input_gate_qualified": input_gate_ok,
            "qualified_peer_ids": qualified_peers,
            "qualified_peer_count": len(qualified_peers),
            "minimum_required": min_peers,
        },
        "dcf_method": {
            "eligible": dcf_eligible,
            "operating_gate_qualified": operating_gate_ok,
            "qualified_ocf_periods": ocf_periods,
            "qualified_capex_periods": capex_periods,
            "paired_cashflow_periods": paired_cashflow_periods,
            "paired_cashflow_period_count": len(paired_cashflow_periods),
            "cashflow_history_qualified": cashflow_history_ok,
            "working_capital_observation_qualified": working_capital_observation_ok,
            "working_capital_bridge_qualified": working_capital_ok,
            "tax_rate_qualified": tax_ok,
            "wacc_qualified": wacc_ok,
            "terminal_growth_qualified": growth_ok,
            "discount_spread_qualified": discount_spread_ok,
            "required_inputs_qualified": dcf_inputs_ok,
        },
        "sotp_method": {
            "eligible": sotp_eligible,
            "operating_gate_qualified": operating_gate_ok,
            "component_failures": sotp_component_failures,
            "material_segment_count": len(material_segments),
        },
        "fallback_methods": ["reverse_valuation", "scenario_valuation"],
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
    return result, issues


def _coverage_issues_from_snapshot(coverage: Mapping[str, Any]) -> list[dict[str, str]]:
    raw_codes = coverage.get("blocking_issue_codes", [])
    if not isinstance(raw_codes, list):
        return [
            _issue(
                "COVERAGE_BLOCKING_ISSUES_INVALID",
                "high",
                "coverage.blocking_issue_codes must be a list",
            )
        ]
    return [
        _issue(str(code), "high", "serialized operating-coverage blocker")
        for code in raw_codes
        if str(code).strip()
    ]


def build_research_question_plan(
    payload: Mapping[str, Any],
    contract: Mapping[str, Any],
    issues: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    question_rows: list[dict[str, Any]] = []
    segments = _segment_by_id(payload)
    issue_keys = {(str(row.get("segment_id")), str(row.get("driver_id"))) for row in issues}
    counter = 1
    for segment_id, segment in segments.items():
        archetype_id = str(segment.get("archetype_id", ""))
        drivers = _driver_map(segment)
        for spec in _required_drivers(archetype_id, contract):
            driver_id = str(spec.get("driver_id", ""))
            qualified, _ = observation_qualified(drivers.get(driver_id, {}), contract)
            if qualified and (segment_id, driver_id) not in issue_keys:
                continue
            question_rows.append(
                {
                    "question_id": f"OEQ-{counter:03d}",
                    "segment_id": segment_id,
                    "driver_id": driver_id,
                    "priority": "high" if str(segment.get("materiality")) == "material" else "medium",
                    "question": str(spec.get("question", "")).format(
                        segment_name=str(segment.get("segment_name", segment_id))
                    ),
                    "target_source_types": list(spec.get("target_source_types", [])),
                    "owner_skill": "evidence-ingest",
                    "target_stage": "T1",
                    "acceptance": {
                        "allowed_statuses": ["confirmed", "bounded_estimate"],
                        "must_include": ["unit", "period", "confidence", "evidence_ids", "financial_mapping"],
                    },
                }
            )
            counter += 1

    for issue in issues:
        code = str(issue.get("code", ""))
        if code.startswith("OPERATING_OVERLAP") or code.startswith("FINANCIAL_OVERLAP"):
            question_rows.append(
                {
                    "question_id": f"OEQ-{counter:03d}",
                    "segment_id": str(issue.get("segment_id", "")),
                    "driver_id": "overlap_reconciliation",
                    "priority": "high",
                    "question": "Determine whether the affected business definitions are disjoint, contained or overlapping; document a numeric allocation or deduction rule.",
                    "target_source_types": ["issuer_segment_note", "issuer_ir", "audited_financial_note"],
                    "owner_skill": "stock-deep-dive",
                    "target_stage": "T2",
                    "acceptance": {
                        "allowed_relations": ["disjoint", "contains", "overlaps"],
                        "must_include": ["allocation_method", "evidence_ids"],
                    },
                }
            )
            counter += 1
    return {
        "artifact_type": "R5_bundle12r_research_question_plan",
        "schema_version": 1,
        "workflow_id": payload.get("workflow_id"),
        "issuer": payload.get("issuer"),
        "question_count": len(question_rows),
        "questions": question_rows,
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }


def build_backflow_plan(issues: Sequence[Mapping[str, str]], payload: Mapping[str, Any]) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[Mapping[str, str]]] = {}
    for issue in issues:
        severity = str(issue.get("severity", ""))
        if severity not in {"critical", "high", "medium"}:
            continue
        key = (str(issue.get("target_stage", "T9")), str(issue.get("owner_skill", "quality-review")))
        grouped.setdefault(key, []).append(issue)

    actions = []
    for index, ((target_stage, owner_skill), rows) in enumerate(sorted(grouped.items()), start=1):
        actions.append(
            {
                "action_id": f"BF12R-{index:03d}",
                "target_stage": target_stage,
                "required_next_skill": owner_skill,
                "issue_codes": sorted({str(row.get("code")) for row in rows}),
                "target_artifacts": sorted(
                    {str(row.get("target_artifact")) for row in rows if str(row.get("target_artifact", ""))}
                ),
                "status": "open",
            }
        )
    return {
        "artifact_type": "R5_bundle12r_backflow_plan",
        "schema_version": 1,
        "workflow_id": payload.get("workflow_id"),
        "decision": "backflow_required" if actions else "no_backflow_required",
        "actions": actions,
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }


def evaluate_bundle12r(payload: Mapping[str, Any], contract: Mapping[str, Any]) -> dict[str, Any]:
    input_issues = validate_input(payload, contract)
    coverage, coverage_issues = evaluate_operating_coverage(payload, contract)
    input_blocking_codes = [
        str(issue.get("code"))
        for issue in input_issues
        if str(issue.get("severity")) in {"critical", "high"}
    ]
    coverage["blocking_issue_codes"] = list(
        dict.fromkeys([*coverage.get("blocking_issue_codes", []), *input_blocking_codes])
    )
    coverage["input_gate_passed"] = not input_blocking_codes
    coverage["operating_gate_passed"] = not coverage["blocking_issue_codes"]
    valuation, valuation_issues = evaluate_valuation_eligibility(payload, contract, coverage)
    issues = input_issues + coverage_issues + valuation_issues
    issues = sorted(
        issues,
        key=lambda row: (
            -SEVERITY_RANK.get(str(row.get("severity")), -1),
            str(row.get("code")),
            str(row.get("segment_id")),
            str(row.get("driver_id")),
        ),
    )
    blocker_count = sum(1 for row in issues if row["severity"] in {"critical", "high"})
    operating_decision = "needs_backflow" if blocker_count else "operating_evidence_ready"
    question_plan = build_research_question_plan(payload, contract, issues)
    backflow_plan = build_backflow_plan(issues, payload)
    return {
        "artifact_type": "R5_bundle12r_operating_evidence_result",
        "schema_version": 1,
        "workflow_id": payload.get("workflow_id"),
        "issuer": payload.get("issuer"),
        "as_of_date": payload.get("as_of_date"),
        "local_gate_id": "RP-12R-OE",
        "decision": operating_decision,
        "blocker_count": blocker_count,
        "issue_count": len(issues),
        "issues": issues,
        "coverage": coverage,
        "valuation_eligibility": valuation,
        "research_question_plan": question_plan,
        "backflow_plan": backflow_plan,
        "preserves_bundle11r_exact_hash_review": True,
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }


def _write_yaml(path: Path, payload: object) -> None:
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
        newline="\n",
    )


def _write_issues_csv(path: Path, issues: Iterable[Mapping[str, str]]) -> None:
    fields = [
        "code",
        "severity",
        "message",
        "segment_id",
        "driver_id",
        "target_stage",
        "owner_skill",
        "target_artifact",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for issue in issues:
            writer.writerow({field: issue.get(field, "") for field in fields})


def _render_readout(result: Mapping[str, Any], generation_id: str) -> str:
    coverage = _mapping(result.get("coverage"))
    revenue = _mapping(coverage.get("revenue_coverage"))
    gross_profit = _mapping(coverage.get("gross_profit_coverage"))
    valuation = _mapping(result.get("valuation_eligibility"))
    peer = _mapping(valuation.get("peer_method"))
    dcf = _mapping(valuation.get("dcf_method"))
    sotp = _mapping(valuation.get("sotp_method"))

    def ratio_text(value: object) -> str:
        number = _as_float(value)
        return "MISSING" if number is None else f"{number:.1%}"

    return "\n".join(
        [
            "# R5 Bundle 12R 经营证据资格化读数",
            "",
            f"- generation_id: `{generation_id}`",
            f"- decision: `{result.get('decision')}`",
            f"- blocker_count: `{result.get('blocker_count')}`",
            f"- issue_count: `{result.get('issue_count')}`",
            f"- revenue_coverage: `{ratio_text(revenue.get('coverage_ratio'))}`",
            f"- gross_profit_coverage: `{ratio_text(gross_profit.get('coverage_ratio'))}`",
            f"- essential_driver_coverage: `{ratio_text(coverage.get('essential_driver_coverage_ratio'))}`",
            f"- peer_method_eligible: `{bool(peer.get('eligible'))}`",
            f"- dcf_method_eligible: `{bool(dcf.get('eligible'))}`",
            f"- sotp_method_eligible: `{bool(sotp.get('eligible'))}`",
            "- Bundle 11R exact-hash human review remains immutable and is not inherited by Bundle 12R outputs.",
            "- `sample_quality_allowed=false`; `p2_allowed=false`.",
            "- 本读数不构成投资建议。",
            "",
        ]
    )


def write_bundle12r_outputs(
    input_path: Path,
    contract_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    payload = load_yaml(input_path)
    contract = load_yaml(contract_path)
    result = evaluate_bundle12r(payload, contract)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_paths = {
        "input_snapshot": output_dir / "R5_bundle12r_operating_evidence_input_snapshot.yaml",
        "contract_snapshot": output_dir / "R5_bundle12r_operating_evidence_contract_snapshot.yaml",
        "result": output_dir / "R5_bundle12r_operating_evidence_result.yaml",
        "coverage": output_dir / "R5_bundle12r_coverage_report.yaml",
        "valuation": output_dir / "R5_bundle12r_valuation_eligibility.yaml",
        "questions": output_dir / "R5_bundle12r_research_question_plan.yaml",
        "backflow": output_dir / "R5_bundle12r_backflow_plan.yaml",
        "issues": output_dir / "R5_bundle12r_quality_issues.csv",
        "readout": output_dir / "R5_bundle12r_readout.md",
        "lock": output_dir / "R5_bundle12r_generation_lock.yaml",
    }

    # Lock self-contained snapshots rather than machine-specific absolute input paths.
    output_paths["input_snapshot"].write_bytes(input_path.read_bytes())
    output_paths["contract_snapshot"].write_bytes(contract_path.read_bytes())
    _write_yaml(output_paths["result"], {key: value for key, value in result.items() if key not in {"research_question_plan", "backflow_plan"}})
    _write_yaml(output_paths["coverage"], result["coverage"])
    _write_yaml(output_paths["valuation"], result["valuation_eligibility"])
    _write_yaml(output_paths["questions"], result["research_question_plan"])
    _write_yaml(output_paths["backflow"], result["backflow_plan"])
    _write_issues_csv(output_paths["issues"], result["issues"])

    prelock_manifest = {
        "input_sha256": sha256_file(input_path),
        "contract_sha256": sha256_file(contract_path),
        "decision": result["decision"],
        "artifact_hashes": {
            key: sha256_file(path)
            for key, path in output_paths.items()
            if key not in {"readout", "lock"}
        },
    }
    generation_id = "op_evidence_gen_r5_bundle12r_" + sha256_bytes(
        canonical_json(prelock_manifest).encode("utf-8")
    )[:16]
    output_paths["readout"].write_text(_render_readout(result, generation_id), encoding="utf-8", newline="\n")
    artifact_hashes = {
        key: sha256_file(path)
        for key, path in output_paths.items()
        if key != "lock"
    }
    lock = {
        "artifact_type": "R5_bundle12r_generation_lock",
        "schema_version": 1,
        "generation_id": generation_id,
        "workflow_id": payload.get("workflow_id"),
        "issuer": payload.get("issuer"),
        "as_of_date": payload.get("as_of_date"),
        "input_hashes": {
            "operating_evidence_input": {
                "file": output_paths["input_snapshot"].name,
                "sha256": sha256_file(input_path),
            },
            "operating_evidence_contract": {
                "file": output_paths["contract_snapshot"].name,
                "sha256": sha256_file(contract_path),
            },
        },
        "artifact_hashes": {
            output_paths[key].name: artifact_hashes[key]
            for key in sorted(artifact_hashes)
        },
        "decision": result["decision"],
        "preserves_bundle11r_exact_hash_review": True,
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
    _write_yaml(output_paths["lock"], lock)
    return {"result": result, "generation_lock": lock, "paths": output_paths}


def validate_generation_lock(lock_path: Path) -> list[str]:
    lock = load_yaml(lock_path)
    issues: list[str] = []
    base_dir = lock_path.parent
    required_inputs = {
        "operating_evidence_input": "R5_bundle12r_operating_evidence_input_snapshot.yaml",
        "operating_evidence_contract": "R5_bundle12r_operating_evidence_contract_snapshot.yaml",
    }
    required_artifacts = {
        "input_snapshot": "R5_bundle12r_operating_evidence_input_snapshot.yaml",
        "contract_snapshot": "R5_bundle12r_operating_evidence_contract_snapshot.yaml",
        "result": "R5_bundle12r_operating_evidence_result.yaml",
        "coverage": "R5_bundle12r_coverage_report.yaml",
        "valuation": "R5_bundle12r_valuation_eligibility.yaml",
        "questions": "R5_bundle12r_research_question_plan.yaml",
        "backflow": "R5_bundle12r_backflow_plan.yaml",
        "issues": "R5_bundle12r_quality_issues.csv",
        "readout": "R5_bundle12r_readout.md",
    }

    if lock.get("artifact_type") != "R5_bundle12r_generation_lock":
        issues.append("invalid lock artifact_type")
    if lock.get("schema_version") != 1:
        issues.append("invalid lock schema_version")

    input_hashes = _mapping(lock.get("input_hashes"))
    if set(input_hashes) != set(required_inputs):
        issues.append("input_hashes keys must match the required Bundle 12R inputs")
    for label, expected_file in required_inputs.items():
        entry = _mapping(input_hashes.get(label))
        if str(entry.get("file", "")) != expected_file:
            issues.append(f"invalid input snapshot filename for {label}")
        path = base_dir / expected_file
        expected = str(entry.get("sha256", ""))
        if len(expected) != 64:
            issues.append(f"invalid input SHA256 for {label}")
        if not path.exists():
            issues.append(f"missing input: {path}")
        elif sha256_file(path) != expected:
            issues.append(f"input hash mismatch: {path}")

    artifact_hashes = _mapping(lock.get("artifact_hashes"))
    expected_artifact_files = set(required_artifacts.values())
    if set(artifact_hashes) != expected_artifact_files:
        issues.append("artifact_hashes keys must match all required Bundle 12R artifacts")
    for filename in sorted(expected_artifact_files):
        expected = str(artifact_hashes.get(filename, ""))
        path = base_dir / filename
        if len(expected) != 64:
            issues.append(f"invalid artifact SHA256: {filename}")
        if not path.exists():
            issues.append(f"missing artifact: {path}")
        elif sha256_file(path) != expected:
            issues.append(f"artifact hash mismatch: {path}")

    result_path = base_dir / required_artifacts["result"]
    result: dict[str, Any] = {}
    if result_path.is_file():
        try:
            result = load_yaml(result_path)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            issues.append(f"cannot load locked result: {exc}")
    if result:
        if lock.get("decision") != result.get("decision"):
            issues.append("lock decision does not match locked result")
        for key in ("workflow_id", "issuer", "as_of_date"):
            if lock.get(key) != result.get(key):
                issues.append(f"lock {key} does not match locked result")

    prelock_files = {key: filename for key, filename in required_artifacts.items() if key != "readout"}
    if all((base_dir / filename).is_file() for filename in prelock_files.values()):
        prelock_manifest = {
            "input_sha256": sha256_file(base_dir / required_inputs["operating_evidence_input"]),
            "contract_sha256": sha256_file(base_dir / required_inputs["operating_evidence_contract"]),
            "decision": result.get("decision") if result else lock.get("decision"),
            "artifact_hashes": {
                key: sha256_file(base_dir / filename)
                for key, filename in prelock_files.items()
            },
        }
        expected_generation_id = "op_evidence_gen_r5_bundle12r_" + sha256_bytes(
            canonical_json(prelock_manifest).encode("utf-8")
        )[:16]
        if lock.get("generation_id") != expected_generation_id:
            issues.append("generation_id does not match locked inputs and artifacts")

    if lock.get("preserves_bundle11r_exact_hash_review") is not True:
        issues.append("preserves_bundle11r_exact_hash_review must remain true")
    if lock.get("sample_quality_allowed") is not False:
        issues.append("sample_quality_allowed must remain false")
    if lock.get("p2_allowed") is not False:
        issues.append("p2_allowed must remain false")
    return issues
