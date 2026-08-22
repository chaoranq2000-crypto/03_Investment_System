from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import src.investment_review.ledger_snapshot_reconstruction as reconstruction_module
from src.investment_review.ledger_snapshot_reconstruction import (
    LEDGER_SNAPSHOT_BASELINE_SCHEMA_VERSION,
    LEDGER_SNAPSHOT_RECONSTRUCTION_SCHEMA_VERSION,
    LedgerSnapshotReconstructionError,
    build_ledger_snapshot_reconstruction,
    canonical_ledger_snapshot_reconstruction_bytes,
    replay_validate_ledger_snapshot_reconstruction,
    validate_ledger_snapshot_reconstruction,
)


def source_binding() -> dict[str, str]:
    return {
        "portfolio_source_sha256": "1" * 64,
        "sync_source_sha256": "2" * 64,
        "mapping_sha256": "3" * 64,
        "source_cutoff_id": "cutoff_fixture_v1",
        "sidecar_projection_sha256": "4" * 64,
        "knowledge_provenance_content_id": "sha256:" + "5" * 64,
        "cash_baseline_proof_content_id": "sha256:" + "6" * 64,
    }


def event(
    event_id: str,
    occurred_at: str,
    *,
    side: str,
    quantity: str,
    gross: str,
    source_record_id: str | None = None,
    symbol: str = "588200.SH",
    known_at: str | None = None,
) -> dict[str, object]:
    event_type = side.lower()
    return {
        "event_id": event_id,
        "source_id": "src_fixture",
        "source_record_id": source_record_id or event_id,
        "event_type": event_type,
        "occurred_at": occurred_at,
        "known_at": known_at or occurred_at,
        "account": "default",
        "market": None,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "price": "1",
        "gross_amount": gross,
        "cash_amount": "0",
        "fees": "0",
        "currency": "CNY",
        "payload_sha256": hashlib.sha256(event_id.encode("utf-8")).hexdigest(),
        "raw_payload": {
            "source_row": {
                "note": "fees_missing=true",
                "external_id": source_record_id or event_id,
            }
        },
        "decision_refs": [],
    }


def fixture_events() -> list[dict[str, object]]:
    return [
        event(
            "evt_a",
            "2025-08-26T01:32:55Z",
            side="BUY",
            quantity="500",
            gross="1036.5",
        ),
        event(
            "evt_b",
            "2025-08-27T06:36:01Z",
            side="SELL",
            quantity="500",
            gross="1061.5",
        ),
        event(
            "evt_c",
            "2026-07-17T03:17:06Z",
            side="BUY",
            quantity="1700",
            gross="6429.4",
        ),
        event(
            "evt_d",
            "2026-07-17T03:20:09Z",
            side="BUY",
            quantity="500",
            gross="1880.5",
        ),
        event(
            "evt_e",
            "2026-07-17T03:20:10Z",
            side="BUY",
            quantity="400",
            gross="1504.4",
        ),
        event(
            "evt_f",
            "2026-07-17T03:20:10Z",
            side="BUY",
            quantity="500",
            gross="1880.5",
        ),
        event(
            "evt_g",
            "2026-07-17T03:27:00Z",
            side="BUY",
            quantity="600",
            gross="2251.8",
        ),
        event(
            "evt_h",
            "2026-07-17T03:27:00Z",
            side="BUY",
            quantity="600",
            gross="2251.8",
        ),
        event(
            "evt_i",
            "2026-07-17T05:55:28Z",
            side="BUY",
            quantity="3800",
            gross="13733.2",
        ),
    ]


def episode() -> dict[str, object]:
    return {
        "episode_id": "te_588200_open",
        "scope": {
            "account_id": "default",
            "instrument_id": "588200.SH",
            "symbol": "588200.SH",
            "currency": "CNY",
        },
        "event_refs": [
            {"event_id": event_id}
            for event_id in (
                "evt_c",
                "evt_d",
                "evt_e",
                "evt_f",
                "evt_g",
                "evt_h",
                "evt_i",
            )
        ],
    }


def build(events: list[dict[str, object]] | None = None) -> dict[str, object]:
    return build_ledger_snapshot_reconstruction(
        events or fixture_events(),
        episode=episode(),
        perspective="user",
        as_of="2026-07-17T05:55:28Z",
        knowledge_cutoff="2026-07-18T00:00:00Z",
        source_binding=source_binding(),
    )


def checkpoint(artifact: dict[str, object]) -> dict[str, object]:
    return next(
        item
        for item in artifact["anchors"]
        if item["anchor_type"] == "checkpoint"
    )


