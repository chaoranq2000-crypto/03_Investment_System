"""Lossless, deterministic BF2 work-order and blocker seed adapter."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

import yaml

from .models import ContractError, QueueDocument, Task
from .queue import atomic_write, queue_bytes, save_queue
from .receipts import canonical_json_bytes, sha256_bytes, sha256_file


INPUT_MANIFEST_SCHEMA = "r5_night_shift_input_manifest_v1"
INVENTORY_SCHEMA = "r5_night_shift_bf2_inventory_v1"
SEED_RECEIPT_SCHEMA = "r5_night_shift_bf2_seed_receipt_v1"
GLOBAL_CASE_ID = "__suite__"
SOURCE_PATH_PATTERN = re.compile(r"\s+in\s+(?P<path>[^:]+):\s+actual=")

WORK_ORDERS_PATH = (
    "reports/p1_6/r5_bundle17r_bf2/source_bf1/run_a/"
    "R5_bundle17r_backflow_work_orders.csv"
)
ISSUE_LEDGER_PATH = (
    "reports/p1_6/r5_bundle17r_bf2/source_bf1/run_a/"
    "R5_bundle17r_backflow_issue_ledger.csv"
)
CASE_MATRIX_PATH = (
    "reports/p1_6/r5_bundle17r_bf2/source_bf1/run_a/"
    "R5_bundle17r_backflow_case_matrix.csv"
)
GENERATION_LOCK_PATH = (
    "reports/p1_6/r5_bundle17r_bf2/source_bf1/run_a/"
    "R5_bundle17r_backflow_generation_lock.json"
)
HANDOFF_DIR = "reports/p1_6/r5_bundle17r_bf2/source_bf1/run_a/work_order_handoffs"
RESULT_DIR = ".local/r5_bundle17r_backflow_results_fixed_run_a"
VERIFIED_RECEIPTS_PATH = (
    "reports/p1_6/r5_bundle17r_bf2/run_verified_c/"
    "R5_bundle17r_bf2_execution_receipts.json"
)
VERIFIED_STATUS_PATH = (
    "reports/p1_6/r5_bundle17r_bf2/run_verified_c/"
    "R5_bundle17r_bf2_status_proposal.yaml"
)
VERIFIED_VALIDATION_PATH = (
    "reports/p1_6/r5_bundle17r_bf2/run_verified_c/"
    "R5_bundle17r_bf2_validation_report.json"
)
VERIFIED_REJECTED_PATH = (
    "reports/p1_6/r5_bundle17r_bf2/run_verified_c/"
    "R5_bundle17r_bf2_rejected_artifacts.csv"
)

GLOBAL_FORBIDDEN_PATHS = (
    "main",
    "data/raw/**",
    "reports/p1_6/R5_READOUT_CANONICAL_INDEX.md",
    "config/r5_readout_canonical_index.yaml",
    ".local/** (git tracked)",
    "reports/p1_6/r5_bundle17r_bf2* (git tracked)",
)


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"BF2 input[{path}]: cannot read JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"BF2 input[{path}]: JSON root must be an object")
    return value


def _yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ContractError(f"BF2 input[{path}]: cannot read YAML: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"BF2 input[{path}]: YAML root must be an object")
    return value


def _csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ContractError(f"BF2 input[{path}]: CSV has no header")
            rows = [
                {str(key): str(value or "").strip() for key, value in row.items()}
                for row in reader
            ]
    except OSError as exc:
        raise ContractError(f"BF2 input[{path}]: cannot read CSV: {exc}") from exc
    return [str(item) for item in reader.fieldnames], rows


def _split(value: Any, separator: str = "|") -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value or "").split(separator) if item.strip()]


def normalize_case_id(value: Any) -> str:
    text = str(value or "").strip()
    return GLOBAL_CASE_ID if text.casefold() in {"", "suite", GLOBAL_CASE_ID} else text


def row_sha256(row: Mapping[str, Any]) -> str:
    normalized = {str(key).strip(): str(value or "").strip() for key, value in row.items()}
    return sha256_bytes(canonical_json_bytes(normalized))


def compute_input_set_sha(records: Sequence[Mapping[str, Any]]) -> str:
    portable = [
        {
            "logical_path": str(item["logical_path"]),
            "sha256": str(item["sha256"]),
            "size_bytes": int(item["size_bytes"]),
        }
        for item in records
    ]
    portable.sort(key=lambda item: item["logical_path"])
    return hashlib.sha256(canonical_json_bytes(portable)).hexdigest()


def verify_input_manifest(
    manifest_path: Path, repo_root: Path
) -> tuple[dict[str, Any], dict[str, Path]]:
    manifest = _json(manifest_path)
    if manifest.get("schema_version") != INPUT_MANIFEST_SCHEMA:
        raise ContractError(
            f"input manifest schema mismatch: {manifest.get('schema_version')!r}"
        )
    records = manifest.get("files")
    if not isinstance(records, list) or not records:
        raise ContractError("input manifest files must be a non-empty array")
    if manifest.get("file_count") != len(records):
        raise ContractError("input manifest file_count does not match files")
    expected_set = str(manifest.get("input_set_sha256") or "")
    actual_set = compute_input_set_sha(records)
    if expected_set != actual_set:
        raise ContractError(
            f"input-set hash mismatch: expected {expected_set}, calculated {actual_set}"
        )
    paths: dict[str, Path] = {}
    root = repo_root.resolve()
    for index, item in enumerate(records):
        if not isinstance(item, dict):
            raise ContractError(f"input manifest files[{index}] must be an object")
        logical = PurePosixPath(str(item.get("logical_path") or ""))
        destination = PurePosixPath(str(item.get("destination_relative_path") or ""))
        if not logical.as_posix() or logical.is_absolute() or ".." in logical.parts:
            raise ContractError(f"unsafe logical input path: {logical}")
        if not destination.as_posix() or destination.is_absolute() or ".." in destination.parts:
            raise ContractError(f"unsafe destination input path: {destination}")
        path = (root / destination).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ContractError(f"input destination escapes repository: {destination}") from exc
        if not path.is_file() or path.is_symlink():
            raise ContractError(f"immutable BF2 input is missing or not regular: {logical}")
        actual_hash = sha256_file(path)
        expected_hash = str(item.get("sha256") or "")
        if actual_hash != expected_hash:
            raise ContractError(
                f"immutable BF2 input hash mismatch for {logical}: "
                f"expected {expected_hash}, got {actual_hash}"
            )
        if path.stat().st_size != int(item.get("size_bytes", -1)):
            raise ContractError(f"immutable BF2 input size mismatch for {logical}")
        paths[logical.as_posix()] = path
    return manifest, paths


def _locked_hashes(lock: Mapping[str, Any]) -> dict[str, str]:
    output = lock.get("output_artifacts")
    if not isinstance(output, Mapping):
        raise ContractError("BF1 generation lock output_artifacts must be an object")
    hashes: dict[str, str] = {}
    for name, record in output.items():
        if isinstance(record, Mapping) and record.get("sha256"):
            hashes[str(name)] = str(record["sha256"])
    return hashes


def _verify_bf1_lock(paths: Mapping[str, Path], lock: Mapping[str, Any]) -> None:
    locked = _locked_hashes(lock)
    for logical in (WORK_ORDERS_PATH, ISSUE_LEDGER_PATH, CASE_MATRIX_PATH):
        basename = PurePosixPath(logical).name
        expected = locked.get(basename)
        if expected is None:
            raise ContractError(f"BF1 generation lock does not cover {basename}")
        actual = sha256_file(paths[logical])
        if expected != actual:
            raise ContractError(
                f"BF1 generation lock mismatch for {basename}: expected {expected}, got {actual}"
            )


def classify_occurrence(issue: Mapping[str, str]) -> str:
    code = str(issue.get("code") or "").strip()
    field = str(issue.get("field") or "").casefold()
    if code == "ASSERTION_POINTER_UNRESOLVED":
        return "engineering_local"
    if any(token in field for token in ("evidence_complete", "official_sources_present")):
        return "evidence_required"
    if "suite_hash_bound" in field:
        return "human_gate"
    if any(
        token in field
        for token in (
            "blockers_zero",
            "packs_materialized",
            "packs_complete",
            "fully_mapped",
            "candidate_ready_count",
            "bundle14_ready",
            "research_ready_count",
            "regression_candidate_ready",
            "regression_research_ready",
            "qualification_deterministic_rerun",
        )
    ):
        return "dependency_blocked"
    return "analysis_required"


def _source_artifact(message: str, repo_root: Path) -> tuple[str | None, str | None]:
    match = SOURCE_PATH_PATTERN.search(message)
    if not match:
        return None, None
    relative = match.group("path").replace("\\", "/").strip()
    path = (repo_root / PurePosixPath(relative)).resolve()
    root = repo_root.resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return relative, None
    if not path.is_file() or path.is_symlink():
        return relative, None
    return relative, sha256_file(path)


def build_inventory(
    manifest_path: Path,
    repo_root: Path,
    *,
    expected_work_orders: int = 6,
    expected_blockers: int = 63,
) -> dict[str, Any]:
    manifest, paths = verify_input_manifest(manifest_path, repo_root)
    required = {
        WORK_ORDERS_PATH,
        ISSUE_LEDGER_PATH,
        CASE_MATRIX_PATH,
        GENERATION_LOCK_PATH,
        VERIFIED_RECEIPTS_PATH,
        VERIFIED_STATUS_PATH,
        VERIFIED_VALIDATION_PATH,
        VERIFIED_REJECTED_PATH,
    }
    missing = sorted(required - set(paths))
    if missing:
        raise ContractError(f"input set is missing required BF2 files: {', '.join(missing)}")

    _, work_orders = _csv(paths[WORK_ORDERS_PATH])
    _, issues = _csv(paths[ISSUE_LEDGER_PATH])
    _, cases = _csv(paths[CASE_MATRIX_PATH])
    generation_lock = _json(paths[GENERATION_LOCK_PATH])
    _verify_bf1_lock(paths, generation_lock)
    if len(work_orders) != expected_work_orders:
        raise ContractError(
            f"BF2 work-order count mismatch: expected {expected_work_orders}, got {len(work_orders)}"
        )
    if len(issues) != expected_blockers:
        raise ContractError(
            f"BF2 blocker occurrence count mismatch: expected {expected_blockers}, got {len(issues)}"
        )

    issue_by_id: dict[str, dict[str, str]] = {}
    for row in issues:
        issue_id = row.get("issue_id", "")
        if not issue_id:
            raise ContractError("every BF2 issue row must have issue_id")
        if issue_id in issue_by_id:
            raise ContractError(f"duplicate BF2 blocker occurrence: {issue_id}")
        issue_by_id[issue_id] = row

    handoffs: dict[str, dict[str, Any]] = {}
    results: dict[str, dict[str, Any]] = {}
    for logical, path in paths.items():
        if logical.startswith(HANDOFF_DIR + "/") and logical.endswith(".yaml"):
            handoff = _yaml(path)
            work_order = handoff.get("work_order")
            if not isinstance(work_order, Mapping) or not work_order.get("work_order_id"):
                raise ContractError(f"invalid BF2 handoff: {logical}")
            handoffs[str(work_order["work_order_id"])] = handoff
        if logical.startswith(RESULT_DIR + "/") and logical.endswith("/result.yaml"):
            result = _yaml(path)
            work_order_id = str(result.get("work_order_id") or "")
            if not work_order_id or work_order_id in results:
                raise ContractError(f"invalid or duplicate BF2 result: {logical}")
            results[work_order_id] = result

    order_ids = [row.get("work_order_id", "") for row in work_orders]
    if not all(order_ids) or len(order_ids) != len(set(order_ids)):
        raise ContractError("BF2 work-order IDs are missing or duplicated")
    if set(handoffs) != set(order_ids):
        raise ContractError("BF2 handoff IDs do not exactly match work orders")
    orphan_results = sorted(set(results) - set(order_ids))
    missing_results = sorted(set(order_ids) - set(results))
    if orphan_results or missing_results:
        raise ContractError(
            f"BF2 result identity mismatch: orphan={orphan_results}, missing={missing_results}"
        )

    issue_to_order: dict[str, str] = {}
    normalized_orders: list[dict[str, Any]] = []
    suite_work_orders: list[str] = []
    source_generation_id = str(generation_lock.get("generation_id") or "")
    for row in work_orders:
        work_order_id = row["work_order_id"]
        issue_ids = _split(row.get("issue_ids"))
        for issue_id in issue_ids:
            if issue_id not in issue_by_id:
                raise ContractError(
                    f"work order {work_order_id} references unknown occurrence {issue_id}"
                )
            if issue_id in issue_to_order:
                raise ContractError(
                    f"occurrence {issue_id} belongs to multiple work orders"
                )
            issue_to_order[issue_id] = work_order_id
        source_case_id = row.get("case_id", "")
        case_id = normalize_case_id(source_case_id)
        if case_id == GLOBAL_CASE_ID:
            suite_work_orders.append(work_order_id)
        handoff = handoffs[work_order_id]
        handoff_generation = str(handoff.get("source_activation_generation_id") or "")
        if handoff_generation and source_generation_id and handoff_generation != str(
            generation_lock.get("source_activation_generation_id") or ""
        ):
            raise ContractError(f"source activation generation mismatch for {work_order_id}")
        result = results[work_order_id]
        if normalize_case_id(result.get("case_id")) != case_id:
            raise ContractError(f"suite/case identity mismatch for result {work_order_id}")
        if result.get("source_work_order_sha256") != row_sha256(row):
            raise ContractError(f"source work-order hash mismatch for result {work_order_id}")
        normalized_orders.append(
            {
                "work_order_id": work_order_id,
                "source_case_id": source_case_id,
                "case_id": case_id,
                "route_id": row.get("route_id", ""),
                "batch_id": row.get("batch_id", ""),
                "owner_skill": row.get("owner_skill", ""),
                "target_stage": row.get("target_stage", ""),
                "source_priority": int(row.get("priority") or 0),
                "issue_ids": issue_ids,
                "issue_count": len(issue_ids),
                "requested_actions": _split(row.get("requested_actions"), "||"),
                "required_outputs": _split(row.get("required_outputs")),
                "acceptance_checks": _split(row.get("acceptance_checks")),
                "depends_on": _split(row.get("depends_on")),
                "execution_status": row.get("execution_status", ""),
                "result_status": str(result.get("execution_status") or ""),
                "resolved_blocker_ids": list(result.get("resolved_blocker_ids") or []),
                "source_work_order_sha256": row_sha256(row),
                "source_generation_id": source_generation_id,
                "allowed_paths": [],
                "allowed_paths_status": "MISSING_IN_SOURCE_CONTRACT",
            }
        )
    if set(issue_by_id) != set(issue_to_order):
        unassigned = sorted(set(issue_by_id) - set(issue_to_order))
        raise ContractError(f"BF2 occurrences are not assigned to work orders: {unassigned}")

    normalized_issues: list[dict[str, Any]] = []
    classification_counts: Counter[str] = Counter()
    for issue_id in sorted(issue_by_id):
        row = issue_by_id[issue_id]
        category = classify_occurrence(row)
        classification_counts[category] += 1
        source_path, source_hash = _source_artifact(row.get("message", ""), repo_root)
        normalized_issues.append(
            {
                "blocker_occurrence_id": issue_id,
                "work_order_id": issue_to_order[issue_id],
                "case_id": normalize_case_id(row.get("case_id")),
                "blocker_code": row.get("code", ""),
                "owner_step": row.get("stage", ""),
                "field": row.get("field", ""),
                "source_owner_skill": row.get("source_owner_skill", ""),
                "source_target_stage": row.get("source_target_stage", ""),
                "message": row.get("message", ""),
                "requested_action": row.get("requested_action", ""),
                "route_id": row.get("route_id", ""),
                "batch_id": row.get("batch_id", ""),
                "owner_skill": row.get("owner_skill", ""),
                "target_stage": row.get("target_stage", ""),
                "severity": "UNVERIFIED_NOT_DECLARED",
                "classification": category,
                "classification_is_resolution": False,
                "source_artifact_path": source_path,
                "source_artifact_sha256": source_hash,
                "source_generation_id": source_generation_id,
                "source_generation_lock_sha256": sha256_file(paths[GENERATION_LOCK_PATH]),
                "resolved": False,
            }
        )

    verified_receipts = _json(paths[VERIFIED_RECEIPTS_PATH])
    verified_status = _yaml(paths[VERIFIED_STATUS_PATH])
    verified_validation = _json(paths[VERIFIED_VALIDATION_PATH])
    _, rejected_rows = _csv(paths[VERIFIED_REJECTED_PATH])
    failed_results = sum(
        str(item.get("result_status") or "").casefold() in {"failed", "rejected", "error"}
        for item in normalized_orders
    )
    resolved_ids = {
        item
        for order in normalized_orders
        for item in order["resolved_blocker_ids"]
    }
    expected_truth = {
        "work_orders_total": expected_work_orders,
        "work_orders_pending": expected_work_orders,
        "blocker_occurrences_total": expected_blockers,
        "blocker_occurrences_resolved": 0,
        "failed_results": 0,
        "orphan_results": 0,
        "rejected_artifacts": 0,
    }
    actual_truth = {
        "work_orders_total": len(normalized_orders),
        "work_orders_pending": sum(
            str(item["result_status"]).casefold() == "pending" for item in normalized_orders
        ),
        "blocker_occurrences_total": len(normalized_issues),
        "blocker_occurrences_resolved": len(resolved_ids),
        "failed_results": failed_results,
        "orphan_results": len(orphan_results),
        "rejected_artifacts": len(rejected_rows),
    }
    if actual_truth != expected_truth:
        raise ContractError(
            f"BF2 input truth mismatch: expected {expected_truth}, got {actual_truth}"
        )
    receipt_summary = verified_receipts.get("summary")
    if not isinstance(receipt_summary, Mapping) or int(receipt_summary.get("pending_count", -1)) != 6:
        raise ContractError("verified BF2 receipts do not preserve six pending work orders")
    if int(verified_status.get("resolved_blocker_occurrence_count", -1)) != 0:
        raise ContractError("verified BF2 status does not preserve zero resolved blockers")
    if int(verified_validation.get("orphan_result_count", -1)) != 0:
        raise ContractError("verified BF2 validation reports orphan results")
    if int(verified_validation.get("rejected_artifact_count", -1)) != 0:
        raise ContractError("verified BF2 validation reports rejected artifacts")
    if len(suite_work_orders) != 2:
        raise ContractError(
            f"expected two suite work orders, found {len(suite_work_orders)}"
        )

    inventory: dict[str, Any] = {
        "schema_version": INVENTORY_SCHEMA,
        "input_set_sha256": manifest["input_set_sha256"],
        "source_commit": manifest["source_commit"],
        "research_gate": "needs_targeted_backflow",
        "summary": actual_truth,
        "classification_counts": dict(sorted(classification_counts.items())),
        "source_generation": {
            "generation_id": source_generation_id,
            "source_activation_generation_id": generation_lock.get(
                "source_activation_generation_id"
            ),
            "schema_version": generation_lock.get("schema_version"),
            "generation_lock_path": GENERATION_LOCK_PATH,
            "generation_lock_sha256": sha256_file(paths[GENERATION_LOCK_PATH]),
        },
        "suite_compatibility": {
            "canonical_case_id": GLOBAL_CASE_ID,
            "source_aliases_accepted": ["", "suite", GLOBAL_CASE_ID],
            "suite_work_order_ids": sorted(suite_work_orders),
            "fixed_results_use_canonical_case_id": all(
                str(results[item].get("case_id")) == GLOBAL_CASE_ID
                for item in suite_work_orders
            ),
            "accepted": True,
        },
        "generation_lock_compatibility": {
            "bf1_output_artifact_mapping_accepted": True,
            "covered_inputs": [WORK_ORDERS_PATH, ISSUE_LEDGER_PATH, CASE_MATRIX_PATH],
        },
        "work_orders": sorted(normalized_orders, key=lambda item: item["work_order_id"]),
        "blocker_occurrences": normalized_issues,
        "release_boundaries": {
            "canonical_workflow_state_mutation_allowed": False,
            "sample_quality_allowed": False,
            "p2_allowed": False,
        },
    }
    inventory["inventory_sha256"] = sha256_bytes(canonical_json_bytes(inventory))
    return inventory


def _occurrence_task_status(category: str) -> str:
    if category == "evidence_required":
        return "evidence_required"
    if category == "human_gate":
        return "human_gate"
    return "dependency_blocked"


def _safe_id(prefix: str, identifier: str) -> str:
    suffix = re.sub(r"[^a-z0-9]+", "_", identifier.casefold()).strip("_")
    return f"{prefix}_{suffix}"


def build_seed_queue(inventory: Mapping[str, Any]) -> QueueDocument:
    blockers = inventory.get("blocker_occurrences")
    work_orders = inventory.get("work_orders")
    if not isinstance(blockers, list) or not isinstance(work_orders, list):
        raise ContractError("BF2 inventory must contain work_orders and blocker_occurrences arrays")
    occurrence_task_ids: dict[str, str] = {}
    tasks: list[Task] = []
    for blocker in sorted(blockers, key=lambda item: str(item["blocker_occurrence_id"])):
        occurrence_id = str(blocker["blocker_occurrence_id"])
        task_id = _safe_id("ns01_t50_bf2_occ", occurrence_id)
        occurrence_task_ids[occurrence_id] = task_id
        category = str(blocker["classification"])
        source_path = blocker.get("source_artifact_path") or "UNKNOWN"
        source_hash = blocker.get("source_artifact_sha256") or "UNKNOWN"
        tasks.append(
            Task(
                id=task_id,
                title=f"BF2 occurrence {occurrence_id}",
                priority=60,
                status=_occurrence_task_status(category),
                depends_on=(),
                work_type=category,
                goal=str(blocker.get("message") or blocker.get("requested_action") or occurrence_id),
                allowed_paths=(),
                forbidden_paths=GLOBAL_FORBIDDEN_PATHS,
                acceptance_commands=(),
                required_artifacts=(),
                retry_limit=0,
                on_success={},
                on_failure={"emit_failure_packet": True},
                human_gate=category == "human_gate",
                notes=(
                    f"work_order_id={blocker['work_order_id']}",
                    f"classification={category}",
                    "classification_is_resolution=false",
                    "allowed_paths_status=MISSING_IN_SOURCE_CONTRACT",
                    f"source_artifact_path={source_path}",
                    f"source_artifact_sha256={source_hash}",
                    f"requested_action={blocker.get('requested_action') or 'UNKNOWN'}",
                ),
            )
        )

    parent_ids = {
        str(order["work_order_id"]): _safe_id(
            "ns01_t50_bf2_wo", str(order["work_order_id"])
        )
        for order in work_orders
    }
    for order in sorted(work_orders, key=lambda item: str(item["work_order_id"])):
        occurrence_dependencies = [
            occurrence_task_ids[item] for item in order.get("issue_ids", [])
        ]
        parent_dependencies = [
            parent_ids[item] for item in order.get("depends_on", [])
        ]
        dependencies = tuple(sorted(set(occurrence_dependencies + parent_dependencies)))
        notes = [
            f"source_work_order_id={order['work_order_id']}",
            f"case_id={order['case_id']}",
            f"route_id={order.get('route_id') or 'UNKNOWN'}",
            f"source_generation_id={order.get('source_generation_id') or 'UNKNOWN'}",
            f"source_priority={order.get('source_priority')}",
            "allowed_paths_status=MISSING_IN_SOURCE_CONTRACT",
            "classification_is_resolution=false",
        ]
        notes.extend(
            f"acceptance_check={item}" for item in order.get("acceptance_checks", [])
        )
        tasks.append(
            Task(
                id=parent_ids[str(order["work_order_id"])],
                title=f"BF2 work order {order['work_order_id']}",
                priority=min(100, int(order.get("source_priority") or 0)),
                status="pending",
                depends_on=dependencies,
                work_type="bf2_work_order",
                goal=" || ".join(order.get("requested_actions", []))
                or f"Complete {order['work_order_id']} without changing research truth",
                allowed_paths=(),
                forbidden_paths=GLOBAL_FORBIDDEN_PATHS,
                acceptance_commands=(),
                required_artifacts=(),
                retry_limit=0,
                on_success={},
                on_failure={"emit_failure_packet": True},
                human_gate=False,
                notes=tuple(notes),
            )
        )

    payload = {
        "schema_version": "r5_night_shift_queue_v1",
        "mission_id": (
            "r5_overnight_01_bf2_seed_" + str(inventory["input_set_sha256"])[:12]
        ),
        "baseline": {
            "source_commit": inventory["source_commit"],
            "input_set_sha256": inventory["input_set_sha256"],
            "research_gate": "needs_targeted_backflow",
            "bf2_work_orders_total": 6,
            "blocker_occurrences_total": 63,
            "blocker_occurrences_resolved": 0,
            "sample_quality_allowed": False,
            "p2_allowed": False,
            "canonical_state_allowed": False,
        },
        "run_window": {
            "timezone": "Europe/London",
            "start_at": "23:00",
            "stop_claiming_at": "06:15",
            "final_readout_at": "06:30",
        },
        "task_selection": {
            "order": ["priority_desc", "dependency_ready", "task_id_asc"],
            "single_integrator": True,
            "max_parallel_shared_state_writers": 1,
        },
        "tasks": [task.to_mapping() for task in sorted(tasks, key=lambda item: item.id)],
    }
    return QueueDocument.from_mapping(payload, path="seeded_queue")


def _write_json(path: Path, value: Any) -> None:
    atomic_write(
        path,
        (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
            "utf-8"
        ),
    )


def write_inventory_reports(
    inventory: Mapping[str, Any],
    *,
    compatibility_output: Path,
    summary_output: Path,
) -> None:
    summary = inventory["summary"]
    suite = inventory["suite_compatibility"]
    generation = inventory["source_generation"]
    classification = inventory["classification_counts"]
    compatibility_lines = [
        "# BF2 compatibility map",
        "",
        f"- Input set: `{inventory['input_set_sha256']}`",
        f"- Source generation: `{generation.get('generation_id') or 'UNKNOWN'}`",
        f"- Generation lock: `{generation['generation_lock_sha256']}`",
        f"- Work orders: `{summary['work_orders_total']}`",
        f"- Blocker occurrences: `{summary['blocker_occurrences_total']}`",
        f"- Resolved occurrences: `{summary['blocker_occurrences_resolved']}`",
        f"- Canonical suite case: `{suite['canonical_case_id']}`",
        f"- Suite work orders: `{', '.join(suite['suite_work_order_ids'])}`",
        "- BF1 generation-lock mapping: `accepted`",
        "- Missing allowed paths: preserved as `MISSING_IN_SOURCE_CONTRACT`",
        "- Canonical/sample-quality/P2 mutation: `false`",
        "",
    ]
    atomic_write(compatibility_output, "\n".join(compatibility_lines).encode("utf-8"))
    summary_lines = [
        "# BF2 night-shift seed summary",
        "",
        f"- Input set: `{inventory['input_set_sha256']}`",
        f"- Work orders: `{summary['work_orders_pending']}` pending / `{summary['work_orders_total']}` total",
        f"- Blocker occurrences: `{summary['blocker_occurrences_resolved']}` resolved / `{summary['blocker_occurrences_total']}` total",
        f"- Failed results: `{summary['failed_results']}`",
        f"- Orphan results: `{summary['orphan_results']}`",
        f"- Rejected artifacts: `{summary['rejected_artifacts']}`",
        "",
        "## Classification (not resolution)",
        "",
    ]
    for name, count in sorted(classification.items()):
        summary_lines.append(f"- `{name}`: `{count}`")
    summary_lines.extend(
        [
            "",
            "No classification, split, or import changed the true resolved count.",
            "Research gate remains `needs_targeted_backflow`; sample quality and P2 remain closed.",
            "",
        ]
    )
    atomic_write(summary_output, "\n".join(summary_lines).encode("utf-8"))


def seed_bf2(
    *,
    manifest_path: Path,
    repo_root: Path,
    output_path: Path,
    inventory_output: Path,
    receipt_output: Path,
    summary_output: Path,
    compatibility_output: Path,
    expected_work_orders: int = 6,
    expected_blockers: int = 63,
    assert_idempotent: bool = False,
) -> dict[str, Any]:
    first_inventory = build_inventory(
        manifest_path,
        repo_root,
        expected_work_orders=expected_work_orders,
        expected_blockers=expected_blockers,
    )
    first_queue = build_seed_queue(first_inventory)
    first_bytes = queue_bytes(first_queue)
    if assert_idempotent:
        second_inventory = build_inventory(
            manifest_path,
            repo_root,
            expected_work_orders=expected_work_orders,
            expected_blockers=expected_blockers,
        )
        second_bytes = queue_bytes(build_seed_queue(second_inventory))
        if canonical_json_bytes(first_inventory) != canonical_json_bytes(second_inventory):
            raise ContractError("BF2 inventory double run is not byte-for-byte deterministic")
        if first_bytes != second_bytes:
            raise ContractError("BF2 seed double run is not byte-for-byte deterministic")
    _write_json(inventory_output, first_inventory)
    save_queue(output_path, first_queue)
    write_inventory_reports(
        first_inventory,
        compatibility_output=compatibility_output,
        summary_output=summary_output,
    )
    safe_pilot_candidates = [
        task.id
        for task in first_queue.tasks
        if task.work_type == "engineering_local"
        and task.allowed_paths
        and task.acceptance_commands
        and task.status in {"pending", "ready"}
    ]
    receipt: dict[str, Any] = {
        "schema_version": SEED_RECEIPT_SCHEMA,
        "input_set_sha256": first_inventory["input_set_sha256"],
        "inventory_sha256": sha256_file(inventory_output),
        "seeded_queue_sha256": sha256_file(output_path),
        "work_orders_total": expected_work_orders,
        "work_orders_pending": expected_work_orders,
        "blocker_occurrences_total": expected_blockers,
        "blocker_occurrences_resolved": 0,
        "seeded_task_count": len(first_queue.tasks),
        "safe_pilot_candidates": safe_pilot_candidates,
        "idempotency": "byte_for_byte_equal" if assert_idempotent else "not_checked",
        "research_gate": "needs_targeted_backflow",
        "sample_quality_allowed": False,
        "p2_allowed": False,
        "canonical_state_allowed": False,
    }
    receipt["stable_receipt_sha256"] = sha256_bytes(canonical_json_bytes(receipt))
    _write_json(receipt_output, receipt)
    return receipt
