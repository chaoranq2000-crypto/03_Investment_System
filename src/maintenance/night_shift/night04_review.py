"""Night04 exact-hash review control plane.

Generated forms are deliberately blank. Reviewer identity, authority,
timestamp, and decision may only enter through an external manifest whose
candidate and review-packet hashes still match the immutable registry.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .night03 import load_yaml, sha256_file, stable_payload, write_json, write_yaml
from .night03_backflow import packet_hash
from .night04 import (
    EXPECTED_CANDIDATE_READY,
    EXPECTED_QUEUE_SHA256,
    MISSION_ID,
    OUTPUT_ROOT,
    SOURCE_QUEUE,
    SOURCE_ROOT,
    Night04Error,
    _note_fields,
    authoritative_queue,
)
from .queue import atomic_write
from .receipts import canonical_json_bytes, sha256_bytes


DECISION_SCHEMA_VERSION = "r5_night04_batch_decision_manifest_v2"
REVIEW_PACKET_SCHEMA_VERSION = "r5_night04_review_packet_v1"
ALLOWED_DECISIONS = ("approve", "reject", "defer", "request_changes")
MACHINE_EMPTY_FIELDS = ("reviewer", "reviewer_authority", "reviewed_at", "decision")
FORBIDDEN_MACHINE_REVIEWERS = re.compile(
    r"(?:^|[\s_.-])(codex|agent|automation|machine|night[_ -]?shift|bot)(?:$|[\s_.-])",
    re.IGNORECASE,
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CANDIDATE_SOURCES: tuple[tuple[str, str, str, str], ...] = (
    ("evidence_required", "candidates/evidence_candidates.yaml", "candidates", "evidence_reviewer"),
    ("analysis_required", "candidates/analysis_candidates.yaml", "candidates", "research_reviewer"),
    ("human_exact_hash_gate", "candidates/human_gate_handoffs.yaml", "handoffs", "human_gate_reviewer"),
    ("engineering_local_pointer", "candidates/pointer_review_index.yaml", "proposals", "engineering_contract_reviewer"),
)
EXPECTED_KIND_COUNTS = {
    "evidence_required": 8,
    "analysis_required": 24,
    "human_exact_hash_gate": 3,
    "engineering_local_pointer": 8,
}


class Night04ReviewError(Night04Error):
    """Raised when the exact-hash review boundary is violated."""


def _candidate_file(repo_root: Path, relative: str) -> Path:
    path = repo_root / SOURCE_ROOT / relative
    if not path.is_file():
        raise Night04ReviewError(f"candidate source missing: {path}")
    return path


def _candidate_items(repo_root: Path) -> list[dict[str, Any]]:
    queue = {str(task["id"]): task for task in authoritative_queue(repo_root)["tasks"]}
    items: list[dict[str, Any]] = []
    for kind, relative, key, authority in CANDIDATE_SOURCES:
        source_path = _candidate_file(repo_root, relative)
        payload = load_yaml(source_path)
        records = payload.get(key)
        if not isinstance(records, list):
            raise Night04ReviewError(f"candidate collection missing: {relative}:{key}")
        for record in records:
            if not isinstance(record, dict):
                raise Night04ReviewError(f"candidate record must be a mapping: {relative}")
            occurrence_id = str(record.get("occurrence_id") or "")
            task = queue.get(occurrence_id)
            if task is None or task.get("night03_candidate_state") != "candidate_ready":
                raise Night04ReviewError(f"candidate is not authoritative: {occurrence_id}")
            supplied_hash = str(record.get("packet_sha256") or "").casefold()
            if not SHA256_RE.fullmatch(supplied_hash) or packet_hash(record) != supplied_hash:
                raise Night04ReviewError(f"candidate packet hash mismatch: {occurrence_id}")
            items.append(
                {
                    "candidate_kind": kind,
                    "required_authority": authority,
                    "source_path": source_path.relative_to(repo_root).as_posix(),
                    "source_collection_sha256": sha256_file(source_path),
                    "candidate": record,
                    "task": task,
                }
            )
    ids = [str(item["candidate"]["occurrence_id"]) for item in items]
    counts = Counter(str(item["candidate_kind"]) for item in items)
    if len(items) != EXPECTED_CANDIDATE_READY or len(set(ids)) != len(ids) or dict(counts) != EXPECTED_KIND_COUNTS:
        raise Night04ReviewError(f"candidate registry taxonomy mismatch: {dict(counts)}")
    return sorted(items, key=lambda item: str(item["candidate"]["occurrence_id"]))


def _source_lineage(kind: str, candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    if kind == "evidence_required":
        bound = candidate.get("bound_source_artifact") or {}
        return [{"role": "bound_failure_source", **dict(bound)}] + [dict(item) for item in candidate.get("candidate_source_paths") or []]
    if kind == "analysis_required":
        return [dict(item) for item in candidate.get("evidence_mapping") or []]
    if kind == "human_exact_hash_gate":
        return [
            {
                "role": "human_gate_candidate",
                "path": candidate.get("candidate_artifact_path"),
                "sha256": candidate.get("candidate_artifact_sha256"),
            }
        ]
    return [
        {
            "role": "pointer_source",
            "path": candidate.get("source_artifact"),
            "proposal_sha256": candidate.get("source_proposal_sha256"),
        }
    ]


def _counterevidence(kind: str, candidate: Mapping[str, Any]) -> list[Any]:
    if kind == "evidence_required":
        return list(candidate.get("conflict_evidence") or [candidate.get("conflict_evidence_status") or "UNKNOWN"])
    if kind == "analysis_required":
        return list(candidate.get("counter_evidence") or ["MISSING_REVIEWED_COUNTER_EVIDENCE"])
    if kind == "human_exact_hash_gate":
        return [{"quality_booleans": dict(candidate.get("quality_booleans") or {})}]
    return list(candidate.get("risks") or [])


def _uncertainties(kind: str, candidate: Mapping[str, Any]) -> list[str]:
    if kind == "evidence_required":
        return [str(item) for item in candidate.get("visible_gaps") or ["UNKNOWN_NOT_REVIEWED"]]
    if kind == "analysis_required":
        return [str(item) for item in candidate.get("unknowns") or ["UNKNOWN_PENDING_EXTERNAL_ANALYST_REVIEW"]]
    if kind == "human_exact_hash_gate":
        return ["external_exact_hash_review_required", "approval_is_not_resolution"]
    return ["pointer_semantics_require_external_approval", "dry_run_is_not_resolution"]


def _downstream_impact(queue_tasks: Sequence[Mapping[str, Any]], occurrence_id: str) -> dict[str, Any]:
    direct = sorted(
        str(task["id"])
        for task in queue_tasks
        if occurrence_id in {str(dep) for dep in task.get("depends_on") or []}
    )
    parents = sorted(
        str(task["id"])
        for task in queue_tasks
        if task.get("work_type") == "bf2_work_order" and occurrence_id in {str(dep) for dep in task.get("depends_on") or []}
    )
    return {
        "direct_dependent_ids": direct,
        "direct_dependency_count": len(direct),
        "parent_work_order_ids": parents,
        "resolution_effect": "recompute_from_independent_receipt_only",
    }


def _review_packet(
    *,
    kind: str,
    authority: str,
    source_path: str,
    candidate: Mapping[str, Any],
    task: Mapping[str, Any],
    downstream: Mapping[str, Any],
) -> dict[str, Any]:
    packet = {
        "schema_version": REVIEW_PACKET_SCHEMA_VERSION,
        "mission_id": MISSION_ID,
        "occurrence_id": str(candidate["occurrence_id"]),
        "parent_id": _note_fields(task).get("work_order_id"),
        "case_id": candidate.get("case_id"),
        "candidate_kind": kind,
        "required_reviewer_authority": authority,
        "candidate_artifact_path": source_path,
        "candidate_sha256": str(candidate["packet_sha256"]).casefold(),
        "source_queue_path": SOURCE_QUEUE.as_posix(),
        "source_queue_sha256": EXPECTED_QUEUE_SHA256,
        "source_lineage": _source_lineage(kind, candidate),
        "decision_options": list(ALLOWED_DECISIONS),
        "downstream_impact": dict(downstream),
        "counterevidence": _counterevidence(kind, candidate),
        "uncertainties": _uncertainties(kind, candidate),
        "reviewer": None,
        "reviewer_authority": None,
        "reviewed_at": None,
        "decision": None,
    }
    packet["packet_sha256"] = sha256_bytes(canonical_json_bytes(packet))
    return packet


def review_packet_contract() -> dict[str, Any]:
    return {
        "schema_version": "r5_night04_review_packet_contract_v1",
        "candidate_count": 43,
        "required_fields": [
            "occurrence_id",
            "parent_id",
            "case_id",
            "candidate_kind",
            "candidate_artifact_path",
            "candidate_sha256",
            "source_lineage",
            "decision_options",
            "downstream_impact",
            "counterevidence",
            "uncertainties",
            *MACHINE_EMPTY_FIELDS,
        ],
        "machine_must_leave_empty": list(MACHINE_EMPTY_FIELDS),
        "candidate_ready_is_resolution": False,
    }


def build_candidate_registry(repo_root: Path) -> dict[str, Any]:
    queue_tasks = authoritative_queue(repo_root)["tasks"]
    review_root = repo_root / OUTPUT_ROOT / "review_control/review_packets"
    entries: list[dict[str, Any]] = []
    for item in _candidate_items(repo_root):
        candidate = item["candidate"]
        occurrence_id = str(candidate["occurrence_id"])
        downstream = _downstream_impact(queue_tasks, occurrence_id)
        packet = _review_packet(
            kind=str(item["candidate_kind"]),
            authority=str(item["required_authority"]),
            source_path=str(item["source_path"]),
            candidate=candidate,
            task=item["task"],
            downstream=downstream,
        )
        packet_path = review_root / f"{occurrence_id}.yaml"
        write_yaml(packet_path, packet)
        entries.append(
            {
                "occurrence_id": occurrence_id,
                "parent_id": packet["parent_id"],
                "case_id": packet["case_id"],
                "candidate_kind": item["candidate_kind"],
                "required_reviewer_authority": item["required_authority"],
                "candidate_artifact_path": item["source_path"],
                "candidate_sha256": packet["candidate_sha256"],
                "review_packet_path": packet_path.relative_to(repo_root).as_posix(),
                "review_packet_sha256": sha256_file(packet_path),
                "review_packet_content_sha256": packet["packet_sha256"],
                "source_lineage": packet["source_lineage"],
                "decision_options": list(ALLOWED_DECISIONS),
                "unblock_leverage": downstream["direct_dependency_count"],
                "critical_path_rank": None,
                "downstream_impact": downstream,
                "counterevidence": packet["counterevidence"],
                "uncertainties": packet["uncertainties"],
                "reviewer": None,
                "reviewer_authority": None,
                "reviewed_at": None,
                "decision": None,
            }
        )
    registry = stable_payload(
        {
            "schema_version": "r5_night04_candidate_registry_v1",
            "mission_id": MISSION_ID,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "candidate_count": len(entries),
            "candidate_kind_counts": dict(Counter(str(item["candidate_kind"]) for item in entries)),
            "immutable": True,
            "candidates": entries,
        }
    )
    if registry["candidate_kind_counts"] != EXPECTED_KIND_COUNTS:
        raise Night04ReviewError("candidate registry counts changed")
    return registry


def batch_decision_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": DECISION_SCHEMA_VERSION,
        "type": "object",
        "required": ["schema_version", "source_queue_sha256", "records"],
        "properties": {
            "schema_version": {"const": DECISION_SCHEMA_VERSION},
            "source_queue_sha256": {"const": EXPECTED_QUEUE_SHA256},
            "records": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "occurrence_id",
                        "candidate_sha256",
                        "review_packet_sha256",
                        "reviewer",
                        "reviewer_authority",
                        "reviewed_at",
                        "decision",
                    ],
                    "properties": {
                        "occurrence_id": {"type": "string", "minLength": 1},
                        "candidate_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                        "review_packet_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                        "reviewer": {"type": "string", "minLength": 1},
                        "reviewer_authority": {"type": "string", "minLength": 1},
                        "reviewed_at": {"type": "string", "format": "date-time"},
                        "decision": {"enum": list(ALLOWED_DECISIONS)},
                        "notes": {"type": "array", "items": {"type": "string"}},
                    },
                    "additionalProperties": False,
                },
            },
        },
        "additionalProperties": False,
    }


def _blank_record(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "occurrence_id": entry["occurrence_id"],
        "candidate_kind": entry["candidate_kind"],
        "candidate_artifact_path": entry["candidate_artifact_path"],
        "candidate_sha256": entry["candidate_sha256"],
        "review_packet_path": entry["review_packet_path"],
        "review_packet_sha256": entry["review_packet_sha256"],
        "reviewer": None,
        "reviewer_authority": None,
        "reviewed_at": None,
        "decision": None,
        "notes": [],
    }


def build_blank_decision_bundles(repo_root: Path, registry: Mapping[str, Any]) -> dict[str, Any]:
    bundle_root = repo_root / OUTPUT_ROOT / "review_control/blank_decision_bundles"
    records: list[dict[str, Any]] = []
    for entry in registry["candidates"]:
        occurrence_id = str(entry["occurrence_id"])
        payload = {
            "schema_version": DECISION_SCHEMA_VERSION,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "records": [_blank_record(entry)],
        }
        path = bundle_root / f"{occurrence_id}.yaml"
        write_yaml(path, payload)
        records.append(
            {
                "occurrence_id": occurrence_id,
                "candidate_kind": entry["candidate_kind"],
                "path": path.relative_to(repo_root).as_posix(),
                "sha256": sha256_file(path),
            }
        )
    return stable_payload(
        {
            "schema_version": "r5_night04_blank_decision_bundle_index_v1",
            "bundle_count": len(records),
            "machine_fields_empty": True,
            "bundles": records,
        }
    )


def validate_machine_fields_empty(repo_root: Path, index: Mapping[str, Any]) -> dict[str, Any]:
    violations: list[str] = []
    for bundle in index.get("bundles") or []:
        payload = load_yaml(repo_root / str(bundle["path"]))
        for record in payload.get("records") or []:
            for field in MACHINE_EMPTY_FIELDS:
                if record.get(field) not in (None, ""):
                    violations.append(f"{record.get('occurrence_id')}:{field}")
    result = stable_payload(
        {
            "schema_version": "r5_night04_human_field_integrity_v1",
            "bundle_count": len(index.get("bundles") or []),
            "machine_owned_fields": list(MACHINE_EMPTY_FIELDS),
            "violations": violations,
            "passed": not violations,
        }
    )
    if violations:
        raise Night04ReviewError(f"machine populated reviewer fields: {violations}")
    return result


def _parse_review_time(value: Any, *, now: datetime) -> str:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError as exc:
        raise Night04ReviewError("reviewed_at is not valid ISO-8601") from exc
    if parsed.tzinfo is None or parsed.astimezone(timezone.utc) > now.astimezone(timezone.utc):
        raise Night04ReviewError("reviewed_at must be timezone-aware and not in the future")
    return parsed.astimezone(timezone.utc).isoformat()


def _authority_allowed(
    reviewer: str,
    authority: str,
    authority_registry: Mapping[str, Iterable[str]] | set[tuple[str, str]] | None,
) -> bool:
    if authority_registry is None:
        return False
    if isinstance(authority_registry, set):
        return (reviewer, authority) in authority_registry
    return authority in set(authority_registry.get(reviewer) or [])


def _record_fingerprint(record: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(dict(record)))


def validate_decision_batch(
    repo_root: Path,
    manifest: Mapping[str, Any],
    *,
    authority_registry: Mapping[str, Iterable[str]] | set[tuple[str, str]] | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if manifest.get("schema_version") != DECISION_SCHEMA_VERSION:
        raise Night04ReviewError("batch schema_version mismatch")
    if str(manifest.get("source_queue_sha256") or "").casefold() != EXPECTED_QUEUE_SHA256:
        raise Night04ReviewError("batch source queue hash mismatch")
    records = manifest.get("records")
    if not isinstance(records, list):
        raise Night04ReviewError("batch records must be a list")
    registry = load_yaml(repo_root / OUTPUT_ROOT / "review_control/candidate_registry.yaml")
    by_id = {str(item["occurrence_id"]): item for item in registry["candidates"]}
    groups: dict[str, list[tuple[int, Mapping[str, Any]]]] = defaultdict(list)
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            groups[f"__invalid_{index}"].append((index, {}))
        else:
            groups[str(record.get("occurrence_id") or f"__invalid_{index}")].append((index, record))
    accepted: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    replayed: list[dict[str, Any]] = []
    clock = now or datetime.now(tz=timezone.utc)
    for occurrence_id, grouped in groups.items():
        fingerprints = {_record_fingerprint(record) for _, record in grouped}
        if len(grouped) > 1 and len(fingerprints) > 1:
            invalid.extend({"index": index, "occurrence_id": occurrence_id, "reason": "conflicting_duplicate"} for index, _ in grouped)
            continue
        index, record = grouped[0]
        try:
            entry = by_id.get(occurrence_id)
            if entry is None:
                raise Night04ReviewError("occurrence is not in immutable registry")
            if str(record.get("candidate_sha256") or "").casefold() != entry["candidate_sha256"]:
                raise Night04ReviewError("stale_candidate_hash")
            if str(record.get("review_packet_sha256") or "").casefold() != entry["review_packet_sha256"]:
                raise Night04ReviewError("stale_review_packet_hash")
            decision = str(record.get("decision") or "")
            if decision not in ALLOWED_DECISIONS:
                raise Night04ReviewError("unsupported_decision")
            reviewer = str(record.get("reviewer") or "").strip()
            if not reviewer or FORBIDDEN_MACHINE_REVIEWERS.search(reviewer):
                raise Night04ReviewError("reviewer_identity_invalid")
            authority = str(record.get("reviewer_authority") or "").strip()
            if authority != entry["required_reviewer_authority"]:
                raise Night04ReviewError("reviewer_authority_scope_mismatch")
            if not _authority_allowed(reviewer, authority, authority_registry):
                raise Night04ReviewError("reviewer_authority_not_externally_verified")
            reviewed_at = _parse_review_time(record.get("reviewed_at"), now=clock)
            normalized = {
                "occurrence_id": occurrence_id,
                "candidate_kind": entry["candidate_kind"],
                "candidate_sha256": entry["candidate_sha256"],
                "review_packet_sha256": entry["review_packet_sha256"],
                "reviewer": reviewer,
                "reviewer_authority": authority,
                "reviewed_at": reviewed_at,
                "decision": decision,
                "notes": [str(item) for item in record.get("notes") or []],
            }
            normalized["decision_digest_sha256"] = sha256_bytes(canonical_json_bytes(normalized))
            accepted.append(normalized)
            replayed.extend(
                {"index": extra_index, "occurrence_id": occurrence_id, "reason": "identical_duplicate_replay"}
                for extra_index, _ in grouped[1:]
            )
        except Night04ReviewError as exc:
            invalid.append({"index": index, "occurrence_id": occurrence_id, "reason": str(exc)})
    return {
        "schema_version": "r5_night04_validated_decision_batch_v1",
        "source_queue_sha256": EXPECTED_QUEUE_SHA256,
        "input_count": len(records),
        "accepted_count": len(accepted),
        "invalid_count": len(invalid),
        "replayed_count": len(replayed),
        "accepted_records": accepted,
        "invalid_records": invalid,
        "replayed_records": replayed,
    }


def apply_replay_guard(records: Sequence[Mapping[str, Any]], seen_digests: set[str]) -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    replayed: list[str] = []
    for record in records:
        digest = str(record.get("decision_digest_sha256") or "")
        if not SHA256_RE.fullmatch(digest):
            raise Night04ReviewError("validated record decision digest missing")
        if digest in seen_digests:
            replayed.append(digest)
        else:
            seen_digests.add(digest)
            accepted.append(dict(record))
    return {"new_records": accepted, "replayed_digests": replayed, "seen_digests": sorted(seen_digests)}


def materialize_phase_b(repo_root: Path) -> dict[str, Any]:
    root = repo_root / OUTPUT_ROOT / "review_control"
    write_json(root / "batch_decision_schema.json", batch_decision_schema())
    write_yaml(root / "review_packet_contract.yaml", review_packet_contract())
    registry = build_candidate_registry(repo_root)
    write_yaml(root / "candidate_registry.yaml", registry)
    bundle_index = build_blank_decision_bundles(repo_root, registry)
    write_yaml(root / "blank_decision_bundles/index.yaml", bundle_index)
    integrity = validate_machine_fields_empty(repo_root, bundle_index)
    write_json(root / "human_field_integrity.json", integrity)
    contracts = {
        "conflict_policy.yaml": {
            "schema_version": "r5_night04_conflict_policy_v1",
            "conflicting_duplicates": "reject_all_records_for_occurrence",
            "identical_duplicates": "accept_first_and_record_replay",
            "decision_alone_resolves_occurrence": False,
        },
        "stale_hash_policy.yaml": {
            "schema_version": "r5_night04_stale_hash_policy_v1",
            "candidate_hash_mismatch": "reject_entire_record",
            "review_packet_hash_mismatch": "reject_entire_record",
            "rebase_or_regeneration_requires_new_external_decision": True,
        },
        "partial_acceptance_contract.yaml": {
            "schema_version": "r5_night04_partial_acceptance_contract_v1",
            "batch_envelope_failure": "reject_batch",
            "record_failure": "reject_record_and_continue_independent_records",
            "error_ledger_required": True,
        },
        "reviewer_authority_contract.yaml": {
            "schema_version": "r5_night04_reviewer_authority_contract_v1",
            "authority_source": "external_registry_only",
            "machine_may_create_reviewer_identity": False,
            "required_by_kind": {kind: authority for kind, _, _, authority in CANDIDATE_SOURCES},
        },
        "inbox_polling_contract.yaml": {
            "schema_version": "r5_night04_inbox_polling_contract_v1",
            "inbox": (OUTPUT_ROOT / "external_decisions").as_posix(),
            "poll_checkpoints": ["startup", "phase_b", "phase_c", "phase_d", "phase_e"],
            "idempotency_key": "decision_digest_sha256",
            "missing_external_decisions": "continue_bounded_work",
            "manufacture_decisions": False,
        },
    }
    for name, payload in contracts.items():
        write_yaml(root / name, payload)
    atomic_write(
        repo_root / OUTPUT_ROOT / "external_decisions/README.md",
        (
            "# External decisions\n\n"
            "Only externally completed exact-hash manifests belong here. Automation must not populate "
            "reviewer identity, authority, reviewed_at, or decision fields.\n"
        ).encode("utf-8"),
    )
    return {"registry": registry, "bundles": bundle_index, "integrity": integrity}