def position_baseline(
    *,
    quantity: str,
    cost_basis: str,
    effective_at: str = "2026-07-16T08:00:00Z",
) -> dict[str, object]:
    return {
        "schema_version": LEDGER_SNAPSHOT_BASELINE_SCHEMA_VERSION,
        "position": {
            "status": "available",
            "quantity": quantity,
            "cost_basis": cost_basis,
            "effective_at": effective_at,
            "known_at": effective_at,
            "method": "explicit_reviewed_baseline",
            "source_refs": ["position_baseline:fixture"],
        },
        "cash": {
            "status": "missing",
            "value": None,
            "currency": "CNY",
            "effective_at": None,
            "known_at": None,
            "recorded_at": None,
            "fee_pending": False,
            "method": "missing",
            "source_refs": [],
        },
    }


def build_single_episode(
    events: list[dict[str, object]],
    *,
    baseline: dict[str, object],
    as_of: str = "2026-07-17T05:55:28Z",
    knowledge_cutoff: str = "2026-07-18T00:00:00Z",
) -> dict[str, object]:
    selected_episode = {
        "episode_id": "te_hostile_fixture",
        "scope": {
            "account_id": "default",
            "instrument_id": "588200.SH",
            "symbol": "588200.SH",
            "currency": "CNY",
        },
        "event_refs": [
            {"event_id": str(item["event_id"])}
            for item in events
        ],
    }
    return build_ledger_snapshot_reconstruction(
        events,
        episode=selected_episode,
        perspective="user",
        as_of=as_of,
        knowledge_cutoff=knowledge_cutoff,
        source_binding=source_binding(),
        baseline_proof=baseline,
    )


def rehash(artifact: dict[str, object]) -> None:
    artifact["content_id"] = ""
    artifact["content_id"] = reconstruction_module._content_id(artifact)


def test_prior_flat_reconstructs_8100_without_fabricating_other_fields() -> None:
    artifact = build()

    assert artifact["schema_version"] == (
        LEDGER_SNAPSHOT_RECONSTRUCTION_SCHEMA_VERSION
    )
    assert artifact["baseline"]["derived_prior_flat"]["status"] == "available"
    assert artifact["event_cursor"]["cursor_scope"] == "partition"
    assert artifact["event_cursor"]["account_event_set_complete"] is False

    fields = checkpoint(artifact)["snapshot_cash_valuation"]["fields"]
    assert fields["position_quantity"] == {
        "status": "available",
        "value": "8100",
        "unit": "shares",
        "source_refs": fields["position_quantity"]["source_refs"],
    }
    assert fields["cost_basis"]["status"] == "partial"
    assert fields["cost_basis"]["value"] == "29931.6"
    assert fields["cash"]["status"] == "missing"
    assert fields["cash"]["value"] is None
    assert fields["price"]["value"] is None
    assert fields["nav"]["value"] is None
    assert fields["weight"]["value"] is None
    assert fields["industry"]["value"] is None
    assert (
        validate_ledger_snapshot_reconstruction(artifact)[
            "validation_status"
        ]
        == "accepted"
    )


def test_same_time_event_anchors_are_ambiguous_but_checkpoint_is_deterministic() -> None:
    artifact = build()
    anchors = [
        item
        for item in artifact["anchors"]
        if item["event_id"] in {"evt_e", "evt_f", "evt_g", "evt_h"}
    ]

    assert anchors
    assert {item["ordering_status"] for item in anchors} == {"ambiguous"}
    assert all(item["position"]["quantity"] is None for item in anchors)
    assert (
        checkpoint(artifact)["position"]["quantity"] == "8100"
    )


def test_input_order_and_exact_duplicate_are_byte_deterministic() -> None:
    inputs = fixture_events()
    first = build(inputs)
    shuffled = list(reversed(inputs)) + [deepcopy(inputs[0])]
    second = build(shuffled)

    assert canonical_ledger_snapshot_reconstruction_bytes(first) == (
        canonical_ledger_snapshot_reconstruction_bytes(second)
    )
    assert replay_validate_ledger_snapshot_reconstruction(
        first,
        event_inputs=inputs,
        episode=episode(),
    )["source_verification"]["status"] == "verified"


def test_missing_opening_baseline_keeps_quantity_partial_not_zero() -> None:
    inputs = fixture_events()[2:]
    artifact = build(inputs)
    fields = checkpoint(artifact)["snapshot_cash_valuation"]["fields"]

    assert fields["position_quantity"]["status"] == "partial"
    assert fields["position_quantity"]["value"] == "8100"
    assert any(
        gap["code"] == "OPENING_BASELINE_NOT_PROVEN"
        for gap in artifact["gaps"]
    )


