from __future__ import annotations

from copy import deepcopy

from src.investment_review.periodic_reports import infer_motive_hypothesis


def _operation(
    *,
    operation_id: str,
    occurred_at: str,
    side: str,
    quantity: str,
    price: str,
    before: str,
    after: str,
) -> dict[str, str]:
    return {
        "operation_id": operation_id,
        "occurred_at": occurred_at,
        "side": side,
        "ts_code": "000001.SZ",
        "quantity": quantity,
        "price_cny": price,
        "quantity_before": before,
        "quantity_after": after,
        "source_ref": f"portfolio.sqlite3#ledger_entries:{operation_id}",
    }


PRIOR_CLOSES = [
    {
        "trade_date": "2026-07-14",
        "close": "10.8",
        "source_ref": "portfolio.sqlite3#close_prices:000001.SZ:2026-07-14",
    },
    {
        "trade_date": "2026-07-13",
        "close": "10.5",
        "source_ref": "portfolio.sqlite3#close_prices:000001.SZ:2026-07-13",
    },
    {
        "trade_date": "2026-07-10",
        "close": "10.2",
        "source_ref": "portfolio.sqlite3#close_prices:000001.SZ:2026-07-10",
    },
]


def test_first_operation_is_unchanged_when_a_future_operation_is_present() -> None:
    first = _operation(
        operation_id="first",
        occurred_at="2026-07-15T01:35:00Z",
        side="BUY",
        quantity="20",
        price="11",
        before="100",
        after="120",
    )
    future = _operation(
        operation_id="future",
        occurred_at="2026-07-15T02:10:00Z",
        side="SELL",
        quantity="20",
        price="11.1",
        before="120",
        after="100",
    )

    without_future = infer_motive_hypothesis(
        first,
        earlier_operations=[],
        prior_closes=PRIOR_CLOSES,
        position_weight_before_pct="10",
    )
    with_future = infer_motive_hypothesis(
        first,
        earlier_operations=[deepcopy(future)],
        prior_closes=PRIOR_CLOSES,
        position_weight_before_pct="10",
    )

    assert with_future == without_future
    assert with_future["label"] == "system_inference"
    assert with_future["input_cutoff_at"] == first["occurred_at"]
    assert with_future["uses_later_information"] is False
    assert with_future["confidence"] == "medium"
    assert with_future["alternative_explanations"]
    assert "MISSING_DECISION" in with_future["important_missing_information"]


def test_reduce_after_same_day_buys_is_a_labeled_hypothesis_not_user_fact() -> None:
    first_buy = _operation(
        operation_id="buy-1",
        occurred_at="2026-07-15T01:35:00Z",
        side="BUY",
        quantity="20",
        price="11",
        before="100",
        after="120",
    )
    second_buy = _operation(
        operation_id="buy-2",
        occurred_at="2026-07-15T01:50:00Z",
        side="BUY",
        quantity="30",
        price="11.05",
        before="120",
        after="150",
    )
    sell = _operation(
        operation_id="sell",
        occurred_at="2026-07-15T02:10:00Z",
        side="SELL",
        quantity="50",
        price="11.1",
        before="150",
        after="100",
    )

    motive = infer_motive_hypothesis(
        sell,
        earlier_operations=[first_buy, second_buy],
        prior_closes=PRIOR_CLOSES,
        position_weight_before_pct="15",
    )

    assert motive["label"] == "system_inference"
    assert "做 T" in motive["most_likely_motive"]
    assert motive["alternative_explanations"]
    assert all(
        observation["observed_at"] <= sell["occurred_at"]
        for observation in motive["supporting_observations"]
    )
