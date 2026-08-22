from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator

from src.investment_review.artifact_io import canonical_json_bytes
from src.investment_review.behavior_hypothesis_candidates import (
    build_behavior_hypothesis_candidate,
    build_behavior_hypothesis_review_event,
)
from src.investment_review.behavior_observation_protocols import (
    PROTOCOL_PROJECTION_SCHEMA_VERSION,
    PROTOCOL_REVIEW_EVENT_SCHEMA_VERSION,
    PROTOCOL_SCHEMA_VERSION,
    PROTOCOL_STATE_SEMANTICS,
    ProtocolProjectedStatus,
    ProtocolReviewEventType,
    build_observation_protocol,
    build_observation_protocol_review_event,
    validate_observation_protocol,
    validate_observation_protocol_review_event,
)


ROOT = Path(__file__).resolve().parents[1]


def _hash(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _source() -> dict[str, object]:
    material: dict[str, object] = {
        "schema_version": "p2h.synthetic_source.v1",
        "artifact_type": "synthetic_evidence_set",
        "evaluations": [
            {"evaluation_id": "evaluation:" + "1" * 32, "status": "observed"}
        ],
    }
    return {**material, "content_id": _hash(material)}


def _candidate(source: dict[str, object]) -> dict[str, object]:
    return build_behavior_hypothesis_candidate(
        {
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
            "alternative_explanations": ["Opportunity conditions may have changed."],
            "applicability_conditions": ["Only the frozen synthetic cohort is covered."],
            "disconfirming_observations": [
                "The association is absent in comparable synthetic episodes."
            ],
            "observation_plan": {
                "question": "Does the observed association persist?",
                "required_facts": ["reviewed decision intent", "episode context"],
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
            "rationale": f"The candidate records the {event_type} review state.",
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


def _draft() -> dict[str, object]:
    return {
        "created_at": "2026-07-20T15:00:00Z",
        "effective_at": "2026-07-20T15:00:00Z",
        "knowledge_at": "2026-07-20T15:00:00Z",
        "accepted_projection_as_of": "2026-07-20T14:00:00Z",
        "accepted_projection_knowledge_cutoff": "2026-07-20T14:00:00Z",
        "question": "Does the observed association persist in comparable synthetic episodes?",
        "required_fact_specs": [
            {
                "fact_key": "decision_intent",
                "description": "The decision intent known at the observation checkpoint.",
                "acceptable_source_types": ["decision_record", "review_note"],
            },
            {
                "fact_key": "episode_context",
                "description": "The bounded context for each comparable synthetic episode.",
                "acceptable_source_types": ["episode_fact"],
            },
        ],
        "observation_window": {
            "starts_at": "2026-07-21T00:00:00Z",
            "ends_at": "2026-08-20T00:00:00Z",
            "review_checkpoints": [
                "2026-07-31T00:00:00Z",
                "2026-08-10T00:00:00Z",
            ],
        },
        "applicability_conditions": ["Only the frozen synthetic cohort is covered."],
        "disconfirming_conditions": [
            "The association is absent in comparable synthetic episodes."
        ],
        "stop_conditions": ["Required source provenance becomes unavailable."],
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
            "submitter_kind": "agent_assisted",
            "human_confirmed": True,
            "source_locator": "synthetic/protocol_draft.json",
            "tool_version": "p2h.observation_protocol.builder.v1",
        },
    }


def _protocol() -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    source = _source()
    candidate = _candidate(source)
    events = [
        _stage1_event(candidate["candidate_id"], "submitted", 13),
        _stage1_event(candidate["candidate_id"], "accepted_for_observation", 14),
    ]
    protocol = build_observation_protocol(
        _draft(),
        candidate=candidate,
        review_events=events,
        candidate_source_artifacts=[source],
    )
    return protocol, source, events


def test_three_closed_schemas_and_public_versions_are_frozen() -> None:
    paths = [
        ROOT / "docs/contracts/P2H_STAGE2_OBSERVATION_PROTOCOL.schema.json",
        ROOT / "docs/contracts/P2H_STAGE2_OBSERVATION_PROTOCOL_REVIEW_EVENT.schema.json",
        ROOT / "docs/contracts/P2H_STAGE2_OBSERVATION_PROTOCOL_PROJECTION.schema.json",
    ]
    for path in paths:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        assert schema["additionalProperties"] is False

    assert PROTOCOL_SCHEMA_VERSION == "p2h.observation_protocol.v1"
    assert PROTOCOL_REVIEW_EVENT_SCHEMA_VERSION.endswith("review_event.v1")
    assert PROTOCOL_PROJECTION_SCHEMA_VERSION.endswith("projection.v1")
    assert {item.value for item in ProtocolProjectedStatus} == {
        "draft",
        "submitted",
        "approved_for_observation",
        "active",
        "paused",
        "completed",
        "abandoned",
        "superseded",
    }
    assert "not prove or disprove" in PROTOCOL_STATE_SEMANTICS


def test_protocol_build_binds_exact_stage1_inputs_and_is_canonical() -> None:
    protocol, source, events = _protocol()

    assert protocol["schema_version"] == PROTOCOL_SCHEMA_VERSION
    assert protocol["protocol_id"].startswith("protocol:")
    assert protocol["canonical_hash"].startswith("sha256:")
    binding = protocol["candidate_binding"]
    assert binding["source_replay_status"] == "verified"
    assert binding["candidate_source_refs"][0]["content_id"] == source["content_id"]
    assert [item["review_event_id"] for item in binding["review_event_refs"]] == [
        event["review_event_id"] for event in events
    ]
    assert binding["accepted_projection"]["status"] == "accepted_for_observation"
    assert validate_observation_protocol(protocol)["validation_status"] == "accepted"


def test_protocol_build_is_deterministic_under_set_and_input_permutation() -> None:
    source = _source()
    candidate = _candidate(source)
    events = [
        _stage1_event(candidate["candidate_id"], "submitted", 13),
        _stage1_event(candidate["candidate_id"], "accepted_for_observation", 14),
    ]
    draft = _draft()
    shuffled = deepcopy(draft)
    shuffled["required_fact_specs"].reverse()
    shuffled["required_fact_specs"][1]["acceptable_source_types"].reverse()
    shuffled["observation_window"]["review_checkpoints"].reverse()
    shuffled["privacy_scope"]["prohibited_data_kinds"].reverse()

    first = build_observation_protocol(
        draft,
        candidate=candidate,
        review_events=events,
        candidate_source_artifacts=[source],
    )
    second = build_observation_protocol(
        shuffled,
        candidate=candidate,
        review_events=list(reversed(events)),
        candidate_source_artifacts=[source],
    )

    assert canonical_json_bytes(first) == canonical_json_bytes(second)


def test_human_protocol_event_has_content_identity_and_closed_type() -> None:
    protocol, _, _ = _protocol()
    event = build_observation_protocol_review_event(
        {
            "protocol_id": protocol["protocol_id"],
            "event_type": "submitted",
            "reviewed_at": "2026-07-20T16:00:00Z",
            "effective_at": "2026-07-20T16:00:00Z",
            "knowledge_at": "2026-07-20T16:00:00Z",
            "reviewer_ref": "synthetic-human-reviewer",
            "rationale": "The explicit protocol draft is submitted for human review.",
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

    assert event["protocol_review_event_id"].startswith("protocol_review_event:")
    assert validate_observation_protocol_review_event(event)["validation_status"] == "accepted"
    assert ProtocolReviewEventType(event["event_type"]) is ProtocolReviewEventType.SUBMITTED
