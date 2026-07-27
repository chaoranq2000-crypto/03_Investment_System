from __future__ import annotations

import json
import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from src.investment_review.artifact_io import canonical_json_bytes
from src.investment_review.models import (
    MARKET_FALLBACK_POLICY_VERSION,
    MARKET_FALLBACK_POLICY_VERSION_V2,
    MARKET_PROVIDER_ALLOWLIST,
    MARKET_PROVIDER_ALLOWLIST_SHA256,
    MARKET_PROVIDER_ALLOWLIST_VERSION,
    MARKET_REQUEST_FINGERPRINT_VERSION,
    ModelValidationError,
    OPERATION_CHECKPOINT_SCHEMA_VERSION,
    OPERATION_CHECKPOINT_SCHEMA_VERSION_V2,
    PUBLIC_INFORMATION_POLICY_VERSION,
    OperationCheckpointRecord,
    OperationCheckpointRecordV2,
    market_request_fingerprint,
)
from src.investment_review.store import (
    DataConflictError,
    REVIEWABILITY_SCHEMA_MANIFEST_SHA256,
    REVIEWABILITY_SCHEMA_MANIFEST_SHA256_V2,
    REVIEWABILITY_SCHEMA_VERSION,
    REVIEWABILITY_SCHEMA_VERSION_V2,
    ReviewStore,
    ReviewStoreError,
)
import src.investment_review.store as review_store_module


SCHEMA_PATH = (
    Path(__file__).parents[1]
    / "docs"
    / "contracts"
    / "INVESTMENT_REVIEW_OPERATION_CHECKPOINT.schema.json"
)
SCHEMA_V2_PATH = (
    Path(__file__).parents[1]
    / "docs"
    / "contracts"
    / "INVESTMENT_REVIEW_OPERATION_CHECKPOINT_V2.schema.json"
)


def _field(
    status: str = "missing",
    value: str | None = None,
    unit: str | None = None,
    refs: list[str] | None = None,
) -> dict[str, object]:
    return {
        "status": status,
        "value": value,
        "unit": unit,
        "source_refs": list(refs or []),
    }


def checkpoint_input() -> dict[str, object]:
    return {
        "episode_id": "episode-1",
        "position_case_id": "case:episode-1",
        "review_kind": "active_checkpoint",
        "checkpoint_type": "active_checkpoint",
        "perspective": "user",
        "as_of": "2026-07-17T06:00:00Z",
        "knowledge_cutoff": "2026-07-25T12:00:00Z",
        "time_provenance": {
            "effective_at": {
                "value": "2026-07-17T05:30:00Z",
                "basis": "source_occurred_at",
                "source_refs": ["event:b", "event:a"],
            },
            "user_known_at": {
                "value": "2026-07-17T05:30:00Z",
                "basis": "owner_action_default",
                "source_refs": ["event:a"],
            },
            "system_observed_at": {
                "value": "2026-07-25T10:00:00Z",
                "basis": "recorded_later",
                "source_refs": ["ingest:1"],
            },
            "recorded_at": {
                "value": "2026-07-25T10:00:00Z",
                "basis": "ingest_observation",
                "source_refs": ["ingest:1"],
            },
        },
        "status_axes": {
            "operation": {
                "status": "ready",
                "summary": "账户操作事实已完成复盘。",
                "source_refs": ["event:b", "event:a"],
            },
            "decision": {
                "status": "not_recorded",
                "summary": "未记录决策理由；不影响操作事实。",
                "source_refs": [],
            },
            "snapshot_cash_valuation": {
                "status": "partial",
                "fields": {
                    "position_quantity": _field(
                        "available", "8100", "share", ["ledger:cutoff"]
                    ),
                    "cost_basis": _field(
                        "available", "3.80", "CNY/share", ["ledger:cutoff"]
                    ),
                    "cash": _field(),
                    "price": _field(),
                    "nav": _field(),
                    "weight": _field(),
                    "industry": _field(),
                },
                "source_refs": ["ledger:cutoff"],
            },
            "market": {
                "status": "available",
                "temporal_role": "reconstructed_public_context",
                "effective_at": "2026-07-16T07:00:00Z",
                "publicly_available_at": None,
                "publicly_available_basis": "unknown",
                "fetched_at": "2026-07-25T10:05:00Z",
                "system_observed_at": "2026-07-25T10:05:00Z",
                "source_refs": ["close_price:588200.SH:2026-07-16"],
            },
            "lifecycle": {
                "status": "open",
                "source_refs": ["episode:1"],
            },
            "outcome": {
                "status": "interim",
                "source_refs": ["episode:1"],
            },
        },
        "market_fallback": {
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
            "cache_refs": ["close_price:588200.SH:2026-07-16"],
            "fetch_receipt_refs": [],
            "fetch_receipts": [],
            "offline_consumers": {
                "renderer": False,
                "source_replay": False,
                "api": False,
                "ui": False,
            },
        },
        "gaps": [],
        "source_refs": ["ledger:cutoff", "event:a", "event:b"],
        "governance": {
            "facts_only": True,
            "no_motive": True,
            "no_advice": True,
            "no_score": True,
            "no_diagnosis": True,
        },
    }


def checkpoint_v2_input(*, perspective: str = "user") -> dict[str, object]:
    payload = checkpoint_input()
    market_source_ref = "close_price:588200.SH:2026-07-16"
    market_evidence_manifest_content_id = "sha256:" + "d" * 64
    payload.update(
        {
            "schema_version": OPERATION_CHECKPOINT_SCHEMA_VERSION_V2,
            "perspective": perspective,
            "operation_anchor_event_id": "event:a",
            "operation_anchor_at": "2026-07-17T05:30:00Z",
            "operation_anchor_ordering_key": [
                "2026-07-17T05:30:00Z",
                2,
                "1",
                "event:a",
            ],
            "information_time_policy_version": (
                PUBLIC_INFORMATION_POLICY_VERSION
            ),
            "knowledge_cutoff": "2026-07-26T12:00:00Z",
        }
    )
    market = payload["status_axes"]["market"]
    market.update(
        {
            "perspective": perspective,
            "eligible_source_refs": (
                [market_source_ref]
                if perspective == "user"
                else []
            ),
            "retrospective_source_refs": (
                []
                if perspective == "user"
                else [market_source_ref]
            ),
            "unknown_source_refs": [],
            "publicly_available_at": "2026-07-16T07:00:00Z",
            "publicly_available_basis": "verified_publication_interval",
            "temporal_role": (
                "user_known_at_operation_by_verified_publication"
                if perspective == "user"
                else "retrospective_context"
            ),
            "status": "available" if perspective == "user" else "missing",
            "representative_source_id": market_source_ref,
            "representative_source_content_id": "sha256:" + "a" * 64,
            "information_time": {
                "status": "verified",
                "lower_bound": "2026-07-16T00:00:00Z",
                "upper_bound": "2026-07-16T07:00:00Z",
                "basis": "provider_publication_date_source_timezone.v1",
                "method_version": "public_information_time.v1",
                "revision_ref": "revision:close:2026-07-16",
            },
            "version_provenance": {
                "status": "verified",
                "content_sha256": "sha256:" + "b" * 64,
                "source_ref": market_source_ref,
                "revision_ref": "revision:close:2026-07-16",
            },
            "perspective_eligibility": {
                "perspective": perspective,
                "status": "eligible" if perspective == "user" else "ineligible",
                "reason_code": (
                    "verified_publication_strictly_before_operation"
                    if perspective == "user"
                    else "system_observed_after_operation"
                ),
                "temporal_role": (
                    "user_known_at_operation_by_verified_publication"
                    if perspective == "user"
                    else "retrospective_public_context"
                ),
                "operation_anchor_at": "2026-07-17T05:30:00Z",
                "projected_user_known_at": (
                    "2026-07-17T05:30:00Z" if perspective == "user" else None
                ),
                "projected_system_known_at": None,
                "actual_user_observation_proven": False,
            },
            "market_evidence_manifest_content_id": (
                market_evidence_manifest_content_id
            ),
            "source_refs": sorted(
                set(market["source_refs"])
                | {
                    market_source_ref,
                    "market_evidence_manifest:"
                    + market_evidence_manifest_content_id,
                }
            ),
        }
    )
    fallback = payload["market_fallback"]
    fallback.update(
        {
            "policy_version": MARKET_FALLBACK_POLICY_VERSION_V2,
            "public_information_policy_version": (
                PUBLIC_INFORMATION_POLICY_VERSION
            ),
            "perspective": perspective,
            "limitation_code": (
                None if perspective == "user" else "withheld_by_cutoff"
            ),
            "guard_audit_at": (
                None if perspective == "user" else "2026-07-27T00:00:00Z"
            ),
            "request_count_status": "verified",
            "unverified_attempt_upper_bound": 0,
        }
    )
    if perspective == "system":
        guard_at = "2026-07-27T00:00:00Z"
        parameters = {"ts_code": "588200.SH", "trade_date": "20260716"}
        receipt = {
            "receipt_id": "",
            "provider_id": "tushare",
            "endpoint_id": "daily",
            "provider_version": "existing-adapter-v2",
            "redacted_parameters": parameters,
            "request_fingerprint_version": MARKET_REQUEST_FINGERPRINT_VERSION,
            "request_fingerprint": market_request_fingerprint(
                provider_id="tushare",
                endpoint_id="daily",
                provider_version="existing-adapter-v2",
                redacted_parameters=parameters,
            ),
            "guard_audit_at": guard_at,
            "started_at": guard_at,
            "completed_at": guard_at,
            "fetched_at": None,
            "system_observed_at": None,
            "response_status": "withheld_by_cutoff",
            "attempt_count": 0,
            "attempt_count_status": "verified",
            "budget_charged_attempts": 0,
            "raw_content_sha256": None,
            "normalized_content_sha256": None,
            "cache_entry_refs": [],
            "cache_lineage": ["market_requirement_v2:test"],
        }
        receipt["receipt_id"] = "market_fetch_receipt_v2_" + hashlib.sha256(
            canonical_json_bytes(receipt)
        ).hexdigest()
        fallback.update(
            {
                "coverage_before": "missing",
                "coverage_after": "missing",
                "status": "withheld_by_cutoff",
                "cache_refs": [],
                "fetch_receipt_refs": [receipt["receipt_id"]],
                "fetch_receipts": [receipt],
            }
        )
    payload["source_refs"] = sorted(
        set(payload["source_refs"])
        | {
            market_source_ref,
            "market_evidence_manifest:" + market_evidence_manifest_content_id,
        }
    )
    return payload


def _reidentify_v2_receipt(receipt: dict[str, object]) -> dict[str, object]:
    receipt["receipt_id"] = ""
    receipt["receipt_id"] = "market_fetch_receipt_v2_" + hashlib.sha256(
        canonical_json_bytes(receipt)
    ).hexdigest()
    return receipt


