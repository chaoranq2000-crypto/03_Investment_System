from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

import src.investment_review.operation_review as operation_module
from src.investment_review.episodes import (
    build_episode_collection,
    validate_episode_collection,
)
from src.investment_review.operation_review import (
    METHOD_VERSION,
    SCHEMA_VERSION,
    OperationReviewError,
    build_operation_review,
    canonical_operation_review_bytes,
    query_operation_review,
    replay_validate_operation_review,
    validate_operation_review,
)


UTC = timezone.utc
BASE = datetime(2026, 7, 17, 1, 30, 0, tzinfo=UTC)
CUTOFF = datetime(2026, 7, 25, 8, 0, 0, tzinfo=UTC)


def _event(
    event_id: str,
    *,
    at: datetime = BASE,
    account: str = "acct-1",
    symbol: str = "588200.SH",
    side: str = "BUY",
    quantity: str = "100",
    event_type: str = "fill",
    sequence: int = 1,
    cash_amount: str | None = None,
    decisions: list[dict] | None = None,
    hostile_payload: bool = False,
) -> dict:
    source_row = {
        "account_id": account,
        "external_id": event_id,
        "dedupe_key": f"dedupe-{event_id}",
        "entry_id": sequence,
        "created_at": at.isoformat(),
    }
    if hostile_payload:
        source_row.update(
            {
                "motive": "<script>BUY NOW</script>",
                "thesis": "guaranteed return",
                "advice": "increase the position",
                "score": 100,
            }
        )
    return {
        "event_id": event_id,
        "source_id": "src-operation-fixture",
        "source_record_id": f"{account}::{event_id}",
        "payload_sha256": hashlib.sha256(event_id.encode("utf-8")).hexdigest(),
        "event_type": event_type,
        "occurred_at": at.isoformat(),
        "known_at": at.isoformat(),
        "account": account,
        "market": None,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "price": None,
        "gross_amount": None,
        "cash_amount": cash_amount,
        "fees": None,
        "currency": "CNY",
        "raw_payload": {"source_row": source_row},
        "decision_refs": decisions or [],
    }


def _decision(
    decision_id: str,
    event_id: str,
    *,
    known_at: datetime,
) -> dict:
    return {
        "decision_id": decision_id,
        "event_id": event_id,
        "relation": "execution",
        "symbol": "588200.SH",
        "market": None,
        "occurred_at": (known_at - timedelta(minutes=1)).isoformat(),
        "known_at": known_at.isoformat(),
        "status": "OPEN",
        "link_source": "decision_event_links",
    }


def _collection(events: list[dict]) -> dict:
    return build_episode_collection(events, cutoff_at=CUTOFF.isoformat())


def _codes(validation: dict) -> set[str]:
    return {
        str(item.get("code"))
        for item in validation.get("findings", [])
        if isinstance(item, dict)
    }


def _operation_map(artifact: dict) -> dict[str, dict]:
    operations = {
        operation["event_id"]: operation
        for review in artifact["episode_reviews"]
        for operation in review["operations"]
    }
    operations.update(
        {
            operation["event_id"]: operation
            for operation in artifact["standalone_operations"]
        }
    )
    return operations


def _closed_events() -> list[dict]:
    return [
        _event("open", quantity="40", event_type="buy", sequence=1),
        _event(
            "increase",
            at=BASE + timedelta(minutes=1),
            quantity="60",
            event_type="buy",
            sequence=2,
        ),
        _event(
            "reduce",
            at=BASE + timedelta(minutes=2),
            side="SELL",
            quantity="30",
            event_type="sell",
            sequence=3,
        ),
        _event(
            "close",
            at=BASE + timedelta(minutes=3),
            side="SELL",
            quantity="70",
            event_type="sell",
            sequence=4,
        ),
    ]


