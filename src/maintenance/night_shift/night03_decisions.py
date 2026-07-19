"""Fail-closed external decision intake for Night03."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

import yaml

from .night03 import (
    EXPECTED_QUEUE_SHA256,
    MISSION_ID,
    OUTPUT_ROOT,
    PACKAGE_ROOT,
    SOURCE_QUEUE,
    Night03Error,
    authoritative_queue,
    sha256_file,
    stable_payload,
    write_json,
    write_yaml,
)
from .queue import atomic_write
from .receipts import canonical_json_bytes, sha256_bytes


DECISION_SCHEMA_VERSION = "r5_night03_external_decision_manifest_v1"
DECISION_KINDS = {
    "evidence_acceptance": {
        "work_type": "evidence_required",
        "authority": "evidence_reviewer",
    },
    "analysis_acceptance": {
        "work_type": "analysis_required",
        "authority": "research_reviewer",
    },
    "human_exact_hash": {
        "work_type": "human_gate",
        "authority": "human_gate_reviewer",
    },
    "pointer_contract_approval": {
        "work_type": "engineering_local",
        "authority": "engineering_contract_reviewer",
    },
}
FORBIDDEN_MACHINE_REVIEWERS = re.compile(
    r"(?:^|[\s_.-])(codex|agent|automation|machine|night[_ -]?shift|bot)(?:$|[\s_.-])",
    re.IGNORECASE,
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def decision_manifest_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": DECISION_SCHEMA_VERSION,
        "type": "object",
        "required": [
            "schema_version",
            "source_queue_path",
            "source_queue_sha256",
            "created_by",
            "created_at",
            "decisions",
            "machine_must_not_populate_reviewer_fields",
        ],
        "properties": {
            "schema_version": {"const": DECISION_SCHEMA_VERSION},
            "source_queue_path": {"const": SOURCE_QUEUE.as_posix()},
            "source_queue_sha256": {"const": EXPECTED_QUEUE_SHA256},
            "created_by": {"type": "string", "minLength": 1},
            "created_at": {"type": "string", "format": "date-time"},
            "machine_must_not_populate_reviewer_fields": {"const": True},
            "decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "occurrence_id",
                        "decision_kind",
                        "decision",
                        "candidate_artifact_path",
                        "candidate_artifact_sha256",
                        "review_packet_path",
                        "review_packet_sha256",
                        "reviewer",
                        "reviewer_authority",
                        "reviewed_at",
                        "notes",
                    ],
                    "properties": {
                        "occurrence_id": {"type": "string", "minLength": 1},
                        "decision_kind": {"enum": sorted(DECISION_KINDS)},
                        "decision": {"enum": ["approved", "rejected"]},
                        "candidate_artifact_path": {"type": "string", "minLength": 1},
                        "candidate_artifact_sha256": {
                            "type": "string",
                            "pattern": "^[0-9a-f]{64}$",
                        },
                        "review_packet_path": {"type": "string", "minLength": 1},
                        "review_packet_sha256": {
                            "type": "string",
                            "pattern": "^[0-9a-f]{64}$",
                        },
                        "reviewer": {"type": "string", "minLength": 1},
                        "reviewer_authority": {"type": "string", "minLength": 1},
                        "reviewed_at": {"type": "string", "format": "date-time"},
                        "notes": {"type": "array", "items": {"type": "string"}},
                    },
                    "additionalProperties": False,
                },
            },
        },
        "additionalProperties": False,
    }


def authority_matrix() -> dict[str, Any]:
    return {
        "schema_version": "r5_night03_authority_matrix_v1",
        "machine_populated_reviewer_allowed": False,
        "future_review_timestamp_allowed": False,
        "decision_authorities": {
            kind: {
                "required_work_type": rule["work_type"],
                "required_reviewer_authority": rule["authority"],
                "approved_is_resolution": False,
            }
            for kind, rule in DECISION_KINDS.items()
        },
    }


def adapter_contracts() -> dict[str, dict[str, Any]]:
    common = {
        "exact_candidate_hash_required": True,
        "exact_review_packet_hash_required": True,
        "source_queue_hash_required": EXPECTED_QUEUE_SHA256,
        "decision_alone_resolves_occurrence": False,
    }
    return {
        "evidence": {
            "schema_version": "r5_night03_evidence_adapter_contract_v1",
            **common,
            "required_fields": [
                "evidence_id",
                "source_hash",
                "source_class",
                "claim_boundary",
                "counter_evidence",
            ],
            "allowed_source_classes": [
                "official_disclosure",
                "official_report",
                "regulatory_source",
                "reviewed_dataset",
            ],
        },
        "analysis": {
            "schema_version": "r5_night03_analysis_adapter_contract_v1",
            **common,
            "required_fields": [
                "conclusion",
                "evidence_ids",
                "counter_evidence",
                "confidence",
                "model_link",
            ],
            "allowed_confidence": ["low", "medium", "high"],
        },
        "human": {
            "schema_version": "r5_night03_human_adapter_contract_v1",
            **common,
            "required_fields": [
                "gate_id",
                "candidate_artifact_sha256",
                "generation_lock_sha256",
            ],
            "rerender_invalidates_review": True,
        },
        "pointer": {
            "schema_version": "r5_night03_pointer_adapter_contract_v1",
            **common,
            "required_fields": [
                "allowed_paths",
                "acceptance_commands",
                "scope_ceiling",
                "proposal_sha256",
                "review_sha",
            ],
            "proposed_is_executable": False,
            "max_tasks_per_wave": 2,
        },
    }


def resolution_policy() -> dict[str, Any]:
    return {
        "schema_version": "r5_night03_resolution_policy_v1",
        "candidate_ready_is_resolved": False,
        "packet_generated_is_resolved": False,
        "no_input_is_resolved": False,
        "approved_decision_is_resolved": False,
        "required_for_resolution": [
            "validated_approved_decision",
            "independent_execution_or_acceptance_receipt",
            "acceptance_passed",
            "source_queue_lineage_match",
            "candidate_and_review_hash_match",
        ],
        "program_goal_auto_close_allowed": False,
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }


def _normalise_relative_path(value: Any, *, field: str) -> str:
    text = str(value or "").replace("\\", "/").strip()
    pure = PurePosixPath(text)
    if not text or pure.is_absolute() or ".." in pure.parts or re.match(r"^[A-Za-z]:", text):
        raise Night03Error(f"{field}: must be a repository-relative path")
    return text


def _bound_file(repo_root: Path, path_value: Any, hash_value: Any, *, field: str) -> Path:
    relative = _normalise_relative_path(path_value, field=f"{field}_path")
    expected = str(hash_value or "").casefold()
    if not SHA256_RE.fullmatch(expected):
        raise Night03Error(f"{field}_sha256: must be 64 lowercase hexadecimal characters")
    path = (repo_root.resolve() / relative).resolve()
    try:
        path.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise Night03Error(f"{field}_path escapes repository") from exc
    if not path.is_file() or path.is_symlink():
        raise Night03Error(f"{field}_path missing or not a regular file: {relative}")
    actual = sha256_file(path)
    if actual != expected:
        raise Night03Error(f"{field} exact-hash mismatch: {actual} != {expected}")
    return path


def _load_structured(path: Path) -> dict[str, Any]:
    if path.suffix.casefold() == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
    else:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Night03Error(f"review packet must be a mapping: {path}")
    return value


def _nonempty_text(packet: Mapping[str, Any], field: str) -> str:
    text = str(packet.get(field) or "").strip()
    if not text:
        raise Night03Error(f"review_packet.{field}: must not be empty")
    return text


def _text_list(packet: Mapping[str, Any], field: str, *, allow_empty: bool = False) -> list[str]:
    value = packet.get(field)
    if not isinstance(value, list) or (not value and not allow_empty):
        raise Night03Error(f"review_packet.{field}: must be a list")
    result = [str(item).strip() for item in value]
    if any(not item for item in result):
        raise Night03Error(f"review_packet.{field}: entries must not be empty")
    return result


def validate_evidence_packet(packet: Mapping[str, Any]) -> None:
    _nonempty_text(packet, "evidence_id")
    source_hash = _nonempty_text(packet, "source_hash").casefold()
    if not SHA256_RE.fullmatch(source_hash):
        raise Night03Error("review_packet.source_hash: invalid SHA-256")
    source_class = _nonempty_text(packet, "source_class")
    allowed = set(adapter_contracts()["evidence"]["allowed_source_classes"])
    if source_class not in allowed:
        raise Night03Error(f"review_packet.source_class: unsupported {source_class!r}")
    _nonempty_text(packet, "claim_boundary")
    _text_list(packet, "counter_evidence", allow_empty=True)


def validate_analysis_packet(packet: Mapping[str, Any]) -> None:
    _nonempty_text(packet, "conclusion")
    _text_list(packet, "evidence_ids")
    _text_list(packet, "counter_evidence", allow_empty=True)
    confidence = _nonempty_text(packet, "confidence")
    if confidence not in {"low", "medium", "high"}:
        raise Night03Error("review_packet.confidence: must be low, medium, or high")
    _nonempty_text(packet, "model_link")


def validate_human_packet(
    packet: Mapping[str, Any], *, candidate_artifact_sha256: str
) -> None:
    _nonempty_text(packet, "gate_id")
    bound = _nonempty_text(packet, "candidate_artifact_sha256").casefold()
    if bound != candidate_artifact_sha256:
        raise Night03Error("human packet candidate hash does not match manifest")
    generation = _nonempty_text(packet, "generation_lock_sha256").casefold()
    if not SHA256_RE.fullmatch(generation):
        raise Night03Error("review_packet.generation_lock_sha256: invalid SHA-256")


def pointer_proposal_hash(packet: Mapping[str, Any]) -> str:
    projection = {
        key: value
        for key, value in packet.items()
        if key not in {"proposal_sha256", "review_sha", "review_state"}
    }
    return sha256_bytes(canonical_json_bytes(projection))


def validate_pointer_packets(
    candidate: Mapping[str, Any], review: Mapping[str, Any]
) -> None:
    candidate_paths = _text_list(candidate, "allowed_paths")
    candidate_commands = _text_list(candidate, "acceptance_commands")
    ceiling = candidate.get("scope_ceiling")
    if not isinstance(ceiling, dict):
        raise Night03Error("pointer candidate scope_ceiling must be a mapping")
    ceiling_paths = _text_list(ceiling, "allowed_paths")
    if not set(candidate_paths).issubset(set(ceiling_paths)):
        raise Night03Error("pointer candidate paths exceed scope ceiling")
    proposal_sha = str(candidate.get("proposal_sha256") or "").casefold()
    calculated = pointer_proposal_hash(candidate)
    if proposal_sha != calculated:
        raise Night03Error("pointer candidate proposal_sha256 mismatch")
    if review.get("review_state") != "approved":
        raise Night03Error("pointer review packet is not approved")
    if review.get("allowed_paths") != candidate_paths:
        raise Night03Error("pointer approved paths do not exactly match proposal")
    if review.get("acceptance_commands") != candidate_commands:
        raise Night03Error("pointer approved commands do not exactly match proposal")
    if review.get("scope_ceiling") != ceiling:
        raise Night03Error("pointer approved scope ceiling does not match proposal")
    if str(review.get("proposal_sha256") or "").casefold() != proposal_sha:
        raise Night03Error("pointer review packet proposal hash mismatch")
    if str(review.get("review_sha") or "").casefold() != pointer_proposal_hash(review):
        raise Night03Error("pointer review_sha mismatch")


def _review_time(value: Any, *, now: datetime) -> str:
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Night03Error("reviewed_at: invalid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise Night03Error("reviewed_at: timezone is required")
    if parsed.astimezone(timezone.utc) > now.astimezone(timezone.utc):
        raise Night03Error("reviewed_at: future timestamps are forbidden")
    return parsed.astimezone(timezone.utc).isoformat()


def validate_decision_manifest(
    repo_root: Path,
    manifest: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    if manifest.get("schema_version") != DECISION_SCHEMA_VERSION:
        raise Night03Error("decision manifest schema_version mismatch")
    if manifest.get("source_queue_path") != SOURCE_QUEUE.as_posix():
        raise Night03Error("decision manifest source_queue_path mismatch")
    if str(manifest.get("source_queue_sha256") or "").casefold() != EXPECTED_QUEUE_SHA256:
        raise Night03Error("decision manifest source_queue_sha256 mismatch")
    if sha256_file(repo_root / SOURCE_QUEUE) != EXPECTED_QUEUE_SHA256:
        raise Night03Error("physical source queue no longer matches exact hash")
    if manifest.get("machine_must_not_populate_reviewer_fields") is not True:
        raise Night03Error("machine reviewer guard must remain true")
    _nonempty_text(manifest, "created_by")
    _review_time(manifest.get("created_at"), now=now or datetime.now(tz=timezone.utc))
    decisions = manifest.get("decisions")
    if not isinstance(decisions, list):
        raise Night03Error("decisions must be a list")
    clock = now or datetime.now(tz=timezone.utc)
    queue_tasks = {str(task["id"]): task for task in authoritative_queue(repo_root)["tasks"]}
    validated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, entry in enumerate(decisions):
        if not isinstance(entry, dict):
            raise Night03Error(f"decisions[{index}] must be a mapping")
        occurrence_id = _nonempty_text(entry, "occurrence_id")
        if occurrence_id in seen:
            raise Night03Error(f"duplicate decision occurrence_id: {occurrence_id}")
        seen.add(occurrence_id)
        task = queue_tasks.get(occurrence_id)
        if task is None or task.get("work_type") == "bf2_work_order":
            raise Night03Error(f"decision occurrence is not authoritative: {occurrence_id}")
        kind = _nonempty_text(entry, "decision_kind")
        rule = DECISION_KINDS.get(kind)
        if rule is None:
            raise Night03Error(f"unsupported decision_kind: {kind}")
        if task.get("work_type") != rule["work_type"]:
            raise Night03Error(
                f"decision kind {kind} does not match {task.get('work_type')} occurrence"
            )
        decision = _nonempty_text(entry, "decision")
        if decision not in {"approved", "rejected"}:
            raise Night03Error(f"unsupported decision: {decision}")
        reviewer = _nonempty_text(entry, "reviewer")
        if FORBIDDEN_MACHINE_REVIEWERS.search(reviewer):
            raise Night03Error("reviewer identity appears machine-generated")
        authority = _nonempty_text(entry, "reviewer_authority")
        if authority != rule["authority"]:
            raise Night03Error(
                f"reviewer_authority {authority!r} does not match {rule['authority']!r}"
            )
        reviewed_at = _review_time(entry.get("reviewed_at"), now=clock)
        _text_list(entry, "notes", allow_empty=True)
        candidate_path = _bound_file(
            repo_root,
            entry.get("candidate_artifact_path"),
            entry.get("candidate_artifact_sha256"),
            field="candidate_artifact",
        )
        review_path = _bound_file(
            repo_root,
            entry.get("review_packet_path"),
            entry.get("review_packet_sha256"),
            field="review_packet",
        )
        candidate = _load_structured(candidate_path)
        review = _load_structured(review_path)
        if kind == "evidence_acceptance":
            validate_evidence_packet(review)
        elif kind == "analysis_acceptance":
            validate_analysis_packet(review)
        elif kind == "human_exact_hash":
            validate_human_packet(
                review,
                candidate_artifact_sha256=str(entry["candidate_artifact_sha256"]).casefold(),
            )
        elif kind == "pointer_contract_approval":
            validate_pointer_packets(candidate, review)
        projection = {
            "occurrence_id": occurrence_id,
            "decision_kind": kind,
            "decision": decision,
            "candidate_artifact_sha256": str(entry["candidate_artifact_sha256"]).casefold(),
            "review_packet_sha256": str(entry["review_packet_sha256"]).casefold(),
            "reviewer": reviewer,
            "reviewer_authority": authority,
            "reviewed_at": reviewed_at,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
        }
        projection["decision_digest_sha256"] = sha256_bytes(canonical_json_bytes(projection))
        validated.append(projection)
    return {
        "schema_version": "r5_night03_validated_decisions_v1",
        "valid": True,
        "decision_count": len(validated),
        "source_queue_sha256": EXPECTED_QUEUE_SHA256,
        "decisions": validated,
    }


def resolution_eligibility(
    validated_decision: Mapping[str, Any] | None,
    execution_receipt: Mapping[str, Any] | None,
) -> dict[str, Any]:
    reasons: list[str] = []
    if not validated_decision:
        reasons.append("missing_validated_decision")
    elif validated_decision.get("decision") != "approved":
        reasons.append("decision_not_approved")
    if not execution_receipt:
        reasons.append("missing_independent_receipt")
    else:
        if execution_receipt.get("terminal_status") != "passed":
            reasons.append("acceptance_not_passed")
        if not execution_receipt.get("lineage_match"):
            reasons.append("lineage_mismatch")
        if not execution_receipt.get("resolution_claim_allowed"):
            reasons.append("resolution_claim_not_allowed")
        if validated_decision and execution_receipt.get("occurrence_id") != validated_decision.get(
            "occurrence_id"
        ):
            reasons.append("occurrence_mismatch")
        if validated_decision and execution_receipt.get(
            "decision_digest_sha256"
        ) != validated_decision.get("decision_digest_sha256"):
            reasons.append("decision_digest_mismatch")
        if execution_receipt.get("source_queue_sha256") != EXPECTED_QUEUE_SHA256:
            reasons.append("source_queue_mismatch")
    return {
        "eligible": not reasons,
        "resolved": not reasons,
        "reasons": reasons,
    }


def decision_validation_markdown() -> str:
    return """# Night03 Decision Validation Contract