def fetch_receipt() -> dict[str, object]:
    parameters = {
        "ts_code": "588200.SH",
        "trade_date": "20260716",
    }
    provider_version = "existing-adapter-v1"
    return {
        "receipt_id": "fetch:1",
        "provider_id": "tushare",
        "endpoint_id": "daily",
        "provider_version": provider_version,
        "redacted_parameters": parameters,
        "request_fingerprint_version": MARKET_REQUEST_FINGERPRINT_VERSION,
        "request_fingerprint": market_request_fingerprint(
            provider_id="tushare",
            endpoint_id="daily",
            provider_version=provider_version,
            redacted_parameters=parameters,
        ),
        "started_at": "2026-07-25T10:00:00Z",
        "completed_at": "2026-07-25T10:00:01Z",
        "fetched_at": "2026-07-25T10:00:01Z",
        "response_status": "succeeded",
        "attempt_count": 1,
        "raw_content_sha256": "sha256:" + ("2" * 64),
        "normalized_content_sha256": "sha256:" + ("3" * 64),
        "cache_entry_refs": ["market_cache:1"],
        "cache_lineage": ["local_requirement:1"],
    }


def _schema_validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _schema_v2_validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_V2_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def test_v1_schema_bytes_remain_frozen_and_v2_schema_is_independent() -> None:
    assert hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest() == (
        "994c881379303101107b50286fafd7b38002f36f423d4eb3db4b9f1c01f1d373"
    )
    assert SCHEMA_V2_PATH != SCHEMA_PATH
    _schema_v2_validator()


def test_schema_accepts_ready_open_review_without_decision() -> None:
    record = OperationCheckpointRecord.from_mapping(checkpoint_input())
    payload = record.to_dict()
    assert payload["schema_version"] == OPERATION_CHECKPOINT_SCHEMA_VERSION
    assert payload["status_axes"]["operation"]["status"] == "ready"
    assert payload["status_axes"]["decision"]["status"] == "not_recorded"
    assert payload["status_axes"]["lifecycle"]["status"] == "open"
    assert payload["status_axes"]["outcome"]["status"] == "interim"
    _schema_validator().validate(payload)


def test_schema_and_model_require_six_closed_independent_axes() -> None:
    missing = checkpoint_input()
    del missing["status_axes"]["decision"]
    with pytest.raises(ModelValidationError, match="missing required fields"):
        OperationCheckpointRecord.from_mapping(missing)

    hostile = checkpoint_input()
    hostile["status_axes"]["operation"]["motive"] = "fabricated"
    with pytest.raises(ModelValidationError, match="unsupported fields"):
        OperationCheckpointRecord.from_mapping(hostile)

    normalized = OperationCheckpointRecord.from_mapping(checkpoint_input()).to_dict()
    schema = _schema_validator()
    extra = deepcopy(normalized)
    extra["advice"] = "BUY"
    errors = list(schema.iter_errors(extra))
    assert errors


def test_json_schema_rejects_cross_axis_and_fallback_state_drift() -> None:
    validator = _schema_validator()
    canonical = OperationCheckpointRecord.from_mapping(checkpoint_input()).to_dict()

    operation_without_evidence = deepcopy(canonical)
    operation_without_evidence["status_axes"]["operation"]["source_refs"] = []
    assert list(validator.iter_errors(operation_without_evidence))

    inconsistent_snapshot = deepcopy(canonical)
    inconsistent_snapshot["status_axes"]["snapshot_cash_valuation"]["status"] = (
        "available"
    )
    assert list(validator.iter_errors(inconsistent_snapshot))

    blocker_without_block = deepcopy(canonical)
    blocker_without_block["gaps"] = [
        {
            "gap_id": "gap-schema",
            "axis": "decision",
            "code": "DECISION_NOTE_MISSING",
            "severity": "blocker",
            "blocks_axis": False,
            "owner": "user",
            "next_step": "Preserve the missing state.",
            "source_refs": [],
        }
    ]
    assert list(validator.iter_errors(blocker_without_block))

    empty_success = deepcopy(canonical)
    empty_success["market_fallback"].update(
        coverage_before="missing",
        coverage_after="satisfied",
        status="succeeded",
        request_count=0,
        cache_refs=["market_cache:unproven"],
    )
    assert list(validator.iter_errors(empty_success))

    self_authorized = deepcopy(canonical)
    self_authorized["market_fallback"]["allowlist"][-1] = (
        "tushare:unapproved_endpoint"
    )
    assert list(validator.iter_errors(self_authorized))


def test_snapshot_fields_preserve_partial_without_zero_fill() -> None:
    payload = OperationCheckpointRecord.from_mapping(checkpoint_input()).to_dict()
    fields = payload["status_axes"]["snapshot_cash_valuation"]["fields"]
    assert fields["position_quantity"]["value"] == "8100"
    assert fields["cash"]["value"] is None
    assert fields["nav"]["value"] is None

    fabricated = checkpoint_input()
    fabricated["status_axes"]["snapshot_cash_valuation"]["fields"]["nav"]["value"] = "0"
    with pytest.raises(ModelValidationError, match="cannot supply a value"):
        OperationCheckpointRecord.from_mapping(fabricated)


def test_ready_and_available_states_require_evidence_and_consistent_components() -> None:
    operation_without_evidence = checkpoint_input()
    operation_without_evidence["status_axes"]["operation"]["source_refs"] = []
    with pytest.raises(ModelValidationError, match="operation ready or partial"):
        OperationCheckpointRecord.from_mapping(operation_without_evidence)

    partial_operation_without_evidence = checkpoint_input()
    partial_operation_without_evidence["status_axes"]["operation"].update(
        status="partial",
        source_refs=[],
    )
    with pytest.raises(ModelValidationError, match="operation ready or partial"):
        OperationCheckpointRecord.from_mapping(partial_operation_without_evidence)

    decision_without_evidence = checkpoint_input()
    decision_without_evidence["status_axes"]["decision"].update(
        status="complete",
        source_refs=[],
    )
    with pytest.raises(ModelValidationError, match="decision complete or partial"):
        OperationCheckpointRecord.from_mapping(decision_without_evidence)

    field_without_evidence = checkpoint_input()
    field_without_evidence["status_axes"]["snapshot_cash_valuation"]["fields"][
        "position_quantity"
    ]["source_refs"] = []
    with pytest.raises(ModelValidationError, match="requires source references"):
        OperationCheckpointRecord.from_mapping(field_without_evidence)

    available_with_missing = checkpoint_input()
    available_with_missing["status_axes"]["snapshot_cash_valuation"]["status"] = (
        "available"
    )
    with pytest.raises(ModelValidationError, match="cannot contain missing"):
        OperationCheckpointRecord.from_mapping(available_with_missing)

    available_without_component = checkpoint_input()
    snapshot = available_without_component["status_axes"]["snapshot_cash_valuation"]
    snapshot["status"] = "available"
    for field in snapshot["fields"].values():
        field.update(
            status="not_applicable",
            value=None,
            unit=None,
            source_refs=[],
        )
    with pytest.raises(ModelValidationError, match="at least one available component"):
        OperationCheckpointRecord.from_mapping(available_without_component)

    snapshot_without_axis_evidence = checkpoint_input()
    snapshot_without_axis_evidence["status_axes"]["snapshot_cash_valuation"][
        "source_refs"
    ] = []
    with pytest.raises(ModelValidationError, match="snapshot available or partial"):
        OperationCheckpointRecord.from_mapping(snapshot_without_axis_evidence)

    market_without_evidence = checkpoint_input()
    market_without_evidence["status_axes"]["market"]["source_refs"] = []
    with pytest.raises(ModelValidationError, match="material market states"):
        OperationCheckpointRecord.from_mapping(market_without_evidence)

    schema_base = OperationCheckpointRecord.from_mapping(checkpoint_input()).to_dict()
    schema_invalids = []
    for axis, status in (
        ("operation", "ready"),
        ("operation", "partial"),
        ("decision", "complete"),
        ("snapshot_cash_valuation", "partial"),
        ("market", "available"),
    ):
        invalid = deepcopy(schema_base)
        invalid["status_axes"][axis]["status"] = status
        invalid["status_axes"][axis]["source_refs"] = []
        schema_invalids.append(invalid)
    validator = _schema_validator()
    for invalid in schema_invalids:
        assert any(
            error.validator == "minItems"
            and list(error.absolute_path)[-1:] == ["source_refs"]
            for error in validator.iter_errors(invalid)
        )


def test_four_times_preserve_late_system_recording_and_owner_basis() -> None:
    payload = OperationCheckpointRecord.from_mapping(checkpoint_input()).to_dict()
    times = payload["time_provenance"]
    assert times["effective_at"]["value"] == "2026-07-17T05:30:00Z"
    assert times["user_known_at"]["value"] == "2026-07-17T05:30:00Z"
    assert times["system_observed_at"]["value"] == "2026-07-25T10:00:00Z"

    backdated = checkpoint_input()
    backdated["time_provenance"]["system_observed_at"]["value"] = (
        "2026-07-17T05:00:00Z"
    )
    with pytest.raises(ValueError, match="cannot be earlier"):
        OperationCheckpointRecord.from_mapping(backdated)

    system_owner = checkpoint_input()
    system_owner["time_provenance"]["system_observed_at"]["basis"] = (
        "owner_action_default"
    )
    with pytest.raises(ModelValidationError, match="cannot prove system observation"):
        OperationCheckpointRecord.from_mapping(system_owner)

    wrong_effective_basis = checkpoint_input()
    wrong_effective_basis["time_provenance"]["effective_at"]["basis"] = (
        "owner_action_default"
    )
    with pytest.raises(ModelValidationError, match="incompatible with this time field"):
        OperationCheckpointRecord.from_mapping(wrong_effective_basis)

    wrong_recorded_basis = checkpoint_input()
    wrong_recorded_basis["time_provenance"]["recorded_at"]["basis"] = (
        "owner_action_default"
    )
    with pytest.raises(ModelValidationError, match="incompatible with this time field"):
        OperationCheckpointRecord.from_mapping(wrong_recorded_basis)


def test_time_cutoffs_and_system_known_market_context_cannot_leak_future_data() -> None:
    cutoff_before_as_of = checkpoint_input()
    cutoff_before_as_of["knowledge_cutoff"] = "2026-07-17T05:45:00Z"
    with pytest.raises(ValueError, match="cannot be earlier"):
        OperationCheckpointRecord.from_mapping(cutoff_before_as_of)

    future_system_known = checkpoint_input()
    market = future_system_known["status_axes"]["market"]
    market["temporal_role"] = "system_known_at_decision"
    market["fetched_at"] = "2026-07-17T05:45:00Z"
    market["system_observed_at"] = "2026-07-17T06:30:00Z"
    with pytest.raises(ValueError, match="cannot be earlier"):
        OperationCheckpointRecord.from_mapping(future_system_known)

    reconstructed_after_cutoff = checkpoint_input()
    reconstructed_after_cutoff["status_axes"]["market"]["fetched_at"] = (
        "2026-07-26T00:00:00Z"
    )
    with pytest.raises(ValueError, match="cannot be earlier"):
        OperationCheckpointRecord.from_mapping(reconstructed_after_cutoff)

    fetched_before_effective = checkpoint_input()
    market = fetched_before_effective["status_axes"]["market"]
    market.update(
        temporal_role="system_known_at_decision",
        effective_at="2026-07-17T05:30:00Z",
        fetched_at="2026-07-17T05:00:00Z",
        system_observed_at="2026-07-17T05:00:00Z",
    )
    with pytest.raises(ValueError, match="cannot be earlier"):
        OperationCheckpointRecord.from_mapping(fetched_before_effective)