def test_closed_no_decision_classifies_quantity_path_without_motive() -> None:
    events = _closed_events()
    artifact = build_operation_review(
        _collection(events),
        event_inputs=events,
    )

    assert artifact["schema_version"] == SCHEMA_VERSION
    assert artifact["method_version"] == METHOD_VERSION
    assert validate_operation_review(artifact)["validation_status"] == "accepted"
    assert len(artifact["episode_reviews"]) == 1
    review = artifact["episode_reviews"][0]
    assert review["episode_status"] == "closed"
    assert review["operation_review_status"] == "ready"
    assert review["decision_context_status"] == "not_recorded"
    assert [
        operation["operation_type"] for operation in review["operations"]
    ] == [
        "position_open",
        "position_increase",
        "position_reduce",
        "position_close",
    ]
    assert [
        (
            operation["qty_before"],
            operation["qty_after"],
            operation["classification_status"],
        )
        for operation in review["operations"]
    ] == [
        ("0", "40", "ready"),
        ("40", "100", "ready"),
        ("100", "70", "ready"),
        ("70", "0", "ready"),
    ]
    assert all(
        operation["method_version"] == METHOD_VERSION
        and operation["source_refs"]["source_id"]
        == "src-operation-fixture"
        and operation["event_id"]
        in operation["source_refs"]["source_keys"]
        for operation in review["operations"]
    )
    assert artifact["governance"] == {
        "facts_only": True,
        "decision_optional": True,
        "historical_decisions_inferred": False,
        "motive_inferred": False,
        "advice_generated": False,
        "model_called": False,
        "quantity_authority": "validated_p2c_event_transitions",
        "cash_authority": "explicit_event_inputs_only",
    }


def test_open_no_decision_is_ready_and_not_recorded() -> None:
    events = [
        _event("open", quantity="25", sequence=1),
        _event(
            "increase",
            at=BASE + timedelta(minutes=1),
            quantity="5",
            sequence=2,
        ),
    ]
    artifact = build_operation_review(
        _collection(events),
        event_inputs=events,
    )

    review = artifact["episode_reviews"][0]
    assert review["episode_status"] == "open"
    assert review["operation_review_status"] == "ready"
    assert review["decision_context_status"] == "not_recorded"
    assert [item["operation_type"] for item in review["operations"]] == [
        "position_open",
        "position_increase",
    ]
    assert all(
        item["classification_status"] == "ready"
        for item in review["operations"]
    )


def test_invalid_decision_link_blocks_only_decision_axis() -> None:
    event = _event(
        "open",
        decisions=[
            _decision(
                "decision-too-late",
                "open",
                known_at=BASE + timedelta(minutes=1),
            )
        ],
    )
    artifact = build_operation_review(
        _collection([event]),
        event_inputs=[event],
    )

    review = artifact["episode_reviews"][0]
    assert review["operation_review_status"] == "ready"
    assert review["operations"][0]["classification_status"] == "ready"
    assert review["operations"][0]["operation_type"] == "position_open"
    assert review["decision_context_status"] == "blocked"


def test_reversal_and_negative_state_are_blocked_without_splitting() -> None:
    events = [
        _event("open", quantity="100", sequence=1),
        _event(
            "reversal",
            at=BASE + timedelta(minutes=1),
            side="SELL",
            quantity="150",
            sequence=2,
        ),
    ]
    artifact = build_operation_review(
        _collection(events),
        event_inputs=events,
    )

    review = artifact["episode_reviews"][0]
    reversal = _operation_map(artifact)["reversal"]
    assert review["operation_review_status"] == "blocked"
    assert reversal["operation_type"] == "position_reversal"
    assert reversal["classification_status"] == "blocked"
    assert reversal["qty_before"] == "100"
    assert reversal["qty_after"] == "-50"
    assert reversal["reason_codes"] == ["UNSPLIT_SIGN_REVERSAL"]
    assert validate_operation_review(artifact)["validation_status"] == "accepted"


