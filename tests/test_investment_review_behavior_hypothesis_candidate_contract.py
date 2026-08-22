from __future__ import annotations

import json
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from src.investment_review.behavior_hypothesis_candidates import (
    ACCEPTED_FOR_OBSERVATION_SEMANTICS,
    CANDIDATE_SCHEMA_PATH,
    CANDIDATE_SCHEMA_VERSION,
    PROJECTION_SCHEMA_PATH,
    PROJECTION_SCHEMA_VERSION,
    REVIEW_EVENT_SCHEMA_PATH,
    REVIEW_EVENT_SCHEMA_VERSION,
    PatternFamily,
    ProjectedStatus,
    ReviewEventType,
    SubjectScopeKind,
)


HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
CANDIDATE_ID = "candidate:" + "c" * 32
EVENT_ID = "review_event:" + "d" * 32


def _validator(path) -> Draft202012Validator:
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _candidate() -> dict[str, object]:
    return {
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "artifact_type": "behavior_hypothesis_candidate",
        "candidate_id": CANDIDATE_ID,
        "canonical_hash": HASH_A,
        "created_at": "2026-07-20T12:00:00Z",
        "effective_at": "2026-07-20T11:00:00Z",
        "knowledge_at": "2026-07-20T12:00:00Z",
        "subject_scope": {"kind": "cohort", "refs": ["synthetic-cohort-001"]},
        "pattern_family": "outcome_conditioning",
        "hypothesis_statement": (
            "The observed association may persist in comparable synthetic episodes."
        ),
        "supporting_evidence": [
            {
                "artifact_type": "p2g.behavior_observation_set.v1",
                "artifact_id": "evaluation:" + "e" * 32,
                "canonical_hash": HASH_B,
                "source_locator": "synthetic/p2g_observation.json",
                "effective_at": "2026-07-20T11:00:00Z",
                "knowledge_at": "2026-07-20T11:30:00Z",
            }
        ],
        "counterevidence": [],
        "source_gaps": [
            {
                "description": "Comparable synthetic episodes are not yet available.",
                "affected_refs": ["synthetic-episode-002"],
            }
        ],
        "alternative_explanations": ["Opportunity quality may have changed."],
        "applicability_conditions": ["Only the frozen synthetic cohort is covered."],
        "disconfirming_observations": ["The association disappears in comparable episodes."],
        "observation_plan": {
            "question": "Does the association persist?",
            "required_facts": ["reviewed decision intent"],
        },
        "provenance": {
            "submitter_kind": "human_reviewed_sidecar",
            "source_locator": "synthetic/candidate.json",
            "tool_version": "p2h.behavior_hypothesis_candidate.builder.v1",
            "canonical_hash": HASH_A,
        },
    }


def _event() -> dict[str, object]:
    return {
        "schema_version": REVIEW_EVENT_SCHEMA_VERSION,
        "artifact_type": "behavior_hypothesis_review_event",
        "review_event_id": EVENT_ID,
        "canonical_hash": HASH_B,
        "candidate_id": CANDIDATE_ID,
        "event_type": "accepted_for_observation",
        "reviewed_at": "2026-07-20T13:00:00Z",
        "effective_at": "2026-07-20T13:00:00Z",
        "knowledge_at": "2026-07-20T13:00:00Z",
        "reviewer_ref": "synthetic-human-reviewer",
        "rationale": "The evidence is sufficient only for continued observation.",
        "evidence_cutoff": "2026-07-20T12:00:00Z",
        "supersedes_event_id": None,
        "supersedes_candidate_id": None,
        "provenance": {
            "submitter_kind": "human",
            "source_locator": "synthetic/review_event.json",
            "tool_version": "p2h.behavior_hypothesis_review_event.builder.v1",
            "canonical_hash": HASH_B,
        },
    }


def test_p2h_stage1_schemas_are_valid_and_accept_minimal_contracts() -> None:
    candidate_validator = _validator(CANDIDATE_SCHEMA_PATH)
    event_validator = _validator(REVIEW_EVENT_SCHEMA_PATH)
    projection_validator = _validator(PROJECTION_SCHEMA_PATH)

    assert not list(candidate_validator.iter_errors(_candidate()))
    assert not list(event_validator.iter_errors(_event()))
    assert not list(
        projection_validator.iter_errors(
            {
                "schema_version": PROJECTION_SCHEMA_VERSION,
                "artifact_type": "behavior_hypothesis_projection",
                "candidate_id": CANDIDATE_ID,
                "status": "accepted_for_observation",
                "as_of": "2026-07-20T13:00:00Z",
                "knowledge_cutoff": "2026-07-20T13:00:00Z",
                "applied_event_ids": [EVENT_ID],
                "last_event_id": EVENT_ID,
                "state_semantics": ACCEPTED_FOR_OBSERVATION_SEMANTICS,
            }
        )
    )


@pytest.mark.parametrize(
    ("mutate", "expected_fragment"),
    [
        (lambda value: value.__setitem__("alternative_explanations", []), "should be non-empty"),
        (
            lambda value: (
                value.__setitem__("counterevidence", []),
                value.__setitem__("source_gaps", []),
            ),
            "not valid under any",
        ),
        (lambda value: value.__setitem__("score", 91), "additional properties"),
        (lambda value: value.__setitem__("created_at", "not-a-time"), "does not match"),
        (
            lambda value: value["supporting_evidence"][0].__setitem__(
                "canonical_hash", "unverified"
            ),
            "does not match",
        ),
    ],
)
def test_candidate_schema_rejects_missing_or_prohibited_contract_fields(
    mutate, expected_fragment: str
) -> None:
    candidate = _candidate()
    mutate(candidate)

    messages = " | ".join(
        error.message for error in _validator(CANDIDATE_SCHEMA_PATH).iter_errors(candidate)
    ).lower()

    assert expected_fragment in messages


def test_review_event_schema_rejects_invalid_status_and_unlinked_supersession() -> None:
    event = _event()
    event["event_type"] = "proven_true"
    errors = list(_validator(REVIEW_EVENT_SCHEMA_PATH).iter_errors(event))
    assert errors

    superseded = _event()
    superseded["event_type"] = "superseded"
    errors = list(_validator(REVIEW_EVENT_SCHEMA_PATH).iter_errors(superseded))
    assert any("not valid under any" in error.message for error in errors)


def test_public_enums_freeze_supported_domain_values() -> None:
    assert SubjectScopeKind.COHORT.value == "cohort"
    assert PatternFamily.OUTCOME_CONDITIONING.value == "outcome_conditioning"
    assert ReviewEventType.ACCEPTED_FOR_OBSERVATION.value == "accepted_for_observation"
    assert ProjectedStatus.ACCEPTED_FOR_OBSERVATION.value == "accepted_for_observation"
    assert "not proven" in ACCEPTED_FOR_OBSERVATION_SEMANTICS