def test_blocker_gap_and_blocked_axis_must_agree_in_both_directions() -> None:
    mismatched_gap = checkpoint_input()
    mismatched_gap["gaps"] = [
        {
            "gap_id": "gap-decision",
            "axis": "decision",
            "code": "DECISION_LINK_AMBIGUOUS",
            "severity": "blocker",
            "blocks_axis": True,
            "owner": "system",
            "next_step": "Resolve the explicit link.",
            "source_refs": ["episode:1"],
        }
    ]
    with pytest.raises(ModelValidationError, match="blocked axis state"):
        OperationCheckpointRecord.from_mapping(mismatched_gap)

    unexplained_block = checkpoint_input()
    unexplained_block["status_axes"]["decision"]["status"] = "blocked"
    with pytest.raises(ModelValidationError, match="requires an explicit blocker gap"):
        OperationCheckpointRecord.from_mapping(unexplained_block)

    blocker_not_blocking = checkpoint_input()
    blocker_not_blocking["gaps"] = [
        {
            "gap_id": "gap-warning",
            "axis": "decision",
            "code": "DECISION_NOTE_MISSING",
            "severity": "blocker",
            "blocks_axis": False,
            "owner": "user",
            "next_step": "Record evidence if available.",
            "source_refs": [],
        }
    ]
    with pytest.raises(ModelValidationError, match="must explicitly block"):
        OperationCheckpointRecord.from_mapping(blocker_not_blocking)


def test_open_interim_is_not_a_gap() -> None:
    invalid = checkpoint_input()
    invalid["gaps"] = [
        {
            "gap_id": "gap-open",
            "axis": "outcome",
            "code": "OPEN_EPISODE_OUTCOME_NOT_FINAL",
            "severity": "info",
            "blocks_axis": False,
            "owner": "system",
            "next_step": "Continue periodic review.",
            "source_refs": ["episode:1"],
        }
    ]
    with pytest.raises(ModelValidationError, match="not a review gap"):
        OperationCheckpointRecord.from_mapping(invalid)


def test_review_kind_checkpoint_type_and_lifecycle_outcome_are_compatible() -> None:
    open_final = checkpoint_input()
    open_final["status_axes"]["outcome"]["status"] = "final"
    with pytest.raises(ModelValidationError, match="active checkpoint requires"):
        OperationCheckpointRecord.from_mapping(open_final)

    disguised_postmortem = checkpoint_input()
    disguised_postmortem["review_kind"] = "postmortem"
    with pytest.raises(ModelValidationError, match="active_checkpoint review kind"):
        OperationCheckpointRecord.from_mapping(disguised_postmortem)

    closed_interim = checkpoint_input()
    closed_interim["review_kind"] = "operation_review"
    closed_interim["checkpoint_type"] = "entry"
    closed_interim["status_axes"]["lifecycle"]["status"] = "closed"
    with pytest.raises(ModelValidationError, match="closed lifecycle"):
        OperationCheckpointRecord.from_mapping(closed_interim)


def test_market_local_hit_forces_zero_network_and_offline_consumers() -> None:
    invalid = checkpoint_input()
    failed_receipt = fetch_receipt()
    failed_receipt.update(
        response_status="failed",
        fetched_at=None,
        raw_content_sha256=None,
        normalized_content_sha256=None,
        cache_entry_refs=[],
    )
    invalid["market_fallback"]["request_count"] = 1
    invalid["market_fallback"]["status"] = "failed"
    invalid["market_fallback"]["fetch_receipt_refs"] = ["fetch:1"]
    invalid["market_fallback"]["fetch_receipts"] = [failed_receipt]
    with pytest.raises(ModelValidationError, match="satisfied local coverage"):
        OperationCheckpointRecord.from_mapping(invalid)

    online = checkpoint_input()
    online["market_fallback"]["offline_consumers"]["renderer"] = True
    with pytest.raises(ModelValidationError, match="must remain offline"):
        OperationCheckpointRecord.from_mapping(online)


@pytest.mark.parametrize("coverage", ["missing", "stale", "insufficient"])
def test_market_fallback_trigger_is_exactly_closed(coverage: str) -> None:
    payload = checkpoint_input()
    receipt = fetch_receipt()
    payload["market_fallback"].update(
        coverage_before=coverage,
        coverage_after="satisfied",
        status="succeeded",
        request_count=1,
        cache_refs=["market_cache:1"],
        fetch_receipt_refs=["fetch:1"],
        fetch_receipts=[receipt],
    )
    payload["status_axes"]["market"]["source_refs"].append("market_cache:1")
    payload["status_axes"]["market"]["fetched_at"] = receipt["fetched_at"]
    record = OperationCheckpointRecord.from_mapping(payload)
    assert record.to_dict()["market_fallback"]["coverage_before"] == coverage


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("timeout_seconds", 21),
        ("max_retries", 3),
        ("max_concurrency", 3),
        ("max_requests_per_run", 21),
    ],
)
def test_market_fallback_caps_are_frozen(field: str, value: int) -> None:
    payload = checkpoint_input()
    payload["market_fallback"]["limits"][field] = value
    with pytest.raises(ModelValidationError, match="frozen policy"):
        OperationCheckpointRecord.from_mapping(payload)


def test_market_receipt_requires_allowlist_redaction_hashes_and_cache_lineage() -> None:
    payload = checkpoint_input()
    receipt = fetch_receipt()
    payload["market_fallback"].update(
        coverage_before="missing",
        coverage_after="satisfied",
        status="succeeded",
        request_count=1,
        cache_refs=["market_cache:1"],
        fetch_receipt_refs=["fetch:1"],
        fetch_receipts=[receipt],
    )
    payload["status_axes"]["market"]["source_refs"].append("market_cache:1")
    payload["status_axes"]["market"]["fetched_at"] = receipt["fetched_at"]
    normalized = OperationCheckpointRecord.from_mapping(payload).to_dict()
    _schema_validator().validate(normalized)
    receipt = normalized["market_fallback"]["fetch_receipts"][0]
    assert receipt["cache_entry_refs"] == ["market_cache:1"]
    assert receipt["raw_content_sha256"].startswith("sha256:")

    stock_basic = deepcopy(payload)
    stock_receipt = fetch_receipt()
    stock_parameters = {
        "exchange": "",
        "list_status": "L",
        "fields": "ts_code,name,industry",
    }
    stock_receipt.update(
        provider_id="tushare",
        endpoint_id="stock_basic",
        redacted_parameters=stock_parameters,
        request_fingerprint=market_request_fingerprint(
            provider_id="tushare",
            endpoint_id="stock_basic",
            provider_version="existing-adapter-v1",
            redacted_parameters=stock_parameters,
        ),
    )
    stock_basic["market_fallback"]["fetch_receipts"] = [stock_receipt]
    stock_basic_normalized = OperationCheckpointRecord.from_mapping(
        stock_basic
    ).to_dict()
    _schema_validator().validate(stock_basic_normalized)
    assert stock_basic_normalized["market_fallback"]["fetch_receipts"][0][
        "redacted_parameters"
    ]["exchange"] == ""

    secret = deepcopy(payload)
    secret["market_fallback"]["fetch_receipts"][0]["redacted_parameters"][
        "api_token"
    ] = "must-not-persist"
    with pytest.raises(ModelValidationError, match="secret fields"):
        OperationCheckpointRecord.from_mapping(secret)

    authorization = deepcopy(payload)
    authorization["market_fallback"]["fetch_receipts"][0][
        "redacted_parameters"
    ]["authorization"] = "Bearer must-not-persist"
    with pytest.raises(ModelValidationError, match="secret fields"):
        OperationCheckpointRecord.from_mapping(authorization)

    secret_value = deepcopy(payload)
    secret_parameters = secret_value["market_fallback"]["fetch_receipts"][0][
        "redacted_parameters"
    ]
    secret_parameters["fields"] = "Bearer"
    secret_value["market_fallback"]["fetch_receipts"][0][
        "request_fingerprint"
    ] = market_request_fingerprint(
        provider_id="tushare",
        endpoint_id="daily",
        provider_version="existing-adapter-v1",
        redacted_parameters=secret_parameters,
    )
    with pytest.raises(ModelValidationError, match="secret material"):
        OperationCheckpointRecord.from_mapping(secret_value)

    wrong_frequency = deepcopy(payload)
    bao_parameters = {
        "code": "sh.588200",
        "fields": "date,time,code,open,high,low,close,volume,amount,adjustflag",
        "start_date": "2026-07-16",
        "end_date": "2026-07-16",
        "frequency": "15",
        "adjustflag": "3",
    }
    wrong_frequency["market_fallback"]["fetch_receipts"][0].update(
        provider_id="baostock",
        endpoint_id="history_k_data_plus_5m",
        redacted_parameters=bao_parameters,
        request_fingerprint=market_request_fingerprint(
            provider_id="baostock",
            endpoint_id="history_k_data_plus_5m",
            provider_version="existing-adapter-v1",
            redacted_parameters=bao_parameters,
        ),
    )
    with pytest.raises(ModelValidationError, match="invalid for frequency"):
        OperationCheckpointRecord.from_mapping(wrong_frequency)

    wrong_parameter = deepcopy(payload)
    wrong_parameter["market_fallback"]["fetch_receipts"][0][
        "redacted_parameters"
    ]["exchange"] = "SSE"
    with pytest.raises(ModelValidationError, match="not allowlisted"):
        OperationCheckpointRecord.from_mapping(wrong_parameter)

    fingerprint_drift = deepcopy(payload)
    fingerprint_drift["market_fallback"]["fetch_receipts"][0][
        "redacted_parameters"
    ]["trade_date"] = "20260717"
    with pytest.raises(ModelValidationError, match="canonical request"):
        OperationCheckpointRecord.from_mapping(fingerprint_drift)

    unlisted = deepcopy(payload)
    unlisted["market_fallback"]["fetch_receipts"][0]["endpoint_id"] = (
        "unapproved_endpoint"
    )
    with pytest.raises(ModelValidationError, match="not allowlisted"):
        OperationCheckpointRecord.from_mapping(unlisted)

    missing_hash = deepcopy(payload)
    missing_hash["market_fallback"]["fetch_receipts"][0][
        "normalized_content_sha256"
    ] = None
    with pytest.raises(ModelValidationError, match="successful market fetch"):
        OperationCheckpointRecord.from_mapping(missing_hash)


