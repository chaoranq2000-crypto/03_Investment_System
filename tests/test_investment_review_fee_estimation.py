from __future__ import annotations

from decimal import Decimal

import pytest

from src.investment_review.fee_estimation import (
    FEE_METHOD,
    FEE_METHOD_VERSION,
    SOURCE_ACTUAL_METHOD_VERSION,
    FeeEstimationError,
    FeeObservation,
    build_fee_profile,
    estimate_fee,
    project_fees,
)


def _observation(
    event_id: str,
    *,
    account_id: str = "acct-a",
    asset_type: str = "equity",
    side: str = "BUY",
    gross_amount: str = "10000",
    source_fees: str | None = "10",
    actual: bool = True,
) -> FeeObservation:
    return FeeObservation.build(
        event_id=event_id,
        account_id=account_id,
        asset_type=asset_type,
        side=side,
        gross_amount=gross_amount,
        source_fees=source_fees,
        source_fee_actual=actual,
        source_fee_provenance={"source": "portfolio.ledger_entries"},
    )


def _rate_samples(
    rates: list[str],
    *,
    account_ids: list[str] | None = None,
    side: str = "BUY",
    asset_type: str = "equity",
) -> list[FeeObservation]:
    accounts = account_ids or ["acct-a"] * len(rates)
    return [
        _observation(
            f"sample-{index}",
            account_id=accounts[index],
            asset_type=asset_type,
            side=side,
            gross_amount="10000",
            source_fees=str(Decimal("10000") * Decimal(rate)),
        )
        for index, rate in enumerate(rates)
    ]


def test_positive_fee_requires_explicit_actual_provenance() -> None:
    actual = _observation("actual", source_fees="1.235", actual=True)
    projection = estimate_fee(actual)

    assert projection.status == "actual"
    assert projection.amount == Decimal("1.235")
    assert projection.source_fees == Decimal("1.235")
    assert projection.method_version == SOURCE_ACTUAL_METHOD_VERSION
    assert projection.sample_count == 0
    assert projection.provenance["source_fee_actual"] is True
    assert projection.to_dict()["source_fees"] == "1.235"
    assert projection.to_dict()["amount"] == "1.235"

    unconfirmed = _observation("unconfirmed", source_fees="1.23", actual=False)
    missing_projection = estimate_fee(unconfirmed)
    assert missing_projection.status == "unknown"
    assert missing_projection.source_fees == Decimal("1.23")
    assert missing_projection.reason_code == "INSUFFICIENT_ACTUAL_SAMPLES"


def test_account_asset_side_median_profile_is_used_when_it_has_five_samples() -> None:
    samples = _rate_samples(["0.001", "0.005", "0.003", "0.002", "0.004"])
    target = _observation(
        "target",
        gross_amount="2000",
        source_fees=None,
        actual=False,
    )

    profile = build_fee_profile(
        samples,
        account_id="acct-a",
        asset_type="equity",
        side="BUY",
    )
    projection = estimate_fee(target, samples)

    assert profile is not None
    assert profile.rate == Decimal("0.003")
    assert profile.fallback_level == "account_asset_type_side"
    assert profile.sample_count == 5
    assert profile.sample_event_ids == tuple(sorted(item.event_id for item in samples))
    assert projection.status == "estimated"
    assert projection.amount == Decimal("6.00")
    assert projection.method == FEE_METHOD
    assert projection.method_version == FEE_METHOD_VERSION
    assert projection.profile_id == profile.profile_id
    assert projection.sample_count == 5
    assert projection.provenance["median_rate"] == "0.003"


def test_falls_back_to_asset_type_and_side_when_account_sample_is_insufficient() -> None:
    samples = _rate_samples(
        ["0.001", "0.002", "0.003", "0.004", "0.005", "0.006"],
        account_ids=["acct-a", "acct-a", "acct-b", "acct-b", "acct-c", "acct-c"],
    )
    target = _observation(
        "target",
        account_id="acct-a",
        gross_amount="2000",
        source_fees=None,
        actual=False,
    )

    projection = estimate_fee(target, samples)

    assert projection.status == "estimated"
    assert projection.amount == Decimal("7.00")
    assert projection.sample_count == 6
    assert projection.provenance["fallback_level"] == "asset_type_side"
    assert projection.provenance["median_rate"] == "0.0035"


