"""P2H Stage 1 behavior-hypothesis candidate domain contracts.

The executable builder, validator, immutable store, and projector are added by
the later P2H Stage 1 checkpoints.  This module freezes the public names and
typed value objects without changing the existing P2G artifact contracts.
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
from .behavior_observations import (
    SCHEMA_VERSION as OBSERVATION_SCHEMA_VERSION,
    validate_behavior_observation_set,
)
from .episode_interpretation import interpretation_policy_codes


CANDIDATE_SCHEMA_VERSION = "p2h.behavior_hypothesis_candidate.v1"
REVIEW_EVENT_SCHEMA_VERSION = "p2h.behavior_hypothesis_review_event.v1"
PROJECTION_SCHEMA_VERSION = "p2h.behavior_hypothesis_projection.v1"
CANDIDATE_VALIDATION_SCHEMA_VERSION = (
    "p2h.behavior_hypothesis_candidate.validation.v1"
)
REVIEW_EVENT_VALIDATION_SCHEMA_VERSION = (
    "p2h.behavior_hypothesis_review_event.validation.v1"
)
REVIEW_LEDGER_VALIDATION_SCHEMA_VERSION = (
    "p2h.behavior_hypothesis_review_ledger.validation.v1"
)
CANDIDATE_BUILDER_VERSION = "p2h.behavior_hypothesis_candidate.builder.v1"
REVIEW_EVENT_BUILDER_VERSION = "p2h.behavior_hypothesis_review_event.builder.v1"
CANONICAL_SORT_VERSION = "p2h.behavior_hypothesis_candidate_sort.v1"

ACCEPTED_FOR_OBSERVATION_SEMANTICS = (
    "Evidence supports continued observation only; the hypothesis is not proven, "
    "is not a psychological diagnosis, and is not trading advice."
)

_ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_SCHEMA_PATH = (
    _ROOT
    / "docs"
    / "contracts"
    / "P2H_STAGE1_BEHAVIOR_HYPOTHESIS_CANDIDATE.schema.json"
)
REVIEW_EVENT_SCHEMA_PATH = (
    _ROOT
    / "docs"
    / "contracts"
    / "P2H_STAGE1_BEHAVIOR_HYPOTHESIS_REVIEW_EVENT.schema.json"
)
PROJECTION_SCHEMA_PATH = (
    _ROOT
    / "docs"
    / "contracts"
    / "P2H_STAGE1_BEHAVIOR_HYPOTHESIS_PROJECTION.schema.json"
)


class BehaviorHypothesisCandidateError(ValueError):
    """Raised when a P2H Stage 1 public contract is violated."""


class BehaviorHypothesisProjectionError(BehaviorHypothesisCandidateError):
    """Raised when immutable review events cannot form one valid projection."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class SubjectScopeKind(str, Enum):
    PORTFOLIO = "portfolio"
    COHORT = "cohort"
    EPISODE_SET = "episode_set"
    SYMBOL = "symbol"
    GLOBAL = "global"


class PatternFamily(str, Enum):
    SEQUENCE = "sequence"
    SIZING = "sizing"
    ENTRY = "entry"
    EXIT = "exit"
    HOLDING_PERIOD = "holding_period"
    OUTCOME_CONDITIONING = "outcome_conditioning"
    PORTFOLIO_CONTEXT = "portfolio_context"
    MARKET_ENVIRONMENT = "market_environment"
    OTHER = "other"


class ReviewEventType(str, Enum):
    SUBMITTED = "submitted"
    ACCEPTED_FOR_OBSERVATION = "accepted_for_observation"
    REVISION_REQUESTED = "revision_requested"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    NOTE_ADDED = "note_added"


class ProjectedStatus(str, Enum):
    CANDIDATE = "candidate"
    SUBMITTED = "submitted"
    ACCEPTED_FOR_OBSERVATION = "accepted_for_observation"
    REVISION_REQUESTED = "revision_requested"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


@dataclass(frozen=True)
class SubjectScope:
    kind: SubjectScopeKind
    refs: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceReference:
    artifact_type: str
    artifact_id: str
    canonical_hash: str
    source_locator: str
    effective_at: str
    knowledge_at: str


@dataclass(frozen=True)
class BehaviorHypothesisCandidate:
    candidate_id: str
    canonical_hash: str
    created_at: str
    effective_at: str
    knowledge_at: str
    subject_scope: SubjectScope
    pattern_family: PatternFamily
    hypothesis_statement: str
    supporting_evidence: tuple[EvidenceReference, ...]
    counterevidence: tuple[EvidenceReference, ...]
    source_gaps: tuple[Mapping[str, Any], ...]
    alternative_explanations: tuple[str, ...]
    applicability_conditions: tuple[str, ...]
    disconfirming_observations: tuple[str, ...]
    observation_plan: Mapping[str, Any]
    provenance: Mapping[str, Any]


@dataclass(frozen=True)
class BehaviorHypothesisReviewEvent:
    review_event_id: str
    canonical_hash: str
    candidate_id: str
    event_type: ReviewEventType
    reviewed_at: str
    effective_at: str
    knowledge_at: str
    reviewer_ref: str
    rationale: str
    evidence_cutoff: str
    supersedes_event_id: str | None
    supersedes_candidate_id: str | None
    provenance: Mapping[str, Any]


