from __future__ import annotations

import hashlib
import sqlite3
from copy import deepcopy
from pathlib import Path

import pytest

from src.investment_review.artifact_io import canonical_json_bytes
from src.investment_review.behavior_hypothesis_candidates import (
    build_behavior_hypothesis_candidate,
    build_behavior_hypothesis_review_event,
)
from src.investment_review.behavior_observation_protocols import (
    build_observation_protocol,
    build_observation_protocol_review_event,
)
from src.investment_review.store import (
    APPLICATION_ID,
    DataConflictError,
    ReviewStore,
    ReviewStoreError,
)


def _hash(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _source() -> dict[str, object]:
    material: dict[str, object] = {
        "schema_version": "p2h.synthetic_source.v1",
        "artifact_type": "synthetic_evidence_set",
        "evaluations": [
            {"evaluation_id": "evaluation:" + "3" * 32, "status": "observed"}
        ],
    }
    return {**material, "content_id": _hash(material)}


def _candidate(source: dict[str, object]) -> dict[str, object]:
    return build_behavior_hypothesis_candidate(
        {
            "created_at": "2026-07-20T12:00:00Z",
            "effective_at": "2026-07-20T11:00:00Z",
            "knowledge_at": "2026-07-20T12:00:00Z",
            "subject_scope": {"kind": "cohort", "refs": ["synthetic-cohort-003"]},
            "pattern_family": "holding_period",
            "hypothesis_statement": "The observed association may recur in comparable episodes.",
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
            "source_gaps": [{"description": "More episodes are missing.", "affected_refs": []}],
            "alternative_explanations": ["The synthetic episode set may be narrow."],
            "applicability_conditions": ["Only the synthetic cohort is covered."],
            "disconfirming_observations": ["The association is absent later."],
            "observation_plan": {
                "question": "Does the association recur?",
                "required_facts": ["reviewed event sequence"],
            },
            "provenance": {
                "submitter_kind": "human_reviewed_sidecar",
                "source_locator": "synthetic/candidate.json",
                "tool_version": "p2h.behavior_hypothesis_candidate.builder.v1",
            },
        }
    )


def _stage1_event(candidate_id: str, event_type: str, hour: int) -> dict[str, object]:
    timestamp = f"2026-07-20T{hour:02d}:00:00Z"
    return build_behavior_hypothesis_review_event(
        {
            "candidate_id": candidate_id,
            "event_type": event_type,
            "reviewed_at": timestamp,
            "effective_at": timestamp,
            "knowledge_at": timestamp,
            "reviewer_ref": "synthetic-human-reviewer",
            "rationale": f"The reviewer records {event_type}.",
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


def _protocol(
    source: dict[str, object],
    candidate: dict[str, object],
    events: list[dict[str, object]],
    *,
    question: str = "Does the association recur in comparable synthetic episodes?",
) -> dict[str, object]:
    return build_observation_protocol(
        {
            "created_at": "2026-07-20T15:00:00Z",
            "effective_at": "2026-07-20T15:00:00Z",
            "knowledge_at": "2026-07-20T15:00:00Z",
            "accepted_projection_as_of": "2026-07-20T14:00:00Z",
            "accepted_projection_knowledge_cutoff": "2026-07-20T14:00:00Z",
            "question": question,
            "required_fact_specs": [
                {
                    "fact_key": "event_sequence",
                    "description": "The reviewed event sequence at each checkpoint.",
                    "acceptable_source_types": ["episode_fact"],
                }
            ],
            "observation_window": {
                "starts_at": "2026-07-21T00:00:00Z",
                "ends_at": "2026-08-20T00:00:00Z",
                "review_checkpoints": ["2026-08-01T00:00:00Z"],
            },
            "applicability_conditions": ["Only comparable synthetic episodes are covered."],
            "disconfirming_conditions": ["The association is absent later."],
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
        review_events=events,
        candidate_source_artifacts=[source],
    )


def _seed(store: ReviewStore) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]], dict[str, object]]:
    source = _source()
    candidate = _candidate(source)
    events = [
        _stage1_event(candidate["candidate_id"], "submitted", 13),
        _stage1_event(candidate["candidate_id"], "accepted_for_observation", 14),
    ]
    store.initialize()
    store.save_behavior_hypothesis_candidate(candidate, source_artifacts=[source])
    for event in events:
        store.save_behavior_hypothesis_review_event(event)
    protocol = _protocol(source, candidate, events)
    return source, candidate, events, protocol


def _protocol_event(protocol_id: str) -> dict[str, object]:
    return build_observation_protocol_review_event(
        {
            "protocol_id": protocol_id,
            "event_type": "submitted",
            "reviewed_at": "2026-07-20T16:00:00Z",
            "effective_at": "2026-07-20T16:00:00Z",
            "knowledge_at": "2026-07-20T16:00:00Z",
            "reviewer_ref": "synthetic-human-reviewer",
            "rationale": "The explicit protocol is submitted for human review.",
            "evidence_cutoff": "2026-07-20T15:00:00Z",
            "supersedes_event_id": None,
            "superseded_by_protocol_id": None,
            "provenance": {
                "submitter_kind": "human",
                "source_locator": "synthetic/protocol_submitted.json",
                "tool_version": "p2h.observation_protocol_review_event.builder.v1",
            },
        }
    )


def test_slice_a_tables_initialize_idempotently_and_preserve_existing_v2(tmp_path: Path) -> None:
    database = tmp_path / "review.sqlite3"
    store = ReviewStore(database)
    store.initialize()
    store.initialize()
    status = store.status()
    assert status["p2h_stage2_slice_a_schema_version"] == 1
    assert status["counts"]["behavior_observation_protocols"] == 0
    assert status["counts"]["behavior_observation_protocol_review_events"] == 0

    existing = tmp_path / "existing-v2.sqlite3"
    conn = sqlite3.connect(existing)
    conn.execute(f"PRAGMA application_id = {APPLICATION_ID}")
    conn.execute("PRAGMA user_version = 2")
    conn.execute("CREATE TABLE schema_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("INSERT INTO schema_meta VALUES ('schema_version', '2')")
    conn.execute("CREATE TABLE legacy_marker(value TEXT NOT NULL)")
    conn.execute("INSERT INTO legacy_marker VALUES ('preserved')")
    conn.commit()
    conn.close()

    upgraded = ReviewStore(existing)
    upgraded.initialize()
    conn = sqlite3.connect(existing)
    assert conn.execute("SELECT value FROM legacy_marker").fetchone()[0] == "preserved"
    assert conn.execute(
        "SELECT value FROM schema_meta WHERE key='p2h_stage2_slice_a_schema_version'"
    ).fetchone()[0] == "1"
    conn.close()


def test_protocol_ingest_is_source_replayed_create_only_and_queryable(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "review.sqlite3")
    source, candidate, _, protocol = _seed(store)
    candidate_before = canonical_json_bytes(store.get_behavior_hypothesis_candidate(candidate["candidate_id"]))
    source_before = canonical_json_bytes(source)

    first = store.save_observation_protocol(
        protocol, candidate_source_artifacts=[source]
    )
    second = store.save_observation_protocol(
        protocol, candidate_source_artifacts=[source]
    )

    assert first["status"] == "INSERTED"
    assert second["status"] == "SKIPPED"
    assert store.get_observation_protocol(protocol["protocol_id"]) == protocol
    assert store.list_observation_protocols(
        protocol_id=protocol["protocol_id"],
        candidate_id=candidate["candidate_id"],
        created_from="2026-07-20T15:00:00Z",
        created_to="2026-07-20T15:00:00Z",
    ) == [protocol]
    assert canonical_json_bytes(store.get_behavior_hypothesis_candidate(candidate["candidate_id"])) == candidate_before
    assert canonical_json_bytes(source) == source_before


def test_protocol_same_id_drift_and_stage1_event_set_drift_fail_closed(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "review.sqlite3")
    source, candidate, _, protocol = _seed(store)
    store.save_observation_protocol(protocol, candidate_source_artifacts=[source])

    conflict = deepcopy(protocol)
    conflict["question"] = "A divergent payload under the same protocol identity."
    with pytest.raises(DataConflictError, match="changed after creation"):
        store.save_observation_protocol(conflict, candidate_source_artifacts=[source])

    source_drift = deepcopy(source)
    source_drift["evaluations"][0]["status"] = "tampered"
    with pytest.raises(ReviewStoreError, match="STAGE1_SOURCE_REPLAY_FAILED"):
        store.save_observation_protocol(
            protocol, candidate_source_artifacts=[source_drift]
        )

    note = _stage1_event(candidate["candidate_id"], "note_added", 15)
    store.save_behavior_hypothesis_review_event(note)
    with pytest.raises(ReviewStoreError, match="STAGE1_REVIEW_EVENT_SET_MISMATCH"):
        store.save_observation_protocol(protocol, candidate_source_artifacts=[source])


def test_protocol_event_is_immutable_dual_time_queryable_and_orphan_safe(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "review.sqlite3")
    source, _, _, protocol = _seed(store)
    store.save_observation_protocol(protocol, candidate_source_artifacts=[source])
    event = _protocol_event(protocol["protocol_id"])

    assert store.save_observation_protocol_review_event(event)["status"] == "INSERTED"
    assert store.save_observation_protocol_review_event(event)["status"] == "SKIPPED"
    assert store.list_observation_protocol_review_events(
        protocol_id=protocol["protocol_id"],
        event_type="submitted",
        as_of="2026-07-20T16:00:00Z",
        knowledge_cutoff="2026-07-20T16:00:00Z",
        reviewed_from="2026-07-20T16:00:00Z",
        reviewed_to="2026-07-20T16:00:00Z",
    ) == [event]
    assert not store.list_observation_protocol_review_events(
        as_of="2026-07-20T15:59:59Z"
    )

    conflict = deepcopy(event)
    conflict["rationale"] = "Divergent immutable content."
    with pytest.raises(DataConflictError, match="changed after creation"):
        store.save_observation_protocol_review_event(conflict)

    orphan = _protocol_event("protocol:" + "9" * 32)
    with pytest.raises(ReviewStoreError, match="not found"):
        store.save_observation_protocol_review_event(orphan)

    assert not hasattr(store, "update_observation_protocol")
    assert not hasattr(store, "delete_observation_protocol")
    assert not hasattr(store, "update_observation_protocol_review_event")
    assert not hasattr(store, "delete_observation_protocol_review_event")