def test_conflicting_duplicate_and_binary_float_fail_closed() -> None:
    inputs = fixture_events()
    conflict = deepcopy(inputs[0])
    conflict["quantity"] = "501"
    with pytest.raises(
        LedgerSnapshotReconstructionError,
        match="conflicting duplicate",
    ):
        build(inputs + [conflict])

    binary_float = deepcopy(inputs)
    binary_float[0]["quantity"] = 500.0
    with pytest.raises(
        LedgerSnapshotReconstructionError,
        match="binary float",
    ):
        build(binary_float)


def test_cutoff_safe_cash_baseline_stays_partial_when_fees_pending() -> None:
    baseline = {
        "schema_version": LEDGER_SNAPSHOT_BASELINE_SCHEMA_VERSION,
        "position": {
            "status": "missing",
            "quantity": None,
            "cost_basis": None,
            "effective_at": None,
            "known_at": None,
            "method": "missing",
            "source_refs": [],
        },
        "cash": {
            "status": "partial",
            "value": "2697",
            "currency": "CNY",
            "effective_at": "2026-07-15T08:00:00Z",
            "known_at": "2026-07-15T08:00:00Z",
            "recorded_at": "2026-07-15T08:00:00Z",
            "fee_pending": True,
            "method": "cash_balance_snapshot",
            "source_refs": ["cash_snapshot:fixture"],
        },
    }
    unrelated = event(
        "evt_unrelated",
        "2026-07-17T04:00:00Z",
        side="BUY",
        quantity="1",
        gross="100",
        symbol="600000.SH",
    )
    artifact = build_ledger_snapshot_reconstruction(
        fixture_events() + [unrelated],
        episode=episode(),
        perspective="user",
        as_of="2026-07-17T05:55:28Z",
        knowledge_cutoff="2026-07-18T00:00:00Z",
        source_binding=source_binding(),
        baseline_proof=baseline,
    )

    cash = checkpoint(artifact)["snapshot_cash_valuation"]["fields"]["cash"]
    assert cash["status"] == "partial"
    # The 2025 round trip is before the baseline and is not counted twice.
    # The unrelated account BUY is included because cash is account-scoped.
    assert cash["value"] == "-27334.6"
    assert "evt_unrelated" in artifact["event_cursor"][
        "included_account_event_ids"
    ]
    assert "evt_unrelated" not in artifact["event_cursor"]["scope_event_ids"]
    cash_gap = next(
        item
        for item in artifact["gaps"]
        if item["code"] == "CASH_BALANCE_PARTIAL_FEE_UNKNOWN"
    )
    assert cash_gap["owner"] == "data_owner"
    assert cash_gap["severity"] == "warning"
    assert cash_gap["next_step"]


def test_sell_reduces_carrying_cost_proportionally_not_by_proceeds() -> None:
    sell = event(
        "evt_sell",
        "2026-07-17T03:17:06Z",
        side="SELL",
        quantity="40",
        gross="800",
    )
    sell_episode = {
        "episode_id": "te_sell",
        "scope": {
            "account_id": "default",
            "instrument_id": "588200.SH",
            "symbol": "588200.SH",
            "currency": "CNY",
        },
        "event_refs": [{"event_id": "evt_sell"}],
    }
    baseline = {
        "schema_version": LEDGER_SNAPSHOT_BASELINE_SCHEMA_VERSION,
        "position": {
            "status": "available",
            "quantity": "100",
            "cost_basis": "1000",
            "effective_at": "2026-07-16T08:00:00Z",
            "known_at": "2026-07-16T08:00:00Z",
            "method": "explicit_reviewed_baseline",
            "source_refs": ["position_baseline:fixture"],
        },
        "cash": {
            "status": "missing",
            "value": None,
            "currency": "CNY",
            "effective_at": None,
            "known_at": None,
            "recorded_at": None,
            "fee_pending": False,
            "method": "missing",
            "source_refs": [],
        },
    }
    artifact = build_ledger_snapshot_reconstruction(
        [sell],
        episode=sell_episode,
        perspective="user",
        as_of="2026-07-17T05:55:28Z",
        knowledge_cutoff="2026-07-18T00:00:00Z",
        source_binding=source_binding(),
        baseline_proof=baseline,
    )
    fields = checkpoint(artifact)["snapshot_cash_valuation"]["fields"]
    assert fields["position_quantity"]["value"] == "60"
    assert fields["cost_basis"]["value"] == "600"
    assert fields["cost_basis"]["status"] == "available"


