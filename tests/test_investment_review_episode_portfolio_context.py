from __future__ import annotations

import hashlib
import json
import random
import sqlite3
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping

import pytest

from src.investment_review.episode_portfolio_context import (
    METRIC_REGISTRY_VERSION,
    SCHEMA_VERSION,
    EpisodePortfolioContextError,
    build_episode_portfolio_context,
    load_episode_portfolio_context,
    query_episode_portfolio_context,
    replay_validate_episode_portfolio_context,
    save_episode_portfolio_context,
    validate_episode_portfolio_context,
    _build_deltas,
    _content_id,
    _stable_id,
)
from src.investment_review.episodes import build_episode_collection
from src.investment_review.cli import main as review_main


UTC = timezone.utc
BASE = datetime(2026, 7, 1, 1, 30, tzinfo=UTC)
CUTOFF = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)


def _event(
    event_id: str,
    *,
    at: datetime = BASE,
    known_at: datetime | None = None,
    side: str = "BUY",
    quantity: str = "100",
    account: str = "acct-1",
    symbol: str = "600000.SH",
    sequence: int | str | None = 1,
    decisions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    known = known_at or at
    source_row: dict[str, Any] = {
        "account_id": account,
        "external_id": event_id,
        "dedupe_key": f"dk-{event_id}",
        "created_at": known.isoformat(),
    }
    if sequence is not None:
        source_row["entry_id"] = sequence
    return {
        "event_id": event_id,
        "source_id": "src-p2e3-fixture",
        "source_record_id": f"{account}::{event_id}",
        "payload_sha256": hashlib.sha256(event_id.encode("utf-8")).hexdigest(),
        "event_type": "fill",
        "occurred_at": at.isoformat(),
        "known_at": known.isoformat(),
        "account": account,
        "market": None,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "currency": "CNY",
        "raw_payload": {"source_row": source_row},
        "decision_refs": decisions or [],
    }


def _decision(
    decision_id: str,
    event_id: str,
    *,
    known_at: datetime,
    symbol: str = "600000.SH",
) -> dict[str, Any]:
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


def _snapshot_ref(
    snapshot_id: str,
    *,
    known_at: datetime,
    included: Iterable[str] = (),
    account: str = "acct-1",
    revision: int = 1,
    symbols: Iterable[str] = ("600000.SH",),
    source_state_hash: str | None = None,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    return {
        "snapshot_id": snapshot_id,
        "account_id": account,
        "as_of_date": as_of_date or known_at.date().isoformat(),
        "knowledge_cutoff_at": known_at.isoformat(),
        "revision": revision,
        "engine_version": "portfolio-snapshot-v1",
        "source_state_hash": source_state_hash
        or hashlib.sha256(snapshot_id.encode("utf-8")).hexdigest(),
        "source_path": "fixture-portfolio.sqlite3",
        "instrument_ids": sorted(symbols),
        "included_event_ids": sorted(included),
    }


def _position(
    *,
    symbol: str = "600000.SH",
    quantity: str = "100",
    price: str | None = "10",
    market_value: str | None = "1000",
    valuation_status: str = "priced",
    staleness_days: int | None = 0,
    industry: str = "银行",
    price_date: str = "2026-06-30",
    price_known_at: datetime | None = BASE - timedelta(hours=2),
    industry_updated_at: datetime | None = BASE - timedelta(days=1),
    industry_point_in_time: bool = True,
) -> dict[str, Any]:
    return {
        "ts_code": symbol,
        "quantity": quantity,
        "average_cost": "10",
        "cost_basis": "1000",
        "price": price,
        "price_date": price_date if price is not None else None,
        "price_source": "fixture.close" if price is not None else None,
        "staleness_days": staleness_days,
        "valuation_status": valuation_status,
        "market_value": market_value,
        "unrealized_pnl": "0" if market_value is not None else None,
        "portfolio_weight": "0.1" if market_value is not None else None,
        "industry_name": industry,
        "industry_source": "fixture.taxonomy" if industry else "",
        "lineage_json": json.dumps(
            {
                "price": (
                    {
                        "trade_date": price_date,
                        "source": "fixture.close",
                        "known_at": price_known_at.isoformat()
                        if price_known_at is not None
                        else None,
                    }
                    if price is not None
                    else None
                ),
                "industry": {
                    "name": industry,
                    "source": "fixture.taxonomy" if industry else "",
                    "updated_at": industry_updated_at.isoformat()
                    if industry_updated_at is not None
                    else None,
                    "point_in_time": industry_point_in_time,
                },
                "transactions": [],
            },
            sort_keys=True,
        ),
    }


def _snapshot(
    snapshot_id: str,
    *,
    known_at: datetime,
    included: Iterable[str] = (),
    revision: int = 1,
    account: str = "acct-1",
    cash: str | None = "9000",
    market_value: str = "1000",
    positions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "snapshot_id": snapshot_id,
        "account_id": account,
        "as_of_date": known_at.date().isoformat(),
        "knowledge_cutoff_at": known_at.isoformat(),
        "calculated_at": known_at.isoformat(),
        "revision": revision,
        "engine_version": "portfolio-snapshot-v1",
        "schema_version": "portfolio.snapshot.v1",
        "source_state_hash": hashlib.sha256(snapshot_id.encode("utf-8")).hexdigest(),
        "currency": "CNY",
        "cost_basis": "1000",
        "market_value": market_value,
        "unrealized_pnl": "0",
        "realized_pnl_to_date": "0",
        "cash_balance": cash,
        "cash_as_of_date": known_at.date().isoformat() if cash is not None else None,
        "cash_source": "fixture.cash" if cash is not None else None,
        "cash_status": "available" if cash is not None else "unavailable",
        "created_from_json": json.dumps(sorted(included)),
        "positions": list(positions if positions is not None else [_position()]),
    }


def _default_snapshots() -> list[dict[str, Any]]:
    return [
        _snapshot(
            "snap-pre-open",
            known_at=BASE - timedelta(minutes=1),
            cash="10000",
            market_value="0",
            positions=[],
        ),
        _snapshot(
            "snap-post-open",
            known_at=BASE + timedelta(minutes=1),
            included=["buy-1"],
        ),
        _snapshot(
            "snap-pre-close",
            known_at=BASE + timedelta(minutes=59),
            included=["buy-1"],
            cash="8900",
            market_value="1100",
            positions=[_position(price="11", market_value="1100")],
        ),
        _snapshot(
            "snap-post-close",
            known_at=BASE + timedelta(minutes=61),
            included=["buy-1", "sell-1"],
            cash="10000",
            market_value="0",
            positions=[],
        ),
    ]


def _create_p2b_db(
    path: Path,
    snapshots: Iterable[Mapping[str, Any]],
    *,
    insertion_seed: int | None = None,
) -> Path:
    rows = [deepcopy(dict(item)) for item in snapshots]
    if insertion_seed is not None:
        random.Random(insertion_seed).shuffle(rows)
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE portfolio_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                as_of_date TEXT NOT NULL,
                knowledge_cutoff_at TEXT NOT NULL,
                calculated_at TEXT NOT NULL,
                revision INTEGER NOT NULL,
                engine_version TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                source_state_hash TEXT NOT NULL,
                currency TEXT NOT NULL,
                cost_basis TEXT NOT NULL,
                market_value TEXT NOT NULL,
                unrealized_pnl TEXT NOT NULL,
                realized_pnl_to_date TEXT NOT NULL,
                cash_balance TEXT,
                cash_as_of_date TEXT,
                cash_source TEXT,
                cash_status TEXT NOT NULL,
                position_count INTEGER NOT NULL,
                priced_position_count INTEGER NOT NULL,
                unpriced_position_count INTEGER NOT NULL,
                valuation_complete INTEGER NOT NULL,
                created_from_json TEXT NOT NULL
            );
            CREATE TABLE position_snapshots (
                snapshot_id TEXT NOT NULL,
                ts_code TEXT NOT NULL,
                quantity TEXT NOT NULL,
                average_cost TEXT,
                cost_basis TEXT NOT NULL,
                price TEXT,
                price_date TEXT,
                price_source TEXT,
                staleness_days INTEGER,
                valuation_status TEXT NOT NULL,
                market_value TEXT,
                unrealized_pnl TEXT,
                portfolio_weight TEXT,
                industry_name TEXT NOT NULL DEFAULT '',
                industry_source TEXT NOT NULL DEFAULT '',
                engine_version TEXT NOT NULL,
                source_state_hash TEXT NOT NULL,
                lineage_json TEXT NOT NULL,
                PRIMARY KEY (snapshot_id, ts_code)
            );
            """
        )
        for snapshot in rows:
            positions = list(snapshot.pop("positions"))
            priced_count = sum(item["valuation_status"] in {"priced", "stale"} for item in positions)
            unpriced_count = sum(item["valuation_status"] == "unpriced" for item in positions)
            connection.execute(
                """
                INSERT INTO portfolio_snapshots (
                    snapshot_id, account_id, as_of_date, knowledge_cutoff_at,
                    calculated_at, revision, engine_version, schema_version,
                    source_state_hash, currency, cost_basis, market_value,
                    unrealized_pnl, realized_pnl_to_date, cash_balance,
                    cash_as_of_date, cash_source, cash_status, position_count,
                    priced_position_count, unpriced_position_count,
                    valuation_complete, created_from_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    snapshot["snapshot_id"],
                    snapshot["account_id"],
                    snapshot["as_of_date"],
                    snapshot["knowledge_cutoff_at"],
                    snapshot["calculated_at"],
                    snapshot["revision"],
                    snapshot["engine_version"],
                    snapshot["schema_version"],
                    snapshot["source_state_hash"],
                    snapshot["currency"],
                    snapshot["cost_basis"],
                    snapshot["market_value"],
                    snapshot["unrealized_pnl"],
                    snapshot["realized_pnl_to_date"],
                    snapshot["cash_balance"],
                    snapshot["cash_as_of_date"],
                    snapshot["cash_source"],
                    snapshot["cash_status"],
                    len(positions),
                    priced_count,
                    unpriced_count,
                    int(unpriced_count == 0),
                    snapshot["created_from_json"],
                ),
            )
            for position in positions:
                connection.execute(
                    """
                    INSERT INTO position_snapshots (
                        snapshot_id, ts_code, quantity, average_cost, cost_basis,
                        price, price_date, price_source, staleness_days,
                        valuation_status, market_value, unrealized_pnl,
                        portfolio_weight, industry_name, industry_source,
                        engine_version, source_state_hash, lineage_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        snapshot["snapshot_id"],
                        position["ts_code"],
                        position["quantity"],
                        position["average_cost"],
                        position["cost_basis"],
                        position["price"],
                        position["price_date"],
                        position["price_source"],
                        position["staleness_days"],
                        position["valuation_status"],
                        position["market_value"],
                        position["unrealized_pnl"],
                        position["portfolio_weight"],
                        position["industry_name"],
                        position["industry_source"],
                        snapshot["engine_version"],
                        snapshot["source_state_hash"],
                        position["lineage_json"],
                    ),
                )
        connection.commit()
    finally:
        connection.close()
    return path


def _collection(
    events: Iterable[Mapping[str, Any]] | None = None,
    snapshots: Iterable[Mapping[str, Any]] | None = None,
    *,
    cutoff: datetime = CUTOFF,
) -> dict[str, Any]:
    event_rows = list(
        events
        if events is not None
        else [
            _event("buy-1"),
            _event(
                "sell-1",
                at=BASE + timedelta(hours=1),
                side="SELL",
                sequence=2,
            ),
        ]
    )
    snapshot_rows = list(
        snapshots
        if snapshots is not None
        else (_snapshot_ref_from_row(item) for item in _default_snapshots())
    )
    return build_episode_collection(
        event_rows,
        cutoff_at=cutoff.isoformat(),
        snapshot_references=snapshot_rows,
    )


def _snapshot_ref_from_row(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    included = json.loads(str(snapshot["created_from_json"]))
    return _snapshot_ref(
        str(snapshot["snapshot_id"]),
        known_at=datetime.fromisoformat(str(snapshot["knowledge_cutoff_at"])),
        included=included,
        account=str(snapshot["account_id"]),
        revision=int(snapshot["revision"]),
        symbols=[item["ts_code"] for item in snapshot["positions"]],
        source_state_hash=str(snapshot["source_state_hash"]),
        as_of_date=str(snapshot["as_of_date"]),
    )


def _build(
    collection: Mapping[str, Any],
    db: Path,
    *,
    as_of: datetime = CUTOFF,
    knowledge_cutoff: datetime = CUTOFF,
    episode_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    return build_episode_portfolio_context(
        collection,
        portfolio_db=db,
        as_of=as_of.isoformat(),
        knowledge_cutoff=knowledge_cutoff.isoformat(),
        episode_ids=episode_ids,
    )


def _codes(artifact: Mapping[str, Any]) -> set[str]:
    codes = {str(item["code"]) for item in artifact.get("warnings", [])}
    for context in artifact.get("contexts", []):
        codes.update(str(item["code"]) for item in context.get("warnings", []))
        for metric in context.get("metrics", {}).values():
            codes.update(str(item) for item in metric.get("warning_codes", []))
    return codes


def _available_metrics(artifact: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        metric
        for context in artifact["contexts"]
        for metric in context["metrics"].values()
        if metric["availability"] in {"available", "partial"}
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rehash(artifact: dict[str, Any]) -> dict[str, Any]:
    artifact["content_id"] = _content_id(artifact)
    return artifact


def _rehash_collection(collection: dict[str, Any]) -> dict[str, Any]:
    material = deepcopy(collection)
    material.pop("validation", None)
    material["collection_digest"] = ""
    collection["collection_digest"] = hashlib.sha256(
        json.dumps(
            material,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return collection


@pytest.fixture
def closed_collection() -> dict[str, Any]:
    return _collection()


@pytest.fixture
def portfolio_db(tmp_path: Path) -> Path:
    return _create_p2b_db(tmp_path / "portfolio.sqlite3", _default_snapshots())


@pytest.fixture
def artifact(closed_collection: dict[str, Any], portfolio_db: Path) -> dict[str, Any]:
    return _build(closed_collection, portfolio_db)


def test_minimal_artifact_matches_public_contract(artifact: dict[str, Any]) -> None:
    assert artifact["schema_version"] == SCHEMA_VERSION
    assert artifact["metric_registry_version"] == METRIC_REGISTRY_VERSION
    assert artifact["content_id"].startswith("sha256:")
    assert len(artifact["content_id"]) == 71
    assert artifact["episode_artifact_ref"]["schema_version"]
    assert artifact["contexts"]
    assert isinstance(artifact["deltas"], list)
    validation = validate_episode_portfolio_context(artifact)
    assert validation["schema_version"] == "p2e3.trade_episode_portfolio_context.validation.v1"
    assert validation["validation_status"] in {"accepted", "accepted_with_warnings"}


@pytest.mark.parametrize("bad_value", [0.25, "NaN", "Infinity", "01"])
def test_validator_rejects_float_and_noncanonical_decimal_values(
    artifact: dict[str, Any], bad_value: object
) -> None:
    mutated = deepcopy(artifact)
    metric = next(
        item
        for context in mutated["contexts"]
        for item in context["metrics"].values()
        if item["value"] is not None
    )
    metric["value"] = bad_value
    assert validate_episode_portfolio_context(mutated)["validation_status"] == "blocked"


def test_build_is_byte_and_content_id_deterministic(
    closed_collection: dict[str, Any], portfolio_db: Path
) -> None:
    first = _build(closed_collection, portfolio_db)
    second = _build(deepcopy(closed_collection), portfolio_db)
    assert first == second
    assert json.dumps(first, sort_keys=True, separators=(",", ":")) == json.dumps(
        second, sort_keys=True, separators=(",", ":")
    )
    assert first["content_id"] == second["content_id"]


def test_shuffled_event_snapshot_and_episode_inputs_have_same_hash(tmp_path: Path) -> None:
    events = [
        _event("buy-1"),
        _event("sell-1", at=BASE + timedelta(hours=1), side="SELL", sequence=2),
        _event("buy-2", at=BASE + timedelta(hours=2), sequence=3),
    ]
    snapshots = _default_snapshots()
    first_collection = _collection(events, [_snapshot_ref_from_row(row) for row in snapshots])
    second_collection = _collection(
        list(reversed(events)),
        list(reversed([_snapshot_ref_from_row(row) for row in snapshots])),
    )
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", snapshots)
    assert _build(first_collection, db) == _build(second_collection, db)


def test_wall_clock_is_not_part_of_content_identity(
    closed_collection: dict[str, Any], portfolio_db: Path
) -> None:
    first = _build(closed_collection, portfolio_db)
    second = _build(closed_collection, portfolio_db)
    assert "generated_at" not in first
    assert first["content_id"] == second["content_id"]


def test_future_snapshot_revision_is_not_consumed(tmp_path: Path) -> None:
    snapshots = _default_snapshots()
    future = _snapshot(
        "snap-future-revision",
        known_at=CUTOFF + timedelta(minutes=1),
        included=["buy-1", "sell-1"],
        revision=99,
        cash="1",
        market_value="999999",
    )
    all_rows = [*snapshots, future]
    collection = _collection(
        snapshots=[_snapshot_ref_from_row(row) for row in all_rows]
    )
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", all_rows)
    result = _build(collection, db)
    assert all(
        context["portfolio_snapshot"]["snapshot_id"] != "snap-future-revision"
        for context in result["contexts"]
    )
    assert "snap-future-revision" not in json.dumps(result, ensure_ascii=False)


def test_event_unknown_at_requested_cutoff_is_excluded(tmp_path: Path) -> None:
    event = _event(
        "future-known",
        at=BASE,
        known_at=BASE + timedelta(hours=1),
    )
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", [])
    result = _build(
        _collection([event], snapshots=[]),
        db,
        as_of=BASE + timedelta(hours=2),
        knowledge_cutoff=BASE + timedelta(minutes=30),
    )
    assert result["contexts"] == []
    assert "EVENTS_EXCLUDED_BY_CUTOFF" in _codes(result)


def test_future_known_cross_partition_state_cannot_leak_into_visible_context(
    tmp_path: Path,
) -> None:
    visible = _event(
        "a-visible",
        at=BASE,
        known_at=BASE,
        symbol="600000.SH",
        sequence=1,
    )
    future_known = _event(
        "b-future-known",
        at=BASE + timedelta(minutes=1),
        known_at=BASE + timedelta(hours=1),
        symbol="000001.SZ",
        sequence=2,
    )
    contaminated = _snapshot(
        "snap-cross-partition",
        known_at=BASE + timedelta(minutes=2),
        included=["a-visible", "b-future-known"],
        cash="7000",
        market_value="3000",
        positions=[
            _position(symbol="600000.SH", quantity="100", market_value="1000"),
            _position(symbol="000001.SZ", quantity="200", market_value="2000"),
        ],
    )
    collection = _collection(
        [visible, future_known],
        [_snapshot_ref_from_row(contaminated)],
        cutoff=BASE + timedelta(hours=2),
    )
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", [contaminated])
    result = _build(
        collection,
        db,
        as_of=BASE + timedelta(minutes=30),
        knowledge_cutoff=BASE + timedelta(minutes=30),
    )
    assert {
        context["anchor"]["event_id"] for context in result["contexts"]
    } == {"a-visible"}
    post = next(
        context
        for context in result["contexts"]
        if context["anchor"]["side"] == "post"
    )
    assert post["portfolio_snapshot"]["status"] == "ambiguous"
    assert post["metrics"] == {}
    assert "EVENT_CURSOR_AMBIGUOUS" in _codes(result)


def test_unknown_event_identity_in_snapshot_cursor_is_ambiguous(tmp_path: Path) -> None:
    rows = _default_snapshots()
    rows[1]["created_from_json"] = json.dumps(["buy-1", "unknown-event"])
    collection = _collection(
        snapshots=[_snapshot_ref_from_row(row) for row in rows]
    )
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", rows)
    result = _build(collection, db)
    post = next(
        context
        for context in result["contexts"]
        if context["anchor"]["event_id"] == "buy-1"
        and context["anchor"]["side"] == "post"
    )
    assert post["portfolio_snapshot"]["status"] == "ambiguous"
    assert post["metrics"] == {}
    assert "EVENT_CURSOR_AMBIGUOUS" in _codes(result)


def test_future_price_is_not_backfilled_into_earlier_anchor(tmp_path: Path) -> None:
    snapshots = _default_snapshots()
    snapshots[1]["positions"] = [
        _position(price="99", market_value="9900", price_date="2026-07-02")
    ]
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", snapshots)
    result = _build(_collection(), db)
    post_open = next(
        item
        for item in result["contexts"]
        if item["anchor"]["event_id"] == "buy-1" and item["anchor"]["side"] == "post"
    )
    assert "99" not in {metric["value"] for metric in post_open["metrics"].values()}
    assert any(code in _codes(result) for code in {"FUTURE_PRICE", "PRICE_NOT_VISIBLE", "UNPRICED"})


def test_same_day_close_is_not_used_before_shanghai_market_close(tmp_path: Path) -> None:
    snapshots = _default_snapshots()
    snapshots[1]["positions"] = [
        _position(
            price="99",
            market_value="9900",
            price_date="2026-07-01",
            price_known_at=BASE - timedelta(minutes=1),
        )
    ]
    snapshots[1]["market_value"] = "9900"
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", snapshots)
    result = _build(_collection(), db)
    post = next(
        item
        for item in result["contexts"]
        if item["anchor"]["event_id"] == "buy-1"
        and item["anchor"]["side"] == "post"
    )
    assert post["portfolio_snapshot"]["status"] == "invalid"
    assert post["metrics"] == {}
    assert "PRICE_NOT_VISIBLE" in _codes(result)


def test_price_without_knowledge_lineage_is_withheld(tmp_path: Path) -> None:
    snapshots = _default_snapshots()
    snapshots[1]["positions"] = [
        _position(price_known_at=None)
    ]
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", snapshots)
    result = _build(_collection(), db)
    assert "PRICE_NOT_VISIBLE" in _codes(result)


def test_future_classification_is_not_used_for_historical_context(tmp_path: Path) -> None:
    snapshots = _default_snapshots()
    for snapshot in snapshots[:3]:
        snapshot["positions"] = [
            _position(industry="", market_value="1000", price="10")
        ] if snapshot["positions"] else []
    future = _snapshot(
        "snap-future-classification",
        known_at=CUTOFF + timedelta(hours=1),
        included=["buy-1", "sell-1"],
        positions=[_position(industry="银行")],
    )
    rows = [*snapshots, future]
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", rows)
    result = _build(
        _collection(snapshots=[_snapshot_ref_from_row(row) for row in rows]), db
    )
    assert "snap-future-classification" not in json.dumps(result, ensure_ascii=False)
    assert any(
        code in _codes(result)
        for code in {"UNCLASSIFIED_INDUSTRY", "MISSING_CLASSIFICATION", "INDUSTRY_PARTIAL"}
    )


def test_each_material_event_has_pre_and_post_anchors(artifact: dict[str, Any]) -> None:
    pairs = {
        (context["anchor"]["event_id"], context["anchor"]["side"])
        for context in artifact["contexts"]
    }
    assert pairs == {
        ("buy-1", "pre"),
        ("buy-1", "post"),
        ("sell-1", "pre"),
        ("sell-1", "post"),
    }
    kinds = {
        (context["anchor"]["event_id"], context["anchor"]["kind"])
        for context in artifact["contexts"]
    }
    assert ("buy-1", "episode_open") in kinds
    assert ("sell-1", "episode_close") in kinds


def test_pre_excludes_and_post_includes_current_event(artifact: dict[str, Any]) -> None:
    contexts = {
        (item["anchor"]["event_id"], item["anchor"]["side"]): item
        for item in artifact["contexts"]
    }
    assert contexts[("buy-1", "pre")]["portfolio_snapshot"]["snapshot_id"] == "snap-pre-open"
    assert contexts[("buy-1", "post")]["portfolio_snapshot"]["snapshot_id"] == "snap-post-open"
    assert contexts[("sell-1", "pre")]["portfolio_snapshot"]["snapshot_id"] == "snap-pre-close"
    assert contexts[("sell-1", "post")]["portfolio_snapshot"]["snapshot_id"] == "snap-post-close"


def test_same_second_fills_use_business_sequence(tmp_path: Path) -> None:
    events = [
        _event("buy-second", quantity="20", sequence=2),
        _event("buy-first", quantity="10", sequence=1),
        _event("sell", at=BASE + timedelta(minutes=1), side="SELL", quantity="30", sequence=3),
    ]
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", [])
    result = _build(_collection(events, snapshots=[]), db)
    observed = []
    for context in result["contexts"]:
        event_id = context["anchor"]["event_id"]
        if event_id not in observed:
            observed.append(event_id)
    assert observed == ["buy-first", "buy-second", "sell"]


def test_numeric_business_sequence_sorts_two_before_ten(tmp_path: Path) -> None:
    events = [
        _event("buy-ten", quantity="20", sequence=10),
        _event("buy-two", quantity="10", sequence=2),
        _event("sell", at=BASE + timedelta(minutes=1), side="SELL", quantity="30", sequence=11),
    ]
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", [])
    result = _build(_collection(events, snapshots=[]), db)
    observed: list[str] = []
    for context in result["contexts"]:
        event_id = str(context["anchor"]["event_id"])
        if event_id not in observed:
            observed.append(event_id)
    assert observed[:2] == ["buy-two", "buy-ten"]


def test_same_second_fills_without_sequence_are_ambiguous(tmp_path: Path) -> None:
    events = [
        _event("buy-a", quantity="10", sequence=None),
        _event("buy-b", quantity="20", sequence=None),
    ]
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", [])
    result = _build(_collection(events, snapshots=[]), db)
    affected = [
        item for item in result["contexts"] if item["anchor"]["event_id"] in {"buy-a", "buy-b"}
    ]
    assert affected
    assert all(item["portfolio_snapshot"]["status"] == "ambiguous" for item in affected)
    assert any(code in _codes(result) for code in {"AMBIGUOUS_EVENT_ORDER", "SAME_SECOND_AMBIGUOUS"})


@pytest.mark.parametrize("seed", range(6))
def test_snapshot_selection_ignores_sqlite_insertion_order(tmp_path: Path, seed: int) -> None:
    rows = _default_snapshots()
    baseline_db = _create_p2b_db(tmp_path / "baseline.sqlite3", rows, insertion_seed=100)
    candidate_db = _create_p2b_db(tmp_path / f"candidate-{seed}.sqlite3", rows, insertion_seed=seed)
    collection = _collection()
    baseline = _build(collection, baseline_db)
    candidate = _build(collection, candidate_db)
    assert candidate == baseline


def test_explicit_revision_and_knowledge_time_choose_latest_visible_row(tmp_path: Path) -> None:
    old = _snapshot(
        "snap-revision-1",
        known_at=BASE - timedelta(minutes=10),
        revision=1,
        cash="9000",
    )
    revised = _snapshot(
        "snap-revision-2",
        known_at=BASE - timedelta(minutes=5),
        revision=2,
        cash="8000",
    )
    post = _snapshot(
        "snap-post-open",
        known_at=BASE + timedelta(minutes=1),
        included=["buy-1"],
    )
    rows = [old, revised, post]
    refs = [_snapshot_ref_from_row(row) for row in rows]
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", rows)
    result = _build(_collection([_event("buy-1")], refs), db)
    pre = next(item for item in result["contexts"] if item["anchor"]["side"] == "pre")
    assert pre["portfolio_snapshot"]["snapshot_id"] == "snap-revision-2"
    assert pre["portfolio_snapshot"]["revision"] == 2


def test_same_rank_snapshot_revisions_degrade_to_ambiguous(tmp_path: Path) -> None:
    first = _snapshot(
        "snap-same-rank-a", known_at=BASE - timedelta(minutes=5), revision=1, cash="9000"
    )
    second = _snapshot(
        "snap-same-rank-b", known_at=BASE - timedelta(minutes=5), revision=1, cash="8000"
    )
    rows = [first, second]
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", rows)
    collection = _collection(
        [_event("buy-1")], [_snapshot_ref_from_row(row) for row in rows]
    )
    result = _build(collection, db)
    pre = next(item for item in result["contexts"] if item["anchor"]["side"] == "pre")
    assert pre["portfolio_snapshot"]["status"] == "ambiguous"
    assert "AMBIGUOUS_SNAPSHOT_REVISION" in _codes(result)


def test_catalog_database_state_hash_drift_is_rejected(tmp_path: Path) -> None:
    rows = _default_snapshots()
    drifted = deepcopy(rows)
    drifted[1]["source_state_hash"] = hashlib.sha256(b"drift").hexdigest()
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", drifted)
    with pytest.raises(EpisodePortfolioContextError, match="catalog/database drift"):
        _build(_collection(), db)


def test_duplicate_snapshot_identity_in_p2c_catalog_is_rejected(
    tmp_path: Path, closed_collection: dict[str, Any]
) -> None:
    duplicated = deepcopy(closed_collection)
    conflict = deepcopy(duplicated["snapshot_catalog"][0])
    conflict["source_state_hash"] = hashlib.sha256(b"conflict").hexdigest()
    duplicated["snapshot_catalog"].append(conflict)
    _rehash_collection(duplicated)
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", _default_snapshots())
    with pytest.raises(EpisodePortfolioContextError, match="blocked|duplicate"):
        _build(duplicated, db)


def test_child_position_state_hash_drift_is_rejected(tmp_path: Path) -> None:
    rows = _default_snapshots()
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", rows)
    connection = sqlite3.connect(db)
    try:
        connection.execute(
            "UPDATE position_snapshots SET source_state_hash = ? WHERE snapshot_id = ?",
            (hashlib.sha256(b"child-drift").hexdigest(), "snap-post-open"),
        )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(EpisodePortfolioContextError, match="lineage drift"):
        _build(_collection(), db)


def test_catalog_instrument_ids_must_match_database_positions(tmp_path: Path) -> None:
    rows = _default_snapshots()
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", rows)
    connection = sqlite3.connect(db)
    try:
        connection.execute(
            "UPDATE position_snapshots SET ts_code = ? WHERE snapshot_id = ?",
            ("000001.SZ", "snap-post-open"),
        )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(EpisodePortfolioContextError, match="instrument drift"):
        _build(_collection(), db)


def test_revision_after_knowledge_cutoff_is_never_consumed(tmp_path: Path) -> None:
    old = _snapshot("snap-r1", known_at=BASE - timedelta(minutes=10), revision=1)
    future = _snapshot("snap-r2", known_at=BASE - timedelta(minutes=1), revision=2)
    rows = [old, future]
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", rows)
    collection = _collection([_event("buy-1")], [_snapshot_ref_from_row(row) for row in rows])
    result = _build(
        collection,
        db,
        as_of=BASE,
        knowledge_cutoff=BASE - timedelta(minutes=5),
    )
    assert all(
        context["portfolio_snapshot"]["snapshot_id"] != "snap-r2"
        for context in result["contexts"]
    )


def test_missing_snapshot_keeps_context_and_missing_metrics(tmp_path: Path) -> None:
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", [])
    result = _build(_collection(snapshots=[]), db)
    assert result["contexts"]
    assert all(item["portfolio_snapshot"]["status"] == "missing" for item in result["contexts"])
    assert all(
        not item["metrics"]
        or all(metric["availability"] == "missing" for metric in item["metrics"].values())
        for item in result["contexts"]
    )


def test_partition_cursor_is_explicitly_partial_not_exact(
    artifact: dict[str, Any],
) -> None:
    linked = [
        context
        for context in artifact["contexts"]
        if context["portfolio_snapshot"]["snapshot_id"] is not None
    ]
    assert linked
    assert all(context["portfolio_snapshot"]["status"] == "replayed" for context in linked)
    assert "PORTFOLIO_CURSOR_SCOPE_LIMITED" in _codes(artifact)
    assert all(
        metric["availability"] != "available"
        for context in linked
        for metric in context["metrics"].values()
    )
    assert all(delta["value"] is None for delta in artifact["deltas"])


def test_complete_account_cursor_proof_allows_exact_post_contexts(
    tmp_path: Path,
) -> None:
    rows = _default_snapshots()
    references = [_snapshot_ref_from_row(row) for row in rows]
    for reference in references:
        reference["cursor_scope"] = "account"
        reference["included_event_set_complete"] = True
    collection = _collection(snapshots=references)
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", rows)
    result = _build(collection, db)
    post_contexts = [
        context
        for context in result["contexts"]
        if context["anchor"]["side"] == "post"
    ]
    assert post_contexts
    assert all(
        context["portfolio_snapshot"]["status"] == "exact"
        for context in post_contexts
    )
    assert all(
        context["portfolio_snapshot"]["cursor_proof"]
        == {
            "cursor_scope": "account",
            "included_event_set_complete": True,
            "boundary_limited": False,
        }
        for context in post_contexts
    )
    assert any(delta["availability"] == "available" for delta in result["deltas"])


def test_unpriced_position_remains_unknown_not_zero(tmp_path: Path) -> None:
    rows = _default_snapshots()
    rows[1]["positions"] = [
        _position(price=None, market_value=None, valuation_status="unpriced", staleness_days=None)
    ]
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", rows)
    result = _build(_collection(), db)
    post = next(
        item
        for item in result["contexts"]
        if item["anchor"]["event_id"] == "buy-1" and item["anchor"]["side"] == "post"
    )
    assert post["portfolio_snapshot"]["status"] == "invalid"
    assert post["metrics"] == {}
    assert {"UNPRICED", "PARTIAL_NAV_UNAVAILABLE"}.issubset(_codes(result))


def test_unknown_valuation_status_is_invalid_not_implicitly_complete(
    tmp_path: Path,
) -> None:
    rows = _default_snapshots()
    rows[1]["positions"] = [_position(valuation_status="mystery")]
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", rows)
    result = _build(_collection(), db)
    post = next(
        context
        for context in result["contexts"]
        if context["anchor"]["event_id"] == "buy-1"
        and context["anchor"]["side"] == "post"
    )
    assert post["portfolio_snapshot"]["status"] == "invalid"
    assert post["metrics"] == {}
    assert "SNAPSHOT_RECONCILIATION_FAILED" in _codes(result)


def test_stale_price_warning_is_traceable(tmp_path: Path) -> None:
    rows = _default_snapshots()
    rows[1]["positions"] = [
        _position(valuation_status="stale", staleness_days=3, price_date="2026-06-28")
    ]
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", rows)
    result = _build(_collection(), db)
    assert any(
        code in _codes(result)
        for code in {"PRICE_STALE", "STALE_PRICE", "STALE_POSITION"}
    )
    assert "fixture.close" in json.dumps(result, ensure_ascii=False)


def test_incomplete_classification_is_partial_not_silently_dropped(tmp_path: Path) -> None:
    rows = _default_snapshots()
    rows[1]["positions"] = [_position(industry="")]
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", rows)
    result = _build(_collection(), db)
    post = next(
        item
        for item in result["contexts"]
        if item["anchor"]["event_id"] == "buy-1" and item["anchor"]["side"] == "post"
    )
    industry_metrics = {
        key: metric
        for key, metric in post["metrics"].items()
        if "industry" in key
    }
    assert industry_metrics
    assert any(metric["availability"] in {"partial", "missing"} for metric in industry_metrics.values())
    assert any(
        code in _codes(result)
        for code in {"UNCLASSIFIED_INDUSTRY", "MISSING_CLASSIFICATION", "INDUSTRY_PARTIAL"}
    )


def test_industry_row_and_point_in_time_lineage_must_match(tmp_path: Path) -> None:
    rows = _default_snapshots()
    position = _position(industry="银行")
    lineage = json.loads(position["lineage_json"])
    lineage["industry"]["name"] = "新能源"
    position["lineage_json"] = json.dumps(
        lineage, ensure_ascii=False, sort_keys=True
    )
    rows[1]["positions"] = [position]
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", rows)
    result = _build(_collection(), db)
    post = next(
        context
        for context in result["contexts"]
        if context["anchor"]["event_id"] == "buy-1"
        and context["anchor"]["side"] == "post"
    )
    assert "MISSING_CLASSIFICATION" in _codes(result)
    assert "industry_weight.unknown" in post["metrics"]


@pytest.mark.parametrize("status", ["linked", "unlinked", "ambiguous", "invalid"])
def test_decision_link_status_is_propagated(status: str, tmp_path: Path) -> None:
    if status == "linked":
        decisions = [_decision("d1", "buy-1", known_at=BASE - timedelta(minutes=1))]
    elif status == "ambiguous":
        decisions = [
            _decision("d1", "buy-1", known_at=BASE - timedelta(minutes=2)),
            _decision("d2", "buy-1", known_at=BASE - timedelta(minutes=1)),
        ]
    elif status == "invalid":
        decisions = [_decision("d1", "buy-1", known_at=BASE + timedelta(minutes=1))]
    else:
        decisions = []
    collection = _collection([_event("buy-1", decisions=decisions)], snapshots=[])
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", [])
    result = _build(collection, db)
    assert {item["decision_link_status"] for item in result["contexts"]} == {status}


def test_open_episode_does_not_invent_close_anchor(tmp_path: Path) -> None:
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", [])
    result = _build(_collection([_event("buy-1")], snapshots=[]), db)
    assert result["contexts"]
    assert all(item["anchor"]["kind"] != "episode_close" for item in result["contexts"])
    assert {item["anchor"]["side"] for item in result["contexts"]} == {"pre", "post"}


def test_compatible_deltas_use_exact_decimal_arithmetic(artifact: dict[str, Any]) -> None:
    metric = next(
        deepcopy(value)
        for context in artifact["contexts"]
        for value in context["metrics"].values()
        if value["value"] is not None
    )
    metric["availability"] = "available"
    before_metric = deepcopy(metric)
    before_metric["value"] = "1.25"
    after_metric = deepcopy(metric)
    after_metric["value"] = "3.5"
    contexts = [
        {
            "context_id": "ctx-before",
            "episode_id": "episode-1",
            "anchor": {"event_id": "event-1", "side": "pre"},
            "metrics": {"nav": before_metric},
        },
        {
            "context_id": "ctx-after",
            "episode_id": "episode-1",
            "anchor": {"event_id": "event-1", "side": "post"},
            "metrics": {"nav": after_metric},
        },
    ]
    delta = _build_deltas(contexts)[0]
    assert delta["availability"] == "available"
    assert Decimal(delta["value"]) == Decimal("2.25")
    assert delta["method_compatibility"] == "same"


def test_incompatible_delta_cannot_publish_a_numeric_value(artifact: dict[str, Any]) -> None:
    mutated = deepcopy(artifact)
    delta = mutated["deltas"][0]
    delta["method_compatibility"] = "incompatible"
    delta["value"] = "1"
    assert validate_episode_portfolio_context(mutated)["validation_status"] == "blocked"


@pytest.mark.parametrize(
    ("cash", "market_value", "quantity"),
    [("0", "0", "0"), ("0", "-1000", "-100")],
)
def test_nonpositive_nav_never_divides_or_fabricates_ratio(
    tmp_path: Path, cash: str, market_value: str, quantity: str
) -> None:
    row = _snapshot(
        "snap-nonpositive",
        known_at=BASE - timedelta(minutes=1),
        cash=cash,
        market_value=market_value,
        positions=[
            _position(
                quantity=quantity,
                market_value=market_value,
                price="10",
            )
        ] if quantity != "0" else [],
    )
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", [row])
    result = _build(
        _collection([_event("buy-1")], [_snapshot_ref_from_row(row)]), db
    )
    ratio_metrics = [
        metric
        for context in result["contexts"]
        for key, metric in context["metrics"].items()
        if any(token in key for token in ("weight", "exposure", "concentration"))
    ]
    assert ratio_metrics
    assert all(
        metric["value"] is None
        and metric["availability"] in {"invalid", "not_applicable", "missing"}
        for metric in ratio_metrics
    )
    assert any(code in _codes(result) for code in {"NON_POSITIVE_NAV", "ZERO_NAV", "NEGATIVE_NAV"})


def test_timezone_equivalent_inputs_canonicalize_to_same_hash(tmp_path: Path) -> None:
    utc_events = [_event("buy-1", at=BASE)]
    shanghai_time = BASE.astimezone(timezone(timedelta(hours=8)))
    local_events = [_event("buy-1", at=shanghai_time)]
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", [])
    first = _build(_collection(utc_events, snapshots=[]), db)
    second = _build(
        _collection(local_events, snapshots=[]),
        db,
        as_of=CUTOFF.astimezone(timezone(timedelta(hours=8))),
        knowledge_cutoff=CUTOFF.astimezone(timezone(timedelta(hours=8))),
    )
    assert first == second
    assert first["as_of"].endswith("Z") or first["as_of"].endswith("+00:00")


def test_shanghai_business_date_controls_snapshot_visibility(tmp_path: Path) -> None:
    event_at = datetime(2026, 6, 30, 17, 30, tzinfo=UTC)
    known = event_at - timedelta(minutes=1)
    row = _snapshot(
        "snap-shanghai-day",
        known_at=known,
        positions=[],
        cash="10000",
        market_value="0",
    )
    row["as_of_date"] = "2026-07-01"
    row["cash_as_of_date"] = "2026-07-01"
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", [row])
    result = _build(
        _collection(
            [_event("buy-1", at=event_at, known_at=event_at)],
            [_snapshot_ref_from_row(row)],
            cutoff=event_at + timedelta(hours=1),
        ),
        db,
        as_of=event_at + timedelta(hours=1),
        knowledge_cutoff=event_at + timedelta(hours=1),
    )
    pre = next(item for item in result["contexts"] if item["anchor"]["side"] == "pre")
    assert pre["portfolio_snapshot"]["snapshot_id"] == "snap-shanghai-day"


def test_available_metrics_have_method_and_parseable_source_provenance(
    artifact: dict[str, Any]
) -> None:
    metrics = _available_metrics(artifact)
    assert metrics
    for metric in metrics:
        assert metric["method"]["method_id"]
        assert metric["method"]["method_version"]
        assert metric["source_refs"]
        for source in metric["source_refs"]:
            assert source["source_type"]
            assert source["source_id"]
            if source.get("effective_at"):
                datetime.fromisoformat(source["effective_at"].replace("Z", "+00:00"))
            if source.get("knowledge_at"):
                datetime.fromisoformat(source["knowledge_at"].replace("Z", "+00:00"))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.__setitem__("unexpected_narrative", "not allowed"),
        lambda value: value.__setitem__("metric_registry_version", "p2e2.registry.v999"),
        lambda value: value["contexts"][0]["anchor"].pop("side"),
        lambda value: next(
            metric
            for context in value["contexts"]
            for metric in context["metrics"].values()
        )["method"].__setitem__("method_version", "p2e2.registry.v999"),
    ],
)
def test_strict_schema_and_registry_reject_rehashed_mutations(
    artifact: dict[str, Any], mutation
) -> None:
    mutated = deepcopy(artifact)
    mutation(mutated)
    _rehash(mutated)
    assert validate_episode_portfolio_context(mutated)["validation_status"] == "blocked"


@pytest.mark.parametrize("bad_value", ["-0", "1.0", "0.0"])
def test_validator_rejects_noncanonical_decimal_after_rehash(
    artifact: dict[str, Any], bad_value: str
) -> None:
    mutated = deepcopy(artifact)
    metric = next(
        metric
        for context in mutated["contexts"]
        for metric in context["metrics"].values()
        if metric["value"] is not None
    )
    metric["value"] = bad_value
    _rehash(mutated)
    assert validate_episode_portfolio_context(mutated)["validation_status"] == "blocked"


def test_validator_rejects_dangling_delta_after_rehash(artifact: dict[str, Any]) -> None:
    mutated = deepcopy(artifact)
    mutated["deltas"][0]["from_context_id"] = "ctx-missing"
    _rehash(mutated)
    validation = validate_episode_portfolio_context(mutated)
    assert validation["validation_status"] == "blocked"
    assert "DANGLING_DELTA_CONTEXT" in {item["code"] for item in validation["findings"]}


def test_validator_rejects_delta_unit_drift_after_rehash(
    artifact: dict[str, Any],
) -> None:
    mutated = deepcopy(artifact)
    mutated["deltas"][0]["unit"] = "WRONG_UNIT"
    _rehash(mutated)
    validation = validate_episode_portfolio_context(mutated)
    assert validation["validation_status"] == "blocked"
    assert "DELTA_UNIT_MISMATCH" in {
        item["code"] for item in validation["findings"]
    }


def test_validator_rejects_missing_delta_after_rehash(
    artifact: dict[str, Any],
) -> None:
    mutated = deepcopy(artifact)
    mutated["deltas"].pop()
    _rehash(mutated)
    validation = validate_episode_portfolio_context(mutated)
    assert validation["validation_status"] == "blocked"
    assert "DELTA_COVERAGE_MISMATCH" in {
        item["code"] for item in validation["findings"]
    }


def test_validator_rejects_incomplete_context_anchor_pair_after_rehash(
    artifact: dict[str, Any],
) -> None:
    mutated = deepcopy(artifact)
    removed = mutated["contexts"].pop()
    removed_id = removed["context_id"]
    mutated["deltas"] = [
        delta
        for delta in mutated["deltas"]
        if removed_id
        not in {delta["from_context_id"], delta["to_context_id"]}
    ]
    _rehash(mutated)
    validation = validate_episode_portfolio_context(mutated)
    assert validation["validation_status"] == "blocked"
    assert "INCOMPLETE_CONTEXT_ANCHOR_PAIR" in {
        item["code"] for item in validation["findings"]
    }


def test_validator_rejects_mismatched_pre_post_anchor_identity_after_rehash(
    artifact: dict[str, Any],
) -> None:
    mutated = deepcopy(artifact)
    event_id = mutated["contexts"][0]["anchor"]["event_id"]
    post = next(
        context
        for context in mutated["contexts"]
        if context["anchor"]["event_id"] == event_id
        and context["anchor"]["side"] == "post"
    )
    shifted = datetime.fromisoformat(post["anchor"]["event_at"]) + timedelta(
        seconds=1
    )
    post["anchor"]["event_at"] = shifted.isoformat()
    post["anchor"]["as_of"] = shifted.isoformat()
    post["target_symbol"] = "000001.SZ"
    _rehash(mutated)
    validation = validate_episode_portfolio_context(mutated)
    assert validation["validation_status"] == "blocked"
    assert "CONTEXT_ANCHOR_PAIR_MISMATCH" in {
        item["code"] for item in validation["findings"]
    }


def test_validator_rejects_forged_context_id_after_rehash(
    artifact: dict[str, Any],
) -> None:
    mutated = deepcopy(artifact)
    mutated["contexts"][0]["context_id"] = "ctx:forged"
    mutated["deltas"] = _build_deltas(mutated["contexts"])
    _rehash(mutated)
    validation = validate_episode_portfolio_context(mutated)
    assert validation["validation_status"] == "blocked"
    assert "CONTEXT_ID_MISMATCH" in {
        item["code"] for item in validation["findings"]
    }


def test_validator_rejects_missing_metrics_for_usable_snapshot_after_rehash(
    artifact: dict[str, Any],
) -> None:
    mutated = deepcopy(artifact)
    event_id = mutated["contexts"][0]["anchor"]["event_id"]
    for context in mutated["contexts"]:
        if context["anchor"]["event_id"] == event_id:
            assert context["portfolio_snapshot"]["status"] in {"exact", "replayed"}
            context["metrics"] = {}
    mutated["deltas"] = _build_deltas(mutated["contexts"])
    _rehash(mutated)
    validation = validate_episode_portfolio_context(mutated)
    assert validation["validation_status"] == "blocked"
    assert "MISSING_METRICS_FOR_USABLE_SNAPSHOT" in {
        item["code"] for item in validation["findings"]
    }


def test_source_binding_requires_every_manifest_event_context_pair(
    artifact: dict[str, Any],
) -> None:
    mutated = deepcopy(artifact)
    removed_event = mutated["source_binding"]["material_events"][0]
    removed_ids = {
        context["context_id"]
        for context in mutated["contexts"]
        if context["episode_id"] == removed_event["episode_id"]
        and context["anchor"]["event_id"] == removed_event["event_id"]
    }
    mutated["contexts"] = [
        context
        for context in mutated["contexts"]
        if context["context_id"] not in removed_ids
    ]
    mutated["deltas"] = [
        delta
        for delta in mutated["deltas"]
        if delta["from_context_id"] not in removed_ids
        and delta["to_context_id"] not in removed_ids
    ]
    _rehash(mutated)
    validation = validate_episode_portfolio_context(mutated)
    assert validation["validation_status"] == "blocked"
    assert "MATERIAL_EVENT_COVERAGE_MISMATCH" in {
        item["code"] for item in validation["findings"]
    }


def test_source_replay_catches_self_consistent_manifest_history_rewrite(
    artifact: dict[str, Any],
    closed_collection: dict[str, Any],
    portfolio_db: Path,
) -> None:
    mutated = deepcopy(artifact)
    mutated["contexts"] = []
    mutated["deltas"] = []
    mutated["source_binding"]["material_events"] = []
    mutated["source_binding"]["material_event_set_content_id"] = (
        "sha256:" + hashlib.sha256(b"[]").hexdigest()
    )
    _rehash(mutated)
    assert validate_episode_portfolio_context(mutated)["validation_status"] in {
        "accepted",
        "accepted_with_warnings",
    }
    validation = replay_validate_episode_portfolio_context(
        mutated,
        episode_collection=closed_collection,
        portfolio_db=portfolio_db,
    )
    assert validation["validation_status"] == "blocked"
    assert "SOURCE_REPLAY_MISMATCH" in {
        item["code"] for item in validation["findings"]
    }


def test_source_replay_accepts_exact_deterministic_rebuild(
    artifact: dict[str, Any],
    closed_collection: dict[str, Any],
    portfolio_db: Path,
) -> None:
    validation = replay_validate_episode_portfolio_context(
        artifact,
        episode_collection=closed_collection,
        portfolio_db=portfolio_db,
    )
    assert validation["validation_status"] in {"accepted", "accepted_with_warnings"}
    assert validation["validation_mode"] == "source_replay"
    assert validation["source_verification"]["status"] == "verified"
    assert validation["source_verification"]["rebuilt_content_id"] == artifact[
        "content_id"
    ]


def test_cursor_proof_prevents_partial_context_upgrade_after_rehash(
    artifact: dict[str, Any],
) -> None:
    mutated = deepcopy(artifact)
    context = next(
        item
        for item in mutated["contexts"]
        if item["portfolio_snapshot"]["cursor_proof"]["boundary_limited"]
    )
    context["portfolio_snapshot"]["status"] = "exact"
    for metric in context["metrics"].values():
        if metric["availability"] == "partial":
            metric["availability"] = "available"
            metric["warning_codes"] = [
                code
                for code in metric["warning_codes"]
                if code != "PORTFOLIO_CURSOR_SCOPE_LIMITED"
            ]
    context["warnings"] = [
        warning
        for warning in context["warnings"]
        if warning["code"] != "PORTFOLIO_CURSOR_SCOPE_LIMITED"
    ]
    mutated["deltas"] = _build_deltas(mutated["contexts"])
    _rehash(mutated)
    validation = validate_episode_portfolio_context(mutated)
    assert validation["validation_status"] == "blocked"
    assert {
        "CURSOR_PROOF_MISMATCH",
        "AVAILABILITY_CEILING_VIOLATION",
    }.intersection(item["code"] for item in validation["findings"])


def test_source_replay_catches_self_consistent_forged_complete_cursor(
    artifact: dict[str, Any],
    closed_collection: dict[str, Any],
    portfolio_db: Path,
) -> None:
    mutated = deepcopy(artifact)
    for context in mutated["contexts"]:
        snapshot = context["portfolio_snapshot"]
        binding = context["source_binding"]["snapshot_binding"]
        if not binding or not snapshot["cursor_proof"]["boundary_limited"]:
            continue
        snapshot["cursor_proof"] = {
            "cursor_scope": "account",
            "included_event_set_complete": True,
            "boundary_limited": False,
        }
        binding["cursor_scope"] = "account"
        binding["included_event_set_complete"] = True
        binding["metric_availability_ceiling"] = "available"
        if context["anchor"]["side"] == "post":
            snapshot["status"] = "exact"
        for metric in context["metrics"].values():
            if metric["warning_codes"] == ["PORTFOLIO_CURSOR_SCOPE_LIMITED"]:
                metric["availability"] = "available"
                metric["warning_codes"] = []
        context["warnings"] = [
            warning
            for warning in context["warnings"]
            if warning["code"] != "PORTFOLIO_CURSOR_SCOPE_LIMITED"
        ]
        context["context_id"] = _stable_id(
            "ctx",
            {
                "episode_id": context["episode_id"],
                "anchor": context["anchor"],
                "target_symbol": context["target_symbol"],
                "decision_link_status": context["decision_link_status"],
                "snapshot_status": snapshot["status"],
                "snapshot_id": snapshot["snapshot_id"],
                "revision": snapshot["revision"],
                "source_binding": context["source_binding"],
                "base_currency": snapshot["base_currency"],
                "metric_registry_version": mutated["metric_registry_version"],
            },
        )
    mutated["contexts"].sort(
        key=lambda context: (
            context["episode_id"],
            context["anchor"]["event_at"],
            json.dumps(context["anchor"]["ordering_key"], separators=(",", ":")),
            0 if context["anchor"]["side"] == "pre" else 1,
            context["context_id"],
        )
    )
    mutated["deltas"] = _build_deltas(mutated["contexts"])
    _rehash(mutated)
    assert validate_episode_portfolio_context(mutated)["validation_status"] in {
        "accepted",
        "accepted_with_warnings",
    }
    validation = replay_validate_episode_portfolio_context(
        mutated,
        episode_collection=closed_collection,
        portfolio_db=portfolio_db,
    )
    assert validation["validation_status"] == "blocked"
    assert "SOURCE_REPLAY_MISMATCH" in {
        item["code"] for item in validation["findings"]
    }


def test_source_replay_rejects_self_consistent_forged_collection_ref(
    artifact: dict[str, Any],
    closed_collection: dict[str, Any],
    portfolio_db: Path,
) -> None:
    mutated = deepcopy(artifact)
    forged = "sha256:" + hashlib.sha256(b"forged-collection").hexdigest()
    mutated["episode_artifact_ref"]["content_id"] = forged
    mutated["source_binding"]["episode_collection_content_id"] = forged
    _rehash(mutated)
    assert validate_episode_portfolio_context(mutated)["validation_status"] in {
        "accepted",
        "accepted_with_warnings",
    }
    validation = replay_validate_episode_portfolio_context(
        mutated,
        episode_collection=closed_collection,
        portfolio_db=portfolio_db,
    )
    assert validation["validation_status"] == "blocked"
    assert "SOURCE_COLLECTION_REF_MISMATCH" in {
        item["code"] for item in validation["findings"]
    }


def test_metric_source_unit_and_value_domain_are_source_bound(
    artifact: dict[str, Any],
) -> None:
    for mutation, expected_code in (
        (
            lambda value: value["contexts"][0]["metrics"]["nav"].__setitem__(
                "unit", "BANANAS"
            ),
            "METRIC_UNIT_MISMATCH",
        ),
        (
            lambda value: value["contexts"][0]["metrics"][
                "position_count"
            ].__setitem__("value", "-0.5"),
            "METRIC_VALUE_DOMAIN_MISMATCH",
        ),
        (
            lambda value: value["contexts"][0]["metrics"]["nav"].__setitem__(
                "source_refs",
                [
                    {
                        "source_type": "forged",
                        "source_id": "not-the-snapshot",
                        "effective_at": None,
                        "knowledge_at": None,
                        "revision": None,
                    }
                ],
            ),
            "SOURCE_REF_BINDING_MISMATCH",
        ),
    ):
        mutated = deepcopy(artifact)
        mutation(mutated)
        _rehash(mutated)
        validation = validate_episode_portfolio_context(mutated)
        assert validation["validation_status"] == "blocked"
        assert expected_code in {
            item["code"] for item in validation["findings"]
        }


def test_validator_enforces_canonical_context_order_and_time(
    artifact: dict[str, Any],
) -> None:
    reordered = deepcopy(artifact)
    reordered["contexts"].reverse()
    _rehash(reordered)
    assert "NON_CANONICAL_CONTEXT_ORDER" in {
        item["code"]
        for item in validate_episode_portfolio_context(reordered)["findings"]
    }

    shifted = deepcopy(artifact)
    shifted["contexts"][0]["anchor"]["event_at"] = "2026-07-01T09:30:00+08:00"
    shifted["contexts"][0]["anchor"]["as_of"] = "2026-07-01T09:30:00+08:00"
    shifted["contexts"][0]["anchor"]["ordering_key"][0] = (
        "2026-07-01T09:30:00+08:00"
    )
    _rehash(shifted)
    assert "NON_CANONICAL_TIME" in {
        item["code"]
        for item in validate_episode_portfolio_context(shifted)["findings"]
    }


def test_validator_rejects_warning_status_delta_and_source_ref_mutations(
    artifact: dict[str, Any],
) -> None:
    partial_warning_removed = deepcopy(artifact)
    limited = next(
        context
        for context in partial_warning_removed["contexts"]
        if context["portfolio_snapshot"]["cursor_proof"]["boundary_limited"]
    )
    limited["warnings"] = [
        warning
        for warning in limited["warnings"]
        if warning["code"] != "PORTFOLIO_CURSOR_SCOPE_LIMITED"
    ]
    _rehash(partial_warning_removed)
    assert "AVAILABILITY_CEILING_VIOLATION" in {
        item["code"]
        for item in validate_episode_portfolio_context(
            partial_warning_removed
        )["findings"]
    }

    delta_drift = deepcopy(artifact)
    delta_drift["deltas"][0]["availability"] = "invalid"
    _rehash(delta_drift)
    assert "DELTA_DERIVATION_MISMATCH" in {
        item["code"]
        for item in validate_episode_portfolio_context(delta_drift)["findings"]
    }

    duplicate_code = deepcopy(artifact)
    metric = next(
        metric
        for context in duplicate_code["contexts"]
        for metric in context["metrics"].values()
        if metric["warning_codes"]
    )
    metric["warning_codes"].append(metric["warning_codes"][0])
    _rehash(duplicate_code)
    assert "NON_CANONICAL_WARNING_CODES" in {
        item["code"]
        for item in validate_episode_portfolio_context(duplicate_code)["findings"]
    }

    future_warning = deepcopy(artifact)
    future_warning["warnings"].append(
        {
            "code": "FORGED_FUTURE_SOURCE",
            "severity": "warning",
            "message": "mutation fixture",
            "source_refs": [
                {
                    "source_type": "trade_event",
                    "source_id": "future-event",
                    "effective_at": "2099-01-01T00:00:00+00:00",
                    "knowledge_at": "2099-01-01T00:00:00+00:00",
                    "revision": None,
                }
            ],
        }
    )
    future_warning["warnings"].sort(
        key=lambda warning: json.dumps(
            warning,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    _rehash(future_warning)
    assert {
        "FUTURE_SOURCE_EFFECTIVE_TIME",
        "FUTURE_SOURCE_KNOWLEDGE_TIME",
    }.issubset(
        item["code"]
        for item in validate_episode_portfolio_context(future_warning)["findings"]
    )


def test_validator_never_upgrades_partial_endpoints_to_available_delta(
    artifact: dict[str, Any],
) -> None:
    mutated = deepcopy(artifact)
    delta = mutated["deltas"][0]
    delta["availability"] = "available"
    delta["value"] = "1"
    _rehash(mutated)
    validation = validate_episode_portfolio_context(mutated)
    assert validation["validation_status"] == "blocked"
    assert "DELTA_ENDPOINT_NOT_AVAILABLE" in {
        item["code"] for item in validation["findings"]
    }


def test_build_keeps_source_database_byte_for_byte_read_only(
    closed_collection: dict[str, Any], portfolio_db: Path
) -> None:
    before = _sha256(portfolio_db)
    _build(closed_collection, portfolio_db)
    after = _sha256(portfolio_db)
    assert after == before


def test_historical_backfill_changes_content_id_without_rewriting_old_artifact(
    tmp_path: Path,
) -> None:
    rows = _default_snapshots()
    first_db = _create_p2b_db(tmp_path / "first.sqlite3", rows)
    collection = _collection()
    first = _build(collection, first_db)
    old_path = save_episode_portfolio_context(tmp_path / "old.json", first)
    old_bytes = old_path.read_bytes()

    revised = deepcopy(rows)
    revised[1]["cash_balance"] = "8500"
    revised[1]["market_value"] = "1500"
    revised[1]["positions"] = [_position(quantity="150", market_value="1500")]
    revised[1]["source_state_hash"] = hashlib.sha256(b"revised").hexdigest()
    second_db = _create_p2b_db(tmp_path / "second.sqlite3", revised)
    revised_collection = _collection(
        snapshots=[_snapshot_ref_from_row(row) for row in revised]
    )
    second = _build(revised_collection, second_db)
    assert second["content_id"] != first["content_id"]
    assert old_path.read_bytes() == old_bytes


def test_structurally_blocked_p2c_source_is_rejected(
    tmp_path: Path, closed_collection: dict[str, Any]
) -> None:
    tampered = deepcopy(closed_collection)
    tampered["episodes"][0]["event_refs"][0]["quantity_after"] = "999"
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", _default_snapshots())
    with pytest.raises(EpisodePortfolioContextError, match="source TradeEpisode collection is blocked"):
        _build(tampered, db)


def test_save_load_validate_and_query_round_trip(tmp_path: Path, artifact: dict[str, Any]) -> None:
    output = save_episode_portfolio_context(tmp_path / "context.json", artifact)
    loaded = load_episode_portfolio_context(output)
    assert loaded == artifact
    assert validate_episode_portfolio_context(loaded)["validation_status"] in {
        "accepted",
        "accepted_with_warnings",
    }
    episode_id = loaded["contexts"][0]["episode_id"]
    context_id = loaded["contexts"][0]["context_id"]
    assert query_episode_portfolio_context(loaded, episode_id=episode_id)
    assert query_episode_portfolio_context(loaded, context_id=context_id) == [
        loaded["contexts"][0]
    ]
    assert query_episode_portfolio_context(
        loaded, content_id=loaded["content_id"]
    ) == loaded["contexts"]
    assert query_episode_portfolio_context(
        loaded, content_id="sha256:" + "0" * 64
    ) == []
    assert query_episode_portfolio_context(loaded, context_id="missing") == []


@pytest.mark.parametrize("preexisting", [False, True])
def test_invalid_save_is_atomic_and_leaves_no_partial_output(
    tmp_path: Path, artifact: dict[str, Any], preexisting: bool
) -> None:
    output = tmp_path / "context.json"
    original = b"existing-content\n"
    if preexisting:
        output.write_bytes(original)
    invalid = deepcopy(artifact)
    invalid["content_id"] = "sha256:bad"
    with pytest.raises(EpisodePortfolioContextError):
        save_episode_portfolio_context(output, invalid)
    if preexisting:
        assert output.read_bytes() == original
    else:
        assert not output.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_load_rejects_malformed_or_nonobject_json(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{", encoding="utf-8")
    with pytest.raises((EpisodePortfolioContextError, json.JSONDecodeError)):
        load_episode_portfolio_context(malformed)
    nonobject = tmp_path / "array.json"
    nonobject.write_text("[]", encoding="utf-8")
    with pytest.raises(EpisodePortfolioContextError):
        load_episode_portfolio_context(nonobject)


def test_episode_id_filter_limits_build_and_query(tmp_path: Path) -> None:
    events = [
        _event("a-buy", account="acct-a", symbol="600000.SH"),
        _event("b-buy", account="acct-b", symbol="000001.SZ"),
    ]
    collection = _collection(events, snapshots=[])
    selected = collection["episodes"][0]["episode_id"]
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", [])
    result = _build(collection, db, episode_ids=[selected])
    assert {item["episode_id"] for item in result["contexts"]} == {selected}
    assert query_episode_portfolio_context(result, episode_id=selected) == result["contexts"]


def test_cli_build_show_and_validate_round_trip(
    tmp_path: Path, closed_collection: dict[str, Any], portfolio_db: Path, capsys
) -> None:
    episode_path = tmp_path / "episodes.json"
    episode_path.write_text(
        json.dumps(closed_collection, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    output = tmp_path / "context.json"
    assert review_main(
        [
            "episode-portfolio-context-build",
            "--episode-artifact",
            str(episode_path),
            "--portfolio-db",
            str(portfolio_db),
            "--cutoff-at",
            CUTOFF.isoformat(),
            "--knowledge-cutoff",
            CUTOFF.isoformat(),
            "--output",
            str(output),
        ]
    ) == 0
    built = json.loads(capsys.readouterr().out)
    assert built["content_id"].startswith("sha256:")
    assert output.is_file()
    assert review_main(["episode-portfolio-context-validate", str(output)]) == 0
    assert "accepted" in capsys.readouterr().out
    assert review_main(
        [
            "episode-portfolio-context-validate",
            str(output),
            "--source-replay",
            "--episode-artifact",
            str(episode_path),
            "--portfolio-db",
            str(portfolio_db),
        ]
    ) == 0
    replay_output = capsys.readouterr().out
    assert '"validation_mode": "source_replay"' in replay_output
    assert '"status": "verified"' in replay_output
    episode_id = closed_collection["episodes"][0]["episode_id"]
    assert review_main(
        ["episode-portfolio-context-show", str(output), "--episode-id", episode_id]
    ) == 0
    assert episode_id in capsys.readouterr().out
    assert review_main(
        [
            "episode-portfolio-context-show",
            str(output),
            "--content-id",
            built["content_id"],
        ]
    ) == 0
    assert episode_id in capsys.readouterr().out


def test_cli_build_failure_is_nonzero_and_atomic(
    tmp_path: Path, closed_collection: dict[str, Any], portfolio_db: Path
) -> None:
    episode_path = tmp_path / "episodes.json"
    episode_path.write_text(json.dumps(closed_collection), encoding="utf-8")
    output = tmp_path / "context.json"
    assert review_main(
        [
            "episode-portfolio-context-build",
            "--episode-artifact",
            str(episode_path),
            "--portfolio-db",
            str(portfolio_db),
            "--cutoff-at",
            "2026-07-01T08:00:00",
            "--knowledge-cutoff",
            CUTOFF.isoformat(),
            "--output",
            str(output),
        ]
    ) == 2
    assert not output.exists()


def test_cli_source_replay_requires_both_sources(
    tmp_path: Path, artifact: dict[str, Any]
) -> None:
    output = save_episode_portfolio_context(tmp_path / "context.json", artifact)
    assert review_main(
        [
            "episode-portfolio-context-validate",
            str(output),
            "--source-replay",
        ]
    ) == 2


@pytest.mark.parametrize(
    ("as_of", "knowledge_cutoff"),
    [
        ("2026-07-01T08:00:00", CUTOFF.isoformat()),
        (CUTOFF.isoformat(), "2026-07-01T08:00:00"),
    ],
)
def test_naive_temporal_boundaries_are_rejected(
    tmp_path: Path, as_of: str, knowledge_cutoff: str
) -> None:
    db = _create_p2b_db(tmp_path / "portfolio.sqlite3", [])
    with pytest.raises(EpisodePortfolioContextError):
        build_episode_portfolio_context(
            _collection(snapshots=[]),
            portfolio_db=db,
            as_of=as_of,
            knowledge_cutoff=knowledge_cutoff,
        )
