"""P2H Stage 2 Slice A observation-protocol contracts.

This module consumes the canonical P2H Stage 1 candidate, complete human-review
event ledger, historical projection, and exact source artifacts.  It creates an
explicit observation protocol only; it does not generate interventions, execute
experiments, update a profile, or provide trading advice.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from jsonschema import Draft202012Validator

from .artifact_io import canonical_json_bytes
from .behavior_hypothesis_candidates import (
    behavior_hypothesis_review_event_sort_key,
    project_behavior_hypothesis_state,
    replay_validate_behavior_hypothesis_candidate,
    validate_behavior_hypothesis_candidate,
    validate_behavior_hypothesis_review_event,
)
from .episode_interpretation import interpretation_policy_codes


PROTOCOL_SCHEMA_VERSION = "p2h.observation_protocol.v1"
PROTOCOL_REVIEW_EVENT_SCHEMA_VERSION = (
    "p2h.observation_protocol_review_event.v1"
)
PROTOCOL_PROJECTION_SCHEMA_VERSION = "p2h.observation_protocol_projection.v1"
PROTOCOL_VALIDATION_SCHEMA_VERSION = "p2h.observation_protocol.validation.v1"
PROTOCOL_EVENT_VALIDATION_SCHEMA_VERSION = (
    "p2h.observation_protocol_review_event.validation.v1"
)
PROTOCOL_LEDGER_VALIDATION_SCHEMA_VERSION = (
    "p2h.observation_protocol_ledger.validation.v1"
)
PROTOCOL_BUILDER_VERSION = "p2h.observation_protocol.builder.v1"
PROTOCOL_EVENT_BUILDER_VERSION = (
    "p2h.observation_protocol_review_event.builder.v1"
)

PROTOCOL_STATE_SEMANTICS = (
    "Lifecycle state only; completed or expired does not prove or disprove the "
    "hypothesis, diagnose a person, score behavior, update a profile, or provide "
    "trading advice."
)

_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_SCHEMA_PATH = (
    _ROOT / "docs" / "contracts" / "P2H_STAGE2_OBSERVATION_PROTOCOL.schema.json"
)
PROTOCOL_REVIEW_EVENT_SCHEMA_PATH = (
    _ROOT
    / "docs"
    / "contracts"
    / "P2H_STAGE2_OBSERVATION_PROTOCOL_REVIEW_EVENT.schema.json"
)
PROTOCOL_PROJECTION_SCHEMA_PATH = (
    _ROOT
    / "docs"
    / "contracts"
    / "P2H_STAGE2_OBSERVATION_PROTOCOL_PROJECTION.schema.json"
)


class ObservationProtocolError(ValueError):
    """Raised when an observation-protocol contract is violated."""


class ObservationProtocolProjectionError(ObservationProtocolError):
    """Raised when immutable protocol events cannot form one projection."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class ProtocolReviewEventType(str, Enum):
    SUBMITTED = "submitted"
    APPROVED_FOR_OBSERVATION = "approved_for_observation"
    ACTIVATED = "activated"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    SUPERSEDED = "superseded"
    NOTE_ADDED = "note_added"


class ProtocolProjectedStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED_FOR_OBSERVATION = "approved_for_observation"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    SUPERSEDED = "superseded"


@dataclass(frozen=True)
class RequiredFactSpec:
    fact_key: str
    description: str
    acceptable_source_types: tuple[str, ...]


@dataclass(frozen=True)
class ObservationWindow:
    starts_at: str
    ends_at: str
    review_checkpoints: tuple[str, ...]


@dataclass(frozen=True)
class ObservationProtocol:
    protocol_id: str
    canonical_hash: str
    candidate_id: str
    question: str
    required_fact_specs: tuple[RequiredFactSpec, ...]
    observation_window: ObservationWindow
    expiry_at: str


@dataclass(frozen=True)
class ObservationProtocolReviewEvent:
    protocol_review_event_id: str
    canonical_hash: str
    protocol_id: str
    event_type: ProtocolReviewEventType
    effective_at: str
    knowledge_at: str
    reviewed_at: str


@dataclass(frozen=True)
class ObservationProtocolProjection:
    canonical_hash: str
    protocol_id: str
    candidate_id: str
    status: ProtocolProjectedStatus
    expiry_state: str
    as_of: str
    knowledge_cutoff: str
    applied_event_ids: tuple[str, ...]
    last_event_id: str | None


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_CANDIDATE_ID_RE = re.compile(r"^candidate:[0-9a-f]{32}$")
_STAGE1_EVENT_ID_RE = re.compile(r"^review_event:[0-9a-f]{32}$")
_PROTOCOL_ID_RE = re.compile(r"^protocol:[0-9a-f]{32}$")
_PROTOCOL_EVENT_ID_RE = re.compile(
    r"^protocol_review_event:[0-9a-f]{32}$"
)
_FACT_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_REVIEWER_REF_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{2,127}$")
_ABSOLUTE_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\|/|~[\\/]|file://)")
_PROFILE_TEXT_RE = re.compile(
    r"\b(?:profile|personalplaybook|personality)\b|个人画像|人格诊断",
    re.IGNORECASE,
)
_INTERVENTION_TEXT_RE = re.compile(
    r"\b(?:intervention|experiment action)\b|干预方案|实验动作",
    re.IGNORECASE,
)

_PROTOCOL_FIELDS = {
    "schema_version",
    "artifact_type",
    "protocol_id",
    "canonical_hash",
    "created_at",
    "effective_at",
    "knowledge_at",
    "candidate_binding",
    "question",
    "required_fact_specs",
    "observation_window",
    "applicability_conditions",
    "disconfirming_conditions",
    "stop_conditions",
    "expiry_at",
    "missing_evidence_policy",
    "privacy_scope",
    "provenance",
    "state_semantics",
}
_PROTOCOL_DRAFT_FIELDS = {
    "created_at",
    "effective_at",
    "knowledge_at",
    "accepted_projection_as_of",
    "accepted_projection_knowledge_cutoff",
    "question",
    "required_fact_specs",
    "observation_window",
    "applicability_conditions",
    "disconfirming_conditions",
    "stop_conditions",
    "expiry_at",
    "missing_evidence_policy",
    "privacy_scope",
    "provenance",
}
_PROTOCOL_EVENT_FIELDS = {
    "schema_version",
    "artifact_type",
    "protocol_review_event_id",
    "canonical_hash",
    "protocol_id",
    "event_type",
    "reviewed_at",
    "effective_at",
    "knowledge_at",
    "reviewer_ref",
    "rationale",
    "evidence_cutoff",
    "supersedes_event_id",
    "superseded_by_protocol_id",
    "provenance",
}


