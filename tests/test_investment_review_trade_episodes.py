from __future__ import annotations

import hashlib
import json
import random
import sqlite3
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.investment_review.cli import main as review_main
from src.investment_review.episodes import (
    COLLECTION_SCHEMA_VERSION,
    build_episode_collection,
    load_episode_collection,
    load_p2b_snapshot_references,
    query_episode_collection,
    save_episode_collection,
    validate_episode,
    validate_episode_collection,
)
from src.investment_review.models import CanonicalTradeEvent, DecisionRecord, SourceDefinition
from src.investment_review.store import ReviewStore


UTC = timezone.utc
BASE = datetime(2026, 7, 1, 1, 35, 10, tzinfo=UTC)
CUTOFF = datetime(2026, 7, 10, 8, 0, 0, tzinfo=UTC)


def event(
    event_id: str,
    *,
    at: datetime = BASE,
    known_at: datetime | None = None,
    account: str = "acct-1",
    symbol: str = "600000.SH",
    market: str | None = None,
    side: str = "BUY",
    quantity: str = "100",
    event_type: str = "fill",
    sequence: int = 1,
    decisions: list[dict] | None = None,
    known_at_fallback: bool = False,
) -> dict:
    known = known_at or at
    return {
        "event_id": event_id,
        "source_id": "src-fixture",
        "source_record_id": f"{account}::{event_id}",
        "payload_sha256": hashlib.sha256(event_id.encode()).hexdigest(),
        "event_type": event_type,
        "occurred_at": at.isoformat(),
        "known_at": known.isoformat(),
        "account": account,
        "market": market,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "currency": "CNY",
        "raw_payload": {
            "known_at_fallback": known_at_fallback,
            "source_row": {
                "account_id": account,
                "external_id": event_id,
                "dedupe_key": f"dk-{event_id}",
                "entry_id": sequence,
                "created_at": known.isoformat(),
            },
        },
        "decision_refs": decisions or [],
    }


def snapshot(
    snapshot_id: str,
    *,
    as_of: str,
    cutoff: datetime | None,
    included: list[str] | None = None,
    account: str = "acct-1",
    instruments: list[str] | None = None,
    revision: int = 1,
    cursor_scope: str = "partition",
    included_event_set_complete: bool = False,
) -> dict:
    return {
        "snapshot_id": snapshot_id,
        "account_id": account,
        "as_of_date": as_of,
        "knowledge_cutoff_at": cutoff.isoformat() if cutoff else None,
        "revision": revision,
        "engine_version": "portfolio-snapshot-v1",
        "source_state_hash": hashlib.sha256(snapshot_id.encode()).hexdigest(),
        "source_path": "fixture.sqlite3",
        "instrument_ids": instruments or [],
        "included_event_ids": included or [],
        "cursor_scope": cursor_scope,
        "included_event_set_complete": included_event_set_complete,
    }


def build(events: list[dict], snapshots: list[dict] | None = None) -> dict:
    return build_episode_collection(
        events,
        cutoff_at=CUTOFF.isoformat(),
        snapshot_references=snapshots or [],
    )


def codes(validation: dict) -> set[str]:
    return {item["code"] for item in validation["findings"]}


def test_closed_open_partial_fill_and_quantity_paths() -> None:
    events = [
        event("e1", quantity="40", sequence=1),
        event("e2", at=BASE + timedelta(minutes=1), quantity="60", sequence=2),
        event("e3", at=BASE + timedelta(days=1), side="BUY", quantity="50", sequence=3),
        event("e4", at=BASE + timedelta(days=2), side="SELL", quantity="90", sequence=4),
        event("e5", at=BASE + timedelta(days=3), side="SELL", quantity="60", sequence=5),
        event("open-1", account="acct-2", symbol="000001.SZ", quantity="25"),
    ]
    result = build(events)
    assert [item["status"] for item in result["episodes"]] == ["closed", "open"]
    closed = result["episodes"][0]
    assert closed["ending_quantity"] == "0"
    assert closed["maximum_absolute_quantity"] == "150"
    assert closed["material_transition_count"] == 5
    assert [item["quantity_after"] for item in closed["event_refs"]] == ["40", "100", "150", "60", "0"]
    assert closed["lineage"]["canonical_content_digest"]
    assert result["validation"]["coverage"]["consumed_once"] == 6
    assert result["validation"]["coverage"]["unassigned"] == 0