def test_market_allowlist_is_code_owned_and_cannot_self_authorize() -> None:
    payload = checkpoint_input()
    changed_allowlist = sorted(
        (set(MARKET_PROVIDER_ALLOWLIST) - {"tushare:daily"})
        | {"tushare:unapproved_endpoint"}
    )
    payload["market_fallback"]["allowlist"] = changed_allowlist
    payload["market_fallback"]["allowlist_version"] = MARKET_PROVIDER_ALLOWLIST_VERSION
    with pytest.raises(ModelValidationError, match="code-owned frozen allowlist"):
        OperationCheckpointRecord.from_mapping(payload)

    wrong_version = checkpoint_input()
    wrong_version["market_fallback"]["allowlist_version"] = "caller_owned_v1"
    with pytest.raises(ModelValidationError, match="allowlist version"):
        OperationCheckpointRecord.from_mapping(wrong_version)

    wrong_hash = checkpoint_input()
    wrong_hash["market_fallback"]["allowlist_sha256"] = "sha256:" + ("0" * 64)
    with pytest.raises(ModelValidationError, match="allowlist hash"):
        OperationCheckpointRecord.from_mapping(wrong_hash)


def test_market_request_cap_counts_every_http_attempt_and_closes_success_state() -> None:
    excessive = checkpoint_input()
    receipts = []
    for index in range(20):
        receipt = fetch_receipt()
        receipt.update(
            receipt_id=f"fetch:{index:02d}",
            response_status="failed",
            attempt_count=3,
            fetched_at=None,
            raw_content_sha256=None,
            normalized_content_sha256=None,
            cache_entry_refs=[],
        )
        receipts.append(receipt)
    excessive["market_fallback"].update(
        coverage_before="missing",
        coverage_after="missing",
        status="failed",
        request_count=20,
        fetch_receipt_refs=[item["receipt_id"] for item in receipts],
        fetch_receipts=receipts,
    )
    with pytest.raises(ModelValidationError, match="all HTTP attempts"):
        OperationCheckpointRecord.from_mapping(excessive)

    too_many_receipts = checkpoint_input()
    success = fetch_receipt()
    receipts = [success]
    for index in range(20):
        unavailable = fetch_receipt()
        unavailable.update(
            receipt_id=f"unavailable:{index:02d}",
            response_status="provider_unavailable",
            attempt_count=0,
            fetched_at=None,
            raw_content_sha256=None,
            normalized_content_sha256=None,
            cache_entry_refs=[],
        )
        receipts.append(unavailable)
    too_many_receipts["market_fallback"].update(
        coverage_before="missing",
        coverage_after="satisfied",
        status="succeeded",
        request_count=1,
        cache_refs=["market_cache:1"],
        fetch_receipt_refs=[item["receipt_id"] for item in receipts],
        fetch_receipts=receipts,
    )
    too_many_receipts["status_axes"]["market"]["source_refs"].append(
        "market_cache:1"
    )
    too_many_receipts["status_axes"]["market"]["fetched_at"] = success["fetched_at"]
    with pytest.raises(ModelValidationError, match="cannot exceed 20"):
        OperationCheckpointRecord.from_mapping(too_many_receipts)

    empty_success = checkpoint_input()
    empty_success["market_fallback"].update(
        coverage_before="missing",
        coverage_after="satisfied",
        status="succeeded",
        request_count=0,
        cache_refs=["market_cache:unproven"],
    )
    with pytest.raises(ModelValidationError, match="successful receipt"):
        OperationCheckpointRecord.from_mapping(empty_success)

    false_not_needed = checkpoint_input()
    false_not_needed["market_fallback"].update(
        coverage_before="missing",
        coverage_after="missing",
        status="not_needed",
    )
    with pytest.raises(ModelValidationError, match="only when local coverage"):
        OperationCheckpointRecord.from_mapping(false_not_needed)


def test_market_fallback_coverage_receipts_and_frozen_context_are_closed() -> None:
    local_without_cache_ref = checkpoint_input()
    local_without_cache_ref["market_fallback"]["cache_refs"] = []
    with pytest.raises(ModelValidationError, match="frozen local cache refs"):
        OperationCheckpointRecord.from_mapping(local_without_cache_ref)

    satisfied_but_missing = checkpoint_input()
    market = satisfied_but_missing["status_axes"]["market"]
    market["status"] = "missing"
    market["temporal_role"] = "missing"
    with pytest.raises(ModelValidationError, match="coverage_after"):
        OperationCheckpointRecord.from_mapping(satisfied_but_missing)

    missing_but_available = checkpoint_input()
    unavailable = fetch_receipt()
    unavailable.update(
        response_status="provider_unavailable",
        attempt_count=0,
        fetched_at=None,
        raw_content_sha256=None,
        normalized_content_sha256=None,
        cache_entry_refs=[],
    )
    missing_but_available["market_fallback"].update(
        coverage_before="missing",
        coverage_after="missing",
        status="provider_unavailable",
        request_count=0,
        cache_refs=[],
        fetch_receipt_refs=["fetch:1"],
        fetch_receipts=[unavailable],
    )
    with pytest.raises(ModelValidationError, match="coverage_after"):
        OperationCheckpointRecord.from_mapping(missing_but_available)

    missing_requirement_lineage = checkpoint_input()
    failed_without_lineage = fetch_receipt()
    failed_without_lineage.update(
        response_status="failed",
        attempt_count=1,
        fetched_at=None,
        raw_content_sha256=None,
        normalized_content_sha256=None,
        cache_entry_refs=[],
        cache_lineage=[],
    )
    missing_requirement_lineage["market_fallback"].update(
        coverage_before="missing",
        coverage_after="missing",
        status="failed",
        request_count=1,
        cache_refs=[],
        fetch_receipt_refs=["fetch:1"],
        fetch_receipts=[failed_without_lineage],
    )
    missing_market = missing_requirement_lineage["status_axes"]["market"]
    missing_market.update(
        status="missing",
        temporal_role="missing",
        effective_at=None,
        fetched_at=None,
        system_observed_at=None,
        source_refs=[],
    )
    with pytest.raises(ModelValidationError, match="triggering cache requirement"):
        OperationCheckpointRecord.from_mapping(missing_requirement_lineage)

    cache_not_frozen = checkpoint_input()
    receipt = fetch_receipt()
    cache_not_frozen["market_fallback"].update(
        coverage_before="missing",
        coverage_after="satisfied",
        status="succeeded",
        request_count=1,
        cache_refs=["market_cache:1"],
        fetch_receipt_refs=["fetch:1"],
        fetch_receipts=[receipt],
    )
    cache_not_frozen["status_axes"]["market"]["fetched_at"] = receipt["fetched_at"]
    with pytest.raises(ModelValidationError, match="frozen fallback cache ref"):
        OperationCheckpointRecord.from_mapping(cache_not_frozen)

    future_receipt = checkpoint_input()
    failed = fetch_receipt()
    failed.update(
        response_status="failed",
        attempt_count=1,
        started_at="2030-01-01T00:00:00Z",
        completed_at="2030-01-01T00:00:01Z",
        fetched_at=None,
        raw_content_sha256=None,
        normalized_content_sha256=None,
        cache_entry_refs=[],
    )
    future_receipt["market_fallback"].update(
        coverage_before="missing",
        coverage_after="missing",
        status="failed",
        request_count=1,
        cache_refs=[],
        fetch_receipt_refs=["fetch:1"],
        fetch_receipts=[failed],
    )
    future_market = future_receipt["status_axes"]["market"]
    future_market.update(
        status="missing",
        temporal_role="missing",
        effective_at=None,
        fetched_at=None,
        system_observed_at=None,
        source_refs=[],
    )
    with pytest.raises(ValueError, match="cannot be earlier"):
        OperationCheckpointRecord.from_mapping(future_receipt)


def test_canonicalization_is_permutation_stable_and_rejects_float() -> None:
    left = checkpoint_input()
    right = deepcopy(left)
    right["source_refs"] = list(reversed(right["source_refs"]))
    right["market_fallback"]["allowlist"] = list(
        reversed(right["market_fallback"]["allowlist"])
    )
    right["status_axes"]["operation"]["source_refs"] = list(
        reversed(right["status_axes"]["operation"]["source_refs"])
    )
    first = OperationCheckpointRecord.from_mapping(left)
    second = OperationCheckpointRecord.from_mapping(right)
    assert first.canonical_bytes == second.canonical_bytes
    assert first.content_id == second.content_id

    binary_float = checkpoint_input()
    binary_float["status_axes"]["snapshot_cash_valuation"]["fields"][
        "position_quantity"
    ]["value"] = 8100.0
    with pytest.raises(ModelValidationError, match="binary float"):
        OperationCheckpointRecord.from_mapping(binary_float)

    object_ref = checkpoint_input()
    object_ref["source_refs"] = [{"not": "a stable string"}]
    with pytest.raises(ModelValidationError, match="must be a string"):
        OperationCheckpointRecord.from_mapping(object_ref)


def test_content_identity_drift_is_rejected() -> None:
    payload = OperationCheckpointRecord.from_mapping(checkpoint_input()).to_dict()
    payload["content_id"] = "sha256:" + ("0" * 64)
    with pytest.raises(ModelValidationError, match="content_id"):
        OperationCheckpointRecord.from_mapping(payload)


def test_checkpoint_identity_is_derived_from_the_semantic_cutoff() -> None:
    first = OperationCheckpointRecord.from_mapping(checkpoint_input())
    assert first.checkpoint_key.startswith("review_checkpoint_key_")
    assert len(first.checkpoint_key) == len("review_checkpoint_key_") + 64

    round_trip = checkpoint_input()
    round_trip["checkpoint_key"] = first.checkpoint_key
    assert (
        OperationCheckpointRecord.from_mapping(round_trip).checkpoint_id
        == first.checkpoint_id
    )

    caller_key = checkpoint_input()
    caller_key["checkpoint_key"] = "review_checkpoint_key_" + ("0" * 64)
    with pytest.raises(ModelValidationError, match="canonical semantic identity"):
        OperationCheckpointRecord.from_mapping(caller_key)

    content_change = checkpoint_input()
    content_change["status_axes"]["operation"]["summary"] = "Changed content."
    changed = OperationCheckpointRecord.from_mapping(content_change)
    assert changed.checkpoint_key == first.checkpoint_key
    assert changed.checkpoint_id == first.checkpoint_id
    assert changed.content_id != first.content_id

    case_drift = checkpoint_input()
    case_drift["position_case_id"] = "caller-controlled-fork"
    changed_case = OperationCheckpointRecord.from_mapping(case_drift)
    assert changed_case.checkpoint_key == first.checkpoint_key
    assert changed_case.checkpoint_id == first.checkpoint_id
    assert changed_case.content_id != first.content_id


def _file_state(path: Path) -> tuple[bytes, tuple[tuple[bool, int, bytes | None], ...]]:
    auxiliary = []
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(path) + suffix)
        auxiliary.append(
            (
                sidecar.exists(),
                sidecar.stat().st_size if sidecar.exists() else 0,
                sidecar.read_bytes() if sidecar.exists() else None,
            )
        )
    return path.read_bytes(), tuple(auxiliary)