def _canonical_hash(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _stable_id(prefix: str, value: object) -> str:
    digest = hashlib.sha256(canonical_json_bytes(value)).hexdigest()[:32]
    return f"{prefix}:{digest}"


def _canonical_timestamp(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ObservationProtocolError(
            f"{field} must be a timezone-aware timestamp"
        )
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ObservationProtocolError(f"invalid {field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ObservationProtocolError(f"{field} must be timezone-aware")
    if parsed.microsecond:
        raise ObservationProtocolError(f"{field} must use whole seconds")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ObservationProtocolError(f"{field} must be text")
    normalized = (
        unicodedata.normalize("NFC", value)
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .strip()
    )
    if not normalized:
        raise ObservationProtocolError(f"{field} must not be empty")
    return normalized


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ObservationProtocolError(f"{field} must be an object")
    return value


def _reject_unknown_fields(
    value: Mapping[str, Any], allowed: set[str], field: str
) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ObservationProtocolError(
            f"{field} has unsupported fields: {', '.join(unknown)}"
        )


def _normalized_id(
    value: object, field: str, pattern: re.Pattern[str]
) -> str:
    normalized = _text(value, field)
    if not pattern.fullmatch(normalized):
        raise ObservationProtocolError(f"invalid {field}")
    return normalized


def _optional_id(
    value: object, field: str, pattern: re.Pattern[str]
) -> str | None:
    if value is None:
        return None
    return _normalized_id(value, field, pattern)


def _sha256(value: object, field: str) -> str:
    normalized = _text(value, field)
    if not _SHA256_RE.fullmatch(normalized):
        raise ObservationProtocolError(f"{field} must be a sha256 content ID")
    return normalized


def _text_list(
    value: object,
    field: str,
    *,
    required: bool,
    preserve_order: bool,
) -> list[str]:
    if not isinstance(value, list):
        raise ObservationProtocolError(f"{field} must be an array")
    normalized = [_text(item, f"{field}[]") for item in value]
    if required and not normalized:
        raise ObservationProtocolError(f"{field} must not be empty")
    if len(set(normalized)) != len(normalized):
        raise ObservationProtocolError(f"{field} contains duplicates")
    return normalized if preserve_order else sorted(normalized)


def _source_locator(value: object, field: str) -> str:
    locator = _text(value, field)
    if _ABSOLUTE_PATH_RE.search(locator):
        raise ObservationProtocolError(f"{field} must be a relative locator")
    return locator


def _canonical_unique_mappings(
    values: Sequence[dict[str, Any]], field: str
) -> list[dict[str, Any]]:
    keyed = {canonical_json_bytes(item): item for item in values}
    if len(keyed) != len(values):
        raise ObservationProtocolError(f"{field} contains duplicates")
    return [keyed[key] for key in sorted(keyed)]


def _normalize_fact_specs(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ObservationProtocolError("required_fact_specs must be a non-empty array")
    specs: list[dict[str, Any]] = []
    keys: set[str] = set()
    for index, item in enumerate(value):
        spec = _mapping(item, f"required_fact_specs[{index}]")
        _reject_unknown_fields(
            spec,
            {"fact_key", "description", "acceptable_source_types"},
            f"required_fact_specs[{index}]",
        )
        fact_key = _text(spec.get("fact_key"), f"required_fact_specs[{index}].fact_key")
        if not _FACT_KEY_RE.fullmatch(fact_key):
            raise ObservationProtocolError("required_fact_specs.fact_key is invalid")
        if fact_key in keys:
            raise ObservationProtocolError("required_fact_specs has duplicate fact_key")
        keys.add(fact_key)
        specs.append(
            {
                "fact_key": fact_key,
                "description": _text(
                    spec.get("description"),
                    f"required_fact_specs[{index}].description",
                ),
                "acceptable_source_types": _text_list(
                    spec.get("acceptable_source_types"),
                    f"required_fact_specs[{index}].acceptable_source_types",
                    required=True,
                    preserve_order=False,
                ),
            }
        )
    return sorted(specs, key=lambda item: item["fact_key"])


def _normalize_window(value: object) -> dict[str, Any]:
    window = _mapping(value, "observation_window")
    _reject_unknown_fields(
        window,
        {"starts_at", "ends_at", "review_checkpoints"},
        "observation_window",
    )
    starts_at = _canonical_timestamp(
        window.get("starts_at"), "observation_window.starts_at"
    )
    ends_at = _canonical_timestamp(
        window.get("ends_at"), "observation_window.ends_at"
    )
    if _datetime(ends_at) <= _datetime(starts_at):
        raise ObservationProtocolError("observation_window.ends_at must follow starts_at")
    raw_checkpoints = window.get("review_checkpoints")
    if not isinstance(raw_checkpoints, list) or not raw_checkpoints:
        raise ObservationProtocolError(
            "observation_window.review_checkpoints must be non-empty"
        )
    checkpoints = sorted(
        _canonical_timestamp(item, "observation_window.review_checkpoints[]")
        for item in raw_checkpoints
    )
    if len(set(checkpoints)) != len(checkpoints):
        raise ObservationProtocolError("review_checkpoints contains duplicates")
    if any(item < starts_at or item > ends_at for item in checkpoints):
        raise ObservationProtocolError(
            "review_checkpoints must fall within the observation window"
        )
    return {
        "starts_at": starts_at,
        "ends_at": ends_at,
        "review_checkpoints": checkpoints,
    }


def _normalize_missing_policy(value: object) -> dict[str, Any]:
    policy = _mapping(value, "missing_evidence_policy")
    _reject_unknown_fields(
        policy,
        {"on_missing", "on_partial", "on_ambiguous", "allow_inference"},
        "missing_evidence_policy",
    )
    expected = {
        "on_missing": "preserve_missing",
        "on_partial": "preserve_partial",
        "on_ambiguous": "preserve_ambiguous",
        "allow_inference": False,
    }
    if dict(policy) != expected:
        raise ObservationProtocolError(
            "missing_evidence_policy must preserve missing, partial, and ambiguous states"
        )
    return expected


def _normalize_privacy_scope(value: object) -> dict[str, Any]:
    scope = _mapping(value, "privacy_scope")
    _reject_unknown_fields(
        scope,
        {
            "data_classification",
            "allowed_source_kinds",
            "prohibited_data_kinds",
            "contains_direct_identifiers",
        },
        "privacy_scope",
    )
    classification = _text(
        scope.get("data_classification"), "privacy_scope.data_classification"
    )
    if classification not in {"synthetic", "private_review_sidecar"}:
        raise ObservationProtocolError("privacy_scope.data_classification is unsupported")
    allowed = _text_list(
        scope.get("allowed_source_kinds"),
        "privacy_scope.allowed_source_kinds",
        required=True,
        preserve_order=False,
    )
    prohibited = _text_list(
        scope.get("prohibited_data_kinds"),
        "privacy_scope.prohibited_data_kinds",
        required=True,
        preserve_order=False,
    )
    required_prohibitions = {
        "broker_export",
        "credentials",
        "order_execution",
        "portfolio_sqlite",
    }
    if not required_prohibitions.issubset(prohibited):
        raise ObservationProtocolError(
            "privacy_scope must prohibit portfolio_sqlite, broker_export, credentials, and order_execution"
        )
    if scope.get("contains_direct_identifiers") is not False:
        raise ObservationProtocolError(
            "privacy_scope.contains_direct_identifiers must be false"
        )
    return {
        "data_classification": classification,
        "allowed_source_kinds": allowed,
        "prohibited_data_kinds": prohibited,
        "contains_direct_identifiers": False,
    }


def _normalize_protocol_provenance(value: object) -> dict[str, Any]:
    provenance = _mapping(value, "provenance")
    _reject_unknown_fields(
        provenance,
        {"submitter_kind", "human_confirmed", "source_locator", "tool_version"},
        "provenance",
    )
    submitter_kind = _text(provenance.get("submitter_kind"), "provenance.submitter_kind")
    if submitter_kind not in {"human", "agent_assisted"}:
        raise ObservationProtocolError("provenance.submitter_kind is unsupported")
    if provenance.get("human_confirmed") is not True:
        raise ObservationProtocolError("protocol draft requires explicit human confirmation")
    return {
        "submitter_kind": submitter_kind,
        "human_confirmed": True,
        "source_locator": _source_locator(
            provenance.get("source_locator"), "provenance.source_locator"
        ),
        "tool_version": _text(
            provenance.get("tool_version", PROTOCOL_BUILDER_VERSION),
            "provenance.tool_version",
        ),
    }


def _normalize_source_refs(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ObservationProtocolError("candidate_source_refs must be non-empty")
    refs: list[dict[str, Any]] = []
    content_ids: set[str] = set()
    for index, item in enumerate(value):
        ref = _mapping(item, f"candidate_source_refs[{index}]")
        _reject_unknown_fields(
            ref,
            {"schema_version", "artifact_type", "content_id", "source_locators"},
            f"candidate_source_refs[{index}]",
        )
        content_id = _sha256(
            ref.get("content_id"), f"candidate_source_refs[{index}].content_id"
        )
        if content_id in content_ids:
            raise ObservationProtocolError("candidate_source_refs has duplicate content_id")
        content_ids.add(content_id)
        raw_locators = ref.get("source_locators")
        if not isinstance(raw_locators, list) or not raw_locators:
            raise ObservationProtocolError("candidate_source_refs.source_locators is required")
        locators = sorted(
            _source_locator(item, f"candidate_source_refs[{index}].source_locators[]")
            for item in raw_locators
        )
        if len(set(locators)) != len(locators):
            raise ObservationProtocolError("candidate source locators contain duplicates")
        refs.append(
            {
                "schema_version": _text(
                    ref.get("schema_version"),
                    f"candidate_source_refs[{index}].schema_version",
                ),
                "artifact_type": _text(
                    ref.get("artifact_type"),
                    f"candidate_source_refs[{index}].artifact_type",
                ),
                "content_id": content_id,
                "source_locators": locators,
            }
        )
    return _canonical_unique_mappings(refs, "candidate_source_refs")


def _normalize_stage1_event_refs(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) < 2:
        raise ObservationProtocolError("review_event_refs requires the complete accepted ledger")
    refs: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, item in enumerate(value):
        ref = _mapping(item, f"review_event_refs[{index}]")
        _reject_unknown_fields(
            ref,
            {
                "review_event_id",
                "canonical_hash",
                "event_type",
                "effective_at",
                "knowledge_at",
                "reviewed_at",
            },
            f"review_event_refs[{index}]",
        )
        event_id = _normalized_id(
            ref.get("review_event_id"),
            f"review_event_refs[{index}].review_event_id",
            _STAGE1_EVENT_ID_RE,
        )
        if event_id in ids:
            raise ObservationProtocolError("review_event_refs contains duplicate event IDs")
        ids.add(event_id)
        refs.append(
            {
                "review_event_id": event_id,
                "canonical_hash": _sha256(
                    ref.get("canonical_hash"),
                    f"review_event_refs[{index}].canonical_hash",
                ),
                "event_type": _text(
                    ref.get("event_type"), f"review_event_refs[{index}].event_type"
                ),
                "effective_at": _canonical_timestamp(
                    ref.get("effective_at"),
                    f"review_event_refs[{index}].effective_at",
                ),
                "knowledge_at": _canonical_timestamp(
                    ref.get("knowledge_at"),
                    f"review_event_refs[{index}].knowledge_at",
                ),
                "reviewed_at": _canonical_timestamp(
                    ref.get("reviewed_at"),
                    f"review_event_refs[{index}].reviewed_at",
                ),
            }
        )
    return sorted(
        refs,
        key=lambda item: (
            item["effective_at"],
            item["knowledge_at"],
            item["reviewed_at"],
            item["review_event_id"],
        ),
    )


def _normalize_accepted_projection(value: object) -> dict[str, Any]:
    projection = _mapping(value, "candidate_binding.accepted_projection")
    allowed = {
        "schema_version",
        "artifact_type",
        "candidate_id",
        "status",
        "as_of",
        "knowledge_cutoff",
        "applied_event_ids",
        "last_event_id",
        "state_semantics",
        "projection_hash",
    }
    _reject_unknown_fields(projection, allowed, "candidate_binding.accepted_projection")
    if projection.get("schema_version") != "p2h.behavior_hypothesis_projection.v1":
        raise ObservationProtocolError("accepted projection schema_version is invalid")
    if projection.get("artifact_type") != "behavior_hypothesis_projection":
        raise ObservationProtocolError("accepted projection artifact_type is invalid")
    if projection.get("status") != "accepted_for_observation":
        raise ObservationProtocolError("accepted projection status is required")
    raw_ids = projection.get("applied_event_ids")
    if not isinstance(raw_ids, list) or len(raw_ids) < 2:
        raise ObservationProtocolError("accepted projection requires applied events")
    applied_ids = [
        _normalized_id(item, "accepted_projection.applied_event_ids[]", _STAGE1_EVENT_ID_RE)
        for item in raw_ids
    ]
    if len(set(applied_ids)) != len(applied_ids):
        raise ObservationProtocolError("accepted projection applied_event_ids contains duplicates")
    last_event_id = _normalized_id(
        projection.get("last_event_id"),
        "accepted_projection.last_event_id",
        _STAGE1_EVENT_ID_RE,
    )
    if last_event_id != applied_ids[-1]:
        raise ObservationProtocolError("accepted projection last_event_id is inconsistent")
    normalized = {
        "schema_version": "p2h.behavior_hypothesis_projection.v1",
        "artifact_type": "behavior_hypothesis_projection",
        "candidate_id": _normalized_id(
            projection.get("candidate_id"),
            "accepted_projection.candidate_id",
            _CANDIDATE_ID_RE,
        ),
        "status": "accepted_for_observation",
        "as_of": _canonical_timestamp(projection.get("as_of"), "accepted_projection.as_of"),
        "knowledge_cutoff": _canonical_timestamp(
            projection.get("knowledge_cutoff"), "accepted_projection.knowledge_cutoff"
        ),
        "applied_event_ids": applied_ids,
        "last_event_id": last_event_id,
        "state_semantics": _text(
            projection.get("state_semantics"), "accepted_projection.state_semantics"
        ),
        "projection_hash": _sha256(
            projection.get("projection_hash"), "accepted_projection.projection_hash"
        ),
    }
    material = deepcopy(normalized)
    declared_hash = material.pop("projection_hash")
    if _canonical_hash(material) != declared_hash:
        raise ObservationProtocolError("accepted projection hash does not match content")
    return normalized


def _normalize_candidate_binding(value: object) -> dict[str, Any]:
    binding = _mapping(value, "candidate_binding")
    _reject_unknown_fields(
        binding,
        {
            "candidate_id",
            "candidate_canonical_hash",
            "candidate_source_refs",
            "review_event_refs",
            "review_event_set_hash",
            "accepted_projection",
            "source_replay_status",
        },
        "candidate_binding",
    )
    candidate_id = _normalized_id(
        binding.get("candidate_id"), "candidate_binding.candidate_id", _CANDIDATE_ID_RE
    )
    event_refs = _normalize_stage1_event_refs(binding.get("review_event_refs"))
    event_set_hash = _sha256(
        binding.get("review_event_set_hash"), "candidate_binding.review_event_set_hash"
    )
    if _canonical_hash(event_refs) != event_set_hash:
        raise ObservationProtocolError("review_event_set_hash does not match event refs")
    projection = _normalize_accepted_projection(binding.get("accepted_projection"))
    if projection["candidate_id"] != candidate_id:
        raise ObservationProtocolError("accepted projection targets another candidate")
    if binding.get("source_replay_status") != "verified":
        raise ObservationProtocolError("candidate source replay must be verified")
    return {
        "candidate_id": candidate_id,
        "candidate_canonical_hash": _sha256(
            binding.get("candidate_canonical_hash"),
            "candidate_binding.candidate_canonical_hash",
        ),
        "candidate_source_refs": _normalize_source_refs(
            binding.get("candidate_source_refs")
        ),
        "review_event_refs": event_refs,
        "review_event_set_hash": event_set_hash,
        "accepted_projection": projection,
        "source_replay_status": "verified",
    }


def _normalize_protocol_common(
    value: Mapping[str, Any], *, candidate_binding: Mapping[str, Any]
) -> dict[str, Any]:
    created_at = _canonical_timestamp(value.get("created_at"), "created_at")
    effective_at = _canonical_timestamp(value.get("effective_at"), "effective_at")
    knowledge_at = _canonical_timestamp(value.get("knowledge_at"), "knowledge_at")
    if _datetime(effective_at) > _datetime(knowledge_at):
        raise ObservationProtocolError("effective_at cannot be later than knowledge_at")
    if _datetime(knowledge_at) > _datetime(created_at):
        raise ObservationProtocolError("knowledge_at cannot be later than created_at")
    projection = candidate_binding["accepted_projection"]
    if projection["as_of"] > effective_at:
        raise ObservationProtocolError("protocol cannot be effective before accepted projection")
    if projection["knowledge_cutoff"] > knowledge_at:
        raise ObservationProtocolError("protocol cannot use future Stage 1 knowledge")
    window = _normalize_window(value.get("observation_window"))
    if window["starts_at"] < effective_at:
        raise ObservationProtocolError("observation window cannot start before protocol")
    expiry_at = _canonical_timestamp(value.get("expiry_at"), "expiry_at")
    if expiry_at < window["ends_at"]:
        raise ObservationProtocolError("expiry_at cannot precede observation_window.ends_at")
    return {
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "artifact_type": "observation_protocol",
        "created_at": created_at,
        "effective_at": effective_at,
        "knowledge_at": knowledge_at,
        "candidate_binding": deepcopy(dict(candidate_binding)),
        "question": _text(value.get("question"), "question"),
        "required_fact_specs": _normalize_fact_specs(value.get("required_fact_specs")),
        "observation_window": window,
        "applicability_conditions": _text_list(
            value.get("applicability_conditions"),
            "applicability_conditions",
            required=True,
            preserve_order=True,
        ),
        "disconfirming_conditions": _text_list(
            value.get("disconfirming_conditions"),
            "disconfirming_conditions",
            required=True,
            preserve_order=True,
        ),
        "stop_conditions": _text_list(
            value.get("stop_conditions"),
            "stop_conditions",
            required=True,
            preserve_order=True,
        ),
        "expiry_at": expiry_at,
        "missing_evidence_policy": _normalize_missing_policy(
            value.get("missing_evidence_policy")
        ),
        "privacy_scope": _normalize_privacy_scope(value.get("privacy_scope")),
        "provenance": _normalize_protocol_provenance(value.get("provenance")),
        "state_semantics": PROTOCOL_STATE_SEMANTICS,
    }


def _protocol_from_material(material: Mapping[str, Any]) -> dict[str, Any]:
    protocol = deepcopy(dict(material))
    protocol["protocol_id"] = _stable_id("protocol", material)
    protocol["canonical_hash"] = _canonical_hash(material)
    return protocol


def _rebuild_protocol(protocol: Mapping[str, Any]) -> dict[str, Any]:
    _reject_unknown_fields(protocol, _PROTOCOL_FIELDS, "protocol")
    binding = _normalize_candidate_binding(protocol.get("candidate_binding"))
    return _protocol_from_material(
        _normalize_protocol_common(protocol, candidate_binding=binding)
    )


def _source_content_id(source: Mapping[str, Any]) -> str:
    declared = source.get("content_id")
    if not isinstance(declared, str) or not _SHA256_RE.fullmatch(declared):
        raise ObservationProtocolError("source artifact requires a sha256 content_id")
    material = deepcopy(dict(source))
    material.pop("content_id", None)
    if _canonical_hash(material) != declared:
        raise ObservationProtocolError("source artifact content_id does not match content")
    return declared


def _candidate_source_refs(
    candidate: Mapping[str, Any], source_artifacts: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    evidence = list(candidate.get("supporting_evidence") or []) + list(
        candidate.get("counterevidence") or []
    )
    by_hash: dict[str, list[str]] = {}
    for ref in evidence:
        if isinstance(ref, Mapping):
            by_hash.setdefault(str(ref.get("canonical_hash") or ""), []).append(
                _source_locator(ref.get("source_locator"), "candidate evidence source_locator")
            )
    refs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in source_artifacts:
        if not isinstance(source, Mapping):
            raise ObservationProtocolError("source artifact must be an object")
        content_id = _source_content_id(source)
        if content_id in seen:
            raise ObservationProtocolError("source artifacts contain duplicate content_id")
        seen.add(content_id)
        locators = sorted(set(by_hash.get(content_id, [])))
        if not locators:
            raise ObservationProtocolError(
                "every explicit source artifact must be referenced by the candidate"
            )
        refs.append(
            {
                "schema_version": _text(
                    source.get("schema_version"), "source.schema_version"
                ),
                "artifact_type": _text(
                    source.get("artifact_type"), "source.artifact_type"
                ),
                "content_id": content_id,
                "source_locators": locators,
            }
        )
    return _canonical_unique_mappings(refs, "candidate_source_refs")


def _stage1_review_event_refs(
    candidate_id: str, review_events: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    by_id: dict[str, tuple[bytes, Mapping[str, Any]]] = {}
    for event in review_events:
        if not isinstance(event, Mapping):
            raise ObservationProtocolError("Stage 1 review event must be an object")
        event_id = str(event.get("review_event_id") or "")
        serialized = canonical_json_bytes(event)
        previous = by_id.get(event_id)
        if previous is not None:
            if previous[0] != serialized:
                raise ObservationProtocolError(
                    "Stage 1 review event ID has divergent payloads"
                )
            continue
        validation = validate_behavior_hypothesis_review_event(event)
        if validation["validation_status"] != "accepted":
            raise ObservationProtocolError(
                "Stage 1 review event failed validation: "
                + ", ".join(validation["finding_codes"])
            )
        if event.get("candidate_id") != candidate_id:
            raise ObservationProtocolError("Stage 1 review event targets another candidate")
        by_id[event_id] = (serialized, event)
    ordered = sorted(
        (item[1] for item in by_id.values()),
        key=behavior_hypothesis_review_event_sort_key,
    )
    refs = [
        {
            "review_event_id": event["review_event_id"],
            "canonical_hash": event["canonical_hash"],
            "event_type": event["event_type"],
            "effective_at": event["effective_at"],
            "knowledge_at": event["knowledge_at"],
            "reviewed_at": event["reviewed_at"],
        }
        for event in ordered
    ]
    return _normalize_stage1_event_refs(refs)


def _accepted_projection_binding(projection: Mapping[str, Any]) -> dict[str, Any]:
    if projection.get("status") != "accepted_for_observation":
        raise ObservationProtocolError(
            "Stage 1 projection must be accepted_for_observation"
        )
    material = deepcopy(dict(projection))
    return _normalize_accepted_projection(
        {**material, "projection_hash": _canonical_hash(material)}
    )


def _build_stage1_binding(
    *,
    candidate: Mapping[str, Any],
    review_events: Sequence[Mapping[str, Any]],
    candidate_source_artifacts: Sequence[Mapping[str, Any]],
    as_of: str,
    knowledge_cutoff: str,
) -> dict[str, Any]:
    candidate_validation = validate_behavior_hypothesis_candidate(candidate)
    if candidate_validation["validation_status"] != "accepted":
        raise ObservationProtocolError(
            "Stage 1 candidate failed validation: "
            + ", ".join(candidate_validation["finding_codes"])
        )
    source_replay = replay_validate_behavior_hypothesis_candidate(
        candidate, source_artifacts=candidate_source_artifacts
    )
    if (
        source_replay["validation_status"] != "accepted"
        or source_replay["source_verification"]["status"] != "verified"
    ):
        raise ObservationProtocolError(
            "Stage 1 candidate source replay failed: "
            + ", ".join(source_replay["finding_codes"])
        )
    event_refs = _stage1_review_event_refs(
        str(candidate["candidate_id"]), review_events
    )
    projection = project_behavior_hypothesis_state(
        candidate,
        review_events,
        as_of=_canonical_timestamp(as_of, "accepted_projection_as_of"),
        knowledge_cutoff=_canonical_timestamp(
            knowledge_cutoff, "accepted_projection_knowledge_cutoff"
        ),
    )
    accepted_projection = _accepted_projection_binding(projection)
    return {
        "candidate_id": candidate["candidate_id"],
        "candidate_canonical_hash": candidate["canonical_hash"],
        "candidate_source_refs": _candidate_source_refs(
            candidate, candidate_source_artifacts
        ),
        "review_event_refs": event_refs,
        "review_event_set_hash": _canonical_hash(event_refs),
        "accepted_projection": accepted_projection,
        "source_replay_status": "verified",
    }


def build_observation_protocol(
    draft: Mapping[str, Any],
    *,
    candidate: Mapping[str, Any],
    review_events: Sequence[Mapping[str, Any]],
    candidate_source_artifacts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build one explicit, source-bound observation protocol deterministically."""

    _reject_unknown_fields(draft, _PROTOCOL_DRAFT_FIELDS, "protocol_draft")
    binding = _build_stage1_binding(
        candidate=candidate,
        review_events=review_events,
        candidate_source_artifacts=candidate_source_artifacts,
        as_of=_text(
            draft.get("accepted_projection_as_of"),
            "accepted_projection_as_of",
        ),
        knowledge_cutoff=_text(
            draft.get("accepted_projection_knowledge_cutoff"),
            "accepted_projection_knowledge_cutoff",
        ),
    )
    return _protocol_from_material(
        _normalize_protocol_common(draft, candidate_binding=binding)
    )


def _protocol_draft_from_artifact(protocol: Mapping[str, Any]) -> dict[str, Any]:
    binding = _mapping(protocol.get("candidate_binding"), "candidate_binding")
    projection = _mapping(binding.get("accepted_projection"), "accepted_projection")
    return {
        "created_at": protocol.get("created_at"),
        "effective_at": protocol.get("effective_at"),
        "knowledge_at": protocol.get("knowledge_at"),
        "accepted_projection_as_of": projection.get("as_of"),
        "accepted_projection_knowledge_cutoff": projection.get("knowledge_cutoff"),
        "question": protocol.get("question"),
        "required_fact_specs": protocol.get("required_fact_specs"),
        "observation_window": protocol.get("observation_window"),
        "applicability_conditions": protocol.get("applicability_conditions"),
        "disconfirming_conditions": protocol.get("disconfirming_conditions"),
        "stop_conditions": protocol.get("stop_conditions"),
        "expiry_at": protocol.get("expiry_at"),
        "missing_evidence_policy": protocol.get("missing_evidence_policy"),
        "privacy_scope": protocol.get("privacy_scope"),
        "provenance": protocol.get("provenance"),
    }


def _json_path(parts: Iterable[object]) -> str:
    return "$" + "".join(
        f"[{part}]" if isinstance(part, int) else f".{part}" for part in parts
    )


def _finding(code: str, message: str, path: str = "$") -> dict[str, str]:
    return {"severity": "blocker", "code": code, "message": message, "path": path}


def _canonical_findings(values: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    keyed = {
        (
            str(item.get("severity") or "blocker"),
            str(item.get("code") or "UNKNOWN"),
            str(item.get("path") or "$"),
            str(item.get("message") or ""),
        ): {
            "severity": str(item.get("severity") or "blocker"),
            "code": str(item.get("code") or "UNKNOWN"),
            "message": str(item.get("message") or ""),
            "path": str(item.get("path") or "$"),
        }
        for item in values
    }
    return [keyed[key] for key in sorted(keyed)]


@lru_cache(maxsize=None)
def _schema_validator(path: str) -> Draft202012Validator:
    schema = json.loads(Path(path).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _schema_findings(
    value: Mapping[str, Any], path: Path, code: str
) -> list[dict[str, str]]:
    return [
        _finding(code, error.message, _json_path(error.absolute_path))
        for error in sorted(
            _schema_validator(str(path)).iter_errors(value),
            key=lambda item: (list(item.absolute_path), item.message),
        )
    ]


def _validation(
    schema_version: str,
    findings: Sequence[Mapping[str, str]],
    *,
    identity: Mapping[str, Any],
    source_status: str = "not_requested",
) -> dict[str, Any]:
    normalized = _canonical_findings(findings)
    return {
        "schema_version": schema_version,
        "validation_status": "blocked" if normalized else "accepted",
        **dict(identity),
        "source_verification": {"status": source_status},
        "findings": normalized,
        "finding_codes": sorted({item["code"] for item in normalized}),
    }


def _walk_text(value: object) -> list[str]:
    values: list[str] = []
    if isinstance(value, str):
        values.append(value)
    elif isinstance(value, Mapping):
        for child in value.values():
            values.extend(_walk_text(child))
    elif isinstance(value, list):
        for child in value:
            values.extend(_walk_text(child))
    return values


def _walk_keys(value: object) -> list[str]:
    values: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            values.append(str(key).lower())
            values.extend(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            values.extend(_walk_keys(child))
    return values


def _protocol_policy_findings(protocol: Mapping[str, Any]) -> list[dict[str, str]]:
    authored = {
        "question": protocol.get("question"),
        "required_fact_specs": protocol.get("required_fact_specs"),
        "applicability_conditions": protocol.get("applicability_conditions"),
        "disconfirming_conditions": protocol.get("disconfirming_conditions"),
        "stop_conditions": protocol.get("stop_conditions"),
    }
    findings: list[dict[str, str]] = []
    for code in sorted(interpretation_policy_codes(authored)):
        findings.append(
            _finding(
                code,
                "protocol-authored content violates the shared no-diagnosis/advice/score policy",
                "$.question",
            )
        )
    authored_text = "\n".join(_walk_text(authored))
    if _PROFILE_TEXT_RE.search(authored_text):
        findings.append(
            _finding(
                "POLICY_PROFILE_WRITE",
                "protocol content cannot create or update a profile",
                "$.question",
            )
        )
    if _INTERVENTION_TEXT_RE.search(authored_text):
        findings.append(
            _finding(
                "POLICY_INTERVENTION_ACTION",
                "Slice A protocol content cannot define an intervention or experiment action",
                "$.question",
            )
        )
    keys = _walk_keys(protocol)
    if any("profile" in key or "personal_playbook" in key for key in keys):
        findings.append(
            _finding("POLICY_PROFILE_WRITE", "profile fields are forbidden")
        )
    if any("intervention" in key or "experiment_action" in key for key in keys):
        findings.append(
            _finding(
                "POLICY_INTERVENTION_ACTION",
                "intervention and experiment-action fields are forbidden",
            )
        )
    if any(
        token in key
        for key in keys
        for token in ("position_size", "expected_return", "order_execution")
    ):
        findings.append(
            _finding("POLICY_DIRECT_ADVICE", "execution and advice fields are forbidden")
        )
    return findings


def validate_observation_protocol(protocol: Mapping[str, Any]) -> dict[str, Any]:
    """Validate canonical structure, identity, time, and policy offline."""

    findings = _schema_findings(
        protocol, PROTOCOL_SCHEMA_PATH, "PROTOCOL_SCHEMA_INVALID"
    )
    try:
        rebuilt = _rebuild_protocol(protocol)
    except (ObservationProtocolError, TypeError, ValueError) as exc:
        findings.append(_finding("PROTOCOL_SEMANTIC_INVALID", str(exc)))
        rebuilt = None
    if rebuilt is not None and dict(protocol) != rebuilt:
        if protocol.get("protocol_id") != rebuilt["protocol_id"]:
            findings.append(
                _finding(
                    "PROTOCOL_ID_MISMATCH",
                    "protocol_id does not match canonical protocol content",
                    "$.protocol_id",
                )
            )
        if protocol.get("canonical_hash") != rebuilt["canonical_hash"]:
            findings.append(
                _finding(
                    "PROTOCOL_HASH_MISMATCH",
                    "canonical_hash does not match canonical protocol content",
                    "$.canonical_hash",
                )
            )
        if dict(protocol) != rebuilt and not any(
            item["code"] in {"PROTOCOL_ID_MISMATCH", "PROTOCOL_HASH_MISMATCH"}
            for item in findings
        ):
            findings.append(
                _finding("PROTOCOL_NOT_CANONICAL", "protocol payload is not canonical")
            )
    findings.extend(_protocol_policy_findings(protocol))
    return _validation(
        PROTOCOL_VALIDATION_SCHEMA_VERSION,
        findings,
        identity={
            "protocol_id": str(protocol.get("protocol_id") or ""),
            "canonical_hash": str(protocol.get("canonical_hash") or ""),
        },
    )


def replay_validate_observation_protocol(
    protocol: Mapping[str, Any],
    *,
    candidate: Mapping[str, Any],
    review_events: Sequence[Mapping[str, Any]],
    candidate_source_artifacts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Replay the exact Stage 1 candidate, source, event-set, and projection binding."""

    offline = validate_observation_protocol(protocol)
    findings = list(offline["findings"])
    binding = protocol.get("candidate_binding")
    if not isinstance(binding, Mapping):
        findings.append(
            _finding("STAGE1_BINDING_INVALID", "candidate_binding is required")
        )
    else:
        candidate_validation = validate_behavior_hypothesis_candidate(candidate)
        if candidate_validation["validation_status"] != "accepted":
            findings.append(
                _finding(
                    "STAGE1_CANDIDATE_INVALID",
                    ", ".join(candidate_validation["finding_codes"]),
                )
            )
        if candidate.get("candidate_id") != binding.get("candidate_id"):
            findings.append(
                _finding(
                    "STAGE1_CANDIDATE_ID_MISMATCH",
                    "candidate ID differs from the protocol binding",
                )
            )
        if candidate.get("canonical_hash") != binding.get("candidate_canonical_hash"):
            findings.append(
                _finding(
                    "STAGE1_CANDIDATE_HASH_MISMATCH",
                    "candidate hash differs from the protocol binding",
                )
            )
        source_replay = replay_validate_behavior_hypothesis_candidate(
            candidate, source_artifacts=candidate_source_artifacts
        )
        if (
            source_replay["validation_status"] != "accepted"
            or source_replay["source_verification"]["status"] != "verified"
        ):
            findings.append(
                _finding(
                    "STAGE1_SOURCE_REPLAY_FAILED",
                    ", ".join(source_replay["finding_codes"]),
                )
            )
        try:
            actual_source_refs = _candidate_source_refs(
                candidate, candidate_source_artifacts
            )
        except (ObservationProtocolError, TypeError, ValueError) as exc:
            findings.append(_finding("STAGE1_SOURCE_BINDING_INVALID", str(exc)))
        else:
            if actual_source_refs != binding.get("candidate_source_refs"):
                findings.append(
                    _finding(
                        "STAGE1_SOURCE_SET_MISMATCH",
                        "exact candidate source artifacts differ from the protocol binding",
                    )
                )
        try:
            actual_event_refs = _stage1_review_event_refs(
                str(candidate.get("candidate_id") or ""), review_events
            )
        except (ObservationProtocolError, TypeError, ValueError) as exc:
            findings.append(
                _finding("STAGE1_REVIEW_EVENT_SET_INVALID", str(exc))
            )
        else:
            if (
                actual_event_refs != binding.get("review_event_refs")
                or _canonical_hash(actual_event_refs)
                != binding.get("review_event_set_hash")
            ):
                findings.append(
                    _finding(
                        "STAGE1_REVIEW_EVENT_SET_MISMATCH",
                        "complete Stage 1 review event set differs from the binding",
                    )
                )
        projection_binding = binding.get("accepted_projection")
        if not isinstance(projection_binding, Mapping):
            findings.append(
                _finding("STAGE1_PROJECTION_INVALID", "accepted projection is required")
            )
        else:
            try:
                actual_projection = project_behavior_hypothesis_state(
                    candidate,
                    review_events,
                    as_of=str(projection_binding.get("as_of") or ""),
                    knowledge_cutoff=str(
                        projection_binding.get("knowledge_cutoff") or ""
                    ),
                )
                actual_projection_binding = _accepted_projection_binding(
                    actual_projection
                )
            except Exception as exc:
                findings.append(_finding("STAGE1_PROJECTION_REPLAY_FAILED", str(exc)))
            else:
                if actual_projection_binding != projection_binding:
                    findings.append(
                        _finding(
                            "STAGE1_PROJECTION_MISMATCH",
                            "historical accepted projection differs from the binding",
                        )
                    )
    normalized = _canonical_findings(findings)
    return _validation(
        PROTOCOL_VALIDATION_SCHEMA_VERSION,
        normalized,
        identity={
            "protocol_id": str(protocol.get("protocol_id") or ""),
            "canonical_hash": str(protocol.get("canonical_hash") or ""),
        },
        source_status="blocked" if normalized else "verified",
    )


def _normalize_event_provenance(value: object) -> dict[str, Any]:
    provenance = _mapping(value, "provenance")
    _reject_unknown_fields(
        provenance,
        {"submitter_kind", "source_locator", "tool_version"},
        "provenance",
    )
    if provenance.get("submitter_kind") != "human":
        raise ObservationProtocolError("protocol lifecycle events must be human-authored")
    return {
        "submitter_kind": "human",
        "source_locator": _source_locator(
            provenance.get("source_locator"), "provenance.source_locator"
        ),
        "tool_version": _text(
            provenance.get("tool_version", PROTOCOL_EVENT_BUILDER_VERSION),
            "provenance.tool_version",
        ),
    }


def _event_material(value: Mapping[str, Any]) -> dict[str, Any]:
    _reject_unknown_fields(value, _PROTOCOL_EVENT_FIELDS, "protocol_review_event")
    protocol_id = _normalized_id(value.get("protocol_id"), "protocol_id", _PROTOCOL_ID_RE)
    try:
        event_type = ProtocolReviewEventType(_text(value.get("event_type"), "event_type"))
    except ValueError as exc:
        raise ObservationProtocolError("event_type is unsupported") from exc
    reviewed_at = _canonical_timestamp(value.get("reviewed_at"), "reviewed_at")
    effective_at = _canonical_timestamp(value.get("effective_at"), "effective_at")
    knowledge_at = _canonical_timestamp(value.get("knowledge_at"), "knowledge_at")
    evidence_cutoff = _canonical_timestamp(
        value.get("evidence_cutoff"), "evidence_cutoff"
    )
    if effective_at > knowledge_at or knowledge_at > reviewed_at:
        raise ObservationProtocolError(
            "event time must satisfy effective_at <= knowledge_at <= reviewed_at"
        )
    if evidence_cutoff > knowledge_at:
        raise ObservationProtocolError("evidence_cutoff cannot exceed knowledge_at")
    reviewer_ref = _text(value.get("reviewer_ref"), "reviewer_ref")
    if not _REVIEWER_REF_RE.fullmatch(reviewer_ref):
        raise ObservationProtocolError("reviewer_ref must be a pseudonymous stable ref")
    supersedes_event_id = _optional_id(
        value.get("supersedes_event_id"),
        "supersedes_event_id",
        _PROTOCOL_EVENT_ID_RE,
    )
    superseded_by_protocol_id = _optional_id(
        value.get("superseded_by_protocol_id"),
        "superseded_by_protocol_id",
        _PROTOCOL_ID_RE,
    )
    if event_type is ProtocolReviewEventType.SUPERSEDED:
        if supersedes_event_id is None or superseded_by_protocol_id is None:
            raise ObservationProtocolError(
                "superseded event requires prior event and replacement protocol refs"
            )
        if superseded_by_protocol_id == protocol_id:
            raise ObservationProtocolError("a protocol cannot supersede itself")
    elif supersedes_event_id is not None or superseded_by_protocol_id is not None:
        raise ObservationProtocolError(
            "supersession refs are only valid for a superseded event"
        )
    return {
        "schema_version": PROTOCOL_REVIEW_EVENT_SCHEMA_VERSION,
        "artifact_type": "observation_protocol_review_event",
        "protocol_id": protocol_id,
        "event_type": event_type.value,
        "reviewed_at": reviewed_at,
        "effective_at": effective_at,
        "knowledge_at": knowledge_at,
        "reviewer_ref": reviewer_ref,
        "rationale": _text(value.get("rationale"), "rationale"),
        "evidence_cutoff": evidence_cutoff,
        "supersedes_event_id": supersedes_event_id,
        "superseded_by_protocol_id": superseded_by_protocol_id,
        "provenance": _normalize_event_provenance(value.get("provenance")),
    }


def build_observation_protocol_review_event(
    value: Mapping[str, Any]
) -> dict[str, Any]:
    """Canonicalize one explicit human lifecycle event."""

    material = _event_material(value)
    event = deepcopy(material)
    event["protocol_review_event_id"] = _stable_id(
        "protocol_review_event", material
    )
    event["canonical_hash"] = _canonical_hash(material)
    return event


def validate_observation_protocol_review_event(
    event: Mapping[str, Any]
) -> dict[str, Any]:
    findings = _schema_findings(
        event,
        PROTOCOL_REVIEW_EVENT_SCHEMA_PATH,
        "PROTOCOL_REVIEW_EVENT_SCHEMA_INVALID",
    )
    try:
        rebuilt = build_observation_protocol_review_event(event)
    except (ObservationProtocolError, TypeError, ValueError) as exc:
        findings.append(_finding("PROTOCOL_REVIEW_EVENT_SEMANTIC_INVALID", str(exc)))
        rebuilt = None
    if rebuilt is not None and dict(event) != rebuilt:
        if event.get("protocol_review_event_id") != rebuilt["protocol_review_event_id"]:
            findings.append(
                _finding(
                    "PROTOCOL_REVIEW_EVENT_ID_MISMATCH",
                    "event ID does not match canonical content",
                    "$.protocol_review_event_id",
                )
            )
        if event.get("canonical_hash") != rebuilt["canonical_hash"]:
            findings.append(
                _finding(
                    "PROTOCOL_REVIEW_EVENT_HASH_MISMATCH",
                    "event hash does not match canonical content",
                    "$.canonical_hash",
                )
            )
    for code in sorted(interpretation_policy_codes(event.get("rationale"))):
        findings.append(
            _finding(
                code,
                "event rationale violates the shared no-diagnosis/advice/score policy",
                "$.rationale",
            )
        )
    return _validation(
        PROTOCOL_EVENT_VALIDATION_SCHEMA_VERSION,
        findings,
        identity={
            "protocol_review_event_id": str(
                event.get("protocol_review_event_id") or ""
            ),
            "canonical_hash": str(event.get("canonical_hash") or ""),
            "protocol_id": str(event.get("protocol_id") or ""),
        },
    )