An approved decision is valid only when the physical Night02 queue, candidate
artifact, and review packet match their declared SHA-256 values; the occurrence
taxonomy matches the decision kind; reviewer identity and authority are external
and non-empty; and `reviewed_at` is timezone-aware and not in the future.

Validation does not resolve an occurrence. Resolution additionally requires an
independent passed execution or acceptance receipt with matching lineage and
decision digest.
"""


def materialize_decision_contracts(repo_root: Path) -> dict[str, Any]:
    root = repo_root / OUTPUT_ROOT / "decisions"
    schema = decision_manifest_schema()
    matrix = authority_matrix()
    adapters = adapter_contracts()
    policy = resolution_policy()
    write_json(root / "decision_manifest_schema.json", schema)
    atomic_write(
        root / "blank_decision_manifest.yaml",
        (repo_root / PACKAGE_ROOT / "templates/blank_decision_manifest.yaml").read_bytes(),
    )
    atomic_write(
        root / "decision_validation_contract.md",
        decision_validation_markdown().encode("utf-8"),
    )
    write_yaml(root / "authority_matrix.yaml", matrix)
    write_yaml(root / "evidence_adapter_contract.yaml", adapters["evidence"])
    write_yaml(root / "analysis_adapter_contract.yaml", adapters["analysis"])
    write_yaml(root / "human_gate_adapter_contract.yaml", adapters["human"])
    write_yaml(root / "pointer_approval_adapter_contract.yaml", adapters["pointer"])
    write_yaml(root / "resolution_policy.yaml", policy)
    return {
        "schema": schema,
        "authority": matrix,
        "adapters": adapters,
        "resolution_policy": policy,
    }
