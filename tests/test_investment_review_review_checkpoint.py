from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from src.investment_review.episodes import build_episode_collection
from src.investment_review.knowledge_provenance import (
    build_knowledge_provenance,
)
from src.investment_review.ledger_snapshot_reconstruction import (
    LEDGER_SNAPSHOT_BASELINE_SCHEMA_VERSION,
    build_ledger_snapshot_reconstruction,
)
from src.investment_review.models import (
    MARKET_FALLBACK_POLICY_VERSION,
    MARKET_FALLBACK_POLICY_VERSION_V2,
    MARKET_PROVIDER_ALLOWLIST,
    MARKET_PROVIDER_ALLOWLIST_SHA256,
    MARKET_PROVIDER_ALLOWLIST_VERSION,
    OPERATION_CHECKPOINT_SCHEMA_VERSION_V2,
    PUBLIC_INFORMATION_POLICY_VERSION,
    OperationCheckpointRecord,
)
from src.investment_review.operation_review import build_operation_review
from src.investment_review.review_checkpoint import (
    METHOD_VERSION,
    METHOD_VERSION_V2,
    ReviewCheckpointConflictError,
    ReviewCheckpointError,
    build_review_checkpoint,
    canonical_review_checkpoint_bytes,
    derive_checkpoint_semantics,
    derive_review_checkpoint_operation_anchor,
    plan_review_checkpoint_append,
    replay_validate_review_checkpoint,
    validate_review_checkpoint,
)
from src.investment_review.store import ReviewStore


OPENED_AT = "2026-01-02T01:30:00Z"
ADJUSTED_AT = "2026-01-03T01:30:00Z"
ACTIVE_AT = "2026-01-04T01:30:00Z"
LATER_ACTIVE_AT = "2026-01-05T01:30:00Z"
RECORDED_AT = "2026-01-06T08:00:00Z"
KNOWLEDGE_CUTOFF = "2026-01-10T00:00:00Z"


def _event(
    event_id: str,
    occurred_at: str,
    *,
    side: str,
    quantity: str,
    sequence: int,
) -> dict[str, object]:
    price = "10"
    gross = str(int(quantity) * int(price))
    cash = f"-{int(gross) + 1}" if side == "BUY" else str(int(gross) - 1)
    return {
        "event_id": event_id,
        "source_id": "checkpoint_fixture",
        "source_record_id": f"row-{sequence}",
        "event_type": side.lower(),
        "occurred_at": occurred_at,
        "known_at": RECORDED_AT,
        "account": "acct",
        "market": "SH",
        "symbol": "600000.SH",
        "side": side,
        "quantity": quantity,
        "price": price,
        "gross_amount": gross,
        "cash_amount": cash,
        "fees": "1",
        "currency": "CNY",
        "payload_sha256": hashlib.sha256(event_id.encode("utf-8")).hexdigest(),
        "raw_payload": {
            "source_row": {
                "account_id": "acct",
                "external_id": event_id,
                "dedupe_key": f"dedupe-{event_id}",
                "entry_id": sequence,
                "created_at": RECORDED_AT,
            }
        },
        "decision_refs": [],
    }


def _open_events() -> list[dict[str, object]]:
    return [
        _event(
            "evt-open",
            OPENED_AT,
            side="BUY",
            quantity="100",
            sequence=1,
        ),
        _event(
            "evt-adjust",
            ADJUSTED_AT,
            side="BUY",
            quantity="50",
            sequence=2,
        ),
    ]


def _closed_events() -> list[dict[str, object]]:
    return [
        _event(
            "evt-open",
            OPENED_AT,
            side="BUY",
            quantity="100",
            sequence=1,
        ),
        _event(
            "evt-close",
            ADJUSTED_AT,
            side="SELL",
            quantity="100",
            sequence=2,
        ),
    ]


