"""Deterministic trade-episode reconstruction for personal investment review.

This module is intentionally pure.  It does not open the portfolio database, write the
review sidecar, calculate P&L, or infer decision intent / psychology.  P2D adapters are
expected to provide normalized, provenance-bearing events and opening positions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
import hashlib
import json
from typing import Iterable, Sequence


ALGORITHM_VERSION = "p2e_episode_engine.v1"


class EpisodeInputError(ValueError):
    """Raised when normalized P2D inputs violate the episode-engine contract."""


class EventSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class EpisodeStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    PARTIAL_OPENING = "partial_opening"
    CLOSED_FROM_OPENING_BALANCE = "closed_from_opening_balance"


class EpisodeEventRole(StrEnum):
    OPENING_BALANCE = "opening_balance"
    OPEN = "open"
    ADD = "add"
    REDUCE = "reduce"
    CLOSE = "close"


class SourceRecordKind(StrEnum):
    TRADE_EVENT = "trade_event"
    OPENING_POSITION = "opening_position"


def _require_text(value: str, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise EpisodeInputError(f"{field_name} must be non-empty")
    return normalized


def _positive_decimal(value: Decimal | int | str, field_name: str) -> Decimal:
    try:
        normalized = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise EpisodeInputError(f"{field_name} must be a valid decimal") from exc
    if not normalized.is_finite() or normalized <= 0:
        raise EpisodeInputError(f"{field_name} must be finite and greater than zero")
    return normalized


def _aware_datetime(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise EpisodeInputError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise EpisodeInputError(f"{field_name} must be timezone-aware")
    return value


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _digest(prefix: str, payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()[:24]}"


@dataclass(frozen=True, slots=True)
class TradeEvent:
    source_event_id: str
    account_id: str
    instrument_id: str
    occurred_at: datetime
    side: EventSide | str
    quantity: Decimal | int | str
    source_ordinal: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_event_id",
            _require_text(self.source_event_id, "source_event_id"),
        )
        object.__setattr__(self, "account_id", _require_text(self.account_id, "account_id"))
        object.__setattr__(
            self,
            "instrument_id",
            _require_text(self.instrument_id, "instrument_id"),
        )
        object.__setattr__(self, "occurred_at", _aware_datetime(self.occurred_at, "occurred_at"))
        try:
            object.__setattr__(self, "side", EventSide(self.side))
        except ValueError as exc:
            raise EpisodeInputError("side must be 'buy' or 'sell'") from exc
        object.__setattr__(self, "quantity", _positive_decimal(self.quantity, "quantity"))
        if isinstance(self.source_ordinal, bool) or not isinstance(self.source_ordinal, int):
            raise EpisodeInputError("source_ordinal must be an integer")
        if self.source_ordinal < 0:
            raise EpisodeInputError("source_ordinal must be non-negative")


@dataclass(frozen=True, slots=True)
class OpeningPosition:
    source_position_id: str
    account_id: str
    instrument_id: str
    as_of: datetime
    quantity: Decimal | int | str
    source_ordinal: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_position_id",
            _require_text(self.source_position_id, "source_position_id"),
        )
        object.__setattr__(self, "account_id", _require_text(self.account_id, "account_id"))
        object.__setattr__(
            self,
            "instrument_id",
            _require_text(self.instrument_id, "instrument_id"),
        )
        object.__setattr__(self, "as_of", _aware_datetime(self.as_of, "as_of"))
        object.__setattr__(self, "quantity", _positive_decimal(self.quantity, "quantity"))
        if isinstance(self.source_ordinal, bool) or not isinstance(self.source_ordinal, int):
            raise EpisodeInputError("source_ordinal must be an integer")
        if self.source_ordinal < 0:
            raise EpisodeInputError("source_ordinal must be non-negative")


@dataclass(frozen=True, slots=True)
class EpisodeAllocation:
    source_record_id: str
    source_record_kind: SourceRecordKind
    role: EpisodeEventRole
    occurred_at: datetime
    quantity: Decimal
    source_ordinal: int

    def to_dict(self) -> dict[str, object]:
        return {
            "source_record_id": self.source_record_id,
            "source_record_kind": self.source_record_kind.value,
            "role": self.role.value,
            "occurred_at": self.occurred_at.isoformat(),
            "quantity": _decimal_text(self.quantity),
            "source_ordinal": self.source_ordinal,
        }


@dataclass(frozen=True, slots=True)
class TradeEpisode:
    episode_id: str
    account_id: str
    instrument_id: str
    status: EpisodeStatus
    opened_at: datetime
    closed_at: datetime | None
    quantity_opened: Decimal
    quantity_closed: Decimal
    quantity_remaining: Decimal
    allocations: tuple[EpisodeAllocation, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "episode_id": self.episode_id,
            "account_id": self.account_id,
            "instrument_id": self.instrument_id,
            "status": self.status.value,
            "opened_at": self.opened_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "quantity_opened": _decimal_text(self.quantity_opened),
            "quantity_closed": _decimal_text(self.quantity_closed),
            "quantity_remaining": _decimal_text(self.quantity_remaining),
            "allocations": [allocation.to_dict() for allocation in self.allocations],
        }


@dataclass(frozen=True, slots=True)
class EpisodeAnomaly:
    anomaly_id: str
    code: str
    account_id: str
    instrument_id: str
    occurred_at: datetime
    source_event_id: str
    unmatched_quantity: Decimal
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "anomaly_id": self.anomaly_id,
            "code": self.code,
            "account_id": self.account_id,
            "instrument_id": self.instrument_id,
            "occurred_at": self.occurred_at.isoformat(),
            "source_event_id": self.source_event_id,
            "unmatched_quantity": _decimal_text(self.unmatched_quantity),
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class EpisodeBuildResult:
    build_id: str
    source_snapshot_id: str
    algorithm_version: str
    episodes: tuple[TradeEpisode, ...]
    anomalies: tuple[EpisodeAnomaly, ...]

    def to_manifest(self) -> dict[str, object]:
        return {
            "build_id": self.build_id,
            "source_snapshot_id": self.source_snapshot_id,
            "algorithm_version": self.algorithm_version,
            "episode_count": len(self.episodes),
            "anomaly_count": len(self.anomalies),
            "episodes": [episode.to_dict() for episode in self.episodes],
            "anomalies": [anomaly.to_dict() for anomaly in self.anomalies],
        }


@dataclass(slots=True)
class _EpisodeState:
    episode_id: str
    account_id: str
    instrument_id: str
    opened_at: datetime
    opened_from_balance: bool
    quantity_opened: Decimal = Decimal("0")
    quantity_closed: Decimal = Decimal("0")
    quantity_remaining: Decimal = Decimal("0")
    allocations: list[EpisodeAllocation] = field(default_factory=list)

    def freeze(self, *, closed_at: datetime | None) -> TradeEpisode:
        if closed_at is None:
            status = (
                EpisodeStatus.PARTIAL_OPENING
                if self.opened_from_balance
                else EpisodeStatus.OPEN
            )
        else:
            status = (
                EpisodeStatus.CLOSED_FROM_OPENING_BALANCE
                if self.opened_from_balance
                else EpisodeStatus.CLOSED
            )
        return TradeEpisode(
            episode_id=self.episode_id,
            account_id=self.account_id,
            instrument_id=self.instrument_id,
            status=status,
            opened_at=self.opened_at,
            closed_at=closed_at,
            quantity_opened=self.quantity_opened,
            quantity_closed=self.quantity_closed,
            quantity_remaining=self.quantity_remaining,
            allocations=tuple(self.allocations),
        )


def _event_sort_key(event: TradeEvent) -> tuple[datetime, int, str]:
    return (event.occurred_at, event.source_ordinal, event.source_event_id)


def _opening_sort_key(position: OpeningPosition) -> tuple[datetime, int, str]:
    return (position.as_of, position.source_ordinal, position.source_position_id)


def _episode_id(
    *,
    source_snapshot_id: str,
    algorithm_version: str,
    account_id: str,
    instrument_id: str,
    anchor_kind: SourceRecordKind,
    anchor_id: str,
    anchor_ordinal: int,
) -> str:
    return _digest(
        "episode",
        {
            "source_snapshot_id": source_snapshot_id,
            "algorithm_version": algorithm_version,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "anchor_kind": anchor_kind.value,
            "anchor_id": anchor_id,
            "anchor_ordinal": anchor_ordinal,
        },
    )


def _build_id(
    *,
    source_snapshot_id: str,
    algorithm_version: str,
    events: Sequence[TradeEvent],
    opening_positions: Sequence[OpeningPosition],
) -> str:
    return _digest(
        "episode_build",
        {
            "source_snapshot_id": source_snapshot_id,
            "algorithm_version": algorithm_version,
            "events": [
                {
                    "source_event_id": event.source_event_id,
                    "account_id": event.account_id,
                    "instrument_id": event.instrument_id,
                    "occurred_at": event.occurred_at.isoformat(),
                    "side": event.side.value,
                    "quantity": _decimal_text(event.quantity),
                    "source_ordinal": event.source_ordinal,
                }
                for event in events
            ],
            "opening_positions": [
                {
                    "source_position_id": position.source_position_id,
                    "account_id": position.account_id,
                    "instrument_id": position.instrument_id,
                    "as_of": position.as_of.isoformat(),
                    "quantity": _decimal_text(position.quantity),
                    "source_ordinal": position.source_ordinal,
                }
                for position in opening_positions
            ],
        },
    )


def reconstruct_trade_episodes(
    events: Iterable[TradeEvent],
    *,
    source_snapshot_id: str,
    opening_positions: Iterable[OpeningPosition] = (),
    algorithm_version: str = ALGORITHM_VERSION,
) -> EpisodeBuildResult:
    """Reconstruct long-only execution episodes from normalized evidence records.

    The engine never invents an opening trade.  A sell without sufficient known opening
    quantity is preserved as an ``unmatched_sell_quantity`` anomaly.  It also does not
    calculate cost basis, realized P&L, decision rationale, or behavioral explanations.
    """

    snapshot_id = _require_text(source_snapshot_id, "source_snapshot_id")
    version = _require_text(algorithm_version, "algorithm_version")
    event_list = sorted(
        tuple(events),
        key=lambda item: (
            item.account_id,
            item.instrument_id,
            *_event_sort_key(item),
        ),
    )
    opening_list = sorted(
        tuple(opening_positions),
        key=lambda item: (item.account_id, item.instrument_id, *_opening_sort_key(item)),
    )

    event_ids = [event.source_event_id for event in event_list]
    if len(event_ids) != len(set(event_ids)):
        raise EpisodeInputError("source_event_id values must be globally unique")
    position_ids = [position.source_position_id for position in opening_list]
    if len(position_ids) != len(set(position_ids)):
        raise EpisodeInputError("source_position_id values must be globally unique")

    openings_by_key: dict[tuple[str, str], OpeningPosition] = {}
    for position in opening_list:
        key = (position.account_id, position.instrument_id)
        if key in openings_by_key:
            raise EpisodeInputError(
                "at most one opening position is allowed per account_id/instrument_id"
            )
        openings_by_key[key] = position

    events_by_key: dict[tuple[str, str], list[TradeEvent]] = {}
    for event in event_list:
        events_by_key.setdefault((event.account_id, event.instrument_id), []).append(event)

    episodes: list[TradeEpisode] = []
    anomalies: list[EpisodeAnomaly] = []
    keys = sorted(set(events_by_key) | set(openings_by_key))

    for account_id, instrument_id in keys:
        key = (account_id, instrument_id)
        opening = openings_by_key.get(key)
        key_events = events_by_key.get(key, [])
        state: _EpisodeState | None = None

        if opening is not None:
            if key_events and key_events[0].occurred_at < opening.as_of:
                raise EpisodeInputError(
                    "opening position as_of must not be later than the first event for its key"
                )
            state = _EpisodeState(
                episode_id=_episode_id(
                    source_snapshot_id=snapshot_id,
                    algorithm_version=version,
                    account_id=account_id,
                    instrument_id=instrument_id,
                    anchor_kind=SourceRecordKind.OPENING_POSITION,
                    anchor_id=opening.source_position_id,
                    anchor_ordinal=opening.source_ordinal,
                ),
                account_id=account_id,
                instrument_id=instrument_id,
                opened_at=opening.as_of,
                opened_from_balance=True,
                quantity_opened=opening.quantity,
                quantity_remaining=opening.quantity,
                allocations=[
                    EpisodeAllocation(
                        source_record_id=opening.source_position_id,
                        source_record_kind=SourceRecordKind.OPENING_POSITION,
                        role=EpisodeEventRole.OPENING_BALANCE,
                        occurred_at=opening.as_of,
                        quantity=opening.quantity,
                        source_ordinal=opening.source_ordinal,
                    )
                ],
            )

        for event in key_events:
            if event.side is EventSide.BUY:
                if state is None:
                    state = _EpisodeState(
                        episode_id=_episode_id(
                            source_snapshot_id=snapshot_id,
                            algorithm_version=version,
                            account_id=account_id,
                            instrument_id=instrument_id,
                            anchor_kind=SourceRecordKind.TRADE_EVENT,
                            anchor_id=event.source_event_id,
                            anchor_ordinal=event.source_ordinal,
                        ),
                        account_id=account_id,
                        instrument_id=instrument_id,
                        opened_at=event.occurred_at,
                        opened_from_balance=False,
                    )
                    role = EpisodeEventRole.OPEN
                else:
                    role = EpisodeEventRole.ADD
                state.quantity_opened += event.quantity
                state.quantity_remaining += event.quantity
                state.allocations.append(
                    EpisodeAllocation(
                        source_record_id=event.source_event_id,
                        source_record_kind=SourceRecordKind.TRADE_EVENT,
                        role=role,
                        occurred_at=event.occurred_at,
                        quantity=event.quantity,
                        source_ordinal=event.source_ordinal,
                    )
                )
                continue

            unmatched = event.quantity
            if state is not None and state.quantity_remaining > 0:
                matched = min(unmatched, state.quantity_remaining)
                role = (
                    EpisodeEventRole.CLOSE
                    if matched == state.quantity_remaining
                    else EpisodeEventRole.REDUCE
                )
                state.quantity_closed += matched
                state.quantity_remaining -= matched
                state.allocations.append(
                    EpisodeAllocation(
                        source_record_id=event.source_event_id,
                        source_record_kind=SourceRecordKind.TRADE_EVENT,
                        role=role,
                        occurred_at=event.occurred_at,
                        quantity=matched,
                        source_ordinal=event.source_ordinal,
                    )
                )
                unmatched -= matched
                if state.quantity_remaining == 0:
                    episodes.append(state.freeze(closed_at=event.occurred_at))
                    state = None

            if unmatched > 0:
                anomaly_id = _digest(
                    "episode_anomaly",
                    {
                        "source_snapshot_id": snapshot_id,
                        "algorithm_version": version,
                        "source_event_id": event.source_event_id,
                        "code": "unmatched_sell_quantity",
                        "unmatched_quantity": _decimal_text(unmatched),
                    },
                )
                anomalies.append(
                    EpisodeAnomaly(
                        anomaly_id=anomaly_id,
                        code="unmatched_sell_quantity",
                        account_id=account_id,
                        instrument_id=instrument_id,
                        occurred_at=event.occurred_at,
                        source_event_id=event.source_event_id,
                        unmatched_quantity=unmatched,
                        message=(
                            "Sell quantity exceeds the opening quantity known to this build; "
                            "no synthetic buy or short episode was created."
                        ),
                    )
                )

        if state is not None:
            episodes.append(state.freeze(closed_at=None))

    episodes.sort(
        key=lambda item: (
            item.account_id,
            item.instrument_id,
            item.opened_at,
            item.episode_id,
        )
    )
    anomalies.sort(
        key=lambda item: (
            item.account_id,
            item.instrument_id,
            item.occurred_at,
            item.source_event_id,
            item.anomaly_id,
        )
    )
    build_id = _build_id(
        source_snapshot_id=snapshot_id,
        algorithm_version=version,
        events=event_list,
        opening_positions=opening_list,
    )
    return EpisodeBuildResult(
        build_id=build_id,
        source_snapshot_id=snapshot_id,
        algorithm_version=version,
        episodes=tuple(episodes),
        anomalies=tuple(anomalies),
    )
