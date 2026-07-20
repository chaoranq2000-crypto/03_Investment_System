from __future__ import annotations

import hashlib
import sqlite3
from copy import deepcopy
from pathlib import Path

import pytest

from src.investment_review.artifact_io import canonical_json_bytes
from src.investment_review.behavior_hypothesis_candidates import (
    ACCEPTED_FOR_OBSERVATION_SEMANTICS,
    BehaviorHypothesisProjectionError,
    build_behavior_hypothesis_candidate,
    build_behavior_hypothesis_review_event,
    project_behavior_hypothesis_state,
    validate_behavior_hypothesis_review_ledger,
)
from src.investment_review.store import ReviewStore


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
            }
        ],
    }
    return {**material, "content_id": _hash(material)}


def _candidate(source: dict[str, object]) -> dict[str, object]:
    return build_behavior_hypothesis_candidate(
        {
            "created_at": "2026-07-20T12:00:00Z",
            "effective_at": "2026-07-20T11:00:00Z",
            "knowledge_at": "2026-07-20T12:00:00Z",
            "subject_scope": {
                "kind": "cohort",
                "refs": ["synthetic-cohort-001"],
            },
            "pattern_family": "outcome_conditioning",
            "hypothesis_statement": (
                "The observed association may persist in comparable synthetic episodes."
            ),
            "supporting_evidence": [
                {
                    "artifact_type": source["schema_version"],
                    "artifact_id": source["evaluations"][0]["evaluation_id"],
                    "canonical_hash": source["content_id"],
                    "source_locator": "synthetic/p2g_observation.json",
                    "effective_at": "2026-07-20T10:00:00Z",
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
            "applicability_conditions": [
                "Only the frozen synthetic cohort is covered."
            ],
            "disconfirming_observations": [
                "The association disappears in comparable episodes."
            ],
            "observation_plan": {
                "question": "Does the association persist?",
                "required_facts": ["reviewed decision intent"],
            },
            "provenance": {
                "submitter_kind": "human_reviewed_sidecar",
                "source_locator": "synthetic/candidate.json",
                "tool_version": "p2h.behavior_hypothesis_candidate.builder.v1",
            },
        }
    )


def _event(
    candidate_id: str,
    event_type: str,
    hour: int,
    *,
    supersedes_event_id: str | None = None,
    supersedes_candidate_id: str | None = None,
) -> dict[str, object]:
    timestamp = f"2026-07-20T{hour:02d}:00:00Z"
    rationale = {
        "submitted": "The candidate is submitted for bounded human review.",
        "accepted_for_observation": (
            "Evidence supports continued observation only; causality remains unproven."
        ),
        "revision_requested": "The evidence boundary requires a new immutable candidate.",
        "rejected": "The current evidence does not support continued observation.",
        "superseded": "A later immutable record replaces this candidate for observation.",
        "note_added": "This note preserves a human audit clarification.",
    }[event_type]
    return build_behavior_hypothesis_review_event(
        {
            "candidate_id": candidate_id,
            "event_type": event_type,
            "reviewed_at": timestamp,
            "effective_at": timestamp,
            "knowledge_at": timestamp,
            "reviewer_ref": "synthetic-human-reviewer",
            "rationale": rationale,
            "evidence_cutoff": "2026-07-20T12:00:00Z",
            "supersedes_event_id": supersedes_event_id,
            "supersedes_candidate_id": supersedes_candidate_id,
            "provenance": {
                "submitter_kind": "human",
                "source_locator": f"synthetic/{event_type}.json",
                "tool_version": "p2h.behavior_hypothesis_review_event.builder.v1",
            },
        }
    )


def test_legal_review_flow_projects_accepted_as_observation_not_proof() -> None:
    candidate = _candidate(_source())
    submitted = _event(candidate["candidate_id"], "submitted", 13)
    accepted = _event(candidate["candidate_id"], "accepted_for_observation", 14)

    projection = project_behavior_hypothesis_state(
        candidate,
        [submitted, accepted],
        as_of="2026-07-20T14:00:00Z",
        knowledge_cutoff="2026-07-20T14:00:00Z",
    )

    assert projection["status"] == "accepted_for_observation"
    assert projection["state_semantics"] == ACCEPTED_FOR_OBSERVATION_SEMANTICS
    assert "not proven" in projection["state_semantics"]
    assert "proven_true" not in projection.values()


def test_as_of_and_knowledge_cutoff_replay_historical_states() -> None:
    candidate = _candidate(_source())
    submitted = _event(candidate["candidate_id"], "submitted", 13)
    accepted = _event(candidate["candidate_id"], "accepted_for_observation", 14)
    events = [accepted, submitted]

    before = project_behavior_hypothesis_state(
        candidate,
        events,
        as_of="2026-07-20T12:59:59Z",
        knowledge_cutoff="2026-07-20T14:00:00Z",
    )
    submitted_state = project_behavior_hypothesis_state(
        candidate,
        events,
        as_of="2026-07-20T13:00:00Z",
        knowledge_cutoff="2026-07-20T13:00:00Z",
    )
    accepted_state = project_behavior_hypothesis_state(
        candidate,
        events,
        as_of="2026-07-20T14:00:00Z",
        knowledge_cutoff="2026-07-20T14:00:00Z",
    )

    assert before["status"] == "candidate"
    assert submitted_state["status"] == "submitted"
    assert accepted_state["status"] == "accepted_for_observation"


def test_out_of_order_and_duplicate_ingest_project_identically() -> None:
    candidate = _candidate(_source())
    submitted = _event(candidate["candidate_id"], "submitted", 13)
    accepted = _event(candidate["candidate_id"], "accepted_for_observation", 14)

    ordered = project_behavior_hypothesis_state(
        candidate,
        [submitted, accepted],
        as_of="2026-07-20T14:00:00Z",
        knowledge_cutoff="2026-07-20T14:00:00Z",
    )
    shuffled = project_behavior_hypothesis_state(
        candidate,
        [accepted, submitted, submitted],
        as_of="2026-07-20T14:00:00Z",
        knowledge_cutoff="2026-07-20T14:00:00Z",
    )

    assert canonical_json_bytes(shuffled) == canonical_json_bytes(ordered)


def test_invalid_transition_or_orphan_event_fails_explicitly() -> None:
    candidate = _candidate(_source())
    accepted = _event(candidate["candidate_id"], "accepted_for_observation", 14)
    with pytest.raises(
        BehaviorHypothesisProjectionError, match="INVALID_REVIEW_TRANSITION"
    ):
        project_behavior_hypothesis_state(
            candidate,
            [accepted],
            as_of="2026-07-20T14:00:00Z",
            knowledge_cutoff="2026-07-20T14:00:00Z",
        )

    orphan = _event("candidate:" + "9" * 32, "submitted", 13)
    validation = validate_behavior_hypothesis_review_ledger(
        candidate,
        [orphan],
        as_of="2026-07-20T14:00:00Z",
        knowledge_cutoff="2026-07-20T14:00:00Z",
    )
    assert validation["validation_status"] == "blocked"
    assert validation["finding_codes"] == ["ORPHAN_REVIEW_EVENT"]


def test_same_time_state_conflict_is_not_hidden_by_id_tie_breaker() -> None:
    candidate = _candidate(_source())
    submitted = _event(candidate["candidate_id"], "submitted", 13)
    accepted = _event(candidate["candidate_id"], "accepted_for_observation", 14)
    rejected = _event(candidate["candidate_id"], "rejected", 14)

    with pytest.raises(
        BehaviorHypothesisProjectionError, match="CONCURRENT_STATE_EVENTS"
    ):
        project_behavior_hypothesis_state(
            candidate,
            [submitted, accepted, rejected],
            as_of="2026-07-20T14:00:00Z",
            knowledge_cutoff="2026-07-20T14:00:00Z",
        )


def test_same_id_different_payload_is_an_explicit_ledger_conflict() -> None:
    candidate = _candidate(_source())
    submitted = _event(candidate["candidate_id"], "submitted", 13)
    conflicting = deepcopy(submitted)
    conflicting["rationale"] = "Divergent payload with the same event identity."

    with pytest.raises(
        BehaviorHypothesisProjectionError, match="REVIEW_EVENT_ID_CONFLICT"
    ):
        project_behavior_hypothesis_state(
            candidate,
            [submitted, conflicting],
            as_of="2026-07-20T13:00:00Z",
            knowledge_cutoff="2026-07-20T13:00:00Z",
        )


def test_supersession_preserves_the_historical_accepted_state() -> None:
    candidate = _candidate(_source())
    submitted = _event(candidate["candidate_id"], "submitted", 13)
    accepted = _event(candidate["candidate_id"], "accepted_for_observation", 14)
    superseded = _event(
        candidate["candidate_id"],
        "superseded",
        15,
        supersedes_event_id=accepted["review_event_id"],
    )
    events = [superseded, submitted, accepted]

    historical = project_behavior_hypothesis_state(
        candidate,
        events,
        as_of="2026-07-20T14:59:59Z",
        knowledge_cutoff="2026-07-20T14:59:59Z",
    )
    current = project_behavior_hypothesis_state(
        candidate,
        events,
        as_of="2026-07-20T15:00:00Z",
        knowledge_cutoff="2026-07-20T15:00:00Z",
    )

    assert historical["status"] == "accepted_for_observation"
    assert current["status"] == "superseded"
    assert accepted["review_event_id"] in current["applied_event_ids"]


def test_note_event_preserves_state_and_audit_order() -> None:
    candidate = _candidate(_source())
    submitted = _event(candidate["candidate_id"], "submitted", 13)
    accepted = _event(candidate["candidate_id"], "accepted_for_observation", 14)
    note = _event(candidate["candidate_id"], "note_added", 15)

    projection = project_behavior_hypothesis_state(
        candidate,
        [note, accepted, submitted],
        as_of="2026-07-20T15:00:00Z",
        knowledge_cutoff="2026-07-20T15:00:00Z",
    )

    assert projection["status"] == "accepted_for_observation"
    assert projection["last_event_id"] == note["review_event_id"]


def test_store_accepts_out_of_order_events_then_projects_strictly(tmp_path: Path) -> None:
    source = _source()
    candidate = _candidate(source)
    submitted = _event(candidate["candidate_id"], "submitted", 13)
    accepted = _event(candidate["candidate_id"], "accepted_for_observation", 14)
    store = ReviewStore(tmp_path / "review.sqlite3")
    store.initialize()
    store.save_behavior_hypothesis_candidate(candidate, source_artifacts=[source])

    store.save_behavior_hypothesis_review_event(accepted)
    with pytest.raises(
        BehaviorHypothesisProjectionError, match="INVALID_REVIEW_TRANSITION"
    ):
        store.project_behavior_hypothesis_candidate(
            candidate["candidate_id"],
            as_of="2026-07-20T14:00:00Z",
            knowledge_cutoff="2026-07-20T14:00:00Z",
        )
    store.save_behavior_hypothesis_review_event(submitted)

    projection = store.project_behavior_hypothesis_candidate(
        candidate["candidate_id"],
        as_of="2026-07-20T14:00:00Z",
        knowledge_cutoff="2026-07-20T14:00:00Z",
    )
    assert projection["status"] == "accepted_for_observation"
    assert store.list_behavior_hypothesis_candidates(
        status="accepted_for_observation"
    )[0]["projection"] == project_behavior_hypothesis_state(
        candidate,
        [submitted, accepted],
        as_of="9999-12-31T23:59:59Z",
        knowledge_cutoff="9999-12-31T23:59:59Z",
    )


def test_review_ledger_has_no_profile_playbook_or_intervention_side_effect(
    tmp_path: Path,
) -> None:
    source = _source()
    candidate = _candidate(source)
    store = ReviewStore(tmp_path / "review.sqlite3")
    store.initialize()
    store.save_behavior_hypothesis_candidate(candidate, source_artifacts=[source])
    store.save_behavior_hypothesis_review_event(
        _event(candidate["candidate_id"], "submitted", 13)
    )
    store.save_behavior_hypothesis_review_event(
        _event(candidate["candidate_id"], "accepted_for_observation", 14)
    )

    conn = sqlite3.connect(tmp_path / "review.sqlite3")
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    conn.close()
    assert not any(
        token in table.casefold()
        for table in tables
        for token in ("profile", "playbook", "intervention")
    )
    assert not hasattr(store, "update_personal_playbook")