def _leave_detached_zero_wal_pair(database: Path) -> None:
    script = """
import os
import sqlite3
import sys

connection = sqlite3.connect(sys.argv[1])
connection.execute("BEGIN IMMEDIATE")
connection.rollback()
result = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
if tuple(int(value) for value in result) != (0, 0, 0):
    os._exit(91)
os._exit(0)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(database)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    wal_path = Path(f"{database}-wal")
    shm_path = Path(f"{database}-shm")
    assert wal_path.is_file() and wal_path.stat().st_size == 0
    assert shm_path.is_file() and shm_path.stat().st_size == 32768


class _FakeUpgradeHeld:
    def __init__(self, path: Path, *, identity: int, size: int) -> None:
        self.path = path
        self.identity = identity
        self.size = size
        self.fail_identity = False
        self.fail_size = False
        self.fail_binding = False

    def assert_held_identity(self, *, stage: str) -> tuple[int, int, int, int]:
        if self.fail_identity:
            raise ReviewStoreError(f"synthetic held identity drift at {stage}")
        return (1, self.identity, self.size, 0)

    def assert_held_identity_and_size(self, *, stage: str) -> None:
        self.assert_held_identity(stage=stage)
        if self.fail_size:
            raise ReviewStoreError(f"synthetic held size drift at {stage}")

    def assert_current_binding(self, *, stage: str) -> None:
        self.assert_held_identity(stage=stage)
        if self.fail_binding:
            raise ReviewStoreError(f"synthetic pathname identity drift at {stage}")


def _fake_upgrade_guard(
    tmp_path: Path,
    label: str,
) -> tuple[object, Path, Path, dict[str, _FakeUpgradeHeld]]:
    database = tmp_path / f"{label}.sqlite3"
    wal_path = Path(f"{database}-wal")
    shm_path = Path(f"{database}-shm")
    database.write_bytes(b"main")
    wal_path.write_bytes(b"")
    shm_path.write_bytes(b"\0" * 32768)
    files = {
        "main": _FakeUpgradeHeld(database, identity=1, size=4),
        "wal": _FakeUpgradeHeld(wal_path, identity=2, size=0),
        "shm": _FakeUpgradeHeld(shm_path, identity=3, size=32768),
    }
    guard = review_store_module._ReviewabilityUpgradeFileGuard.__new__(
        review_store_module._ReviewabilityUpgradeFileGuard
    )
    guard.path = database
    guard.expected_main = (1, 1, 4, 0, hashlib.sha256(b"main").hexdigest())
    guard.expected_wal = (1, 2, 0, 0, hashlib.sha256(b"").hexdigest())
    guard.expected_shm = (
        1,
        3,
        32768,
        0,
        hashlib.sha256(b"\0" * 32768).hexdigest(),
    )
    guard._files = files
    guard._writer_open = False
    guard._writer_conn = None
    guard._marker_committed = False
    guard._checkpoint_complete = False
    guard._checkpoint_result = None
    guard._auxiliary_terminal_absent = False
    return guard, wal_path, shm_path, files


def test_reviewability_initializer_is_new_candidate_only_and_idempotent(
    tmp_path: Path,
) -> None:
    legacy_path = tmp_path / "legacy-v1.sqlite3"
    legacy_conn = sqlite3.connect(legacy_path)
    try:
        legacy_conn.execute("PRAGMA application_id = 0x49525657")
        legacy_conn.execute("PRAGMA user_version = 1")
        legacy_conn.execute(
            "CREATE TABLE schema_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        legacy_conn.execute(
            "INSERT INTO schema_meta VALUES ('schema_version', '1')"
        )
        legacy_conn.commit()
    finally:
        legacy_conn.close()
    before_legacy = _file_state(legacy_path)
    with pytest.raises(ReviewStoreError, match="refusing silent upgrade"):
        ReviewStore(legacy_path).initialize_reviewability_candidate()
    assert _file_state(legacy_path) == before_legacy

    unrelated_path = tmp_path / "unrelated.sqlite3"
    unrelated_conn = sqlite3.connect(unrelated_path)
    try:
        unrelated_conn.execute("CREATE TABLE portfolio_marker(value TEXT)")
        unrelated_conn.execute("INSERT INTO portfolio_marker VALUES ('preserve')")
        unrelated_conn.commit()
    finally:
        unrelated_conn.close()
    before_unrelated = _file_state(unrelated_path)
    with pytest.raises(ReviewStoreError, match="refusing silent upgrade"):
        ReviewStore(unrelated_path).initialize_reviewability_candidate()
    assert _file_state(unrelated_path) == before_unrelated

    zero_byte_path = tmp_path / "existing-zero-byte.sqlite3"
    zero_byte_path.write_bytes(b"")
    before_zero_byte = _file_state(zero_byte_path)
    with pytest.raises(ReviewStoreError, match="refusing silent upgrade"):
        ReviewStore(zero_byte_path).initialize_reviewability_candidate()
    assert _file_state(zero_byte_path) == before_zero_byte

    core_path = tmp_path / "existing-core.sqlite3"
    core = ReviewStore(core_path)
    core.initialize()
    assert core.status()["reviewability_schema_version"] is None
    before_core = _file_state(core_path)
    with pytest.raises(ReviewStoreError, match="refusing silent upgrade"):
        core.initialize_reviewability_candidate()
    assert _file_state(core_path) == before_core

    product_path = tmp_path / "existing-product.sqlite3"
    product = ReviewStore(product_path)
    product.initialize()
    product.initialize_product_completion()
    before_product = _file_state(product_path)
    with pytest.raises(ReviewStoreError, match="refusing silent upgrade"):
        product.initialize_reviewability_candidate()
    assert _file_state(product_path) == before_product

    candidate_path = tmp_path / "new-v3-candidate.sqlite3"
    candidate = ReviewStore(candidate_path)
    first = candidate.initialize_reviewability_candidate()
    after_first = _file_state(candidate_path)
    second = candidate.initialize_reviewability_candidate()
    assert second == first
    assert _file_state(candidate_path) == after_first
    status = candidate.status()
    assert status["reviewability_schema_version"] == REVIEWABILITY_SCHEMA_VERSION
    assert (
        status["reviewability_checkpoint_contract_version"]
        == OPERATION_CHECKPOINT_SCHEMA_VERSION
    )
    assert status["reviewability_market_policy_version"] == (
        MARKET_FALLBACK_POLICY_VERSION
    )
    assert status["reviewability_market_provider_allowlist_version"] == (
        MARKET_PROVIDER_ALLOWLIST_VERSION
    )
    assert status["reviewability_market_provider_allowlist_sha256"] == (
        MARKET_PROVIDER_ALLOWLIST_SHA256
    )
    assert status["reviewability_schema_manifest_sha256"] == (
        REVIEWABILITY_SCHEMA_MANIFEST_SHA256
    )
    assert status["counts"]["operation_review_checkpoints"] == 0
    assert status["counts"]["operation_checkpoint_gaps"] == 0
    after_status = _file_state(candidate_path)
    third = candidate.initialize_reviewability_candidate()
    assert third == first
    assert _file_state(candidate_path) == after_status


@pytest.mark.parametrize(
    "drift_sql",
    [
        "DELETE FROM schema_meta WHERE key='reviewability_schema_version'",
        "DELETE FROM schema_meta WHERE key='p2h_stage1_schema_version'",
        "DELETE FROM schema_meta WHERE key='p2h_stage2_slice_a_schema_version'",
        "UPDATE schema_meta SET value='not-a-time' WHERE key='initialized_at'",
        "UPDATE schema_meta SET value='2' WHERE key='reviewability_schema_version'",
        (
            "UPDATE schema_meta SET value='bad' "
            "WHERE key='reviewability_schema_manifest_sha256'"
        ),
        "DROP INDEX idx_operation_checkpoints_case_time",
        "CREATE VIEW unexpected_review_view AS SELECT 1 AS value",
        (
            "CREATE TRIGGER unexpected_review_trigger "
            "AFTER INSERT ON operation_review_checkpoints "
            "BEGIN SELECT 1; END"
        ),
        "PRAGMA journal_mode=DELETE",
    ],
)
def test_reviewability_refuses_marker_or_structure_drift_without_repair(
    tmp_path: Path, drift_sql: str
) -> None:
    database = tmp_path / "drifted.sqlite3"
    store = ReviewStore(database)
    store.initialize_reviewability_candidate()
    conn = sqlite3.connect(database)
    try:
        conn.execute(drift_sql)
        conn.commit()
    finally:
        conn.close()
    before = _file_state(database)
    with pytest.raises(ReviewStoreError, match="refusing silent upgrade"):
        store.initialize_reviewability_candidate()
    assert _file_state(database) == before


def test_reviewability_manifest_rejects_constraint_drift_with_same_columns(
    tmp_path: Path,
) -> None:
    database = tmp_path / "constraint-drift.sqlite3"
    store = ReviewStore(database)
    store.initialize_reviewability_candidate()
    conn = sqlite3.connect(database)
    try:
        conn.execute("PRAGMA writable_schema = ON")
        conn.execute(
            """
            UPDATE sqlite_master
            SET sql = replace(
                sql,
                'checkpoint_key TEXT NOT NULL UNIQUE',
                'checkpoint_key TEXT UNIQUE'
            )
            WHERE type = 'table' AND name = 'operation_review_checkpoints'
            """
        )
        conn.execute("PRAGMA writable_schema = OFF")
        conn.commit()
    finally:
        conn.close()
    before = _file_state(database)
    with pytest.raises(ReviewStoreError, match="refusing silent upgrade"):
        store.initialize_reviewability_candidate()
    assert _file_state(database) == before


def test_reviewability_manifest_covers_core_foundation_constraints(
    tmp_path: Path,
) -> None:
    database = tmp_path / "core-constraint-drift.sqlite3"
    store = ReviewStore(database)
    store.initialize_reviewability_candidate()
    conn = sqlite3.connect(database)
    try:
        conn.execute("PRAGMA writable_schema = ON")
        conn.execute(
            """
            UPDATE sqlite_master
            SET sql = replace(
                sql,
                'value TEXT NOT NULL',
                'value TEXT'
            )
            WHERE type = 'table' AND name = 'schema_meta'
            """
        )
        conn.execute("PRAGMA writable_schema = OFF")
        conn.commit()
    finally:
        conn.close()
    before = _file_state(database)
    with pytest.raises(ReviewStoreError, match="refusing silent upgrade"):
        store.initialize_reviewability_candidate()
    assert _file_state(database) == before


def test_reviewability_immutable_gate_rejects_committed_live_wal_drift(
    tmp_path: Path,
) -> None:
    database = tmp_path / "live-wal-drift.sqlite3"
    store = ReviewStore(database)
    store.initialize_reviewability_candidate()
    writer = sqlite3.connect(database)
    try:
        writer.execute("CREATE VIEW unexpected_live_wal_view AS SELECT 1 AS value")
        writer.commit()
        assert Path(f"{database}-wal").exists()
        with pytest.raises(ReviewStoreError, match="nonempty WAL"):
            store.initialize_reviewability_candidate()
    finally:
        writer.close()


def test_status_rejects_reviewability_manifest_drift(
    tmp_path: Path,
) -> None:
    database = tmp_path / "status-drift.sqlite3"
    store = ReviewStore(database)
    store.initialize_reviewability_candidate()
    conn = sqlite3.connect(database)
    try:
        conn.execute("CREATE VIEW unexpected_status_view AS SELECT 1 AS value")
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(ReviewStoreError, match="structure or constraints drifted"):
        store.status()


def test_reviewability_initializer_checks_owned_path_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "identity-race.sqlite3"
    monkeypatch.setattr("src.investment_review.store.os.path.samestat", lambda *_: False)
    with pytest.raises(ReviewStoreError, match="path identity changed"):
        ReviewStore(database).initialize_reviewability_candidate()
    assert database.exists()
    assert database.stat().st_size == 0


def test_reviewability_initializer_rechecks_owned_path_after_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "identity-race-after-validation.sqlite3"
    original_samestat = os.path.samestat
    calls = 0

    def staged_samestat(left: os.stat_result, right: os.stat_result) -> bool:
        nonlocal calls
        calls += 1
        return calls < 5 and original_samestat(left, right)

    monkeypatch.setattr(
        "src.investment_review.store.os.path.samestat",
        staged_samestat,
    )
    with pytest.raises(ReviewStoreError, match="path identity changed"):
        ReviewStore(database).initialize_reviewability_candidate()
    assert calls == 5


def test_checkpoint_store_is_create_only_idempotent_and_key_drift_safe(
    tmp_path: Path,
) -> None:
    store = ReviewStore(tmp_path / "candidate.sqlite3")
    store.initialize_reviewability_candidate()
    raw = checkpoint_input()
    first = store.save_operation_checkpoint(raw)
    second = store.save_operation_checkpoint(raw)
    assert first["status"] == "INSERTED"
    assert second["status"] == "SKIPPED"
    stored = store.get_operation_checkpoint(first["checkpoint_id"])
    assert stored["content_id"] == first["content_id"]
    assert store.list_operation_checkpoints(position_case_id="case:episode-1") == [
        stored
    ]

    drift = checkpoint_input()
    drift["status_axes"]["operation"]["summary"] = "changed immutable summary"
    with pytest.raises(DataConflictError, match="changed after creation"):
        store.save_operation_checkpoint(drift)

    case_fork = checkpoint_input()
    case_fork["position_case_id"] = "caller-controlled-fork"
    with pytest.raises(DataConflictError, match="changed after creation"):
        store.save_operation_checkpoint(case_fork)


def test_checkpoint_save_revalidates_candidate_inside_write_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ReviewStore(tmp_path / "write-lock-validation.sqlite3")
    store.initialize_reviewability_candidate()
    original = ReviewStore._validate_reviewability_candidate
    transaction_states: list[bool] = []

    def spy(conn: sqlite3.Connection) -> None:
        transaction_states.append(conn.in_transaction)
        original(conn)

    monkeypatch.setattr(
        ReviewStore,
        "_validate_reviewability_candidate",
        staticmethod(spy),
    )
    store.save_operation_checkpoint(checkpoint_input())
    assert True in transaction_states


def test_checkpoint_store_semantic_cutoff_is_uniquely_constrained(
    tmp_path: Path,
) -> None:
    store = ReviewStore(tmp_path / "semantic-unique.sqlite3")
    store.initialize_reviewability_candidate()
    receipt = store.save_operation_checkpoint(checkpoint_input())
    conn = sqlite3.connect(store.path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO operation_review_checkpoints(
                    checkpoint_id, checkpoint_key, content_id, episode_id,
                    position_case_id, review_kind, checkpoint_type,
                    perspective, as_of, knowledge_cutoff, effective_at,
                    user_known_at, system_observed_at, recorded_at,
                    operation_status, decision_status, snapshot_status,
                    market_status, lifecycle_status, outcome_status,
                    payload_json, payload_sha256, inserted_at,
                    row_integrity_sha256
                )
                SELECT
                    ?, ?, ?, episode_id, position_case_id, review_kind,
                    checkpoint_type, perspective, as_of, knowledge_cutoff,
                    effective_at, user_known_at, system_observed_at, recorded_at,
                    operation_status, decision_status, snapshot_status,
                    market_status, lifecycle_status, outcome_status,
                    payload_json, payload_sha256, inserted_at,
                    row_integrity_sha256
                FROM operation_review_checkpoints
                WHERE checkpoint_id = ?
                """,
                (
                    "review_checkpoint_duplicate",
                    "review_checkpoint_key_" + ("f" * 64),
                    "sha256:" + ("f" * 64),
                    receipt["checkpoint_id"],
                ),
            )
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("label", "tamper_sql"),
    [
        (
            "payload_hash",
            "UPDATE operation_review_checkpoints "
            "SET payload_sha256 = 'bad' WHERE checkpoint_id = ?",
        ),
        (
            "projection",
            "UPDATE operation_review_checkpoints "
            "SET perspective = 'system' WHERE checkpoint_id = ?",
        ),
        (
            "payload_json",
            "UPDATE operation_review_checkpoints "
            "SET payload_json = payload_json || ' ' WHERE checkpoint_id = ?",
        ),
        (
            "inserted_at",
            "UPDATE operation_review_checkpoints "
            "SET inserted_at = '2026-07-26T00:00:00Z' WHERE checkpoint_id = ?",
        ),
        (
            "row_integrity",
            "UPDATE operation_review_checkpoints "
            "SET row_integrity_sha256 = 'bad' WHERE checkpoint_id = ?",
        ),
    ],
)
def test_checkpoint_reads_and_idempotent_save_fail_closed_on_main_row_tamper(
    tmp_path: Path,
    label: str,
    tamper_sql: str,
) -> None:
    store = ReviewStore(tmp_path / f"tamper-{label}.sqlite3")
    store.initialize_reviewability_candidate()
    raw = checkpoint_input()
    receipt = store.save_operation_checkpoint(raw)
    conn = sqlite3.connect(store.path)
    try:
        conn.execute(tamper_sql, (receipt["checkpoint_id"],))
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(ReviewStoreError):
        store.get_operation_checkpoint(receipt["checkpoint_id"])
    with pytest.raises(ReviewStoreError):
        store.list_operation_checkpoints()
    with pytest.raises(ReviewStoreError):
        store.save_operation_checkpoint(raw)


