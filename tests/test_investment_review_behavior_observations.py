from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Mapping

import pytest

from src.investment_review.artifact_io import canonical_json_bytes
from src.investment_review.behavior_cohort import (
    build_behavior_cohort,
    save_behavior_cohort,
)
from src.investment_review.behavior_observations import (
    DETECTOR_IDS,
    EVALUATION_STATUSES,
    BehaviorObservationError,
    build_behavior_observation_set,
    load_behavior_observation_set,
    query_behavior_observation_set,
    replay_validate_behavior_observation_set,
    save_behavior_observation_set,
    validate_behavior_observation_set,
)
from src.investment_review.cli import main as review_main
from src.investment_review.episode_review import build_facts_only_episode_review
from src.investment_review import behavior_observations as observation_module


UTC = timezone.utc
CUTOFF = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)


def _load_p2f_helpers() -> ModuleType:
    module_name = "_investment_review_p2g2_fixture_helpers"
    existing = sys.modules.get(module_name)
    if isinstance(existing, ModuleType):
        return existing
    source_path = Path(__file__).with_name(
        "test_investment_review_review_input_bundle.py"
    )
    spec = importlib.util.spec_from_file_location(module_name, source_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


P2F1 = _load_p2f_helpers()


def _instrument_position(
    instrument_id: str,
    quantity: str,
    *,
    price: str = "10",
) -> dict[str, Any]:
    market_value = Decimal(quantity) * Decimal(price)
    row = P2F1._position(
        quantity=quantity,
        price=price,
        market_value=str(market_value),
        price_known_at=datetime(2026, 6, 30, 23, 0, tzinfo=UTC),
    )
    row["ts_code"] = instrument_id
    row["cost_basis"] = str(market_value)
    row["average_cost"] = price
    row["portfolio_weight"] = str(market_value / Decimal("10000"))
    return row


def _event(
    event_id: str,
    *,
    at: datetime,
    side: str,
    quantity: str,
    sequence: int,
    account_id: str,
    instrument_id: str,
    currency: str,
    known_at: datetime | None = None,
) -> dict[str, Any]:
    row = P2F1._event(
        event_id,
        at=at,
        known_at=known_at,
        side=side,
        quantity=quantity,
        sequence=sequence,
        decision_refs=(),
    )
    row["account"] = account_id
    row["symbol"] = instrument_id
    row["currency"] = currency
    row["source_record_id"] = f"{account_id}::{event_id}"
    source_row = row["raw_payload"]["source_row"]
    source_row["account_id"] = account_id
    source_row["external_id"] = event_id
    source_row["dedupe_key"] = f"dk-{event_id}"
    return row


def _snapshot(
    snapshot_id: str,
    *,
    known_at: datetime,
    included: Iterable[str],
    account_id: str,
    instrument_id: str,
    currency: str,
    quantity: str | None,
) -> dict[str, Any]:
    market_value = Decimal(quantity or "0") * Decimal("10")
    positions = (
        []
        if quantity is None
        else [_instrument_position(instrument_id, quantity)]
    )
    row = P2F1._snapshot(
        snapshot_id,
        known_at=known_at,
        included=included,
        cash=str(Decimal("10000") - market_value),
        market_value=str(market_value),
        positions=positions,
    )
    row["account_id"] = account_id
    row["currency"] = currency
    row["cost_basis"] = str(market_value)
    return row


def _episode_artifacts(
    root: Path,
    name: str,
    *,
    opened_at: datetime,
    closed_at: datetime | None,
    quantity: str = "100",
    account_id: str = "acct-1",
    instrument_id: str = "600000.SH",
    currency: str = "CNY",
    exact_cursor: bool = True,
    close_known_at: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    work = root / name
    work.mkdir(parents=True, exist_ok=True)
    buy_id = f"{name}-buy"
    sell_id = f"{name}-sell"
    events = [
        _event(
            buy_id,
            at=opened_at,
            side="BUY",
            quantity=quantity,
            sequence=1,
            account_id=account_id,
            instrument_id=instrument_id,
            currency=currency,
        )
    ]
    if closed_at is not None:
        events.append(
            _event(
                sell_id,
                at=closed_at,
                side="SELL",
                quantity=quantity,
                sequence=2,
                account_id=account_id,
                instrument_id=instrument_id,
                currency=currency,
                known_at=close_known_at,
            )
        )
    snapshots = [
        _snapshot(
            f"{name}-pre-open",
            known_at=opened_at - timedelta(minutes=1),
            included=(),
            account_id=account_id,
            instrument_id=instrument_id,
            currency=currency,
            quantity=None,
        ),
        _snapshot(
            f"{name}-post-open",
            known_at=opened_at + timedelta(minutes=1),
            included=(buy_id,),
            account_id=account_id,
            instrument_id=instrument_id,
            currency=currency,
            quantity=quantity,
        ),
    ]
    if closed_at is not None:
        snapshots.extend(
            [
                _snapshot(
                    f"{name}-pre-close",
                    known_at=closed_at - timedelta(minutes=1),
                    included=(buy_id,),
                    account_id=account_id,
                    instrument_id=instrument_id,
                    currency=currency,
                    quantity=quantity,
                ),
                _snapshot(
                    f"{name}-post-close",
                    known_at=max(
                        closed_at + timedelta(minutes=1),
                        (
                            close_known_at + timedelta(minutes=1)
                            if close_known_at is not None
                            else closed_at + timedelta(minutes=1)
                        ),
                    ),
                    included=(buy_id, sell_id),
                    account_id=account_id,
                    instrument_id=instrument_id,
                    currency=currency,
                    quantity=None,
                ),
            ]
        )
    references = [P2F1._snapshot_ref(item) for item in snapshots]
    if exact_cursor:
        for reference in references:
            reference["cursor_scope"] = "account"
            reference["included_event_set_complete"] = True
    collection = P2F1._collection(events, references)
    portfolio_db = P2F1._create_p2b_db(work / "portfolio.sqlite3", snapshots)
    portfolio_context = P2F1.build_episode_portfolio_context(
        collection,
        portfolio_db=portfolio_db,
        as_of=CUTOFF.isoformat(),
        knowledge_cutoff=CUTOFF.isoformat(),
    )
    chain = P2F1.FixtureChain(
        collection=collection,
        portfolio_db=portfolio_db,
        portfolio_context=portfolio_context,
        episode_id=str(collection["episodes"][0]["episode_id"]),
        decisions=(),
        supplemental=(),
    )
    bundle = P2F1._build_bundle(chain, decisions=(), supplemental=())
    return build_facts_only_episode_review(bundle), bundle


def _cohort(
    root: Path, name: str, specs: Iterable[Mapping[str, Any]]
) -> dict[str, Any]:
    reviews: list[dict[str, Any]] = []
    bundles: list[dict[str, Any]] = []
    for index, spec in enumerate(specs):
        review, bundle = _episode_artifacts(
            root / name,
            f"{name}-{index}",
            **dict(spec),
        )
        reviews.append(review)
        bundles.append(bundle)
    return build_behavior_cohort(
        reviews,
        bundles,
        effective_from="2026-07-01T00:00:00Z",
        effective_to="2026-07-01T09:00:00Z",
        knowledge_cutoff="2026-07-01T10:00:00Z",
        effective_anchor="episode_opened_at",
    )


def _spec(
    hour: int,
    *,
    minute: int = 0,
    duration_minutes: int | None = 30,
    **values: Any,
) -> dict[str, Any]:
    opened = datetime(2026, 7, 1, hour, minute, tzinfo=UTC)
    result = {
        "opened_at": opened,
        "closed_at": (
            None if duration_minutes is None else opened + timedelta(minutes=duration_minutes)
        ),
    }
    result.update(values)
    return result


@pytest.fixture(scope="module")
def cohorts(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict[str, Any]]:
    root = tmp_path_factory.mktemp("p2g2")
    return {
        "base": _cohort(
            root,
            "base",
            [_spec(1, quantity="100"), _spec(2, duration_minutes=60, quantity="200")],
        ),
        "singleton": _cohort(root, "singleton", [_spec(1)]),
        "equal": _cohort(root, "equal", [_spec(1), _spec(1, duration_minutes=60)]),
        "overlap": _cohort(
            root,
            "overlap",
            [_spec(1, duration_minutes=120), _spec(2, duration_minutes=30)],
        ),
        "open": _cohort(
            root,
            "open",
            [_spec(1, duration_minutes=None), _spec(2, duration_minutes=30)],
        ),
        "accounts": _cohort(
            root,
            "accounts",
            [_spec(1, account_id="acct-1"), _spec(2, account_id="acct-2")],
        ),
        "instruments": _cohort(
            root,
            "instruments",
            [_spec(1, instrument_id="600000.SH"), _spec(2, instrument_id="000001.SZ")],
        ),
        "partial": _cohort(
            root,
            "partial",
            [_spec(1, exact_cursor=False), _spec(2, quantity="200", exact_cursor=False)],
        ),
        "decrease": _cohort(
            root,
            "decrease",
            [_spec(1, quantity="100"), _spec(2, quantity="80")],
        ),
        "stable": _cohort(
            root,
            "stable",
            [_spec(1, quantity="100"), _spec(2, quantity="110")],
        ),
        "currency": _cohort(
            root,
            "currency",
            [_spec(1, currency="CNY"), _spec(2, quantity="200", currency="USD")],
        ),
        "zero_duration": _cohort(
            root,
            "zero-duration",
            [_spec(1, duration_minutes=0), _spec(2, duration_minutes=30)],
        ),
        "late_known_event": _cohort(
            root,
            "late-known-event",
            [
                _spec(
                    1,
                    close_known_at=datetime(2026, 7, 1, 2, 30, tzinfo=UTC),
                ),
                _spec(2),
            ],
        ),
    }


def _only(
    cohort: Mapping[str, Any], detector_id: str, parameters: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    config = None
    if parameters is not None:
        config = {
            "detectors": [
                {"detector_id": detector_id, "parameters": dict(parameters)}
            ]
        }
    return build_behavior_observation_set(
        cohort,
        detector_config=config,
        detectors=[detector_id],
    )


def _evaluation(
    artifact: Mapping[str, Any], detector_id: str, *, size: int = 2
) -> Mapping[str, Any]:
    return next(
        item
        for item in artifact["evaluations"]
        if item["detector_id"] == detector_id
        and len(item["subject"]["episode_ids"]) == size
    )


def _codes(validation: Mapping[str, Any]) -> set[str]:
    return {
        str(item.get("code"))
        for item in validation.get("findings", [])
        if isinstance(item, Mapping)
    }


def _rehash(document: dict[str, Any]) -> None:
    material = deepcopy(document)
    material.pop("content_id", None)
    document["content_id"] = "sha256:" + hashlib.sha256(
        canonical_json_bytes(material)
    ).hexdigest()


def _all_values(value: object) -> Iterable[object]:
    yield value
    if isinstance(value, Mapping):
        for nested in value.values():
            yield from _all_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _all_values(nested)


def test_schema_release_and_source_status_are_ready(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    artifact = build_behavior_observation_set(cohorts["base"])
    assert artifact["schema_version"] == "p2g.behavior_observation_set.v1"
    assert artifact["content_id"].startswith("sha256:")
    assert artifact["release_readiness"] == {"status": "ready", "blocker_codes": []}
    assert artifact["source_verification"]["status"] == "verified"
    assert validate_behavior_observation_set(artifact)["validation_status"] == "accepted"


def test_exact_p2g1_source_identity_is_preserved(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    source = cohorts["base"]
    artifact = build_behavior_observation_set(source)
    assert artifact["source_cohort"] == {
        "schema_version": source["schema_version"],
        "cohort_id": source["cohort_id"],
        "content_id": source["content_id"],
        "release_readiness": "ready",
        "source_verification": "verified",
    }
    assert canonical_json_bytes(artifact["scope"]) == canonical_json_bytes(
        source["selection_spec"]
    )


def test_full_expanded_detector_config_enters_artifact_identity(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    artifact = build_behavior_observation_set(cohorts["base"])
    assert [item["detector_id"] for item in artifact["detector_contract"]["detectors"]] == list(DETECTOR_IDS)
    assert all("detector_version" in item and "enabled" in item and "parameters" in item for item in artifact["detector_contract"]["detectors"])


def test_artifact_has_no_binary_float_or_prohibited_semantic_key(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    artifact = build_behavior_observation_set(cohorts["base"])
    assert not any(isinstance(value, float) for value in _all_values(artifact))
    prohibited = {
        "advice",
        "diagnosis",
        "emotion",
        "interpretation",
        "motive",
        "narrative",
        "psychology",
        "recommendation",
        "score",
    }
    assert not ({str(key).lower() for key in _all_values(artifact) if isinstance(key, str)} & prohibited)


def test_all_four_detectors_emit_a_full_ledger(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    artifact = build_behavior_observation_set(cohorts["base"])
    assert artifact["counts"]["detector_counts"] == {
        "adjacent_episode_cadence": 1,
        "same_instrument_reentry_gap": 2,
        "episode_scale_transition": 1,
        "holding_duration_transition": 1,
    }
    assert artifact["counts"]["evaluation_count"] == 5


def test_same_input_is_byte_identical(cohorts: dict[str, dict[str, Any]]) -> None:
    first = build_behavior_observation_set(cohorts["base"])
    second = build_behavior_observation_set(deepcopy(cohorts["base"]))
    assert canonical_json_bytes(first) == canonical_json_bytes(second)


def test_environment_does_not_enter_identity(
    cohorts: dict[str, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    first = build_behavior_observation_set(cohorts["base"])
    monkeypatch.setenv("TZ", "Pacific/Honolulu")
    monkeypatch.setenv("PYTHONHASHSEED", "941")
    second = build_behavior_observation_set(cohorts["base"])
    assert first["content_id"] == second["content_id"]


def test_config_order_and_decimal_lexical_form_normalize_identically(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    rows = [
        {
            "detector_id": "episode_scale_transition",
            "parameters": {
                "material_increase_ratio": "1.2500",
                "material_decrease_ratio": "0.800",
            },
        },
        {
            "detector_id": "same_instrument_reentry_gap",
            "parameters": {"maximum_gap_seconds": "0600"},
        },
    ]
    first = build_behavior_observation_set(cohorts["base"], detector_config={"detectors": rows})
    second = build_behavior_observation_set(cohorts["base"], detector_config={"detectors": list(reversed(rows))})
    assert canonical_json_bytes(first) == canonical_json_bytes(second)


@pytest.mark.parametrize(
    "config,detectors",
    [
        ({"detectors": [{"detector_id": "unknown"}]}, None),
        ({"detectors": [{"detector_id": "adjacent_episode_cadence", "detector_version": "2"}]}, None),
        ({"detectors": [{"detector_id": "same_instrument_reentry_gap", "parameters": {"maximum_gap_seconds": 1.5}}]}, None),
        ({"detectors": [{"detector_id": "episode_scale_transition", "parameters": {"extra": "1"}}]}, None),
        ({"detectors": [{"detector_id": item, "enabled": False} for item in DETECTOR_IDS]}, None),
        (None, ["unknown"]),
    ],
)
def test_invalid_detector_configs_fail_closed(
    cohorts: dict[str, dict[str, Any]],
    config: Mapping[str, Any] | None,
    detectors: list[str] | None,
) -> None:
    with pytest.raises(BehaviorObservationError):
        build_behavior_observation_set(
            cohorts["base"], detector_config=config, detectors=detectors
        )


def test_cadence_records_nonnegative_anchor_gap(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    item = _evaluation(_only(cohorts["base"], "adjacent_episode_cadence"), "adjacent_episode_cadence")
    assert item["status"] == "observed"
    assert item["facts"]["anchor_gap_seconds"] == "3600"
    assert item["facts"]["inter_episode_gap_seconds"] == "1800"
    assert item["facts"]["overlap"] is False


def test_cadence_singleton_is_not_applicable(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    item = _evaluation(_only(cohorts["singleton"], "adjacent_episode_cadence"), "adjacent_episode_cadence", size=1)
    assert item["status"] == "not_applicable"
    assert item["reason_codes"] == ["no_adjacent_episode"]


def test_equal_open_times_are_ambiguous_not_id_ordered(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    artifact = _only(cohorts["equal"], "adjacent_episode_cadence")
    item = _evaluation(artifact, "adjacent_episode_cadence")
    assert item["status"] == "insufficient_evidence"
    assert item["reason_codes"] == ["ambiguous_temporal_order"]


def test_overlap_is_explicit_in_cadence(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    item = _evaluation(_only(cohorts["overlap"], "adjacent_episode_cadence"), "adjacent_episode_cadence")
    assert item["status"] == "observed"
    assert item["facts"]["overlap"] is True
    assert item["facts"]["inter_episode_gap_seconds"] == "-3600"
    assert item["reason_codes"] == ["overlapping_episodes"]


def test_adjacency_never_crosses_accounts(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    artifact = _only(cohorts["accounts"], "adjacent_episode_cadence")
    assert len(artifact["evaluations"]) == 2
    assert all(item["subject"]["subject_kind"] == "episode" for item in artifact["evaluations"])


def test_reentry_within_threshold_is_observed(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    item = _evaluation(_only(cohorts["base"], "same_instrument_reentry_gap"), "same_instrument_reentry_gap")
    assert item["status"] == "observed"
    assert item["facts"]["gap_seconds"] == "1800"


def test_reentry_threshold_is_inclusive(cohorts: dict[str, dict[str, Any]]) -> None:
    artifact = _only(
        cohorts["base"],
        "same_instrument_reentry_gap",
        {"maximum_gap_seconds": "1800"},
    )
    assert _evaluation(artifact, "same_instrument_reentry_gap")["status"] == "observed"


def test_reentry_above_threshold_is_not_observed(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    artifact = _only(
        cohorts["base"],
        "same_instrument_reentry_gap",
        {"maximum_gap_seconds": "1799"},
    )
    item = _evaluation(artifact, "same_instrument_reentry_gap")
    assert item["status"] == "not_observed"
    assert item["reason_codes"] == ["gap_exceeds_threshold"]


def test_reentry_without_followup_remains_in_ledger(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    artifact = _only(cohorts["base"], "same_instrument_reentry_gap")
    singleton = _evaluation(artifact, "same_instrument_reentry_gap", size=1)
    assert singleton["status"] == "not_applicable"
    assert singleton["reason_codes"] == ["no_following_same_instrument_episode"]


def test_open_prior_episode_is_not_a_reentry_gap(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    item = _evaluation(_only(cohorts["open"], "same_instrument_reentry_gap"), "same_instrument_reentry_gap")
    assert item["status"] == "not_applicable"
    assert item["reason_codes"] == ["open_episode"]


def test_overlapping_reentry_is_insufficient_not_negative_gap_observation(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    item = _evaluation(_only(cohorts["overlap"], "same_instrument_reentry_gap"), "same_instrument_reentry_gap")
    assert item["status"] == "insufficient_evidence"
    assert item["facts"]["gap_seconds"] == "-3600"


def test_reentry_prior_close_known_after_next_open_is_insufficient(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    item = _evaluation(
        _only(cohorts["late_known_event"], "same_instrument_reentry_gap"),
        "same_instrument_reentry_gap",
    )
    assert item["status"] == "insufficient_evidence"
    assert item["reason_codes"] == ["fact_known_after_subject_event"]
    assert item["chronology_checks"]["knowledge_cutoff"] == "valid"
    assert item["chronology_checks"]["subject_knowledge"] == "late"


def test_different_instrument_has_no_same_instrument_followup(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    artifact = _only(cohorts["instruments"], "same_instrument_reentry_gap")
    assert len(artifact["evaluations"]) == 2
    assert all(item["status"] == "not_applicable" for item in artifact["evaluations"])


def test_scale_increase_uses_exact_highest_priority_metric(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    item = _evaluation(_only(cohorts["base"], "episode_scale_transition"), "episode_scale_transition")
    assert item["status"] == "observed"
    assert item["facts"]["metric_key"] == "target_position_weight"
    assert item["facts"]["ratio"] == "2"
    assert item["facts"]["transition"] == "increase"


def test_scale_increase_boundary_is_inclusive(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    artifact = _only(
        cohorts["base"],
        "episode_scale_transition",
        {
            "material_increase_ratio": "2",
            "material_decrease_ratio": "0.5",
        },
    )
    assert _evaluation(artifact, "episode_scale_transition")["status"] == "observed"


def test_scale_decrease_boundary_is_inclusive(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    item = _evaluation(_only(cohorts["decrease"], "episode_scale_transition"), "episode_scale_transition")
    assert item["status"] == "observed"
    assert item["facts"]["ratio"] == "0.8"
    assert item["facts"]["transition"] == "decrease"


def test_scale_within_thresholds_is_not_observed(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    item = _evaluation(_only(cohorts["stable"], "episode_scale_transition"), "episode_scale_transition")
    assert item["status"] == "not_observed"
    assert item["reason_codes"] == ["within_thresholds"]


def test_present_partial_high_priority_metric_blocks_fallback(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    item = _evaluation(_only(cohorts["partial"], "episode_scale_transition"), "episode_scale_transition")
    assert item["status"] == "not_comparable"
    assert item["facts"]["metric_key"] == "target_position_weight"
    assert item["reason_codes"] == ["partial_or_ambiguous_source"]


def test_prior_scale_fact_known_after_current_open_is_insufficient(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    rows = observation_module._episode_rows(cohorts["base"])
    prior = deepcopy(rows[0])
    current = rows[1]
    projection = deepcopy(prior["projection"])
    prior["projection"] = projection
    metric = next(
        fact
        for fact in projection["fact_sections"]["portfolio_context"]["facts"]
        if fact["kind"] == "portfolio_metric"
        and fact["data"]["anchor_kind"] == "episode_open"
        and fact["data"]["side"] == "post"
        and fact["data"]["metric_key"] == "target_position_weight"
    )
    metric["knowledge_at"] = "2026-07-01T02:30:00Z"
    state, reason, facts, evidence = observation_module._metric_pair(
        prior,
        current,
        ["target_position_weight", "maximum_absolute_quantity"],
    )
    assert state == "insufficient_evidence"
    assert reason == "fact_known_after_subject_event"
    assert facts["prior_metric_known_at"] == "2026-07-01T02:30:00Z"
    assert evidence


def test_target_value_currency_mismatch_is_not_comparable(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    artifact = _only(
        cohorts["currency"],
        "episode_scale_transition",
        {
            "metric_priority": [
                "target_position_value",
                "maximum_absolute_quantity",
            ]
        },
    )
    item = _evaluation(artifact, "episode_scale_transition")
    assert item["status"] == "not_comparable"
    assert item["reason_codes"] == ["incomparable_currency"]


def test_quantity_fallback_requires_same_instrument(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    artifact = _only(
        cohorts["instruments"],
        "episode_scale_transition",
        {"metric_priority": ["maximum_absolute_quantity"]},
    )
    item = _evaluation(artifact, "episode_scale_transition")
    assert item["status"] == "not_comparable"
    assert item["reason_codes"] == ["different_instrument"]


def test_scale_values_and_ratios_remain_decimal_strings(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    facts = _evaluation(_only(cohorts["base"], "episode_scale_transition"), "episode_scale_transition")["facts"]
    assert all(isinstance(facts[key], str) for key in ("prior_value", "current_value", "ratio"))


def test_holding_duration_longer_is_observed(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    item = _evaluation(_only(cohorts["base"], "holding_duration_transition"), "holding_duration_transition")
    assert item["status"] == "observed"
    assert item["facts"]["ratio"] == "2"
    assert item["facts"]["transition"] == "longer"


def test_holding_duration_boundary_is_inclusive(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    artifact = _only(
        cohorts["base"],
        "holding_duration_transition",
        {"longer_ratio": "2", "shorter_ratio": "0.5"},
    )
    assert _evaluation(artifact, "holding_duration_transition")["status"] == "observed"


def test_holding_duration_within_thresholds_is_not_observed(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    item = _evaluation(_only(cohorts["stable"], "holding_duration_transition"), "holding_duration_transition")
    assert item["status"] == "not_observed"
    assert item["reason_codes"] == ["within_thresholds"]


def test_open_episode_duration_is_not_applicable(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    item = _evaluation(_only(cohorts["open"], "holding_duration_transition"), "holding_duration_transition")
    assert item["status"] == "not_applicable"
    assert item["reason_codes"] == ["open_episode"]


def test_same_instrument_duration_domain_is_explicit(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    artifact = _only(
        cohorts["instruments"],
        "holding_duration_transition",
        {
            "same_instrument_only": True,
            "longer_ratio": "1.25",
            "shorter_ratio": "0.75",
        },
    )
    item = _evaluation(artifact, "holding_duration_transition")
    assert item["status"] == "not_applicable"
    assert item["reason_codes"] == ["different_instrument"]


def test_zero_prior_duration_is_not_comparable(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    item = _evaluation(_only(cohorts["zero_duration"], "holding_duration_transition"), "holding_duration_transition")
    assert item["status"] == "not_comparable"
    assert item["reason_codes"] == ["zero_denominator"]


def test_prior_close_known_after_current_open_blocks_duration_comparison(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    item = _evaluation(
        _only(cohorts["late_known_event"], "holding_duration_transition"),
        "holding_duration_transition",
    )
    assert item["status"] == "insufficient_evidence"
    assert item["reason_codes"] == ["fact_known_after_subject_event"]


def test_evidence_refs_resolve_to_exact_p2g1_fact_ids(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    cohort = cohorts["base"]
    artifact = build_behavior_observation_set(cohort)
    available = {
        (
            item["episode_id"],
            item["review_id"],
            section_name,
            fact["fact_id"],
        )
        for item in cohort["included_reviews"]
        for section_name, section in item["facts_projection"]["fact_sections"].items()
        for fact in section["facts"]
    }
    for evaluation in artifact["evaluations"]:
        for ref in evaluation["evidence_refs"]:
            assert (
                ref["episode_id"],
                ref["review_id"],
                ref["section"],
                ref["fact_id"],
            ) in available


@pytest.mark.parametrize(
    "field,value",
    [
        ("evaluation_id", None),
        ("detector_id", "episode_scale_transition"),
        ("status", "observed"),
        ("episode_id", None),
        ("review_id", None),
        ("account_id", "acct-1"),
        ("instrument_id", "600000.sh"),
        ("reason_code", "within_thresholds"),
    ],
)
def test_query_filters(
    cohorts: dict[str, dict[str, Any]], field: str, value: str | None
) -> None:
    artifact = build_behavior_observation_set(cohorts["stable"])
    sample = artifact["evaluations"][-1]
    resolved = value
    if field == "evaluation_id":
        resolved = sample["evaluation_id"]
    elif field == "episode_id":
        resolved = sample["subject"]["episode_ids"][0]
    elif field == "review_id":
        resolved = sample["subject"]["review_ids"][0]
    result = query_behavior_observation_set(artifact, **{field: resolved})
    assert result
    assert all(isinstance(item, dict) for item in result)


def test_query_combines_filters_with_and_semantics(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    artifact = build_behavior_observation_set(cohorts["stable"])
    item = _evaluation(artifact, "episode_scale_transition")
    result = query_behavior_observation_set(
        artifact,
        detector_id="episode_scale_transition",
        status="not_observed",
        episode_id=item["subject"]["episode_ids"][0],
        account_id="acct-1",
        reason_code="within_thresholds",
        content_id=artifact["content_id"],
    )
    assert result == [item]
    assert query_behavior_observation_set(
        artifact,
        detector_id="episode_scale_transition",
        status="observed",
    ) == []


def test_query_content_mismatch_returns_empty_and_copy_isolated(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    artifact = build_behavior_observation_set(cohorts["base"])
    assert query_behavior_observation_set(artifact, content_id="sha256:missing") == []
    result = query_behavior_observation_set(artifact)
    result[0]["counts"]["evaluation_count"] = 999
    assert artifact["counts"]["evaluation_count"] != 999


@pytest.mark.parametrize(
    "kwargs",
    [
        {"detector_id": "unknown"},
        {"status": "unknown"},
        {"reason_code": "unknown"},
    ],
)
def test_query_unknown_registry_value_fails_closed(
    cohorts: dict[str, dict[str, Any]], kwargs: Mapping[str, str]
) -> None:
    with pytest.raises(BehaviorObservationError):
        query_behavior_observation_set(
            build_behavior_observation_set(cohorts["base"]), **kwargs
        )


@pytest.mark.parametrize(
    "mutation,expected_code",
    [
        (lambda item: item.update({"content_id": "sha256:bad"}), "CONTENT_ID_MISMATCH"),
        (lambda item: item["counts"].update({"evaluation_count": 999}), "COUNTS_MISMATCH"),
        (lambda item: item["evaluations"].append(deepcopy(item["evaluations"][0])), "DUPLICATE_EVALUATION_ID"),
        (lambda item: item["evaluations"][0].update({"recommendation": "forbidden"}), "PROHIBITED_SEMANTIC_FIELD"),
        (lambda item: item["evaluations"][0].update({"evidence_refs": []}), "EVIDENCE_REFS_MISSING"),
        (lambda item: item["evaluations"][0].update({"status": "unknown"}), "UNKNOWN_EVALUATION_STATUS"),
    ],
)
def test_validator_blocks_mutations(
    cohorts: dict[str, dict[str, Any]], mutation: Any, expected_code: str
) -> None:
    artifact = build_behavior_observation_set(cohorts["base"])
    mutation(artifact)
    if expected_code != "CONTENT_ID_MISMATCH":
        _rehash(artifact)
    validation = validate_behavior_observation_set(artifact)
    assert validation["validation_status"] == "blocked"
    assert expected_code in _codes(validation)


def test_source_replay_matches_exact_canonical_bytes(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    artifact = build_behavior_observation_set(cohorts["base"])
    result = replay_validate_behavior_observation_set(
        artifact, cohort=cohorts["base"]
    )
    assert result["validation_status"] == "accepted"
    assert result["source_verification"]["status"] == "verified"
    assert result["source_verification"]["rebuilt_content_id"] == artifact["content_id"]


def test_source_replay_rejects_different_or_mutated_cohort(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    artifact = build_behavior_observation_set(cohorts["base"])
    result = replay_validate_behavior_observation_set(
        artifact, cohort=cohorts["stable"]
    )
    assert result["validation_status"] == "blocked"
    assert "SOURCE_REPLAY_ERROR" in _codes(result)


def test_create_only_io_roundtrip_and_overwrite_refusal(
    cohorts: dict[str, dict[str, Any]], tmp_path: Path
) -> None:
    artifact = build_behavior_observation_set(cohorts["base"])
    output = tmp_path / "observations.json"
    assert save_behavior_observation_set(output, artifact) == output
    assert load_behavior_observation_set(output) == artifact
    with pytest.raises(BehaviorObservationError):
        save_behavior_observation_set(output, artifact)


def test_cli_build_show_validate_and_source_replay(
    cohorts: dict[str, dict[str, Any]], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cohort_path = tmp_path / "cohort.json"
    output = tmp_path / "observations.json"
    save_behavior_cohort(cohort_path, cohorts["base"])
    assert review_main(
        [
            "behavior-observation-build",
            "--cohort",
            str(cohort_path),
            "--output",
            str(output),
        ]
    ) == 0
    build_payload = json.loads(capsys.readouterr().out)
    assert build_payload["release_readiness"] == "ready"
    assert review_main(
        [
            "behavior-observation-show",
            str(output),
            "--detector-id",
            "episode_scale_transition",
            "--status",
            "observed",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)
    assert review_main(["behavior-observation-validate", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["validation_status"] == "accepted"
    assert review_main(
        [
            "behavior-observation-validate",
            str(output),
            "--source-replay",
            "--cohort",
            str(cohort_path),
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["source_verification"]["status"] == "verified"


def test_cli_refuses_overwrite_and_incomplete_source_replay(
    cohorts: dict[str, dict[str, Any]], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cohort_path = tmp_path / "cohort.json"
    output = tmp_path / "observations.json"
    save_behavior_cohort(cohort_path, cohorts["base"])
    assert review_main(
        ["behavior-observation-build", "--cohort", str(cohort_path), "--output", str(output)]
    ) == 0
    capsys.readouterr()
    assert review_main(
        ["behavior-observation-build", "--cohort", str(cohort_path), "--output", str(output)]
    ) == 2
    assert "already exists" in capsys.readouterr().err
    assert review_main(
        ["behavior-observation-validate", str(output), "--source-replay"]
    ) == 2
    assert "requires --cohort" in capsys.readouterr().err


def test_status_registry_is_fully_counted(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    artifact = build_behavior_observation_set(cohorts["partial"])
    assert list(artifact["counts"]["status_counts"]) == list(EVALUATION_STATUSES)
    assert sum(artifact["counts"]["status_counts"].values()) == artifact["counts"]["evaluation_count"]


def test_no_machine_path_or_environment_value_enters_artifact(
    cohorts: dict[str, dict[str, Any]],
) -> None:
    artifact = build_behavior_observation_set(cohorts["base"])
    strings = {item for item in _all_values(artifact) if isinstance(item, str)}
    assert not any(str(Path.cwd()) in item for item in strings)
    assert not any(os.environ.get("TEMP", "__absent__") in item for item in strings)