@dataclass(frozen=True)
class BehaviorHypothesisProjection:
    candidate_id: str
    status: ProjectedStatus
    as_of: str
    knowledge_cutoff: str
    applied_event_ids: tuple[str, ...]
    last_event_id: str | None
    state_semantics: str = ACCEPTED_FOR_OBSERVATION_SEMANTICS


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_CANDIDATE_ID_RE = re.compile(r"^candidate:[0-9a-f]{32}$")
_REVIEW_EVENT_ID_RE = re.compile(r"^review_event:[0-9a-f]{32}$")
_UNCERTAINTY_RE = re.compile(
    r"\b(?:may|might|could|appears?|suggests?|possibly|potentially|associated)\b"
    r"|可能|或许|似乎|有待|尚不能|相关",
    re.IGNORECASE,
)

_CANDIDATE_FIELDS = {
    "schema_version",
    "artifact_type",
    "candidate_id",
    "canonical_hash",
    "created_at",
    "effective_at",
    "knowledge_at",
    "subject_scope",
    "pattern_family",
    "hypothesis_statement",
    "supporting_evidence",
    "counterevidence",
    "source_gaps",
    "alternative_explanations",
    "applicability_conditions",
    "disconfirming_observations",
    "observation_plan",
    "provenance",
}
_REVIEW_EVENT_FIELDS = {
    "schema_version",
    "artifact_type",
    "review_event_id",
    "canonical_hash",
    "candidate_id",
    "event_type",
    "reviewed_at",
    "effective_at",
    "knowledge_at",
    "reviewer_ref",
    "rationale",
    "evidence_cutoff",
    "supersedes_event_id",
    "supersedes_candidate_id",
    "provenance",
}


