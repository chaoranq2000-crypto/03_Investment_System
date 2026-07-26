from __future__ import annotations

import json
import os
import sqlite3
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from src.investment_review.models import (
    MARKET_FALLBACK_POLICY_VERSION,
    MARKET_PROVIDER_ALLOWLIST,
    MARKET_PROVIDER_ALLOWLIST_SHA256,
    MARKET_PROVIDER_ALLOWLIST_VERSION,
    MARKET_REQUEST_FINGERPRINT_VERSION,
    ModelValidationError,
    OPERATION_CHECKPOINT_SCHEMA_VERSION,
    OperationCheckpointRecord,
    market_request_fingerprint,
)
from src.investment_review.store import (
    DataConflictError,
    REVIEWABILITY_SCHEMA_MANIFEST_SHA256,
    REVIEWABILITY_SCHEMA_VERSION,
    ReviewStore,
    ReviewStoreError,
)


SCHEMA_PATH = (
    Path(__file__).parents[1]
    / "docs"
    / "contracts"
    / "INVESTMENT_REVIEW_OPERATION_CHECKPOINT.schema.json"
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