@pytest.mark.parametrize(
    ("event_type", "side", "quantity"),
    [
        ("opening", "BUY", "80"),
        ("correction", "BUY", "20"),
        ("corporate_action", "TRANSFER_IN", "5"),
        ("transfer", "TRANSFER_IN", "10"),
    ],
)
def test_special_quantity_events_are_never_relabelled_as_normal_trades(
    event_type: str,
    side: str,
    quantity: str,
) -> None:
    event = _event(
        f"special-{event_type}",
        event_type=event_type,
        side=side,
        quantity=quantity,
    )
    artifact = build_operation_review(
        _collection([event]),
        event_inputs=[event],
    )

    review = artifact["episode_reviews"][0]
    operation = review["operations"][0]
    assert review["operation_review_status"] == "partial"
    assert operation["operation_type"] == "special_quantity_adjustment"
    assert operation["classification_status"] == "ambiguous"
    assert operation["reason_codes"] == [
        "SPECIAL_EVENT_REQUIRES_EXPLICIT_SEMANTICS"
    ]
    assert operation["operation_type"] not in {
        "position_open",
        "position_increase",
        "position_reduce",
        "position_close",
    }


def test_cash_events_are_standalone_and_preserve_null_versus_zero() -> None:
    events = [
        _event(
            "cash-null",
            event_type="dividend",
            side="OTHER",
            quantity="0",
            cash_amount=None,
            sequence=1,
        ),
        _event(
            "cash-zero",
            at=BASE + timedelta(minutes=1),
            event_type="cash_fee",
            side="OTHER",
            quantity="0",
            cash_amount="0",
            sequence=2,
        ),
    ]
    artifact = build_operation_review(
        _collection(events),
        event_inputs=events,
    )
    operations = _operation_map(artifact)

    assert artifact["episode_reviews"] == []
    assert len(artifact["standalone_operations"]) == 2
    assert operations["cash-null"]["operation_type"] == "cash_dividend"
    assert operations["cash-null"]["cash_amount"] is None
    assert operations["cash-null"]["cash_amount_status"] == "missing"
    assert operations["cash-null"]["reason_codes"] == [
        "CASH_AMOUNT_NOT_RECORDED"
    ]
    assert operations["cash-zero"]["operation_type"] == "cash_fee"
    assert operations["cash-zero"]["cash_amount"] == "0"
    assert operations["cash-zero"]["cash_amount_status"] == "available"
    for operation in operations.values():
        assert operation["episode_id"] is None
        assert operation["quantity_applicability"] == "not_applicable"
        assert operation["qty_before"] is None
        assert operation["qty_after"] is None
        assert operation["signed_quantity"] is None
        assert operation["classification_status"] == "ready"
        assert operation["decision_context_status"] == "not_applicable"


def test_missing_cash_source_input_fails_closed() -> None:
    cash = _event(
        "cash",
        event_type="dividend",
        side="OTHER",
        quantity="0",
        cash_amount="12.50",
    )
    artifact = build_operation_review(_collection([cash]), event_inputs=[])
    operation = artifact["standalone_operations"][0]

    assert operation["classification_status"] == "blocked"
    assert operation["cash_amount"] is None
    assert operation["reason_codes"] == ["MISSING_EXPLICIT_CASH_EVENT_INPUT"]
    assert validate_operation_review(artifact)["validation_status"] == "accepted"


def test_shuffle_exact_duplicate_and_source_replay_are_byte_stable() -> None:
    events = _closed_events()
    collection = _collection(events)
    baseline = build_operation_review(collection, event_inputs=events)
    shuffled = build_operation_review(
        collection,
        event_inputs=[events[2], events[0], events[3], events[1]],
    )
    duplicated = build_operation_review(
        collection,
        event_inputs=[*events, deepcopy(events[0]), deepcopy(events[2])],
    )

    assert canonical_operation_review_bytes(baseline) == (
        canonical_operation_review_bytes(shuffled)
    )
    assert canonical_operation_review_bytes(baseline) == (
        canonical_operation_review_bytes(duplicated)
    )
    assert baseline["content_id"] == shuffled["content_id"]
    assert baseline["content_id"] == duplicated["content_id"]
    assert {
        item["operation_id"] for item in _operation_map(baseline).values()
    } == {
        item["operation_id"] for item in _operation_map(duplicated).values()
    }
    replay = replay_validate_operation_review(
        baseline,
        episode_collection=collection,
        event_inputs=[*reversed(events), deepcopy(events[0])],
    )
    assert replay["validation_status"] == "accepted"
    assert replay["source_verification"]["status"] == "verified"
    assert replay["findings"] == []


