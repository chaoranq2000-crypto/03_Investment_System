"""Deterministic P2G-2 cross-episode behavior observations.

This module consumes exactly one validated P2G-1 behavior cohort.  It produces
facts-only detector evaluations; it never reads the portfolio database, P2F
artifacts, the network, the wall clock, or a model.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .artifact_io import (
    ArtifactIOError,
    atomic_create_bytes,
    canonical_json_bytes,
    load_json_object,
    pretty_json_bytes,
)
from .behavior_cohort import SCHEMA_VERSION as COHORT_SCHEMA_VERSION
from .behavior_cohort import validate_behavior_cohort


SCHEMA_VERSION = "p2g.behavior_observation_set.v1"
VALIDATION_SCHEMA_VERSION = "p2g.behavior_observation_set.validation.v1"
BUILDER_VERSION = "p2g.behavior_observation_set.builder.v1"
DETECTOR_CONTRACT_VERSION = "p2g.behavior_detector.v1"
DETECTOR_CONFIG_VERSION = "p2g.behavior_detector_config.v1"
REASON_REGISTRY_VERSION = "p2g.behavior_observation_reason_registry.v1"
CANONICAL_SORT_VERSION = "p2g.behavior_observation_sort.v1"

DETECTOR_IDS = (
    "adjacent_episode_cadence",
    "same_instrument_reentry_gap",
    "episode_scale_transition",
    "holding_duration_transition",
)
EVALUATION_STATUSES = (
    "observed",
    "not_observed",
    "insufficient_evidence",
    "not_comparable",
    "not_applicable",
)
REASON_CODE_REGISTRY = (
    "ambiguous_metric_fact",
    "ambiguous_temporal_order",
    "different_instrument",
    "fact_known_after_subject_event",
    "gap_exceeds_threshold",
    "incomparable_currency",
    "incomparable_denominator",
    "incomparable_metric_definition",
    "incomparable_unit",
    "invalid_detector_config",
    "invalid_episode_interval",
    "invalid_scale_value",
    "missing_denominator",
    "missing_required_fact",
    "missing_required_metric",
    "missing_timezone",
    "negative_scale_value",
    "no_adjacent_episode",
    "no_following_same_instrument_episode",
    "open_episode",
    "overlapping_episodes",
    "partial_or_ambiguous_source",
    "stale_or_unpriced_source",
    "unknown_detector",
    "unknown_detector_version",
    "within_thresholds",
    "zero_denominator",
)

_DEFAULT_DETECTORS: dict[str, dict[str, Any]] = {
    "adjacent_episode_cadence": {
        "detector_id": "adjacent_episode_cadence",
        "detector_version": "1",
        "enabled": True,
        "parameters": {},
    },
    "same_instrument_reentry_gap": {
        "detector_id": "same_instrument_reentry_gap",
        "detector_version": "1",
        "enabled": True,
        "parameters": {"maximum_gap_seconds": "604800"},
    },
    "episode_scale_transition": {
        "detector_id": "episode_scale_transition",
        "detector_version": "1",
        "enabled": True,
        "parameters": {
            "material_decrease_ratio": "0.8",
            "material_increase_ratio": "1.25",
            "metric_priority": [
                "target_position_weight",
                "target_position_value",
                "maximum_absolute_quantity",
            ],
        },
    },
    "holding_duration_transition": {
        "detector_id": "holding_duration_transition",
        "detector_version": "1",
        "enabled": True,
        "parameters": {
            "longer_ratio": "1.25",
            "same_instrument_only": False,
            "shorter_ratio": "0.75",
        },
    },
}

_PROHIBITED_KEYS = {
    "advice",
    "confidence_score",
    "diagnosis",
    "emotion",
    "interpretation",
    "motive",
    "narrative",
    "opinion",
    "psychology",
    "ranking",
    "recommendation",
    "score",
    "trade_instruction",
}
_METRIC_KEYS = {
    "target_position_weight",
    "target_position_value",
    "maximum_absolute_quantity",
}


class BehaviorObservationError(ValueError):
    """Raised when a P2G-2 input or artifact violates the contract."""


def _digest(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _content_id(value: Mapping[str, Any]) -> str:
    payload = {key: deepcopy(item) for key, item in value.items() if key != "content_id"}
    return "sha256:" + _digest(payload)


def _finding(severity: str, code: str, message: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "message": message}


def _validation(
    findings: Iterable[Mapping[str, str]], *, mode: str = "offline"
) -> dict[str, Any]:
    rows = sorted(
        [dict(item) for item in findings],
        key=lambda item: (item.get("severity", ""), item.get("code", ""), item.get("message", "")),
    )
    blockers = [item for item in rows if item.get("severity") == "blocker"]
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "validation_mode": mode,
        "validation_status": "blocked" if blockers else "accepted",
        "blocker_count": len(blockers),
        "finding_count": len(rows),
        "findings": rows,
    }


def _decimal(value: object, field: str, *, nonnegative: bool = False) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float) or value is None:
        raise BehaviorObservationError(f"{field} must be a decimal string or integer")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise BehaviorObservationError(f"{field} is not a valid decimal") from exc
    if not result.is_finite():
        raise BehaviorObservationError(f"{field} must be finite")
    if nonnegative and result < 0:
        raise BehaviorObservationError(f"{field} must be nonnegative")
    return result


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise BehaviorObservationError(f"{field} must be a timestamp")
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise BehaviorObservationError(f"{field} is not a valid ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BehaviorObservationError(f"{field} is missing a timezone")
    return parsed.astimezone(timezone.utc)


def _seconds(delta: object) -> str:
    total = getattr(delta, "total_seconds")()
    if int(total) != total:
        raise BehaviorObservationError("timestamp interval must resolve to whole seconds")
    return str(int(total))


def _normalize_config(
    config: Mapping[str, Any] | None = None,
    *,
    selected_detectors: Sequence[str] | None = None,
) -> dict[str, Any]:
    definitions = deepcopy(_DEFAULT_DETECTORS)
    if config is not None:
        allowed_root = {"schema_version", "contract_version", "detectors"}
        unknown_root = set(config) - allowed_root
        if unknown_root:
            raise BehaviorObservationError(
                f"detector config has unknown fields: {sorted(unknown_root)}"
            )
        if config.get("schema_version", DETECTOR_CONFIG_VERSION) != DETECTOR_CONFIG_VERSION:
            raise BehaviorObservationError("unknown detector config schema version")
        if config.get("contract_version", DETECTOR_CONTRACT_VERSION) != DETECTOR_CONTRACT_VERSION:
            raise BehaviorObservationError("unknown detector contract version")
        rows = config.get("detectors", [])
        if not isinstance(rows, list):
            raise BehaviorObservationError("detector config detectors must be an array")
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, Mapping):
                raise BehaviorObservationError("each detector config must be an object")
            unknown = set(row) - {"detector_id", "detector_version", "enabled", "parameters"}
            if unknown:
                raise BehaviorObservationError(
                    f"detector config has unknown fields: {sorted(unknown)}"
                )
            detector_id = str(row.get("detector_id") or "")
            if detector_id not in definitions:
                raise BehaviorObservationError(f"unknown detector: {detector_id}")
            if detector_id in seen:
                raise BehaviorObservationError(f"duplicate detector config: {detector_id}")
            seen.add(detector_id)
            if str(row.get("detector_version", "1")) != "1":
                raise BehaviorObservationError(
                    f"unknown detector version for {detector_id}"
                )
            if "enabled" in row and not isinstance(row["enabled"], bool):
                raise BehaviorObservationError(f"{detector_id}.enabled must be boolean")
            merged = definitions[detector_id]
            merged["enabled"] = row.get("enabled", merged["enabled"])
            parameters = row.get("parameters", {})
            if not isinstance(parameters, Mapping):
                raise BehaviorObservationError(f"{detector_id}.parameters must be an object")
            merged["parameters"].update(deepcopy(dict(parameters)))

    if selected_detectors:
        selected = {str(item) for item in selected_detectors}
        unknown = selected - set(DETECTOR_IDS)
        if unknown:
            raise BehaviorObservationError(f"unknown detector: {sorted(unknown)}")
        for detector_id in DETECTOR_IDS:
            definitions[detector_id]["enabled"] = detector_id in selected

    cadence = definitions["adjacent_episode_cadence"]["parameters"]
    if cadence:
        raise BehaviorObservationError("adjacent_episode_cadence has no parameters")

    reentry = definitions["same_instrument_reentry_gap"]["parameters"]
    if set(reentry) != {"maximum_gap_seconds"}:
        raise BehaviorObservationError("invalid same_instrument_reentry_gap parameters")
    maximum_gap = _decimal(reentry["maximum_gap_seconds"], "maximum_gap_seconds", nonnegative=True)
    if maximum_gap != maximum_gap.to_integral_value():
        raise BehaviorObservationError("maximum_gap_seconds must be a whole number")
    reentry["maximum_gap_seconds"] = _decimal_text(maximum_gap)

    scale = definitions["episode_scale_transition"]["parameters"]
    if set(scale) != {
        "material_decrease_ratio",
        "material_increase_ratio",
        "metric_priority",
    }:
        raise BehaviorObservationError("invalid episode_scale_transition parameters")
    decrease = _decimal(scale["material_decrease_ratio"], "material_decrease_ratio", nonnegative=True)
    increase = _decimal(scale["material_increase_ratio"], "material_increase_ratio", nonnegative=True)
    if decrease >= 1 or increase <= 1:
        raise BehaviorObservationError("scale thresholds must bracket 1")
    priority = scale["metric_priority"]
    if (
        not isinstance(priority, list)
        or not priority
        or len(set(str(item) for item in priority)) != len(priority)
        or any(str(item) not in _METRIC_KEYS for item in priority)
    ):
        raise BehaviorObservationError("metric_priority is invalid")
    scale["material_decrease_ratio"] = _decimal_text(decrease)
    scale["material_increase_ratio"] = _decimal_text(increase)
    scale["metric_priority"] = [str(item) for item in priority]

    duration = definitions["holding_duration_transition"]["parameters"]
    if set(duration) != {"longer_ratio", "same_instrument_only", "shorter_ratio"}:
        raise BehaviorObservationError("invalid holding_duration_transition parameters")
    if not isinstance(duration["same_instrument_only"], bool):
        raise BehaviorObservationError("same_instrument_only must be boolean")
    shorter = _decimal(duration["shorter_ratio"], "shorter_ratio", nonnegative=True)
    longer = _decimal(duration["longer_ratio"], "longer_ratio", nonnegative=True)
    if shorter >= 1 or longer <= 1:
        raise BehaviorObservationError("duration thresholds must bracket 1")
    duration["shorter_ratio"] = _decimal_text(shorter)
    duration["longer_ratio"] = _decimal_text(longer)

    if not any(item["enabled"] for item in definitions.values()):
        raise BehaviorObservationError("at least one detector must be enabled")
    return {
        "schema_version": DETECTOR_CONFIG_VERSION,
        "contract_version": DETECTOR_CONTRACT_VERSION,
        "detectors": [definitions[item] for item in DETECTOR_IDS],
    }


def _section(projection: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    sections = projection.get("fact_sections")
    if not isinstance(sections, Mapping) or not isinstance(sections.get(name), Mapping):
        raise BehaviorObservationError(f"facts projection is missing {name}")
    return sections[name]


def _facts(projection: Mapping[str, Any], section: str, kind: str) -> list[Mapping[str, Any]]:
    return [
        item
        for item in _section(projection, section).get("facts", [])
        if isinstance(item, Mapping) and item.get("kind") == kind
    ]


def _single_fact(
    projection: Mapping[str, Any], section: str, kind: str
) -> Mapping[str, Any]:
    values = _facts(projection, section, kind)
    if len(values) != 1:
        raise BehaviorObservationError(f"expected exactly one {kind} fact")
    return values[0]


def _fact_ref(
    episode: Mapping[str, Any], section: str, fact: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "episode_id": episode["episode_id"],
        "review_id": episode["review_id"],
        "facts_content_id": episode["facts_content_id"],
        "section": section,
        "fact_id": str(fact.get("fact_id") or ""),
        "kind": str(fact.get("kind") or ""),
        "source_refs": deepcopy(list(fact.get("source_refs", []))),
    }


def _episode_rows(cohort: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for included in cohort.get("included_reviews", []):
        if not isinstance(included, Mapping):
            raise BehaviorObservationError("included review must be an object")
        projection = included.get("facts_projection")
        if not isinstance(projection, Mapping):
            raise BehaviorObservationError("included review has no facts projection")
        lifecycle = _single_fact(projection, "timeline", "episode_lifecycle")
        identity = _single_fact(projection, "security_context", "security_identity")
        lifecycle_data = lifecycle.get("data")
        identity_data = identity.get("data")
        if not isinstance(lifecycle_data, Mapping) or not isinstance(identity_data, Mapping):
            raise BehaviorObservationError("lifecycle or security identity data is malformed")
        opened_at = str(lifecycle_data.get("opened_at") or "")
        _timestamp(opened_at, "episode.opened_at")
        closed_raw = lifecycle_data.get("closed_at")
        closed_at = str(closed_raw) if closed_raw is not None else None
        if closed_at is not None:
            _timestamp(closed_at, "episode.closed_at")
        execution_facts: dict[str, Mapping[str, Any]] = {}
        for fact in _facts(projection, "timeline", "execution_event"):
            data = fact.get("data")
            if isinstance(data, Mapping) and str(data.get("event_id") or ""):
                execution_facts[str(data["event_id"])] = fact
        opening_event_id = str(lifecycle_data.get("opening_event_id") or "")
        closing_raw = lifecycle_data.get("closing_event_id")
        closing_event_id = str(closing_raw) if closing_raw is not None else None
        row = {
            "episode_id": str(included.get("episode_id") or ""),
            "review_id": str(included.get("review_id") or ""),
            "facts_content_id": str(included.get("facts_content_id") or ""),
            "selected_review_content_id": str(included.get("selected_review_content_id") or ""),
            "knowledge_at": str(included.get("knowledge_at") or ""),
            "account_id": str(identity_data.get("account_id") or ""),
            "instrument_id": str(identity_data.get("instrument_id") or "").upper(),
            "currency": str(identity_data.get("currency") or "").upper(),
            "opened_at": opened_at,
            "closed_at": closed_at,
            "status": str(lifecycle_data.get("status") or ""),
            "opening_event_id": opening_event_id,
            "closing_event_id": closing_event_id,
            "maximum_absolute_quantity": str(
                lifecycle_data.get("maximum_absolute_quantity") or ""
            ),
            "projection": projection,
            "lifecycle_fact": lifecycle,
            "identity_fact": identity,
            "opening_event_fact": execution_facts.get(opening_event_id),
            "closing_event_fact": (
                execution_facts.get(closing_event_id)
                if closing_event_id is not None
                else None
            ),
        }
        if not all(row[key] for key in ("episode_id", "review_id", "facts_content_id", "account_id", "instrument_id")):
            raise BehaviorObservationError("episode identity fields must be non-empty")
        rows.append(row)
    return sorted(
        rows,
        key=lambda item: (
            item["account_id"],
            _timestamp(item["opened_at"], "episode.opened_at"),
            item["episode_id"],
            item["review_id"],
            item["facts_content_id"],
        ),
    )


def _subject(episodes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "subject_kind": "episode" if len(episodes) == 1 else "episode_pair",
        "episode_ids": [str(item["episode_id"]) for item in episodes],
        "review_ids": [str(item["review_id"]) for item in episodes],
    }


def _dimensions(episodes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    accounts = sorted({str(item["account_id"]) for item in episodes})
    if len(accounts) != 1:
        raise BehaviorObservationError("detector subject must belong to one account")
    return {
        "account_id": accounts[0],
        "instrument_ids": sorted({str(item["instrument_id"]) for item in episodes}),
    }


def _evaluation_id(
    source_content_id: str,
    detector_id: str,
    detector_version: str,
    subject: Mapping[str, Any],
    parameters: Mapping[str, Any],
) -> str:
    return "evaluation:" + _digest(
        {
            "source_cohort_content_id": source_content_id,
            "detector_id": detector_id,
            "detector_version": detector_version,
            "subject": subject,
            "parameters": parameters,
        }
    )[:32]


def _evaluation(
    source_content_id: str,
    detector: Mapping[str, Any],
    episodes: Sequence[Mapping[str, Any]],
    *,
    status: str,
    reason_codes: Sequence[str],
    facts: Mapping[str, Any],
    evidence: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    subject = _subject(episodes)
    parameters = deepcopy(dict(detector["parameters"]))
    detector_id = str(detector["detector_id"])
    detector_version = str(detector["detector_version"])
    reasons = sorted(set(str(item) for item in reason_codes))
    temporal_order = "valid"
    if "ambiguous_temporal_order" in reasons:
        temporal_order = "ambiguous"
    elif "overlapping_episodes" in reasons:
        temporal_order = "overlap"
    elif "invalid_episode_interval" in reasons:
        temporal_order = "invalid"
    subject_knowledge = "valid"
    if "fact_known_after_subject_event" in reasons:
        subject_knowledge = "late"
    elif len(episodes) == 1 or status == "not_applicable":
        subject_knowledge = "not_applicable"
    dimensions = _dimensions(episodes)
    dimensions["instrument_id"] = (
        dimensions["instrument_ids"][0]
        if len(dimensions["instrument_ids"]) == 1
        else None
    )
    return {
        "evaluation_id": _evaluation_id(
            source_content_id, detector_id, detector_version, subject, parameters
        ),
        "detector_id": detector_id,
        "detector_version": detector_version,
        "subject": subject,
        "subject_kind": subject["subject_kind"],
        "subject_refs": {
            "episode_ids": deepcopy(subject["episode_ids"]),
            "review_ids": deepcopy(subject["review_ids"]),
        },
        "dimensions": dimensions,
        "status": status,
        "reason_codes": reasons,
        "parameters": parameters,
        "facts": deepcopy(dict(facts)),
        "chronology_checks": {
            "knowledge_cutoff": "valid",
            "subject_knowledge": subject_knowledge,
            "temporal_order": temporal_order,
        },
        "evidence_refs": sorted(
            [deepcopy(dict(item)) for item in evidence],
            key=lambda item: (
                item.get("episode_id", ""),
                item.get("review_id", ""),
                item.get("section", ""),
                item.get("fact_id", ""),
            ),
        ),
    }


def _base_evidence(episodes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for episode in episodes:
        rows.append(_fact_ref(episode, "timeline", episode["lifecycle_fact"]))
        rows.append(_fact_ref(episode, "security_context", episode["identity_fact"]))
    return rows


def _append_event_evidence(
    evidence: list[dict[str, Any]],
    episode: Mapping[str, Any],
    field: str,
) -> Mapping[str, Any] | None:
    fact = episode.get(field)
    if isinstance(fact, Mapping):
        evidence.append(_fact_ref(episode, "timeline", fact))
        return fact
    return None


def _fact_known_after(fact: Mapping[str, Any] | None, subject_at: datetime) -> bool | None:
    if not isinstance(fact, Mapping) or fact.get("knowledge_at") is None:
        return None
    return _timestamp(fact["knowledge_at"], "fact.knowledge_at") > subject_at


def _adjacent_pairs(rows: Sequence[Mapping[str, Any]]) -> list[list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["account_id"])].append(row)
    subjects: list[list[Mapping[str, Any]]] = []
    for account_id in sorted(grouped):
        account_rows = grouped[account_id]
        if len(account_rows) == 1:
            subjects.append([account_rows[0]])
        else:
            subjects.extend(
                [[account_rows[index], account_rows[index + 1]] for index in range(len(account_rows) - 1)]
            )
    return subjects


def _cadence_evaluations(
    rows: Sequence[Mapping[str, Any]], detector: Mapping[str, Any], source_content_id: str
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for episodes in _adjacent_pairs(rows):
        evidence = _base_evidence(episodes)
        if len(episodes) == 1:
            result.append(
                _evaluation(
                    source_content_id,
                    detector,
                    episodes,
                    status="not_applicable",
                    reason_codes=["no_adjacent_episode"],
                    facts={"adjacent_episode_count": 0},
                    evidence=evidence,
                )
            )
            continue
        prior, current = episodes
        prior_open_fact = _append_event_evidence(
            evidence, prior, "opening_event_fact"
        )
        _append_event_evidence(evidence, current, "opening_event_fact")
        prior_open = _timestamp(prior["opened_at"], "prior.opened_at")
        current_open = _timestamp(current["opened_at"], "current.opened_at")
        if prior_open == current_open:
            status, reasons = "insufficient_evidence", ["ambiguous_temporal_order"]
            facts = {
                "prior_opened_at": prior["opened_at"],
                "current_opened_at": current["opened_at"],
            }
        elif _fact_known_after(prior_open_fact, current_open) is None:
            status, reasons = "insufficient_evidence", ["missing_required_fact"]
            facts = {
                "prior_opened_at": prior["opened_at"],
                "current_opened_at": current["opened_at"],
                "required_event_id": prior["opening_event_id"],
            }
        elif _fact_known_after(prior_open_fact, current_open):
            status, reasons = "insufficient_evidence", [
                "fact_known_after_subject_event"
            ]
            facts = {
                "prior_opened_at": prior["opened_at"],
                "prior_open_known_at": prior_open_fact["knowledge_at"],
                "current_opened_at": current["opened_at"],
            }
        else:
            overlap = False
            inter_episode_gap: str | None = None
            reasons = []
            if prior.get("closed_at") is not None:
                prior_close = _timestamp(prior["closed_at"], "prior.closed_at")
                inter_episode_gap = _seconds(current_open - prior_close)
                overlap = prior_close > current_open
                if overlap:
                    reasons.append("overlapping_episodes")
            status = "observed"
            facts = {
                "prior_opened_at": prior["opened_at"],
                "current_opened_at": current["opened_at"],
                "anchor_gap_seconds": _seconds(current_open - prior_open),
                "inter_episode_gap_seconds": inter_episode_gap,
                "overlap": overlap,
            }
        result.append(
            _evaluation(
                source_content_id,
                detector,
                episodes,
                status=status,
                reason_codes=reasons,
                facts=facts,
                evidence=evidence,
            )
        )
    return result


def _reentry_evaluations(
    rows: Sequence[Mapping[str, Any]], detector: Mapping[str, Any], source_content_id: str
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    threshold = int(detector["parameters"]["maximum_gap_seconds"])
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["account_id"])].append(row)
    for account_id in sorted(grouped):
        account_rows = grouped[account_id]
        for index, prior in enumerate(account_rows):
            candidates = [
                item
                for item in account_rows[index + 1 :]
                if item["instrument_id"] == prior["instrument_id"]
            ]
            if not candidates:
                episodes = [prior]
                result.append(
                    _evaluation(
                        source_content_id,
                        detector,
                        episodes,
                        status="not_applicable",
                        reason_codes=["no_following_same_instrument_episode"],
                        facts={"following_same_instrument_episode_count": 0},
                        evidence=_base_evidence(episodes),
                    )
                )
                continue
            current = candidates[0]
            episodes = [prior, current]
            evidence = _base_evidence(episodes)
            prior_close_fact = _append_event_evidence(
                evidence, prior, "closing_event_fact"
            )
            _append_event_evidence(evidence, current, "opening_event_fact")
            prior_open = _timestamp(prior["opened_at"], "prior.opened_at")
            current_open = _timestamp(current["opened_at"], "current.opened_at")
            if prior_open == current_open:
                status, reasons = "insufficient_evidence", ["ambiguous_temporal_order"]
                facts = {
                    "prior_opened_at": prior["opened_at"],
                    "current_opened_at": current["opened_at"],
                }
            elif prior.get("closed_at") is None:
                status, reasons = "not_applicable", ["open_episode"]
                facts = {"prior_closed_at": None, "current_opened_at": current["opened_at"]}
            else:
                prior_close = _timestamp(prior["closed_at"], "prior.closed_at")
                gap = int(_seconds(current_open - prior_close))
                facts = {
                    "prior_closed_at": prior["closed_at"],
                    "current_opened_at": current["opened_at"],
                    "gap_seconds": str(gap),
                    "overlap": gap < 0,
                }
                if gap < 0:
                    status, reasons = "insufficient_evidence", ["overlapping_episodes"]
                elif _fact_known_after(prior_close_fact, current_open) is None:
                    status, reasons = "insufficient_evidence", [
                        "missing_required_fact"
                    ]
                    facts["required_event_id"] = prior["closing_event_id"]
                elif _fact_known_after(prior_close_fact, current_open):
                    status, reasons = "insufficient_evidence", [
                        "fact_known_after_subject_event"
                    ]
                    facts["prior_close_known_at"] = prior_close_fact[
                        "knowledge_at"
                    ]
                elif gap <= threshold:
                    status, reasons = "observed", []
                else:
                    status, reasons = "not_observed", ["gap_exceeds_threshold"]
            result.append(
                _evaluation(
                    source_content_id,
                    detector,
                    episodes,
                    status=status,
                    reason_codes=reasons,
                    facts=facts,
                    evidence=evidence,
                )
            )
    return result


def _metric_facts(episode: Mapping[str, Any], metric_key: str) -> list[Mapping[str, Any]]:
    return [
        fact
        for fact in _facts(episode["projection"], "portfolio_context", "portfolio_metric")
        if isinstance(fact.get("data"), Mapping)
        and fact["data"].get("anchor_kind") in {"open", "episode_open"}
        and fact["data"].get("side") == "post"
        and fact["data"].get("metric_key") == metric_key
    ]


def _metric_pair(
    prior: Mapping[str, Any], current: Mapping[str, Any], priority: Sequence[str]
) -> tuple[str, str, dict[str, Any], list[dict[str, Any]]]:
    """Return state, reason, facts, evidence for the first present metric family."""

    for metric_key in priority:
        if metric_key == "maximum_absolute_quantity":
            if prior["instrument_id"] != current["instrument_id"]:
                return "not_comparable", "different_instrument", {"metric_key": metric_key}, []
            try:
                prior_value = _decimal(
                    prior["maximum_absolute_quantity"], "prior.maximum_absolute_quantity"
                )
                current_value = _decimal(
                    current["maximum_absolute_quantity"], "current.maximum_absolute_quantity"
                )
            except BehaviorObservationError:
                return "insufficient_evidence", "missing_required_fact", {"metric_key": metric_key}, []
            if prior_value < 0 or current_value < 0:
                return "not_comparable", "negative_scale_value", {"metric_key": metric_key}, []
            return (
                "comparable",
                "",
                {
                    "metric_key": metric_key,
                    "method": {"method_id": "episode_lifecycle_maximum_absolute_quantity", "method_version": "1"},
                    "unit": "quantity",
                    "prior_value": _decimal_text(prior_value),
                    "current_value": _decimal_text(current_value),
                },
                [],
            )

        prior_facts = _metric_facts(prior, metric_key)
        current_facts = _metric_facts(current, metric_key)
        if not prior_facts and not current_facts:
            continue
        if len(prior_facts) != 1 or len(current_facts) != 1:
            reason = "ambiguous_metric_fact" if len(prior_facts) > 1 or len(current_facts) > 1 else "missing_required_metric"
            return "insufficient_evidence" if reason == "ambiguous_metric_fact" else "not_comparable", reason, {"metric_key": metric_key}, []
        prior_fact, current_fact = prior_facts[0], current_facts[0]
        evidence = [
            _fact_ref(prior, "portfolio_context", prior_fact),
            _fact_ref(current, "portfolio_context", current_fact),
        ]
        prior_data = prior_fact["data"]
        current_data = current_fact["data"]
        states = {
            str(prior_fact.get("availability") or prior_data.get("availability") or "missing"),
            str(current_fact.get("availability") or current_data.get("availability") or "missing"),
        }
        warnings = {
            str(item)
            for fact in (prior_fact, current_fact)
            for item in fact.get("warning_codes", [])
        }
        if states != {"available"}:
            reason = (
                "stale_or_unpriced_source"
                if any("STALE" in item or "UNPRICED" in item for item in warnings)
                else "partial_or_ambiguous_source"
            )
            return "not_comparable", reason, {"metric_key": metric_key, "availability_states": sorted(states)}, evidence
        prior_known_at = prior_fact.get("knowledge_at")
        current_known_at = current_fact.get("knowledge_at")
        if prior_known_at is None or current_known_at is None:
            return "insufficient_evidence", "missing_required_fact", {"metric_key": metric_key}, evidence
        if _timestamp(prior_known_at, "prior_metric.knowledge_at") > _timestamp(
            current["opened_at"], "current.opened_at"
        ):
            return (
                "insufficient_evidence",
                "fact_known_after_subject_event",
                {
                    "metric_key": metric_key,
                    "prior_metric_known_at": prior_known_at,
                    "current_opened_at": current["opened_at"],
                },
                evidence,
            )
        if _timestamp(current_known_at, "current_metric.knowledge_at") > _timestamp(
            current["knowledge_at"], "current_review.knowledge_at"
        ):
            return "insufficient_evidence", "fact_known_after_subject_event", {"metric_key": metric_key}, evidence
        if prior_data.get("method") != current_data.get("method"):
            return "not_comparable", "incomparable_metric_definition", {"metric_key": metric_key}, evidence
        if metric_key == "target_position_value" and prior["currency"] != current["currency"]:
            return "not_comparable", "incomparable_currency", {"metric_key": metric_key}, evidence
        if prior_data.get("unit") != current_data.get("unit"):
            return "not_comparable", "incomparable_unit", {"metric_key": metric_key}, evidence
        if "value" not in prior_data or "value" not in current_data:
            return "not_comparable", "missing_required_metric", {"metric_key": metric_key}, evidence
        try:
            prior_value = _decimal(prior_data["value"], "prior.metric.value")
            current_value = _decimal(current_data["value"], "current.metric.value")
        except BehaviorObservationError:
            return "insufficient_evidence", "invalid_scale_value", {"metric_key": metric_key}, evidence
        if prior_value < 0 or current_value < 0:
            return "not_comparable", "negative_scale_value", {"metric_key": metric_key}, evidence
        return (
            "comparable",
            "",
            {
                "metric_key": metric_key,
                "method": deepcopy(prior_data.get("method")),
                "unit": str(prior_data.get("unit") or ""),
                "currency": prior["currency"] if metric_key == "target_position_value" else None,
                "prior_value": _decimal_text(prior_value),
                "current_value": _decimal_text(current_value),
            },
            evidence,
        )
    return "not_comparable", "missing_required_metric", {"metric_key": None}, []


def _scale_evaluations(
    rows: Sequence[Mapping[str, Any]], detector: Mapping[str, Any], source_content_id: str
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    decrease = _decimal(detector["parameters"]["material_decrease_ratio"], "material_decrease_ratio")
    increase = _decimal(detector["parameters"]["material_increase_ratio"], "material_increase_ratio")
    priority = detector["parameters"]["metric_priority"]
    for episodes in _adjacent_pairs(rows):
        evidence = _base_evidence(episodes)
        if len(episodes) == 1:
            result.append(
                _evaluation(
                    source_content_id,
                    detector,
                    episodes,
                    status="not_applicable",
                    reason_codes=["no_adjacent_episode"],
                    facts={"adjacent_episode_count": 0},
                    evidence=evidence,
                )
            )
            continue
        prior, current = episodes
        if _timestamp(prior["opened_at"], "prior.opened_at") == _timestamp(
            current["opened_at"], "current.opened_at"
        ):
            status, reasons, facts = (
                "insufficient_evidence",
                ["ambiguous_temporal_order"],
                {"prior_opened_at": prior["opened_at"], "current_opened_at": current["opened_at"]},
            )
        else:
            metric_state, reason, facts, metric_evidence = _metric_pair(prior, current, priority)
            evidence.extend(metric_evidence)
            if metric_state != "comparable":
                status, reasons = metric_state, [reason]
            else:
                prior_value = _decimal(facts["prior_value"], "prior_value")
                current_value = _decimal(facts["current_value"], "current_value")
                if prior_value == 0:
                    status, reasons = "not_comparable", ["zero_denominator"]
                else:
                    ratio = current_value / prior_value
                    facts["ratio"] = _decimal_text(ratio)
                    if ratio >= increase:
                        facts["transition"] = "increase"
                        status, reasons = "observed", []
                    elif ratio <= decrease:
                        facts["transition"] = "decrease"
                        status, reasons = "observed", []
                    else:
                        facts["transition"] = "within_thresholds"
                        status, reasons = "not_observed", ["within_thresholds"]
        result.append(
            _evaluation(
                source_content_id,
                detector,
                episodes,
                status=status,
                reason_codes=reasons,
                facts=facts,
                evidence=evidence,
            )
        )
    return result


def _duration_evaluations(
    rows: Sequence[Mapping[str, Any]], detector: Mapping[str, Any], source_content_id: str
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    shorter = _decimal(detector["parameters"]["shorter_ratio"], "shorter_ratio")
    longer = _decimal(detector["parameters"]["longer_ratio"], "longer_ratio")
    same_only = bool(detector["parameters"]["same_instrument_only"])
    for episodes in _adjacent_pairs(rows):
        evidence = _base_evidence(episodes)
        if len(episodes) == 1:
            status, reasons, facts = "not_applicable", ["no_adjacent_episode"], {"adjacent_episode_count": 0}
        else:
            prior, current = episodes
            prior_close_fact = _append_event_evidence(
                evidence, prior, "closing_event_fact"
            )
            _append_event_evidence(evidence, current, "closing_event_fact")
            if _timestamp(prior["opened_at"], "prior.opened_at") == _timestamp(
                current["opened_at"], "current.opened_at"
            ):
                status, reasons, facts = "insufficient_evidence", ["ambiguous_temporal_order"], {
                    "prior_opened_at": prior["opened_at"],
                    "current_opened_at": current["opened_at"],
                }
            elif same_only and prior["instrument_id"] != current["instrument_id"]:
                status, reasons, facts = "not_applicable", ["different_instrument"], {}
            elif prior.get("closed_at") is None or current.get("closed_at") is None:
                status, reasons, facts = "not_applicable", ["open_episode"], {
                    "prior_closed_at": prior.get("closed_at"),
                    "current_closed_at": current.get("closed_at"),
                }
            elif _fact_known_after(
                prior_close_fact,
                _timestamp(current["opened_at"], "current.opened_at"),
            ) is None:
                status, reasons, facts = "insufficient_evidence", [
                    "missing_required_fact"
                ], {
                    "required_event_id": prior["closing_event_id"],
                    "current_opened_at": current["opened_at"],
                }
            elif _fact_known_after(
                prior_close_fact,
                _timestamp(current["opened_at"], "current.opened_at"),
            ):
                status, reasons, facts = "insufficient_evidence", [
                    "fact_known_after_subject_event"
                ], {
                    "prior_close_known_at": prior_close_fact["knowledge_at"],
                    "current_opened_at": current["opened_at"],
                }
            else:
                prior_duration = _timestamp(prior["closed_at"], "prior.closed_at") - _timestamp(
                    prior["opened_at"], "prior.opened_at"
                )
                current_duration = _timestamp(current["closed_at"], "current.closed_at") - _timestamp(
                    current["opened_at"], "current.opened_at"
                )
                prior_seconds = int(_seconds(prior_duration))
                current_seconds = int(_seconds(current_duration))
                facts = {
                    "prior_duration_seconds": str(prior_seconds),
                    "current_duration_seconds": str(current_seconds),
                }
                if prior_seconds < 0 or current_seconds < 0:
                    status, reasons = "insufficient_evidence", ["invalid_episode_interval"]
                elif prior_seconds == 0:
                    status, reasons = "not_comparable", ["zero_denominator"]
                else:
                    ratio = Decimal(current_seconds) / Decimal(prior_seconds)
                    facts["ratio"] = _decimal_text(ratio)
                    if ratio >= longer:
                        facts["transition"] = "longer"
                        status, reasons = "observed", []
                    elif ratio <= shorter:
                        facts["transition"] = "shorter"
                        status, reasons = "observed", []
                    else:
                        facts["transition"] = "within_thresholds"
                        status, reasons = "not_observed", ["within_thresholds"]
        result.append(
            _evaluation(
                source_content_id,
                detector,
                episodes,
                status=status,
                reason_codes=reasons,
                facts=facts,
                evidence=evidence,
            )
        )
    return result


def _evaluation_sort_key(item: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        DETECTOR_IDS.index(str(item.get("detector_id"))),
        str((item.get("dimensions") or {}).get("account_id") or ""),
        tuple((item.get("subject") or {}).get("episode_ids") or []),
        str(item.get("evaluation_id") or ""),
    )


def _counts(evaluations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(str(item.get("status") or "") for item in evaluations)
    detector_counts = Counter(str(item.get("detector_id") or "") for item in evaluations)
    episode_ids = {
        str(value)
        for item in evaluations
        for value in (item.get("subject") or {}).get("episode_ids", [])
    }
    review_ids = {
        str(value)
        for item in evaluations
        for value in (item.get("subject") or {}).get("review_ids", [])
    }
    result = {
        "evaluation_count": len(evaluations),
        "status_counts": {status: status_counts.get(status, 0) for status in EVALUATION_STATUSES},
        "detector_counts": {detector_id: detector_counts.get(detector_id, 0) for detector_id in DETECTOR_IDS},
        "unique_episode_count": len(episode_ids),
        "unique_review_count": len(review_ids),
    }
    for status in EVALUATION_STATUSES:
        result[f"{status}_count"] = status_counts.get(status, 0)
    return result


def build_behavior_observation_set(
    cohort: Mapping[str, Any],
    *,
    detector_config: Mapping[str, Any] | None = None,
    detectors: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build one deterministic P2G-2 artifact from one validated P2G-1 cohort."""

    validation = validate_behavior_cohort(cohort)
    if validation.get("validation_status") == "blocked":
        raise BehaviorObservationError("P2G-1 cohort failed structural validation")
    if cohort.get("schema_version") != COHORT_SCHEMA_VERSION:
        raise BehaviorObservationError("unsupported P2G-1 cohort schema")
    if (cohort.get("release_readiness") or {}).get("status") != "ready":
        raise BehaviorObservationError("P2G-1 cohort is not release-ready")
    if (cohort.get("source_verification") or {}).get("status") != "verified":
        raise BehaviorObservationError("P2G-1 cohort source is not verified")
    config = _normalize_config(detector_config, selected_detectors=detectors)
    rows = _episode_rows(cohort)
    if not rows:
        raise BehaviorObservationError("P2G-1 cohort has no included reviews")
    source_content_id = str(cohort.get("content_id") or "")
    evaluations: list[dict[str, Any]] = []
    definitions = {item["detector_id"]: item for item in config["detectors"]}
    if definitions["adjacent_episode_cadence"]["enabled"]:
        evaluations.extend(_cadence_evaluations(rows, definitions["adjacent_episode_cadence"], source_content_id))
    if definitions["same_instrument_reentry_gap"]["enabled"]:
        evaluations.extend(_reentry_evaluations(rows, definitions["same_instrument_reentry_gap"], source_content_id))
    if definitions["episode_scale_transition"]["enabled"]:
        evaluations.extend(_scale_evaluations(rows, definitions["episode_scale_transition"], source_content_id))
    if definitions["holding_duration_transition"]["enabled"]:
        evaluations.extend(_duration_evaluations(rows, definitions["holding_duration_transition"], source_content_id))
    evaluations.sort(key=_evaluation_sort_key)
    identity = {
        "schema_version": SCHEMA_VERSION,
        "source_cohort_content_id": source_content_id,
        "detector_config": config,
    }
    artifact: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "behavior_observation_set",
        "content_id": "",
        "observation_set_id": "observation-set:" + _digest(identity)[:32],
        "source_cohort": {
            "schema_version": str(cohort.get("schema_version") or ""),
            "cohort_id": str(cohort.get("cohort_id") or ""),
            "content_id": source_content_id,
            "release_readiness": "ready",
            "source_verification": "verified",
        },
        "scope": deepcopy(dict(cohort.get("selection_spec") or {})),
        "detector_contract": config,
        "reason_registry": {
            "registry_version": REASON_REGISTRY_VERSION,
            "reason_codes": list(REASON_CODE_REGISTRY),
        },
        "evaluations": evaluations,
        "counts": _counts(evaluations),
        "release_readiness": {"status": "ready", "blocker_codes": []},
        "source_verification": {
            "status": "verified",
            "validation_mode": "validated_p2g1_cohort",
            "verified_content_id": source_content_id,
        },
        "canonicalization": {
            "builder_version": BUILDER_VERSION,
            "canonical_json": "utf8_sorted_keys_compact_no_float",
            "content_hash": "sha256",
            "sort_version": CANONICAL_SORT_VERSION,
        },
    }
    artifact["content_id"] = _content_id(artifact)
    offline = validate_behavior_observation_set(artifact)
    if offline["validation_status"] == "blocked":
        raise BehaviorObservationError("built P2G-2 artifact failed structural validation")
    return artifact


