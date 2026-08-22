from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

from src.investment_review.artifact_io import canonical_json_bytes
from src.investment_review.behavior_hypothesis_candidates import (
    build_behavior_hypothesis_candidate,
    build_behavior_hypothesis_review_event,
)
from src.investment_review.behavior_observation_protocols import (
    ObservationProtocolError,
    build_observation_protocol,
    build_observation_protocol_review_event,
    replay_validate_observation_protocol,
    validate_observation_protocol,
    validate_observation_protocol_review_event,
)


def _hash(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _inputs() -> tuple[dict[str, object], dict[str, object], list[dict[str, object]], dict[str, object]]:
    source_material: dict[str, object] = {
        "schema_version": "p2h.synthetic_source.v1",
        "artifact_type": "synthetic_evidence_set",
        "evaluations": [
            {"evaluation_id": "evaluation:" + "2" * 32, "status": "observed"}
        ],
    }
    source = {**source_material, "content_id": _hash(source_material)}
    candidate = build_behavior_hypothesis_candidate(
        {
            "created_at": "2026-07-20T12:00:00Z",
            "effective_at": "2026-07-20T11:00:00Z",
            "knowledge_at": "2026-07-20T12:00:00Z",
            "subject_scope": {"kind": "cohort", "refs": ["synthetic-cohort-002"]},
            "pattern_family": "sequence",
            "hypothesis_statement": "The observed sequence may recur in comparable episodes.",
            "supporting_evidence": [
                {
                    "artifact_type": source["artifact_type"],
                    "artifact_id": source["evaluations"][0]["evaluation_id"],
                    "canonical_hash": source["content_id"],
                    "source_locator": "synthetic/source.json",
                    "effective_at": "2026-07-20T10:00:00Z",
                    "knowledge_at": "2026-07-20T11:30:00Z",
                }
            ],
            "counterevidence": [],
            "source_gaps": [
                {"description": "More episodes are missing.", "affected_refs": []}
            ],
            "alternative_explanations": ["The available episode set may be narrow."],
            "applicability_conditions": ["Only the synthetic cohort is covered."],
            "disconfirming_observations": ["The sequence is absent in later episodes."],
            "observation_plan": {
                "question": "Does the sequence recur?",
                "required_facts": ["event order"],
            },
            "provenance": {
                "submitter_kind": "human_reviewed_sidecar",
                "source_locator": "synthetic/candidate.json",
                "tool_version": "p2h.behavior_hypothesis_candidate.builder.v1",
            },
        }
    )

    def event(event_type: str, hour: int) -> dict[str, object]:
        timestamp = f"2026-07-20T{hour:02d}:00:00Z"
        return build_behavior_hypothesis_review_event(
            {
                "candidate_id": candidate["candidate_id"],
                "event_type": event_type,
                "reviewed_at": timestamp,
                "effective_at": timestamp,
                "knowledge_at": timestamp,
                "reviewer_ref": "synthetic-human-reviewer",
                "rationale": f"The human reviewer records {event_type}.",
                "evidence_cutoff": "2026-07-20T12:00:00Z",
                "supersedes_event_id": None,
                "supersedes_candidate_id": None,
                "provenance": {
                    "submitter_kind": "human",
                    "source_locator": f"synthetic/{event_type}.json",
                    "tool_version": "p2h.behavior_hypothesis_review_event.builder.v1",
                },
            }
        )

    events = [event("submitted", 13), event("accepted_for_observation", 14)]
    draft: dict[str, object] = {
        "created_at": "2026-07-20T15:00:00Z",
        "effective_at": "2026-07-20T15:00:00Z",
        "knowledge_at": "2026-07-20T15:00:00Z",
        "accepted_projection_as_of": "2026-07-20T14:00:00Z",
        "accepted_projection_knowledge_cutoff": "2026-07-20T14:00:00Z",
        "question": "Does the sequence recur in comparable synthetic episodes?",
        "required_fact_specs": [
            {
                "fact_key": "event_order",
                "description": "The event order known at the checkpoint.",
                "acceptable_source_types": ["episode_fact"],
            }
        ],
        "observation_window": {
            "starts_at": "2026-07-21T00:00:00Z",
            "ends_at": "2026-08-20T00:00:00Z",
            "review_checkpoints": ["2026-08-01T00:00:00Z"],
        },
        "applicability_conditions": ["Only comparable synthetic episodes are covered."],
        "disconfirming_conditions": ["The sequence is absent in later episodes."],
        "stop_conditions": ["The exact source lineage cannot be reproduced."],
        "expiry_at": "2026-08-21T00:00:00Z",
        "missing_evidence_policy": {
            "on_missing": "preserve_missing",
            "on_partial": "preserve_partial",
            "on_ambiguous": "preserve_ambiguous",
            "allow_inference": False,
        },
        "privacy_scope": {
            "data_classification": "synthetic",
            "allowed_source_kinds": ["synthetic_stage1_artifact"],
            "prohibited_data_kinds": [
                "portfolio_sqlite",
                "broker_export",
                "credentials",
                "order_execution",
            ],
            "contains_direct_identifiers": False,
        },
        "provenance": {
            "submitter_kind": "human",
            "human_confirmed": True,
            "source_locator": "synthetic/protocol.json",
            "tool_version": "p2h.observation_protocol.builder.v1",
        },
    }
    return source, candidate, events, draft


def _protocol_inputs() -> tuple[dict[str, object], dict[str, object], list[dict[str, object]], dict[str, object]]:
    source, candidate, events, draft = _inputs()
    protocol = build_observation_protocol(
        draft,
        candidate=candidate,
        review_events=events,
        candidate_source_artifacts=[source],
    )
    return source, candidate, events, protocol


def test_exact_stage1_source_event_set_and_projection_replay_are_verified() -> None:
    source, candidate, events, protocol = _protocol_inputs()
    result = replay_validate_observation_protocol(
        protocol,
        candidate=candidate,
        review_events=list(reversed(events)),
        candidate_source_artifacts=[source],
    )
    assert result["validation_status"] == "accepted"
    assert result["source_verification"] == {"status": "verified"}
    assert result["finding_codes"] == []


def test_candidate_event_source_and_projection_drift_fail_closed() -> None:
    source, candidate, events, protocol = _protocol_inputs()

    candidate_drift = deepcopy(candidate)
    candidate_drift["canonical_hash"] = "sha256:" + "0" * 64
    result = replay_validate_observation_protocol(
        protocol,
        candidate=candidate_drift,
        review_events=events,
        candidate_source_artifacts=[source],
    )
    assert result["validation_status"] == "blocked"
    assert "STAGE1_CANDIDATE_HASH_MISMATCH" in result["finding_codes"]

    missing_event = replay_validate_observation_protocol(
        protocol,
        candidate=candidate,
        review_events=events[:1],
        candidate_source_artifacts=[source],
    )
    assert "STAGE1_REVIEW_EVENT_SET_INVALID" in missing_event["finding_codes"]

    source_drift = deepcopy(source)
    source_drift["evaluations"][0]["status"] = "tampered"
    replay = replay_validate_observation_protocol(
        protocol,
        candidate=candidate,
        review_events=events,
        candidate_source_artifacts=[source_drift],
    )
    assert "STAGE1_SOURCE_REPLAY_FAILED" in replay["finding_codes"]

    projection_drift = deepcopy(protocol)
    projection_drift["candidate_binding"]["accepted_projection"]["projection_hash"] = (
        "sha256:" + "9" * 64
    )
    assert validate_observation_protocol(projection_drift)["validation_status"] == "blocked"


def test_protocol_identity_and_canonical_payload_tamper_are_rejected() -> None:
    _, _, _, protocol = _protocol_inputs()
    changed = deepcopy(protocol)
    changed["question"] = "A changed question must create a new protocol identity."
    result = validate_observation_protocol(changed)
    assert "PROTOCOL_ID_MISMATCH" in result["finding_codes"]
    assert "PROTOCOL_HASH_MISMATCH" in result["finding_codes"]


def test_draft_requires_human_confirmation_relative_locator_and_no_future_cutoff() -> None:
    source, candidate, events, draft = _inputs()

    not_confirmed = deepcopy(draft)
    not_confirmed["provenance"]["human_confirmed"] = False
    with pytest.raises(ObservationProtocolError, match="human confirmation"):
        build_observation_protocol(
            not_confirmed,
            candidate=candidate,
            review_events=events,
            candidate_source_artifacts=[source],
        )

    absolute = deepcopy(draft)
    absolute["provenance"]["source_locator"] = "C:\\Users\\example\\draft.json"
    with pytest.raises(ObservationProtocolError, match="relative locator"):
        build_observation_protocol(
            absolute,
            candidate=candidate,
            review_events=events,
            candidate_source_artifacts=[source],
        )

    future = deepcopy(draft)
    future["accepted_projection_knowledge_cutoff"] = "2026-07-20T16:00:00Z"
    with pytest.raises(ObservationProtocolError, match="future Stage 1 knowledge"):
        build_observation_protocol(
            future,
            candidate=candidate,
            review_events=events,
            candidate_source_artifacts=[source],
        )


def test_event_requires_human_provenance_and_rejects_advice_text() -> None:
    _, _, _, protocol = _protocol_inputs()
    base: dict[str, object] = {
        "protocol_id": protocol["protocol_id"],
        "event_type": "submitted",
        "reviewed_at": "2026-07-20T16:00:00Z",
        "effective_at": "2026-07-20T16:00:00Z",
        "knowledge_at": "2026-07-20T16:00:00Z",
        "reviewer_ref": "synthetic-human-reviewer",
        "rationale": "The protocol is submitted for human review.",
        "evidence_cutoff": "2026-07-20T15:00:00Z",
        "supersedes_event_id": None,
        "superseded_by_protocol_id": None,
        "provenance": {
            "submitter_kind": "human",
            "source_locator": "synthetic/submitted.json",
            "tool_version": "p2h.observation_protocol_review_event.builder.v1",
        },
    }
    nonhuman = deepcopy(base)
    nonhuman["provenance"]["submitter_kind"] = "agent_assisted"
    with pytest.raises(ObservationProtocolError, match="human-authored"):
        build_observation_protocol_review_event(nonhuman)

    advice = build_observation_protocol_review_event(base)
    advice["rationale"] = "You should buy more now."
    result = validate_observation_protocol_review_event(advice)
    assert "POLICY_DIRECT_ADVICE" in result["finding_codes"]