def test_conflicting_event_projection_blocks_the_affected_operation() -> None:
    event = _event("open", quantity="100")
    conflicting = deepcopy(event)
    conflicting["side"] = "SELL"
    artifact = build_operation_review(
        _collection([event]),
        event_inputs=[event, conflicting],
    )
    operation = artifact["episode_reviews"][0]["operations"][0]

    assert operation["classification_status"] == "blocked"
    assert operation["reason_codes"] == ["CONFLICTING_EVENT_INPUT"]
    assert artifact["episode_reviews"][0]["operation_review_status"] == "blocked"


def test_side_or_quantity_mismatch_blocks_instead_of_guessing() -> None:
    event = _event("open", quantity="100")
    mismatched = deepcopy(event)
    mismatched["quantity"] = "99"
    artifact = build_operation_review(
        _collection([event]),
        event_inputs=[mismatched],
    )
    operation = artifact["episode_reviews"][0]["operations"][0]

    assert operation["classification_status"] == "blocked"
    assert operation["reason_codes"] == ["EVENT_INPUT_TRANSITION_MISMATCH"]
    assert operation["operation_type"] == "position_open"


@pytest.mark.parametrize(
    ("event_type", "side", "reason_code"),
    [
        ("buy", "SELL", "EVENT_TYPE_SIDE_MISMATCH"),
        ("unknown_adjustment", "BUY", "UNSUPPORTED_POSITION_EVENT_TYPE"),
    ],
)
def test_explicit_event_semantics_conflict_or_unknown_blocks(
    event_type: str,
    side: str,
    reason_code: str,
) -> None:
    event = _event(
        "explicit-conflict",
        event_type=event_type,
        side=side,
        quantity="100",
    )
    artifact = build_operation_review(
        _collection([event]),
        event_inputs=[event],
    )
    operation = artifact["episode_reviews"][0]["operations"][0]

    assert operation["classification_status"] == "blocked"
    assert reason_code in operation["reason_codes"]
    assert artifact["episode_reviews"][0]["operation_review_status"] == "blocked"
    assert validate_operation_review(artifact)["validation_status"] == "accepted"


def test_validator_and_replay_reject_tampered_operation() -> None:
    events = _closed_events()
    collection = _collection(events)
    artifact = build_operation_review(collection, event_inputs=events)
    tampered = deepcopy(artifact)
    tampered["episode_reviews"][0]["operations"][0][
        "operation_type"
    ] = "position_close"

    validation = validate_operation_review(tampered)
    assert validation["validation_status"] == "blocked"
    assert {
        "OPERATION_REVIEW_CONTENT_ID_MISMATCH",
        "OPERATION_ID_MISMATCH",
        "READY_OPERATION_TRANSITION_MISMATCH",
    }.issubset(_codes(validation))
    replay = replay_validate_operation_review(
        tampered,
        episode_collection=collection,
        event_inputs=events,
    )
    assert replay["validation_status"] == "blocked"
    assert replay["source_verification"]["status"] == "blocked"
    assert "OPERATION_REVIEW_SOURCE_REPLAY_MISMATCH" in _codes(replay)
    with pytest.raises(OperationReviewError):
        query_operation_review(tampered)


def test_hostile_free_text_is_not_promoted_to_operation_output() -> None:
    event = _event("hostile", hostile_payload=True)
    artifact = build_operation_review(
        _collection([event]),
        event_inputs=[event],
    )
    rendered = canonical_operation_review_bytes(artifact).decode("utf-8")
    operation_payload = {
        "episode_reviews": artifact["episode_reviews"],
        "standalone_operations": artifact["standalone_operations"],
    }

    assert "<script>" not in rendered
    assert "guaranteed return" not in rendered
    assert "increase the position" not in rendered
    assert all(
        forbidden not in str(operation_payload).lower()
        for forbidden in (
            "motive",
            "thesis",
            "advice",
            "score",
            "diagnosis",
            "recommendation",
        )
    )
    assert artifact["governance"]["motive_inferred"] is False
    assert artifact["governance"]["advice_generated"] is False
    assert validate_operation_review(artifact)["validation_status"] == "accepted"