@pytest.mark.parametrize("tamper_kind", ["delete", "projection"])
def test_checkpoint_reads_fail_closed_on_gap_projection_tamper(
    tmp_path: Path,
    tamper_kind: str,
) -> None:
    store = ReviewStore(tmp_path / f"gap-{tamper_kind}.sqlite3")
    store.initialize_reviewability_candidate()
    raw = checkpoint_input()
    raw["gaps"] = [
        {
            "gap_id": "gap-decision-note",
            "axis": "decision",
            "code": "DECISION_NOTE_NOT_RECORDED",
            "severity": "warning",
            "blocks_axis": False,
            "owner": "user",
            "next_step": "Add a note only if contemporaneous evidence exists.",
            "source_refs": [],
        }
    ]
    receipt = store.save_operation_checkpoint(raw)
    conn = sqlite3.connect(store.path)
    try:
        if tamper_kind == "delete":
            conn.execute(
                "DELETE FROM operation_checkpoint_gaps WHERE checkpoint_id = ?",
                (receipt["checkpoint_id"],),
            )
        else:
            conn.execute(
                "UPDATE operation_checkpoint_gaps SET next_step = 'drift' "
                "WHERE checkpoint_id = ?",
                (receipt["checkpoint_id"],),
            )
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(ReviewStoreError):
        store.get_operation_checkpoint(receipt["checkpoint_id"])
    with pytest.raises(ReviewStoreError):
        store.save_operation_checkpoint(raw)


def test_checkpoint_store_replay_is_independent_of_semantic_set_order(
    tmp_path: Path,
) -> None:
    left = ReviewStore(tmp_path / "left.sqlite3")
    right = ReviewStore(tmp_path / "right.sqlite3")
    left.initialize_reviewability_candidate()
    right.initialize_reviewability_candidate()
    original = checkpoint_input()
    permuted = deepcopy(original)
    permuted["source_refs"] = list(reversed(permuted["source_refs"]))
    permuted["market_fallback"]["allowlist"] = list(
        reversed(permuted["market_fallback"]["allowlist"])
    )
    left_receipt = left.save_operation_checkpoint(original)
    right_receipt = right.save_operation_checkpoint(permuted)
    assert left_receipt["content_id"] == right_receipt["content_id"]
    assert left.list_operation_checkpoints() == right.list_operation_checkpoints()


def test_v2_checkpoint_binds_anchor_policy_and_strict_publication_boundary() -> None:
    payload = checkpoint_v2_input()
    record = OperationCheckpointRecordV2.from_mapping(payload)
    assert record.to_dict()["schema_version"] == OPERATION_CHECKPOINT_SCHEMA_VERSION_V2
    assert record.to_dict()["operation_anchor_at"] < record.to_dict()["as_of"]
    assert (
        record.to_dict()["status_axes"]["market"]["temporal_role"]
        == "user_known_at_operation_by_verified_publication"
    )
    _schema_v2_validator().validate(record.to_dict())

    equal_publication = checkpoint_v2_input()
    equal_publication["status_axes"]["market"]["publicly_available_at"] = (
        equal_publication["operation_anchor_at"]
    )
    equal_publication["status_axes"]["market"]["information_time"][
        "upper_bound"
    ] = equal_publication["operation_anchor_at"]
    with pytest.raises(ModelValidationError, match="strictly pre-operation"):
        OperationCheckpointRecordV2.from_mapping(equal_publication)

    with pytest.raises(ModelValidationError, match="unsupported fields"):
        OperationCheckpointRecord.from_mapping(payload)


def test_v2_system_late_observation_is_retrospective_zero_request() -> None:
    record = OperationCheckpointRecordV2.from_mapping(
        checkpoint_v2_input(perspective="system")
    ).to_dict()
    assert record["status_axes"]["market"]["status"] == "missing"
    assert record["market_fallback"]["status"] == "withheld_by_cutoff"
    assert record["market_fallback"]["request_count"] == 0
    assert record["market_fallback"]["fetch_receipts"][0]["attempt_count"] == 0
    assert record["market_fallback"]["fetch_receipts"][0]["started_at"] == (
        record["market_fallback"]["guard_audit_at"]
    )
    assert record["status_axes"]["market"]["system_observed_at"] > (
        record["operation_anchor_at"]
    )


def test_v2_withholding_is_a_fallback_limitation_not_a_market_axis_state() -> None:
    payload = checkpoint_v2_input(perspective="system")
    payload["status_axes"]["market"]["status"] = "withheld"

    with pytest.raises(ModelValidationError, match="status_axes.market.status"):
        OperationCheckpointRecordV2.from_mapping(payload)
    assert list(_schema_v2_validator().iter_errors(payload))


def test_v2_schema_discriminator_is_required_and_exact() -> None:
    missing = checkpoint_v2_input()
    missing.pop("schema_version")
    with pytest.raises(
        ModelValidationError, match="missing required fields.*schema_version"
    ):
        OperationCheckpointRecordV2.from_mapping(missing)

    wrong = checkpoint_v2_input()
    wrong["schema_version"] = OPERATION_CHECKPOINT_SCHEMA_VERSION
    with pytest.raises(ModelValidationError, match="Unsupported operation checkpoint v2"):
        OperationCheckpointRecordV2.from_mapping(wrong)