def test_future_known_non_episode_event_is_excluded_and_bound_to_cursor() -> None:
    future_known = event(
        "evt_future_known",
        "2026-07-17T04:00:00Z",
        known_at="2026-07-19T00:00:00Z",
        side="BUY",
        quantity="1",
        gross="1",
        symbol="600000.SH",
    )
    artifact = build(fixture_events() + [future_known])

    assert artifact["event_cursor"]["excluded_future_known_ids"] == [
        "evt_future_known"
    ]
    assert "evt_future_known" not in artifact["event_cursor"][
        "included_account_event_ids"
    ]


def test_same_time_identity_order_cannot_choose_checkpoint_cost() -> None:
    baseline = position_baseline(
        quantity="10",
        cost_basis="100",
        effective_at="2026-07-16T08:00:00Z",
    )

    sell_first_by_id = [
        event(
            "a_sell",
            "2026-07-17T03:20:10Z",
            side="SELL",
            quantity="10",
            gross="150",
        ),
        event(
            "z_buy",
            "2026-07-17T03:20:10Z",
            side="BUY",
            quantity="10",
            gross="200",
        ),
    ]
    buy_first_by_id = [
        event(
            "a_buy",
            "2026-07-17T03:20:10Z",
            side="BUY",
            quantity="10",
            gross="200",
        ),
        event(
            "z_sell",
            "2026-07-17T03:20:10Z",
            side="SELL",
            quantity="10",
            gross="150",
        ),
    ]
    for item in [*sell_first_by_id, *buy_first_by_id]:
        item["fees"] = "1"
        item["raw_payload"]["source_row"]["note"] = ""

    first = build_single_episode(sell_first_by_id, baseline=baseline)
    second = build_single_episode(buy_first_by_id, baseline=baseline)

    for artifact in (first, second):
        fields = checkpoint(artifact)["snapshot_cash_valuation"]["fields"]
        assert fields["position_quantity"]["status"] == "available"
        assert fields["position_quantity"]["value"] == "10"
        assert fields["cost_basis"]["status"] == "partial"
        assert fields["cost_basis"]["value"] is None
        assert {
            gap["code"] for gap in artifact["gaps"]
        } >= {"SAME_TIME_BUSINESS_ORDER_AMBIGUOUS"}
        assert "NEGATIVE_POSITION_QUANTITY" not in {
            gap["code"] for gap in artifact["gaps"]
        }


def test_same_time_negative_check_uses_feasible_business_orders_not_ids() -> None:
    baseline = position_baseline(
        quantity="0",
        cost_basis="0",
        effective_at="2026-07-16T08:00:00Z",
    )
    events = [
        event(
            "a_sell",
            "2026-07-17T03:20:10Z",
            side="SELL",
            quantity="10",
            gross="100",
        ),
        event(
            "z_buy",
            "2026-07-17T03:20:10Z",
            side="BUY",
            quantity="10",
            gross="100",
        ),
    ]
    for item in events:
        item["fees"] = "1"
        item["raw_payload"]["source_row"]["note"] = ""

    artifact = build_single_episode(events, baseline=baseline)
    fields = checkpoint(artifact)["snapshot_cash_valuation"]["fields"]

    assert fields["position_quantity"]["status"] == "available"
    assert fields["position_quantity"]["value"] == "0"
    assert "NEGATIVE_POSITION_QUANTITY" not in {
        gap["code"] for gap in artifact["gaps"]
    }
    assert "SAME_TIME_BUSINESS_ORDER_AMBIGUOUS" in {
        gap["code"] for gap in artifact["gaps"]
    }