def test_builder_and_query_do_not_mutate_inputs_or_artifact() -> None:
    events = _closed_events()
    collection = _collection(events)
    events_before = deepcopy(events)
    collection_before = deepcopy(collection)

    artifact = build_operation_review(collection, event_inputs=events)
    artifact_before = deepcopy(artifact)
    episode_id = artifact["episode_reviews"][0]["episode_id"]
    result = query_operation_review(
        artifact,
        episode_id=episode_id,
        operation_type="position_reduce",
        classification_status="ready",
    )

    assert events == events_before
    assert collection == collection_before
    assert artifact == artifact_before
    assert len(result) == 1
    assert result[0]["event_id"] == "reduce"
    result[0]["reason_codes"].append("MUTATED_QUERY_COPY")
    assert artifact == artifact_before


def test_invalid_collection_digest_shape_is_rejected() -> None:
    collection = _collection([_event("open")])
    collection["collection_digest"] = "not-a-sha256"
    with pytest.raises(OperationReviewError):
        build_operation_review(collection, event_inputs=[_event("open")])


def test_tampered_p2c_collection_cannot_build_or_replay_as_verified() -> None:
    event = _event("open")
    collection = _collection([event])
    artifact = build_operation_review(collection, event_inputs=[event])
    tampered_collection = deepcopy(collection)
    event_ref = tampered_collection["episodes"][0]["event_refs"][0]
    event_ref["quantity_before"] = "50"
    event_ref["quantity_after"] = "150"

    p2c_validation = validate_episode_collection(tampered_collection)
    assert p2c_validation["validation_status"] == "blocked"
    assert {
        "COLLECTION_DIGEST_MISMATCH",
        "EPISODE_DIGEST_MISMATCH",
    }.issubset(_codes(p2c_validation))
    with pytest.raises(OperationReviewError):
        build_operation_review(
            tampered_collection,
            event_inputs=[event],
        )
    replay = replay_validate_operation_review(
        artifact,
        episode_collection=tampered_collection,
        event_inputs=[event],
    )
    assert replay["validation_status"] == "blocked"
    assert replay["source_verification"]["status"] == "blocked"
    assert "OPERATION_REVIEW_REBUILD_FAILED" in _codes(replay)


def test_forged_p2c_schema_is_rejected_at_build_boundary() -> None:
    event = _event("open")
    collection = _collection([event])
    collection["schema_version"] = "forged.collection.v999"

    with pytest.raises(OperationReviewError):
        build_operation_review(collection, event_inputs=[event])


def test_self_rehashed_semantic_tampering_is_rejected() -> None:
    events = _closed_events()
    artifact = build_operation_review(
        _collection(events),
        event_inputs=events,
    )
    tampered = deepcopy(artifact)
    episode = tampered["episode_reviews"][0]
    operation = episode["operations"][0]
    episode["scope"]["motive"] = "guaranteed"
    operation["effective_at"] = "not-a-time"
    operation["reason_codes"] = ["RECOMMEND_BUY"]
    tampered["content_id"] = operation_module._content_id(tampered)

    validation = validate_operation_review(tampered)

    assert validation["validation_status"] == "blocked"
    assert {
        "MALFORMED_EPISODE_SCOPE",
        "MISSING_OPERATION_IDENTITY_FACT",
        "UNKNOWN_OPERATION_REASON_CODE",
        "READY_POSITION_HAS_REASON_CODE",
    }.issubset(_codes(validation))
    with pytest.raises(OperationReviewError):
        query_operation_review(tampered)


def test_binary_float_is_never_canonical_or_queryable() -> None:
    event = _event("open")
    artifact = build_operation_review(
        _collection([event]),
        event_inputs=[event],
    )
    tampered = deepcopy(artifact)
    tampered["episode_reviews"][0]["scope"]["score"] = 1.25

    with pytest.raises(OperationReviewError):
        canonical_operation_review_bytes(tampered)
    validation = validate_operation_review(tampered)
    assert validation["validation_status"] == "blocked"
    assert "NON_CANONICAL_OPERATION_REVIEW_VALUE" in _codes(validation)


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("side", "SELL", "READY_OPERATION_EVENT_FACT_MISMATCH"),
        ("event_type", "correction", "READY_OPERATION_EVENT_FACT_MISMATCH"),
    ],
)
def test_ready_position_semantics_are_closed_after_rehash(
    field: str,
    value: str,
    expected_code: str,
) -> None:
    event = _event("open")
    artifact = build_operation_review(
        _collection([event]),
        event_inputs=[event],
    )
    tampered = deepcopy(artifact)
    tampered["episode_reviews"][0]["operations"][0][field] = value
    tampered["content_id"] = operation_module._content_id(tampered)

    validation = validate_operation_review(tampered)

    assert validation["validation_status"] == "blocked"
    assert expected_code in _codes(validation)


