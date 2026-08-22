from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

import pytest

from src.investment_review.knowledge_provenance import (
    METHOD_VERSION,
    REPLAY_SCHEMA_VERSION,
    SCHEMA_VERSION,
    VALIDATION_SCHEMA_VERSION,
    KnowledgeProvenanceError,
    build_knowledge_provenance,
    canonical_knowledge_provenance_bytes,
    project_perspective_event_inputs,
    replay_validate_knowledge_provenance,
    validate_knowledge_provenance,
)


AS_OF = "2026-07-17T10:00:00Z"
CUTOFF = "2026-07-20T00:00:00Z"
PAYLOAD_A = "a" * 64
PAYLOAD_B = "b" * 64


def event(
    event_id: str = "evt_a",
    *,
    event_type: str = "buy",
    side: str = "BUY",
    occurred_at: str = AS_OF,
    source_created_at: str = "2026-07-18T00:00:00Z",
    ingested_at: str = "2026-07-25T00:00:00Z",
    payload_sha256: str = PAYLOAD_A,
    fact_domain: str | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "event_id": event_id,
        "source_id": "src_portfolio",
        "source_record_id": f"acct::{event_id}",
        "event_type": event_type,
        "occurred_at": occurred_at,
        # This legacy byte is intentionally preserved and is not used as the
        # sole user/system knowledge authority.
        "known_at": occurred_at,
        "account": "acct",
        "market": "SH",
        "symbol": "588200.SH",
        "side": side,
        "quantity": "100",
        "price": "3.9",
        "payload_sha256": payload_sha256,
        "first_ingest_run_id": f"run_{event_id}",
        "ingested_at": ingested_at,
        "raw_payload": {
            "known_at_fallback": True,
            "source_row": {
                "account_id": "acct",
                "external_id": event_id,
                "dedupe_key": event_id,
                "created_at": source_created_at,
            },
        },
        "decision_refs": [],
    }
    if fact_domain is not None:
        value["fact_domain"] = fact_domain
    return value


def evidence(
    source_event: dict[str, Any],
    *,
    observed_at: str = "2026-07-25T00:00:01Z",
) -> dict[str, Any]:
    event_id = source_event["event_id"]
    return {
        "event_id": event_id,
        "source_id": source_event["source_id"],
        "source_record_id": source_event["source_record_id"],
        "event_type": source_event["event_type"],
        "occurred_at": source_event["occurred_at"],
        "known_at": source_event["known_at"],
        "account": source_event["account"],
        "market": source_event["market"],
        "symbol": source_event["symbol"],
        "payload_sha256": source_event["payload_sha256"],
        "raw_payload": deepcopy(source_event["raw_payload"]),
        "ingested_at": source_event["ingested_at"],
        "first_ingest": {
            "run_id": source_event["first_ingest_run_id"],
            "outcome": "INSERTED",
            "observed_at": observed_at,
            "observation_payload_sha256": source_event["payload_sha256"],
            "source_id": source_event["source_id"],
            "source_fingerprint": "fingerprint-v1",
            "started_at": source_event["ingested_at"],
            "finished_at": source_event["ingested_at"],
            "status": "COMPLETED",
            "manifest": {"adapter": "investment_review_sync_service"},
        },
    }


def build(
    source_event: dict[str, Any],
    *,
    perspective: str,
    observed_at: str = "2026-07-25T00:00:01Z",
    as_of: str = AS_OF,
    cutoff: str = CUTOFF,
) -> dict[str, Any]:
    return build_knowledge_provenance(
        [source_event],
        perspective=perspective,
        as_of=as_of,
        knowledge_cutoff=cutoff,
        observation_evidence=[
            evidence(source_event, observed_at=observed_at)
        ],
    )


def projected_event(artifact: dict[str, Any]) -> dict[str, Any]:
    assert len(artifact["events"]) == 1
    return artifact["events"][0]


