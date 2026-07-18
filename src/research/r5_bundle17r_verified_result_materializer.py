"""Verified result-package materializer for R5 Bundle 17R-BF2.

BF2 intentionally accepts local work-order result manifests but does not execute arbitrary
commands.  This companion stage closes the operator gap without weakening that boundary: it binds
BF1 work orders and blocker occurrences, requires hash-backed evidence for every passed acceptance
check, enforces dependency order, and emits deterministic BF2-compatible result packages.

The module never mutates the canonical workflow state, never grants sample quality or P2, and never
copies a repository candidate into the repository.  Local source files are copied only into the
configured BF2 dropzone; repository sources remain referenced in place.
"""

from __future__ import annotations

import argparse
import csv
import fnmatch
import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

import yaml

SCHEMA_VERSION = "r5_bundle17r_bf2_ex1_materialization_v1"
RESULT_SCHEMA_VERSION = "r5_bundle17r_work_order_result_v1"
SPEC_SCHEMA_VERSION = "r5_bundle17r_bf2_ex1_work_order_spec_v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PASSED = {"passed", "complete", "completed", "engineering_pass"}
FAILED = {"failed", "rejected", "error"}
PENDING = {"pending", "manual_pending", "needs_manual_route"}


class VerifiedResultError(ValueError):
    """Raised when a result claim cannot be materialized safely."""


@dataclass(frozen=True)
class WorkOrder:
    row: Mapping[str, str]
    work_order_id: str
    case_id: str
    route_id: str
    issue_ids: tuple[str, ...]
    acceptance_checks: tuple[str, ...]
    depends_on: tuple[str, ...]
    source_row_sha256: str


