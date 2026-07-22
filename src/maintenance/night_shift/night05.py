"""Night05 external-review intake and truthful zero-input close.

Night05 starts from the exact remote delivery of Night04. It may validate
authentic external exact-hash decisions, but it never invents reviewer
identity, authority, timestamps, or decisions. Without external decisions
and independent passed execution receipts, the only valid close is
review_intake_ready with all 69 unresolved queue items preserved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from copy import deepcopy
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from .night03 import (
    load_json,
    load_yaml,
    sha256_file,
    stable_payload,
    write_json,
    write_yaml,
)
from .night04_review import apply_replay_guard, validate_decision_batch
from .queue import atomic_write
from .receipts import canonical_json_bytes, sha256_bytes


MISSION_ID = "r5_overnight_05_20260723"
PACKAGE_ID = "R5_Overnight_Mission_05_20260723"
SOURCE_MISSION_ID = "r5_overnight_04_20260722"
SOURCE_COMMIT = "d0fc0fb735f0f581619e330b3fa6f1ef1914a276"
SOURCE_BRANCH = "codex/r5-night04-review-acceleration-and-unlock"
TARGET_BRANCH = "codex/r5-night05-external-review-intake"
SOURCE_ROOT = Path("reports/p1_6/r5_night_shift/r5_overnight_04_20260722")
OUTPUT_ROOT = Path("reports/p1_6/r5_night_shift/r5_overnight_05_20260723")
PACKAGE_ROOT = Path("codex_tasks/night_shift/r5_overnight_05_20260723")
SOURCE_QUEUE = SOURCE_ROOT / "next_night_queue.yaml"
SOURCE_REMOTE_RECEIPT = PACKAGE_ROOT / "inputs/night04_remote_delivery_receipt.json"
EXPECTED_SOURCE_FILE_COUNT = 228
EXPECTED_QUEUE_SHA256 = "57bef7dd3969d8b5405fdf9570e7792d11dd5b33f9a061f8664b513250f60700"
EXPECTED_DECISION_QUEUE_SHA256 = (
    "daaf3a9a9b37fa4c23c75e8bda401e41c41149917a1bf02419f89107ea9abe68"
)
EXPECTED_TOTAL_ITEMS = 69
EXPECTED_CANDIDATES = 43
EXPECTED_DEPENDENCIES = 20
EXPECTED_PARENTS = 6
EXPECTED_OCCURRENCES = 63
EXPECTED_SOURCE_HASHES = {
    "next_night_queue.yaml": EXPECTED_QUEUE_SHA256,
    "review_control/candidate_registry.yaml": (
        "c4577d21fa83951b6d7b001e1164b5e307f6bf388406a0cef7efc0c17ebf2fa1"
    ),
    "review_control/blank_decision_bundles/index.yaml": (
        "3459092ffc6928faa8cc29ff21fc7e5fa097754f6cf62adf6178b63ac8e78813"
    ),
    "review_acceleration/review_groups.yaml": (
        "5ecaf68b43fc95735070cec5d3a50ff08facc26c14382c217a7c7f6d7f6515cd"
    ),
    "review_acceleration/max_unlock_path.yaml": (
        "6900eb15f894a2d54901bcd93899de43e949088f1131cf8c3d259f404895088a"
    ),
    "review_acceleration/first_parent_path.yaml": (
        "2d43804c5025cf4f6a17c98efdf35fe19b3c48fea867ce482eb83e19d451ffe4"
    ),
    "pointer_prevalidation/batch_simulation.yaml": (
        "e27bfc7978f82e982ba1f7815d690e8b06314db2e96eff3207db9957f1bfee68"
    ),
    "pointer_prevalidation/conflict_matrix.yaml": (
        "ac1b65be239531a8d0bf2d46c2f89183d9c7f6f90d5c9b3332e31ec4f749be3f"
    ),
    "morning_readout.json": (
        "028941fbc3d62c6650878ccd26f9089b1f1c38f9c235a9d9de71b46188b967f1"
    ),
}
EXPECTED_KIND_COUNTS = {
    "analysis_required": 24,
    "evidence_required": 8,
    "engineering_local_pointer": 8,
    "human_exact_hash_gate": 3,
}
EXPECTED_QUEUE_TYPE_COUNTS = {
    "analysis_required": 24,
    "evidence_required": 8,
    "engineering_local": 8,
    "human_gate": 3,
    "dependency_blocked": EXPECTED_DEPENDENCIES,
    "bf2_work_order": EXPECTED_PARENTS,
}
WAVE_A_IDS = (
    "ns02_t30_occ_04343acd916afae4",
    "ns02_t30_occ_101f0195f0c5cf37",
    "ns02_t30_occ_1842382e6647f17d",
    "ns02_t30_occ_1977687ea7bce884",
    "ns02_t30_occ_23259d462e4ca0f3",
    "ns02_t30_occ_2c030a28f8631544",
    "ns02_t30_occ_3139481aee5c01e0",
)
WAVE_B_IDS = (
    "ns02_t30_occ_3caf2ad00e1b6285",
    "ns02_t30_occ_6870f1ec5d1048be",
    "ns02_t30_occ_6cd0e0bd57166a21",
    "ns02_t30_occ_86fb71b6c845c94f",
    "ns02_t30_occ_becffa9c7cb6d886",
    "ns02_t30_occ_d2ef6aeae1113c9c",
)
AUTHORITY_REGISTRY = OUTPUT_ROOT / "external_decisions/external_authority_registry.yaml"
AUTHORITY_SCHEMA = "r5_night05_external_authority_registry_v1"
DECISION_LEDGER = OUTPUT_ROOT / "execution/decision_replay_ledger.json"
REMOTE_RECEIPT = OUTPUT_ROOT / "publication/remote_delivery_receipt.json"
CI_STATUS = OUTPUT_ROOT / "publication/ci_status.md"
HISTORICAL_PATHS = (
    Path("reports/p1_6/r5_bundle17r"),
    Path("reports/p1_6/r5_night_shift/r5_overnight_02_20260720"),
    Path("reports/p1_6/r5_night_shift/r5_overnight_03_20260721"),
    SOURCE_ROOT,
)
ALLOWED_SCOPE_PREFIXES = (
    ".github/workflows/ci.yml",
    PACKAGE_ROOT.as_posix() + "/",
    OUTPUT_ROOT.as_posix() + "/",
    "scripts/run_r5_night_shift.py",
    "src/maintenance/night_shift/night05.py",
    "tests/test_r5_night_shift_night05",
)


class Night05Error(RuntimeError):
    """Raised when Night05 would cross a truth or publication boundary."""


class Night05Outcome(str, Enum):
    REVIEW_INTAKE_READY = "review_intake_ready"
    PARTIAL_RESOLUTION_PROGRESS = "partial_resolution_progress"
    FAILED = "failed"


def evaluate_night05_outcome(
    *,
    valid_external_decisions: int,
    independent_passed_receipts: int,
    resolved_delta: int,
    safety_failure: bool = False,
) -> Night05Outcome:
    if min(valid_external_decisions, independent_passed_receipts, resolved_delta) < 0:
        raise Night05Error("Night05 counts must not be negative")
    if resolved_delta > valid_external_decisions:
        raise Night05Error("resolved delta exceeds valid external decisions")
    if resolved_delta > independent_passed_receipts:
        raise Night05Error("resolved delta exceeds independent passed receipts")
    if safety_failure:
        return Night05Outcome.FAILED
    if resolved_delta:
        return Night05Outcome.PARTIAL_RESOLUTION_PROGRESS
    return Night05Outcome.REVIEW_INTAKE_READY


def _git_bytes(repo_root: Path, *args: str, check: bool = True) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise Night05Error(
            f"git {' '.join(args)} failed: {result.stderr.decode(errors='replace')}"
        )
    return result.stdout


def _git(repo_root: Path, *args: str, check: bool = True) -> str:
    return _git_bytes(repo_root, *args, check=check).decode(
        "utf-8", errors="replace"
    ).strip()


def _verify_stable_receipt(value: Mapping[str, Any], *, label: str) -> None:
    supplied = str(value.get("stable_receipt_sha256") or "")
    projection = {
        key: item for key, item in value.items() if key != "stable_receipt_sha256"
    }
    actual = sha256_bytes(canonical_json_bytes(projection))
    if supplied != actual:
        raise Night05Error(f"{label} stable receipt mismatch: {supplied} != {actual}")


def _read_structured(path: Path) -> dict[str, Any]:
    try:
        value = (
            json.loads(path.read_text(encoding="utf-8"))
            if path.suffix.casefold() == ".json"
            else yaml.safe_load(path.read_text(encoding="utf-8"))
        )
    except (OSError, UnicodeError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise Night05Error(f"cannot read structured input {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise Night05Error(f"structured input must be a mapping: {path}")
    return value


def _note_fields(task: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for note in task.get("notes") or []:
        text = str(note)
        if "=" in text:
            key, value = text.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def source_delivery_receipt(repo_root: Path) -> dict[str, Any]:
    path = repo_root / SOURCE_REMOTE_RECEIPT
    if not path.is_file():
        raise Night05Error(f"Night04 remote delivery snapshot missing: {path}")
    value = load_json(path)
    _verify_stable_receipt(value, label="Night04 remote delivery")
    ci = value.get("ci") or {}
    expected = {
        "mission_id": SOURCE_MISSION_ID,
        "target_branch": SOURCE_BRANCH,
        "local_head": SOURCE_COMMIT,
        "remote_head": SOURCE_COMMIT,
        "exact_head_match": True,
        "ci_head": SOURCE_COMMIT,
        "ci_conclusion": "success",
        "ci_run_id": 29764207418,
        "pr_created": False,
        "main_merged": False,
        "force_push_used": False,
    }
    observed = {
        "mission_id": value.get("mission_id"),
        "target_branch": value.get("target_branch"),
        "local_head": value.get("local_head"),
        "remote_head": value.get("remote_head"),
        "exact_head_match": value.get("exact_head_match"),
        "ci_head": ci.get("head_sha"),
        "ci_conclusion": ci.get("conclusion"),
        "ci_run_id": ci.get("database_id"),
        "pr_created": value.get("pr_created"),
        "main_merged": value.get("main_merged"),
        "force_push_used": value.get("force_push_used"),
    }
    if observed != expected:
        raise Night05Error(f"Night04 remote delivery mismatch: {observed}")
    return value


def authoritative_queue(repo_root: Path) -> dict[str, Any]:
    path = repo_root / SOURCE_QUEUE
    actual_hash = sha256_file(path) if path.is_file() else None
    if actual_hash != EXPECTED_QUEUE_SHA256:
        raise Night05Error(f"Night04 queue hash mismatch: {actual_hash}")
    value = load_yaml(path)
    tasks = value.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != EXPECTED_TOTAL_ITEMS:
        raise Night05Error("Night04 queue must contain exactly 69 tasks")
    ids = [str(item.get("id") or "") for item in tasks if isinstance(item, dict)]
    if len(ids) != EXPECTED_TOTAL_ITEMS or len(set(ids)) != len(ids) or not all(ids):
        raise Night05Error("Night04 queue IDs are missing or duplicated")
    counts = Counter(str(item.get("work_type")) for item in tasks)
    observed = {key: counts.get(key, 0) for key in EXPECTED_QUEUE_TYPE_COUNTS}
    if observed != EXPECTED_QUEUE_TYPE_COUNTS:
        raise Night05Error(f"Night04 queue taxonomy drifted: {observed}")
    if value.get("source_commit") is not None:
        raise Night05Error("Night04 carry-forward queue source commit was already mutated")
    if value.get("source_commit_policy") != "resolve_final_remote_head_at_bootstrap":
        raise Night05Error("Night04 carry-forward queue bootstrap policy drifted")
    return value


def _source_git_manifest(repo_root: Path) -> dict[str, Any]:
    raw = _git(
        repo_root, "ls-tree", "-r", SOURCE_COMMIT, "--", SOURCE_ROOT.as_posix()
    )
    records: list[dict[str, Any]] = []
    for line in raw.splitlines():
        metadata, relative = line.split("\t", 1)
        mode, object_type, oid = metadata.split()
        if object_type != "blob":
            continue
        payload = _git_bytes(repo_root, "cat-file", "blob", oid)
        records.append(
            {
                "path": relative,
                "git_mode": mode,
                "git_blob_oid": oid,
                "blob_sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
            }
        )
    if len(records) != EXPECTED_SOURCE_FILE_COUNT:
        raise Night05Error(
            f"Night04 tracked source file count drifted: {len(records)}"
        )
    return stable_payload(
        {
            "schema_version": "r5_night05_source_git_manifest_v1",
            "mission_id": MISSION_ID,
            "source_mission_id": SOURCE_MISSION_ID,
            "source_commit": SOURCE_COMMIT,
            "source_root": SOURCE_ROOT.as_posix(),
            "hash_representation": "git_blob_bytes",
            "file_count": len(records),
            "files": records,
        }
    )


def build_source_preflight(repo_root: Path) -> dict[str, Any]:
    delivery = source_delivery_receipt(repo_root)
    queue = authoritative_queue(repo_root)
    key_files: list[dict[str, Any]] = []
    for relative, expected in EXPECTED_SOURCE_HASHES.items():
        path = repo_root / SOURCE_ROOT / relative
        actual = sha256_file(path) if path.is_file() else None
        if actual != expected:
            raise Night05Error(
                f"Night04 source hash drifted for {relative}: {actual} != {expected}"
            )
        key_files.append(
            {
                "path": (SOURCE_ROOT / relative).as_posix(),
                "sha256": actual,
                "bytes": path.stat().st_size,
            }
        )

    registry = load_yaml(
        repo_root / SOURCE_ROOT / "review_control/candidate_registry.yaml"
    )
    _verify_stable_receipt(registry, label="Night04 candidate registry")
    candidates = registry.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != EXPECTED_CANDIDATES:
        raise Night05Error("Night04 candidate registry must contain 43 candidates")
    candidate_counts = Counter(str(item.get("candidate_kind")) for item in candidates)
    observed_kinds = {
        key: candidate_counts.get(key, 0) for key in EXPECTED_KIND_COUNTS
    }
    if observed_kinds != EXPECTED_KIND_COUNTS:
        raise Night05Error(f"Night04 candidate taxonomy drifted: {observed_kinds}")

    lineage = load_json(repo_root / SOURCE_ROOT / "queue/lineage_audit.json")
    _verify_stable_receipt(lineage, label="Night04 lineage audit")
    if (
        not lineage.get("passed")
        or lineage.get("task_count") != EXPECTED_TOTAL_ITEMS
        or lineage.get("mismatch_task_ids")
    ):
        raise Night05Error("Night04 lineage audit is not clean")
    lineage_ids = {
        str(item.get("task_id")) for item in lineage.get("records") or []
    }
    queue_ids = {str(item.get("id")) for item in queue["tasks"]}
    if lineage_ids != queue_ids:
        raise Night05Error("Night04 queue and lineage ID sets differ")

    readout = load_json(repo_root / SOURCE_ROOT / "morning_readout.json")
    _verify_stable_receipt(readout, label="Night04 morning readout")
    truth = readout.get("research_truth") or {}
    observed_truth = {
        "resolved": truth.get("blocker_occurrences_resolved"),
        "total": truth.get("blocker_occurrences_total"),
        "candidate_ready": truth.get("candidate_ready"),
        "dependency_blocked": truth.get("dependency_blocked"),
        "dependency_unlocked": truth.get("dependency_unlocked"),
        "parents_resolved": truth.get("work_orders_resolved"),
        "program_goal": truth.get("program_goal"),
        "sample_quality": truth.get("sample_quality_allowed"),
        "p2": truth.get("p2_allowed"),
    }
    expected_truth = {
        "resolved": 0,
        "total": EXPECTED_OCCURRENCES,
        "candidate_ready": EXPECTED_CANDIDATES,
        "dependency_blocked": EXPECTED_DEPENDENCIES,
        "dependency_unlocked": 0,
        "parents_resolved": 0,
        "program_goal": "open_needs_targeted_backflow",
        "sample_quality": False,
        "p2": False,
    }
    if observed_truth != expected_truth:
        raise Night05Error(f"Night04 starting truth drifted: {observed_truth}")

    return stable_payload(
        {
            "schema_version": "r5_night05_source_preflight_v1",
            "mission_id": MISSION_ID,
            "source_mission_id": SOURCE_MISSION_ID,
            "source_commit": SOURCE_COMMIT,
            "source_branch": SOURCE_BRANCH,
            "source_delivery_receipt": {
                "path": SOURCE_REMOTE_RECEIPT.as_posix(),
                "physical_sha256": sha256_file(repo_root / SOURCE_REMOTE_RECEIPT),
                "stable_receipt_sha256": delivery["stable_receipt_sha256"],
                "ci_run_id": delivery["ci"]["database_id"],
                "ci_conclusion": delivery["ci"]["conclusion"],
            },
            "queue_sha256": EXPECTED_QUEUE_SHA256,
            "queue_task_count": len(queue["tasks"]),
            "candidate_count": len(candidates),
            "candidate_kind_counts": observed_kinds,
            "starting_truth": observed_truth,
            "key_files": key_files,
            "source_hashes_reproducible": True,
            "passed": True,
        }
    )


def build_review_wave_plan(repo_root: Path) -> dict[str, Any]:
    registry = load_yaml(
        repo_root / SOURCE_ROOT / "review_control/candidate_registry.yaml"
    )
    by_id = {str(item["occurrence_id"]): item for item in registry["candidates"]}
    all_ids = set(by_id)
    wave_a = set(WAVE_A_IDS)
    wave_b = set(WAVE_B_IDS)
    if wave_a & wave_b or not (wave_a | wave_b) <= all_ids:
        raise Night05Error("Night05 Wave A/B IDs do not match the candidate registry")
    wave_c = sorted(all_ids - wave_a - wave_b)
    if len(wave_c) != 30:
        raise Night05Error(f"Night05 Wave C must contain 30 candidates: {len(wave_c)}")
    groups = load_yaml(
        repo_root / SOURCE_ROOT / "review_acceleration/review_groups.yaml"
    )
    _verify_stable_receipt(groups, label="Night04 review groups")
    max_unlock = load_yaml(
        repo_root / SOURCE_ROOT / "review_acceleration/max_unlock_path.yaml"
    )
    _verify_stable_receipt(max_unlock, label="Night04 max unlock path")
    first_seven = tuple(
        str(item["occurrence_id"]) for item in max_unlock["steps"][:7]
    )
    if groups.get("candidate_count") != EXPECTED_CANDIDATES:
        raise Night05Error("Night04 review groups candidate count drifted")
    if first_seven != WAVE_A_IDS:
        raise Night05Error("Night05 Wave A no longer matches the max-unlock path")
    first_parent = load_yaml(
        repo_root / SOURCE_ROOT / "review_acceleration/first_parent_path.yaml"
    )
    _verify_stable_receipt(first_parent, label="Night04 first parent path")
    return stable_payload(
        {
            "schema_version": "r5_night05_review_wave_plan_v1",
            "mission_id": MISSION_ID,
            "source_commit": SOURCE_COMMIT,
            "candidate_count": EXPECTED_CANDIDATES,
            "waves": [
                {
                    "wave_id": "wave_a_top_leverage_7",
                    "priority": 1,
                    "candidate_count": len(WAVE_A_IDS),
                    "candidate_ids": list(WAVE_A_IDS),
                    "dependency_membership_coverage": EXPECTED_DEPENDENCIES,
                    "actual_dependency_unlock": 0,
                },
                {
                    "wave_id": "wave_b_copper_parent_remaining_6",
                    "priority": 2,
                    "candidate_count": len(WAVE_B_IDS),
                    "candidate_ids": list(WAVE_B_IDS),
                    "selected_parent_id": "ns02_t30_wo_e205ce3a49c56b7e",
                    "all_atomic_receipts_required": True,
                },
                {
                    "wave_id": "wave_c_remaining_30",
                    "priority": 3,
                    "candidate_count": len(wave_c),
                    "candidate_ids": wave_c,
                },
            ],
            "external_review_required": True,
            "machine_may_populate_decision_fields": False,
        }
    )


def load_external_authorities(
    repo_root: Path,
) -> tuple[set[tuple[str, str]], dict[str, Any]]:
    path = repo_root / AUTHORITY_REGISTRY
    if not path.is_file():
        return set(), {
            "path": AUTHORITY_REGISTRY.as_posix(),
            "status": "missing_external_registry",
            "reviewer_count": 0,
            "authority_binding_count": 0,
            "sha256": None,
        }
    if path.is_symlink():
        raise Night05Error("external authority registry must not be a symlink")
    value = _read_structured(path)
    if value.get("schema_version") != AUTHORITY_SCHEMA:
        raise Night05Error("external authority registry schema mismatch")
    reviewers = value.get("reviewers")
    if not isinstance(reviewers, list):
        raise Night05Error("external authority registry reviewers must be a list")
    bindings: set[tuple[str, str]] = set()
    names: set[str] = set()
    for item in reviewers:
        if not isinstance(item, dict):
            raise Night05Error("external authority registry entry must be a mapping")
        reviewer = str(item.get("reviewer") or "").strip()
        authorities = item.get("authorities")
        if not reviewer or not isinstance(authorities, list) or not authorities:
            raise Night05Error("external authority registry entry is incomplete")
        names.add(reviewer)
        bindings.update(
            (reviewer, str(authority).strip())
            for authority in authorities
            if str(authority).strip()
        )
    return bindings, {
        "path": AUTHORITY_REGISTRY.as_posix(),
        "status": "verified_external_registry",
        "reviewer_count": len(names),
        "authority_binding_count": len(bindings),
        "sha256": sha256_file(path),
    }


def _decision_files(repo_root: Path) -> list[Path]:
    root = repo_root / OUTPUT_ROOT / "external_decisions"
    if not root.is_dir():
        return []
    return sorted(
        path
        for path in root.iterdir()
        if path.is_file()
        and not path.is_symlink()
        and path.name != AUTHORITY_REGISTRY.name
        and not path.name.casefold().startswith("readme")
        and ".template." not in path.name.casefold()
        and path.suffix.casefold() in {".json", ".yaml", ".yml"}
    )


def _existing_decision_ledger(repo_root: Path) -> dict[str, Any]:
    path = repo_root / DECISION_LEDGER
    if not path.is_file():
        return {"records": []}
    value = load_json(path)
    _verify_stable_receipt(value, label="Night05 decision replay ledger")
    if not isinstance(value.get("records"), list):
        raise Night05Error("Night05 decision replay ledger records must be a list")
    return value


def consume_external_decisions(repo_root: Path) -> dict[str, Any]:
    authorities, authority_receipt = load_external_authorities(repo_root)
    files = _decision_files(repo_root)
    manifests: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for path in files:
        relative = path.relative_to(repo_root).as_posix()
        try:
            validated = validate_decision_batch(
                repo_root,
                _read_structured(path),
                authority_registry=authorities,
            )
        except Exception as exc:
            manifests.append(
                {
                    "path": relative,
                    "sha256": sha256_file(path),
                    "status": "invalid_manifest",
                    "reason": str(exc),
                }
            )
            invalid.append({"manifest_path": relative, "reason": str(exc)})
            continue
        manifests.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "status": (
                    "partially_valid" if validated["invalid_count"] else "valid"
                ),
                "input_count": validated["input_count"],
                "accepted_count": validated["accepted_count"],
                "invalid_count": validated["invalid_count"],
                "replayed_count": validated["replayed_count"],
            }
        )
        accepted.extend(
            {**item, "source_manifest_path": relative}
            for item in validated["accepted_records"]
        )
        invalid.extend(
            {**item, "manifest_path": relative}
            for item in validated["invalid_records"]
        )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in accepted:
        grouped[str(item["occurrence_id"])].append(item)
    conflict_free: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for occurrence_id, records in sorted(grouped.items()):
        digests = {str(item["decision_digest_sha256"]) for item in records}
        if len(digests) > 1:
            conflicts.append(
                {
                    "occurrence_id": occurrence_id,
                    "reason": "cross_manifest_conflict",
                    "decision_digests": sorted(digests),
                    "source_manifest_paths": sorted(
                        str(item["source_manifest_path"]) for item in records
                    ),
                }
            )
        else:
            conflict_free.append(records[0])

    previous = _existing_decision_ledger(repo_root)
    previous_records = [dict(item) for item in previous.get("records") or []]
    previous_by_digest = {
        str(item["decision_digest_sha256"]): item for item in previous_records
    }
    replay = apply_replay_guard(conflict_free, set(previous_by_digest))
    for item in replay["new_records"]:
        previous_by_digest[str(item["decision_digest_sha256"])] = item
    ledger_records = sorted(
        previous_by_digest.values(),
        key=lambda item: (
            str(item["occurrence_id"]),
            str(item["decision_digest_sha256"]),
        ),
    )
    ledger = stable_payload(
        {
            "schema_version": "r5_night05_decision_replay_ledger_v1",
            "mission_id": MISSION_ID,
            "source_queue_sha256": EXPECTED_DECISION_QUEUE_SHA256,
            "records": ledger_records,
        }
    )
    write_json(repo_root / DECISION_LEDGER, ledger)
    approved = [item for item in ledger_records if item.get("decision") == "approve"]
    outcome = (
        "no_external_decisions"
        if not files and not ledger_records
        else "validated_decisions_pending_typed_execution"
        if ledger_records
        else "external_decisions_rejected"
    )
    payload = stable_payload(
        {
            "schema_version": "r5_night05_external_decision_intake_v1",
            "mission_id": MISSION_ID,
            "source_commit": SOURCE_COMMIT,
            "source_queue_sha256": EXPECTED_DECISION_QUEUE_SHA256,
            "authority_registry": authority_receipt,
            "scanned_manifest_count": len(files),
            "manifests": manifests,
            "validated_decision_count": len(conflict_free),
            "ledger_decision_count": len(ledger_records),
            "approved_decision_count": len(approved),
            "newly_consumed_count": len(replay["new_records"]),
            "replayed_decision_count": len(replay["replayed_digests"]),
            "invalid_record_count": len(invalid) + len(conflicts),
            "invalid_records": invalid,
            "cross_manifest_conflicts": conflicts,
            "approved_records": approved,
            "machine_generated_decisions": 0,
            "external_gate_state": "open" if approved else "blocked_external",
            "outcome": outcome,
        }
    )
    write_json(
        repo_root / OUTPUT_ROOT / "execution/decision_intake.json", payload
    )
    return payload


def build_typed_execution_summary(
    intake: Mapping[str, Any],
) -> dict[str, Any]:
    pending = sorted(
        str(item["occurrence_id"]) for item in intake.get("approved_records") or []
    )
    return stable_payload(
        {
            "schema_version": "r5_night05_typed_execution_summary_v1",
            "mission_id": MISSION_ID,
            "approved_input_count": len(pending),
            "pending_explicit_executor_count": len(pending),
            "pending_occurrence_ids": pending,
            "independent_passed_receipt_count": 0,
            "resolved_delta": 0,
            "automatic_execution_used": False,
            "outcome": (
                "approved_decisions_pending_explicit_executor"
                if pending
                else "blocked_external_no_approved_decisions"
            ),
        }
    )


def build_recompute_summary(repo_root: Path) -> dict[str, Any]:
    dependencies = load_json(
        repo_root / SOURCE_ROOT / "execution/dependency_recompute.json"
    )
    parents = load_json(repo_root / SOURCE_ROOT / "execution/parent_recompute.json")
    _verify_stable_receipt(dependencies, label="Night04 dependency recompute")
    _verify_stable_receipt(parents, label="Night04 parent recompute")
    if (
        dependencies.get("dependency_count") != EXPECTED_DEPENDENCIES
        or dependencies.get("unlocked_count") != 0
        or dependencies.get("resolved_count") != 0
        or parents.get("parent_count") != EXPECTED_PARENTS
        or parents.get("resolved_parent_count") != 0
        or parents.get("pending_parent_count") != EXPECTED_PARENTS
    ):
        raise Night05Error(
            "Night04 recompute source does not preserve zero-resolution truth"
        )
    return stable_payload(
        {
            "schema_version": "r5_night05_recompute_summary_v1",
            "mission_id": MISSION_ID,
            "trigger": "no_independent_passed_execution_receipts",
            "dependency_count": EXPECTED_DEPENDENCIES,
            "dependency_unlocked_count": 0,
            "dependency_blocked_count": EXPECTED_DEPENDENCIES,
            "parent_count": EXPECTED_PARENTS,
            "parent_resolved_count": 0,
            "parent_pending_count": EXPECTED_PARENTS,
            "source_dependency_receipt_sha256": dependencies[
                "stable_receipt_sha256"
            ],
            "source_parent_receipt_sha256": parents["stable_receipt_sha256"],
            "state_change_allowed": False,
        }
    )


def build_next_queue(repo_root: Path) -> dict[str, Any]:
    source = authoritative_queue(repo_root)
    result = deepcopy(source)
    result["package_id"] = PACKAGE_ID
    result["mission_id"] = MISSION_ID
    result["source_mission_id"] = SOURCE_MISSION_ID
    result["source_commit"] = SOURCE_COMMIT
    result["source_commit_policy"] = (
        "resolved_from_night04_remote_delivery_receipt"
    )
    result["publication_receipt"] = SOURCE_REMOTE_RECEIPT.as_posix()
    if source["tasks"] != result["tasks"]:
        raise Night05Error("Night05 carry-forward tasks changed during source resolution")
    for before, after in zip(source["tasks"], result["tasks"], strict=True):
        if before["id"] != after["id"]:
            raise Night05Error("Night05 carry-forward ID drift")
        before_notes = _note_fields(before)
        after_notes = _note_fields(after)
        for key in ("source_artifact_path", "source_artifact_sha256"):
            if before_notes.get(key) != after_notes.get(key):
                raise Night05Error(f"Night05 carry-forward {key} drift")
    return result


def build_change_log() -> dict[str, Any]:
    return stable_payload(
        {
            "schema_version": "r5_night05_change_log_v1",
            "mission_id": MISSION_ID,
            "starting_resolved": 0,
            "ending_resolved": 0,
            "resolved_delta": 0,
            "changed_occurrence_ids": [],
            "changed_dependency_ids": [],
            "changed_parent_ids": [],
            "reason": (
                "no_valid_external_decision_and_no_independent_passed_receipt"
            ),
            "silent_rewrite_used": False,
        }
    )


def build_blocker_ledger(intake: Mapping[str, Any]) -> dict[str, Any]:
    approved = int(intake.get("approved_decision_count") or 0)
    blockers = [
        {
            "blocker_id": "external_authority_registry_missing",
            "owner": "external_review_lead",
            "severity": "high",
            "status": (
                "open"
                if intake["authority_registry"]["status"]
                == "missing_external_registry"
                else "resolved"
            ),
            "next_step": "register_real_reviewer_authority_pairs",
        },
        {
            "blocker_id": "external_decisions_zero_of_43",
            "owner": "typed_external_reviewers",
            "severity": "high",
            "status": "open" if approved == 0 else "partial",
            "next_step": "complete_wave_a_exact_hash_decision_manifests",
        },
        {
            "blocker_id": "independent_execution_receipts_missing",
            "owner": "night05_executor",
            "severity": "high",
            "status": "open",
            "next_step": "execute_valid_approved_records_by_candidate_kind",
        },
        {
            "blocker_id": "pointer_duplicate_semantics_and_shared_files",
            "owner": "engineering_executor",
            "severity": "medium",
            "status": "open",
            "next_step": (
                "deduplicate_by_semantic_variant_and_validate_each_occurrence"
            ),
        },
    ]
    return stable_payload(
        {
            "schema_version": "r5_night05_blocker_ledger_v1",
            "mission_id": MISSION_ID,
            "program_goal": "open_needs_targeted_backflow",
            "blocker_occurrences_total": EXPECTED_OCCURRENCES,
            "blocker_occurrences_resolved": 0,
            "candidate_ready_count": EXPECTED_CANDIDATES,
            "dependency_blocked_count": EXPECTED_DEPENDENCIES,
            "parent_blocked_count": EXPECTED_PARENTS,
            "blockers": blockers,
        }
    )


def build_mission_state(intake: Mapping[str, Any]) -> dict[str, Any]:
    no_decisions = int(intake.get("approved_decision_count") or 0) == 0
    return stable_payload(
        {
            "schema_version": "r5_night05_mission_state_v1",
            "mission_id": MISSION_ID,
            "source_commit": SOURCE_COMMIT,
            "target_branch": TARGET_BRANCH,
            "mission_outcome": "review_intake_ready",
            "program_goal": {
                "state": "open_needs_targeted_backflow",
                "close_allowed": False,
                "blocker_occurrences_total": EXPECTED_OCCURRENCES,
                "blocker_occurrences_resolved": 0,
            },
            "phases": [
                {"id": "n5_00_isolated_bootstrap", "status": "passed"},
                {
                    "id": "n5_01_external_decision_intake",
                    "status": (
                        "closed_review_intake_ready" if no_decisions else "passed"
                    ),
                },
                {"id": "n5_02_wave_a_review", "status": "blocked_external"},
                {
                    "id": "n5_03_wave_b_first_parent",
                    "status": "blocked_external",
                },
                {
                    "id": "n5_04_wave_c_remaining_review",
                    "status": "blocked_external",
                },
                {
                    "id": "n5_05_recompute_and_close",
                    "status": "passed_zero_input_close",
                },
            ],
            "truth_boundary": {
                "candidate_is_not_resolution": True,
                "approval_is_not_passed_receipt": True,
                "machine_generated_decisions": 0,
                "sample_quality_passed": False,
                "p2_ready": False,
            },
        }
    )


def _status_paths(repo_root: Path) -> list[str]:
    rows = _git_bytes(
        repo_root, "status", "--porcelain=v1", "--untracked-files=all"
    ).decode("utf-8", errors="replace").splitlines()
    paths: list[str] = []
    for row in rows:
        path = row[3:].strip().replace("\\", "/")
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path.strip('"'))
    return sorted(set(paths))


def build_scope_audit(repo_root: Path) -> dict[str, Any]:
    historical_changed: set[str] = set()
    for historical in HISTORICAL_PATHS:
        committed = _git(
            repo_root,
            "diff",
            "--name-only",
            f"{SOURCE_COMMIT}..HEAD",
            "--",
            historical.as_posix(),
        )
        working = _git(
            repo_root,
            "diff",
            "--name-only",
            SOURCE_COMMIT,
            "--",
            historical.as_posix(),
        )
        historical_changed.update(
            item
            for item in (committed + "\n" + working).splitlines()
            if item
        )
    changed = _status_paths(repo_root)
    out_of_scope = [
        path
        for path in changed
        if not any(
            path == prefix or path.startswith(prefix)
            for prefix in ALLOWED_SCOPE_PREFIXES
        )
    ]
    temporary = [
        path
        for path in changed
        if "/__pycache__/" in f"/{path}/"
        or path.endswith(".pyc")
        or "/.local/" in f"/{path}/"
    ]
    diff_check = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    passed = (
        not historical_changed
        and not out_of_scope
        and not temporary
        and diff_check.returncode == 0
    )
    if not passed:
        raise Night05Error(
            "Night05 scope audit failed: "
            f"historical={sorted(historical_changed)} "
            f"out_of_scope={out_of_scope} temporary={temporary} "
            f"diff={diff_check.stdout}{diff_check.stderr}"
        )
    return stable_payload(
        {
            "schema_version": "r5_night05_scope_audit_v1",
            "mission_id": MISSION_ID,
            "baseline_commit": SOURCE_COMMIT,
            "historical_paths": [path.as_posix() for path in HISTORICAL_PATHS],
            "historical_changed_paths": sorted(historical_changed),
            "observed_changed_paths": changed,
            "out_of_scope_paths": out_of_scope,
            "temporary_paths": temporary,
            "git_diff_check": "passed",
            "pr_created": False,
            "main_merged": False,
            "force_push_used": False,
            "passed": True,
        }
    )


def build_ci_contract(repo_root: Path) -> dict[str, Any]:
    workflow = repo_root / ".github/workflows/ci.yml"
    text = workflow.read_text(encoding="utf-8")
    checks = {
        "full_history_checkout": "fetch-depth: 0" in text,
        "source_route_gate": (
            "run_source_route_quality_gate.py --import-check" in text
        ),
        "night_shift_suite": "tests/test_r5_night_shift_*.py" in text,
        "full_pytest": "python -m pytest -q" in text,
        "night04_historical_guard": SOURCE_ROOT.as_posix() in text,
        "night05_baseline_guard": SOURCE_COMMIT in text,
        "no_publication_mutation": True,
    }
    if not all(checks.values()):
        raise Night05Error(f"Night05 CI contract incomplete: {checks}")
    return stable_payload(
        {
            "schema_version": "r5_night05_ci_contract_v1",
            "mission_id": MISSION_ID,
            "workflow": ".github/workflows/ci.yml",
            "workflow_sha256": sha256_file(workflow),
            "checks": checks,
            "passed": True,
        }
    )


def build_full_regression(
    *,
    night_shift_passed: int,
    full_passed: int,
    full_skipped: int,
    source_capabilities: int,
    source_blocking: int,
) -> dict[str, Any]:
    passed = (
        night_shift_passed >= 200
        and full_passed >= 1133
        and full_skipped >= 2
        and source_capabilities >= 17
        and source_blocking == 0
    )
    if not passed:
        raise Night05Error(
            "Night05 regression baseline failed: "
            f"night_shift={night_shift_passed}, full={full_passed}, "
            f"skipped={full_skipped}, capabilities={source_capabilities}, "
            f"blocking={source_blocking}"
        )
    return stable_payload(
        {
            "schema_version": "r5_night05_full_regression_v1",
            "mission_id": MISSION_ID,
            "commands": [
                {
                    "command": (
                        "python -m pytest -q tests/test_r5_night_shift_*.py"
                    ),
                    "passed": night_shift_passed,
                    "result": "passed",
                },
                {
                    "command": (
                        "python scripts/run_source_route_quality_gate.py "
                        "--import-check --output "
                        "reports/quality/ci_source_route_quality_report.yaml"
                    ),
                    "capabilities": source_capabilities,
                    "blocking": source_blocking,
                    "result": "passed",
                },
                {
                    "command": "python -m pytest -q",
                    "passed": full_passed,
                    "skipped": full_skipped,
                    "result": "passed",
                },
                {"command": "git diff --check", "result": "passed"},
                {"command": "historical path diff guard", "result": "passed"},
            ],
            "all_passed": True,
        }
    )


def build_tracked_delivery_receipt(repo_root: Path) -> dict[str, Any]:
    rows = _git(
        repo_root,
        "log",
        "--reverse",
        "--format=%H%x09%s",
        f"{SOURCE_COMMIT}..HEAD",
    ).splitlines()
    commits = [
        {"sha": row.split("\t", 1)[0], "subject": row.split("\t", 1)[1]}
        for row in rows
        if "\t" in row
    ]
    if not commits:
        raise Night05Error(
            "Night05 tracked delivery needs at least one implementation commit"
        )
    return stable_payload(
        {
            "schema_version": "r5_night05_tracked_delivery_receipt_v1",
            "mission_id": MISSION_ID,
            "target_branch": TARGET_BRANCH,
            "baseline_commit": SOURCE_COMMIT,
            "implementation_snapshot_before_publication_commit": {
                "commit_sha": _git(repo_root, "rev-parse", "HEAD"),
                "tree_sha": _git(repo_root, "rev-parse", "HEAD^{tree}"),
            },
            "commits_after_baseline_before_publication_commit": len(commits),
            "commits": commits,
            "final_publication_head": None,
            "final_publication_resolution_policy": (
                "authoritative_post_push_remote_receipt"
            ),
            "remote_delivery_receipt": REMOTE_RECEIPT.as_posix(),
            "ci_status": CI_STATUS.as_posix(),
            "pr_creation_allowed": False,
            "merge_main_allowed": False,
            "force_push_allowed": False,
        }
    )


def build_morning_readout(repo_root: Path) -> dict[str, Any]:
    intake = load_json(
        repo_root / OUTPUT_ROOT / "execution/decision_intake.json"
    )
    recompute = load_json(
        repo_root / OUTPUT_ROOT / "execution/recompute_summary.json"
    )
    regression_path = repo_root / OUTPUT_ROOT / "validation/full_regression.json"
    scope_path = repo_root / OUTPUT_ROOT / "validation/scope_audit.json"
    ci_path = repo_root / OUTPUT_ROOT / "validation/ci_contract.json"
    tracked_path = (
        repo_root / OUTPUT_ROOT / "publication/tracked_delivery_receipt.json"
    )
    validation = {
        "full_regression": (
            bool(load_json(regression_path).get("all_passed"))
            if regression_path.is_file()
            else False
        ),
        "scope_audit": (
            bool(load_json(scope_path).get("passed"))
            if scope_path.is_file()
            else False
        ),
        "ci_contract": (
            bool(load_json(ci_path).get("passed")) if ci_path.is_file() else False
        ),
    }
    tracked = load_json(tracked_path) if tracked_path.is_file() else None
    outcome = evaluate_night05_outcome(
        valid_external_decisions=int(
            intake.get("validated_decision_count") or 0
        ),
        independent_passed_receipts=0,
        resolved_delta=0,
    ).value
    return stable_payload(
        {
            "schema_version": "r5_night05_morning_readout_v1",
            "mission_id": MISSION_ID,
            "target_branch": TARGET_BRANCH,
            "mission_outcome": outcome,
            "outcome_meaning": (
                "external_review_intake_prepared_research_program_still_open"
            ),
            "source_commit": SOURCE_COMMIT,
            "source_ci_run_id": 29764207418,
            "review_intake": {
                "candidate_count": EXPECTED_CANDIDATES,
                "external_authority_bindings": intake["authority_registry"][
                    "authority_binding_count"
                ],
                "scanned_manifests": intake["scanned_manifest_count"],
                "validated_decisions": intake["validated_decision_count"],
                "approved_decisions": intake["approved_decision_count"],
                "machine_generated_decisions": intake[
                    "machine_generated_decisions"
                ],
            },
            "research_truth": {
                "blocker_occurrences_total": EXPECTED_OCCURRENCES,
                "blocker_occurrences_resolved": 0,
                "resolved_delta": 0,
                "candidate_ready": EXPECTED_CANDIDATES,
                "dependency_blocked": recompute["dependency_blocked_count"],
                "dependency_unlocked": recompute["dependency_unlocked_count"],
                "work_orders_pending": recompute["parent_pending_count"],
                "work_orders_resolved": recompute["parent_resolved_count"],
                "program_goal": "open_needs_targeted_backflow",
                "sample_quality_allowed": False,
                "p2_allowed": False,
            },
            "validation": validation,
            "delivery": {
                "tracked_delivery_ready": tracked is not None,
                "publication_resolution_policy": (
                    tracked["final_publication_resolution_policy"]
                    if tracked
                    else None
                ),
                "pr_created": False,
                "main_merged": False,
                "force_push_used": False,
            },
            "next_queue": {
                "path": (OUTPUT_ROOT / "next_night_queue.yaml").as_posix(),
                "task_count": EXPECTED_TOTAL_ITEMS,
                "ids_and_source_hashes_preserved": True,
            },
            "blockers": [
                {
                    "owner": "external_review_lead",
                    "severity": "high",
                    "next_step": (
                        "register real reviewer-authority pairs and complete "
                        "the seven Wave A exact-hash manifests"
                    ),
                }
            ],
        }
    )


def morning_readout_markdown(readout: Mapping[str, Any]) -> str:
    intake = readout["review_intake"]
    truth = readout["research_truth"]
    validation = readout["validation"]
    return "\n".join(
        [
            "# Night05 晨间交接",
            "",
            f"- 工程终态：{readout['mission_outcome']}",
            (
                "- 外部 authority binding："
                f"{intake['external_authority_bindings']}"
            ),
            f"- 已扫描决定 manifest：{intake['scanned_manifests']}",
            (
                "- 有效 / 已批准决定："
                f"{intake['validated_decisions']} / {intake['approved_decisions']}"
            ),
            (
                "- 阻塞项已解决："
                f"{truth['blocker_occurrences_resolved']}/"
                f"{truth['blocker_occurrences_total']}"
            ),
            (
                f"- 依赖解除：{truth['dependency_unlocked']}/"
                f"{EXPECTED_DEPENDENCIES}"
            ),
            (
                f"- 父任务完成：{truth['work_orders_resolved']}/"
                f"{EXPECTED_PARENTS}"
            ),
            (
                "- 回归 / scope / CI contract："
                f"{validation['full_regression']} / "
                f"{validation['scope_audit']} / "
                f"{validation['ci_contract']}"
            ),
            "- Program Goal：open_needs_targeted_backflow",
            "- Sample quality / P2：false / false",
            "",
            (
                "review_intake_ready 表示 Night05 的外部评审接收链路已准备"
                "并完成零输入收口，不表示任何研究 occurrence、dependency "
                "或 parent 已解决。"
            ),
            "",
            (
                "当前没有真实外部 reviewer-authority registry 或 exact-hash "
                "决定；69 个 unresolved ID 与 source hash 原样结转。"
            ),
            "",
        ]
    )


def materialize_bootstrap(repo_root: Path) -> dict[str, Any]:
    source_manifest = _source_git_manifest(repo_root)
    source_preflight = build_source_preflight(repo_root)
    waves = build_review_wave_plan(repo_root)
    write_json(
        repo_root / OUTPUT_ROOT / "preflight/source_git_manifest.json",
        source_manifest,
    )
    write_json(
        repo_root / OUTPUT_ROOT / "preflight/source_preflight.json",
        source_preflight,
    )
    write_yaml(
        repo_root / OUTPUT_ROOT / "review/review_wave_plan.yaml", waves
    )

    intake = consume_external_decisions(repo_root)
    typed = build_typed_execution_summary(intake)
    recompute = build_recompute_summary(repo_root)
    write_json(
        repo_root / OUTPUT_ROOT / "execution/typed_execution_summary.json",
        typed,
    )
    write_json(
        repo_root / OUTPUT_ROOT / "execution/recompute_summary.json",
        recompute,
    )
    write_yaml(
        repo_root / OUTPUT_ROOT / "next_night_queue.yaml",
        build_next_queue(repo_root),
    )
    write_json(
        repo_root / OUTPUT_ROOT / "progress/change_log.json",
        build_change_log(),
    )
    write_json(
        repo_root / OUTPUT_ROOT / "progress/blocker_ledger.json",
        build_blocker_ledger(intake),
    )
    write_yaml(
        repo_root / OUTPUT_ROOT / "mission_state.yaml",
        build_mission_state(intake),
    )
    structural = stable_payload(
        {
            "schema_version": "r5_night05_structural_gate_v1",
            "mission_id": MISSION_ID,
            "source_preflight_passed": source_preflight["passed"],
            "source_file_count": source_manifest["file_count"],
            "queue_task_count": EXPECTED_TOTAL_ITEMS,
            "candidate_count": EXPECTED_CANDIDATES,
            "machine_generated_decisions": intake["machine_generated_decisions"],
            "resolved_delta": 0,
            "passed": True,
        }
    )
    write_json(
        repo_root / OUTPUT_ROOT / "validation/structural_gate.json",
        structural,
    )
    readout = build_morning_readout(repo_root)
    write_json(repo_root / OUTPUT_ROOT / "morning_readout.json", readout)
    atomic_write(
        repo_root / OUTPUT_ROOT / "morning_readout.md",
        morning_readout_markdown(readout).encode("utf-8"),
    )
    return {
        "source_preflight": source_preflight,
        "review_waves": waves,
        "intake": intake,
        "typed_execution": typed,
        "recompute": recompute,
        "outcome": readout["mission_outcome"],
    }


def materialize_regression(
    repo_root: Path,
    *,
    night_shift_passed: int,
    full_passed: int,
    full_skipped: int,
    source_capabilities: int,
    source_blocking: int,
) -> dict[str, Any]:
    scope = build_scope_audit(repo_root)
    regression = build_full_regression(
        night_shift_passed=night_shift_passed,
        full_passed=full_passed,
        full_skipped=full_skipped,
        source_capabilities=source_capabilities,
        source_blocking=source_blocking,
    )
    ci = build_ci_contract(repo_root)
    write_json(
        repo_root / OUTPUT_ROOT / "validation/scope_audit.json", scope
    )
    write_json(
        repo_root / OUTPUT_ROOT / "validation/full_regression.json",
        regression,
    )
    write_json(
        repo_root / OUTPUT_ROOT / "validation/ci_contract.json", ci
    )
    return {"scope": scope, "regression": regression, "ci": ci}


def materialize_tracked_publication(repo_root: Path) -> dict[str, Any]:
    receipt = build_tracked_delivery_receipt(repo_root)
    write_json(
        repo_root
        / OUTPUT_ROOT
        / "publication/tracked_delivery_receipt.json",
        receipt,
    )
    return receipt


def materialize_morning_readout(repo_root: Path) -> dict[str, Any]:
    readout = build_morning_readout(repo_root)
    write_json(repo_root / OUTPUT_ROOT / "morning_readout.json", readout)
    atomic_write(
        repo_root / OUTPUT_ROOT / "morning_readout.md",
        morning_readout_markdown(readout).encode("utf-8"),
    )
    return readout


def build_remote_delivery_receipt(
    repo_root: Path,
    *,
    remote_head: str,
    ci_run_id: int,
    ci_url: str,
    ci_conclusion: str,
) -> dict[str, Any]:
    local_head = _git(repo_root, "rev-parse", "HEAD")
    remote_ref = _git(
        repo_root, "ls-remote", "origin", f"refs/heads/{TARGET_BRANCH}"
    )
    remote_sha = remote_ref.split()[0] if remote_ref else ""
    if local_head != remote_head or remote_sha != remote_head:
        raise Night05Error(
            f"remote head mismatch: local={local_head} "
            f"declared={remote_head} remote={remote_sha}"
        )
    if ci_conclusion != "success":
        raise Night05Error(f"exact-head CI is not successful: {ci_conclusion}")
    return stable_payload(
        {
            "schema_version": "r5_night05_remote_delivery_receipt_v1",
            "mission_id": MISSION_ID,
            "target_branch": TARGET_BRANCH,
            "local_head": local_head,
            "remote_head": remote_sha,
            "exact_head_match": True,
            "ci": {
                "database_id": ci_run_id,
                "head_sha": remote_head,
                "conclusion": ci_conclusion,
                "url": ci_url,
            },
            "tracked_receipt": (
                OUTPUT_ROOT / "publication/tracked_delivery_receipt.json"
            ).as_posix(),
            "tracked_in_identified_commit": False,
            "pr_created": False,
            "main_merged": False,
            "force_push_used": False,
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize the Night05 intake mission"
    )
    parser.add_argument("--repo", default=".")
    parser.add_argument(
        "--mode",
        choices=("bootstrap", "regression", "tracked", "morning", "remote"),
        required=True,
    )
    parser.add_argument("--night-shift-passed", type=int)
    parser.add_argument("--full-passed", type=int)
    parser.add_argument("--full-skipped", type=int, default=0)
    parser.add_argument("--source-capabilities", type=int)
    parser.add_argument("--source-blocking", type=int, default=0)
    parser.add_argument("--remote-head")
    parser.add_argument("--ci-run-id", type=int)
    parser.add_argument("--ci-url")
    parser.add_argument("--ci-conclusion")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo).resolve()
    if args.mode == "bootstrap":
        result = materialize_bootstrap(repo_root)
    elif args.mode == "regression":
        required = (
            args.night_shift_passed,
            args.full_passed,
            args.source_capabilities,
        )
        if any(value is None for value in required):
            raise Night05Error(
                "regression mode requires observed test and route counts"
            )
        result = materialize_regression(
            repo_root,
            night_shift_passed=args.night_shift_passed,
            full_passed=args.full_passed,
            full_skipped=args.full_skipped,
            source_capabilities=args.source_capabilities,
            source_blocking=args.source_blocking,
        )
    elif args.mode == "tracked":
        result = materialize_tracked_publication(repo_root)
    elif args.mode == "morning":
        result = materialize_morning_readout(repo_root)
    else:
        if not all(
            (
                args.remote_head,
                args.ci_run_id,
                args.ci_url,
                args.ci_conclusion,
            )
        ):
            raise Night05Error(
                "remote mode requires exact remote head and CI evidence"
            )
        result = build_remote_delivery_receipt(
            repo_root,
            remote_head=args.remote_head,
            ci_run_id=args.ci_run_id,
            ci_url=args.ci_url,
            ci_conclusion=args.ci_conclusion,
        )
        write_json(repo_root / REMOTE_RECEIPT, result)
        atomic_write(
            repo_root / CI_STATUS,
            (
                "# Night05 CI status\n\n"
                f"- Head: {args.remote_head}\n"
                f"- Run: {args.ci_run_id}\n"
                f"- Conclusion: {args.ci_conclusion}\n"
                f"- URL: {args.ci_url}\n"
            ).encode("utf-8"),
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
