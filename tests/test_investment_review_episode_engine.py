from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import random

import pytest

from src.portfolio.investment_review_episode_engine import (
    EpisodeEventRole,
    EpisodeInputError,
    EpisodeStatus,
    OpeningPosition,
    TradeEvent,
    reconstruct_trade_episodes,
)


BASE = datetime(2026, 7, 1, 1, 30, tzinfo=timezone.utc)


def event(
    event_id: str,
    *,
    hour: int,
    side: str,
    quantity: str,
    account: str = "acct-1",
    instrument: str = "600000.SH",
    ordinal: int = 0,
) -> TradeEvent:
    return TradeEvent(
        source_event_id=event_id,
        account_id=account,
        instrument_id=instrument,
        occurred_at=BASE + timedelta(hours=hour),
        side=side,
        quantity=quantity,
        source_ordinal=ordinal,
    )


def test_single_round_trip_closes_one_episode() -> None:
    result = reconstruct_trade_episodes(
        [
            event("buy-1", hour=1, side="buy", quantity="100"),
            event("sell-1", hour=2, side="sell", quantity="100"),
        ],
        source_snapshot_id="snapshot-1",
    )

    assert len(result.episodes) == 1
    episode = result.episodes[0]
    assert episode.status is EpisodeStatus.CLOSED
    assert episode.quantity_opened == Decimal("100")
    assert episode.quantity_closed == Decimal("100")
    assert episode.quantity_remaining == Decimal("0")
    assert [item.role for item in episode.allocations] == [
        EpisodeEventRole.OPEN,
        EpisodeEventRole.CLOSE,
    ]
    assert result.anomalies == ()


def test_scale_in_and_scale_out_preserves_event_roles() -> None:
    result = reconstruct_trade_episodes(
        [
            event("buy-1", hour=1, side="buy", quantity="100"),
            event("buy-2", hour=2, side="buy", quantity="50"),
            event("sell-1", hour=3, side="sell", quantity="40"),
            event("sell-2", hour=4, side="sell", quantity="110"),
        ],
        source_snapshot_id="snapshot-1",
    )

    episode = result.episodes[0]
    assert episode.status is EpisodeStatus.CLOSED
    assert [item.role for item in episode.allocations] == [
        EpisodeEventRole.OPEN,
        EpisodeEventRole.ADD,
        EpisodeEventRole.REDUCE,
        EpisodeEventRole.CLOSE,
    ]
    assert episode.quantity_opened == Decimal("150")
    assert episode.quantity_closed == Decimal("150")


def test_opening_position_is_explicit_partial_episode() -> None:
    opening = OpeningPosition(
        source_position_id="opening-1",
        account_id="acct-1",
        instrument_id="600000.SH",
        as_of=BASE,
        quantity="80",
    )
    result = reconstruct_trade_episodes(
        [event("sell-1", hour=1, side="sell", quantity="30")],
        source_snapshot_id="snapshot-1",
        opening_positions=[opening],
    )

    episode = result.episodes[0]
    assert episode.status is EpisodeStatus.PARTIAL_OPENING
    assert episode.quantity_remaining == Decimal("50")
    assert episode.allocations[0].role is EpisodeEventRole.OPENING_BALANCE
    assert episode.allocations[1].role is EpisodeEventRole.REDUCE


def test_opening_position_can_close_without_inventing_prior_buy() -> None:
    opening = OpeningPosition(
        source_position_id="opening-1",
        account_id="acct-1",
        instrument_id="600000.SH",
        as_of=BASE,
        quantity="80",
    )
    result = reconstruct_trade_episodes(
        [event("sell-1", hour=1, side="sell", quantity="80")],
        source_snapshot_id="snapshot-1",
        opening_positions=[opening],
    )

    assert result.episodes[0].status is EpisodeStatus.CLOSED_FROM_OPENING_BALANCE
    assert result.anomalies == ()


def test_unmatched_sell_becomes_anomaly_not_short_episode() -> None:
    result = reconstruct_trade_episodes(
        [event("sell-1", hour=1, side="sell", quantity="25")],
        source_snapshot_id="snapshot-1",
    )

    assert result.episodes == ()
    assert len(result.anomalies) == 1
    assert result.anomalies[0].code == "unmatched_sell_quantity"
    assert result.anomalies[0].unmatched_quantity == Decimal("25")


def test_oversell_closes_known_episode_and_preserves_excess_as_anomaly() -> None:
    result = reconstruct_trade_episodes(
        [
            event("buy-1", hour=1, side="buy", quantity="10"),
            event("sell-1", hour=2, side="sell", quantity="12"),
        ],
        source_snapshot_id="snapshot-1",
    )

    assert result.episodes[0].status is EpisodeStatus.CLOSED
    assert result.episodes[0].quantity_closed == Decimal("10")
    assert result.anomalies[0].unmatched_quantity == Decimal("2")