def test_episode_identity_scope_and_source_binding_are_closed() -> None:
    event = _event("open")
    artifact = build_operation_review(
        _collection([event]),
        event_inputs=[event],
    )
    tampered = deepcopy(artifact)
    episode = tampered["episode_reviews"][0]
    operation = episode["operations"][0]
    episode["episode_id"] = ""
    episode["scope"] = {}
    operation["episode_id"] = ""
    operation["operation_id"] = operation_module._operation_id(
        episode_id="",
        event_id=operation["event_id"],
        operation_type=operation["operation_type"],
    )
    binding = tampered["source_binding"]
    binding["episode_collection_schema_version"] = "forged.v1"
    binding["event_projection_count"] = -1
    tampered["content_id"] = operation_module._content_id(tampered)

    validation = validate_operation_review(tampered)

    assert validation["validation_status"] == "blocked"
    assert {
        "INVALID_EPISODE_IDENTITY",
        "MALFORMED_EPISODE_SCOPE",
        "MALFORMED_OPERATION_SOURCE_BINDING",
    }.issubset(_codes(validation))


def test_cash_semantics_and_material_lineage_are_closed_after_rehash() -> None:
    event = _event(
        "cash",
        event_type="dividend",
        side="OTHER",
        quantity="0",
        cash_amount="1.50",
    )
    artifact = build_operation_review(
        _collection([event]),
        event_inputs=[event],
    )
    tampered = deepcopy(artifact)
    operation = tampered["standalone_operations"][0]
    operation["event_type"] = "correction"
    operation["side"] = "BUY"
    operation["source_refs"]["payload_sha256"] = None
    tampered["content_id"] = operation_module._content_id(tampered)

    validation = validate_operation_review(tampered)

    assert validation["validation_status"] == "blocked"
    assert {
        "INVALID_READY_CASH_EVENT",
        "MISSING_MATERIAL_SOURCE_LINEAGE",
    }.issubset(_codes(validation))


def test_position_event_input_time_and_source_mismatch_blocks() -> None:
    event = _event("open")
    collection = _collection([event])
    mismatched = deepcopy(event)
    mismatched["occurred_at"] = (
        BASE + timedelta(days=365)
    ).isoformat()
    mismatched["payload_sha256"] = "f" * 64

    artifact = build_operation_review(
        collection,
        event_inputs=[mismatched],
    )
    operation = artifact["episode_reviews"][0]["operations"][0]

    assert operation["classification_status"] == "blocked"
    assert "EVENT_INPUT_PROVENANCE_MISMATCH" in operation["reason_codes"]
    assert artifact["episode_reviews"][0]["operation_review_status"] == "blocked"
    assert validate_operation_review(artifact)["validation_status"] == "accepted"


def test_same_time_query_preserves_p2c_sequence_not_event_id_order() -> None:
    events = [
        _event("z-open", quantity="40", sequence=1),
        _event("a-increase", quantity="60", sequence=2),
    ]
    artifact = build_operation_review(
        _collection(events),
        event_inputs=events,
    )
    episode_id = artifact["episode_reviews"][0]["episode_id"]

    operations = query_operation_review(artifact, episode_id=episode_id)

    assert [item["event_id"] for item in operations] == [
        "z-open",
        "a-increase",
    ]
    assert [item["sequence_index"] for item in operations] == [0, 1]
    assert [
        (item["qty_before"], item["qty_after"]) for item in operations
    ] == [("0", "40"), ("40", "100")]


