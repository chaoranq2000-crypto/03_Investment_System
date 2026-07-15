"""Reviewed-evidence intake bridge for R5 Bundle 15R.

The module consumes already-reviewed official issuer evidence. It does not fetch,
extract, review, or promote evidence. It builds a deterministic, conflict-aware
candidate pack for the existing Bundle 14R trigger evaluator and can emit a proposed
workflow-state copy without mutating canonical state.
"""

from __future__ import annotations

import csv
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

import yaml


ALLOWED_SOURCE_CLASSES = {
    "issuer_periodic_report",
    "issuer_announcement",
    "issuer_ir_record",
}
REVIEWED_STATUSES = {"reviewed", "accepted"}
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
AUTO_FIELDS = {"source_evidence_id", "locator"}


class IntakeContractError(ValueError):
    """Raised when a Bundle 15R registry or reviewed input is malformed."""


def _load_yaml(path: str | Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise IntakeContractError(f"YAML root must be a mapping: {path}")
    return payload


def _dump_yaml(path: str | Path, payload: Mapping[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(dict(payload), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def canonical_json(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_sha256(payload: Any) -> str:
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, tuple, dict)) and not value:
        return True
    return False


def validate_registry(registry: Mapping[str, Any]) -> None:
    required = {
        "workflow_id",
        "source_bundle13r_generation_id",
        "period_anchor_ref",
        "triggers",
    }
    missing = sorted(required - set(registry))
    if missing:
        raise IntakeContractError(f"registry missing fields: {missing}")
    triggers = registry.get("triggers")
    if not isinstance(triggers, list) or not triggers:
        raise IntakeContractError("registry.triggers must be a non-empty list")
    trigger_ids: set[str] = set()
    metric_keys: set[str] = set()
    for index, trigger in enumerate(triggers):
        if not isinstance(trigger, Mapping):
            raise IntakeContractError(f"trigger[{index}] must be a mapping")
        required_trigger = {
            "trigger_id",
            "metric_key",
            "business_scope",
            "allowed_source_classes",
            "required_fields",
            "status",
        }
        missing_trigger = sorted(required_trigger - set(trigger))
        if missing_trigger:
            raise IntakeContractError(
                f"trigger[{index}] missing fields: {missing_trigger}"
            )
        trigger_id = str(trigger["trigger_id"])
        metric_key = str(trigger["metric_key"])
        if trigger_id in trigger_ids:
            raise IntakeContractError(f"duplicate trigger_id: {trigger_id}")
        if metric_key in metric_keys:
            raise IntakeContractError(f"duplicate metric_key: {metric_key}")
        trigger_ids.add(trigger_id)
        metric_keys.add(metric_key)
        allowed = set(trigger.get("allowed_source_classes") or [])
        if not allowed or not allowed.issubset(ALLOWED_SOURCE_CLASSES):
            raise IntakeContractError(
                f"trigger {trigger_id} has unsupported source classes: {sorted(allowed)}"
            )
        required_fields = trigger.get("required_fields")
        if not isinstance(required_fields, list) or not required_fields:
            raise IntakeContractError(
                f"trigger {trigger_id} required_fields must be non-empty"
            )


def validate_reviewed_input(
    reviewed_input: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> None:
    required = {
        "schema_version",
        "workflow_id",
        "as_of",
        "period_anchor_ref",
        "records",
    }
    missing = sorted(required - set(reviewed_input))
    if missing:
        raise IntakeContractError(f"reviewed input missing fields: {missing}")
    if reviewed_input.get("workflow_id") != registry.get("workflow_id"):
        raise IntakeContractError("workflow_id mismatch")
    if reviewed_input.get("period_anchor_ref") != registry.get("period_anchor_ref"):
        raise IntakeContractError("period_anchor_ref mismatch")
    records = reviewed_input.get("records")
    if not isinstance(records, list):
        raise IntakeContractError("records must be a list")


def _record_reasons(
    record: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> list[str]:
    reasons: list[str] = []
    required_record = {
        "evidence_id",
        "source_class",
        "official_issuer_source",
        "review_status",
        "document_date",
        "period_compatible",
        "period_anchor_ref",
        "source_hash",
        "locator",
        "metrics",
    }
    missing = sorted(required_record - set(record))
    if missing:
        reasons.append("missing_record_fields:" + ",".join(missing))
        return reasons
    if record.get("source_class") not in ALLOWED_SOURCE_CLASSES:
        reasons.append("source_class_not_allowed")
    if record.get("official_issuer_source") is not True:
        reasons.append("not_official_issuer_source")
    if record.get("review_status") not in REVIEWED_STATUSES:
        reasons.append("review_status_not_eligible")
    if record.get("period_compatible") is not True:
        reasons.append("period_not_compatible")
    if record.get("period_anchor_ref") != registry.get("period_anchor_ref"):
        reasons.append("period_anchor_mismatch")
    source_hash = str(record.get("source_hash") or "")
    if not SHA256_PATTERN.fullmatch(source_hash):
        reasons.append("invalid_source_hash")
    if _is_missing(record.get("locator")):
        reasons.append("missing_locator")
    if not isinstance(record.get("metrics"), list):
        reasons.append("metrics_not_list")
    return reasons


def _metric_reasons(
    *,
    record: Mapping[str, Any],
    metric: Mapping[str, Any],
    trigger: Mapping[str, Any] | None,
) -> list[str]:
    reasons: list[str] = []
    if trigger is None:
        return ["metric_key_not_in_bundle14r_registry"]
    if record.get("source_class") not in set(trigger.get("allowed_source_classes") or []):
        reasons.append("source_class_not_allowed_for_trigger")
    payload = metric.get("payload")
    if not isinstance(payload, Mapping):
        return reasons + ["payload_not_mapping"]
    required_fields = [str(item) for item in trigger.get("required_fields") or []]
    for field in required_fields:
        if field in AUTO_FIELDS:
            continue
        if field not in payload or _is_missing(payload.get(field)):
            reasons.append(f"missing_required_value:{field}")
    expected_scope = str(trigger.get("business_scope") or "").strip()
    supplied_scope = str(payload.get("business_scope") or "").strip()
    if supplied_scope and expected_scope and supplied_scope != expected_scope:
        reasons.append("business_scope_mismatch")
    return reasons


def _candidate_value_signature(
    candidate: Mapping[str, Any],
    trigger: Mapping[str, Any],
) -> str:
    required_payload_fields = [
        str(field)
        for field in trigger.get("required_fields") or []
        if field not in AUTO_FIELDS
    ]
    value_payload = {
        field: candidate.get(field)
        for field in required_payload_fields
    }
    return canonical_sha256(value_payload)


def _candidate_group_key(
    candidate: Mapping[str, Any],
    trigger: Mapping[str, Any],
) -> tuple[str, str, str]:
    period = str(candidate.get("period") or "")
    scope = str(
        candidate.get("business_scope")
        or trigger.get("business_scope")
        or ""
    )
    return (str(candidate["metric_keys"][0]), period, scope)


def build_intake(
    registry: Mapping[str, Any],
    reviewed_input: Mapping[str, Any],
) -> dict[str, Any]:
    validate_registry(registry)
    validate_reviewed_input(reviewed_input, registry)

    trigger_by_metric = {
        str(trigger["metric_key"]): dict(trigger)
        for trigger in registry["triggers"]
    }
    rejections: list[dict[str, Any]] = []
    provisional: list[dict[str, Any]] = []
    input_metric_count = 0

    for record_index, raw_record in enumerate(reviewed_input.get("records") or []):
        if not isinstance(raw_record, Mapping):
            rejections.append(
                {
                    "record_index": record_index,
                    "evidence_id": "",
                    "metric_key": "",
                    "reason": "record_not_mapping",
                }
            )
            continue
        record = dict(raw_record)
        record_reasons = _record_reasons(record, registry)
        metrics = record.get("metrics") if isinstance(record.get("metrics"), list) else []
        if record_reasons:
            metric_keys = [
                str(metric.get("metric_key") or "")
                for metric in metrics
                if isinstance(metric, Mapping)
            ] or [""]
            for metric_key in metric_keys:
                for reason in record_reasons:
                    rejections.append(
                        {
                            "record_index": record_index,
                            "evidence_id": str(record.get("evidence_id") or ""),
                            "metric_key": metric_key,
                            "reason": reason,
                        }
                    )
            continue

        for metric_index, raw_metric in enumerate(metrics):
            input_metric_count += 1
            if not isinstance(raw_metric, Mapping):
                rejections.append(
                    {
                        "record_index": record_index,
                        "evidence_id": str(record.get("evidence_id") or ""),
                        "metric_key": "",
                        "reason": f"metric_not_mapping:{metric_index}",
                    }
                )
                continue
            metric = dict(raw_metric)
            metric_key = str(metric.get("metric_key") or "")
            trigger = trigger_by_metric.get(metric_key)
            reasons = _metric_reasons(
                record=record,
                metric=metric,
                trigger=trigger,
            )
            if reasons:
                for reason in reasons:
                    rejections.append(
                        {
                            "record_index": record_index,
                            "evidence_id": str(record.get("evidence_id") or ""),
                            "metric_key": metric_key,
                            "reason": reason,
                        }
                    )
                continue

            assert trigger is not None
            payload = dict(metric["payload"])
            available_fields = sorted(
                set(str(item) for item in metric.get("available_fields") or [])
                | set(payload)
                | AUTO_FIELDS
            )
            candidate: dict[str, Any] = {
                "evidence_id": str(record["evidence_id"]),
                "source_class": str(record["source_class"]),
                "official_issuer_source": True,
                "review_status": str(record["review_status"]),
                "document_date": str(record["document_date"]),
                "period_compatible": True,
                "period_anchor_ref": str(record["period_anchor_ref"]),
                "metric_keys": [metric_key],
                "available_fields": available_fields,
                "source_hash": str(record["source_hash"]).lower(),
                "locator": str(record["locator"]),
                "source_evidence_id": str(record["evidence_id"]),
                "bundle14r_trigger_id": str(trigger["trigger_id"]),
            }
            candidate.update(payload)
            provisional.append(candidate)

    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for candidate in provisional:
        trigger = trigger_by_metric[candidate["metric_keys"][0]]
        grouped.setdefault(_candidate_group_key(candidate, trigger), []).append(candidate)

    candidates: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    duplicate_suppressed_count = 0

    for group_key in sorted(grouped):
        group = sorted(
            grouped[group_key],
            key=lambda item: (
                item["evidence_id"],
                item["source_hash"],
                item["locator"],
            ),
        )
        trigger = trigger_by_metric[group[0]["metric_keys"][0]]
        signatures: dict[str, list[dict[str, Any]]] = {}
        for item in group:
            signatures.setdefault(
                _candidate_value_signature(item, trigger),
                [],
            ).append(item)

        if len(signatures) > 1:
            conflicts.append(
                {
                    "metric_key": group_key[0],
                    "period": group_key[1],
                    "business_scope": group_key[2],
                    "bundle14r_trigger_id": trigger["trigger_id"],
                    "distinct_value_count": len(signatures),
                    "evidence_ids": sorted(item["evidence_id"] for item in group),
                    "value_signatures": sorted(signatures),
                    "resolution": "explicit_reviewed_reconciliation_required",
                }
            )
            for item in group:
                rejections.append(
                    {
                        "record_index": "",
                        "evidence_id": item["evidence_id"],
                        "metric_key": group_key[0],
                        "reason": "conflicting_reviewed_values",
                    }
                )
            continue

        candidates.append(group[0])
        for duplicate in group[1:]:
            duplicate_suppressed_count += 1
            rejections.append(
                {
                    "record_index": "",
                    "evidence_id": duplicate["evidence_id"],
                    "metric_key": group_key[0],
                    "reason": "duplicate_same_value_suppressed",
                }
            )

    candidates.sort(
        key=lambda item: (
            item["metric_keys"][0],
            str(item.get("period") or ""),
            item["evidence_id"],
        )
    )
    represented_triggers = sorted(
        {item["bundle14r_trigger_id"] for item in candidates}
    )
    trigger_count = len(registry["triggers"])
    if not candidates:
        status = "waiting_for_reviewed_same-period_official_operating_evidence"
        next_action = "wait_for_reviewed_official_evidence"
    elif len(represented_triggers) == trigger_count:
        status = "all_trigger_candidates_ready_for_bundle14r_evaluation"
        next_action = "run_existing_bundle14r_trigger_evaluator"
    else:
        status = "partial_reviewed_candidates_ready"
        next_action = "run_existing_bundle14r_trigger_evaluator_for_selective_backflow"

    candidate_pack = {
        "schema_version": 1,
        "workflow_id": registry["workflow_id"],
        "as_of": reviewed_input["as_of"],
        "status": status,
        "source_bundle14r_generation_id": registry.get(
            "source_bundle13r_generation_id"
        ),
        "period_anchor_ref": registry["period_anchor_ref"],
        "candidates": candidates,
        "notes": [
            "Bundle 15R candidates remain subject to the existing Bundle 14R evaluator.",
            "Candidate construction does not promote a claim or authorize downstream regeneration.",
            "Conflicting values are excluded; equal-value duplicates are suppressed deterministically.",
        ],
    }

    summary = {
        "schema_version": 1,
        "workflow_id": registry["workflow_id"],
        "decision": status,
        "input_record_count": len(reviewed_input.get("records") or []),
        "input_metric_count": input_metric_count,
        "provisional_candidate_count": len(provisional),
        "eligible_candidate_count": len(candidates),
        "represented_trigger_count": len(represented_triggers),
        "bundle14r_trigger_count": trigger_count,
        "rejection_count": len(rejections),
        "conflict_group_count": len(conflicts),
        "duplicate_suppressed_count": duplicate_suppressed_count,
        "next_action": next_action,
        "bundle12r_rerun_allowed": False,
        "valuation_refresh_allowed": False,
        "model_regeneration_allowed": False,
        "reader_regeneration_allowed": False,
        "human_review_status": "pending",
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }

    conflict_ledger = {
        "schema_version": 1,
        "workflow_id": registry["workflow_id"],
        "conflict_group_count": len(conflicts),
        "conflicts": conflicts,
        "guardrail": "conflicting_reviewed_values_fail_closed",
    }
    return {
        "candidate_pack": candidate_pack,
        "rejections": sorted(
            rejections,
            key=lambda item: (
                str(item.get("metric_key") or ""),
                str(item.get("evidence_id") or ""),
                str(item.get("reason") or ""),
            ),
        ),
        "conflict_ledger": conflict_ledger,
        "summary": summary,
    }


def build_proposed_workflow_state(
    workflow_state: Mapping[str, Any],
    summary: Mapping[str, Any],
    generation_id: str,
) -> dict[str, Any]:
    updated = deepcopy(dict(workflow_state))
    updated["status"] = "in_progress"
    updated["current_stage"] = "R5_bundle15r_reviewed_evidence_intake"
    updated["next_stage"] = (
        "R5_bundle14r_evidence_trigger_backflow"
        if summary.get("eligible_candidate_count", 0)
        else "R5_bundle15r_reviewed_evidence_intake"
    )
    updated["active_skill"] = "evidence-ingest"
    updated["required_next_skill"] = "evidence-ingest"
    updated["bundle15r_reviewed_evidence_intake"] = {
        "status": summary.get("decision"),
        "generation_id": generation_id,
        "eligible_candidate_count": summary.get("eligible_candidate_count"),
        "represented_trigger_count": summary.get("represented_trigger_count"),
        "conflict_group_count": summary.get("conflict_group_count"),
        "next_action": summary.get("next_action"),
        "bundle12r_rerun_allowed": False,
        "valuation_refresh_allowed": False,
        "model_regeneration_allowed": False,
        "reader_regeneration_allowed": False,
        "human_review_status": "pending",
        "sample_quality_allowed": False,
        "p2_allowed": False,
        "canonical_state_overwritten": False,
    }
    return updated


def _write_rejections(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["record_index", "evidence_id", "metric_key", "reason"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_intake_outputs(
    *,
    registry_path: str | Path,
    reviewed_input_path: str | Path,
    output_dir: str | Path,
    workflow_state_path: str | Path | None = None,
) -> dict[str, Any]:
    registry_path = Path(registry_path)
    reviewed_input_path = Path(reviewed_input_path)
    registry = _load_yaml(registry_path)
    reviewed_input = _load_yaml(reviewed_input_path)
    built = build_intake(registry, reviewed_input)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    candidate_path = output / "R5_bundle15r_candidate_pack.yaml"
    rejection_path = output / "R5_bundle15r_rejection_ledger.csv"
    conflict_path = output / "R5_bundle15r_conflict_ledger.yaml"
    summary_path = output / "R5_bundle15r_intake_summary.yaml"
    lock_path = output / "R5_bundle15r_generation_lock.yaml"

    _dump_yaml(candidate_path, built["candidate_pack"])
    _write_rejections(rejection_path, built["rejections"])
    _dump_yaml(conflict_path, built["conflict_ledger"])
    _dump_yaml(summary_path, built["summary"])

    lock_core = {
        "schema_version": 1,
        "workflow_id": registry["workflow_id"],
        "registry_path": str(registry_path),
        "registry_sha256": file_sha256(registry_path),
        "reviewed_input_path": str(reviewed_input_path),
        "reviewed_input_sha256": file_sha256(reviewed_input_path),
        "artifacts": {
            candidate_path.name: file_sha256(candidate_path),
            rejection_path.name: file_sha256(rejection_path),
            conflict_path.name: file_sha256(conflict_path),
            summary_path.name: file_sha256(summary_path),
        },
        "fixed_boundaries": {
            "bundle12r_rerun_allowed": False,
            "valuation_refresh_allowed": False,
            "model_regeneration_allowed": False,
            "reader_regeneration_allowed": False,
            "human_review_status": "pending",
            "sample_quality_allowed": False,
            "p2_allowed": False,
        },
    }
    generation_id = "reviewed_evidence_intake_gen_r5_bundle15r_" + canonical_sha256(
        lock_core
    )[:16]
    generation_lock = dict(lock_core)
    generation_lock["generation_id"] = generation_id
    _dump_yaml(lock_path, generation_lock)

    paths: dict[str, Path] = {
        "candidate_pack": candidate_path,
        "rejection_ledger": rejection_path,
        "conflict_ledger": conflict_path,
        "summary": summary_path,
        "generation_lock": lock_path,
    }

    if workflow_state_path is not None:
        workflow_state = _load_yaml(workflow_state_path)
        proposed = build_proposed_workflow_state(
            workflow_state,
            built["summary"],
            generation_id,
        )
        proposed_path = output / "workflow_state.bundle15r.proposed.yaml"
        _dump_yaml(proposed_path, proposed)
        paths["workflow_state_copy"] = proposed_path

    return {
        "summary": built["summary"],
        "generation_lock": generation_lock,
        "paths": paths,
    }