def test_zero_source_fee_is_not_actual_and_source_value_is_not_overwritten() -> None:
    samples = _rate_samples(["0.001"] * 5)
    target = _observation("zero-fee", source_fees="0", actual=True, gross_amount="1000")

    projection = estimate_fee(target, samples)

    assert projection.status == "estimated"
    assert projection.amount == Decimal("1.00")
    assert projection.source_fees == Decimal("0")
    assert projection.to_dict()["source_fees"] == "0"
    assert projection.provenance["source_fee_preserved"] == "0"


@pytest.mark.parametrize(
    ("target", "samples", "reason", "sample_count"),
    [
        (
            _observation("few", source_fees=None, actual=False),
            _rate_samples(["0.001"] * 4),
            "INSUFFICIENT_ACTUAL_SAMPLES",
            4,
        ),
        (
            _observation("no-gross", gross_amount="0", source_fees=None, actual=False),
            _rate_samples(["0.001"] * 5),
            "INVALID_GROSS_AMOUNT",
            0,
        ),
        (
            _observation(
                "unknown-asset",
                asset_type="unknown",
                source_fees=None,
                actual=False,
            ),
            _rate_samples(["0.001"] * 5),
            "UNRECOGNIZED_ASSET_TYPE",
            0,
        ),
        (
            _observation("cash-event", side="OTHER", source_fees="2", actual=True),
            _rate_samples(["0.001"] * 5),
            "UNSUPPORTED_SIDE",
            0,
        ),
    ],
)
def test_invalid_or_unsupported_inputs_remain_unknown(
    target: FeeObservation,
    samples: list[FeeObservation],
    reason: str,
    sample_count: int,
) -> None:
    projection = estimate_fee(target, samples)

    assert projection.status == "unknown"
    assert projection.amount is None
    assert projection.reason_code == reason
    assert projection.sample_count == sample_count
    assert projection.method_version == FEE_METHOD_VERSION
    assert projection.provenance["reason_code"] == reason


def test_estimate_rounds_to_one_cent_with_decimal_half_up() -> None:
    samples = _rate_samples(["0.001235"] * 5)
    target = _observation(
        "round-half-up",
        gross_amount="1000",
        source_fees=None,
        actual=False,
    )

    projection = estimate_fee(target, samples)

    assert projection.status == "estimated"
    assert projection.amount == Decimal("1.24")
    assert projection.to_dict()["amount"] == "1.24"
    assert projection.provenance["rounding"] == "0.01_CNY_ROUND_HALF_UP"


def test_batch_projection_is_permutation_invariant_and_provenance_is_stable() -> None:
    samples = _rate_samples(["0.004", "0.001", "0.003", "0.005", "0.002"])
    targets = [
        _observation("target-b", source_fees="0", actual=False, gross_amount="3000"),
        _observation("target-a", source_fees=None, actual=False, gross_amount="2000"),
    ]

    first = project_fees(targets, samples)
    second = project_fees(reversed(targets), reversed(samples))

    assert [item.event_id for item in first] == ["target-a", "target-b"]
    assert [item.to_dict() for item in first] == [item.to_dict() for item in second]
    assert first[0].provenance["sample_event_ids"] == sorted(item.event_id for item in samples)


def test_duplicate_identity_with_content_drift_is_rejected() -> None:
    first = _observation("same-id", gross_amount="10000", source_fees="10")
    drifted = _observation("same-id", gross_amount="20000", source_fees="10")
    target = _observation("target", source_fees=None, actual=False)

    with pytest.raises(FeeEstimationError, match="conflicting fee observation"):
        estimate_fee(target, [first, drifted])


def test_method_does_not_allow_the_five_sample_floor_to_be_weakened() -> None:
    target = _observation("target", source_fees=None, actual=False)

    with pytest.raises(FeeEstimationError, match="requires min_sample_count=5"):
        estimate_fee(target, _rate_samples(["0.001"] * 4), min_sample_count=4)