def test_explicit_same_time_sequence_has_event_specific_pre_post_anchors() -> None:
    baseline = position_baseline(
        quantity="10",
        cost_basis="100",
        effective_at="2026-07-16T08:00:00Z",
    )
    baseline["cash"] = {
        "status": "available",
        "value": "1000",
        "currency": "CNY",
        "effective_at": "2026-07-16T08:00:00Z",
        "known_at": "2026-07-16T08:00:00Z",
        "recorded_at": "2026-07-16T08:00:00Z",
        "fee_pending": False,
        "method": "cash_balance_snapshot",
        "source_refs": ["cash_baseline:fixture"],
    }
    events = [
        event(
            "evt_sequence_one",
            "2026-07-17T03:20:10Z",
            side="BUY",
            quantity="5",
            gross="50",
        ),
        event(
            "evt_sequence_two",
            "2026-07-17T03:20:10Z",
            side="BUY",
            quantity="2",
            gross="20",
        ),
    ]
    for sequence, item in enumerate(events, start=1):
        item["fees"] = "1"
        item["raw_payload"]["source_row"]["note"] = ""
        item["raw_payload"]["source_row"]["business_sequence"] = sequence

    artifact = build_single_episode(events, baseline=baseline)
    anchors = {
        (item["event_id"], item["anchor_type"]): item
        for item in artifact["anchors"]
        if item["event_id"] is not None
    }

    expected = {
        ("evt_sequence_one", "event_pre"): ("10", "100", "1000"),
        ("evt_sequence_one", "event_post"): ("15", "151", "949"),
        ("evt_sequence_two", "event_pre"): ("15", "151", "949"),
        ("evt_sequence_two", "event_post"): ("17", "172", "928"),
    }
    for key, (quantity, cost, cash) in expected.items():
        anchor = anchors[key]
        fields = anchor["snapshot_cash_valuation"]["fields"]
        assert anchor["ordering_status"] == "proven"
        assert anchor["position"]["quantity"] == quantity
        assert anchor["position"]["cost_basis"] == cost
        assert fields["cash"]["value"] == cash


def test_entry_id_is_not_same_time_business_order_proof() -> None:
    baseline = position_baseline(quantity="10", cost_basis="100")
    events = [
        event(
            "evt_entry_one",
            "2026-07-17T03:20:10Z",
            side="BUY",
            quantity="5",
            gross="50",
        ),
        event(
            "evt_entry_two",
            "2026-07-17T03:20:10Z",
            side="BUY",
            quantity="2",
            gross="20",
        ),
    ]
    for sequence, item in enumerate(events, start=1):
        item["fees"] = "1"
        item["raw_payload"]["source_row"]["note"] = ""
        item["raw_payload"]["source_row"]["entry_id"] = sequence

    artifact = build_single_episode(events, baseline=baseline)
    anchors = {
        (item["event_id"], item["anchor_type"]): item
        for item in artifact["anchors"]
        if item["event_id"] is not None
    }

    for anchor in anchors.values():
        assert anchor["ordering_status"] == "ambiguous"
        assert anchor["position"]["quantity"] is None
    checkpoint_fields = checkpoint(artifact)["snapshot_cash_valuation"]["fields"]
    assert checkpoint_fields["position_quantity"]["status"] == "available"
    assert checkpoint_fields["position_quantity"]["value"] == "17"
    assert checkpoint_fields["position_quantity"]["unit"] == "shares"
    assert "SAME_TIME_BUSINESS_ORDER_AMBIGUOUS" in {
        item["code"] for item in artifact["gaps"]
    }


def test_conflicting_business_sequence_evidence_fails_closed() -> None:
    baseline = position_baseline(quantity="10", cost_basis="100")
    events = [
        event(
            "evt_sequence_conflict",
            "2026-07-17T03:20:10Z",
            side="BUY",
            quantity="5",
            gross="50",
        ),
        event(
            "evt_sequence_peer",
            "2026-07-17T03:20:10Z",
            side="BUY",
            quantity="2",
            gross="20",
        ),
    ]
    for item in events:
        item["fees"] = "1"
        item["raw_payload"]["source_row"]["note"] = ""
    events[0]["raw_payload"]["business_sequence"] = 1
    events[0]["raw_payload"]["source_row"]["business_sequence"] = 2
    events[1]["raw_payload"]["business_sequence"] = 3
    events[1]["raw_payload"]["source_row"]["business_sequence"] = 3

    with pytest.raises(
        LedgerSnapshotReconstructionError,
        match=r"(sequence|conflict|order)",
    ):
        build_single_episode(events, baseline=baseline)