def _canonical_hash(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _stable_id(prefix: str, value: object) -> str:
    return f"{prefix}:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()[:32]


def _canonical_timestamp(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BehaviorHypothesisCandidateError(
            f"{field} must be a timezone-aware timestamp"
        )
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise BehaviorHypothesisCandidateError(f"invalid {field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BehaviorHypothesisCandidateError(
            f"{field} must be timezone-aware"
        )
    if parsed.microsecond:
        raise BehaviorHypothesisCandidateError(
            f"{field} must use whole seconds"
        )
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise BehaviorHypothesisCandidateError(f"{field} must be text")
    normalized = (
        unicodedata.normalize("NFC", value)
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .strip()
    )
    if not normalized:
        raise BehaviorHypothesisCandidateError(f"{field} must not be empty")
    return normalized


def _optional_id(
    value: object,
    field: str,
    pattern: re.Pattern[str],
) -> str | None:
    if value is None:
        return None
    normalized = _text(value, field)
    if not pattern.fullmatch(normalized):
        raise BehaviorHypothesisCandidateError(f"invalid {field}")
    return normalized


def _text_list(
    value: object,
    field: str,
    *,
    required: bool,
    preserve_order: bool,
) -> list[str]:
    if not isinstance(value, list):
        raise BehaviorHypothesisCandidateError(f"{field} must be an array")
    normalized = [_text(item, f"{field}[]") for item in value]
    if required and not normalized:
        raise BehaviorHypothesisCandidateError(f"{field} must not be empty")
    if len(set(normalized)) != len(normalized):
        raise BehaviorHypothesisCandidateError(f"{field} contains duplicates")
    return normalized if preserve_order else sorted(normalized)


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise BehaviorHypothesisCandidateError(f"{field} must be an object")
    return value


def _reject_unknown_fields(
    value: Mapping[str, Any], allowed: set[str], field: str
) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise BehaviorHypothesisCandidateError(
            f"{field} has unsupported fields: {', '.join(unknown)}"
        )


def _normalize_scope(value: object) -> dict[str, Any]:
    scope = _mapping(value, "subject_scope")
    _reject_unknown_fields(scope, {"kind", "refs"}, "subject_scope")
    try:
        kind = SubjectScopeKind(_text(scope.get("kind"), "subject_scope.kind"))
    except ValueError as exc:
        raise BehaviorHypothesisCandidateError(
            "subject_scope.kind is unsupported"
        ) from exc
    refs = _text_list(
        scope.get("refs"),
        "subject_scope.refs",
        required=True,
        preserve_order=False,
    )
    return {"kind": kind.value, "refs": refs}


def _normalize_evidence_ref(value: object, field: str) -> dict[str, Any]:
    ref = _mapping(value, field)
    allowed = {
        "artifact_type",
        "artifact_id",
        "canonical_hash",
        "source_locator",
        "effective_at",
        "knowledge_at",
    }
    _reject_unknown_fields(ref, allowed, field)
    canonical_hash = _text(ref.get("canonical_hash"), f"{field}.canonical_hash")
    if not _SHA256_RE.fullmatch(canonical_hash):
        raise BehaviorHypothesisCandidateError(
            f"{field}.canonical_hash must be a sha256 content ID"
        )
    effective_at = _canonical_timestamp(ref.get("effective_at"), f"{field}.effective_at")
    knowledge_at = _canonical_timestamp(ref.get("knowledge_at"), f"{field}.knowledge_at")
    if _datetime(knowledge_at) < _datetime(effective_at):
        raise BehaviorHypothesisCandidateError(
            f"{field}.knowledge_at cannot precede effective_at"
        )
    return {
        "artifact_type": _text(ref.get("artifact_type"), f"{field}.artifact_type"),
        "artifact_id": _text(ref.get("artifact_id"), f"{field}.artifact_id"),
        "canonical_hash": canonical_hash,
        "source_locator": _text(ref.get("source_locator"), f"{field}.source_locator"),
        "effective_at": effective_at,
        "knowledge_at": knowledge_at,
    }


def _normalize_evidence_refs(
    value: object, field: str, *, required: bool
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise BehaviorHypothesisCandidateError(f"{field} must be an array")
    refs = [_normalize_evidence_ref(item, f"{field}[{index}]") for index, item in enumerate(value)]
    if required and not refs:
        raise BehaviorHypothesisCandidateError(f"{field} must not be empty")
    keyed = {canonical_json_bytes(item): item for item in refs}
    if len(keyed) != len(refs):
        raise BehaviorHypothesisCandidateError(f"{field} contains duplicates")
    return [keyed[key] for key in sorted(keyed)]


def _normalize_source_gaps(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise BehaviorHypothesisCandidateError("source_gaps must be an array")
    gaps: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        gap = _mapping(item, f"source_gaps[{index}]")
        _reject_unknown_fields(
            gap, {"description", "affected_refs"}, f"source_gaps[{index}]"
        )
        gaps.append(
            {
                "description": _text(
                    gap.get("description"), f"source_gaps[{index}].description"
                ),
                "affected_refs": _text_list(
                    gap.get("affected_refs"),
                    f"source_gaps[{index}].affected_refs",
                    required=False,
                    preserve_order=False,
                ),
            }
        )
    keyed = {canonical_json_bytes(item): item for item in gaps}
    if len(keyed) != len(gaps):
        raise BehaviorHypothesisCandidateError("source_gaps contains duplicates")
    return [keyed[key] for key in sorted(keyed)]


def _normalize_observation_plan(value: object) -> dict[str, Any]:
    plan = _mapping(value, "observation_plan")
    _reject_unknown_fields(plan, {"question", "required_facts"}, "observation_plan")
    return {
        "question": _text(plan.get("question"), "observation_plan.question"),
        "required_facts": _text_list(
            plan.get("required_facts"),
            "observation_plan.required_facts",
            required=True,
            preserve_order=True,
        ),
    }


def _normalize_provenance(
    value: object, field: str, *, default_tool_version: str
) -> dict[str, Any]:
    provenance = _mapping(value, field)
    _reject_unknown_fields(
        provenance,
        {"submitter_kind", "source_locator", "tool_version", "canonical_hash"},
        field,
    )
    submitter_kind = _text(provenance.get("submitter_kind"), f"{field}.submitter_kind")
    if submitter_kind not in {"human", "agent_assisted", "human_reviewed_sidecar"}:
        raise BehaviorHypothesisCandidateError(
            f"{field}.submitter_kind is unsupported"
        )
    tool_version = provenance.get("tool_version", default_tool_version)
    return {
        "submitter_kind": submitter_kind,
        "source_locator": _text(
            provenance.get("source_locator"), f"{field}.source_locator"
        ),
        "tool_version": _text(tool_version, f"{field}.tool_version"),
    }


def _candidate_material(value: Mapping[str, Any]) -> dict[str, Any]:
    _reject_unknown_fields(value, _CANDIDATE_FIELDS, "candidate")
    try:
        pattern_family = PatternFamily(
            _text(value.get("pattern_family"), "pattern_family")
        )
    except ValueError as exc:
        raise BehaviorHypothesisCandidateError("pattern_family is unsupported") from exc
    created_at = _canonical_timestamp(value.get("created_at"), "created_at")
    effective_at = _canonical_timestamp(value.get("effective_at"), "effective_at")
    knowledge_at = _canonical_timestamp(value.get("knowledge_at"), "knowledge_at")
    if _datetime(effective_at) > _datetime(knowledge_at):
        raise BehaviorHypothesisCandidateError(
            "effective_at cannot be later than knowledge_at"
        )
    if _datetime(knowledge_at) > _datetime(created_at):
        raise BehaviorHypothesisCandidateError(
            "knowledge_at cannot be later than created_at"
        )
    supporting = _normalize_evidence_refs(
        value.get("supporting_evidence"), "supporting_evidence", required=True
    )
    counterevidence = _normalize_evidence_refs(
        value.get("counterevidence", []), "counterevidence", required=False
    )
    source_gaps = _normalize_source_gaps(value.get("source_gaps", []))
    if not counterevidence and not source_gaps:
        raise BehaviorHypothesisCandidateError(
            "counterevidence or source_gaps must be non-empty"
        )
    for field, refs in (
        ("supporting_evidence", supporting),
        ("counterevidence", counterevidence),
    ):
        future = [
            item["artifact_id"]
            for item in refs
            if _datetime(item["knowledge_at"]) > _datetime(knowledge_at)
        ]
        if future:
            raise BehaviorHypothesisCandidateError(
                f"{field} contains evidence after knowledge_at: {future}"
            )
    return {
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "artifact_type": "behavior_hypothesis_candidate",
        "created_at": created_at,
        "effective_at": effective_at,
        "knowledge_at": knowledge_at,
        "subject_scope": _normalize_scope(value.get("subject_scope")),
        "pattern_family": pattern_family.value,
        "hypothesis_statement": _text(
            value.get("hypothesis_statement"), "hypothesis_statement"
        ),
        "supporting_evidence": supporting,
        "counterevidence": counterevidence,
        "source_gaps": source_gaps,
        "alternative_explanations": _text_list(
            value.get("alternative_explanations"),
            "alternative_explanations",
            required=True,
            preserve_order=True,
        ),
        "applicability_conditions": _text_list(
            value.get("applicability_conditions"),
            "applicability_conditions",
            required=True,
            preserve_order=True,
        ),
        "disconfirming_observations": _text_list(
            value.get("disconfirming_observations"),
            "disconfirming_observations",
            required=True,
            preserve_order=True,
        ),
        "observation_plan": _normalize_observation_plan(value.get("observation_plan")),
        "provenance": _normalize_provenance(
            value.get("provenance"),
            "provenance",
            default_tool_version=CANDIDATE_BUILDER_VERSION,
        ),
    }


def build_behavior_hypothesis_candidate(value: Mapping[str, Any]) -> dict[str, Any]:
    """Canonicalize an explicit candidate submission and derive its identity."""

    material = _candidate_material(value)
    canonical_hash = _canonical_hash(material)
    candidate = deepcopy(material)
    candidate["candidate_id"] = _stable_id("candidate", material)
    candidate["canonical_hash"] = canonical_hash
    candidate["provenance"]["canonical_hash"] = canonical_hash
    return candidate


def _review_event_material(value: Mapping[str, Any]) -> dict[str, Any]:
    _reject_unknown_fields(value, _REVIEW_EVENT_FIELDS, "review_event")
    candidate_id = _text(value.get("candidate_id"), "candidate_id")
    if not _CANDIDATE_ID_RE.fullmatch(candidate_id):
        raise BehaviorHypothesisCandidateError("invalid candidate_id")
    try:
        event_type = ReviewEventType(_text(value.get("event_type"), "event_type"))
    except ValueError as exc:
        raise BehaviorHypothesisCandidateError("event_type is unsupported") from exc
    reviewed_at = _canonical_timestamp(value.get("reviewed_at"), "reviewed_at")
    effective_at = _canonical_timestamp(value.get("effective_at"), "effective_at")
    knowledge_at = _canonical_timestamp(value.get("knowledge_at"), "knowledge_at")
    evidence_cutoff = _canonical_timestamp(
        value.get("evidence_cutoff"), "evidence_cutoff"
    )
    if _datetime(effective_at) > _datetime(knowledge_at):
        raise BehaviorHypothesisCandidateError(
            "effective_at cannot be later than knowledge_at"
        )
    if _datetime(reviewed_at) > _datetime(knowledge_at):
        raise BehaviorHypothesisCandidateError(
            "reviewed_at cannot be later than knowledge_at"
        )
    if _datetime(evidence_cutoff) > _datetime(reviewed_at):
        raise BehaviorHypothesisCandidateError(
            "evidence_cutoff cannot be later than reviewed_at"
        )
    supersedes_event_id = _optional_id(
        value.get("supersedes_event_id"),
        "supersedes_event_id",
        _REVIEW_EVENT_ID_RE,
    )
    supersedes_candidate_id = _optional_id(
        value.get("supersedes_candidate_id"),
        "supersedes_candidate_id",
        _CANDIDATE_ID_RE,
    )
    if event_type is ReviewEventType.SUPERSEDED and not (
        supersedes_event_id or supersedes_candidate_id
    ):
        raise BehaviorHypothesisCandidateError(
            "superseded event requires a supersession reference"
        )
    return {
        "schema_version": REVIEW_EVENT_SCHEMA_VERSION,
        "artifact_type": "behavior_hypothesis_review_event",
        "candidate_id": candidate_id,
        "event_type": event_type.value,
        "reviewed_at": reviewed_at,
        "effective_at": effective_at,
        "knowledge_at": knowledge_at,
        "reviewer_ref": _text(value.get("reviewer_ref"), "reviewer_ref"),
        "rationale": _text(value.get("rationale"), "rationale"),
        "evidence_cutoff": evidence_cutoff,
        "supersedes_event_id": supersedes_event_id,
        "supersedes_candidate_id": supersedes_candidate_id,
        "provenance": _normalize_provenance(
            value.get("provenance"),
            "provenance",
            default_tool_version=REVIEW_EVENT_BUILDER_VERSION,
        ),
    }


def build_behavior_hypothesis_review_event(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Canonicalize an explicit immutable human review event."""

    material = _review_event_material(value)
    canonical_hash = _canonical_hash(material)
    event = deepcopy(material)
    event["review_event_id"] = _stable_id("review_event", material)
    event["canonical_hash"] = canonical_hash
    event["provenance"]["canonical_hash"] = canonical_hash
    return event


def _json_path(parts: Iterable[object]) -> str:
    value = "$"
    for part in parts:
        value += f"[{part}]" if isinstance(part, int) else f".{part}"
    return value


def _finding(code: str, message: str, path: str = "$") -> dict[str, str]:
    return {"severity": "blocker", "code": code, "message": message, "path": path}


def _canonical_findings(values: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    unique = {
        canonical_json_bytes(
            {
                "severity": str(value["severity"]),
                "code": str(value["code"]),
                "message": str(value["message"]),
                "path": str(value["path"]),
            }
        ): {
            "severity": str(value["severity"]),
            "code": str(value["code"]),
            "message": str(value["message"]),
            "path": str(value["path"]),
        }
        for value in values
    }
    return [unique[key] for key in sorted(unique)]


@lru_cache(maxsize=3)
def _schema_validator(path: str) -> Draft202012Validator:
    schema = json.loads(Path(path).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _schema_findings(
    value: object, path: Path, code: str
) -> list[dict[str, str]]:
    return [
        _finding(code, error.message, _json_path(error.absolute_path))
        for error in sorted(
            _schema_validator(str(path)).iter_errors(value),
            key=lambda item: (_json_path(item.absolute_path), item.message),
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


def _candidate_policy_findings(candidate: Mapping[str, Any]) -> list[dict[str, str]]:
    statement = str(candidate.get("hypothesis_statement") or "")
    authored = {
        "hypothesis_statement": statement,
        "alternative_explanations": candidate.get("alternative_explanations"),
        "applicability_conditions": candidate.get("applicability_conditions"),
        "disconfirming_observations": candidate.get("disconfirming_observations"),
        "observation_plan": candidate.get("observation_plan"),
    }
    findings: list[dict[str, str]] = []
    if statement and not _UNCERTAINTY_RE.search(statement):
        findings.append(
            _finding(
                "UNCERTAINTY_LANGUAGE_REQUIRED",
                "hypothesis_statement must use bounded uncertainty language",
                "$.hypothesis_statement",
            )
        )
    for code in sorted(interpretation_policy_codes(authored)):
        findings.append(
            _finding(
                code,
                "candidate-authored content violates the shared no-diagnosis/advice/score policy",
                "$.hypothesis_statement",
            )
        )
    return findings


def validate_behavior_hypothesis_candidate(
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate canonical structure, identity, time, and policy semantics offline."""

    findings = _schema_findings(
        candidate, CANDIDATE_SCHEMA_PATH, "CANDIDATE_SCHEMA_INVALID"
    )
    try:
        rebuilt = build_behavior_hypothesis_candidate(candidate)
    except (BehaviorHypothesisCandidateError, TypeError, ValueError) as exc:
        findings.append(_finding("CANDIDATE_SEMANTIC_INVALID", str(exc)))
        rebuilt = None
    if rebuilt is not None and dict(candidate) != rebuilt:
        if candidate.get("candidate_id") != rebuilt["candidate_id"]:
            findings.append(
                _finding(
                    "CANDIDATE_ID_MISMATCH",
                    "candidate_id does not match canonical candidate content",
                    "$.candidate_id",
                )
            )
        if candidate.get("canonical_hash") != rebuilt["canonical_hash"]:
            findings.append(
                _finding(
                    "CANDIDATE_HASH_MISMATCH",
                    "canonical_hash does not match canonical candidate content",
                    "$.canonical_hash",
                )
            )
        if dict(candidate) != rebuilt and not any(
            item["code"] in {"CANDIDATE_ID_MISMATCH", "CANDIDATE_HASH_MISMATCH"}
            for item in findings
        ):
            findings.append(
                _finding(
                    "CANDIDATE_NOT_CANONICAL",
                    "candidate payload is not in canonical normalized form",
                )
            )
    findings.extend(_candidate_policy_findings(candidate))
    return _validation(
        CANDIDATE_VALIDATION_SCHEMA_VERSION,
        findings,
        identity={
            "candidate_id": str(candidate.get("candidate_id") or ""),
            "canonical_hash": str(candidate.get("canonical_hash") or ""),
        },
    )


def validate_behavior_hypothesis_review_event(
    event: Mapping[str, Any],
) -> dict[str, Any]:
    findings = _schema_findings(
        event, REVIEW_EVENT_SCHEMA_PATH, "REVIEW_EVENT_SCHEMA_INVALID"
    )
    try:
        rebuilt = build_behavior_hypothesis_review_event(event)
    except (BehaviorHypothesisCandidateError, TypeError, ValueError) as exc:
        findings.append(_finding("REVIEW_EVENT_SEMANTIC_INVALID", str(exc)))
        rebuilt = None
    if rebuilt is not None and dict(event) != rebuilt:
        if event.get("review_event_id") != rebuilt["review_event_id"]:
            findings.append(
                _finding(
                    "REVIEW_EVENT_ID_MISMATCH",
                    "review_event_id does not match canonical event content",
                    "$.review_event_id",
                )
            )
        if event.get("canonical_hash") != rebuilt["canonical_hash"]:
            findings.append(
                _finding(
                    "REVIEW_EVENT_HASH_MISMATCH",
                    "canonical_hash does not match canonical event content",
                    "$.canonical_hash",
                )
            )
        if dict(event) != rebuilt and not any(
            item["code"] in {"REVIEW_EVENT_ID_MISMATCH", "REVIEW_EVENT_HASH_MISMATCH"}
            for item in findings
        ):
            findings.append(
                _finding(
                    "REVIEW_EVENT_NOT_CANONICAL",
                    "review event payload is not in canonical normalized form",
                )
            )
    policy_codes = interpretation_policy_codes(
        {
            "rationale": event.get("rationale"),
        }
    )
    for code in sorted(policy_codes):
        findings.append(
            _finding(
                code,
                "review rationale violates the shared no-diagnosis/advice/score policy",
                "$.rationale",
            )
        )
    return _validation(
        REVIEW_EVENT_VALIDATION_SCHEMA_VERSION,
        findings,
        identity={
            "review_event_id": str(event.get("review_event_id") or ""),
            "canonical_hash": str(event.get("canonical_hash") or ""),
            "candidate_id": str(event.get("candidate_id") or ""),
        },
    )


def _declared_source_content_id(source: Mapping[str, Any]) -> str | None:
    content_id = source.get("content_id")
    return str(content_id) if isinstance(content_id, str) else None


def _source_content_id(source: Mapping[str, Any]) -> str:
    material = deepcopy(dict(source))
    material.pop("content_id", None)
    return _canonical_hash(material)


def _collect_artifact_id_counts(value: object) -> dict[str, int]:
    counts: dict[str, int] = {}

    def visit(item: object) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                if (
                    isinstance(child, str)
                    and (str(key).endswith("_id") or key == "artifact_id")
                    and key != "content_id"
                ):
                    counts[child] = counts.get(child, 0) + 1
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return counts


def _source_findings(source: Mapping[str, Any], index: int) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    declared = _declared_source_content_id(source)
    if declared is None or not _SHA256_RE.fullmatch(declared):
        findings.append(
            _finding(
                "SOURCE_CONTENT_ID_MISSING",
                "source artifact requires a sha256 content_id",
                f"$.sources[{index}].content_id",
            )
        )
    else:
        try:
            actual = _source_content_id(source)
        except Exception as exc:
            findings.append(
                _finding(
                    "SOURCE_CANONICALIZATION_FAILED",
                    str(exc),
                    f"$.sources[{index}]",
                )
            )
        else:
            if actual != declared:
                findings.append(
                    _finding(
                        "SOURCE_CONTENT_HASH_MISMATCH",
                        "source content_id does not match canonical source content",
                        f"$.sources[{index}].content_id",
                    )
                )
    if source.get("schema_version") == OBSERVATION_SCHEMA_VERSION:
        validation = validate_behavior_observation_set(source)
        if validation["validation_status"] != "accepted":
            findings.append(
                _finding(
                    "P2G_SOURCE_INVALID",
                    "P2G observation source failed its canonical validator",
                    f"$.sources[{index}]",
                )
            )
        if (source.get("release_readiness") or {}).get("status") != "ready":
            findings.append(
                _finding(
                    "P2G_SOURCE_NOT_READY",
                    "P2G observation source is not release-ready",
                    f"$.sources[{index}].release_readiness",
                )
            )
        if (source.get("source_verification") or {}).get("status") != "verified":
            findings.append(
                _finding(
                    "P2G_SOURCE_UNVERIFIED",
                    "P2G observation source is not source-verified",
                    f"$.sources[{index}].source_verification",
                )
            )
    return findings


def replay_validate_behavior_hypothesis_candidate(
    candidate: Mapping[str, Any],
    *,
    source_artifacts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Replay every evidence reference against explicit immutable source artifacts."""

    offline = validate_behavior_hypothesis_candidate(candidate)
    findings = list(offline["findings"])
    source_rows: list[dict[str, Any]] = []
    source_bytes: set[bytes] = set()
    for index, source in enumerate(source_artifacts):
        if not isinstance(source, Mapping):
            findings.append(
                _finding(
                    "SOURCE_ARTIFACT_INVALID",
                    "source artifact must be an object",
                    f"$.sources[{index}]",
                )
            )
            continue
        findings.extend(_source_findings(source, index))
        try:
            serialized = canonical_json_bytes(source)
        except Exception:
            continue
        if serialized in source_bytes:
            continue
        source_bytes.add(serialized)
        source_rows.append(
            {
                "source": source,
                "content_id": _declared_source_content_id(source),
                "types": {
                    str(source.get("schema_version") or ""),
                    str(source.get("artifact_type") or ""),
                },
                "id_counts": _collect_artifact_id_counts(source),
            }
        )
    evidence = list(candidate.get("supporting_evidence") or []) + list(
        candidate.get("counterevidence") or []
    )
    for index, raw_ref in enumerate(evidence):
        if not isinstance(raw_ref, Mapping):
            continue
        ref_hash = str(raw_ref.get("canonical_hash") or "")
        ref_id = str(raw_ref.get("artifact_id") or "")
        ref_type = str(raw_ref.get("artifact_type") or "")
        path = f"$.evidence[{index}]"
        hash_matches = [row for row in source_rows if row["content_id"] == ref_hash]
        if not hash_matches:
            id_matches = [row for row in source_rows if ref_id in row["id_counts"]]
            findings.append(
                _finding(
                    "SOURCE_HASH_MISMATCH" if id_matches else "SOURCE_REF_MISSING",
                    (
                        "evidence canonical_hash does not match the explicit source"
                        if id_matches
                        else "evidence reference is absent from explicit sources"
                    ),
                    path,
                )
            )
            continue
        type_matches = [row for row in hash_matches if ref_type in row["types"]]
        if not type_matches:
            findings.append(
                _finding(
                    "SOURCE_TYPE_MISMATCH",
                    "evidence artifact_type does not match the exact source artifact",
                    path,
                )
            )
            continue
        id_matches = [row for row in type_matches if ref_id in row["id_counts"]]
        if not id_matches:
            findings.append(
                _finding(
                    "SOURCE_REF_MISSING",
                    "evidence artifact_id is absent from the exact source artifact",
                    path,
                )
            )
            continue
        if len(id_matches) > 1 or any(
            row["id_counts"].get(ref_id, 0) != 1 for row in id_matches
        ):
            findings.append(
                _finding(
                    "SOURCE_REF_AMBIGUOUS",
                    "evidence artifact_id is not unique in the exact source artifact",
                    path,
                )
            )
    normalized = _canonical_findings(findings)
    return _validation(
        CANDIDATE_VALIDATION_SCHEMA_VERSION,
        normalized,
        identity={
            "candidate_id": str(candidate.get("candidate_id") or ""),
            "canonical_hash": str(candidate.get("canonical_hash") or ""),
        },
        source_status="blocked" if normalized else "verified",
    )


_STATE_TRANSITIONS: dict[str, set[str]] = {
    "candidate": {"submitted"},
    "submitted": {
        "accepted_for_observation",
        "revision_requested",
        "rejected",
        "superseded",
    },
    "accepted_for_observation": {"superseded"},
    "revision_requested": {"superseded"},
    "rejected": {"superseded"},
    "superseded": set(),
}


def behavior_hypothesis_review_event_sort_key(
    event: Mapping[str, Any],
) -> tuple[str, str, str, str]:
    """Return the frozen business/knowledge/review/identity event order."""

    return (
        str(event.get("effective_at") or ""),
        str(event.get("knowledge_at") or ""),
        str(event.get("reviewed_at") or ""),
        str(event.get("review_event_id") or ""),
    )


def _projection_error(code: str, message: str) -> None:
    raise BehaviorHypothesisProjectionError(code, message)


def _prepare_review_events(
    candidate: Mapping[str, Any],
    review_events: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    candidate_id = str(candidate.get("candidate_id") or "")
    by_id: dict[str, tuple[bytes, dict[str, Any]]] = {}
    for raw in review_events:
        if not isinstance(raw, Mapping):
            _projection_error(
                "REVIEW_EVENT_INVALID", "review event must be an object"
            )
        event = deepcopy(dict(raw))
        event_id = str(event.get("review_event_id") or "")
        serialized = canonical_json_bytes(event)
        existing = by_id.get(event_id)
        if existing is not None:
            if existing[0] != serialized:
                _projection_error(
                    "REVIEW_EVENT_ID_CONFLICT",
                    f"review event {event_id} has divergent payloads",
                )
            continue
        validation = validate_behavior_hypothesis_review_event(event)
        if validation["validation_status"] != "accepted":
            _projection_error(
                "REVIEW_EVENT_INVALID",
                ", ".join(validation["finding_codes"]),
            )
        if event["candidate_id"] != candidate_id:
            _projection_error(
                "ORPHAN_REVIEW_EVENT",
                f"event {event['review_event_id']} targets another candidate",
            )
        by_id[event_id] = (serialized, event)
    return sorted(
        (value[1] for value in by_id.values()),
        key=behavior_hypothesis_review_event_sort_key,
    )


def project_behavior_hypothesis_state(
    candidate: Mapping[str, Any],
    review_events: Sequence[Mapping[str, Any]],
    *,
    as_of: str,
    knowledge_cutoff: str,
) -> dict[str, Any]:
    """Project one deterministic state from an explicit immutable event ledger."""

    candidate_validation = validate_behavior_hypothesis_candidate(candidate)
    if candidate_validation["validation_status"] != "accepted":
        _projection_error(
            "CANDIDATE_INVALID",
            ", ".join(candidate_validation["finding_codes"]),
        )
    normalized_as_of = _canonical_timestamp(as_of, "as_of")
    normalized_cutoff = _canonical_timestamp(
        knowledge_cutoff, "knowledge_cutoff"
    )
    if str(candidate["effective_at"]) > normalized_as_of:
        _projection_error(
            "CANDIDATE_NOT_EFFECTIVE",
            "candidate is not effective at the requested as_of",
        )
    if str(candidate["knowledge_at"]) > normalized_cutoff:
        _projection_error(
            "CANDIDATE_NOT_KNOWN",
            "candidate is not known at the requested knowledge_cutoff",
        )

    prepared = _prepare_review_events(candidate, review_events)
    visible = [
        event
        for event in prepared
        if event["effective_at"] <= normalized_as_of
        and event["knowledge_at"] <= normalized_cutoff
    ]
    state_groups: dict[tuple[str, str, str], list[str]] = {}
    for event in visible:
        if event["event_type"] == "note_added":
            continue
        group_key = (
            event["effective_at"],
            event["knowledge_at"],
            event["reviewed_at"],
        )
        state_groups.setdefault(group_key, []).append(event["review_event_id"])
    conflicts = [ids for ids in state_groups.values() if len(ids) > 1]
    if conflicts:
        _projection_error(
            "CONCURRENT_STATE_EVENTS",
            "multiple state-changing events share the same semantic time",
        )

    status = "candidate"
    applied_event_ids: list[str] = []
    applied_id_set: set[str] = set()
    candidate_created_at = str(candidate["created_at"])
    candidate_effective_at = str(candidate["effective_at"])
    candidate_knowledge_at = str(candidate["knowledge_at"])
    for event in visible:
        event_id = str(event["review_event_id"])
        if event["effective_at"] < candidate_effective_at:
            _projection_error(
                "EVENT_EFFECTIVE_BEFORE_CANDIDATE",
                f"event {event_id} is effective before its candidate",
            )
        if event["knowledge_at"] < candidate_knowledge_at:
            _projection_error(
                "EVENT_KNOWN_BEFORE_CANDIDATE",
                f"event {event_id} is known before its candidate",
            )
        if event["reviewed_at"] < candidate_created_at:
            _projection_error(
                "EVENT_REVIEWED_BEFORE_CANDIDATE",
                f"event {event_id} was reviewed before candidate creation",
            )
        if event["evidence_cutoff"] < candidate_knowledge_at:
            _projection_error(
                "EVIDENCE_CUTOFF_BEFORE_CANDIDATE",
                f"event {event_id} excludes candidate-visible evidence",
            )

        event_type = str(event["event_type"])
        supersedes_event_id = event.get("supersedes_event_id")
        supersedes_candidate_id = event.get("supersedes_candidate_id")
        if event_type == "note_added":
            if status == "candidate":
                _projection_error(
                    "INVALID_REVIEW_TRANSITION",
                    "note_added requires a submitted candidate",
                )
            if supersedes_event_id is not None or supersedes_candidate_id is not None:
                _projection_error(
                    "UNEXPECTED_SUPERSESSION_REFERENCE",
                    "note_added cannot carry supersession references",
                )
        else:
            if event_type not in _STATE_TRANSITIONS[status]:
                _projection_error(
                    "INVALID_REVIEW_TRANSITION",
                    f"{status} cannot transition to {event_type}",
                )
            if event_type == "superseded":
                if (
                    supersedes_event_id is not None
                    and supersedes_event_id not in applied_id_set
                ):
                    _projection_error(
                        "SUPERSESSION_EVENT_NOT_VISIBLE",
                        "supersedes_event_id must reference an earlier visible event",
                    )
                if supersedes_candidate_id == candidate["candidate_id"]:
                    _projection_error(
                        "SELF_SUPERSESSION_INVALID",
                        "a candidate cannot supersede itself",
                    )
            elif supersedes_event_id is not None or supersedes_candidate_id is not None:
                _projection_error(
                    "UNEXPECTED_SUPERSESSION_REFERENCE",
                    f"{event_type} cannot carry supersession references",
                )
            status = event_type
        applied_event_ids.append(event_id)
        applied_id_set.add(event_id)

    projection = {
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "artifact_type": "behavior_hypothesis_projection",
        "candidate_id": candidate["candidate_id"],
        "status": status,
        "as_of": normalized_as_of,
        "knowledge_cutoff": normalized_cutoff,
        "applied_event_ids": applied_event_ids,
        "last_event_id": applied_event_ids[-1] if applied_event_ids else None,
        "state_semantics": ACCEPTED_FOR_OBSERVATION_SEMANTICS,
    }
    schema_errors = _schema_findings(
        projection, PROJECTION_SCHEMA_PATH, "PROJECTION_SCHEMA_INVALID"
    )
    if schema_errors:
        _projection_error(
            "PROJECTION_SCHEMA_INVALID",
            ", ".join(item["message"] for item in schema_errors),
        )
    return projection


def validate_behavior_hypothesis_review_ledger(
    candidate: Mapping[str, Any],
    review_events: Sequence[Mapping[str, Any]],
    *,
    as_of: str,
    knowledge_cutoff: str,
) -> dict[str, Any]:
    """Return a stable validation envelope for a candidate plus event ledger."""

    try:
        projection = project_behavior_hypothesis_state(
            candidate,
            review_events,
            as_of=as_of,
            knowledge_cutoff=knowledge_cutoff,
        )
    except BehaviorHypothesisProjectionError as exc:
        return {
            "schema_version": REVIEW_LEDGER_VALIDATION_SCHEMA_VERSION,
            "validation_status": "blocked",
            "candidate_id": str(candidate.get("candidate_id") or ""),
            "projection": None,
            "findings": [
                {
                    "severity": "blocker",
                    "code": exc.code,
                    "message": str(exc),
                    "path": "$.review_events",
                }
            ],
            "finding_codes": [exc.code],
        }
    return {
        "schema_version": REVIEW_LEDGER_VALIDATION_SCHEMA_VERSION,
        "validation_status": "accepted",
        "candidate_id": candidate["candidate_id"],
        "projection": projection,
        "findings": [],
        "finding_codes": [],
    }