def _source_binding(knowledge_content_id: str) -> dict[str, str]:
    return {
        "portfolio_source_sha256": "1" * 64,
        "sync_source_sha256": "2" * 64,
        "mapping_sha256": "3" * 64,
        "source_cutoff_id": "checkpoint_fixture_cutoff",
        "sidecar_projection_sha256": "4" * 64,
        "knowledge_provenance_content_id": knowledge_content_id,
        "cash_baseline_proof_content_id": "sha256:" + ("5" * 64),
    }


def _baseline() -> dict[str, object]:
    return {
        "schema_version": LEDGER_SNAPSHOT_BASELINE_SCHEMA_VERSION,
        "position": {
            "status": "available",
            "quantity": "0",
            "cost_basis": "0",
            "effective_at": "2026-01-01T00:00:00Z",
            "known_at": "2026-01-01T00:00:00Z",
            "method": "explicit_reviewed_baseline",
            "source_refs": ["position_baseline:checkpoint_fixture"],
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


def _sources(
    events: list[dict[str, object]],
    *,
    as_of: str,
) -> dict[str, Any]:
    collection = build_episode_collection(
        events,
        cutoff_at=KNOWLEDGE_CUTOFF,
    )
    assert len(collection["episodes"]) == 1
    episode = collection["episodes"][0]
    operation_review = build_operation_review(
        collection,
        event_inputs=events,
    )
    knowledge = build_knowledge_provenance(
        events,
        perspective="user",
        as_of=as_of,
        knowledge_cutoff=KNOWLEDGE_CUTOFF,
    )
    reconstruction = build_ledger_snapshot_reconstruction(
        events,
        episode=episode,
        perspective="user",
        as_of=as_of,
        knowledge_cutoff=KNOWLEDGE_CUTOFF,
        source_binding=_source_binding(str(knowledge["content_id"])),
        baseline_proof=_baseline(),
    )
    return {
        "episode": episode,
        "operation_review": operation_review,
        "knowledge_provenance": knowledge,
        "ledger_snapshot_reconstruction": reconstruction,
    }


def _market(
    cache_ref: str = "local_close:600000.SH:2026-01-01",
    *,
    price: str = "9.90",
) -> tuple[dict[str, object], dict[str, object]]:
    axis = {
        "status": "available",
        "temporal_role": "system_known_at_decision",
        "effective_at": "2026-01-01T07:00:00Z",
        "publicly_available_at": "2026-01-01T07:01:00Z",
        "publicly_available_basis": "exchange_calendar",
        "fetched_at": "2026-01-01T07:02:00Z",
        "system_observed_at": "2026-01-01T07:02:00Z",
        "summary": f"冻结的本地收盘价为 {price}。",
        "source_refs": [cache_ref],
    }
    fallback = {
        "policy_version": MARKET_FALLBACK_POLICY_VERSION,
        "allowlist_version": MARKET_PROVIDER_ALLOWLIST_VERSION,
        "allowlist_sha256": MARKET_PROVIDER_ALLOWLIST_SHA256,
        "coverage_before": "satisfied",
        "coverage_after": "satisfied",
        "status": "not_needed",
        "request_count": 0,
        "limits": {
            "timeout_seconds": 20,
            "max_retries": 2,
            "max_concurrency": 2,
            "max_requests_per_run": 20,
        },
        "allowlist": sorted(MARKET_PROVIDER_ALLOWLIST),
        "cache_refs": [cache_ref],
        "fetch_receipt_refs": [],
        "fetch_receipts": [],
        "offline_consumers": {
            "renderer": False,
            "source_replay": False,
            "api": False,
            "ui": False,
        },
    }
    return axis, fallback


def _market_v2() -> tuple[dict[str, object], dict[str, object]]:
    axis, fallback = _market()
    cache_ref = str(axis["source_refs"][0])
    manifest_content_id = "sha256:" + "d" * 64
    axis.update(
        {
            "temporal_role": "user_known_at_operation_by_verified_publication",
            "perspective": "user",
            "eligible_source_refs": [cache_ref],
            "retrospective_source_refs": [],
            "unknown_source_refs": [],
            "publicly_available_basis": "verified_publication_interval",
            "representative_source_id": cache_ref,
            "representative_source_content_id": "sha256:" + "a" * 64,
            "information_time": {
                "status": "verified",
                "lower_bound": "2026-01-01T00:00:00Z",
                "upper_bound": "2026-01-01T07:01:00Z",
                "basis": "provider_publication_date_source_timezone.v1",
                "method_version": "public_information_time.v1",
                "revision_ref": "revision:close:2026-01-01",
            },
            "version_provenance": {
                "status": "verified",
                "content_sha256": "sha256:" + "b" * 64,
                "source_ref": cache_ref,
                "revision_ref": "revision:close:2026-01-01",
            },
            "perspective_eligibility": {
                "perspective": "user",
                "status": "eligible",
                "reason_code": "verified_publication_strictly_before_operation",
                "temporal_role": (
                    "user_known_at_operation_by_verified_publication"
                ),
                "operation_anchor_at": ADJUSTED_AT,
                "projected_user_known_at": ADJUSTED_AT,
                "projected_system_known_at": None,
                "actual_user_observation_proven": False,
            },
            "market_evidence_manifest_content_id": manifest_content_id,
            "source_refs": sorted(
                {
                    cache_ref,
                    "market_evidence_manifest:" + manifest_content_id,
                }
            ),
        }
    )
    fallback.update(
        {
            "policy_version": MARKET_FALLBACK_POLICY_VERSION_V2,
            "public_information_policy_version": (
                PUBLIC_INFORMATION_POLICY_VERSION
            ),
            "perspective": "user",
            "limitation_code": None,
            "guard_audit_at": None,
            "request_count_status": "verified",
            "unverified_attempt_upper_bound": 0,
        }
    )
    return axis, fallback


def _build(
    sources: dict[str, Any],
    *,
    checkpoint_type: str,
    as_of: str,
    market_cache_ref: str = "local_close:600000.SH:2026-01-01",
) -> dict[str, Any]:
    market_axis, market_fallback = _market(market_cache_ref)
    return build_review_checkpoint(
        **sources,
        perspective="user",
        checkpoint_as_of=as_of,
        knowledge_cutoff=KNOWLEDGE_CUTOFF,
        checkpoint_type=checkpoint_type,
        market_axis=market_axis,
        market_fallback=market_fallback,
    )


def _codes(receipt: dict[str, Any]) -> set[str]:
    return {str(item["code"]) for item in receipt["findings"]}


def test_active_checkpoint_is_ready_open_interim_without_an_outcome_gap() -> None:
    sources = _sources(_open_events(), as_of=ACTIVE_AT)
    checkpoint = _build(
        sources,
        checkpoint_type="active_checkpoint",
        as_of=ACTIVE_AT,
    )

    assert checkpoint["review_kind"] == "active_checkpoint"
    assert checkpoint["checkpoint_type"] == "active_checkpoint"
    assert checkpoint["position_case_id"] == (
        f"position_case:{checkpoint['episode_id']}"
    )
    axes = checkpoint["status_axes"]
    assert axes["operation"]["status"] == "ready"
    assert axes["decision"]["status"] == "not_recorded"
    assert axes["lifecycle"]["status"] == "open"
    assert axes["outcome"]["status"] == "interim"
    assert "尚未形成最终结果" in axes["outcome"]["summary"]
    assert "OPEN_EPISODE_OUTCOME_NOT_FINAL" not in {
        item["code"] for item in checkpoint["gaps"]
    }
    assert f"method:{METHOD_VERSION}" in checkpoint["source_refs"]
    assert validate_review_checkpoint(checkpoint)["validation_status"] == "accepted"
    assert canonical_review_checkpoint_bytes(checkpoint)

    market_axis, market_fallback = _market()
    replay = replay_validate_review_checkpoint(
        checkpoint,
        **sources,
        perspective="user",
        checkpoint_as_of=ACTIVE_AT,
        knowledge_cutoff=KNOWLEDGE_CUTOFF,
        checkpoint_type="active_checkpoint",
        market_axis=market_axis,
        market_fallback=market_fallback,
    )
    assert replay["validation_status"] == "accepted"
    assert replay["source_verification"]["status"] == "verified"


def test_v2_active_checkpoint_recomputes_and_replays_operation_anchor() -> None:
    sources = _sources(_open_events(), as_of=ACTIVE_AT)
    market_axis, market_fallback = _market_v2()
    checkpoint = build_review_checkpoint(
        **sources,
        perspective="user",
        checkpoint_as_of=ACTIVE_AT,
        knowledge_cutoff=KNOWLEDGE_CUTOFF,
        checkpoint_type="active_checkpoint",
        market_axis=market_axis,
        market_fallback=market_fallback,
        checkpoint_schema_version=OPERATION_CHECKPOINT_SCHEMA_VERSION_V2,
    )
    assert checkpoint["operation_anchor_event_id"] == "evt-adjust"
    assert checkpoint["operation_anchor_at"] == ADJUSTED_AT
    assert checkpoint["operation_anchor_at"] < checkpoint["as_of"]
    assert checkpoint["operation_anchor_ordering_key"][3] == "evt-adjust"
    helper_anchor = derive_review_checkpoint_operation_anchor(
        sources["episode"],
        operation_review=sources["operation_review"],
        checkpoint_type="active_checkpoint",
        checkpoint_as_of=ACTIVE_AT,
    )
    assert checkpoint["operation_anchor_event_id"] == helper_anchor[
        "operation_anchor_event_id"
    ]
    assert checkpoint["operation_anchor_at"] == helper_anchor["operation_anchor_at"]
    assert checkpoint["operation_anchor_ordering_key"] == helper_anchor[
        "operation_anchor_ordering_key"
    ]
    assert checkpoint["operation_anchor_ordering_key"][0] == ADJUSTED_AT
    assert f"method:{METHOD_VERSION_V2}" in checkpoint["source_refs"]
    assert validate_review_checkpoint(checkpoint)["validation_status"] == "accepted"
    replay = replay_validate_review_checkpoint(
        checkpoint,
        **sources,
        perspective="user",
        checkpoint_as_of=ACTIVE_AT,
        knowledge_cutoff=KNOWLEDGE_CUTOFF,
        checkpoint_type="active_checkpoint",
        market_axis=market_axis,
        market_fallback=market_fallback,
        checkpoint_schema_version=OPERATION_CHECKPOINT_SCHEMA_VERSION_V2,
    )
    assert replay["validation_status"] == "accepted"
    assert replay["source_verification"]["status"] == "verified"


def test_v2_checkpoint_rejects_representative_effective_after_fetch() -> None:
    sources = _sources(_open_events(), as_of=ACTIVE_AT)
    market_axis, market_fallback = _market_v2()
    market_axis["effective_at"] = "2026-01-01T07:03:00Z"
    with pytest.raises(ReviewCheckpointError, match="closed operation contract"):
        build_review_checkpoint(
            **sources,
            perspective="user",
            checkpoint_as_of=ACTIVE_AT,
            knowledge_cutoff=KNOWLEDGE_CUTOFF,
            checkpoint_type="active_checkpoint",
            market_axis=market_axis,
            market_fallback=market_fallback,
            checkpoint_schema_version=OPERATION_CHECKPOINT_SCHEMA_VERSION_V2,
        )


def test_v2_active_anchor_skips_later_ambiguous_nonmaterial_operation() -> None:
    events = _open_events() + [
        _event(
            "evt-ambiguous",
            "2026-01-03T12:00:00Z",
            side="TRANSFER_IN",
            quantity="10",
            sequence=3,
        )
    ]
    collection = build_episode_collection(events, cutoff_at=KNOWLEDGE_CUTOFF)
    operation_review = build_operation_review(collection, event_inputs=events)
    assert operation_review["episode_reviews"][0]["operations"][-1][
        "classification_status"
    ] == "ambiguous"
    anchor = derive_review_checkpoint_operation_anchor(
        collection["episodes"][0],
        operation_review=operation_review,
        checkpoint_type="active_checkpoint",
        checkpoint_as_of=ACTIVE_AT,
    )
    assert anchor["operation_anchor_event_id"] == "evt-adjust"
    assert anchor["operation_anchor_at"] == ADJUSTED_AT
    assert anchor["classification_status"] == "ready"


def test_entry_adjustment_exit_and_postmortem_have_closed_semantics() -> None:
    entry_sources = _sources([_open_events()[0]], as_of=OPENED_AT)
    entry = _build(
        entry_sources,
        checkpoint_type="entry",
        as_of=OPENED_AT,
    )
    adjustment_sources = _sources(_open_events(), as_of=ADJUSTED_AT)
    adjustment = _build(
        adjustment_sources,
        checkpoint_type="adjustment",
        as_of=ADJUSTED_AT,
    )
    closed_sources = _sources(_closed_events(), as_of=ADJUSTED_AT)
    exit_checkpoint = _build(
        closed_sources,
        checkpoint_type="exit",
        as_of=ADJUSTED_AT,
    )
    postmortem = _build(
        closed_sources,
        checkpoint_type="postmortem",
        as_of=ADJUSTED_AT,
    )

    assert entry["review_kind"] == "operation_review"
    assert entry["status_axes"]["lifecycle"]["status"] == "open"
    assert entry["status_axes"]["outcome"]["status"] == "interim"
    assert adjustment["review_kind"] == "operation_review"
    assert adjustment["status_axes"]["lifecycle"]["status"] == "open"
    assert adjustment["status_axes"]["outcome"]["status"] == "interim"
    assert exit_checkpoint["review_kind"] == "operation_review"
    assert exit_checkpoint["status_axes"]["lifecycle"]["status"] == "closed"
    assert exit_checkpoint["status_axes"]["outcome"]["status"] == "final"
    assert postmortem["review_kind"] == "postmortem"
    assert postmortem["status_axes"]["lifecycle"]["status"] == "closed"
    assert postmortem["status_axes"]["outcome"]["status"] == "final"
    assert exit_checkpoint["checkpoint_key"] != postmortem["checkpoint_key"]
    assert exit_checkpoint["position_case_id"] == postmortem["position_case_id"]
    for checkpoint in (entry, adjustment, exit_checkpoint, postmortem):
        assert validate_review_checkpoint(checkpoint)["validation_status"] == "accepted"
        assert "pnl" not in checkpoint
        assert "final_pnl" not in checkpoint


def test_same_cutoff_is_idempotent_and_content_drift_conflicts() -> None:
    sources = _sources(_open_events(), as_of=ACTIVE_AT)
    first = _build(
        sources,
        checkpoint_type="active_checkpoint",
        as_of=ACTIVE_AT,
    )
    repetitions = [
        _build(
            sources,
            checkpoint_type="active_checkpoint",
            as_of=ACTIVE_AT,
        )
        for _ in range(12)
    ]
    assert {item["checkpoint_key"] for item in repetitions} == {
        first["checkpoint_key"]
    }
    assert {
        canonical_review_checkpoint_bytes(item) for item in repetitions
    } == {canonical_review_checkpoint_bytes(first)}
    assert plan_review_checkpoint_append(first)["status"] == "INSERTED"
    assert (
        plan_review_checkpoint_append(
            repetitions[-1],
            existing_checkpoints=[first],
        )["status"]
        == "SKIPPED"
    )

    changed_market = _build(
        sources,
        checkpoint_type="active_checkpoint",
        as_of=ACTIVE_AT,
        market_cache_ref="local_close:600000.SH:2026-01-01:revision-2",
    )
    assert changed_market["checkpoint_key"] == first["checkpoint_key"]
    assert changed_market["content_id"] != first["content_id"]
    with pytest.raises(
        ReviewCheckpointConflictError,
        match="semantic identity",
    ):
        plan_review_checkpoint_append(
            changed_market,
            existing_checkpoints=[first],
        )


def test_store_concurrency_is_create_only_and_different_cutoff_appends(
    tmp_path: Path,
) -> None:
    store = ReviewStore(tmp_path / "reviewability.sqlite3")
    store.initialize_reviewability_candidate()
    sources = _sources(_open_events(), as_of=ACTIVE_AT)
    checkpoint = _build(
        sources,
        checkpoint_type="active_checkpoint",
        as_of=ACTIVE_AT,
    )

    with ThreadPoolExecutor(max_workers=8) as pool:
        receipts = list(
            pool.map(
                lambda _index: store.save_operation_checkpoint(
                    checkpoint
                ),
                range(16),
            )
        )

    assert sum(item["status"] == "INSERTED" for item in receipts) == 1
    assert sum(item["status"] == "SKIPPED" for item in receipts) == 15
    first_bytes = canonical_review_checkpoint_bytes(
        store.get_operation_checkpoint(checkpoint["checkpoint_key"])
    )

    later = _build(
        _sources(_open_events(), as_of=LATER_ACTIVE_AT),
        checkpoint_type="active_checkpoint",
        as_of=LATER_ACTIVE_AT,
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        cross_cutoff = list(
            pool.map(
                store.save_operation_checkpoint,
                (checkpoint, later),
            )
        )

    assert {item["status"] for item in cross_cutoff} == {
        "INSERTED",
        "SKIPPED",
    }
    stored = store.list_operation_checkpoints(
        position_case_id=checkpoint["position_case_id"]
    )
    assert [item["checkpoint_key"] for item in stored] == [
        checkpoint["checkpoint_key"],
        later["checkpoint_key"],
    ]
    assert canonical_review_checkpoint_bytes(stored[0]) == first_bytes


def test_different_cutoffs_append_distinct_semantic_identities() -> None:
    events = _open_events()
    first_sources = _sources(events, as_of=ACTIVE_AT)
    later_sources = _sources(events, as_of=LATER_ACTIVE_AT)
    first = _build(
        first_sources,
        checkpoint_type="active_checkpoint",
        as_of=ACTIVE_AT,
    )
    later = _build(
        later_sources,
        checkpoint_type="active_checkpoint",
        as_of=LATER_ACTIVE_AT,
    )

    assert first["episode_id"] == later["episode_id"]
    assert first["position_case_id"] == later["position_case_id"]
    assert first["checkpoint_key"] != later["checkpoint_key"]
    assert first["checkpoint_id"] != later["checkpoint_id"]
    assert (
        plan_review_checkpoint_append(
            later,
            existing_checkpoints=[first],
        )["status"]
        == "INSERTED"
    )


def test_position_case_never_merges_distinct_reentry_episodes() -> None:
    first_sources = _sources([_open_events()[0]], as_of=OPENED_AT)
    other_event = _event(
        "evt-other-open",
        OPENED_AT,
        side="BUY",
        quantity="100",
        sequence=20,
    )
    other_sources = _sources([other_event], as_of=OPENED_AT)
    first = _build(
        first_sources,
        checkpoint_type="entry",
        as_of=OPENED_AT,
    )
    other = _build(
        other_sources,
        checkpoint_type="entry",
        as_of=OPENED_AT,
    )

    assert first["episode_id"] != other["episode_id"]
    assert first["position_case_id"] != other["position_case_id"]
    assert first["checkpoint_key"] != other["checkpoint_key"]


def test_exit_and_adjustment_cannot_be_fabricated() -> None:
    open_sources = _sources(_open_events(), as_of=ACTIVE_AT)
    with pytest.raises(ReviewCheckpointError, match="exit requires a closed"):
        _build(
            open_sources,
            checkpoint_type="exit",
            as_of=ACTIVE_AT,
        )
    with pytest.raises(
        ReviewCheckpointError,
        match="must coincide with a non-entry operation",
    ):
        _build(
            open_sources,
            checkpoint_type="adjustment",
            as_of=ACTIVE_AT,
        )

    active = _build(
        open_sources,
        checkpoint_type="active_checkpoint",
        as_of=ACTIVE_AT,
    )
    hostile = deepcopy(active)
    hostile["final_pnl"] = "999999"
    validation = validate_review_checkpoint(hostile)
    assert validation["validation_status"] == "blocked"
    assert "MALFORMED_REVIEW_CHECKPOINT_SHAPE" in _codes(validation)


def test_interim_outcome_cannot_be_promoted_to_gap_or_final() -> None:
    sources = _sources(_open_events(), as_of=ACTIVE_AT)
    active = _build(
        sources,
        checkpoint_type="active_checkpoint",
        as_of=ACTIVE_AT,
    )
    raw = deepcopy(active)
    raw["gaps"].append(
        {
            "gap_id": "forged-gap",
            "axis": "outcome",
            "code": "OPEN_EPISODE_OUTCOME_NOT_FINAL",
            "severity": "warning",
            "blocks_axis": False,
            "owner": "nobody",
            "next_step": "none",
            "source_refs": [],
        }
    )
    raw["checkpoint_id"] = None
    raw["checkpoint_key"] = None
    raw["content_id"] = None
    with pytest.raises(Exception):
        OperationCheckpointRecord.from_mapping(raw)

    final = deepcopy(active)
    final["status_axes"]["outcome"]["status"] = "final"
    final["checkpoint_id"] = None
    final["checkpoint_key"] = None
    final["content_id"] = None
    with pytest.raises(Exception):
        OperationCheckpointRecord.from_mapping(final)


def test_market_projection_is_mandatory_and_never_synthesized() -> None:
    sources = _sources(_open_events(), as_of=ACTIVE_AT)
    with pytest.raises(ReviewCheckpointError, match="closed operation contract"):
        build_review_checkpoint(
            **sources,
            perspective="user",
            checkpoint_as_of=ACTIVE_AT,
            knowledge_cutoff=KNOWLEDGE_CUTOFF,
            checkpoint_type="active_checkpoint",
            market_axis={},
            market_fallback={},
        )


def test_source_replay_detects_same_cutoff_market_drift() -> None:
    sources = _sources(_open_events(), as_of=ACTIVE_AT)
    checkpoint = _build(
        sources,
        checkpoint_type="active_checkpoint",
        as_of=ACTIVE_AT,
    )
    changed_axis, changed_fallback = _market(
        "local_close:600000.SH:2026-01-01:revision-2",
        price="9.91",
    )
    replay = replay_validate_review_checkpoint(
        checkpoint,
        **sources,
        perspective="user",
        checkpoint_as_of=ACTIVE_AT,
        knowledge_cutoff=KNOWLEDGE_CUTOFF,
        checkpoint_type="active_checkpoint",
        market_axis=changed_axis,
        market_fallback=changed_fallback,
    )
    assert replay["validation_status"] == "blocked"
    assert replay["source_verification"]["status"] == "blocked"
    assert "REVIEW_CHECKPOINT_SOURCE_REPLAY_MISMATCH" in _codes(replay)


def test_semantic_helper_exposes_only_episode_scoped_lifecycle_facts() -> None:
    sources = _sources(_open_events(), as_of=ACTIVE_AT)
    semantics = derive_checkpoint_semantics(
        sources["episode"],
        operation_review=sources["operation_review"],
        checkpoint_type="active_checkpoint",
        checkpoint_as_of=ACTIVE_AT,
    )
    assert semantics == {
        "episode_id": sources["episode"]["episode_id"],
        "position_case_id": (
            f"position_case:{sources['episode']['episode_id']}"
        ),
        "review_kind": "active_checkpoint",
        "checkpoint_type": "active_checkpoint",
        "lifecycle": "open",
        "outcome": "interim",
        "anchor_event_id": "evt-adjust",
    }
