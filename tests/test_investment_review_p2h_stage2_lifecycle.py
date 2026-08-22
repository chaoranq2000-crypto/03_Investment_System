from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path

import pytest

from src.investment_review.artifact_io import canonical_json_bytes
from src.investment_review.behavior_hypothesis_candidates import (
    build_behavior_hypothesis_candidate,
    build_behavior_hypothesis_review_event,
)
from src.investment_review.behavior_observation_protocols import (
    PROTOCOL_STATE_SEMANTICS,
    ObservationProtocolProjectionError,
    build_observation_protocol,
    build_observation_protocol_review_event,
    project_observation_protocol_state,
    validate_observation_protocol_ledger,
    validate_observation_protocol_projection,
)
from src.investment_review.store import ReviewStore, ReviewStoreError


def _hash(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _inputs() -> tuple[dict[str, object], dict[str, object], list[dict[str, object]], dict[str, object]]:
    source_material: dict[str, object] = {
        "schema_version": "p2h.synthetic_source.v1",
        "artifact_type": "synthetic_evidence_set",
        "evaluations": [
            {"evaluation_id": "evaluation:" + "4" * 32, "status": "observed"}
        ],
    }
    source = {**source_material, "content_id": _hash(source_material)}
    candidate = build_behavior_hypothesis_candidate(
        {
            "created_at": "2026-07-20T12:00:00Z",
            "effective_at": "2026-07-20T11:00:00Z",
            "knowledge_at": "2026-07-20T12:00:00Z",
            "subject_scope": {"kind": "cohort", "refs": ["synthetic-cohort-004"]},
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
            "source_gaps": [{"description": "Later episodes are missing.", "affected_refs": []}],
            "alternative_explanations": ["The synthetic episode set may be narrow."],
            "applicability_conditions": ["Only the synthetic cohort is covered."],
            "disconfirming_observations": ["The sequence is absent later."],
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

    def stage1_event(event_type: str, hour: int) -> dict[str, object]:
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

    stage1_events = [
        stage1_event("submitted", 13),
        stage1_event("accepted_for_observation", 14),
    ]
    protocol = build_observation_protocol(
        {
            "created_at": "2026-07-20T15:00:00Z",
            "effective_at": "2026-07-20T15:00:00Z",
            "knowledge_at": "2026-07-20T15:00:00Z",
            "accepted_projection_as_of": "2026-07-20T14:00:00Z",
            "accepted_projection_knowledge_cutoff": "2026-07-20T14:00:00Z",
            "question": "Does the sequence recur in comparable synthetic episodes?",
            "required_fact_specs": [
                {
                    "fact_key": "event_order",
                    "description": "The event order known at each checkpoint.",
                    "acceptable_source_types": ["episode_fact"],
                }
            ],
            "observation_window": {
                "starts_at": "2026-07-21T00:00:00Z",
                "ends_at": "2026-08-20T00:00:00Z",
                "review_checkpoints": ["2026-08-01T00:00:00Z"],
            },
            "applicability_conditions": ["Only comparable synthetic episodes are covered."],
            "disconfirming_conditions": ["The sequence is absent later."],
            "stop_conditions": ["Exact source lineage becomes unavailable."],
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
        },
        candidate=candidate,
        review_events=stage1_events,
        candidate_source_artifacts=[source],
    )
    return source, candidate, stage1_events, protocol


def _event(
    protocol_id: str,
    event_type: str,
    timestamp: str,
    *,
    effective_at: str | None = None,
    knowledge_at: str | None = None,
    supersedes_event_id: str | None = None,
    superseded_by_protocol_id: str | None = None,
) -> dict[str, object]:
    return build_observation_protocol_review_event(
        {
            "protocol_id": protocol_id,
            "event_type": event_type,
            "reviewed_at": timestamp,
            "effective_at": effective_at or timestamp,
            "knowledge_at": knowledge_at or timestamp,
            "reviewer_ref": "synthetic-human-reviewer",
            "rationale": f"The human reviewer records {event_type}.",
            "evidence_cutoff": "2026-07-20T15:00:00Z",
            "supersedes_event_id": supersedes_event_id,
            "superseded_by_protocol_id": superseded_by_protocol_id,
            "provenance": {
                "submitter_kind": "human",
                "source_locator": f"synthetic/protocol_{event_type}.json",
                "tool_version": "p2h.observation_protocol_review_event.builder.v1",
            },
        }
    )


def test_legal_lifecycle_note_and_completion_have_governance_only_semantics() -> None:
    _, _, _, protocol = _inputs()
    submitted = _event(protocol["protocol_id"], "submitted", "2026-07-20T16:00:00Z")
    approved = _event(
        protocol["protocol_id"], "approved_for_observation", "2026-07-20T17:00:00Z"
    )
    activated = _event(protocol["protocol_id"], "activated", "2026-07-20T18:00:00Z")
    note = _event(protocol["protocol_id"], "note_added", "2026-07-20T19:00:00Z")
    paused = _event(protocol["protocol_id"], "paused", "2026-07-20T20:00:00Z")
    reactivated = _event(protocol["protocol_id"], "activated", "2026-07-20T21:00:00Z")
    completed = _event(protocol["protocol_id"], "completed", "2026-07-20T22:00:00Z")
    events = [submitted, approved, activated, note, paused, reactivated, completed]

    with_note = project_observation_protocol_state(
        protocol,
        events,
        as_of="2026-07-20T19:00:00Z",
        knowledge_cutoff="2026-07-20T19:00:00Z",
    )
    final = project_observation_protocol_state(
        protocol,
        events,
        as_of="2026-07-20T22:00:00Z",
        knowledge_cutoff="2026-07-20T22:00:00Z",
    )

    assert with_note["status"] == "active"
    assert with_note["last_event_id"] == note["protocol_review_event_id"]
    assert final["status"] == "completed"
    assert final["state_semantics"] == PROTOCOL_STATE_SEMANTICS
    assert "proven_true" not in canonical_json_bytes(final).decode("utf-8")
    assert validate_observation_protocol_projection(final)["validation_status"] == "accepted"
    tampered = deepcopy(final)
    tampered["status"] = "active"
    assert "PROTOCOL_PROJECTION_HASH_MISMATCH" in validate_observation_protocol_projection(
        tampered
    )["finding_codes"]


def test_event_permutation_duplicate_replay_and_future_knowledge_are_deterministic() -> None:
    _, _, _, protocol = _inputs()
    submitted = _event(protocol["protocol_id"], "submitted", "2026-07-20T16:00:00Z")
    approved = _event(
        protocol["protocol_id"],
        "approved_for_observation",
        "2026-07-20T19:00:00Z",
        effective_at="2026-07-20T17:00:00Z",
        knowledge_at="2026-07-20T19:00:00Z",
    )

    before_knowledge = project_observation_protocol_state(
        protocol,
        [approved, submitted],
        as_of="2026-07-20T18:00:00Z",
        knowledge_cutoff="2026-07-20T18:00:00Z",
    )
    ordered = project_observation_protocol_state(
        protocol,
        [submitted, approved],
        as_of="2026-07-20T19:00:00Z",
        knowledge_cutoff="2026-07-20T19:00:00Z",
    )
    shuffled = project_observation_protocol_state(
        protocol,
        [approved, submitted, submitted],
        as_of="2026-07-20T19:00:00Z",
        knowledge_cutoff="2026-07-20T19:00:00Z",
    )

    assert before_knowledge["status"] == "submitted"
    assert canonical_json_bytes(ordered) == canonical_json_bytes(shuffled)


def test_illegal_transition_orphan_conflict_and_same_id_drift_fail_explicitly() -> None:
    _, _, _, protocol = _inputs()
    submitted = _event(protocol["protocol_id"], "submitted", "2026-07-20T16:00:00Z")
    activated = _event(protocol["protocol_id"], "activated", "2026-07-20T17:00:00Z")
    with pytest.raises(
        ObservationProtocolProjectionError, match="INVALID_PROTOCOL_TRANSITION"
    ):
        project_observation_protocol_state(
            protocol,
            [submitted, activated],
            as_of="2026-07-20T17:00:00Z",
            knowledge_cutoff="2026-07-20T17:00:00Z",
        )

    approved = _event(
        protocol["protocol_id"], "approved_for_observation", "2026-07-20T17:00:00Z"
    )
    abandoned = _event(protocol["protocol_id"], "abandoned", "2026-07-20T17:00:00Z")
    with pytest.raises(
        ObservationProtocolProjectionError, match="CONCURRENT_PROTOCOL_STATE_EVENTS"
    ):
        project_observation_protocol_state(
            protocol,
            [submitted, approved, abandoned],
            as_of="2026-07-20T17:00:00Z",
            knowledge_cutoff="2026-07-20T17:00:00Z",
        )

    orphan = _event("protocol:" + "8" * 32, "submitted", "2026-07-20T16:00:00Z")
    result = validate_observation_protocol_ledger(
        protocol,
        [orphan],
        as_of="2026-07-20T16:00:00Z",
        knowledge_cutoff="2026-07-20T16:00:00Z",
    )
    assert result["finding_codes"] == ["ORPHAN_PROTOCOL_REVIEW_EVENT"]

    drift = deepcopy(submitted)
    drift["rationale"] = "Divergent payload under one event identity."
    with pytest.raises(
        ObservationProtocolProjectionError, match="PROTOCOL_REVIEW_EVENT_ID_CONFLICT"
    ):
        project_observation_protocol_state(
            protocol,
            [submitted, drift],
            as_of="2026-07-20T16:00:00Z",
            knowledge_cutoff="2026-07-20T16:00:00Z",
        )


def test_expiry_is_separate_from_state_and_blocks_late_activation() -> None:
    _, _, _, protocol = _inputs()
    submitted = _event(protocol["protocol_id"], "submitted", "2026-07-20T16:00:00Z")
    expired = project_observation_protocol_state(
        protocol,
        [submitted],
        as_of="2026-08-21T00:00:00Z",
        knowledge_cutoff="2026-08-21T00:00:00Z",
    )
    assert expired["status"] == "submitted"
    assert expired["expiry_state"] == "expired"

    late_approval = _event(
        protocol["protocol_id"],
        "approved_for_observation",
        "2026-08-21T00:00:00Z",
    )
    with pytest.raises(ObservationProtocolProjectionError, match="PROTOCOL_EXPIRED"):
        project_observation_protocol_state(
            protocol,
            [submitted, late_approval],
            as_of="2026-08-21T00:00:00Z",
            knowledge_cutoff="2026-08-21T00:00:00Z",
        )


def test_supersession_requires_an_earlier_visible_event() -> None:
    _, _, _, protocol = _inputs()
    submitted = _event(protocol["protocol_id"], "submitted", "2026-07-20T16:00:00Z")
    superseded = _event(
        protocol["protocol_id"],
        "superseded",
        "2026-07-20T17:00:00Z",
        supersedes_event_id="protocol_review_event:" + "7" * 32,
        superseded_by_protocol_id="protocol:" + "9" * 32,
    )
    with pytest.raises(
        ObservationProtocolProjectionError,
        match="PROTOCOL_SUPERSESSION_EVENT_NOT_VISIBLE",
    ):
        project_observation_protocol_state(
            protocol,
            [submitted, superseded],
            as_of="2026-07-20T17:00:00Z",
            knowledge_cutoff="2026-07-20T17:00:00Z",
        )

    valid = _event(
        protocol["protocol_id"],
        "superseded",
        "2026-07-20T17:00:00Z",
        supersedes_event_id=submitted["protocol_review_event_id"],
        superseded_by_protocol_id="protocol:" + "9" * 32,
    )
    projection = project_observation_protocol_state(
        protocol,
        [valid, submitted],
        as_of="2026-07-20T17:00:00Z",
        knowledge_cutoff="2026-07-20T17:00:00Z",
    )
    assert projection["status"] == "superseded"


def test_store_accepts_out_of_order_events_but_rejects_concurrent_state_time(tmp_path: Path) -> None:
    source, candidate, stage1_events, protocol = _inputs()
    store = ReviewStore(tmp_path / "review.sqlite3")
    store.initialize()
    store.save_behavior_hypothesis_candidate(candidate, source_artifacts=[source])
    for event in stage1_events:
        store.save_behavior_hypothesis_review_event(event)
    store.save_observation_protocol(protocol, candidate_source_artifacts=[source])

    submitted = _event(protocol["protocol_id"], "submitted", "2026-07-20T16:00:00Z")
    approved = _event(
        protocol["protocol_id"], "approved_for_observation", "2026-07-20T17:00:00Z"
    )
    store.save_observation_protocol_review_event(approved)
    store.save_observation_protocol_review_event(submitted)
    projection = store.project_observation_protocol(
        protocol["protocol_id"],
        as_of="2026-07-20T17:00:00Z",
        knowledge_cutoff="2026-07-20T17:00:00Z",
    )
    assert projection["status"] == "approved_for_observation"

    concurrent = _event(
        protocol["protocol_id"], "abandoned", "2026-07-20T17:00:00Z"
    )
    with pytest.raises(ReviewStoreError, match="CONCURRENT_PROTOCOL_STATE_EVENTS"):
        store.save_observation_protocol_review_event(concurrent)