def test_account_cash_anchor_marks_cross_symbol_same_time_order_ambiguous() -> None:
    baseline = position_baseline(
        quantity="10",
        cost_basis="100",
        effective_at="2026-07-16T08:00:00Z",
    )
    baseline["cash"] = {
        "status": "available",
        "value": "1000",
        "currency": "CNY",
        "effective_at": "2026-07-16T08:00:00Z",
        "known_at": "2026-07-16T08:00:00Z",
        "recorded_at": "2026-07-16T08:00:00Z",
        "fee_pending": False,
        "method": "cash_balance_snapshot",
        "source_refs": ["cash_baseline:fixture"],
    }
    target = event(
        "evt_target",
        "2026-07-17T03:20:10Z",
        side="BUY",
        quantity="5",
        gross="50",
    )
    unrelated = event(
        "evt_other_symbol",
        "2026-07-17T03:20:10Z",
        side="BUY",
        quantity="2",
        gross="20",
        symbol="600000.SH",
    )
    for item in (target, unrelated):
        item["fees"] = "1"
        item["raw_payload"]["source_row"]["note"] = ""
    selected_episode = {
        "episode_id": "te_cross_symbol_cash",
        "scope": {
            "account_id": "default",
            "instrument_id": "588200.SH",
            "symbol": "588200.SH",
            "currency": "CNY",
        },
        "event_refs": [{"event_id": "evt_target"}],
    }

    artifact = build_ledger_snapshot_reconstruction(
        [target, unrelated],
        episode=selected_episode,
        perspective="user",
        as_of="2026-07-17T05:55:28Z",
        knowledge_cutoff="2026-07-18T00:00:00Z",
        source_binding=source_binding(),
        baseline_proof=baseline,
    )
    pre = next(
        item
        for item in artifact["anchors"]
        if item["event_id"] == "evt_target"
        and item["anchor_type"] == "event_pre"
    )
    post = next(
        item
        for item in artifact["anchors"]
        if item["event_id"] == "evt_target"
        and item["anchor_type"] == "event_post"
    )

    assert pre["position"]["quantity"] == "10"
    assert post["position"]["quantity"] == "15"
    for anchor in (pre, post):
        cash = anchor["snapshot_cash_valuation"]["fields"]["cash"]
        assert cash["status"] == "partial"
        assert cash["value"] is None
    assert "SAME_TIME_BUSINESS_ORDER_AMBIGUOUS" in {
        gap["code"] for gap in artifact["gaps"]
    }
    checkpoint_cash = checkpoint(artifact)["snapshot_cash_valuation"]["fields"][
        "cash"
    ]
    assert checkpoint_cash["status"] == "available"
    assert checkpoint_cash["value"] == "928"


def test_event_type_and_side_conflict_fails_closed() -> None:
    conflicting = event(
        "evt_conflicting_semantics",
        "2026-07-17T03:20:10Z",
        side="SELL",
        quantity="5",
        gross="50",
    )
    conflicting["event_type"] = "buy"
    conflicting["fees"] = "1"
    conflicting["raw_payload"]["source_row"]["note"] = ""

    with pytest.raises(
        LedgerSnapshotReconstructionError,
        match=r"(event_type|side|semantic|conflict)",
    ):
        build_single_episode(
            [conflicting],
            baseline=position_baseline(quantity="10", cost_basis="100"),
        )


def test_cross_symbol_cash_event_semantic_conflict_fails_closed() -> None:
    baseline = position_baseline(quantity="10", cost_basis="100")
    baseline["cash"] = {
        "status": "available",
        "value": "1000",
        "currency": "CNY",
        "effective_at": "2026-07-16T08:00:00Z",
        "known_at": "2026-07-16T08:00:00Z",
        "recorded_at": "2026-07-16T08:00:00Z",
        "fee_pending": False,
        "method": "cash_balance_snapshot",
        "source_refs": ["cash_baseline:fixture"],
    }
    target = event(
        "evt_target",
        "2026-07-17T03:20:10Z",
        side="BUY",
        quantity="5",
        gross="50",
    )
    conflicting_cash_event = event(
        "evt_other_symbol_conflict",
        "2026-07-17T03:21:10Z",
        side="SELL",
        quantity="2",
        gross="20",
        symbol="600000.SH",
    )
    conflicting_cash_event["event_type"] = "buy"
    for item in (target, conflicting_cash_event):
        item["fees"] = "1"
        item["raw_payload"]["source_row"]["note"] = ""
    selected_episode = {
        "episode_id": "te_cross_symbol_conflict",
        "scope": {
            "account_id": "default",
            "instrument_id": "588200.SH",
            "symbol": "588200.SH",
            "currency": "CNY",
        },
        "event_refs": [{"event_id": "evt_target"}],
    }

    with pytest.raises(
        LedgerSnapshotReconstructionError,
        match=r"(event_type|side|semantic|conflict)",
    ):
        build_ledger_snapshot_reconstruction(
            [target, conflicting_cash_event],
            episode=selected_episode,
            perspective="user",
            as_of="2026-07-17T05:55:28Z",
            knowledge_cutoff="2026-07-18T00:00:00Z",
            source_binding=source_binding(),
            baseline_proof=baseline,
        )


