from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

from src.investment_review.artifact_io import canonical_json_bytes
from src.investment_review.behavior_hypothesis_candidates import (
    BehaviorHypothesisCandidateError,
    build_behavior_hypothesis_candidate,
    build_behavior_hypothesis_review_event,
    replay_validate_behavior_hypothesis_candidate,
    validate_behavior_hypothesis_candidate,
    validate_behavior_hypothesis_review_event,
)


def _hash(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _source() -> dict[str, object]:
    material: dict[str, object] = {
        "schema_version": "p2h.synthetic_source.v1",
        "artifact_type": "synthetic_evidence_set",
        "evaluations": [
            {
                "evaluation_id": "evaluation:" + "1" * 32,
                "status": "observed",
            },
            {
                "evaluation_id": "evaluation:" + "2" * 32,
                "status": "not_observed",
            },
        ],
    }
    return {**material, "content_id": _hash(material)}


def _evidence(
    source: dict[str, object], evaluation_id: str, *, knowledge_at: str
) -> dict[str, object]:
    return {
        "artifact_type": source["schema_version"],
        "artifact_id": evaluation_id,
        "canonical_hash": source["content_id"],
        "source_locator": "synthetic/p2g_observation.json",
        "effective_at": "2026-07-20T10:00:00Z",
        "knowledge_at": knowledge_at,
    }


def _draft(source: dict[str, object] | None = None) -> dict[str, object]:
    source = source or _source()
    evaluations = source["evaluations"]
    return {
        "created_at": "2026-07-20T12:00:00Z",
        "effective_at": "2026-07-20T11:00:00Z",
        "knowledge_at": "2026-07-20T12:00:00Z",
        "subject_scope": {
            "kind": "cohort",
            "refs": ["synthetic-cohort-002", "synthetic-cohort-001"],
        },
        "pattern_family": "outcome_conditioning",
        "hypothesis_statement": (
            "The observed association may persist in comparable synthetic episodes."
        ),
        "supporting_evidence": [
            _evidence(source, evaluations[1]["evaluation_id"], knowledge_at="2026-07-20T11:30:00Z"),
            _evidence(source, evaluations[0]["evaluation_id"], knowledge_at="2026-07-20T11:00:00Z"),
        ],
        "counterevidence": [],
        "source_gaps": [
            {
                "description": "Comparable synthetic episodes are not yet available.",
                "affected_refs": ["synthetic-episode-003", "synthetic-episode-002"],
            }
        ],
        "alternative_explanations": [
            "Opportunity quality may have changed.",
            "Portfolio conditions may have changed.",
        ],
        "applicability_conditions": [
            "Only the frozen synthetic cohort is covered.",
            "Evidence is bounded by the stated cutoff.",
        ],
        "disconfirming_observations": [
            "The association disappears in comparable episodes.",
            "The association reverses with reviewed intent held constant.",
        ],
        "observation_plan": {
            "question": "Does the association persist?",
            "required_facts": [
                "reviewed decision intent",
                "pre-event portfolio context",
            ],
        },
        "provenance": {
            "submitter_kind": "human_reviewed_sidecar",
            "source_locator": "synthetic/candidate.json",
            "tool_version": "p2h.behavior_hypothesis_candidate.builder.v1",
        },
    }


def _event(candidate_id: str) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
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
        },
    }


def test_candidate_builder_is_stable_for_mapping_and_set_reordering() -> None:
    draft = _draft()
    first = build_behavior_hypothesis_candidate(draft)
    reordered = dict(reversed(list(deepcopy(draft).items())))
    reordered["subject_scope"]["refs"].reverse()
    reordered["supporting_evidence"].reverse()
    reordered["source_gaps"][0]["affected_refs"].reverse()

    assert build_behavior_hypothesis_candidate(reordered) == first
    assert first["candidate_id"].startswith("candidate:")
    assert first["provenance"]["canonical_hash"] == first["canonical_hash"]


def test_candidate_builder_preserves_semantic_list_order() -> None:
    draft = _draft()
    reordered = deepcopy(draft)
    reordered["alternative_explanations"].reverse()

    first = build_behavior_hypothesis_candidate(draft)
    second = build_behavior_hypothesis_candidate(reordered)

    assert second["alternative_explanations"] == list(
        reversed(first["alternative_explanations"])
    )
    assert second["canonical_hash"] != first["canonical_hash"]


def test_timezone_equivalent_candidate_inputs_are_identical() -> None:
    utc = _draft()
    offset = deepcopy(utc)
    offset.update(
        {
            "created_at": "2026-07-20T20:00:00+08:00",
            "effective_at": "2026-07-20T19:00:00+08:00",
            "knowledge_at": "2026-07-20T20:00:00+08:00",
        }
    )
    for ref in offset["supporting_evidence"]:
        ref["effective_at"] = "2026-07-20T18:00:00+08:00"
    offset["supporting_evidence"][0]["knowledge_at"] = "2026-07-20T19:30:00+08:00"
    offset["supporting_evidence"][1]["knowledge_at"] = "2026-07-20T19:00:00+08:00"

    assert build_behavior_hypothesis_candidate(offset) == build_behavior_hypothesis_candidate(utc)