@pytest.mark.parametrize("malformed", [None, [], "not-an-artifact"])
def test_malformed_replay_returns_blocked_receipt(
    malformed: object,
) -> None:
    event = _event("open")
    replay = replay_validate_operation_review(
        malformed,
        episode_collection=_collection([event]),
        event_inputs=[event],
    )

    assert replay["validation_status"] == "blocked"
    assert replay["source_verification"]["status"] == "blocked"
    assert "MALFORMED_OPERATION_REVIEW" in _codes(replay)
    assert "OPERATION_REVIEW_SOURCE_REPLAY_MISMATCH" in _codes(replay)


def test_optional_source_record_id_retains_canonical_lineage_and_ready() -> None:
    event = _event("open")
    event["source_record_id"] = None
    collection = _collection([event])
    assert validate_episode_collection(collection)["validation_status"] in {
        "accepted",
        "accepted_with_warnings",
    }

    artifact = build_operation_review(
        collection,
        event_inputs=[event],
    )
    operation = artifact["episode_reviews"][0]["operations"][0]

    assert operation["classification_status"] == "ready"
    assert operation["operation_type"] == "position_open"
    assert operation["source_refs"]["source_record_id"] is None
    assert "acct-1::open" in operation["source_refs"]["source_keys"]
    assert "EVENT_INPUT_PROVENANCE_MISMATCH" not in operation["reason_codes"]
    assert validate_operation_review(artifact)["validation_status"] == "accepted"


def test_blocked_position_role_cannot_contradict_quantity_facts() -> None:
    event = _event("open")
    artifact = build_operation_review(
        _collection([event]),
        event_inputs=[event],
    )
    tampered = deepcopy(artifact)
    episode = tampered["episode_reviews"][0]
    operation = episode["operations"][0]
    operation["operation_type"] = "position_close"
    operation["classification_status"] = "blocked"
    operation["reason_codes"] = ["CONFLICTING_EVENT_INPUT"]
    operation["operation_id"] = operation_module._operation_id(
        episode_id=episode["episode_id"],
        event_id=operation["event_id"],
        operation_type=operation["operation_type"],
    )
    episode["operation_review_status"] = "blocked"
    episode["reason_codes"] = ["BLOCKED_OPERATION_FACT"]
    tampered["summary"] = operation_module._summary(
        tampered["episode_reviews"],
        tampered["standalone_operations"],
    )
    tampered["content_id"] = operation_module._content_id(tampered)

    validation = validate_operation_review(tampered)

    assert validation["validation_status"] == "blocked"
    assert "POSITION_OPERATION_ROLE_MISMATCH" in _codes(validation)
    with pytest.raises(OperationReviewError):
        query_operation_review(tampered)


def test_blocked_cash_type_cannot_contradict_explicit_event_type() -> None:
    event = _event(
        "cash",
        event_type="dividend",
        side="OTHER",
        quantity="0",
        cash_amount="1",
    )
    artifact = build_operation_review(
        _collection([event]),
        event_inputs=[event],
    )
    tampered = deepcopy(artifact)
    operation = tampered["standalone_operations"][0]
    operation["event_type"] = "fill"
    operation["side"] = "BUY"
    operation["classification_status"] = "blocked"
    operation["reason_codes"] = ["INVALID_EXPLICIT_CASH_EVENT"]
    tampered["summary"] = operation_module._summary(
        tampered["episode_reviews"],
        tampered["standalone_operations"],
    )
    tampered["content_id"] = operation_module._content_id(tampered)

    validation = validate_operation_review(tampered)

    assert validation["validation_status"] == "blocked"
    assert "CASH_EVENT_TYPE_MISMATCH" in _codes(validation)


def test_lone_surrogate_validation_and_replay_fail_closed() -> None:
    event = _event("open")
    collection = _collection([event])
    artifact = build_operation_review(
        collection,
        event_inputs=[event],
    )
    tampered = deepcopy(artifact)
    tampered["episode_reviews"][0]["scope"]["account_id"] = "\ud800"

    validation = validate_operation_review(tampered)
    replay = replay_validate_operation_review(
        tampered,
        episode_collection=collection,
        event_inputs=[event],
    )

    assert validation["validation_status"] == "blocked"
    assert "NON_CANONICAL_OPERATION_REVIEW_VALUE" in _codes(validation)
    assert replay["validation_status"] == "blocked"
    assert replay["source_verification"]["status"] == "blocked"