def test_v2_unknown_provider_attempt_count_is_bounded_not_fabricated() -> None:
    payload = checkpoint_v2_input(perspective="system")
    fallback = payload["market_fallback"]
    receipt = deepcopy(fallback["fetch_receipts"][0])
    receipt.update(
        {
            "guard_audit_at": "2026-07-27T00:00:00Z",
            "started_at": "2026-07-27T00:00:01Z",
            "completed_at": "2026-07-27T00:00:03Z",
            "fetched_at": None,
            "system_observed_at": "2026-07-27T00:00:02Z",
            "response_status": "failed",
            "attempt_count": 0,
            "attempt_count_status": "unknown",
            "budget_charged_attempts": 3,
        }
    )
    _reidentify_v2_receipt(receipt)
    fallback.update(
        {
            "status": "failed",
            "limitation_code": "provider_attempt_count_unknown",
            "guard_audit_at": None,
            "request_count": 0,
            "request_count_status": "bounded_unknown",
            "unverified_attempt_upper_bound": 3,
            "fetch_receipt_refs": [receipt["receipt_id"]],
            "fetch_receipts": [receipt],
        }
    )
    record = OperationCheckpointRecordV2.from_mapping(payload).to_dict()
    assert record["market_fallback"]["request_count"] == 0
    assert record["market_fallback"]["request_count_status"] == "bounded_unknown"
    assert record["market_fallback"]["unverified_attempt_upper_bound"] == 3

    wrong_status = deepcopy(payload)
    wrong_status["market_fallback"]["request_count_status"] = "verified"
    with pytest.raises(ModelValidationError, match="request count status drift"):
        OperationCheckpointRecordV2.from_mapping(wrong_status)

    wrong_limitation = deepcopy(payload)
    wrong_limitation["market_fallback"]["limitation_code"] = None
    with pytest.raises(ModelValidationError, match="limitation/status drift"):
        OperationCheckpointRecordV2.from_mapping(wrong_limitation)

    wrong_order = deepcopy(payload)
    wrong_receipt = wrong_order["market_fallback"]["fetch_receipts"][0]
    wrong_receipt["system_observed_at"] = "2026-07-27T00:00:00Z"
    _reidentify_v2_receipt(wrong_receipt)
    wrong_order["market_fallback"]["fetch_receipt_refs"] = [
        wrong_receipt["receipt_id"]
    ]
    with pytest.raises(ValueError, match="cannot be earlier"):
        OperationCheckpointRecordV2.from_mapping(wrong_order)


def test_v2_receipt_time_order_and_normalized_parameter_keys_are_closed() -> None:
    payload = checkpoint_v2_input(perspective="system")
    receipt = payload["market_fallback"]["fetch_receipts"][0]
    receipt["started_at"] = "2026-07-26T23:59:59Z"
    _reidentify_v2_receipt(receipt)
    with pytest.raises(ModelValidationError, match="bind start/completion"):
        OperationCheckpointRecordV2.from_mapping(payload)

    duplicate = checkpoint_v2_input(perspective="system")
    duplicate_receipt = duplicate["market_fallback"]["fetch_receipts"][0]
    duplicate_receipt["redacted_parameters"] = {
        "ts_code": "588200.SH",
        " ts_code ": "588200.SH",
        "trade_date": "20260716",
    }
    _reidentify_v2_receipt(duplicate_receipt)
    with pytest.raises(ModelValidationError, match="duplicate normalized keys"):
        OperationCheckpointRecordV2.from_mapping(duplicate)


def test_v2_market_proof_manifest_and_source_less_state_are_closed() -> None:
    forged_unknown = checkpoint_v2_input()
    market = forged_unknown["status_axes"]["market"]
    market["information_time"].update(
        {
            "status": "unknown",
            "lower_bound": None,
            "upper_bound": None,
            "basis": "unknown",
        }
    )
    market["publicly_available_at"] = None
    market["publicly_available_basis"] = "unknown"
    with pytest.raises(ModelValidationError, match="policy-known user market proof"):
        OperationCheckpointRecordV2.from_mapping(forged_unknown)

    missing_manifest_ref = checkpoint_v2_input()
    market = missing_manifest_ref["status_axes"]["market"]
    manifest_ref = "market_evidence_manifest:" + market[
        "market_evidence_manifest_content_id"
    ]
    market["source_refs"].remove(manifest_ref)
    missing_manifest_ref["source_refs"].remove(manifest_ref)
    with pytest.raises(ModelValidationError, match="bind the frozen evidence manifest"):
        OperationCheckpointRecordV2.from_mapping(missing_manifest_ref)

    source_less = checkpoint_v2_input(perspective="system")
    market = source_less["status_axes"]["market"]
    manifest_ref = "market_evidence_manifest:" + market[
        "market_evidence_manifest_content_id"
    ]
    market.update(
        {
            "status": "missing",
            "temporal_role": "missing",
            "eligible_source_refs": [],
            "retrospective_source_refs": [],
            "unknown_source_refs": [],
            "effective_at": None,
            "publicly_available_at": None,
            "publicly_available_basis": "not_applicable",
            "fetched_at": None,
            "system_observed_at": None,
            "representative_source_id": None,
            "representative_source_content_id": None,
            "information_time": None,
            "version_provenance": None,
            "perspective_eligibility": None,
            "source_refs": [manifest_ref],
        }
    )
    source_less["source_refs"] = sorted(
        set(source_less["source_refs"]) | {manifest_ref}
    )
    assert OperationCheckpointRecordV2.from_mapping(source_less).to_dict()[
        "status_axes"
    ]["market"]["temporal_role"] == "missing"

    forged_time = deepcopy(source_less)
    forged_time["status_axes"]["market"]["effective_at"] = (
        "2026-07-16T07:00:00Z"
    )
    with pytest.raises(ModelValidationError, match="explicit missing projection"):
        OperationCheckpointRecordV2.from_mapping(forged_time)


def test_exact_v1_to_v2_marker_upgrade_is_atomic_no_ddl_and_replays_v1(
    tmp_path: Path,
) -> None:
    database = tmp_path / "upgrade-candidate.sqlite3"
    store = ReviewStore(database)
    store.initialize_reviewability_candidate()
    v1_receipt = store.save_operation_checkpoint(checkpoint_input())
    before_v1 = store.get_operation_checkpoint(v1_receipt["checkpoint_id"])
    with sqlite3.connect(database) as conn:
        before_ddl = conn.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "ORDER BY type, name"
        ).fetchall()

    upgraded = store.upgrade_reviewability_candidate_v2()
    assert upgraded["status"] == "UPGRADED"
    assert upgraded["reviewability_schema_version"] == REVIEWABILITY_SCHEMA_VERSION_V2
    assert upgraded["checkpoint_contract_version"] == (
        OPERATION_CHECKPOINT_SCHEMA_VERSION_V2
    )
    assert upgraded["market_policy_version"] == MARKET_FALLBACK_POLICY_VERSION_V2
    assert upgraded["public_information_policy_version"] == (
        PUBLIC_INFORMATION_POLICY_VERSION
    )
    assert upgraded["schema_manifest_sha256"] == (
        REVIEWABILITY_SCHEMA_MANIFEST_SHA256_V2
    )
    assert store.get_operation_checkpoint(v1_receipt["checkpoint_id"]) == before_v1
    with sqlite3.connect(database) as conn:
        after_ddl = conn.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "ORDER BY type, name"
        ).fetchall()
    assert after_ddl == before_ddl
    wal_path = Path(f"{database}-wal")
    assert not wal_path.exists() or wal_path.stat().st_size == 0
    with pytest.raises(ReviewStoreError, match="exact precondition"):
        store.upgrade_reviewability_candidate_v2()

    assert store.save_operation_checkpoint(before_v1)["status"] == "SKIPPED"
    new_v1 = checkpoint_input()
    new_v1["knowledge_cutoff"] = "2026-07-26T13:00:00Z"
    with pytest.raises(ReviewStoreError, match="must not create a new v1"):
        store.save_operation_checkpoint(new_v1)

    v2 = checkpoint_v2_input()
    assert store.save_operation_checkpoint(v2)["status"] == "INSERTED"
    tuple_collision = checkpoint_v2_input()
    tuple_collision["operation_anchor_ordering_key"][2] = "different"
    with pytest.raises(DataConflictError, match="new knowledge_cutoff"):
        store.save_operation_checkpoint(tuple_collision)


def test_v2_marker_upgrade_rolls_back_all_marker_changes_on_midflight_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ReviewStore(tmp_path / "upgrade-rollback.sqlite3")
    store.initialize_reviewability_candidate()
    original = ReviewStore._update_exact_marker
    calls = 0

    def fail_second_marker(
        conn: sqlite3.Connection, *, key: str, expected: str, replacement: str
    ) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ReviewStoreError("synthetic marker failure")
        original(conn, key=key, expected=expected, replacement=replacement)

    monkeypatch.setattr(
        ReviewStore, "_update_exact_marker", staticmethod(fail_second_marker)
    )
    with pytest.raises(ReviewStoreError, match="synthetic marker failure"):
        store.upgrade_reviewability_candidate_v2()
    status = store.status()
    assert status["reviewability_schema_version"] == REVIEWABILITY_SCHEMA_VERSION
    assert status["reviewability_schema_manifest_sha256"] == (
        REVIEWABILITY_SCHEMA_MANIFEST_SHA256
    )
    assert status["reviewability_public_information_policy_version"] is None


@pytest.mark.skipif(os.name != "nt", reason="Windows delete-sharing semantics")
def test_v2_marker_upgrade_no_delete_hold_blocks_real_path_replacement_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "upgrade-path-race.sqlite3"
    replacement = tmp_path / "upgrade-path-race-replacement.sqlite3"
    store = ReviewStore(database)
    store.initialize_reviewability_candidate()
    shutil.copy2(database, replacement)
    original_connect = review_store_module.sqlite3.connect
    replacement_attempted = False
    sharing_violation = False

    def racing_connect(*args: object, **kwargs: object) -> sqlite3.Connection:
        nonlocal replacement_attempted, sharing_violation
        target = str(args[0]) if args else str(kwargs.get("database") or "")
        if "mode=rw" in target and not replacement_attempted:
            replacement_attempted = True
            try:
                os.replace(replacement, database)
            except PermissionError:
                sharing_violation = True
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(review_store_module.sqlite3, "connect", racing_connect)
    upgraded = store.upgrade_reviewability_candidate_v2()
    assert upgraded["status"] == "UPGRADED"
    assert replacement_attempted is True
    assert sharing_violation is True
    assert replacement.exists()


