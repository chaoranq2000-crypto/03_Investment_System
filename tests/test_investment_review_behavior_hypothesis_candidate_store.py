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


def _event(candidate_id: str, event_type: str = "submitted") -> dict[str, object]:
    return build_behavior_hypothesis_review_event(
        {
            "candidate_id": candidate_id,
            "event_type": event_type,
            "reviewed_at": "2026-07-20T13:00:00Z",
            "effective_at": "2026-07-20T13:00:00Z",
            "knowledge_at": "2026-07-20T13:00:00Z",
            "reviewer_ref": "synthetic-human-reviewer",
            "rationale": "The candidate is recorded for bounded human review.",
            "evidence_cutoff": "2026-07-20T12:00:00Z",
            "supersedes_event_id": None,
            "supersedes_candidate_id": None,
            "provenance": {
                "submitter_kind": "human",
                "source_locator": "synthetic/review_event.json",
                "tool_version": "p2h.behavior_hypothesis_review_event.builder.v1",
            },
        }
    )


def test_p2h_tables_initialize_idempotently_and_upgrade_existing_v2(tmp_path: Path) -> None:
    database = tmp_path / "review.sqlite3"
    store = ReviewStore(database)
    assert store.initialize()["schema_version"] == 2
    assert store.initialize()["schema_version"] == 2
    status = store.status()
    assert status["p2h_stage1_schema_version"] == 1
    assert status["counts"]["behavior_hypothesis_candidates"] == 0
    assert status["counts"]["behavior_hypothesis_review_events"] == 0

    legacy = tmp_path / "existing-v2.sqlite3"
    conn = sqlite3.connect(legacy)
    conn.execute(f"PRAGMA application_id = {APPLICATION_ID}")
    conn.execute("PRAGMA user_version = 2")
    conn.execute("CREATE TABLE schema_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("INSERT INTO schema_meta VALUES ('schema_version', '2')")
    conn.execute("CREATE TABLE legacy_marker(value TEXT NOT NULL)")
    conn.execute("INSERT INTO legacy_marker VALUES ('preserved')")
    conn.commit()
    conn.close()

    upgraded = ReviewStore(legacy)
    upgraded.initialize()
    conn = sqlite3.connect(legacy)
    marker = conn.execute("SELECT value FROM legacy_marker").fetchone()[0]
    p2h_version = conn.execute(
        "SELECT value FROM schema_meta WHERE key='p2h_stage1_schema_version'"
    ).fetchone()[0]
    conn.close()
    assert marker == "preserved"
    assert p2h_version == "1"


def test_candidate_ingest_is_source_verified_create_only_and_queryable(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "review.sqlite3")
    store.initialize()
    source = _source()
    candidate = _candidate(source)

    first = store.save_behavior_hypothesis_candidate(
        candidate, source_artifacts=[source]
    )
    second = store.save_behavior_hypothesis_candidate(
        candidate, source_artifacts=[source]
    )

    assert first["status"] == "INSERTED"
    assert second["status"] == "SKIPPED"
    assert store.get_behavior_hypothesis_candidate(candidate["candidate_id"]) == candidate
    assert store.replay_behavior_hypothesis_candidate(
        candidate["candidate_id"], source_artifacts=[source]
    )["source_verification"] == {"status": "verified"}
    assert len(
        store.list_behavior_hypothesis_candidates(
            candidate_id=candidate["candidate_id"],
            status="candidate",
            pattern_family="outcome_conditioning",
            scope_kind="cohort",
            scope_ref="synthetic-cohort-001",
            as_of="2026-07-20T11:00:00Z",
            knowledge_cutoff="2026-07-20T12:00:00Z",
            created_from="2026-07-20T12:00:00Z",
            created_to="2026-07-20T12:00:00Z",
        )
    ) == 1
    assert not store.list_behavior_hypothesis_candidates(
        as_of="2026-07-20T10:59:59Z"
    )
    assert not store.list_behavior_hypothesis_candidates(
        knowledge_cutoff="2026-07-20T11:59:59Z"
    )


def test_candidate_conflict_and_source_drift_fail_closed(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "review.sqlite3")
    store.initialize()
    source = _source()
    candidate = _candidate(source)
    store.save_behavior_hypothesis_candidate(candidate, source_artifacts=[source])

    conflicting = deepcopy(candidate)
    conflicting["hypothesis_statement"] = (
        "The observed association may not persist in comparable synthetic episodes."
    )
    with pytest.raises(DataConflictError, match="changed after creation"):
        store.save_behavior_hypothesis_candidate(
            conflicting, source_artifacts=[source]
        )

    other_source = deepcopy(source)
    other_source["evaluations"][0]["status"] = "tampered"
    other_store = ReviewStore(tmp_path / "other-store.sqlite3")
    other_store.initialize()
    with pytest.raises(ReviewStoreError, match="failed source replay"):
        other_store.save_behavior_hypothesis_candidate(
            candidate, source_artifacts=[other_source]
        )


def test_review_event_ingest_is_immutable_and_visible_by_dual_time(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "review.sqlite3")
    store.initialize()
    source = _source()
    candidate = _candidate(source)
    store.save_behavior_hypothesis_candidate(candidate, source_artifacts=[source])
    event = _event(candidate["candidate_id"])

    assert store.save_behavior_hypothesis_review_event(event)["status"] == "INSERTED"
    assert store.save_behavior_hypothesis_review_event(event)["status"] == "SKIPPED"
    assert len(
        store.list_behavior_hypothesis_review_events(
            candidate_id=candidate["candidate_id"],
            event_type="submitted",
            as_of="2026-07-20T13:00:00Z",
            knowledge_cutoff="2026-07-20T13:00:00Z",
            reviewed_from="2026-07-20T13:00:00Z",
            reviewed_to="2026-07-20T13:00:00Z",
        )
    ) == 1
    assert not store.list_behavior_hypothesis_review_events(
        as_of="2026-07-20T12:59:59Z"
    )
    assert store.list_behavior_hypothesis_candidates(
        status="submitted", as_of="2026-07-20T13:00:00Z"
    )[0]["projected_status"] == "submitted"
    assert store.list_behavior_hypothesis_candidates(
        status="candidate", as_of="2026-07-20T12:59:59Z"
    )[0]["projected_status"] == "candidate"

    conflicting = deepcopy(event)
    conflicting["rationale"] = "Changed after immutable creation."
    with pytest.raises(DataConflictError, match="changed after creation"):
        store.save_behavior_hypothesis_review_event(conflicting)


def test_orphan_review_events_and_mutation_api_are_rejected(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "review.sqlite3")
    store.initialize()
    orphan = _event("candidate:" + "9" * 32)

    with pytest.raises(ReviewStoreError, match="candidate not found"):
        store.save_behavior_hypothesis_review_event(orphan)

    assert not hasattr(store, "update_behavior_hypothesis_candidate")
    assert not hasattr(store, "delete_behavior_hypothesis_candidate")
    assert not hasattr(store, "update_behavior_hypothesis_review_event")
    assert not hasattr(store, "delete_behavior_hypothesis_review_event")