def test_future_effective_baseline_cannot_leak_into_earlier_anchors() -> None:
    only_event = event(
        "evt_before_future_baseline",
        "2026-07-17T03:20:10Z",
        side="BUY",
        quantity="5",
        gross="50",
    )
    future_baseline = position_baseline(
        quantity="10",
        cost_basis="100",
        effective_at="2026-07-17T12:00:00Z",
    )

    with pytest.raises(
        LedgerSnapshotReconstructionError,
        match=r"(baseline|effective|as_of|future)",
    ):
        build_single_episode(
            [only_event],
            baseline=future_baseline,
            as_of="2026-07-17T05:55:28Z",
            knowledge_cutoff="2026-07-18T00:00:00Z",
        )


def test_negative_position_baseline_cannot_be_hidden_by_later_buy() -> None:
    only_event = event(
        "evt_later_buy",
        "2026-07-17T03:20:10Z",
        side="BUY",
        quantity="20",
        gross="200",
    )

    with pytest.raises(
        LedgerSnapshotReconstructionError,
        match=r"(baseline|negative|quantity|cost)",
    ):
        build_single_episode(
            [only_event],
            baseline=position_baseline(
                quantity="-10",
                cost_basis="-100",
            ),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [("gross_amount", "-50"), ("fees", "-1")],
)
def test_negative_trade_economic_amounts_fail_closed(
    field: str,
    value: str,
) -> None:
    only_event = event(
        "evt_negative_economic_amount",
        "2026-07-17T03:20:10Z",
        side="BUY",
        quantity="5",
        gross="50",
    )
    only_event[field] = value
    only_event["raw_payload"]["source_row"]["note"] = ""

    with pytest.raises(
        LedgerSnapshotReconstructionError,
        match=r"(negative|gross|fee|amount|invalid)",
    ):
        build_single_episode(
            [only_event],
            baseline=position_baseline(quantity="10", cost_basis="100"),
        )


@pytest.mark.parametrize("mismatch_axis", ["event", "cash_baseline"])
def test_currency_mismatch_cannot_be_silently_treated_as_cny(
    mismatch_axis: str,
) -> None:
    only_event = event(
        "evt_currency",
        "2026-07-17T03:20:10Z",
        side="BUY",
        quantity="5",
        gross="50",
    )
    baseline = position_baseline(quantity="10", cost_basis="100")
    if mismatch_axis == "event":
        only_event["currency"] = "USD"
    else:
        baseline["cash"] = {
            "status": "available",
            "value": "1000",
            "currency": "USD",
            "effective_at": "2026-07-16T08:00:00Z",
            "known_at": "2026-07-16T08:00:00Z",
            "recorded_at": "2026-07-16T08:00:00Z",
            "fee_pending": False,
            "method": "cash_balance_snapshot",
            "source_refs": ["cash_baseline:usd"],
        }

    with pytest.raises(
        LedgerSnapshotReconstructionError,
        match=r"(currency|mismatch|FX)",
    ):
        build_single_episode([only_event], baseline=baseline)


@pytest.mark.parametrize("missing_axis", ["event", "episode"])
def test_missing_currency_cannot_default_to_cny(missing_axis: str) -> None:
    only_event = event(
        "evt_missing_currency",
        "2026-07-17T03:20:10Z",
        side="BUY",
        quantity="5",
        gross="50",
    )
    selected_episode = {
        "episode_id": "te_missing_currency",
        "scope": {
            "account_id": "default",
            "instrument_id": "588200.SH",
            "symbol": "588200.SH",
            "currency": "CNY",
        },
        "event_refs": [{"event_id": "evt_missing_currency"}],
    }
    if missing_axis == "event":
        only_event["currency"] = None
    else:
        selected_episode["scope"].pop("currency")

    with pytest.raises(
        LedgerSnapshotReconstructionError,
        match=r"(currency|required|missing)",
    ):
        build_ledger_snapshot_reconstruction(
            [only_event],
            episode=selected_episode,
            perspective="user",
            as_of="2026-07-17T05:55:28Z",
            knowledge_cutoff="2026-07-18T00:00:00Z",
            source_binding=source_binding(),
            baseline_proof=position_baseline(
                quantity="10",
                cost_basis="100",
            ),
        )


def test_validator_rejects_self_rehashed_position_axis_contradiction() -> None:
    artifact = build()
    tampered = deepcopy(artifact)
    checkpoint_anchor = checkpoint(tampered)
    checkpoint_anchor["position"]["quantity"] = "999"
    rehash(tampered)

    assert validate_ledger_snapshot_reconstruction(tampered)[
        "validation_status"
    ] == "blocked"