def test_v2_marker_upgrade_fails_closed_when_rw_handle_is_substituted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "upgrade-swap-back.sqlite3"
    replacement = tmp_path / "upgrade-swap-back-replacement.sqlite3"
    store = ReviewStore(database)
    store.initialize_reviewability_candidate()
    shutil.copy2(database, replacement)
    original_connect = review_store_module.sqlite3.connect
    substituted = False

    def substituted_connect(*args: object, **kwargs: object) -> sqlite3.Connection:
        nonlocal substituted
        target = str(args[0]) if args else str(kwargs.get("database") or "")
        if "mode=rw" in target and not substituted:
            substituted = True
            replacement_uri = f"{replacement.resolve().as_uri()}?mode=rw"
            return original_connect(replacement_uri, uri=True)
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(
        review_store_module.sqlite3, "connect", substituted_connect
    )
    with pytest.raises(
        ReviewStoreError, match="SQLite main path drifted at after_rw_open"
    ):
        store.upgrade_reviewability_candidate_v2()
    assert substituted is True
    assert store.initialize_reviewability_candidate()[
        "reviewability_schema_version"
    ] == REVIEWABILITY_SCHEMA_VERSION
    assert ReviewStore(replacement).initialize_reviewability_candidate()[
        "reviewability_schema_version"
    ] == REVIEWABILITY_SCHEMA_VERSION


def test_v2_marker_upgrade_holds_existing_zero_wal_and_shm_through_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "upgrade-existing-aux.sqlite3"
    store = ReviewStore(database)
    store.initialize_reviewability_candidate()
    keeper = sqlite3.connect(database)
    try:
        keeper.execute("BEGIN IMMEDIATE")
        keeper.rollback()
        assert keeper.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0] == 0
        wal_path = Path(f"{database}-wal")
        shm_path = Path(f"{database}-shm")
        assert wal_path.is_file() and wal_path.stat().st_size == 0
        assert shm_path.is_file() and shm_path.stat().st_size == 32768

        upgraded = store.upgrade_reviewability_candidate_v2()
        assert upgraded["status"] == "UPGRADED"
        assert upgraded["reviewability_schema_version"] == (
            REVIEWABILITY_SCHEMA_VERSION_V2
        )
        assert wal_path.is_file() and wal_path.stat().st_size == 0
        assert shm_path.is_file() and shm_path.stat().st_size == 32768
    finally:
        keeper.close()

    if os.name == "nt":
        terminal_database = tmp_path / "upgrade-terminal-aux.sqlite3"
        terminal_store = ReviewStore(terminal_database)
        terminal_store.initialize_reviewability_candidate()
        _leave_detached_zero_wal_pair(terminal_database)
        terminal_wal = Path(f"{terminal_database}-wal")
        terminal_shm = Path(f"{terminal_database}-shm")
        original_connect = review_store_module.sqlite3.connect
        connection_targets: list[str] = []

        def recording_connect(
            *args: object, **kwargs: object
        ) -> sqlite3.Connection:
            target = str(args[0]) if args else str(kwargs.get("database") or "")
            connection_targets.append(target)
            return original_connect(*args, **kwargs)

        monkeypatch.setattr(
            review_store_module.sqlite3,
            "connect",
            recording_connect,
        )
        terminal_upgrade = terminal_store.upgrade_reviewability_candidate_v2()
        assert terminal_upgrade["status"] == "UPGRADED"
        assert not terminal_wal.exists()
        assert not terminal_shm.exists()
        read_only_targets = [
            target for target in connection_targets if "mode=ro" in target
        ]
        assert read_only_targets
        assert all("immutable=1" in target for target in read_only_targets)


@pytest.mark.parametrize(
    "auxiliary_shape",
    ["wal_only", "shm_only", "nonempty_wal", "wrong_shm_size"],
)
def test_marker_upgrade_rejects_invalid_entrance_auxiliary_pair(
    tmp_path: Path,
    auxiliary_shape: str,
) -> None:
    database = tmp_path / f"upgrade-invalid-{auxiliary_shape}.sqlite3"
    store = ReviewStore(database)
    store.initialize_reviewability_candidate()
    wal_path = Path(f"{database}-wal")
    shm_path = Path(f"{database}-shm")
    if auxiliary_shape == "wal_only":
        wal_path.write_bytes(b"")
    elif auxiliary_shape == "shm_only":
        shm_path.write_bytes(b"\0" * 32768)
    elif auxiliary_shape == "nonempty_wal":
        wal_path.write_bytes(b"drift")
        shm_path.write_bytes(b"\0" * 32768)
    else:
        wal_path.write_bytes(b"")
        shm_path.write_bytes(b"bad")

    with pytest.raises(ReviewStoreError, match="stable zero-WAL"):
        store.upgrade_reviewability_candidate_v2()


@pytest.mark.parametrize(
    ("checkpoint_result", "expected"),
    [
        ((0, 0, 0), True),
        ((0, 1, 1), False),
        ((0, 0, 1), False),
        ((1, 0, 0), False),
    ],
)
def test_upgrade_guard_checkpoint_result_requires_exact_zero_tuple(
    tmp_path: Path,
    checkpoint_result: tuple[int, int, int],
    expected: bool,
) -> None:
    guard, _, _, _ = _fake_upgrade_guard(tmp_path, str(checkpoint_result))
    connection = sqlite3.connect(":memory:")
    try:
        guard._writer_open = True
        guard._writer_conn = connection
        guard._marker_committed = True
        assert guard.record_checkpoint_result(
            checkpoint_result,
            stage="synthetic_checkpoint",
        ) is expected
    finally:
        connection.close()


@pytest.mark.parametrize(
    "checkpoint_result",
    [None, (0, 0), (0, 0, 0, 0)],
)
def test_upgrade_guard_rejects_incomplete_checkpoint_result_shape(
    tmp_path: Path,
    checkpoint_result: tuple[int, ...] | None,
) -> None:
    guard, _, _, _ = _fake_upgrade_guard(tmp_path, "incomplete-result")
    connection = sqlite3.connect(":memory:")
    try:
        guard._writer_open = True
        guard._writer_conn = connection
        guard._marker_committed = True
        with pytest.raises(ReviewStoreError, match="result is incomplete"):
            guard.record_checkpoint_result(
                checkpoint_result,
                stage="synthetic_checkpoint",
            )
    finally:
        connection.close()


def test_upgrade_guard_terminal_auxiliary_state_is_paired_and_one_way(
    tmp_path: Path,
) -> None:
    guard, wal_path, shm_path, _ = _fake_upgrade_guard(tmp_path, "terminal")
    connection = sqlite3.connect(":memory:")
    guard._writer_open = True
    guard._writer_conn = connection
    guard._marker_committed = True
    assert guard.record_checkpoint_result(
        (0, 0, 0), stage="terminal_checkpoint"
    ) is True
    wal_path.unlink()
    shm_path.unlink()
    connection.close()
    guard.assert_after_writer_close(connection, stage="terminal_close")
    guard.assert_current(stage="terminal_replay_one")
    guard.assert_current(stage="terminal_replay_two")
    wal_path.write_bytes(b"")
    with pytest.raises(ReviewStoreError, match="reappeared"):
        guard.assert_current(stage="terminal_reappeared")


def test_upgrade_guard_rejects_premature_single_and_drifted_terminal_absence(
    tmp_path: Path,
) -> None:
    early, early_wal, early_shm, _ = _fake_upgrade_guard(tmp_path, "early")
    early_connection = sqlite3.connect(":memory:")
    early._writer_open = True
    early._writer_conn = early_connection
    early_wal.unlink()
    early_shm.unlink()
    early_connection.close()
    with pytest.raises(ReviewStoreError, match="before marker commit"):
        early.assert_after_writer_close(early_connection, stage="early_close")

    incomplete, incomplete_wal, incomplete_shm, _ = _fake_upgrade_guard(
        tmp_path, "incomplete"
    )
    incomplete_connection = sqlite3.connect(":memory:")
    incomplete._writer_open = True
    incomplete._writer_conn = incomplete_connection
    incomplete._marker_committed = True
    assert incomplete.record_checkpoint_result(
        (0, 1, 1), stage="incomplete_checkpoint"
    ) is False
    incomplete_wal.unlink()
    incomplete_shm.unlink()
    incomplete_connection.close()
    with pytest.raises(ReviewStoreError, match=r"exact \(0, 0, 0\)"):
        incomplete.assert_after_writer_close(
            incomplete_connection,
            stage="incomplete_close",
        )

    for missing_label in ("wal", "shm"):
        single, single_wal, single_shm, _ = _fake_upgrade_guard(
            tmp_path, f"single-{missing_label}"
        )
        single_connection = sqlite3.connect(":memory:")
        single._writer_open = True
        single._writer_conn = single_connection
        single._marker_committed = True
        assert single.record_checkpoint_result(
            (0, 0, 0), stage="single_checkpoint"
        ) is True
        (single_wal if missing_label == "wal" else single_shm).unlink()
        single_connection.close()
        with pytest.raises(ReviewStoreError, match="one-sided"):
            single.assert_after_writer_close(
                single_connection,
                stage=f"single_{missing_label}_close",
            )

    binding, _, _, binding_files = _fake_upgrade_guard(tmp_path, "binding")
    binding_connection = sqlite3.connect(":memory:")
    binding._writer_open = True
    binding._writer_conn = binding_connection
    binding._marker_committed = True
    assert binding.record_checkpoint_result(
        (0, 0, 0), stage="binding_checkpoint"
    ) is True
    binding_files["wal"].fail_binding = True
    binding_connection.close()
    with pytest.raises(ReviewStoreError, match="pathname identity drift"):
        binding.assert_after_writer_close(
            binding_connection,
            stage="binding_close",
        )

    held, held_wal, held_shm, held_files = _fake_upgrade_guard(
        tmp_path, "held-size"
    )
    held_connection = sqlite3.connect(":memory:")
    held._writer_open = True
    held._writer_conn = held_connection
    held._marker_committed = True
    assert held.record_checkpoint_result(
        (0, 0, 0), stage="held_checkpoint"
    ) is True
    held_files["wal"].fail_size = True
    held_wal.unlink()
    held_shm.unlink()
    held_connection.close()
    with pytest.raises(ReviewStoreError, match="held size drift"):
        held.assert_after_writer_close(held_connection, stage="held_close")


def test_v2_marker_upgrade_rejects_pre_open_metadata_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "upgrade-metadata-race.sqlite3"
    store = ReviewStore(database)
    store.initialize_reviewability_candidate()
    original_assert = ReviewStore._assert_reviewability_upgrade_path_state
    touched = False

    def touch_after_pre_open_check(path: Path, **kwargs: object) -> None:
        nonlocal touched
        original_assert(path, **kwargs)
        if kwargs.get("stage") == "before_rw_open" and not touched:
            stat_result = path.stat()
            os.utime(
                path,
                ns=(
                    stat_result.st_atime_ns,
                    stat_result.st_mtime_ns + 10_000_000,
                ),
            )
            touched = True

    monkeypatch.setattr(
        ReviewStore,
        "_assert_reviewability_upgrade_path_state",
        staticmethod(touch_after_pre_open_check),
    )
    with pytest.raises(ReviewStoreError, match="main identity changed at after_rw_open"):
        store.upgrade_reviewability_candidate_v2()
    assert touched is True