def test_buy_after_close_starts_a_new_episode() -> None:
    result = reconstruct_trade_episodes(
        [
            event("buy-1", hour=1, side="buy", quantity="10"),
            event("sell-1", hour=2, side="sell", quantity="10"),
            event("buy-2", hour=3, side="buy", quantity="20"),
        ],
        source_snapshot_id="snapshot-1",
    )

    assert len(result.episodes) == 2
    assert result.episodes[0].status is EpisodeStatus.CLOSED
    assert result.episodes[1].status is EpisodeStatus.OPEN
    assert result.episodes[0].episode_id != result.episodes[1].episode_id


def test_same_timestamp_uses_source_ordinal_then_source_id() -> None:
    first = event("buy-z", hour=1, side="buy", quantity="10", ordinal=1)
    second = event("sell-a", hour=1, side="sell", quantity="10", ordinal=2)
    result = reconstruct_trade_episodes(
        [second, first],
        source_snapshot_id="snapshot-1",
    )

    assert len(result.episodes) == 1
    assert result.episodes[0].status is EpisodeStatus.CLOSED
    assert result.anomalies == ()


def test_build_and_episode_ids_are_deterministic_for_shuffled_input() -> None:
    records = [
        event("buy-1", hour=1, side="buy", quantity="10"),
        event("sell-1", hour=2, side="sell", quantity="10"),
        event("buy-2", hour=3, side="buy", quantity="5"),
    ]
    shuffled = records.copy()
    random.Random(42).shuffle(shuffled)

    first = reconstruct_trade_episodes(records, source_snapshot_id="snapshot-1")
    second = reconstruct_trade_episodes(shuffled, source_snapshot_id="snapshot-1")

    assert first.build_id == second.build_id
    assert [item.episode_id for item in first.episodes] == [
        item.episode_id for item in second.episodes
    ]
    assert first.to_manifest() == second.to_manifest()


def test_accounts_and_instruments_are_partitioned() -> None:
    result = reconstruct_trade_episodes(
        [
            event("a-buy", hour=1, side="buy", quantity="10", account="acct-a"),
            event("b-buy", hour=1, side="buy", quantity="20", account="acct-b"),
            event(
                "c-buy",
                hour=1,
                side="buy",
                quantity="30",
                account="acct-a",
                instrument="000001.SZ",
            ),
        ],
        source_snapshot_id="snapshot-1",
    )

    assert len(result.episodes) == 3
    assert {
        (item.account_id, item.instrument_id, item.quantity_remaining)
        for item in result.episodes
    } == {
        ("acct-a", "600000.SH", Decimal("10")),
        ("acct-b", "600000.SH", Decimal("20")),
        ("acct-a", "000001.SZ", Decimal("30")),
    }


def test_duplicate_source_event_ids_are_rejected() -> None:
    with pytest.raises(EpisodeInputError, match="globally unique"):
        reconstruct_trade_episodes(
            [
                event("duplicate", hour=1, side="buy", quantity="10"),
                event("duplicate", hour=2, side="sell", quantity="10"),
            ],
            source_snapshot_id="snapshot-1",
        )


@pytest.mark.parametrize("quantity", ["0", "-1", "NaN", "Infinity"])
def test_non_positive_or_non_finite_quantity_is_rejected(quantity: str) -> None:
    with pytest.raises(EpisodeInputError):
        event("bad", hour=1, side="buy", quantity=quantity)


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(EpisodeInputError, match="timezone-aware"):
        TradeEvent(
            source_event_id="bad-time",
            account_id="acct-1",
            instrument_id="600000.SH",
            occurred_at=datetime(2026, 7, 1, 9, 30),
            side="buy",
            quantity="10",
        )


def test_opening_snapshot_cannot_postdate_first_event() -> None:
    opening = OpeningPosition(
        source_position_id="opening-1",
        account_id="acct-1",
        instrument_id="600000.SH",
        as_of=BASE + timedelta(hours=2),
        quantity="80",
    )
    with pytest.raises(EpisodeInputError, match="must not be later"):
        reconstruct_trade_episodes(
            [event("buy-1", hour=1, side="buy", quantity="10")],
            source_snapshot_id="snapshot-1",
            opening_positions=[opening],
        )


def test_manifest_contains_no_pnl_or_behavioral_inference_fields() -> None:
    result = reconstruct_trade_episodes(
        [event("buy-1", hour=1, side="buy", quantity="10")],
        source_snapshot_id="snapshot-1",
    )
    serialized = str(result.to_manifest()).lower()

    assert "pnl" not in serialized
    assert "emotion" not in serialized
    assert "psychology" not in serialized
    assert "decision_reason" not in serialized
