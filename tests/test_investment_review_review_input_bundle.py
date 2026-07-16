from __future__ import annotations

import hashlib
import json
import random
import sqlite3
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import pytest

from src.investment_review.artifact_io import canonical_json_bytes
from src.investment_review.cli import main as review_main
from src.investment_review.episode_portfolio_context import (
    build_episode_portfolio_context,
    replay_validate_episode_portfolio_context,
)
from src.investment_review.episodes import build_episode_collection
from src.investment_review.review_input_bundle import (
    ReviewInputBundleError,
    _content_id as _bundle_content_id,
    _episode_portfolio_slice,
    _file_sha256 as _bundle_source_sha256,
    _context_status,
    _portfolio_section,
    _wrapped_source_content_id,
    build_review_input_bundle,
    load_review_input_bundle,
    query_review_input_bundle,
    replay_validate_review_input_bundle,
    save_review_input_bundle,
    validate_review_input_bundle,
)


UTC = timezone.utc
BASE = datetime(2026, 7, 1, 1, 30, tzinfo=UTC)
CUTOFF = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _value_content_id(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _rehash(bundle: dict[str, Any]) -> dict[str, Any]:
    bundle["content_id"] = _bundle_content_id(bundle)
    return bundle


def _event(
    event_id: str,
    *,
    at: datetime = BASE,
    known_at: datetime | None = None,
    side: str = "BUY",
    quantity: str = "100",
    sequence: int | None = 1,
    decision_refs: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    known = known_at or at
    source_row: dict[str, Any] = {
        "account_id": "acct-1",
        "external_id": event_id,
        "dedupe_key": f"dk-{event_id}",
        "created_at": known.isoformat(),
    }
    if sequence is not None:
        source_row["entry_id"] = sequence
    return {
        "event_id": event_id,
        "source_id": "src-p2f-fixture",
        "source_record_id": f"acct-1::{event_id}",
        "payload_sha256": hashlib.sha256(event_id.encode("utf-8")).hexdigest(),
        "event_type": "fill",
        "occurred_at": at.isoformat(),
        "known_at": known.isoformat(),
        "account": "acct-1",
        "market": None,
        "symbol": "600000.SH",
        "side": side,
        "quantity": quantity,
        "currency": "CNY",
        "raw_payload": {"source_row": source_row},
        "decision_refs": [dict(item) for item in decision_refs],
    }


def _decision_ref(
    decision_id: str,
    event_id: str,
    *,
    effective_at: datetime,
    knowledge_at: datetime,
) -> dict[str, Any]:
    return {
        "decision_id": decision_id,
        "event_id": event_id,
        "relation": "execution",
        "symbol": "600000.SH",
        "market": None,
        "occurred_at": effective_at.isoformat(),
        "known_at": knowledge_at.isoformat(),
        "status": "OPEN",
        "link_source": "decision_event_links",
    }


def _position(
    *,
    quantity: str = "100",
    price: str | None = "10",
    market_value: str | None = "1000",
    valuation_status: str = "priced",
    staleness_days: int | None = 0,
    price_date: str = "2026-06-30",
    price_known_at: datetime | None = BASE - timedelta(hours=2),
) -> dict[str, Any]:
    return {
        "ts_code": "600000.SH",
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
        "industry_name": "银行",
        "industry_source": "fixture.taxonomy",
        "lineage_json": json.dumps(
            {
                "price": (
                    {
                        "trade_date": price_date,
                        "source": "fixture.close",
                        "known_at": (
                            price_known_at.isoformat()
                            if price_known_at is not None
                            else None
                        ),
                    }
                    if price is not None
                    else None
                ),
                "industry": {
                    "name": "银行",
                    "source": "fixture.taxonomy",
                    "updated_at": (BASE - timedelta(days=1)).isoformat(),
                    "point_in_time": True,
                },
                "transactions": [],
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
    }


def _snapshot(
    snapshot_id: str,
    *,
    known_at: datetime,
    included: Iterable[str] = (),
    cash: str | None = "9000",
    market_value: str = "1000",
    positions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    position_rows = list(positions if positions is not None else [_position()])
    return {
        "snapshot_id": snapshot_id,
        "account_id": "acct-1",
        "as_of_date": known_at.date().isoformat(),
        "knowledge_cutoff_at": known_at.isoformat(),
        "calculated_at": known_at.isoformat(),
        "revision": 1,
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
        "positions": position_rows,
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


def _snapshot_ref(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "snapshot_id": str(snapshot["snapshot_id"]),
        "account_id": str(snapshot["account_id"]),
        "as_of_date": str(snapshot["as_of_date"]),
        "knowledge_cutoff_at": str(snapshot["knowledge_cutoff_at"]),
        "revision": int(snapshot["revision"]),
        "engine_version": str(snapshot["engine_version"]),
        "source_state_hash": str(snapshot["source_state_hash"]),
        "source_path": "fixture-portfolio.sqlite3",
        "instrument_ids": sorted(
            str(item["ts_code"]) for item in snapshot["positions"]
        ),
        "included_event_ids": sorted(
            json.loads(str(snapshot["created_from_json"]))
        ),
    }


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
            priced_count = sum(
                item["valuation_status"] in {"priced", "stale"}
                for item in positions
            )
            unpriced_count = sum(
                item["valuation_status"] == "unpriced" for item in positions
            )
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
) -> dict[str, Any]:
    event_rows = list(
        events
        if events is not None
        else [
            _event(
                "buy-1",
                decision_refs=[
                    _decision_ref(
                        "decision-1",
                        "buy-1",
                        effective_at=BASE - timedelta(minutes=20),
                        knowledge_at=BASE - timedelta(minutes=15),
                    )
                ],
            ),
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
        else (_snapshot_ref(item) for item in _default_snapshots())
    )
    return build_episode_collection(
        event_rows,
        cutoff_at=CUTOFF.isoformat(),
        snapshot_references=snapshot_rows,
    )


def _optional_source(
    source_id: str,
    source_kind: str,
    *,
    effective_at: datetime,
    knowledge_at: datetime,
    locator: str | None = None,
    payload: Mapping[str, Any] | None = None,
    status: str = "available",
    warning_codes: Iterable[str] = (),
    event_id: str | None = None,
    relation: str | None = None,
) -> dict[str, Any]:
    body = dict(
        payload
        if payload is not None
        else {
            "source_id": source_id,
            "statement": f"fixture {source_kind}",
            "decimal_value": "10.25",
        }
    )
    result = {
        "source_id": source_id,
        "source_kind": source_kind,
        "effective_at": effective_at.isoformat(),
        "knowledge_at": knowledge_at.isoformat(),
        "content_id": _value_content_id(body),
        "locator": locator or f"fixture/{source_kind}/{source_id}.json",
        "status": status,
        "warning_codes": sorted(warning_codes),
        "payload": body,
    }
    if event_id is not None:
        result["event_id"] = event_id
    if relation is not None:
        result["relation"] = relation
    return result


@dataclass(frozen=True)
class FixtureChain:
    collection: dict[str, Any]
    portfolio_db: Path
    portfolio_context: dict[str, Any]
    episode_id: str
    decisions: tuple[dict[str, Any], ...]
    supplemental: tuple[dict[str, Any], ...]


def _fixture_chain(
    tmp_path: Path,
    *,
    events: Iterable[Mapping[str, Any]] | None = None,
    snapshots: list[dict[str, Any]] | None = None,
    decisions: Iterable[dict[str, Any]] | None = None,
    supplemental: Iterable[dict[str, Any]] | None = None,
) -> FixtureChain:
    snapshot_rows = deepcopy(snapshots if snapshots is not None else _default_snapshots())
    collection = _collection(events, [_snapshot_ref(item) for item in snapshot_rows])
    portfolio_db = _create_p2b_db(tmp_path / "portfolio.sqlite3", snapshot_rows)
    portfolio_context = build_episode_portfolio_context(
        collection,
        portfolio_db=portfolio_db,
        as_of=CUTOFF.isoformat(),
        knowledge_cutoff=CUTOFF.isoformat(),
    )
    episode_id = str(collection["episodes"][0]["episode_id"])
    decision_rows = tuple(
        decisions
        if decisions is not None
        else (
            _optional_source(
                "decision-1",
                "decision",
                effective_at=BASE - timedelta(minutes=20),
                knowledge_at=BASE - timedelta(minutes=15),
                event_id="buy-1",
                relation="execution",
            ),
        )
    )
    supplemental_rows = tuple(
        supplemental
        if supplemental is not None
        else (
            _optional_source(
                "market-1",
                "market_context",
                effective_at=BASE - timedelta(minutes=10),
                knowledge_at=BASE - timedelta(minutes=5),
            ),
            _optional_source(
                "outcome-1",
                "outcome",
                effective_at=BASE + timedelta(hours=1),
                knowledge_at=BASE + timedelta(hours=2),
            ),
        )
    )
    return FixtureChain(
        collection=collection,
        portfolio_db=portfolio_db,
        portfolio_context=portfolio_context,
        episode_id=episode_id,
        decisions=decision_rows,
        supplemental=supplemental_rows,
    )


def _build_bundle(
    chain: FixtureChain,
    *,
    review_cutoff: datetime = CUTOFF,
    decisions: Iterable[Mapping[str, Any]] | None = None,
    supplemental: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    return build_review_input_bundle(
        chain.collection,
        chain.portfolio_context,
        portfolio_db=chain.portfolio_db,
        episode_id=chain.episode_id,
        review_cutoff=review_cutoff.isoformat(),
        decision_sources=chain.decisions if decisions is None else decisions,
        supplemental_sources=(
            chain.supplemental if supplemental is None else supplemental
        ),
    )


def _finding_codes(validation: Mapping[str, Any]) -> set[str]:
    return {
        str(item.get("code"))
        for item in validation.get("findings", [])
        if isinstance(item, Mapping)
    }


def _warning_codes(bundle: Mapping[str, Any]) -> set[str]:
    return {
        str(item.get("code"))
        for item in bundle.get("warnings", [])
        if isinstance(item, Mapping)
    }


def _all_values(value: object) -> Iterable[object]:
    yield value
    if isinstance(value, Mapping):
        for nested in value.values():
            yield from _all_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _all_values(nested)


@pytest.fixture
def chain(tmp_path: Path) -> FixtureChain:
    return _fixture_chain(tmp_path)


@pytest.fixture
def bundle(chain: FixtureChain) -> dict[str, Any]:
    return _build_bundle(chain)


def test_f1_01_repeated_build_has_identical_content_id_and_bytes(
    chain: FixtureChain,
) -> None:
    first = _build_bundle(chain)
    second = _build_bundle(chain)
    assert first == second
    assert first["content_id"] == second["content_id"]
    assert canonical_json_bytes(first) == canonical_json_bytes(second)


def test_f1_02_optional_source_reordering_is_canonical(
    chain: FixtureChain,
) -> None:
    first = _build_bundle(chain)
    second = _build_bundle(
        chain,
        decisions=reversed(chain.decisions),
        supplemental=reversed(chain.supplemental),
    )
    assert second == first
    assert second["source_inventory"] == sorted(
        second["source_inventory"],
        key=lambda item: (
            item["source_kind"],
            item["source_id"],
            item["content_id"],
        ),
    )


def test_f1_03_decimal_values_remain_strings_and_no_float_enters_bundle(
    bundle: dict[str, Any],
) -> None:
    assert not any(isinstance(value, float) for value in _all_values(bundle))
    assert "10.25" in {
        value for value in _all_values(bundle) if isinstance(value, str)
    }
    portfolio = bundle["frozen_sources"]["portfolio_context_episode_slice"]
    metric_values = [
        metric["value"]
        for context in portfolio["contexts"]
        for metric in context.get("metrics", {}).values()
        if metric.get("value") is not None
    ]
    assert metric_values
    assert all(isinstance(value, str) for value in metric_values)


def test_f1_04_future_decision_is_withheld_by_knowledge_cutoff(
    chain: FixtureChain,
) -> None:
    future = deepcopy(chain.decisions[0])
    future["knowledge_at"] = (CUTOFF + timedelta(seconds=1)).isoformat()
    result = _build_bundle(chain, decisions=[future])
    assert result["frozen_sources"]["linked_decisions"] == []
    assert all(
        item["source_id"] != "decision-1"
        for item in result["source_inventory"]
    )
    assert "DECISION_WITHHELD_BY_CUTOFF" in _warning_codes(result)


@pytest.mark.parametrize("source_kind", ["price", "classification"])
def test_f1_05_future_market_lineage_is_excluded_with_warning(
    chain: FixtureChain,
    source_kind: str,
) -> None:
    future = _optional_source(
        f"{source_kind}-future",
        source_kind,
        effective_at=CUTOFF + timedelta(seconds=1),
        knowledge_at=CUTOFF + timedelta(seconds=2),
    )
    result = _build_bundle(
        chain,
        supplemental=[*chain.supplemental, future],
    )
    assert all(
        item["source_id"] != future["source_id"]
        for item in result["frozen_sources"]["supplemental_sources"]
    )
    assert all(
        item["source_id"] != future["source_id"]
        for item in result["source_inventory"]
    )
    assert f"{source_kind.upper()}_WITHHELD_BY_CUTOFF" in _warning_codes(result)


def test_f1_06_missing_p2e3_is_default_rejected(
    chain: FixtureChain,
) -> None:
    with pytest.raises(ReviewInputBundleError):
        build_review_input_bundle(
            chain.collection,
            None,
            portfolio_db=chain.portfolio_db,
            episode_id=chain.episode_id,
            review_cutoff=CUTOFF.isoformat(),
        )


def test_f1_06_contract_only_missing_p2e3_is_explicitly_release_blocked(
    chain: FixtureChain,
) -> None:
    result = build_review_input_bundle(
        chain.collection,
        None,
        portfolio_db=chain.portfolio_db,
        episode_id=chain.episode_id,
        review_cutoff=CUTOFF.isoformat(),
        decision_sources=chain.decisions,
        supplemental_sources=chain.supplemental,
        allow_missing_portfolio_context=True,
    )
    assert result["portfolio_context_ref"]["status"] == "missing"
    assert (
        result["frozen_sources"]["portfolio_context_episode_slice"]["status"]
        == "missing"
    )
    assert result["source_verification"]["status"] == "missing"
    assert result["section_availability"]["portfolio_context"]["status"] == "missing"
    assert result["release_readiness"]["status"] == "blocked"
    assert validate_review_input_bundle(result)["validation_status"] in {
        "accepted_with_warnings",
        "blocked",
    }


def test_f1_07_nonverified_or_ambiguous_p2e3_cannot_enter_production_bundle(
    tmp_path: Path,
) -> None:
    snapshots = _default_snapshots()
    snapshots[1]["created_from_json"] = json.dumps(["buy-1", "unknown-event"])
    chain = _fixture_chain(tmp_path, snapshots=snapshots)
    replay = replay_validate_episode_portfolio_context(
        chain.portfolio_context,
        episode_collection=chain.collection,
        portfolio_db=chain.portfolio_db,
    )
    assert replay["source_verification"]["status"] == "verified"
    assert any(
        context["portfolio_snapshot"]["status"] == "ambiguous"
        for context in chain.portfolio_context["contexts"]
    )
    result = build_review_input_bundle(
        chain.collection,
        chain.portfolio_context,
        portfolio_db=chain.portfolio_db,
        episode_id=chain.episode_id,
        review_cutoff=CUTOFF.isoformat(),
    )
    assert result["section_availability"]["portfolio_context"]["status"] == "ambiguous"
    assert result["source_verification"]["status"] == "verified"


@pytest.mark.parametrize(
    ("valuation_status", "price", "market_value", "expected"),
    [
        ("stale", "10", "1000", "stale"),
        ("unpriced", None, None, "unpriced"),
    ],
)
def test_f1_08_stale_and_unpriced_states_propagate_without_zero_fill(
    tmp_path: Path,
    valuation_status: str,
    price: str | None,
    market_value: str | None,
    expected: str,
) -> None:
    snapshots = _default_snapshots()
    for index in (1, 2):
        snapshots[index]["positions"] = [
            _position(
                price=price,
                market_value=market_value,
                valuation_status=valuation_status,
                staleness_days=10 if valuation_status == "stale" else None,
            )
        ]
        snapshots[index]["market_value"] = market_value or "0"
    result = _build_bundle(_fixture_chain(tmp_path, snapshots=snapshots))
    portfolio = result["frozen_sources"]["portfolio_context_episode_slice"]
    availability = {
        metric["availability"]
        for context in portfolio["contexts"]
        for metric in context.get("metrics", {}).values()
    }
    codes = {
        code
        for context in portfolio["contexts"]
        for metric in context.get("metrics", {}).values()
        for code in metric.get("warning_codes", [])
    }
    if expected == "stale":
        assert "STALE_POSITION" in codes
        assert "0" not in {
            metric["value"]
            for context in portfolio["contexts"]
            for metric in context.get("metrics", {}).values()
            if metric.get("availability") == "stale"
            and metric.get("value") is not None
        }
    else:
        assert result["section_availability"]["portfolio_context"]["status"] in {
            "unpriced",
            "invalid",
        }
        assert "0" not in {
            metric["value"]
            for context in portfolio["contexts"]
            for metric in context.get("metrics", {}).values()
            if metric.get("availability") == "unpriced"
            and metric.get("value") is not None
        }
    assert availability


def test_f1_09_open_episode_does_not_forge_close_or_outcome(
    tmp_path: Path,
) -> None:
    snapshots = _default_snapshots()[:2]
    open_chain = _fixture_chain(
        tmp_path,
        events=[_event("buy-1")],
        snapshots=snapshots,
        decisions=[],
        supplemental=[],
    )
    result = _build_bundle(open_chain)
    episode = result["frozen_sources"]["episode"]
    assert episode["status"] == "open"
    assert episode["closed_at"] is None
    assert result["frozen_sources"]["supplemental_sources"] == []
    assert result["section_availability"]["outcome_context"]["status"] == "missing"


def test_f1_10_invalid_episode_reference_is_rejected_after_outer_rehash(
    bundle: dict[str, Any],
) -> None:
    mutated = deepcopy(bundle)
    mutated["episode_ref"]["episode_id"] = "te:not-the-frozen-episode"
    _rehash(mutated)
    validation = validate_review_input_bundle(mutated)
    assert validation["validation_status"] == "blocked"
    assert _finding_codes(validation)


def test_f1_11_optional_source_content_change_changes_bundle_content_id(
    chain: FixtureChain,
) -> None:
    original = _build_bundle(chain)
    changed = deepcopy(chain.decisions[0])
    changed["payload"]["statement"] = "changed reviewed source"
    changed["content_id"] = _value_content_id(changed["payload"])
    rebuilt = _build_bundle(chain, decisions=[changed])
    assert rebuilt["content_id"] != original["content_id"]
    assert rebuilt["episode_ref"] == original["episode_ref"]


def test_f1_12_wall_clock_metadata_is_excluded_from_content_identity(
    bundle: dict[str, Any],
) -> None:
    assert "generated_at" not in bundle
    assert "writer_runtime" not in bundle
    assert bundle["canonicalization"]["excluded_fields"] == ["content_id"]
    assert _bundle_content_id(bundle) == bundle["content_id"]


@pytest.mark.parametrize("preexisting", [False, True])
def test_f1_13_invalid_save_is_atomic_and_leaves_no_partial_file(
    tmp_path: Path,
    bundle: dict[str, Any],
    preexisting: bool,
) -> None:
    output = tmp_path / "review-input.json"
    original = b"existing artifact\n"
    if preexisting:
        output.write_bytes(original)
    invalid = deepcopy(bundle)
    invalid["content_id"] = "sha256:bad"
    with pytest.raises(ReviewInputBundleError):
        save_review_input_bundle(output, invalid)
    if preexisting:
        assert output.read_bytes() == original
    else:
        assert not output.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_f1_14_build_and_source_replay_keep_portfolio_db_byte_exact(
    chain: FixtureChain,
) -> None:
    before = _sha256(chain.portfolio_db)
    result = _build_bundle(chain)
    validation = replay_validate_review_input_bundle(
        result,
        episode_collection=chain.collection,
        episode_portfolio_context=chain.portfolio_context,
        portfolio_db=chain.portfolio_db,
        decision_sources=chain.decisions,
        supplemental_sources=chain.supplemental,
    )
    after = _sha256(chain.portfolio_db)
    assert after == before
    assert validation["validation_status"] in {"accepted", "accepted_with_warnings"}
    assert validation["source_verification"]["status"] == "verified"
    assert validation["source_verification"]["portfolio_db_sha256_before"] == before
    assert validation["source_verification"]["portfolio_db_sha256_after"] == before


def test_real_p2e3_source_replay_succeeds_before_p2f_consumption(
    chain: FixtureChain,
) -> None:
    before = _sha256(chain.portfolio_db)
    validation = replay_validate_episode_portfolio_context(
        chain.portfolio_context,
        episode_collection=chain.collection,
        portfolio_db=chain.portfolio_db,
    )
    assert validation["validation_status"] in {"accepted", "accepted_with_warnings"}
    assert validation["source_verification"]["status"] == "verified"
    assert _sha256(chain.portfolio_db) == before


def test_save_load_and_query_round_trip(
    tmp_path: Path,
    bundle: dict[str, Any],
) -> None:
    output = save_review_input_bundle(tmp_path / "review-input.json", bundle)
    loaded = load_review_input_bundle(output)
    assert loaded == bundle
    assert query_review_input_bundle(loaded) == [loaded]
    assert query_review_input_bundle(
        loaded, content_id=loaded["content_id"]
    ) == [loaded]
    assert query_review_input_bundle(
        loaded, section="portfolio_context_episode_slice"
    ) == [loaded["frozen_sources"]["portfolio_context_episode_slice"]]
    assert query_review_input_bundle(
        loaded, section="episode_snapshot_catalog"
    ) == [loaded["frozen_sources"]["episode_snapshot_catalog"]]
    first_source = loaded["source_inventory"][0]
    assert query_review_input_bundle(
        loaded, source_id=first_source["source_id"]
    ) == [first_source]
    assert query_review_input_bundle(
        loaded, content_id="sha256:" + "0" * 64
    ) == []
    assert query_review_input_bundle(loaded, source_id="missing") == []


def test_load_rejects_malformed_and_nonobject_json(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{", encoding="utf-8")
    with pytest.raises((ReviewInputBundleError, json.JSONDecodeError)):
        load_review_input_bundle(malformed)
    nonobject = tmp_path / "array.json"
    nonobject.write_text("[]", encoding="utf-8")
    with pytest.raises(ReviewInputBundleError):
        load_review_input_bundle(nonobject)


@pytest.mark.parametrize(
    "review_cutoff",
    [
        "2026-07-01T08:00:00",
        "not-a-timestamp",
    ],
)
def test_review_cutoff_requires_canonical_timezone_aware_timestamp(
    chain: FixtureChain,
    review_cutoff: str,
) -> None:
    with pytest.raises(ReviewInputBundleError):
        build_review_input_bundle(
            chain.collection,
            chain.portfolio_context,
            portfolio_db=chain.portfolio_db,
            episode_id=chain.episode_id,
            review_cutoff=review_cutoff,
        )


def test_cutoff_order_cannot_precede_frozen_source_boundary(
    chain: FixtureChain,
) -> None:
    with pytest.raises(ReviewInputBundleError):
        _build_bundle(chain, review_cutoff=CUTOFF - timedelta(seconds=1))


def test_self_consistent_rehash_cannot_hide_cutoff_order_reversal(
    bundle: dict[str, Any],
) -> None:
    mutated = deepcopy(bundle)
    mutated["build_request"]["review_cutoff"] = (
        CUTOFF - timedelta(seconds=1)
    ).isoformat()
    _rehash(mutated)
    validation = validate_review_input_bundle(mutated)
    assert validation["validation_status"] == "blocked"
    assert _finding_codes(validation)


def test_inventory_missing_required_source_is_rejected_after_rehash(
    bundle: dict[str, Any],
) -> None:
    mutated = deepcopy(bundle)
    mutated["source_inventory"] = mutated["source_inventory"][1:]
    _rehash(mutated)
    validation = validate_review_input_bundle(mutated)
    assert validation["validation_status"] == "blocked"
    assert _finding_codes(validation)


def test_inventory_extra_unfrozen_source_is_rejected_after_rehash(
    bundle: dict[str, Any],
) -> None:
    mutated = deepcopy(bundle)
    extra = deepcopy(mutated["source_inventory"][-1])
    extra["source_id"] = "inventory-only"
    extra["content_id"] = _value_content_id({"unfrozen": True})
    extra["locator"] = "fixture/unfrozen.json"
    mutated["source_inventory"].append(extra)
    mutated["source_inventory"].sort(
        key=lambda item: (
            item["source_kind"],
            item["source_id"],
            item["content_id"],
        )
    )
    _rehash(mutated)
    validation = validate_review_input_bundle(mutated)
    assert validation["validation_status"] == "blocked"
    assert _finding_codes(validation)


def test_inventory_duplicate_identity_with_conflicting_content_is_rejected(
    bundle: dict[str, Any],
) -> None:
    mutated = deepcopy(bundle)
    conflict = deepcopy(mutated["source_inventory"][0])
    conflict["content_id"] = _value_content_id({"forged": True})
    conflict["locator"] = "fixture/conflicting-copy.json"
    mutated["source_inventory"].append(conflict)
    mutated["source_inventory"].sort(
        key=lambda item: (
            item["source_kind"],
            item["source_id"],
            item["content_id"],
        )
    )
    _rehash(mutated)
    validation = validate_review_input_bundle(mutated)
    assert validation["validation_status"] == "blocked"
    assert _finding_codes(validation)


def test_section_availability_cannot_be_promoted_without_sources(
    chain: FixtureChain,
) -> None:
    missing = _build_bundle(chain, decisions=[], supplemental=[])
    mutated = deepcopy(missing)
    section = mutated["section_availability"]["market_context"]
    assert section["status"] == "missing"
    section["status"] = "available"
    section["source_ids"] = []
    section.pop("reason", None)
    _rehash(mutated)
    validation = validate_review_input_bundle(mutated)
    assert validation["validation_status"] == "blocked"
    assert _finding_codes(validation)


def test_source_inventory_noncanonical_order_is_rejected_after_rehash(
    bundle: dict[str, Any],
) -> None:
    mutated = deepcopy(bundle)
    mutated["source_inventory"].reverse()
    _rehash(mutated)
    validation = validate_review_input_bundle(mutated)
    assert validation["validation_status"] == "blocked"
    assert _finding_codes(validation)


def test_equivalent_noncanonical_cutoff_timezone_is_rejected_after_rehash(
    bundle: dict[str, Any],
) -> None:
    mutated = deepcopy(bundle)
    mutated["build_request"]["review_cutoff"] = "2026-07-01T16:00:00+08:00"
    _rehash(mutated)
    validation = validate_review_input_bundle(mutated)
    assert validation["validation_status"] == "blocked"
    assert _finding_codes(validation)


def test_nested_episode_content_drift_is_not_hidden_by_outer_rehash(
    bundle: dict[str, Any],
) -> None:
    mutated = deepcopy(bundle)
    event = mutated["frozen_sources"]["episode"]["event_refs"][0]
    event["signed_quantity"] = "999"
    _rehash(mutated)
    validation = validate_review_input_bundle(mutated)
    assert validation["validation_status"] == "blocked"
    assert _finding_codes(validation)


def test_episode_snapshot_catalog_is_exact_frozen_reference_closure(
    bundle: dict[str, Any],
) -> None:
    episode = bundle["frozen_sources"]["episode"]
    catalog = bundle["frozen_sources"]["episode_snapshot_catalog"]
    referenced = {
        item["snapshot_ref"]
        for item in episode["snapshot_links"]
        if item.get("snapshot_ref")
    }
    assert {item["snapshot_id"] for item in catalog} == referenced
    assert all(
        any(
            inventory["frozen_pointer"]
            == f"/frozen_sources/episode_snapshot_catalog/{index}"
            for inventory in bundle["source_inventory"]
        )
        for index, _ in enumerate(catalog)
    )


def test_removed_episode_snapshot_catalog_entry_is_blocked_after_rehash(
    bundle: dict[str, Any],
) -> None:
    mutated = deepcopy(bundle)
    removed = mutated["frozen_sources"]["episode_snapshot_catalog"].pop()
    mutated["source_inventory"] = [
        item
        for item in mutated["source_inventory"]
        if item["source_id"] != removed["snapshot_id"]
    ]
    _rehash(mutated)
    validation = validate_review_input_bundle(mutated)
    assert validation["validation_status"] == "blocked"
    assert "EPISODE_SNAPSHOT_CATALOG_MISMATCH" in _finding_codes(validation)


def test_nested_optional_source_content_id_is_recomputed_from_payload(
    bundle: dict[str, Any],
) -> None:
    mutated = deepcopy(bundle)
    decision = mutated["frozen_sources"]["linked_decisions"][0]
    forged = _value_content_id({"forged": "self-consistent-inventory"})
    decision["content_id"] = forged
    inventory = next(
        item
        for item in mutated["source_inventory"]
        if item["source_id"] == decision["source_id"]
    )
    inventory["content_id"] = forged
    mutated["source_inventory"].sort(
        key=lambda item: (
            item["source_kind"],
            item["source_id"],
            item["content_id"],
        )
    )
    _rehash(mutated)
    validation = validate_review_input_bundle(mutated)
    assert validation["validation_status"] == "blocked"
    assert _finding_codes(validation)


def test_nested_portfolio_context_id_drift_is_not_hidden_by_outer_rehash(
    bundle: dict[str, Any],
) -> None:
    mutated = deepcopy(bundle)
    mutated["frozen_sources"]["portfolio_context_episode_slice"]["contexts"][0][
        "context_id"
    ] = "ctx:" + "0" * 32
    _rehash(mutated)
    validation = validate_review_input_bundle(mutated)
    assert validation["validation_status"] == "blocked"
    assert _finding_codes(validation)


def test_exact_p2e3_nested_schema_rejects_self_rehashed_extra_field(
    bundle: dict[str, Any],
) -> None:
    mutated = deepcopy(bundle)
    mutated["frozen_sources"]["portfolio_context_episode_slice"]["contexts"][0][
        "forged_extra"
    ] = "not-owned-by-p2e3"
    _rehash(mutated)
    validation = validate_review_input_bundle(mutated)
    assert validation["validation_status"] == "blocked"
    assert "P2E3_SLICE_SCHEMA_VIOLATION" in _finding_codes(validation)


def test_collection_scope_p2e3_warning_is_retained_but_scoped(
    chain: FixtureChain,
) -> None:
    artifact = deepcopy(chain.portfolio_context)
    artifact["warnings"].append(
        {
            "code": "COLLECTION_LEVEL_FIXTURE_WARNING",
            "severity": "warning",
            "message": "Fixture warning has no episode-specific source refs.",
            "source_refs": [],
        }
    )
    portfolio_slice = _episode_portfolio_slice(
        artifact, episode_id=chain.episode_id
    )
    retained = next(
        item
        for item in portfolio_slice["warnings"]
        if item["code"] == "COLLECTION_LEVEL_FIXTURE_WARNING"
    )
    assert retained["scope"] == "collection"


def test_inventory_locator_drift_from_frozen_source_is_rejected(
    bundle: dict[str, Any],
) -> None:
    mutated = deepcopy(bundle)
    decision_id = mutated["frozen_sources"]["linked_decisions"][0]["source_id"]
    inventory = next(
        item
        for item in mutated["source_inventory"]
        if item["source_id"] == decision_id
    )
    inventory["locator"] = "fixture/forged-locator.json"
    _rehash(mutated)
    validation = validate_review_input_bundle(mutated)
    assert validation["validation_status"] == "blocked"
    assert _finding_codes(validation)


def test_source_verification_fields_cannot_be_forged_with_outer_rehash(
    bundle: dict[str, Any],
) -> None:
    mutated = deepcopy(bundle)
    mutated["source_verification"]["validator_version"] = "forged-validator"
    mutated["source_verification"]["portfolio_db_sha256_before"] = "0" * 64
    mutated["source_verification"]["portfolio_db_sha256_after"] = "0" * 64
    mutated["source_verification"]["rebuilt_content_id"] = mutated["content_id"]
    _rehash(mutated)
    validation = validate_review_input_bundle(mutated)
    assert validation["validation_status"] == "blocked"
    assert _finding_codes(validation)


def test_source_replay_rejects_deleted_material_event_after_outer_rehash(
    bundle: dict[str, Any],
    chain: FixtureChain,
) -> None:
    mutated = deepcopy(bundle)
    portfolio = mutated["frozen_sources"]["portfolio_context_episode_slice"]
    removed = portfolio["source_binding"]["material_events"].pop()
    removed_event_id = removed["event_id"]
    removed_context_ids = {
        item["context_id"]
        for item in portfolio["contexts"]
        if item["anchor"]["event_id"] == removed_event_id
    }
    portfolio["contexts"] = [
        item
        for item in portfolio["contexts"]
        if item["anchor"]["event_id"] != removed_event_id
    ]
    portfolio["deltas"] = [
        item
        for item in portfolio["deltas"]
        if item["from_context_id"] not in removed_context_ids
        and item["to_context_id"] not in removed_context_ids
    ]
    _rehash(mutated)
    validation = replay_validate_review_input_bundle(
        mutated,
        episode_collection=chain.collection,
        episode_portfolio_context=chain.portfolio_context,
        portfolio_db=chain.portfolio_db,
        decision_sources=chain.decisions,
        supplemental_sources=chain.supplemental,
    )
    assert validation["validation_status"] == "blocked"
    assert _finding_codes(validation)


def test_future_frozen_source_is_rejected_even_after_inventory_rehash(
    bundle: dict[str, Any],
) -> None:
    mutated = deepcopy(bundle)
    decision = mutated["frozen_sources"]["linked_decisions"][0]
    decision["knowledge_at"] = "2099-01-01T00:00:00Z"
    inventory = next(
        item
        for item in mutated["source_inventory"]
        if item["source_id"] == decision["source_id"]
    )
    inventory["knowledge_at"] = decision["knowledge_at"]
    _rehash(mutated)
    validation = validate_review_input_bundle(mutated)
    assert validation["validation_status"] == "blocked"
    assert _finding_codes(validation)


def test_source_replay_rejects_cross_episode_substitution(
    tmp_path: Path,
) -> None:
    multi = _fixture_chain(
        tmp_path,
        events=[
            _event("buy-1"),
            _event(
                "sell-1",
                at=BASE + timedelta(hours=1),
                side="SELL",
                sequence=2,
            ),
            _event(
                "buy-2",
                at=BASE + timedelta(hours=2),
                side="BUY",
                sequence=3,
            ),
        ],
        decisions=[],
    )
    assert len(multi.collection["episodes"]) == 2
    original = _build_bundle(multi)
    other = next(
        item
        for item in multi.collection["episodes"]
        if item["episode_id"] != multi.episode_id
    )
    mutated = deepcopy(original)
    mutated["episode_ref"]["episode_id"] = other["episode_id"]
    mutated["frozen_sources"]["episode"] = deepcopy(other)
    _rehash(mutated)
    validation = replay_validate_review_input_bundle(
        mutated,
        episode_collection=multi.collection,
        episode_portfolio_context=multi.portfolio_context,
        portfolio_db=multi.portfolio_db,
        decision_sources=multi.decisions,
        supplemental_sources=multi.supplemental,
    )
    assert validation["validation_status"] == "blocked"
    assert _finding_codes(validation)


def test_missing_contract_bundle_cannot_forge_release_ready_or_verified(
    chain: FixtureChain,
) -> None:
    missing = build_review_input_bundle(
        chain.collection,
        None,
        portfolio_db=chain.portfolio_db,
        episode_id=chain.episode_id,
        review_cutoff=CUTOFF.isoformat(),
        allow_missing_portfolio_context=True,
    )
    mutated = deepcopy(missing)
    mutated["source_verification"]["status"] = "verified"
    mutated["release_readiness"]["status"] = "ready"
    _rehash(mutated)
    validation = validate_review_input_bundle(mutated)
    assert validation["validation_status"] == "blocked"
    assert _finding_codes(validation)


def test_review_input_cli_build_show_and_source_replay_validate(
    tmp_path: Path,
    chain: FixtureChain,
    capsys: pytest.CaptureFixture[str],
) -> None:
    episode_path = tmp_path / "episodes.json"
    context_path = tmp_path / "portfolio-context.json"
    decisions_path = tmp_path / "decisions.json"
    supplemental_path = tmp_path / "supplemental.json"
    output = tmp_path / "review-input.json"
    episode_path.write_text(
        json.dumps(chain.collection, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    context_path.write_text(
        json.dumps(chain.portfolio_context, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    decisions_path.write_text(
        json.dumps(chain.decisions, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    supplemental_path.write_text(
        json.dumps(chain.supplemental, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )

    assert (
        review_main(
            [
                "review-input-build",
                "--episode-artifact",
                str(episode_path),
                "--portfolio-context",
                str(context_path),
                "--portfolio-db",
                str(chain.portfolio_db),
                "--episode-id",
                chain.episode_id,
                "--review-cutoff",
                CUTOFF.isoformat(),
                "--decision-source",
                str(decisions_path),
                "--supplemental-source",
                str(supplemental_path),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    built = load_review_input_bundle(output)
    capsys.readouterr()

    assert (
        review_main(
            [
                "review-input-show",
                str(output),
                "--content-id",
                built["content_id"],
            ]
        )
        == 0
    )
    shown = json.loads(capsys.readouterr().out)
    assert shown[0]["content_id"] == built["content_id"]

    assert (
        review_main(
            [
                "review-input-validate",
                str(output),
                "--source-replay",
                "--episode-artifact",
                str(episode_path),
                "--portfolio-context",
                str(context_path),
                "--portfolio-db",
                str(chain.portfolio_db),
                "--decision-source",
                str(decisions_path),
                "--supplemental-source",
                str(supplemental_path),
            ]
        )
        == 0
    )
    validated = json.loads(capsys.readouterr().out)
    assert validated["source_verification"]["status"] == "verified"


def test_review_input_cli_source_replay_requires_all_primary_sources(
    tmp_path: Path,
    bundle: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = save_review_input_bundle(tmp_path / "review-input.json", bundle)
    assert (
        review_main(
            [
                "review-input-validate",
                str(output),
                "--source-replay",
            ]
        )
        == 2
    )
    error = json.loads(capsys.readouterr().err)
    assert "requires --episode-artifact" in error["error"]


def test_optional_source_rejects_conflicting_time_alias(
    chain: FixtureChain,
) -> None:
    source = deepcopy(chain.supplemental[0])
    source["known_at"] = "2099-01-01T00:00:00+00:00"
    with pytest.raises(ReviewInputBundleError):
        _build_bundle(chain, supplemental=[source])


def test_optional_source_rejects_payload_change_with_stale_content_id(
    chain: FixtureChain,
) -> None:
    source = deepcopy(chain.supplemental[0])
    source["payload"]["statement"] = "forged without source hash update"
    with pytest.raises(ReviewInputBundleError):
        _build_bundle(chain, supplemental=[source])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("event_id", "sell-1"),
        ("relation", "forged_relation"),
        ("effective_at", (BASE - timedelta(minutes=30)).isoformat()),
        ("knowledge_at", (BASE - timedelta(minutes=10)).isoformat()),
    ],
)
def test_decision_envelope_must_match_canonical_p2c_link(
    chain: FixtureChain,
    field: str,
    value: str,
) -> None:
    decision = deepcopy(chain.decisions[0])
    decision[field] = value
    with pytest.raises(ReviewInputBundleError):
        _build_bundle(chain, decisions=[decision])


def test_self_consistent_frozen_decision_link_forgery_is_blocked(
    bundle: dict[str, Any],
    chain: FixtureChain,
) -> None:
    mutated = deepcopy(bundle)
    decision = mutated["frozen_sources"]["linked_decisions"][0]
    link_ref = decision["decision_link_refs"][0]
    link_ref["event_id"] = "sell-1"
    link_ref["relation"] = "forged_relation"
    decision["content_id"] = _wrapped_source_content_id(decision)
    inventory = next(
        item
        for item in mutated["source_inventory"]
        if item["source_id"] == decision["source_id"]
    )
    inventory["content_id"] = decision["content_id"]
    _rehash(mutated)
    offline = validate_review_input_bundle(mutated)
    assert offline["validation_status"] == "blocked"
    assert "DECISION_LINK_CLOSURE_MISMATCH" in _finding_codes(offline)
    replay = replay_validate_review_input_bundle(
        mutated,
        episode_collection=chain.collection,
        episode_portfolio_context=chain.portfolio_context,
        portfolio_db=chain.portfolio_db,
        decision_sources=chain.decisions,
        supplemental_sources=chain.supplemental,
    )
    assert replay["validation_status"] == "blocked"
    assert "DECISION_LINK_CLOSURE_MISMATCH" in _finding_codes(replay)


def test_canonical_decision_known_after_linked_event_is_invalid(
    tmp_path: Path,
) -> None:
    invalid_ref = _decision_ref(
        "decision-invalid",
        "buy-1",
        effective_at=BASE - timedelta(minutes=20),
        knowledge_at=BASE + timedelta(minutes=30),
    )
    invalid_chain = _fixture_chain(
        tmp_path,
        events=[
            _event("buy-1", decision_refs=[invalid_ref]),
            _event(
                "sell-1",
                at=BASE + timedelta(hours=1),
                side="SELL",
                sequence=2,
            ),
        ],
        decisions=[
            _optional_source(
                "decision-invalid",
                "decision",
                effective_at=BASE - timedelta(minutes=20),
                knowledge_at=BASE + timedelta(minutes=30),
                event_id="buy-1",
                relation="execution",
            )
        ],
        supplemental=[],
    )
    result = _build_bundle(invalid_chain)
    frozen = result["frozen_sources"]["linked_decisions"][0]
    assert frozen["availability"] == "invalid"
    assert "DECISION_KNOWN_AFTER_LINKED_EVENT" in frozen["warning_codes"]
    assert (
        result["section_availability"]["execution_consistency"]["status"]
        == "invalid"
    )


def test_later_episode_decision_known_before_linked_event_remains_available(
    tmp_path: Path,
) -> None:
    decision_ref = _decision_ref(
        "decision-later",
        "sell-1",
        effective_at=BASE + timedelta(minutes=20),
        knowledge_at=BASE + timedelta(minutes=30),
    )
    later_chain = _fixture_chain(
        tmp_path,
        events=[
            _event("buy-1"),
            _event(
                "sell-1",
                at=BASE + timedelta(hours=1),
                side="SELL",
                sequence=2,
                decision_refs=[decision_ref],
            ),
        ],
        decisions=[
            _optional_source(
                "decision-later",
                "decision",
                effective_at=BASE + timedelta(minutes=20),
                knowledge_at=BASE + timedelta(minutes=30),
                event_id="sell-1",
                relation="execution",
            )
        ],
        supplemental=[],
    )
    result = _build_bundle(later_chain)
    frozen = result["frozen_sources"]["linked_decisions"][0]
    assert frozen["decision_link_refs"] == [
        {
            "event_id": "sell-1",
            "relation": "execution",
            "link_content_id": frozen["decision_link_refs"][0][
                "link_content_id"
            ],
            "availability": "available",
            "warning_codes": [],
        }
    ]
    assert frozen["availability"] == "available"
    assert (
        result["section_availability"]["execution_consistency"]["status"]
        == "available"
    )


def test_one_decision_multiple_execution_links_are_exactly_frozen_and_replayed(
    tmp_path: Path,
) -> None:
    effective = BASE - timedelta(minutes=20)
    known = BASE - timedelta(minutes=15)
    shared_refs = {
        event_id: _decision_ref(
            "decision-shared",
            event_id,
            effective_at=effective,
            knowledge_at=known,
        )
        for event_id in ("buy-1", "sell-1")
    }
    decision_source = _optional_source(
        "decision-shared",
        "decision",
        effective_at=effective,
        knowledge_at=known,
        relation="execution",
    )
    decision_source["event_ids"] = ["buy-1", "sell-1"]
    multi_chain = _fixture_chain(
        tmp_path,
        events=[
            _event("buy-1", decision_refs=[shared_refs["buy-1"]]),
            _event(
                "sell-1",
                at=BASE + timedelta(hours=1),
                side="SELL",
                sequence=2,
                decision_refs=[shared_refs["sell-1"]],
            ),
        ],
        decisions=[decision_source],
        supplemental=[],
    )
    result = _build_bundle(multi_chain)
    frozen = result["frozen_sources"]["linked_decisions"][0]
    assert [item["event_id"] for item in frozen["decision_link_refs"]] == [
        "buy-1",
        "sell-1",
    ]
    assert all(
        item["availability"] == "available"
        for item in frozen["decision_link_refs"]
    )
    assert validate_review_input_bundle(result)["validation_status"] != "blocked"
    replay = replay_validate_review_input_bundle(
        result,
        episode_collection=multi_chain.collection,
        episode_portfolio_context=multi_chain.portfolio_context,
        portfolio_db=multi_chain.portfolio_db,
        decision_sources=multi_chain.decisions,
        supplemental_sources=[],
    )
    assert replay["validation_status"] != "blocked"

    mutated = deepcopy(result)
    mutated_decision = mutated["frozen_sources"]["linked_decisions"][0]
    mutated_decision["decision_link_refs"].pop()
    mutated_decision["content_id"] = _wrapped_source_content_id(mutated_decision)
    inventory = next(
        item
        for item in mutated["source_inventory"]
        if item["source_id"] == "decision-shared"
    )
    inventory["content_id"] = mutated_decision["content_id"]
    _rehash(mutated)
    validation = validate_review_input_bundle(mutated)
    assert validation["validation_status"] == "blocked"
    assert "DECISION_LINK_CLOSURE_MISMATCH" in _finding_codes(validation)


def test_decision_without_event_binding_is_not_frozen_as_available(
    chain: FixtureChain,
) -> None:
    decision = deepcopy(chain.decisions[0])
    decision.pop("event_id")
    decision.pop("relation")
    result = _build_bundle(chain, decisions=[decision])
    assert result["frozen_sources"]["linked_decisions"] == []
    assert "DECISION_EVENT_BINDING_MISSING" in _warning_codes(result)
    assert (
        result["section_availability"]["execution_consistency"]["status"]
        == "ambiguous"
    )


def test_reverse_source_double_time_is_rejected(
    chain: FixtureChain,
) -> None:
    source = deepcopy(chain.supplemental[0])
    source["effective_at"] = BASE.isoformat()
    source["knowledge_at"] = (BASE - timedelta(seconds=1)).isoformat()
    with pytest.raises(ReviewInputBundleError):
        _build_bundle(chain, supplemental=[source])


def test_source_status_is_preserved_instead_of_promoted(
    chain: FixtureChain,
) -> None:
    source = deepcopy(chain.supplemental[0])
    source["status"] = "invalid"
    result = _build_bundle(chain, supplemental=[source])
    frozen = result["frozen_sources"]["supplemental_sources"][0]
    assert frozen["availability"] == "invalid"
    assert result["section_availability"]["market_context"]["status"] == "invalid"


def test_partial_p2e3_metrics_remain_ambiguous_in_section_and_inventory(
    chain: FixtureChain,
) -> None:
    result = _build_bundle(chain)
    portfolio = result["frozen_sources"]["portfolio_context_episode_slice"]
    assert any(
        metric.get("availability") == "partial"
        for context in portfolio["contexts"]
        for metric in context.get("metrics", {}).values()
    )
    assert result["section_availability"]["portfolio_context"]["status"] == "ambiguous"
    context_inventory = [
        item
        for item in result["source_inventory"]
        if item["source_kind"] == "context"
    ]
    assert context_inventory
    assert any(item["status"] == "ambiguous" for item in context_inventory)


def test_context_and_portfolio_availability_do_not_promote_mixed_missing() -> None:
    available = {
        "context_id": "context-available",
        "portfolio_snapshot": {"status": "exact"},
        "source_binding": {
            "snapshot_binding": {"metric_availability_ceiling": "full"}
        },
        "metrics": {"nav": {"availability": "available", "warning_codes": []}},
        "warnings": [],
    }
    missing_metric = deepcopy(available)
    missing_metric["context_id"] = "context-missing"
    missing_metric["metrics"] = {
        "nav": {"availability": "missing", "warning_codes": []}
    }
    assert _context_status(missing_metric)[0] == "missing"
    section = _portfolio_section(
        {"status": "available", "contexts": [available, missing_metric]}
    )
    assert section["status"] == "ambiguous"


def test_same_time_ordering_ambiguity_propagates_to_timeline_and_inventory(
    tmp_path: Path,
) -> None:
    ambiguous_chain = _fixture_chain(
        tmp_path,
        events=[
            _event("buy-1", sequence=None),
            _event(
                "sell-1",
                at=BASE,
                side="SELL",
                sequence=None,
            ),
        ],
        decisions=[],
        supplemental=[],
    )
    result = _build_bundle(ambiguous_chain)
    timeline = result["section_availability"]["timeline"]
    assert timeline["status"] == "ambiguous"
    assert "AMBIGUOUS_EVENT_ORDER" in timeline["warning_codes"]
    event_inventory = [
        item
        for item in result["source_inventory"]
        if item["source_kind"] == "material_event"
    ]
    assert event_inventory
    assert all(item["status"] == "ambiguous" for item in event_inventory)


def test_snapshot_inventory_preserves_date_precision(bundle: dict[str, Any]) -> None:
    snapshots = [
        item for item in bundle["source_inventory"] if item["source_kind"] == "snapshot"
    ]
    assert snapshots
    assert all(item["effective_at"] is None for item in snapshots)
    assert all(item["effective_precision"] == "date" for item in snapshots)
    assert all(item["effective_date"] for item in snapshots)


def test_warning_and_exclusion_manifests_are_exactly_closed(
    chain: FixtureChain,
) -> None:
    future = _optional_source(
        "future-market",
        "market_context",
        effective_at=CUTOFF + timedelta(hours=1),
        knowledge_at=CUTOFF + timedelta(hours=1),
    )
    result = _build_bundle(chain, supplemental=[future])
    assert result["excluded_sources"] == [
        {
            "source_id": "future-market",
            "source_kind": "market_context",
            "reason_code": "MARKET_CONTEXT_WITHHELD_BY_CUTOFF",
            "effective_at": (CUTOFF + timedelta(hours=1)).isoformat().replace(
                "+00:00", "Z"
            ),
            "knowledge_at": (CUTOFF + timedelta(hours=1)).isoformat().replace(
                "+00:00", "Z"
            ),
            "payload_content_id": future["content_id"],
            "locator": future["locator"],
        }
    ]
    assert "MARKET_CONTEXT_WITHHELD_BY_CUTOFF" in _warning_codes(result)
    mutated = deepcopy(result)
    mutated["warnings"] = [
        item
        for item in mutated["warnings"]
        if item["code"] != "MARKET_CONTEXT_WITHHELD_BY_CUTOFF"
    ]
    _rehash(mutated)
    validation = validate_review_input_bundle(mutated)
    assert validation["validation_status"] == "blocked"
    assert "WARNING_CLOSURE_MISMATCH" in _finding_codes(validation)

    old_reason = "MARKET_CONTEXT_WITHHELD_BY_CUTOFF"
    new_reason = "SELF_CONSISTENT_UNKNOWN_EXCLUSION"

    def replace_reason(value: object) -> object:
        if isinstance(value, dict):
            return {
                key: replace_reason(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [replace_reason(item) for item in value]
        return new_reason if value == old_reason else value

    forged = replace_reason(deepcopy(result))
    assert isinstance(forged, dict)
    _rehash(forged)
    forged_validation = validate_review_input_bundle(forged)
    assert forged_validation["validation_status"] == "blocked"
    assert "EXCLUDED_SOURCE_SEMANTICS_INVALID" in _finding_codes(
        forged_validation
    )

    not_future = deepcopy(result)
    not_future["excluded_sources"][0]["effective_at"] = CUTOFF.isoformat().replace(
        "+00:00", "Z"
    )
    not_future["excluded_sources"][0]["knowledge_at"] = CUTOFF.isoformat().replace(
        "+00:00", "Z"
    )
    _rehash(not_future)
    not_future_validation = validate_review_input_bundle(not_future)
    assert not_future_validation["validation_status"] == "blocked"
    assert "EXCLUDED_SOURCE_SEMANTICS_INVALID" in _finding_codes(
        not_future_validation
    )


def test_legacy_p2c_projection_cannot_enter_p2f(chain: FixtureChain) -> None:
    legacy = deepcopy(chain.collection)
    legacy["projection_version"] = "p2c_v1"
    with pytest.raises(ReviewInputBundleError, match="current P2C projection"):
        build_review_input_bundle(
            legacy,
            chain.portfolio_context,
            portfolio_db=chain.portfolio_db,
            episode_id=chain.episode_id,
            review_cutoff=CUTOFF.isoformat(),
        )


@pytest.mark.parametrize(
    "payload",
    [None, {"frozen_sources": {"episode": {"ending_quantity": {"bad": 1}}}}],
)
def test_review_input_validator_is_total_for_malformed_json(payload: object) -> None:
    validation = validate_review_input_bundle(payload)  # type: ignore[arg-type]
    assert validation["validation_status"] == "blocked"
    assert validation["findings"]


def test_ambiguous_decision_linkage_is_not_degraded_by_missing_sources(
    tmp_path: Path,
) -> None:
    refs = [
        _decision_ref(
            decision_id,
            "buy-1",
            effective_at=BASE - timedelta(minutes=20 + index),
            knowledge_at=BASE - timedelta(minutes=10 + index),
        )
        for index, decision_id in enumerate(("decision-a", "decision-b"))
    ]
    ambiguous_chain = _fixture_chain(
        tmp_path,
        events=[
            _event("buy-1", decision_refs=refs),
            _event(
                "sell-1",
                at=BASE + timedelta(hours=1),
                side="SELL",
                sequence=2,
            ),
        ],
        decisions=[],
        supplemental=[],
    )
    result = _build_bundle(ambiguous_chain)
    assert (
        result["frozen_sources"]["episode"]["decision_linkage"]["status"]
        == "ambiguous"
    )
    assert (
        result["section_availability"]["execution_consistency"]["status"]
        == "ambiguous"
    )
    assert "DECISION_SOURCE_MISSING" in _warning_codes(result)


def test_invalid_decision_source_outranks_ambiguous_linkage(
    tmp_path: Path,
) -> None:
    refs = [
        _decision_ref(
            decision_id,
            "buy-1",
            effective_at=BASE - timedelta(minutes=20 + index),
            knowledge_at=BASE - timedelta(minutes=10 + index),
        )
        for index, decision_id in enumerate(("decision-a", "decision-b"))
    ]
    invalid_source = _optional_source(
        "decision-a",
        "decision",
        effective_at=BASE - timedelta(minutes=20),
        knowledge_at=BASE - timedelta(minutes=10),
        status="invalid",
        event_id="buy-1",
        relation="execution",
    )
    ambiguous_chain = _fixture_chain(
        tmp_path,
        events=[
            _event("buy-1", decision_refs=refs),
            _event(
                "sell-1",
                at=BASE + timedelta(hours=1),
                side="SELL",
                sequence=2,
            ),
        ],
        decisions=[invalid_source],
        supplemental=[],
    )
    result = _build_bundle(ambiguous_chain)
    assert result["frozen_sources"]["linked_decisions"][0]["availability"] == "invalid"
    assert (
        result["section_availability"]["execution_consistency"]["status"]
        == "invalid"
    )


def test_global_source_id_collision_is_rejected(
    chain: FixtureChain,
) -> None:
    supplemental = deepcopy(chain.supplemental[0])
    supplemental["source_id"] = "decision-1"
    supplemental["payload"]["source_id"] = "decision-1"
    supplemental["content_id"] = _value_content_id(supplemental["payload"])
    with pytest.raises(ReviewInputBundleError):
        _build_bundle(chain, supplemental=[supplemental])


def test_future_only_market_source_sets_withheld_section(
    chain: FixtureChain,
) -> None:
    future = _optional_source(
        "market-future-only",
        "market_context",
        effective_at=CUTOFF + timedelta(seconds=1),
        knowledge_at=CUTOFF + timedelta(seconds=1),
    )
    result = _build_bundle(chain, supplemental=[future])
    section = result["section_availability"]["market_context"]
    assert section["status"] == "withheld_by_cutoff"
    assert "MARKET_CONTEXT_WITHHELD_BY_CUTOFF" in section["warning_codes"]


def test_contract_only_cli_writes_artifact_but_returns_nonzero(
    tmp_path: Path,
    chain: FixtureChain,
    capsys: pytest.CaptureFixture[str],
) -> None:
    episode_path = tmp_path / "episodes.json"
    output = tmp_path / "contract-only.json"
    episode_path.write_text(
        json.dumps(chain.collection, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    assert (
        review_main(
            [
                "review-input-build",
                "--episode-artifact",
                str(episode_path),
                "--portfolio-db",
                str(chain.portfolio_db),
                "--episode-id",
                chain.episode_id,
                "--review-cutoff",
                CUTOFF.isoformat(),
                "--allow-missing-portfolio-context",
                "--output",
                str(output),
            ]
        )
        == 2
    )
    assert output.is_file()
    payload = json.loads(capsys.readouterr().out)
    assert payload["release_readiness"] == "blocked"


def test_sqlite_source_identity_includes_wal_bytes(tmp_path: Path) -> None:
    database = tmp_path / "portfolio.sqlite3"
    database.write_bytes(b"main")
    without_wal = _bundle_source_sha256(database)
    Path(str(database) + "-wal").write_bytes(b"committed-wal-state")
    with_wal = _bundle_source_sha256(database)
    assert with_wal != without_wal


def test_self_consistent_wrapper_locator_forgery_fails_source_replay(
    bundle: dict[str, Any],
    chain: FixtureChain,
) -> None:
    mutated = deepcopy(bundle)
    source = mutated["frozen_sources"]["supplemental_sources"][0]
    source["locator"] = "fixture/forged-locator.json"
    source["content_id"] = _wrapped_source_content_id(source)
    inventory = next(
        item
        for item in mutated["source_inventory"]
        if item["source_id"] == source["source_id"]
    )
    inventory["locator"] = source["locator"]
    inventory["content_id"] = source["content_id"]
    _rehash(mutated)
    assert validate_review_input_bundle(mutated)["validation_status"] != "blocked"
    replay = replay_validate_review_input_bundle(
        mutated,
        episode_collection=chain.collection,
        episode_portfolio_context=chain.portfolio_context,
        portfolio_db=chain.portfolio_db,
        decision_sources=chain.decisions,
        supplemental_sources=chain.supplemental,
    )
    assert replay["validation_status"] == "blocked"
    assert "SOURCE_REPLAY_MISMATCH" in _finding_codes(replay)
