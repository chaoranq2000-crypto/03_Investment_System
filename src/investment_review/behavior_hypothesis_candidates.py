"""P2H Stage 1 behavior-hypothesis candidate domain contracts.

The executable builder, validator, immutable store, and projector are added by
the later P2H Stage 1 checkpoints.  This module freezes the public names and
typed value objects without changing the existing P2G artifact contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


CANDIDATE_SCHEMA_VERSION = "p2h.behavior_hypothesis_candidate.v1"
REVIEW_EVENT_SCHEMA_VERSION = "p2h.behavior_hypothesis_review_event.v1"
PROJECTION_SCHEMA_VERSION = "p2h.behavior_hypothesis_projection.v1"

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