def test_reentry_creates_distinct_stable_episode_ids() -> None:
    events = [
        event("e1"),
        event("e2", at=BASE + timedelta(hours=1), side="SELL"),
        event("e3", at=BASE + timedelta(hours=2), quantity="20", sequence=3),
        event("e4", at=BASE + timedelta(hours=3), side="SELL", quantity="20", sequence=4),
    ]
    first = build(events)
    second = build(list(reversed(events)))
    assert len(first["episodes"]) == 2
    assert first["episodes"][0]["episode_id"] != first["episodes"][1]["episode_id"]
    assert first["collection_digest"] == second["collection_digest"]


def test_collection_rejects_duplicate_episode_identity_after_rehash() -> None:
    result = build(
        [
            event("e1", account="acct-a", symbol="600000.SH"),
            event("e2", account="acct-b", symbol="000001.SZ"),
        ]
    )
    assert len(result["episodes"]) == 2
    result["episodes"][1]["episode_id"] = result["episodes"][0]["episode_id"]
    material = deepcopy(result)
    material.pop("validation", None)
    material["collection_digest"] = ""
    result["collection_digest"] = hashlib.sha256(
        json.dumps(
            material,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    validation = validate_episode_collection(result)
    assert validation["validation_status"] == "blocked"
    assert "DUPLICATE_EPISODE_IDENTITY" in codes(validation)


def test_partitioning_is_explicit_by_account_and_instrument() -> None:
    result = build(
        [
            event("a1", account="acct-a", symbol="600000.SH"),
            event("a2", account="acct-b", symbol="600000.SH"),
            event("a3", account="acct-a", symbol="000001.SZ"),
        ]
    )
    scopes = {
        (item["scope"]["account_id"], item["scope"]["instrument_id"])
        for item in result["episodes"]
    }
    assert scopes == {
        ("acct-a", "600000.SH"),
        ("acct-b", "600000.SH"),
        ("acct-a", "000001.SZ"),
    }


def test_shuffle_rerun_and_equal_timestamp_order_are_deterministic() -> None:
    events = [
        event("e3", sequence=3, quantity="30"),
        event("e1", sequence=1, quantity="10"),
        event("e2", sequence=2, quantity="20"),
        event("e4", at=BASE + timedelta(minutes=1), side="SELL", quantity="60", sequence=4),
    ]
    baseline = build(events)
    for seed in range(8):
        shuffled = list(events)
        random.Random(seed).shuffle(shuffled)
        candidate = build(shuffled)
        assert candidate["collection_digest"] == baseline["collection_digest"]
        assert [item["event_id"] for item in candidate["episodes"][0]["event_refs"]] == ["e1", "e2", "e3", "e4"]


def test_exact_duplicate_is_deduplicated_and_conflict_blocks() -> None:
    original = event("e1")
    duplicate = build([original, deepcopy(original)])
    assert duplicate["episodes"][0]["material_transition_count"] == 1
    assert duplicate["consumption_ledger"][0]["input_occurrences"] == 2
    assert "EXACT_DUPLICATE_EVENT" in codes(duplicate["validation"])

    conflicting = deepcopy(original)
    conflicting["quantity"] = "200"
    result = build([original, conflicting])
    assert result["episodes"] == []
    assert result["validation"]["validation_status"] == "blocked"
    assert "CONFLICTING_DUPLICATE_EVENT" in codes(result["validation"])


def test_typed_adjustments_and_non_position_events_remain_visible() -> None:
    events = [
        event("cash", event_type="dividend", side="OTHER", quantity="0", sequence=1),
        event("opening", event_type="opening", side="BUY", quantity="80", sequence=2),
        event("correction", at=BASE + timedelta(minutes=1), event_type="correction", side="BUY", quantity="20", sequence=3),
        event("transfer", at=BASE + timedelta(minutes=2), event_type="transfer", side="TRANSFER_OUT", quantity="10", sequence=4),
        event("corp", account="acct-2", symbol="000001.SZ", event_type="corporate_action", side="TRANSFER_IN", quantity="5"),
    ]
    result = build(events)
    assert result["episodes"][0]["status"] == "data_gap"
    assert result["episodes"][1]["status"] == "data_gap"
    assert any(item["outcome"] == "non_position_changing" for item in result["consumption_ledger"])
    assert "TYPED_QUANTITY_ADJUSTMENT" in codes(result["episodes"][0]["validation"])
    assert "OPENING_BALANCE_INCOMPLETE_HISTORY" in codes(result["episodes"][0]["validation"])


def test_unsplit_reversal_blocks_without_silent_event_loss() -> None:
    events = [
        event("e1", quantity="100"),
        event("reverse", at=BASE + timedelta(minutes=1), side="SELL", quantity="150", sequence=2),
        event("later", at=BASE + timedelta(minutes=2), side="BUY", quantity="50", sequence=3),
    ]
    result = build(events)
    episode = result["episodes"][0]
    assert episode["status"] == "ambiguous"
    assert "UNSPLIT_SIGN_REVERSAL" in codes(episode["validation"])
    ledger = {item["event_id"]: item for item in result["consumption_ledger"]}
    assert ledger["reverse"]["outcome"] == "consumed"
    assert ledger["later"]["outcome"] == "blocked_after_ambiguous_boundary"
    assert result["validation"]["validation_status"] == "blocked"


def test_invalid_naive_missing_identity_and_cutoff_inputs_are_preserved() -> None:
    naive = event("naive")
    naive["occurred_at"] = "2026-07-01T09:35:10"
    missing = event("missing")
    missing["account"] = ""
    future = event("future", at=CUTOFF + timedelta(days=1))
    late_known = event("late-known", at=CUTOFF - timedelta(days=1), known_at=CUTOFF + timedelta(hours=1))
    result = build([naive, missing, future, late_known])
    ledger = {item["event_id"]: item for item in result["consumption_ledger"]}
    assert ledger["naive"]["outcome"] == "rejected_invalid"
    assert ledger["missing"]["outcome"] == "rejected_invalid"
    assert ledger["future"]["outcome"] == "excluded_after_cutoff"
    assert ledger["late-known"]["outcome"] == "excluded_not_known_at_cutoff"
    assert result["validation"]["temporal_checks"]["naive_timestamps"] >= 1


def test_snapshot_linkage_exact_fallback_missing_and_future_safe() -> None:
    open_event = event("e1")
    close_event = event("e2", at=BASE + timedelta(days=1), side="SELL", sequence=2)
    snapshots = [
        snapshot("before", as_of="2026-06-30", cutoff=BASE - timedelta(minutes=5)),
        snapshot(
            "after-open",
            as_of="2026-07-01",
            cutoff=BASE,
            included=["e1"],
            instruments=["600000.SH"],
        ),
        snapshot(
            "future-only",
            as_of="2026-07-02",
            cutoff=CUTOFF + timedelta(days=1),
            included=["e1", "e2"],
            instruments=["600000.SH"],
        ),
    ]
    result = build([open_event, close_event], snapshots)
    links = result["episodes"][0]["snapshot_links"]
    assert any(item["link_role"] == "before_open" and item["link_method"] == "latest_at_or_before" for item in links)
    assert any(item["link_role"] == "after_open" and item["link_method"] == "exact_event_cursor" for item in links)
    assert any(item["link_role"] == "after_close" and item["link_method"] == "missing" for item in links)
    assert all(item.get("snapshot_ref") != "future-only" for item in links)


def decision(decision_id: str, event_id: str, *, known_at: datetime, symbol: str = "600000.SH") -> dict:
    return {
        "decision_id": decision_id,
        "event_id": event_id,
        "relation": "execution",
        "symbol": symbol,
        "market": None,
        "occurred_at": (known_at - timedelta(minutes=1)).isoformat(),
        "known_at": known_at.isoformat(),
        "status": "OPEN",
        "link_source": "decision_event_links",
    }


def test_decision_links_are_explicit_temporal_and_unambiguous() -> None:
    linked = build([event("e1", decisions=[decision("d1", "e1", known_at=BASE - timedelta(minutes=1))])])
    linked_evidence = linked["episodes"][0]["decision_linkage"]
    assert linked_evidence["status"] == "linked"
    assert linked_evidence["decision_refs"] == ["d1"]
    assert linked_evidence["decision_links"] == [
        {
            "decision_id": "d1",
            "container_event_id": "e1",
            "event_id": "e1",
            "relation": "execution",
            "effective_at": (BASE - timedelta(minutes=2)).isoformat(
                timespec="seconds"
            ),
            "known_at": (BASE - timedelta(minutes=1)).isoformat(
                timespec="seconds"
            ),
            "symbol": "600000.SH",
            "market": None,
            "status": "OPEN",
            "link_source": "decision_event_links",
        }
    ]

    unlinked = build([event("e1")])
    assert unlinked["episodes"][0]["decision_linkage"]["status"] == "unlinked"

    ambiguous = build(
        [
            event(
                "e1",
                decisions=[
                    decision("d1", "e1", known_at=BASE - timedelta(minutes=2)),
                    decision("d2", "e1", known_at=BASE - timedelta(minutes=1)),
                ],
            )
        ]
    )
    assert ambiguous["episodes"][0]["decision_linkage"]["status"] == "ambiguous"
    assert ambiguous["validation"]["validation_status"] == "blocked"

    invalid = build([event("e1", decisions=[decision("d1", "e1", known_at=BASE + timedelta(minutes=1))])])
    assert invalid["episodes"][0]["decision_linkage"]["status"] == "invalid"
    assert "DECISION_LINK_INVALID" in codes(invalid["episodes"][0]["validation"])


def test_one_decision_can_cover_multiple_execution_events() -> None:
    shared_known_at = BASE - timedelta(minutes=1)
    result = build(
        [
            event(
                "e1",
                decisions=[decision("d-shared", "e1", known_at=shared_known_at)],
            ),
            event(
                "e2",
                at=BASE + timedelta(minutes=1),
                side="SELL",
                sequence=2,
                decisions=[decision("d-shared", "e2", known_at=shared_known_at)],
            ),
        ]
    )
    linkage = result["episodes"][0]["decision_linkage"]
    assert linkage["status"] == "linked"
    assert linkage["decision_refs"] == ["d-shared"]
    assert [item["event_id"] for item in linkage["decision_links"]] == ["e1", "e2"]
    assert "DECISION_LINK_AMBIGUOUS" not in codes(result["validation"])
    assert "DECISION_LINK_STATUS_MISMATCH" not in codes(result["validation"])


@pytest.mark.parametrize("missing_field", ["decision_id", "event_id", "link_source"])
def test_malformed_explicit_decision_link_is_not_downgraded_to_unlinked(
    missing_field: str,
) -> None:
    raw = decision("d1", "e1", known_at=BASE - timedelta(minutes=1))
    raw.pop(missing_field)
    result = build([event("e1", decisions=[raw])])
    linkage = result["episodes"][0]["decision_linkage"]
    assert linkage["status"] == "invalid"
    assert "DECISION_LINK_INVALID" in codes(result["validation"])


def test_decision_link_rejects_forged_status_and_conflicting_time_alias() -> None:
    forged_status = decision("d1", "e1", known_at=BASE - timedelta(minutes=1))
    forged_status["status"] = "FORGED"
    invalid = build([event("e1", decisions=[forged_status])])
    assert invalid["episodes"][0]["decision_linkage"]["status"] == "invalid"

    conflicting_time = decision(
        "d2", "e1", known_at=BASE - timedelta(minutes=1)
    )
    conflicting_time["effective_at"] = (BASE - timedelta(hours=1)).isoformat()
    conflict = build([event("e1", decisions=[conflicting_time])])
    assert conflict["episodes"][0]["decision_linkage"]["status"] == "invalid"
    assert "DECISION_LINK_INVALID" in codes(conflict["validation"])


def test_numeric_event_sequence_is_validated_structurally_not_lexically() -> None:
    result = build(
        [
            event("e10", quantity="10", sequence=10),
            event("e2", quantity="10", sequence=2),
        ]
    )
    episode = result["episodes"][0]
    assert [int(item["ordering_key"][2]) for item in episode["event_refs"]] == [2, 10]
    assert "NON_CANONICAL_EVENT_ORDER" not in codes(
        validate_episode(episode)
    )

    numeric_rank_episode = deepcopy(episode)
    numeric_rank_episode["event_refs"][0]["ordering_key"][1] = 2
    numeric_rank_episode["event_refs"][1]["ordering_key"][1] = 10
    assert "NON_CANONICAL_EVENT_ORDER" not in codes(
        validate_episode(numeric_rank_episode)
    )


def test_validator_requires_canonical_decision_link_evidence() -> None:
    collection = build(
        [
            event(
                "e1",
                decisions=[
                    decision("d1", "e1", known_at=BASE - timedelta(minutes=1))
                ],
            )
        ]
    )
    episode = deepcopy(collection["episodes"][0])
    episode["decision_linkage"].pop("decision_links")
    validation = validate_episode(episode)
    assert validation["validation_status"] == "blocked"
    assert "MALFORMED_DECISION_LINKAGE" in codes(validation)
    assert "DECISION_LINK_CLOSURE_MISMATCH" in codes(validation)


def test_decision_link_cannot_move_to_another_event_or_relation() -> None:
    moved = decision(
        "d1", "e2", known_at=BASE - timedelta(minutes=1)
    )
    moved["relation"] = "forged_relation"
    collection = build(
        [
            event("e1", decisions=[moved]),
            event(
                "e2",
                at=BASE + timedelta(minutes=1),
                side="SELL",
                sequence=2,
            ),
        ]
    )
    linkage = collection["episodes"][0]["decision_linkage"]
    assert linkage["status"] == "invalid"
    assert linkage["decision_links"][0]["container_event_id"] == "e1"
    assert linkage["decision_links"][0]["event_id"] == "e2"
    assert "DECISION_LINK_INVALID" in codes(collection["validation"])


def test_validator_blocks_tampered_contracts() -> None:
    closed = build([event("e1"), event("e2", at=BASE + timedelta(minutes=1), side="SELL", sequence=2)])["episodes"][0]
    mutations = []

    unsupported = deepcopy(closed)
    unsupported["schema_version"] = "portfolio.trade_episode.v999"
    mutations.append((unsupported, "UNSUPPORTED_EPISODE_SCHEMA"))

    duplicate = deepcopy(closed)
    duplicate["event_refs"].append(deepcopy(duplicate["event_refs"][0]))
    mutations.append((duplicate, "DUPLICATE_EVENT_CONSUMPTION"))

    bad_boundary = deepcopy(closed)
    bad_boundary["closed_at"] = (BASE - timedelta(minutes=1)).isoformat()
    mutations.append((bad_boundary, "INVALID_EPISODE_BOUNDARY"))

    open_zero = deepcopy(closed)
    open_zero["status"] = "open"
    open_zero["closed_at"] = None
    mutations.append((open_zero, "INVALID_OPEN_STATUS"))

    nonzero_closed = deepcopy(closed)
    nonzero_closed["ending_quantity"] = "1"
    mutations.append((nonzero_closed, "INVALID_CLOSED_STATUS"))

    bad_cutoff = deepcopy(closed)
    bad_cutoff["cutoff_at"] = (BASE - timedelta(minutes=1)).isoformat()
    mutations.append((bad_cutoff, "CUTOFF_BEFORE_LAST_EVENT"))

    missing_lineage = deepcopy(closed)
    missing_lineage["event_refs"][0]["source_refs"] = {}
    mutations.append((missing_lineage, "MISSING_SOURCE_LINEAGE"))

    for payload, expected_code in mutations:
        assert expected_code in codes(validate_episode(payload))

    collection = build([event("e1")])
    collection["schema_version"] = "bad"
    assert "UNSUPPORTED_COLLECTION_SCHEMA" in codes(validate_episode_collection(collection))


def test_validator_rejects_snapshot_scope_and_future_tampering() -> None:
    result = build(
        [event("e1")],
        [
            snapshot(
                "after-open",
                as_of="2026-07-01",
                cutoff=BASE,
                included=["e1"],
                instruments=["600000.SH"],
            )
        ],
    )
    episode = deepcopy(result["episodes"][0])
    catalog = deepcopy(result["snapshot_catalog"])
    catalog[0]["account_id"] = "wrong-account"
    catalog[0]["instrument_ids"] = ["000001.SZ"]
    after_link = next(item for item in episode["snapshot_links"] if item["link_role"] == "after_open")
    after_link["snapshot_knowledge_cutoff_at"] = (BASE + timedelta(days=1)).isoformat()
    validation = validate_episode(episode, snapshot_catalog=catalog)
    assert "SNAPSHOT_ACCOUNT_MISMATCH" in codes(validation)
    assert "SNAPSHOT_INSTRUMENT_MISMATCH" in codes(validation)

    before_link = next(item for item in episode["snapshot_links"] if item["link_role"] == "before_open")
    before_link.update(
        {
            "snapshot_ref": "after-open",
            "link_method": "latest_at_or_before",
            "snapshot_knowledge_cutoff_at": (BASE + timedelta(minutes=1)).isoformat(),
        }
    )
    catalog[0]["knowledge_cutoff_at"] = (BASE + timedelta(minutes=1)).isoformat()
    assert "FUTURE_SNAPSHOT_LINK" in codes(validate_episode(episode, snapshot_catalog=catalog))


def test_snapshot_links_require_exact_catalog_time_and_role_set_closure() -> None:
    result = build(
        [event("e1")],
        [
            snapshot(
                "after-open",
                as_of="2026-07-01",
                cutoff=BASE,
                included=["e1"],
                instruments=["600000.SH"],
            )
        ],
    )
    episode = deepcopy(result["episodes"][0])
    catalog = deepcopy(result["snapshot_catalog"])
    linked = next(
        item for item in episode["snapshot_links"] if item["snapshot_ref"]
    )
    linked["snapshot_as_of"] = "2026-07-02"
    validation = validate_episode(episode, snapshot_catalog=catalog)
    assert "SNAPSHOT_LINK_CLOSURE_MISMATCH" in codes(validation)

    removed = deepcopy(result["episodes"][0])
    removed["snapshot_links"] = [
        item for item in removed["snapshot_links"] if item["link_role"] != "after_open"
    ]
    validation = validate_episode(removed, snapshot_catalog=catalog)
    assert "SNAPSHOT_LINK_SET_MISMATCH" in codes(validation)


@pytest.mark.parametrize(
    "payload",
    [
        {"ending_quantity": {"bad": 1}},
        {"event_refs": "bad"},
        {"snapshot_links": "bad"},
    ],
)
def test_episode_validator_is_total_for_malformed_json(payload: dict) -> None:
    validation = validate_episode(payload)
    assert validation["validation_status"] == "blocked"
    assert validation["findings"]


def test_snapshot_cursor_proof_is_preserved_and_invalid_claims_block() -> None:
    proven = build(
        [event("e1")],
        [
            snapshot(
                "after-open",
                as_of="2026-07-01",
                cutoff=BASE,
                included=["e1"],
                instruments=["600000.SH"],
                cursor_scope="account",
                included_event_set_complete=True,
            )
        ],
    )
    assert proven["snapshot_catalog"][0]["cursor_scope"] == "account"
    assert proven["snapshot_catalog"][0]["included_event_set_complete"] is True

    invalid = build(
        [event("e1")],
        [
            snapshot(
                "bad-proof",
                as_of="2026-07-01",
                cutoff=BASE,
                included=["e1"],
                cursor_scope="partition",
                included_event_set_complete=True,
            )
        ],
    )
    assert invalid["validation"]["validation_status"] == "blocked"
    assert "INVALID_SNAPSHOT_REFERENCE" in codes(invalid["validation"])


def test_artifact_round_trip_query_and_canonical_serialization(tmp_path: Path) -> None:
    result = build(
        [
            event("e1"),
            event("e2", account="acct-2", symbol="000001.SZ"),
        ]
    )
    output = save_episode_collection(tmp_path / "episodes.json", result)
    loaded = load_episode_collection(output)
    assert loaded["collection_digest"] == result["collection_digest"]
    assert validate_episode_collection(loaded)["validation_status"] == "accepted_with_warnings"
    assert len(query_episode_collection(loaded, account="acct-1")) == 1
    assert len(query_episode_collection(loaded, instrument="000001.SZ", status="open")) == 1
    assert len(
        query_episode_collection(
            loaded,
            interval_start=(BASE - timedelta(minutes=1)).isoformat(),
            interval_end=(BASE + timedelta(minutes=1)).isoformat(),
        )
    ) == 2
    reordered = json.loads(json.dumps(loaded, sort_keys=False))
    assert reordered["collection_digest"] == loaded["collection_digest"]


def test_review_store_exposes_only_explicit_projection_links(tmp_path: Path) -> None:
    store = ReviewStore(tmp_path / "review.sqlite3")
    store.initialize()
    source = SourceDefinition(name="fixture", kind="csv", uri="fixture.csv", identity_key="fixture")
    trade = CanonicalTradeEvent.build(
        source_id=source.source_id,
        source_record_id="acct-1::row-1",
        event_type="fill",
        occurred_at=BASE.isoformat(),
        known_at=BASE.isoformat(),
        timezone="UTC",
        account="acct-1",
        symbol="600000.SH",
        side="BUY",
        quantity="100",
        price="10",
        raw_payload={"source_row": {"dedupe_key": "dk-row-1", "entry_id": 1}},
    )
    store.import_events(source, [trade])
    note = DecisionRecord.build(
        symbol="600000.SH",
        occurred_at=(BASE - timedelta(minutes=2)).isoformat(),
        known_at=(BASE - timedelta(minutes=1)).isoformat(),
        thesis="fixture decision",
        timezone="UTC",
    )
    decision_id = store.add_decision(note)
    store.link_decision_event(decision_id, trade.event_id)
    inputs = store.list_episode_projection_inputs(account="acct-1", symbol="600000.SH")
    assert len(inputs) == 1
    assert inputs[0]["decision_refs"][0]["decision_id"] == decision_id
    assert inputs[0]["decision_refs"][0]["link_source"] == "decision_event_links"


def test_p2b_snapshot_reader_is_read_only_and_preserves_lineage(tmp_path: Path) -> None:
    database = tmp_path / "portfolio.sqlite3"
    with sqlite3.connect(database) as conn:
        conn.executescript(
            """
            CREATE TABLE portfolio_snapshots(
                snapshot_id TEXT PRIMARY KEY, account_id TEXT, as_of_date TEXT,
                knowledge_cutoff_at TEXT, revision INTEGER, engine_version TEXT,
                source_state_hash TEXT
            );
            CREATE TABLE position_snapshots(
                snapshot_id TEXT, ts_code TEXT, lineage_json TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO portfolio_snapshots VALUES(?,?,?,?,?,?,?)",
            ("ps-1", "acct-1", "2026-07-01", BASE.isoformat(), 1, "portfolio-snapshot-v1", "hash"),
        )
        conn.execute(
            "INSERT INTO position_snapshots VALUES(?,?,?)",
            (
                "ps-1",
                "600000.SH",
                json.dumps({"transactions": [{"dedupe_key": "dk-e1"}]}, sort_keys=True),
            ),
        )
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    refs = load_p2b_snapshot_references(database, account="acct-1")
    after = hashlib.sha256(database.read_bytes()).hexdigest()
    assert before == after
    assert refs[0]["included_source_keys"] == ["dk-e1"]
    assert refs[0]["instrument_ids"] == ["600000.SH"]


def test_cli_build_query_and_validate_use_local_artifacts(tmp_path: Path, capsys) -> None:
    store = ReviewStore(tmp_path / "review.sqlite3")
    store.initialize()
    source = SourceDefinition(name="fixture", kind="csv", uri="fixture.csv", identity_key="fixture")
    trade = CanonicalTradeEvent.build(
        source_id=source.source_id,
        source_record_id="acct-1::row-1",
        event_type="fill",
        occurred_at=BASE.isoformat(),
        known_at=BASE.isoformat(),
        timezone="UTC",
        account="acct-1",
        symbol="600000.SH",
        side="BUY",
        quantity="100",
        price="10",
        raw_payload={"source_row": {"dedupe_key": "dk-row-1", "entry_id": 1, "created_at": BASE.isoformat()}},
    )
    store.import_events(source, [trade])
    artifact = tmp_path / "episodes.json"
    assert review_main(
        [
            "--db",
            str(store.path),
            "episode-build",
            "--cutoff-at",
            CUTOFF.isoformat(),
            "--account",
            "acct-1",
            "--output",
            str(artifact),
        ]
    ) == 0
    assert artifact.exists()
    capsys.readouterr()
    assert review_main(["episode-query", str(artifact), "--status", "open"]) == 0
    assert "episode_id" in capsys.readouterr().out
    assert review_main(["episode-validate", str(artifact)]) == 0
    assert "accepted_with_warnings" in capsys.readouterr().out


def test_fixture_manifest_covers_the_complete_package_matrix() -> None:
    manifest = json.loads(
        Path("tests/fixtures/investment_review_p2c/scenario_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert {item["id"] for item in manifest["cases"]} == {
        f"T{number:02d}" for number in range(1, 37)
    }


def test_collection_digest_detects_artifact_drift() -> None:
    result = build([event("e1")])
    result["episodes"][0]["ending_quantity"] = "999"
    validation = validate_episode_collection(result)
    assert "COLLECTION_DIGEST_MISMATCH" in codes(validation)


@pytest.mark.parametrize("bad_status", ["buy", "recommend", "unknown"])
def test_query_rejects_non_contract_statuses(bad_status: str) -> None:
    with pytest.raises(ValueError, match="unsupported status"):
        query_episode_collection(build([event("e1")]), status=bad_status)