def rehash(artifact: dict[str, Any]) -> None:
    material = deepcopy(artifact)
    material["content_id"] = ""
    artifact["content_id"] = "sha256:" + hashlib.sha256(
        json.dumps(
            material,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def test_late_import_is_user_visible_but_system_withheld() -> None:
    source_event = event()

    user = build(source_event, perspective="user")
    system = build(source_event, perspective="system")

    assert user["schema_version"] == SCHEMA_VERSION
    assert user["method_version"] == METHOD_VERSION
    assert validate_knowledge_provenance(user) == {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "validation_status": "accepted",
        "findings": [],
    }
    assert user["visible_event_ids"] == ["evt_a"]
    assert system["visible_event_ids"] == []
    assert system["withheld_event_ids"] == ["evt_a"]

    user_event = projected_event(user)
    system_event = projected_event(system)
    assert user_event["fact_kind"] == "owner_action"
    assert user_event["owner_action_default_applied"] is True
    assert user_event["time_provenance"]["user_known_at"] == {
        "value": "2026-07-17T10:00:00+00:00",
        "basis": "owner_action_default",
        "source_refs": user_event["source_refs"],
    }
    # Raw source created_at is recorded evidence only.
    assert user_event["time_provenance"]["recorded_at"]["basis"] == (
        "recorded_later"
    )
    assert user_event["time_provenance"]["recorded_at"]["value"] == (
        "2026-07-18T00:00:00+00:00"
    )
    assert system_event["time_provenance"]["system_observed_at"] == {
        "value": None,
        "basis": "not_observed",
        "source_refs": [],
    }
    assert system_event["visibility"]["reason"] == (
        "system_observation_withheld_by_cutoff"
    )
    assert system_event["withheld_evidence"][0]["status"] == (
        "withheld_by_cutoff"
    )

    projected = project_perspective_event_inputs(user, [source_event])
    assert projected == [source_event]
    assert projected[0]["event_id"] == source_event["event_id"]
    assert projected[0]["known_at"] == source_event["known_at"]
    assert project_perspective_event_inputs(system, [source_event]) == []


def test_live_first_ingest_makes_user_and_system_views_converge() -> None:
    source_event = event(
        source_created_at=AS_OF,
        ingested_at=AS_OF,
    )

    user = build(
        source_event,
        perspective="user",
        observed_at=AS_OF,
    )
    system = build(
        source_event,
        perspective="system",
        observed_at=AS_OF,
    )

    assert user["visible_event_ids"] == system["visible_event_ids"] == [
        "evt_a"
    ]
    system_time = projected_event(system)["time_provenance"][
        "system_observed_at"
    ]
    assert system_time["value"] == "2026-07-17T10:00:00+00:00"
    assert system_time["basis"] == "ingest_observation"
    assert system_time["source_refs"]
    assert replay_validate_knowledge_provenance(
        user,
        event_inputs=[source_event],
        observation_evidence=[
            evidence(source_event, observed_at=AS_OF)
        ],
    )["source_verification"]["status"] == "verified"
    assert replay_validate_knowledge_provenance(
        system,
        event_inputs=[source_event],
        observation_evidence=[
            evidence(source_event, observed_at=AS_OF)
        ],
    ) == {
        "schema_version": REPLAY_SCHEMA_VERSION,
        "validation_status": "accepted",
        "source_verification": {
            "status": "verified",
            "content_id": system["content_id"],
        },
        "findings": [],
    }


def test_system_observation_after_as_of_but_before_knowledge_cutoff_is_visible() -> None:
    source_event = event(
        source_created_at="2026-07-18T00:00:00Z",
        ingested_at="2026-07-18T00:00:01Z",
    )

    artifact = build(
        source_event,
        perspective="system",
        observed_at="2026-07-18T00:00:02Z",
    )

    assert artifact["visible_event_ids"] == ["evt_a"]
    item = projected_event(artifact)
    assert item["time_provenance"]["system_observed_at"]["value"] == (
        "2026-07-18T00:00:02+00:00"
    )
    assert item["visibility"]["status"] == "visible"


@pytest.mark.parametrize(
    ("event_type", "side"),
    [("dividend", "OTHER"), ("cash_fee", "OTHER"), ("opening", "OTHER")],
)
def test_non_owner_account_facts_use_source_occurred_not_owner_default(
    event_type: str,
    side: str,
) -> None:
    source_event = event(event_type=event_type, side=side)

    artifact = build(source_event, perspective="user")
    item = projected_event(artifact)

    assert item["fact_domain"] == "account"
    assert item["fact_kind"] == "account_fact"
    assert item["owner_action_default_applied"] is False
    assert item["time_provenance"]["user_known_at"]["basis"] == (
        "source_occurred_at"
    )
    assert artifact["visible_event_ids"] == ["evt_a"]


def test_market_fact_never_receives_owner_action_default() -> None:
    source_event = event(
        event_type="price",
        side="OTHER",
        fact_domain="market",
    )

    artifact = build(source_event, perspective="user")
    item = projected_event(artifact)

    assert item["fact_domain"] == "market"
    assert item["fact_kind"] == "market_fact"
    assert item["owner_action_default_applied"] is False
    assert item["time_provenance"]["user_known_at"] == {
        "value": None,
        "basis": "not_observed",
        "source_refs": [],
    }
    assert artifact["visible_event_ids"] == []


def test_input_and_evidence_permutation_are_byte_deterministic() -> None:
    first = event("evt_a", payload_sha256=PAYLOAD_A)
    second = event(
        "evt_b",
        occurred_at="2026-07-17T09:59:00Z",
        payload_sha256=PAYLOAD_B,
    )
    inputs = [first, second]
    observations = [evidence(first), evidence(second)]

    artifact_a = build_knowledge_provenance(
        inputs,
        perspective="user",
        as_of=AS_OF,
        knowledge_cutoff=CUTOFF,
        observation_evidence=observations,
    )
    artifact_b = build_knowledge_provenance(
        list(reversed(inputs)),
        perspective="user",
        as_of=AS_OF,
        knowledge_cutoff=CUTOFF,
        observation_evidence=list(reversed(observations)),
    )

    assert artifact_a["content_id"] == artifact_b["content_id"]
    assert canonical_knowledge_provenance_bytes(
        artifact_a
    ) == canonical_knowledge_provenance_bytes(artifact_b)
    assert artifact_a["visible_event_ids"] == ["evt_a", "evt_b"]
    assert project_perspective_event_inputs(
        artifact_a, list(reversed(inputs))
    ) == [first, second]


def test_tamper_unknown_fields_float_basis_and_replay_drift_are_blocked() -> None:
    source_event = event(
        source_created_at=AS_OF,
        ingested_at=AS_OF,
    )
    source_evidence = evidence(source_event, observed_at=AS_OF)
    artifact = build_knowledge_provenance(
        [source_event],
        perspective="system",
        as_of=AS_OF,
        knowledge_cutoff=CUTOFF,
        observation_evidence=[source_evidence],
    )

    unknown = deepcopy(artifact)
    unknown["motive"] = "forbidden"
    assert (
        validate_knowledge_provenance(unknown)["validation_status"]
        == "blocked"
    )

    float_value = deepcopy(artifact)
    float_value["governance"]["confidence"] = 0.9
    validation = validate_knowledge_provenance(float_value)
    assert validation["validation_status"] == "blocked"
    assert {
        item["code"] for item in validation["findings"]
    }.issuperset({"NON_CANONICAL_VALUE", "INVALID_KNOWLEDGE_GOVERNANCE"})

    wrong_basis = deepcopy(artifact)
    wrong_basis["events"][0]["time_provenance"][
        "system_observed_at"
    ]["basis"] = "owner_action_default"
    assert (
        validate_knowledge_provenance(wrong_basis)["validation_status"]
        == "blocked"
    )

    drifted_evidence = deepcopy(source_evidence)
    drifted_evidence["first_ingest"]["observed_at"] = (
        "2026-07-17T10:00:01Z"
    )
    replay = replay_validate_knowledge_provenance(
        artifact,
        event_inputs=[source_event],
        observation_evidence=[drifted_evidence],
    )
    assert replay["validation_status"] == "blocked"
    assert replay["source_verification"]["status"] == "blocked"


def test_malformed_time_validator_fails_closed_without_raising() -> None:
    source_event = event(
        source_created_at=AS_OF,
        ingested_at=AS_OF,
    )
    artifact = build(
        source_event,
        perspective="system",
        observed_at=AS_OF,
    )
    malformed = deepcopy(artifact)
    malformed["events"][0]["time_provenance"]["effective_at"]["value"] = (
        "not-a-time"
    )

    validation = validate_knowledge_provenance(malformed)

    assert validation["validation_status"] == "blocked"
    assert "INVALID_TIME_PROJECTION_VALUE" in {
        item["code"] for item in validation["findings"]
    }


def test_binary_float_in_source_event_is_rejected_before_projection() -> None:
    source_event = event()
    source_event["price"] = 3.9

    with pytest.raises(KnowledgeProvenanceError, match="binary float"):
        build_knowledge_provenance(
            [source_event],
            perspective="user",
            as_of=AS_OF,
            knowledge_cutoff=CUTOFF,
            observation_evidence=[evidence(source_event)],
        )


def test_invalid_first_ingest_binding_and_conflicting_duplicates_fail_closed() -> None:
    source_event = event()
    bad_evidence = evidence(source_event)
    bad_evidence["first_ingest"]["outcome"] = "SKIPPED"

    with pytest.raises(
        KnowledgeProvenanceError,
        match="first-ingest observation binding is invalid",
    ):
        build_knowledge_provenance(
            [source_event],
            perspective="system",
            as_of=AS_OF,
            knowledge_cutoff=CUTOFF,
            observation_evidence=[bad_evidence],
        )

    conflict = deepcopy(source_event)
    conflict["known_at"] = "2026-07-17T10:00:01Z"
    with pytest.raises(
        KnowledgeProvenanceError, match="conflicting duplicate event_id"
    ):
        build_knowledge_provenance(
            [source_event, conflict],
            perspective="user",
            as_of=AS_OF,
            knowledge_cutoff=CUTOFF,
            observation_evidence=[evidence(source_event)],
        )


@pytest.mark.parametrize(
    ("as_of", "cutoff", "perspective", "message"),
    [
        (
            "2026-07-17 10:00:00",
            CUTOFF,
            "user",
            "explicit timezone",
        ),
        (
            "2026-07-21T00:00:00Z",
            CUTOFF,
            "user",
            "as_of cannot be later",
        ),
        (AS_OF, CUTOFF, "omniscient", "unsupported knowledge perspective"),
    ],
)
def test_invalid_root_time_or_perspective_is_rejected(
    as_of: str,
    cutoff: str,
    perspective: str,
    message: str,
) -> None:
    source_event = event()
    with pytest.raises(KnowledgeProvenanceError, match=message):
        build_knowledge_provenance(
            [source_event],
            perspective=perspective,
            as_of=as_of,
            knowledge_cutoff=cutoff,
            observation_evidence=[evidence(source_event)],
        )


def test_future_recorded_evidence_is_withheld_without_relabeling_user_knowledge() -> None:
    source_event = event(
        source_created_at="2026-07-21T00:00:00Z",
        ingested_at="2026-07-25T00:00:00Z",
    )

    artifact = build_knowledge_provenance(
        [source_event],
        perspective="user",
        as_of=AS_OF,
        knowledge_cutoff=CUTOFF,
        observation_evidence=[evidence(source_event)],
    )

    item = projected_event(artifact)
    assert item["time_provenance"]["user_known_at"] == {
        "value": "2026-07-17T10:00:00+00:00",
        "basis": "owner_action_default",
        "source_refs": item["source_refs"],
    }
    assert item["time_provenance"]["recorded_at"] == {
        "value": None,
        "basis": "unknown",
        "source_refs": [],
    }
    assert item["gaps"][0]["code"] == (
        "RECORDED_TIME_WITHHELD_BY_CUTOFF"
    )
    assert {
        evidence_item["field"]
        for evidence_item in item["withheld_evidence"]
    } == {"system_observed_at", "recorded_at"}
    assert item["visibility"]["status"] == "withheld"
    assert artifact["visible_event_ids"] == []
    assert artifact["withheld_event_ids"] == ["evt_a"]
    assert artifact["visibility_ledger"][0]["reason"] == (
        "recorded_after_knowledge_cutoff"
    )
    assert validate_knowledge_provenance(artifact)["validation_status"] == (
        "accepted"
    )


def test_future_effective_event_is_withheld_even_when_observation_is_cutoff_safe() -> None:
    source_event = event(
        occurred_at="2026-07-21T00:00:00Z",
        source_created_at="2026-07-21T00:00:00Z",
        ingested_at="2026-07-21T00:00:01Z",
    )
    cutoff = "2026-07-22T00:00:00Z"

    artifact = build_knowledge_provenance(
        [source_event],
        perspective="system",
        as_of=AS_OF,
        knowledge_cutoff=cutoff,
        observation_evidence=[
            evidence(
                source_event,
                observed_at="2026-07-21T00:00:02Z",
            )
        ],
    )

    assert artifact["events"] == []
    assert artifact["visible_event_ids"] == []
    assert artifact["visibility_ledger"][0]["reason"] == (
        "effective_after_as_of"
    )


def test_missing_recorded_time_is_retained_with_null_basis_and_gap() -> None:
    source_event = event(source_created_at="", ingested_at="")

    artifact = build(
        source_event,
        perspective="user",
    )

    item = projected_event(artifact)
    assert item["time_provenance"]["recorded_at"] == {
        "value": None,
        "basis": "unknown",
        "source_refs": [],
    }
    assert item["gaps"][0]["code"] == "RECORDED_TIME_NOT_PROVEN"
    assert item["visibility"]["reason"] == "recorded_time_not_proven"
    assert artifact["withheld_event_ids"] == ["evt_a"]
    assert validate_knowledge_provenance(artifact)["validation_status"] == (
        "accepted"
    )


def test_naive_source_created_time_falls_back_to_immutable_ingest_time() -> None:
    source_event = event(
        source_created_at="2026-07-18 00:00:00",
        ingested_at="2026-07-18T00:00:01Z",
    )

    artifact = build(source_event, perspective="user")
    recorded = projected_event(artifact)["time_provenance"]["recorded_at"]

    assert recorded["basis"] == "ingest_observation"
    assert recorded["value"] == "2026-07-18T00:00:01+00:00"
    assert validate_knowledge_provenance(artifact)["validation_status"] == (
        "accepted"
    )


@pytest.mark.parametrize("field", ["quantity", "decision_refs"])
def test_projection_rejects_full_event_input_drift(field: str) -> None:
    source_event = event()
    artifact = build(source_event, perspective="user")
    drifted = deepcopy(source_event)
    drifted[field] = "999" if field == "quantity" else ["decision:forged"]

    with pytest.raises(
        KnowledgeProvenanceError,
        match="event inputs do not match",
    ):
        project_perspective_event_inputs(artifact, [drifted])
    assert replay_validate_knowledge_provenance(
        artifact,
        event_inputs=[drifted],
        observation_evidence=[evidence(drifted)],
    )["validation_status"] == "blocked"


def test_same_identity_with_different_full_input_is_rejected() -> None:
    source_event = event()
    conflicting = deepcopy(source_event)
    conflicting["quantity"] = "101"

    with pytest.raises(
        KnowledgeProvenanceError,
        match="conflicting duplicate event_id",
    ):
        build_knowledge_provenance(
            [source_event, conflicting],
            perspective="user",
            as_of=AS_OF,
            knowledge_cutoff=CUTOFF,
            observation_evidence=[evidence(source_event)],
        )


def test_first_ingest_must_bind_event_identity_and_follow_effective_time() -> None:
    source_event = event()
    missing_identity = deepcopy(source_event)
    missing_identity["first_ingest_run_id"] = None
    with pytest.raises(
        KnowledgeProvenanceError,
        match="first-ingest observation binding is invalid",
    ):
        build_knowledge_provenance(
            [missing_identity],
            perspective="system",
            as_of=AS_OF,
            knowledge_cutoff=CUTOFF,
            observation_evidence=[evidence(source_event)],
        )

    with pytest.raises(
        KnowledgeProvenanceError,
        match="precedes effective time",
    ):
        build_knowledge_provenance(
            [source_event],
            perspective="system",
            as_of=AS_OF,
            knowledge_cutoff=CUTOFF,
            observation_evidence=[
                evidence(
                    source_event,
                    observed_at="2026-07-17T09:59:59Z",
                )
            ],
        )


def test_validator_blocks_lone_surrogate_and_closed_shape_tampering() -> None:
    source_event = event(
        source_created_at=AS_OF,
        ingested_at=AS_OF,
    )
    artifact = build(
        source_event,
        perspective="system",
        observed_at=AS_OF,
    )

    surrogate = deepcopy(artifact)
    surrogate["events"][0]["event_id"] = "evt_\ud800"
    assert validate_knowledge_provenance(surrogate)["validation_status"] == (
        "blocked"
    )

    malformed = deepcopy(artifact)
    malformed["events"][0]["time_provenance"]["recorded_at"] = "not-an-object"
    assert validate_knowledge_provenance(malformed)["validation_status"] == (
        "blocked"
    )


def test_rehashed_visibility_and_event_membership_tampering_is_blocked() -> None:
    source_event = event(
        source_created_at=AS_OF,
        ingested_at=AS_OF,
    )
    artifact = build(
        source_event,
        perspective="system",
        observed_at=AS_OF,
    )

    reason_drift = deepcopy(artifact)
    reason_drift["events"][0]["visibility"]["reason"] = (
        "system_observation_not_proven"
    )
    reason_drift["visibility_ledger"][0]["reason"] = (
        "system_observation_not_proven"
    )
    rehash(reason_drift)
    assert validate_knowledge_provenance(reason_drift)[
        "validation_status"
    ] == "blocked"

    removed = deepcopy(artifact)
    removed["events"] = []
    rehash(removed)
    assert validate_knowledge_provenance(removed)["validation_status"] == (
        "blocked"
    )


def test_rehashed_source_binding_and_coordinated_removal_are_blocked() -> None:
    source_event = event()
    artifact = build(source_event, perspective="user")

    arbitrary_full_id = deepcopy(artifact)
    arbitrary_full_id["source_binding"]["full_event_input_content_id"] = (
        "sha256:" + "f" * 64
    )
    rehash(arbitrary_full_id)
    assert validate_knowledge_provenance(arbitrary_full_id)[
        "validation_status"
    ] == "blocked"

    forged_refs = deepcopy(artifact)
    forged_refs["source_binding"]["event_input_manifest"][0][
        "source_refs"
    ] = ["forged"]
    forged_refs["events"][0]["source_refs"] = ["forged"]
    for field in ("effective_at", "user_known_at"):
        forged_refs["events"][0]["time_provenance"][field][
            "source_refs"
        ] = ["forged"]
    forged_refs["events"][0]["visibility"]["source_refs"] = ["forged"]
    forged_refs["visibility_ledger"][0]["source_refs"] = ["forged"]
    rehash(forged_refs)
    assert validate_knowledge_provenance(forged_refs)[
        "validation_status"
    ] == "blocked"

    removed = deepcopy(artifact)
    removed["events"] = []
    removed["visibility_ledger"] = []
    removed["visible_event_ids"] = []
    removed["withheld_event_ids"] = []
    removed["source_binding"]["event_input_count"] = 0
    removed["source_binding"]["event_input_manifest"] = []
    rehash(removed)
    assert validate_knowledge_provenance(removed)["validation_status"] == (
        "blocked"
    )


def test_rehashed_unhashable_json_fields_fail_closed_without_raising() -> None:
    source_event = event()
    artifact = build(source_event, perspective="system")
    mutations = [
        lambda value: value.__setitem__("perspective", []),
        lambda value: value["events"][0].__setitem__("fact_kind", []),
        lambda value: value["events"][0]["time_provenance"][
            "user_known_at"
        ].__setitem__("basis", []),
        lambda value: value["events"][0]["withheld_evidence"][
            0
        ].__setitem__("field", []),
        lambda value: value["events"][0]["visibility"].__setitem__(
            "reason", []
        ),
        lambda value: value["visibility_ledger"][0].__setitem__(
            "reason", []
        ),
    ]
    for mutate in mutations:
        malformed = deepcopy(artifact)
        mutate(malformed)
        rehash(malformed)
        assert validate_knowledge_provenance(malformed)[
            "validation_status"
        ] == "blocked"

    missing_recorded = build(
        event(source_created_at="", ingested_at=""),
        perspective="user",
    )
    missing_recorded["events"][0]["gaps"][0]["code"] = []
    rehash(missing_recorded)
    assert validate_knowledge_provenance(missing_recorded)[
        "validation_status"
    ] == "blocked"


def test_unknown_buy_like_event_never_acquires_owner_action_default() -> None:
    source_event = event(
        event_type="market_snapshot_unknown",
        side="BUY",
        fact_domain="market",
    )

    item = projected_event(build(source_event, perspective="user"))

    assert item["fact_kind"] == "market_fact"
    assert item["owner_action_default_applied"] is False
    assert item["time_provenance"]["user_known_at"]["basis"] == "not_observed"