def test_self_rehashed_reversed_episode_chain_is_not_queryable() -> None:
    events = [
        _event("z-open", quantity="40", sequence=1),
        _event("a-increase", quantity="60", sequence=2),
    ]
    artifact = build_operation_review(
        _collection(events),
        event_inputs=events,
    )
    tampered = deepcopy(artifact)
    operations = tampered["episode_reviews"][0]["operations"]
    operations.reverse()
    for sequence_index, operation in enumerate(operations):
        operation["sequence_index"] = sequence_index
    tampered["content_id"] = operation_module._content_id(tampered)

    validation = validate_operation_review(tampered)

    assert validation["validation_status"] == "blocked"
    assert {
        "EPISODE_CHAIN_START_MISMATCH",
        "EPISODE_QUANTITY_CHAIN_MISMATCH",
    }.issubset(_codes(validation))
    with pytest.raises(OperationReviewError):
        query_operation_review(tampered)


@pytest.mark.parametrize(
    "extreme_timestamp",
    [
        "0001-01-01T00:00:00+23:59",
        "9999-12-31T23:59:59-23:59",
    ],
)
def test_timestamp_normalization_overflow_fails_closed(
    extreme_timestamp: str,
) -> None:
    event = _event("open")
    collection = _collection([event])
    artifact = build_operation_review(
        collection,
        event_inputs=[event],
    )
    tampered = deepcopy(artifact)
    tampered["episode_reviews"][0]["operations"][0][
        "effective_at"
    ] = extreme_timestamp
    tampered["content_id"] = operation_module._content_id(tampered)

    validation = validate_operation_review(tampered)
    replay = replay_validate_operation_review(
        tampered,
        episode_collection=collection,
        event_inputs=[event],
    )

    assert validation["validation_status"] == "blocked"
    assert "MISSING_OPERATION_IDENTITY_FACT" in _codes(validation)
    assert replay["validation_status"] == "blocked"
    assert replay["source_verification"]["status"] == "blocked"


def test_decimal_exponent_overflow_fails_closed() -> None:
    event = _event("open")
    collection = _collection([event])
    artifact = build_operation_review(
        collection,
        event_inputs=[event],
    )
    tampered = deepcopy(artifact)
    tampered["episode_reviews"][0]["operations"][0][
        "qty_after"
    ] = "1e999999999"
    tampered["content_id"] = operation_module._content_id(tampered)

    validation = validate_operation_review(tampered)
    replay = replay_validate_operation_review(
        tampered,
        episode_collection=collection,
        event_inputs=[event],
    )

    assert validation["validation_status"] == "blocked"
    assert "INVALID_POSITION_QUANTITY" in _codes(validation)
    assert replay["validation_status"] == "blocked"
    assert replay["source_verification"]["status"] == "blocked"


def test_self_rehashed_reversed_cash_order_is_not_queryable() -> None:
    events = [
        _event(
            "cash-early",
            event_type="dividend",
            side="OTHER",
            quantity="0",
            cash_amount="1",
            sequence=1,
        ),
        _event(
            "cash-late",
            at=BASE + timedelta(minutes=1),
            event_type="cash_fee",
            side="OTHER",
            quantity="0",
            cash_amount="-1",
            sequence=2,
        ),
    ]
    artifact = build_operation_review(
        _collection(events),
        event_inputs=events,
    )
    tampered = deepcopy(artifact)
    standalone = tampered["standalone_operations"]
    standalone.reverse()
    for sequence_index, operation in enumerate(standalone):
        operation["sequence_index"] = sequence_index
    tampered["content_id"] = operation_module._content_id(tampered)

    validation = validate_operation_review(tampered)

    assert validation["validation_status"] == "blocked"
    assert "STANDALONE_OPERATION_ORDER_MISMATCH" in _codes(validation)
    with pytest.raises(OperationReviewError):
        query_operation_review(tampered)