def _walk_prohibited(value: object, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).lower()
            if any(
                key_text == token
                or key_text.startswith(f"{token}_")
                or key_text.endswith(f"_{token}")
                for token in _PROHIBITED_KEYS
            ):
                found.append(f"{path}.{key}")
            found.extend(_walk_prohibited(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_walk_prohibited(item, f"{path}[{index}]"))
    return found


def _validate_impl(artifact: Mapping[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    try:
        canonical_json_bytes(artifact)
    except Exception as exc:
        findings.append(_finding("blocker", "NON_CANONICAL_VALUE", str(exc)))
        return _validation(findings)
    if artifact.get("schema_version") != SCHEMA_VERSION:
        findings.append(_finding("blocker", "SCHEMA_VERSION_MISMATCH", "unsupported P2G-2 schema"))
    expected_root_keys = {
        "artifact_type",
        "canonicalization",
        "content_id",
        "counts",
        "detector_contract",
        "evaluations",
        "observation_set_id",
        "reason_registry",
        "release_readiness",
        "schema_version",
        "scope",
        "source_cohort",
        "source_verification",
    }
    if set(artifact) != expected_root_keys:
        findings.append(
            _finding(
                "blocker",
                "ROOT_FIELDS_MISMATCH",
                f"root fields differ: {sorted(set(artifact) ^ expected_root_keys)}",
            )
        )
    if artifact.get("artifact_type") != "behavior_observation_set":
        findings.append(
            _finding(
                "blocker",
                "ARTIFACT_TYPE_MISMATCH",
                "artifact_type must be behavior_observation_set",
            )
        )
    if artifact.get("content_id") != _content_id(artifact):
        findings.append(_finding("blocker", "CONTENT_ID_MISMATCH", "content_id does not match canonical bytes"))
    prohibited = _walk_prohibited(artifact)
    if prohibited:
        findings.append(_finding("blocker", "PROHIBITED_SEMANTIC_FIELD", ", ".join(prohibited)))
    source = artifact.get("source_cohort")
    if not isinstance(source, Mapping):
        findings.append(_finding("blocker", "SOURCE_COHORT_MISSING", "source_cohort must be an object"))
        source = {}
    expected_source_keys = {
        "schema_version",
        "cohort_id",
        "content_id",
        "release_readiness",
        "source_verification",
    }
    if set(source) != expected_source_keys:
        findings.append(
            _finding(
                "blocker",
                "SOURCE_COHORT_FIELDS_MISMATCH",
                "source_cohort fields are not exact",
            )
        )
    if source.get("schema_version") != COHORT_SCHEMA_VERSION:
        findings.append(_finding("blocker", "SOURCE_SCHEMA_MISMATCH", "source cohort schema is unsupported"))
    if source.get("release_readiness") != "ready" or source.get("source_verification") != "verified":
        findings.append(_finding("blocker", "SOURCE_STATUS_MISMATCH", "source cohort must remain ready and verified"))
    source_content_id = str(source.get("content_id") or "")
    try:
        config = _normalize_config(
            artifact.get("detector_contract") if isinstance(artifact.get("detector_contract"), Mapping) else None
        )
        if artifact.get("detector_contract") != config:
            findings.append(_finding("blocker", "DETECTOR_CONFIG_NOT_EXPANDED", "detector config is not fully normalized"))
    except Exception as exc:
        findings.append(_finding("blocker", "INVALID_DETECTOR_CONFIG", str(exc)))
        config = {"detectors": []}
    registry = artifact.get("reason_registry")
    if registry != {
        "registry_version": REASON_REGISTRY_VERSION,
        "reason_codes": list(REASON_CODE_REGISTRY),
    }:
        findings.append(_finding("blocker", "REASON_REGISTRY_MISMATCH", "reason registry is not exact"))
    evaluations = artifact.get("evaluations")
    if not isinstance(evaluations, list):
        findings.append(_finding("blocker", "EVALUATIONS_MALFORMED", "evaluations must be an array"))
        evaluations = []
    enabled = {
        str(item.get("detector_id")): item
        for item in config.get("detectors", [])
        if isinstance(item, Mapping) and item.get("enabled") is True
    }
    ids: set[str] = set()
    subjects: set[bytes] = set()
    for index, evaluation in enumerate(evaluations):
        if not isinstance(evaluation, Mapping):
            findings.append(_finding("blocker", "EVALUATION_MALFORMED", f"evaluation {index} must be an object"))
            continue
        detector_id = str(evaluation.get("detector_id") or "")
        expected_evaluation_keys = {
            "chronology_checks",
            "detector_id",
            "detector_version",
            "dimensions",
            "evaluation_id",
            "evidence_refs",
            "facts",
            "parameters",
            "reason_codes",
            "status",
            "subject",
            "subject_kind",
            "subject_refs",
        }
        if set(evaluation) != expected_evaluation_keys:
            findings.append(
                _finding(
                    "blocker",
                    "EVALUATION_FIELDS_MISMATCH",
                    f"evaluation {index} fields are not exact",
                )
            )
        detector = enabled.get(detector_id)
        if detector is None:
            findings.append(_finding("blocker", "UNKNOWN_OR_DISABLED_DETECTOR", detector_id))
            continue
        subject = evaluation.get("subject")
        if not isinstance(subject, Mapping):
            findings.append(_finding("blocker", "SUBJECT_MALFORMED", f"evaluation {index} subject is malformed"))
            continue
        if set(subject) != {"subject_kind", "episode_ids", "review_ids"}:
            findings.append(
                _finding("blocker", "SUBJECT_FIELDS_MISMATCH", f"evaluation {index}")
            )
        if evaluation.get("subject_kind") != subject.get("subject_kind") or evaluation.get(
            "subject_refs"
        ) != {
            "episode_ids": subject.get("episode_ids"),
            "review_ids": subject.get("review_ids"),
        }:
            findings.append(
                _finding("blocker", "SUBJECT_ALIAS_MISMATCH", f"evaluation {index}")
            )
        expected_id = _evaluation_id(
            source_content_id,
            detector_id,
            str(detector.get("detector_version") or ""),
            subject,
            detector.get("parameters") or {},
        )
        if evaluation.get("evaluation_id") != expected_id:
            findings.append(_finding("blocker", "EVALUATION_ID_MISMATCH", f"evaluation {index} id mismatch"))
        if expected_id in ids:
            findings.append(_finding("blocker", "DUPLICATE_EVALUATION_ID", expected_id))
        ids.add(expected_id)
        subject_key = canonical_json_bytes({"detector_id": detector_id, "subject": subject})
        if subject_key in subjects:
            findings.append(_finding("blocker", "DUPLICATE_DETECTOR_SUBJECT", expected_id))
        subjects.add(subject_key)
        if evaluation.get("detector_version") != detector.get("detector_version") or evaluation.get("parameters") != detector.get("parameters"):
            findings.append(_finding("blocker", "DETECTOR_IDENTITY_MISMATCH", expected_id))
        status = str(evaluation.get("status") or "")
        if status not in EVALUATION_STATUSES:
            findings.append(_finding("blocker", "UNKNOWN_EVALUATION_STATUS", expected_id))
        reasons = evaluation.get("reason_codes")
        if not isinstance(reasons, list) or reasons != sorted(set(reasons)) or any(item not in REASON_CODE_REGISTRY for item in reasons):
            findings.append(_finding("blocker", "INVALID_REASON_CODES", expected_id))
        if status in {"not_observed", "insufficient_evidence", "not_comparable", "not_applicable"} and not reasons:
            findings.append(_finding("blocker", "MISSING_REASON_CODE", expected_id))
        if not isinstance(evaluation.get("facts"), Mapping):
            findings.append(_finding("blocker", "FACTS_MALFORMED", expected_id))
        chronology = evaluation.get("chronology_checks")
        if not isinstance(chronology, Mapping) or set(chronology) != {
            "knowledge_cutoff",
            "subject_knowledge",
            "temporal_order",
        } or chronology.get("knowledge_cutoff") != "valid" or chronology.get(
            "temporal_order"
        ) not in {"valid", "ambiguous", "overlap", "invalid"} or chronology.get(
            "subject_knowledge"
        ) not in {"valid", "late", "not_applicable"}:
            findings.append(_finding("blocker", "CHRONOLOGY_CHECKS_MALFORMED", expected_id))
        dimensions = evaluation.get("dimensions")
        if not isinstance(dimensions, Mapping) or set(dimensions) != {
            "account_id",
            "instrument_id",
            "instrument_ids",
        }:
            findings.append(_finding("blocker", "DIMENSIONS_MALFORMED", expected_id))
        elif dimensions.get("instrument_id") != (
            dimensions.get("instrument_ids", [None])[0]
            if len(dimensions.get("instrument_ids", [])) == 1
            else None
        ):
            findings.append(_finding("blocker", "DIMENSION_ALIAS_MISMATCH", expected_id))
        refs = evaluation.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            findings.append(_finding("blocker", "EVIDENCE_REFS_MISSING", expected_id))
        else:
            for ref in refs:
                if not isinstance(ref, Mapping) or not all(
                    str(ref.get(key) or "")
                    for key in ("episode_id", "review_id", "facts_content_id", "section", "fact_id", "kind")
                ) or not isinstance(ref.get("source_refs"), list):
                    findings.append(_finding("blocker", "EVIDENCE_REF_MALFORMED", expected_id))
                    break
    if evaluations and evaluations != sorted(evaluations, key=_evaluation_sort_key):
        findings.append(_finding("blocker", "EVALUATION_ORDER_MISMATCH", "evaluations are not canonically sorted"))
    expected_counts = _counts([item for item in evaluations if isinstance(item, Mapping)])
    if artifact.get("counts") != expected_counts:
        findings.append(_finding("blocker", "COUNTS_MISMATCH", "counts do not match evaluations"))
    if artifact.get("release_readiness") != {"status": "ready", "blocker_codes": []}:
        findings.append(_finding("blocker", "RELEASE_READINESS_MISMATCH", "release readiness must be ready"))
    if artifact.get("source_verification") != {
        "status": "verified",
        "validation_mode": "validated_p2g1_cohort",
        "verified_content_id": source_content_id,
    }:
        findings.append(_finding("blocker", "SOURCE_VERIFICATION_MISMATCH", "source verification is inconsistent"))
    expected_canonicalization = {
        "builder_version": BUILDER_VERSION,
        "canonical_json": "utf8_sorted_keys_compact_no_float",
        "content_hash": "sha256",
        "sort_version": CANONICAL_SORT_VERSION,
    }
    if artifact.get("canonicalization") != expected_canonicalization:
        findings.append(
            _finding(
                "blocker",
                "CANONICALIZATION_MISMATCH",
                "canonicalization metadata is not exact",
            )
        )
    expected_set_id = "observation-set:" + _digest(
        {
            "schema_version": SCHEMA_VERSION,
            "source_cohort_content_id": source_content_id,
            "detector_config": config,
        }
    )[:32]
    if artifact.get("observation_set_id") != expected_set_id:
        findings.append(_finding("blocker", "OBSERVATION_SET_ID_MISMATCH", "observation_set_id mismatch"))
    return _validation(findings)


def validate_behavior_observation_set(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """Validate arbitrary JSON-like P2G-2 input without raising."""

    if not isinstance(artifact, Mapping):
        return _validation([_finding("blocker", "MALFORMED_OBSERVATION_SET", "artifact must be an object")])
    try:
        return _validate_impl(artifact)
    except Exception as exc:
        return _validation([_finding("blocker", "MALFORMED_OBSERVATION_SET", str(exc))])


def replay_validate_behavior_observation_set(
    artifact: Mapping[str, Any], *, cohort: Mapping[str, Any]
) -> dict[str, Any]:
    """Rebuild from the exact P2G-1 source cohort and compare canonical bytes."""

    offline = validate_behavior_observation_set(artifact)
    findings = list(offline.get("findings", []))
    rebuilt_content_id: str | None = None
    if offline.get("validation_status") != "blocked":
        try:
            source = artifact.get("source_cohort") or {}
            if cohort.get("content_id") != source.get("content_id"):
                raise BehaviorObservationError("source cohort content_id mismatch")
            config = artifact.get("detector_contract")
            enabled = [
                str(item.get("detector_id"))
                for item in config.get("detectors", [])
                if isinstance(item, Mapping) and item.get("enabled") is True
            ]
            rebuilt = build_behavior_observation_set(
                cohort, detector_config=config, detectors=enabled
            )
            rebuilt_content_id = str(rebuilt.get("content_id") or "")
            if canonical_json_bytes(rebuilt) != canonical_json_bytes(artifact):
                findings.append(
                    _finding(
                        "blocker",
                        "SOURCE_REPLAY_MISMATCH",
                        "P2G-2 bytes differ from deterministic P2G-1 source replay",
                    )
                )
        except Exception as exc:
            findings.append(_finding("blocker", "SOURCE_REPLAY_ERROR", str(exc)))
    result = _validation(findings, mode="source_replay")
    result["release_readiness"] = str((artifact.get("release_readiness") or {}).get("status") or "blocked")
    result["source_verification"] = {
        "status": (
            "verified"
            if result["validation_status"] != "blocked"
            and result["release_readiness"] == "ready"
            else "blocked"
        ),
        "verified_content_id": str(artifact.get("content_id") or ""),
        "rebuilt_content_id": rebuilt_content_id,
    }
    return result


def save_behavior_observation_set(path: str | Path, artifact: Mapping[str, Any]) -> Path:
    validation = validate_behavior_observation_set(artifact)
    if validation["validation_status"] == "blocked":
        raise BehaviorObservationError("refusing to save an invalid behavior observation set")
    output = Path(path)
    if output.exists():
        raise BehaviorObservationError(f"output already exists: {output}")
    try:
        return atomic_create_bytes(output, pretty_json_bytes(artifact))
    except (ArtifactIOError, FileExistsError) as exc:
        raise BehaviorObservationError(f"output already exists or is invalid: {output}") from exc


def load_behavior_observation_set(path: str | Path) -> dict[str, Any]:
    try:
        return load_json_object(path)
    except ArtifactIOError as exc:
        raise BehaviorObservationError(str(exc)) from exc


def query_behavior_observation_set(
    artifact: Mapping[str, Any],
    *,
    evaluation_id: str | None = None,
    detector_id: str | None = None,
    status: str | None = None,
    episode_id: str | None = None,
    review_id: str | None = None,
    account_id: str | None = None,
    instrument_id: str | None = None,
    reason_code: str | None = None,
    content_id: str | None = None,
) -> list[Any]:
    """Query evaluations with AND semantics across all supplied filters."""

    validation = validate_behavior_observation_set(artifact)
    if validation["validation_status"] == "blocked":
        raise BehaviorObservationError("refusing to query an invalid behavior observation set")
    if content_id is not None and artifact.get("content_id") != content_id:
        return []
    if detector_id is not None and detector_id not in DETECTOR_IDS:
        raise BehaviorObservationError(f"unknown detector: {detector_id}")
    if status is not None and status not in EVALUATION_STATUSES:
        raise BehaviorObservationError(f"unknown status: {status}")
    if reason_code is not None and reason_code not in REASON_CODE_REGISTRY:
        raise BehaviorObservationError(f"unknown reason code: {reason_code}")
    result: list[Any] = []
    for item in artifact.get("evaluations", []):
        subject = item.get("subject") or {}
        dimensions = item.get("dimensions") or {}
        if evaluation_id is not None and item.get("evaluation_id") != evaluation_id:
            continue
        if detector_id is not None and item.get("detector_id") != detector_id:
            continue
        if status is not None and item.get("status") != status:
            continue
        if episode_id is not None and episode_id not in subject.get("episode_ids", []):
            continue
        if review_id is not None and review_id not in subject.get("review_ids", []):
            continue
        if account_id is not None and dimensions.get("account_id") != account_id:
            continue
        if instrument_id is not None and instrument_id.upper() not in dimensions.get("instrument_ids", []):
            continue
        if reason_code is not None and reason_code not in item.get("reason_codes", []):
            continue
        result.append(deepcopy(dict(item)))
    if any(
        value is not None
        for value in (
            evaluation_id,
            detector_id,
            status,
            episode_id,
            review_id,
            account_id,
            instrument_id,
            reason_code,
        )
    ):
        return result
    return [deepcopy(dict(artifact))]


__all__ = [
    "BUILDER_VERSION",
    "DETECTOR_CONFIG_VERSION",
    "DETECTOR_CONTRACT_VERSION",
    "DETECTOR_IDS",
    "EVALUATION_STATUSES",
    "REASON_CODE_REGISTRY",
    "REASON_REGISTRY_VERSION",
    "SCHEMA_VERSION",
    "VALIDATION_SCHEMA_VERSION",
    "BehaviorObservationError",
    "build_behavior_observation_set",
    "load_behavior_observation_set",
    "query_behavior_observation_set",
    "replay_validate_behavior_observation_set",
    "save_behavior_observation_set",
    "validate_behavior_observation_set",
]