def test_validator_rejects_self_rehashed_fabricated_valuation_field() -> None:
    artifact = build()
    tampered = deepcopy(artifact)
    price = checkpoint(tampered)["snapshot_cash_valuation"]["fields"]["price"]
    price.update(
        {
            "status": "available",
            "value": "9999",
            "source_refs": ["fabricated:price"],
        }
    )
    rehash(tampered)

    assert validate_ledger_snapshot_reconstruction(tampered)[
        "validation_status"
    ] == "blocked"


def test_validator_rejects_self_rehashed_value_hidden_behind_missing_cash() -> None:
    artifact = build()
    tampered = deepcopy(artifact)
    cash = checkpoint(tampered)["snapshot_cash_valuation"]["fields"]["cash"]
    assert cash["status"] == "missing"
    cash["value"] = "999"
    rehash(tampered)

    assert validate_ledger_snapshot_reconstruction(tampered)[
        "validation_status"
    ] == "blocked"


def test_validator_rejects_self_rehashed_value_hidden_in_missing_baseline() -> None:
    artifact = build()
    tampered = deepcopy(artifact)
    assert tampered["baseline"]["position"]["status"] == "missing"
    tampered["baseline"]["position"]["quantity"] = "999"
    rehash(tampered)

    assert validate_ledger_snapshot_reconstruction(tampered)[
        "validation_status"
    ] == "blocked"


def test_validator_rejects_self_rehashed_fabricated_cursor_membership() -> None:
    artifact = build()
    tampered = deepcopy(artifact)
    tampered["event_cursor"]["included_event_ids"].append("evt_fabricated")
    tampered["event_cursor"]["included_event_ids"].sort()
    rehash(tampered)

    assert validate_ledger_snapshot_reconstruction(tampered)[
        "validation_status"
    ] == "blocked"


def test_validator_rejects_self_rehashed_cutoff_before_as_of() -> None:
    artifact = build()
    tampered = deepcopy(artifact)
    tampered["knowledge_cutoff"] = "2026-07-17T00:00:00+00:00"
    rehash(tampered)

    assert validate_ledger_snapshot_reconstruction(tampered)[
        "validation_status"
    ] == "blocked"


def test_validator_rejects_scope_event_missing_from_account_cash_cursor() -> None:
    artifact = build()
    tampered = deepcopy(artifact)
    episode_event_id = tampered["source_binding"]["episode_event_ids"][0]
    tampered["event_cursor"]["included_account_event_ids"].remove(
        episode_event_id
    )
    rehash(tampered)

    assert validate_ledger_snapshot_reconstruction(tampered)[
        "validation_status"
    ] == "blocked"


def test_validator_requires_gap_owner_severity_and_next_step() -> None:
    artifact = build()
    tampered = deepcopy(artifact)
    tampered["gaps"][0]["owner"] = ""
    tampered["gaps"][0]["next_step"] = ""
    rehash(tampered)

    assert validate_ledger_snapshot_reconstruction(tampered)[
        "validation_status"
    ] == "blocked"


def test_validator_rejects_hidden_same_time_anchor_ambiguity() -> None:
    artifact = build()
    tampered = deepcopy(artifact)
    anchor = next(
        item
        for item in tampered["anchors"]
        if item["anchor_type"] == "event_pre"
        and item["ordering_status"] == "ambiguous"
    )
    anchor["ordering_status"] = "proven"
    anchor["same_time_event_ids"] = []
    rehash(tampered)

    assert validate_ledger_snapshot_reconstruction(tampered)[
        "validation_status"
    ] == "blocked"


def test_validator_rejects_event_anchor_pair_after_checkpoint_as_of() -> None:
    artifact = build()
    tampered = deepcopy(artifact)
    event_id = next(
        item["event_id"]
        for item in tampered["anchors"]
        if item["anchor_type"] == "event_post"
    )
    for anchor in tampered["anchors"]:
        if anchor["event_id"] != event_id:
            continue
        anchor["effective_at"] = "2026-07-19T00:00:00+00:00"
        anchor["anchor_id"] = (
            "ledger_anchor_"
            + reconstruction_module._content_id(
                {
                    "episode_id": tampered["episode_id"],
                    "anchor_type": anchor["anchor_type"],
                    "event_id": anchor["event_id"],
                    "effective_at": anchor["effective_at"],
                }
            )[7:39]
        )
    rehash(tampered)

    assert validate_ledger_snapshot_reconstruction(tampered)[
        "validation_status"
    ] == "blocked"