@dataclass
class MaterializedResult:
    work_order: WorkOrder
    declared_status: str
    effective_status: str
    result_path: str = ""
    result_sha256: str = ""
    resolved_blocker_ids: list[str] = field(default_factory=list)
    check_count: int = 0
    artifact_count: int = 0
    validation_errors: list[str] = field(default_factory=list)
    source_spec_path: str = ""
    source_spec_sha256: str = ""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_object(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_row(row: Mapping[str, Any]) -> dict[str, str]:
    return {str(key).strip(): str(value or "").strip() for key, value in row.items()}


def row_sha256(row: Mapping[str, Any]) -> str:
    """Use BF2's exact canonical row function when available."""

    try:
        from src.research.r5_bundle17r_backflow_execution import row_sha256 as bf2_row_sha256
    except (ImportError, AttributeError):
        return sha256_object(normalize_row(row))
    return str(bf2_row_sha256(row))


def normalize_relpath(value: str) -> str:
    text = str(value or "").replace("\\", "/").strip()
    path = PurePosixPath(text)
    if not text or path.is_absolute():
        raise VerifiedResultError(f"unsafe relative path: {value!r}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise VerifiedResultError(f"unsafe relative path: {value!r}")
    return path.as_posix()


def resolve_under(root: Path, value: str, *, must_exist: bool = False) -> Path:
    normalized = normalize_relpath(value)
    resolved_root = root.resolve()
    candidate = (resolved_root / normalized).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise VerifiedResultError(f"path escapes root: {value!r}") from exc
    if must_exist and not candidate.exists():
        raise VerifiedResultError(f"required path does not exist: {value}")
    if candidate.exists():
        cursor = candidate
        while cursor != resolved_root:
            if cursor.is_symlink():
                raise VerifiedResultError(f"symlinks are not allowed: {value}")
            cursor = cursor.parent
    return candidate


def load_structured(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
    elif path.suffix.lower() in {".yaml", ".yml"}:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    else:
        raise VerifiedResultError(f"unsupported structured file: {path}")
    if not isinstance(value, dict):
        raise VerifiedResultError(f"structured root must be a mapping: {path}")
    return value


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise VerifiedResultError(f"CSV has no header: {path}")
        rows = [normalize_row(row) for row in reader]
    return [str(name) for name in reader.fieldnames], rows


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def dump_yaml(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(value, allow_unicode=True, sort_keys=True, width=1000),
        encoding="utf-8",
    )


def dump_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def first_value(row: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def split_list(value: Any, *, double_pipe: bool = False) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        result: list[str] = []
        for item in value:
            result.extend(split_list(item, double_pipe=double_pipe))
        return [item for index, item in enumerate(result) if item and item not in result[:index]]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return split_list(parsed, double_pipe=double_pipe)
    delimiter = " || " if double_pipe and " || " in text else "|"
    values = [part.strip() for part in text.split(delimiter)]
    return [item for index, item in enumerate(values) if item and item not in values[:index]]


def extract_lock_records(value: Any) -> dict[str, str]:
    found: dict[str, str] = {}

    def visit(node: Any) -> None:
        if isinstance(node, Mapping):
            path_value = first_value(node, ("path", "relative_path", "artifact_path", "file"))
            hash_value = first_value(node, ("sha256", "hash", "file_sha256")).lower()
            if path_value and HEX64.fullmatch(hash_value):
                try:
                    found[normalize_relpath(path_value)] = hash_value
                except VerifiedResultError:
                    pass
            for key, child in node.items():
                key_text = str(key)
                if isinstance(child, Mapping):
                    child_hash = first_value(child, ("sha256", "hash", "file_sha256")).lower()
                    if HEX64.fullmatch(child_hash) and (
                        "/" in key_text or "." in PurePosixPath(key_text).name
                    ):
                        try:
                            found[normalize_relpath(key_text)] = child_hash
                        except VerifiedResultError:
                            pass
                if isinstance(child, str) and HEX64.fullmatch(child.lower()):
                    if "/" in key_text or "." in PurePosixPath(key_text).name:
                        try:
                            found[normalize_relpath(key_text)] = child.lower()
                        except VerifiedResultError:
                            pass
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return found


def locked_hash_matches(relpath: str, digest: str, records: Mapping[str, str]) -> bool:
    normalized = normalize_relpath(relpath)
    if records.get(normalized) == digest:
        return True
    basename_matches = [value for path, value in records.items() if PurePosixPath(path).name == PurePosixPath(normalized).name]
    return len(set(basename_matches)) == 1 and basename_matches[0] == digest


def git_baseline_check(repo_root: Path, baseline: str) -> dict[str, Any]:
    if not baseline:
        return {"checked": False, "reason": "baseline_not_declared"}
    if not re.fullmatch(r"[0-9a-f]{40}", baseline):
        raise VerifiedResultError("source_baseline_commit must be a 40-character SHA")
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", baseline, "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise VerifiedResultError(f"cannot verify git baseline: {exc}") from exc
    if ancestor.returncode != 0:
        raise VerifiedResultError(f"baseline {baseline} is not an ancestor of HEAD {head}")
    return {"checked": True, "baseline": baseline, "head": head, "ancestor": True}


def validate_declared_file(root: Path, binding: Mapping[str, Any], *, label: str) -> tuple[Path, str, str]:
    relpath = normalize_relpath(str(binding.get("path") or ""))
    declared = str(binding.get("sha256") or "").lower()
    if not HEX64.fullmatch(declared):
        raise VerifiedResultError(f"{label} requires a lower-case SHA-256")
    path = resolve_under(root, relpath, must_exist=True)
    if not path.is_file():
        raise VerifiedResultError(f"{label} is not a file: {relpath}")
    actual = sha256_file(path)
    if actual != declared:
        raise VerifiedResultError(f"{label} hash mismatch: {relpath}")
    return path, relpath, actual


def load_policy(repo_root: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    path = resolve_under(repo_root, str(manifest.get("policy_path") or ""), must_exist=True)
    policy = load_structured(path)
    required = (
        "allowed_source_roots",
        "allowed_repo_prefixes",
        "repo_candidate_extensions",
        "archive_extensions",
        "reject_path_patterns",
    )
    for key in required:
        if not isinstance(policy.get(key), list):
            raise VerifiedResultError(f"policy.{key} must be a list")
    return policy


def build_work_orders(rows: Sequence[Mapping[str, str]]) -> dict[str, WorkOrder]:
    result: dict[str, WorkOrder] = {}
    for row in rows:
        work_order_id = first_value(row, ("work_order_id", "order_id"))
        case_id = first_value(row, ("case_id", "company_case_id")) or "__suite__"
        if not work_order_id:
            raise VerifiedResultError("every work-order row requires work_order_id")
        if work_order_id in result:
            raise VerifiedResultError(f"duplicate work_order_id: {work_order_id}")
        result[work_order_id] = WorkOrder(
            row=dict(row),
            work_order_id=work_order_id,
            case_id=case_id,
            route_id=first_value(row, ("route_id", "execution_route", "route")),
            issue_ids=tuple(split_list(first_value(row, ("issue_ids", "blocker_ids", "issue_id", "blocker_id")))),
            acceptance_checks=tuple(split_list(row.get("acceptance_checks"))),
            depends_on=tuple(split_list(row.get("depends_on"))),
            source_row_sha256=row_sha256(row),
        )
    return result


def issue_ownership(rows: Sequence[Mapping[str, str]]) -> dict[str, str]:
    by_issue: dict[str, str] = {}
    for row in rows:
        issue_id = first_value(row, ("issue_id", "blocker_id", "occurrence_id"))
        work_order_id = first_value(row, ("work_order_id", "order_id"))
        if not issue_id:
            raise VerifiedResultError("every issue-ledger row requires an occurrence ID")
        if issue_id in by_issue:
            raise VerifiedResultError(f"duplicate issue occurrence ID: {issue_id}")
        by_issue[issue_id] = work_order_id
    return by_issue


def bind_issues_to_work_orders(
    work_orders: Mapping[str, WorkOrder],
    ledger_owners: Mapping[str, str],
) -> dict[str, list[str]]:
    """Require every source blocker occurrence to have exactly one BF1 work-order owner."""

    assigned: dict[str, str] = {}
    for work_order_id, work_order in work_orders.items():
        for issue_id in work_order.issue_ids:
            if issue_id not in ledger_owners:
                raise VerifiedResultError(
                    f"work order {work_order_id} references blocker absent from issue ledger: {issue_id}"
                )
            previous = assigned.get(issue_id)
            if previous is not None and previous != work_order_id:
                raise VerifiedResultError(
                    f"blocker occurrence assigned to multiple work orders: {issue_id}: "
                    f"{previous}, {work_order_id}"
                )
            ledger_owner = ledger_owners.get(issue_id) or ""
            if ledger_owner and ledger_owner != work_order_id:
                raise VerifiedResultError(
                    f"issue-ledger/work-order ownership mismatch for {issue_id}: "
                    f"{ledger_owner} != {work_order_id}"
                )
            assigned[issue_id] = work_order_id

    for issue_id, ledger_owner in ledger_owners.items():
        owner = ledger_owner or assigned.get(issue_id, "")
        if not owner:
            raise VerifiedResultError(f"source blocker has no work-order owner: {issue_id}")
        if owner not in work_orders:
            raise VerifiedResultError(f"issue {issue_id} references unknown work order {owner}")
        previous = assigned.get(issue_id)
        if previous is not None and previous != owner:
            raise VerifiedResultError(
                f"conflicting work-order owners for {issue_id}: {previous}, {owner}"
            )
        assigned[issue_id] = owner

    by_work_order: dict[str, list[str]] = {}
    for issue_id, work_order_id in assigned.items():
        by_work_order.setdefault(work_order_id, []).append(issue_id)
    return {key: sorted(value) for key, value in by_work_order.items()}


def discover_specs(spec_dir: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    if not spec_dir.exists():
        return result
    for path in sorted(spec_dir.rglob("*.yaml")) + sorted(spec_dir.rglob("*.yml")) + sorted(spec_dir.rglob("*.json")):
        if path.name.startswith("."):
            continue
        payload = load_structured(path)
        work_order_id = str(payload.get("work_order_id") or "").strip()
        if not work_order_id:
            continue
        if work_order_id in result:
            raise VerifiedResultError(f"duplicate work-order specs for {work_order_id}")
        result[work_order_id] = path
    return result


def rejected_path(path: str, policy: Mapping[str, Any]) -> bool:
    lowered = path.lower()
    for pattern in policy.get("reject_path_patterns") or []:
        text = str(pattern)
        if fnmatch.fnmatch(path, text) or fnmatch.fnmatch(lowered, text.lower()) or text.lower() in lowered:
            return True
    return False


def validate_source_path(
    repo_root: Path,
    spec_dir: Path,
    source_root: str,
    relpath: str,
    policy: Mapping[str, Any],
) -> tuple[Path, str]:
    normalized = normalize_relpath(relpath)
    if rejected_path(normalized, policy):
        raise VerifiedResultError(f"rejected path pattern: {normalized}")
    if source_root == "repo":
        if not any(normalized.startswith(str(prefix)) for prefix in policy.get("allowed_source_roots") or []):
            raise VerifiedResultError(f"repo source is outside allowed roots: {normalized}")
        return resolve_under(repo_root, normalized, must_exist=True), normalized
    if source_root == "spec_dir":
        return resolve_under(spec_dir, normalized, must_exist=True), normalized
    raise VerifiedResultError(f"unsupported source_root: {source_root}")


def verify_hash(path: Path, declared: str, label: str) -> str:
    digest = str(declared or "").lower()
    if not HEX64.fullmatch(digest):
        raise VerifiedResultError(f"{label} requires a lower-case SHA-256")
    if not path.is_file():
        raise VerifiedResultError(f"{label} is not a file: {path}")
    actual = sha256_file(path)
    if actual != digest:
        raise VerifiedResultError(f"{label} hash mismatch: {path}")
    return actual


def materialize_check(
    check: Mapping[str, Any],
    work_order_dir: Path,
    repo_root: Path,
    spec_dir: Path,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    check_id = str(check.get("id") or "").strip()
    acceptance_check = str(check.get("acceptance_check") or "").strip()
    status = str(check.get("status") or "").strip().lower()
    verifier = str(check.get("verifier") or "").strip()
    evidence = check.get("evidence")
    if not check_id or not acceptance_check or status not in PASSED or not verifier:
        raise VerifiedResultError("each passed check requires id, exact acceptance_check, passed status and verifier")
    if not isinstance(evidence, Mapping):
        raise VerifiedResultError(f"check {check_id} requires hash-backed evidence")
    source_root = str(evidence.get("source_root") or "repo")
    source_path, normalized = validate_source_path(
        repo_root,
        spec_dir,
        source_root,
        str(evidence.get("path") or ""),
        policy,
    )
    digest = verify_hash(source_path, str(evidence.get("sha256") or ""), f"check {check_id} evidence")
    evidence_kind = str(evidence.get("kind") or "other").strip()
    target_rel = normalize_relpath(f"check_evidence/{check_id}/{PurePosixPath(normalized).name}")
    target_path = resolve_under(work_order_dir, target_rel)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, target_path)
    if sha256_file(target_path) != digest:
        raise VerifiedResultError(f"copied check evidence hash mismatch: {check_id}")
    return {
        "id": check_id,
        "status": "passed",
        "acceptance_check": acceptance_check,
        "verifier": verifier,
        "evidence_kind": evidence_kind,
        "evidence_path": f"{work_order_dir.name}/{target_rel}",
        "evidence_sha256": digest,
    }


def materialize_artifact(
    artifact: Mapping[str, Any],
    work_order_dir: Path,
    repo_root: Path,
    spec_dir: Path,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    source_root = str(artifact.get("source_root") or "repo")
    source_path, normalized = validate_source_path(
        repo_root,
        spec_dir,
        source_root,
        str(artifact.get("path") or ""),
        policy,
    )
    digest = verify_hash(source_path, str(artifact.get("sha256") or ""), "produced artifact")
    disposition = str(artifact.get("disposition") or "").strip()
    if disposition not in {"repo_candidate", "archive_only", "local_only"}:
        raise VerifiedResultError(f"invalid artifact disposition: {disposition}")
    suffix = source_path.suffix.lower()
    promotion_target = str(artifact.get("promotion_target") or "").strip()
    if disposition == "repo_candidate":
        if suffix not in set(policy.get("repo_candidate_extensions") or []):
            raise VerifiedResultError(f"extension cannot be promoted: {suffix}")
        promotion_target = normalize_relpath(promotion_target)
        if not any(promotion_target.startswith(str(prefix)) for prefix in policy.get("allowed_repo_prefixes") or []):
            raise VerifiedResultError(f"unsafe promotion target: {promotion_target}")
        if rejected_path(promotion_target, policy):
            raise VerifiedResultError(f"rejected promotion target: {promotion_target}")
    elif suffix in set(policy.get("archive_extensions") or []) and disposition != "archive_only":
        raise VerifiedResultError(f"archive extension must be archive_only: {suffix}")

    if source_root == "repo":
        bf2_source_root = "repo"
        bf2_path = normalized
    else:
        target_rel = normalize_relpath(f"artifacts/{normalized}")
        target_path = resolve_under(work_order_dir, target_rel)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target_path)
        if sha256_file(target_path) != digest:
            raise VerifiedResultError("copied artifact hash mismatch")
        bf2_source_root = "dropzone"
        bf2_path = f"{work_order_dir.name}/{target_rel}"

    return {
        "source_root": bf2_source_root,
        "path": bf2_path,
        "sha256": digest,
        "disposition": disposition,
        "promotion_target": promotion_target,
    }


def validate_manual_attestation(
    spec: Mapping[str, Any],
    policy: Mapping[str, Any],
    work_order: WorkOrder,
    work_order_dir: Path,
    repo_root: Path,
    spec_dir: Path,
) -> dict[str, Any] | None:
    manual_routes = set(str(item) for item in policy.get("manual_routes") or [])
    value = spec.get("manual_attestation")
    if work_order.route_id not in manual_routes and not isinstance(value, Mapping):
        return None
    if not isinstance(value, Mapping):
        raise VerifiedResultError(f"manual route {work_order.route_id} requires manual_attestation")
    reviewer = str(value.get("reviewer") or "").strip()
    signed = value.get("signed") is True
    source_root = str(value.get("source_root") or "repo")
    attestation_path = str(value.get("attestation_path") or "").strip()
    attestation_sha = str(value.get("attestation_sha256") or "").lower()
    if not reviewer or not signed or not attestation_path or not HEX64.fullmatch(attestation_sha):
        raise VerifiedResultError("manual attestation requires reviewer, signed=true, path and SHA-256")
    source_path, normalized = validate_source_path(
        repo_root, spec_dir, source_root, attestation_path, policy
    )
    digest = verify_hash(source_path, attestation_sha, "manual attestation")
    target_rel = normalize_relpath(f"manual_attestation/{PurePosixPath(normalized).name}")
    target_path = resolve_under(work_order_dir, target_rel)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, target_path)
    if sha256_file(target_path) != digest:
        raise VerifiedResultError("copied manual attestation hash mismatch")
    return {
        "reviewer": reviewer,
        "signed": True,
        "attestation_path": f"{work_order_dir.name}/{target_rel}",
        "attestation_sha256": digest,
    }


def validate_spec_shape(spec: Mapping[str, Any]) -> None:
    if str(spec.get("schema_version") or "") != SPEC_SCHEMA_VERSION:
        raise VerifiedResultError(f"unexpected work-order spec schema: {spec.get('schema_version')}")
    if not str(spec.get("work_order_id") or "").strip():
        raise VerifiedResultError("work-order spec requires work_order_id")
    status = str(spec.get("execution_status") or "").strip().lower()
    if status not in PASSED | FAILED | PENDING:
        raise VerifiedResultError(f"unsupported execution_status: {status}")


def build_result_for_spec(
    work_order: WorkOrder,
    spec_path: Path | None,
    repo_root: Path,
    spec_dir: Path,
    dropzone: Path,
    policy: Mapping[str, Any],
    issue_ids_from_ledger: Sequence[str],
) -> tuple[dict[str, Any], MaterializedResult]:
    work_order_dir = resolve_under(dropzone, work_order.work_order_id)
    if work_order_dir.exists():
        shutil.rmtree(work_order_dir)
    work_order_dir.mkdir(parents=True, exist_ok=True)

    if spec_path is None:
        status = "manual_pending" if work_order.route_id in set(policy.get("manual_routes") or []) else "pending"
        payload = {
            "schema_version": RESULT_SCHEMA_VERSION,
            "work_order_id": work_order.work_order_id,
            "case_id": work_order.case_id,
            "source_work_order_sha256": work_order.source_row_sha256,
            "execution_status": status,
            "resolved_blocker_ids": [],
            "checks": [],
            "produced_artifacts": [],
            "materialization": {
                "schema_version": SCHEMA_VERSION,
                "reason": "verified_result_spec_missing",
                "sample_quality_allowed": False,
                "p2_allowed": False,
            },
        }
        return payload, MaterializedResult(work_order, status, status)

    spec = load_structured(spec_path)
    validate_spec_shape(spec)
    declared_status = str(spec.get("execution_status") or "").strip().lower()
    record = MaterializedResult(
        work_order=work_order,
        declared_status=declared_status,
        effective_status=declared_status,
        source_spec_path=spec_path.relative_to(repo_root).as_posix() if spec_path.is_relative_to(repo_root) else spec_path.name,
        source_spec_sha256=sha256_file(spec_path),
    )

    if str(spec.get("work_order_id") or "").strip() != work_order.work_order_id:
        raise VerifiedResultError(f"work_order_id mismatch in {spec_path}")
    spec_case = str(spec.get("case_id") or "").strip()
    if spec_case and spec_case != work_order.case_id:
        raise VerifiedResultError(f"case_id mismatch in {spec_path}")

    resolved = sorted(set(str(item).strip() for item in spec.get("resolved_blocker_ids") or [] if str(item).strip()))
    owned = sorted(set(work_order.issue_ids) | set(issue_ids_from_ledger))
    if not set(resolved).issubset(set(owned)):
        raise VerifiedResultError(f"spec resolves blockers not owned by {work_order.work_order_id}")

    checks_payload: list[dict[str, Any]] = []
    artifacts_payload: list[dict[str, Any]] = []
    manual_attestation: dict[str, Any] | None = None
    if declared_status in PASSED:
        if set(resolved) != set(owned):
            raise VerifiedResultError(
                f"passed work order must resolve every owned blocker: {work_order.work_order_id}"
            )
        raw_checks = spec.get("checks")
        if not isinstance(raw_checks, list) or not raw_checks:
            raise VerifiedResultError(f"passed work order requires checks: {work_order.work_order_id}")
        for raw in raw_checks:
            if not isinstance(raw, Mapping):
                raise VerifiedResultError("check entry must be a mapping")
            checks_payload.append(materialize_check(raw, work_order_dir, repo_root, spec_dir, policy))
        represented = {item["acceptance_check"] for item in checks_payload}
        required = set(work_order.acceptance_checks)
        if represented != required:
            missing = sorted(required - represented)
            extra = sorted(represented - required)
            raise VerifiedResultError(
                f"acceptance-check coverage mismatch for {work_order.work_order_id}; missing={missing}, extra={extra}"
            )
        manual_attestation = validate_manual_attestation(
            spec, policy, work_order, work_order_dir, repo_root, spec_dir
        )
    else:
        resolved = []

    raw_artifacts = spec.get("produced_artifacts") or []
    if not isinstance(raw_artifacts, list):
        raise VerifiedResultError("produced_artifacts must be a list")
    if declared_status not in PASSED:
        for raw in raw_artifacts:
            if isinstance(raw, Mapping) and str(raw.get("disposition") or "") == "repo_candidate":
                raise VerifiedResultError("non-passed work order cannot declare repo_candidate artifacts")
    for raw in raw_artifacts:
        if not isinstance(raw, Mapping):
            raise VerifiedResultError("artifact entry must be a mapping")
        artifacts_payload.append(materialize_artifact(raw, work_order_dir, repo_root, spec_dir, policy))

    payload: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "work_order_id": work_order.work_order_id,
        "case_id": work_order.case_id,
        "source_work_order_sha256": work_order.source_row_sha256,
        "execution_status": declared_status,
        "resolved_blocker_ids": resolved,
        "checks": checks_payload,
        "produced_artifacts": artifacts_payload,
        "materialization": {
            "schema_version": SCHEMA_VERSION,
            "source_spec_sha256": record.source_spec_sha256,
            "hash_backed_check_evidence": declared_status not in PASSED or bool(checks_payload),
            "dependency_gate_pending": declared_status in PASSED and bool(work_order.depends_on),
            "canonical_workflow_state_mutation_allowed": False,
            "sample_quality_allowed": False,
            "p2_allowed": False,
        },
    }
    if manual_attestation is not None:
        payload["manual_attestation"] = manual_attestation
    record.resolved_blocker_ids = resolved
    record.check_count = len(checks_payload)
    record.artifact_count = len(artifacts_payload)
    return payload, record


def enforce_dependencies(
    work_orders: Mapping[str, WorkOrder],
    payloads: Mapping[str, dict[str, Any]],
    records: Mapping[str, MaterializedResult],
) -> None:
    for work_order_id, work_order in work_orders.items():
        payload = payloads[work_order_id]
        status = str(payload.get("execution_status") or "").lower()
        if status not in PASSED:
            continue
        unknown = sorted(set(work_order.depends_on) - set(work_orders))
        if unknown:
            raise VerifiedResultError(f"unknown dependencies for {work_order_id}: {unknown}")
        incomplete = [
            dependency
            for dependency in work_order.depends_on
            if str(payloads[dependency].get("execution_status") or "").lower() not in PASSED
        ]
        if incomplete:
            raise VerifiedResultError(f"passed work order has incomplete dependencies: {work_order_id}: {incomplete}")
        payload["materialization"]["dependency_gate_pending"] = False
        payload["materialization"]["verified_dependencies"] = sorted(work_order.depends_on)
        records[work_order_id].effective_status = "engineering_pass"
        payload["execution_status"] = "engineering_pass"


def check_target_collisions(payloads: Mapping[str, Mapping[str, Any]]) -> None:
    targets: dict[str, str] = {}
    for work_order_id, payload in payloads.items():
        if str(payload.get("execution_status") or "").lower() not in PASSED:
            continue
        for artifact in payload.get("produced_artifacts") or []:
            if artifact.get("disposition") != "repo_candidate":
                continue
            target = str(artifact.get("promotion_target") or "")
            digest = str(artifact.get("sha256") or "")
            previous = targets.get(target)
            if previous is not None and previous != digest:
                raise VerifiedResultError(f"promotion target collision with different hashes: {target}")
            targets[target] = digest


def build_generation_lock(
    output_root: Path,
    metadata: Mapping[str, Any],
    written_files: Sequence[Path],
) -> dict[str, Any]:
    artifacts: dict[str, dict[str, Any]] = {}
    for path in sorted(written_files):
        if not path.is_file():
            raise VerifiedResultError(f"generation-lock artifact is missing: {path}")
        relpath = path.relative_to(output_root).as_posix()
        artifacts[relpath] = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
    generation_seed = {"metadata": dict(metadata), "artifacts": artifacts}
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "R5_bundle17r_bf2_ex1_generation_lock",
        "generation_id": "bf2_ex1_" + sha256_object(generation_seed)[:24],
        "metadata": dict(metadata),
        "artifacts": artifacts,
        "canonical_workflow_state_mutation_allowed": False,
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }


def run_materialization(repo_root: Path, manifest_path: Path, output_dir: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    manifest_path = manifest_path.resolve()
    manifest = load_structured(manifest_path)
    if str(manifest.get("schema_version") or "") != "r5_bundle17r_bf2_ex1_manifest_v1":
        raise VerifiedResultError("unexpected EX1 manifest schema")

    policy = load_policy(repo_root, manifest)
    baseline = git_baseline_check(repo_root, str(manifest.get("source_baseline_commit") or ""))
    inputs = manifest.get("inputs")
    if not isinstance(inputs, Mapping):
        raise VerifiedResultError("manifest.inputs must be a mapping")
    lock_path, lock_rel, lock_sha = validate_declared_file(repo_root, inputs.get("generation_lock") or {}, label="generation lock")
    work_path, work_rel, work_sha = validate_declared_file(repo_root, inputs.get("work_orders") or {}, label="work orders")
    issue_path, issue_rel, issue_sha = validate_declared_file(repo_root, inputs.get("issue_ledger") or {}, label="issue ledger")
    lock_records = extract_lock_records(load_structured(lock_path))
    if policy.get("require_generation_lock_coverage", True):
        if not locked_hash_matches(work_rel, work_sha, lock_records):
            raise VerifiedResultError("work-orders hash is not covered by BF1 generation lock")
        if not locked_hash_matches(issue_rel, issue_sha, lock_records):
            raise VerifiedResultError("issue-ledger hash is not covered by BF1 generation lock")

    _work_fields, work_rows = load_csv(work_path)
    _issue_fields, issue_rows = load_csv(issue_path)
    work_orders = build_work_orders(work_rows)
    issue_by_id = issue_ownership(issue_rows)
    issues_by_work_order = bind_issues_to_work_orders(work_orders, issue_by_id)

    spec_dir = resolve_under(repo_root, str(manifest.get("result_specs_dir") or ""))
    dropzone = resolve_under(repo_root, str(manifest.get("output_dropzone") or ""))
    target_output = output_dir.resolve() if output_dir else resolve_under(repo_root, str(manifest.get("output_dir") or ""))
    spec_dir.mkdir(parents=True, exist_ok=True)
    dropzone.mkdir(parents=True, exist_ok=True)
    target_output.mkdir(parents=True, exist_ok=True)
    orphan_result_dirs = sorted(
        path.parent.name
        for path in dropzone.rglob("result.yaml")
        if path.parent.name not in work_orders and path.parent.name != "reviews"
    )
    if orphan_result_dirs:
        raise VerifiedResultError(
            f"orphan BF2 result directories must be triaged before materialization: {orphan_result_dirs}"
        )
    specs = discover_specs(spec_dir)
    orphans = sorted(set(specs) - set(work_orders))
    if orphans:
        raise VerifiedResultError(f"orphan work-order specs: {orphans}")

    payloads: dict[str, dict[str, Any]] = {}
    records: dict[str, MaterializedResult] = {}
    for work_order_id, work_order in sorted(work_orders.items()):
        payload, record = build_result_for_spec(
            work_order,
            specs.get(work_order_id),
            repo_root,
            spec_dir,
            dropzone,
            policy,
            issues_by_work_order.get(work_order_id, []),
        )
        payloads[work_order_id] = payload
        records[work_order_id] = record

    enforce_dependencies(work_orders, payloads, records)
    check_target_collisions(payloads)

    for work_order_id, payload in sorted(payloads.items()):
        result_path = resolve_under(dropzone, f"{work_order_id}/result.yaml")
        dump_yaml(result_path, payload)
        records[work_order_id].result_path = result_path.relative_to(repo_root).as_posix()
        records[work_order_id].result_sha256 = sha256_file(result_path)

    matrix_rows = [
        {
            "work_order_id": record.work_order.work_order_id,
            "case_id": record.work_order.case_id,
            "route_id": record.work_order.route_id,
            "depends_on": "|".join(record.work_order.depends_on),
            "declared_status": record.declared_status,
            "effective_status": payloads[record.work_order.work_order_id]["execution_status"],
            "owned_blocker_count": len(set(record.work_order.issue_ids) | set(issues_by_work_order.get(record.work_order.work_order_id, []))),
            "resolved_blocker_count": len(record.resolved_blocker_ids),
            "check_count": record.check_count,
            "artifact_count": record.artifact_count,
            "result_path": record.result_path,
            "result_sha256": record.result_sha256,
            "source_spec_path": record.source_spec_path,
            "source_spec_sha256": record.source_spec_sha256,
        }
        for record in records.values()
    ]
    matrix_rows.sort(key=lambda row: (str(row["case_id"]), str(row["work_order_id"])))
    matrix_path = target_output / "R5_bundle17r_bf2_ex1_work_order_matrix.csv"
    dump_csv(
        matrix_path,
        [
            "work_order_id",
            "case_id",
            "route_id",
            "depends_on",
            "declared_status",
            "effective_status",
            "owned_blocker_count",
            "resolved_blocker_count",
            "check_count",
            "artifact_count",
            "result_path",
            "result_sha256",
            "source_spec_path",
            "source_spec_sha256",
        ],
        matrix_rows,
    )

    passed_count = sum(str(row["effective_status"]) in PASSED for row in matrix_rows)
    pending_count = sum(str(row["effective_status"]) in PENDING for row in matrix_rows)
    failed_count = sum(str(row["effective_status"]) in FAILED for row in matrix_rows)
    resolved_count = sum(int(row["resolved_blocker_count"]) for row in matrix_rows)
    report = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "R5_bundle17r_bf2_ex1_materialization_report",
        "bundle_id": str(manifest.get("bundle_id") or "R5_bundle17r_BF2_EX1"),
        "source_baseline_commit": str(manifest.get("source_baseline_commit") or ""),
        "baseline_check": baseline,
        "source_bf1_generation_lock": {"path": lock_rel, "sha256": lock_sha},
        "source_work_orders": {"path": work_rel, "sha256": work_sha, "count": len(work_orders)},
        "source_issue_ledger": {"path": issue_rel, "sha256": issue_sha, "occurrence_count": len(issue_rows)},
        "result_spec_count": len(specs),
        "materialized_result_count": len(payloads),
        "engineering_pass_count": passed_count,
        "pending_count": pending_count,
        "failed_count": failed_count,
        "resolved_blocker_occurrence_count": resolved_count,
        "unresolved_blocker_occurrence_count": len(issue_rows) - resolved_count,
        "next_command": (
            "python scripts/run_r5_bundle17r_backflow_execution.py --repo-root . "
            "--manifest <filled BF2 manifest>"
        ),
        "canonical_workflow_state_mutation_allowed": False,
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
    report_path = target_output / "R5_bundle17r_bf2_ex1_materialization_report.json"
    dump_json(report_path, report)

    readout = "\n".join(
        [
            "# R5 Bundle 17R-BF2-EX1 verified result materialization",
            "",
            f"- Work orders: {len(work_orders)}",
            f"- Verified specs supplied: {len(specs)}",
            f"- Engineering-pass results: {passed_count}",
            f"- Pending results: {pending_count}",
            f"- Failed results: {failed_count}",
            f"- Source blocker occurrences: {len(issue_rows)}",
            f"- Resolved blocker occurrences: {resolved_count}",
            f"- Unresolved blocker occurrences: {len(issue_rows) - resolved_count}",
            "- Canonical workflow-state mutation: **not authorized**",
            "- Sample-quality release: **not authorized**",
            "- P2 release: **not authorized**",
            "",
            "Every passed acceptance check is backed by a physical evidence file and exact SHA-256. ",
            "Every passed work order resolves exactly its owned blocker occurrences and has all dependencies passed. ",
            "The generated dropzone is an input to the existing BF2 receipt gate; it is not itself a promotion or activation decision.",
            "",
        ]
    )
    readout_path = target_output / "R5_bundle17r_bf2_ex1_close_readout.md"
    readout_path.write_text(readout, encoding="utf-8")

    metadata = {
        "bundle_id": report["bundle_id"],
        "source_baseline_commit": report["source_baseline_commit"],
        "manifest_sha256": sha256_file(manifest_path),
        "source_bf1_generation_lock_sha256": lock_sha,
        "dropzone": dropzone.relative_to(repo_root).as_posix(),
    }
    lock = build_generation_lock(
        target_output,
        metadata,
        [matrix_path, report_path, readout_path],
    )
    lock_path_out = target_output / "R5_bundle17r_bf2_ex1_generation_lock.json"
    dump_json(lock_path_out, lock)

    return {
        "report": report,
        "generation_lock": lock,
        "output_dir": target_output,
        "dropzone": dropzone,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize hash-backed BF2 result packages without canonical state mutation."
    )
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = args.repo_root / manifest_path
    output_dir = args.output_dir
    if output_dir is not None and not output_dir.is_absolute():
        output_dir = args.repo_root / output_dir
    try:
        result = run_materialization(args.repo_root, manifest_path, output_dir)
    except (VerifiedResultError, OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"ERROR: {exc}")
        return 2
    report = result["report"]
    print(
        "OK: "
        f"work_orders={report['materialized_result_count']} "
        f"passed={report['engineering_pass_count']} "
        f"unresolved={report['unresolved_blocker_occurrence_count']} "
        f"dropzone={result['dropzone']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