def test_candidate_validator_detects_identity_drift_and_policy_violations() -> None:
    candidate = build_behavior_hypothesis_candidate(_draft())
    assert validate_behavior_hypothesis_candidate(candidate)["validation_status"] == "accepted"

    tampered = deepcopy(candidate)
    tampered["hypothesis_statement"] = "You should buy immediately because greed caused the loss."
    validation = validate_behavior_hypothesis_candidate(tampered)

    assert validation["validation_status"] == "blocked"
    assert "CANDIDATE_ID_MISMATCH" in validation["finding_codes"]
    assert "CANDIDATE_HASH_MISMATCH" in validation["finding_codes"]
    assert "POLICY_DIRECT_ADVICE" in validation["finding_codes"]
    assert "POLICY_PSYCHOLOGY_DIAGNOSIS" in validation["finding_codes"]


def test_future_knowledge_and_unknown_fields_fail_closed() -> None:
    future = _draft()
    future["supporting_evidence"][0]["knowledge_at"] = "2026-07-20T12:00:01Z"
    with pytest.raises(BehaviorHypothesisCandidateError, match="after knowledge_at"):
        build_behavior_hypothesis_candidate(future)

    prohibited = _draft()
    prohibited["position_instruction"] = "increase"
    with pytest.raises(BehaviorHypothesisCandidateError, match="unsupported fields"):
        build_behavior_hypothesis_candidate(prohibited)


def test_source_replay_verifies_exact_hash_type_and_artifact_id() -> None:
    source = _source()
    candidate = build_behavior_hypothesis_candidate(_draft(source))

    validation = replay_validate_behavior_hypothesis_candidate(
        candidate, source_artifacts=[source]
    )

    assert validation["validation_status"] == "accepted"
    assert validation["source_verification"] == {"status": "verified"}


def test_source_replay_reports_hash_mismatch_missing_and_ambiguous_refs() -> None:
    source = _source()
    candidate = build_behavior_hypothesis_candidate(_draft(source))

    wrong_hash = deepcopy(candidate)
    wrong_hash["supporting_evidence"][0]["canonical_hash"] = "sha256:" + "f" * 64
    validation = replay_validate_behavior_hypothesis_candidate(
        wrong_hash, source_artifacts=[source]
    )
    assert "SOURCE_HASH_MISMATCH" in validation["finding_codes"]

    missing = deepcopy(candidate)
    missing["supporting_evidence"][0]["artifact_id"] = "evaluation:" + "9" * 32
    validation = replay_validate_behavior_hypothesis_candidate(
        missing, source_artifacts=[source]
    )
    assert "SOURCE_REF_MISSING" in validation["finding_codes"]

    ambiguous_source = deepcopy(source)
    ambiguous_source.pop("content_id")
    ambiguous_source["evaluations"].append(deepcopy(ambiguous_source["evaluations"][0]))
    ambiguous_source["content_id"] = _hash(ambiguous_source)
    ambiguous = build_behavior_hypothesis_candidate(_draft(ambiguous_source))
    validation = replay_validate_behavior_hypothesis_candidate(
        ambiguous, source_artifacts=[ambiguous_source]
    )
    assert "SOURCE_REF_AMBIGUOUS" in validation["finding_codes"]


def test_source_replay_rejects_tampered_source_content() -> None:
    source = _source()
    candidate = build_behavior_hypothesis_candidate(_draft(source))
    source["evaluations"][0]["status"] = "tampered"

    validation = replay_validate_behavior_hypothesis_candidate(
        candidate, source_artifacts=[source]
    )

    assert "SOURCE_CONTENT_HASH_MISMATCH" in validation["finding_codes"]


def test_review_event_builder_and_validator_are_deterministic() -> None:
    candidate = build_behavior_hypothesis_candidate(_draft())
    draft = _event(candidate["candidate_id"])
    event = build_behavior_hypothesis_review_event(draft)
    timezone_equivalent = deepcopy(draft)
    timezone_equivalent.update(
        {
            "reviewed_at": "2026-07-20T21:00:00+08:00",
            "effective_at": "2026-07-20T21:00:00+08:00",
            "knowledge_at": "2026-07-20T21:00:00+08:00",
            "evidence_cutoff": "2026-07-20T20:00:00+08:00",
        }
    )

    assert build_behavior_hypothesis_review_event(timezone_equivalent) == event
    assert validate_behavior_hypothesis_review_event(event)["validation_status"] == "accepted"


def test_review_event_time_and_supersession_rules_fail_closed() -> None:
    candidate = build_behavior_hypothesis_candidate(_draft())
    event = _event(candidate["candidate_id"])
    event["evidence_cutoff"] = "2026-07-20T13:00:01Z"
    with pytest.raises(BehaviorHypothesisCandidateError, match="evidence_cutoff"):
        build_behavior_hypothesis_review_event(event)

    superseded = _event(candidate["candidate_id"])
    superseded["event_type"] = "superseded"
    with pytest.raises(BehaviorHypothesisCandidateError, match="supersession reference"):
        build_behavior_hypothesis_review_event(superseded)
