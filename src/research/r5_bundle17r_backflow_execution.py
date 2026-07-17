"""Deterministic intake and promotion gate for R5 Bundle 17R targeted backflow.

This module deliberately does not execute arbitrary shell commands and does not mutate the
canonical workflow state.  It consumes the BF1 compiler outputs plus work-order result packages,
verifies exact hashes, preserves every source blocker occurrence, classifies local artifacts, and
emits deterministic engineering receipts and human-review handoffs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

import yaml

SCHEMA_VERSION = "r5_bundle17r_bf2_execution_v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")

WORK_ORDER_ID_KEYS = ("work_order_id", "order_id", "handoff_id")
CASE_ID_KEYS = ("case_id", "case_key", "research_case_id", "stock_code")
ROUTE_KEYS = ("execution_route", "route", "required_route", "required_skill")
BLOCKER_ID_KEYS = (
    "blocker_ids",
    "source_blocker_ids",
    "issue_ids",
    "blocker_id",
    "issue_id",
)
ISSUE_ID_KEYS = ("blocker_id", "issue_id", "blocker_occurrence_id", "occurrence_id")
STATUS_KEYS = ("execution_status", "status", "result_status")
PATH_KEYS = ("path", "artifact_path", "relative_path", "file", "filename")
HASH_KEYS = ("sha256", "digest", "file_sha256", "content_sha256")


class BackflowExecutionError(ValueError):
    """Raised when an input cannot be accepted without weakening the gate."""


@dataclass(frozen=True)
class ArtifactRecord:
    source_path: str
    source_sha256: str
    disposition: str
    promotion_target: str | None
    reason: str


@dataclass(frozen=True)
class WorkOrderReceipt:
    work_order_id: str
    case_id: str
    route: str
    source_work_order_sha256: str
    result_manifest_sha256: str | None
    receipt_status: str
    resolved_blocker_ids: tuple[str, ...]
    artifacts: tuple[ArtifactRecord, ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "work_order_id": self.work_order_id,
            "case_id": self.case_id,
            "route": self.route,
            "source_work_order_sha256": self.source_work_order_sha256,
            "result_manifest_sha256": self.result_manifest_sha256,
            "receipt_status": self.receipt_status,
            "resolved_blocker_ids": list(self.resolved_blocker_ids),
            "artifacts": [
                {
                    "source_path": item.source_path,
                    "source_sha256": item.source_sha256,
                    "disposition": item.disposition,
                    "promotion_target": item.promotion_target,
                    "reason": item.reason,
                }
                for item in self.artifacts
            ],
            "reasons": list(self.reasons),
        }
        payload["receipt_sha256"] = sha256_object(payload)
        return payload


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_object(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BackflowExecutionError(f"YAML root must be a mapping: {path}")
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BackflowExecutionError(f"JSON root must be a mapping: {path}")
    return value


def load_structured(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".json":
        return load_json(path)
    if path.suffix.lower() in {".yaml", ".yml"}:
        return load_yaml(path)
    raise BackflowExecutionError(f"unsupported structured file type: {path}")


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise BackflowExecutionError(f"CSV has no header: {path}")
        rows = [{str(key): str(value or "") for key, value in row.items()} for row in reader]
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
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def first_value(row: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def split_ids(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        result: list[str] = []
        for item in value:
            result.extend(split_ids(item))
        return sorted(set(result))
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return split_ids(parsed)
    return sorted({item.strip() for item in re.split(r"[;,|\s]+", text) if item.strip()})


def normalize_row(row: Mapping[str, Any]) -> dict[str, str]:
    return {str(key).strip(): str(value or "").strip() for key, value in row.items()}


def row_sha256(row: Mapping[str, Any]) -> str:
    return sha256_object(normalize_row(row))


def normalize_relpath(value: str) -> str:
    text = value.replace("\\", "/").strip()
    path = PurePosixPath(text)
    if not text or path.is_absolute() or ".." in path.parts:
        raise BackflowExecutionError(f"unsafe relative path: {value!r}")
    if any(part in {"", "."} for part in path.parts):
        path = PurePosixPath(*[part for part in path.parts if part not in {"", "."}])
    return path.as_posix()


def resolve_under(root: Path, value: str) -> Path:
    normalized = normalize_relpath(value)
    candidate = (root / normalized).resolve()
    resolved_root = root.resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise BackflowExecutionError(f"path escapes root: {value!r}") from exc
    return candidate


def extract_lock_records(value: Any) -> dict[str, str]:
    """Extract path/hash pairs from common generation-lock shapes.

    Bundle generations have used both an ``artifacts`` list and direct path-to-hash mappings.  The
    recursive extractor accepts either while still requiring a 64-character lower-case SHA-256.
    """

    found: dict[str, str] = {}

    def visit(node: Any) -> None:
        if isinstance(node, Mapping):
            path_value = first_value(node, PATH_KEYS)
            hash_value = first_value(node, HASH_KEYS).lower()
            if path_value and HEX64.fullmatch(hash_value):
                try:
                    found[normalize_relpath(path_value)] = hash_value
                except BackflowExecutionError:
                    pass
            for key, child in node.items():
                key_text = str(key)
                if isinstance(child, str) and HEX64.fullmatch(child.lower()):
                    if "/" in key_text or "." in PurePosixPath(key_text).name:
                        try:
                            found[normalize_relpath(key_text)] = child.lower()
                        except BackflowExecutionError:
                            pass
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return found


def match_locked_hash(relpath: str, locked: Mapping[str, str]) -> str | None:
    normalized = normalize_relpath(relpath)
    if normalized in locked:
        return locked[normalized]
    suffix_matches = [digest for path, digest in locked.items() if path.endswith("/" + normalized)]
    if len(set(suffix_matches)) == 1:
        return suffix_matches[0]
    basename_matches = [
        digest
        for path, digest in locked.items()
        if PurePosixPath(path).name == PurePosixPath(normalized).name
    ]
    if len(set(basename_matches)) == 1:
        return basename_matches[0]
    return None


def verify_locked_input(
    repo_root: Path,
    relpath: str,
    locked: Mapping[str, str],
    *,
    require_coverage: bool,
) -> dict[str, Any]:
    path = resolve_under(repo_root, relpath)
    if not path.is_file():
        raise BackflowExecutionError(f"required BF1 input is missing: {relpath}")
    actual = sha256_file(path)
    expected = match_locked_hash(relpath, locked)
    if expected is None and require_coverage:
        raise BackflowExecutionError(f"BF1 generation lock does not cover input: {relpath}")
    if expected is not None and expected != actual:
        raise BackflowExecutionError(
            f"BF1 input hash mismatch for {relpath}: expected {expected}, got {actual}"
        )
    return {
        "path": normalize_relpath(relpath),
        "sha256": actual,
        "lock_covered": expected is not None,
    }


def load_policy(path: Path | None) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "require_input_lock_coverage": True,
        "passed_statuses": ["passed", "complete", "completed", "engineering_pass"],
        "failed_statuses": ["failed", "rejected", "error"],
        "manual_statuses": ["manual_pending", "pending", "needs_manual_route"],
        "always_manual_routes": ["manual", "human_review", "evidence_review"],
        "allowed_repo_prefixes": [
            ".agents/",
            ".github/workflows/",
            "config/",
            "data/",
            "decisions/",
            "docs/",
            "reports/",
            "schemas/",
            "scripts/",
            "src/",
            "templates/",
            "tests/",
        ],
        "repo_candidate_extensions": [
            ".csv",
            ".html",
            ".json",
            ".md",
            ".py",
            ".toml",
            ".txt",
            ".yaml",
            ".yml",
        ],
        "archive_extensions": [".zip", ".png", ".jpg", ".jpeg", ".webp", ".log"],
        "reject_path_patterns": [
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
            ".mypy_cache",
            ".DS_Store",
            "node_modules",
            ".env",
            "credentials",
            "secret",
            "token",
            "*.pyc",
            "*.pyo",
            "*.tmp",
            "*.temp",
            "~*",
        ],
        "require_checks_for_pass": True,
        "require_resolved_blocker_for_pass": True,
        "require_manual_attestation": True,
    }
    if path is None:
        return defaults
    supplied = load_yaml(path)
    merged = dict(defaults)
    merged.update(supplied)
    return merged


def pattern_matches(path: str, pattern: str) -> bool:
    path_lower = path.lower()
    pattern_lower = pattern.lower()
    if "*" in pattern_lower or "?" in pattern_lower:
        import fnmatch

        return fnmatch.fnmatch(path_lower, pattern_lower) or fnmatch.fnmatch(
            PurePosixPath(path_lower).name,
            pattern_lower,
        )
    return pattern_lower in path_lower


def classify_artifact(
    repo_root: Path,
    dropzone: Path,
    artifact: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> ArtifactRecord:
    source_root_name = str(artifact.get("source_root") or "repo").strip().lower()
    if source_root_name not in {"repo", "dropzone"}:
        raise BackflowExecutionError(f"unsupported artifact source_root: {source_root_name}")
    source_root = repo_root if source_root_name == "repo" else dropzone
    source_rel = normalize_relpath(str(artifact.get("path") or ""))
    source_path = resolve_under(source_root, source_rel)
    if not source_path.is_file() or source_path.is_symlink():
        return ArtifactRecord(source_rel, "", "reject", None, "missing_or_symlink")

    actual_hash = sha256_file(source_path)
    declared_hash = str(artifact.get("sha256") or "").strip().lower()
    if not HEX64.fullmatch(declared_hash) or declared_hash != actual_hash:
        return ArtifactRecord(source_rel, actual_hash, "reject", None, "sha256_mismatch")

    combined_name = f"{source_root_name}/{source_rel}"
    reject_patterns = [str(item) for item in policy.get("reject_path_patterns") or []]
    if any(pattern_matches(combined_name, pattern) for pattern in reject_patterns):
        return ArtifactRecord(source_rel, actual_hash, "reject", None, "reject_pattern")

    suffix = source_path.suffix.lower()
    declared = str(artifact.get("disposition") or "").strip().lower()
    archive_extensions = {str(item).lower() for item in policy.get("archive_extensions") or []}
    repo_extensions = {
        str(item).lower() for item in policy.get("repo_candidate_extensions") or []
    }

    if suffix in archive_extensions:
        if declared and declared not in {"archive_only", "local_only"}:
            return ArtifactRecord(source_rel, actual_hash, "reject", None, "binary_not_promotable")
        return ArtifactRecord(source_rel, actual_hash, "archive_only", None, "archive_extension")

    target_value = str(artifact.get("promotion_target") or "").strip()
    if declared == "archive_only":
        return ArtifactRecord(source_rel, actual_hash, "archive_only", None, "declared_archive")
    if declared not in {"repo_candidate", "local_only", ""}:
        return ArtifactRecord(source_rel, actual_hash, "reject", None, "unknown_disposition")
    if declared == "local_only":
        return ArtifactRecord(source_rel, actual_hash, "archive_only", None, "declared_local_only")
    if suffix not in repo_extensions:
        return ArtifactRecord(source_rel, actual_hash, "reject", None, "extension_not_allowed")

    if not target_value:
        if source_root_name == "repo":
            target_value = source_rel
        else:
            return ArtifactRecord(
                source_rel, actual_hash, "reject", None, "missing_promotion_target"
            )
    target = normalize_relpath(target_value)
    allowed_prefixes = [str(item) for item in policy.get("allowed_repo_prefixes") or []]
    if not any(
        target == prefix.rstrip("/") or target.startswith(prefix)
        for prefix in allowed_prefixes
    ):
        return ArtifactRecord(
            source_rel, actual_hash, "reject", target, "promotion_target_not_allowed"
        )
    target_suffix = PurePosixPath(target).suffix.lower()
    if target_suffix not in repo_extensions:
        return ArtifactRecord(
            source_rel, actual_hash, "reject", target, "target_extension_not_allowed"
        )
    return ArtifactRecord(source_rel, actual_hash, "repo_candidate", target, "eligible")


def discover_results(dropzone: Path) -> dict[str, Path]:
    if not dropzone.exists():
        return {}
    candidates: list[Path] = []
    for pattern in ("**/result.yaml", "**/result.yml", "**/result.json"):
        candidates.extend(dropzone.glob(pattern))
    direct = [
        path
        for path in dropzone.iterdir()
        if path.is_file() and path.suffix.lower() in {".yaml", ".yml", ".json"}
    ]
    candidates.extend(direct)

    by_id: dict[str, Path] = {}
    for path in sorted(set(item.resolve() for item in candidates)):
        try:
            payload = load_structured(path)
        except (BackflowExecutionError, json.JSONDecodeError, yaml.YAMLError):
            continue
        work_order_id = str(payload.get("work_order_id") or "").strip()
        if not work_order_id:
            continue
        if work_order_id in by_id:
            raise BackflowExecutionError(
                f"duplicate result manifests for work order {work_order_id}"
            )
        by_id[work_order_id] = path
    return by_id


def index_issues(
    issue_rows: Sequence[Mapping[str, str]],
) -> tuple[dict[str, list[str]], dict[str, dict[str, str]]]:
    by_work_order: dict[str, list[str]] = defaultdict(list)
    by_issue: dict[str, dict[str, str]] = {}
    for row in issue_rows:
        issue_id = first_value(row, ISSUE_ID_KEYS)
        if not issue_id:
            raise BackflowExecutionError(
                "every issue-ledger row requires an issue/blocker occurrence id"
            )
        if issue_id in by_issue:
            raise BackflowExecutionError(f"duplicate blocker occurrence id: {issue_id}")
        work_order_id = first_value(row, WORK_ORDER_ID_KEYS)
        by_issue[issue_id] = dict(row)
        if work_order_id:
            by_work_order[work_order_id].append(issue_id)
    return {key: sorted(value) for key, value in by_work_order.items()}, by_issue


def build_receipt(
    work_order: Mapping[str, str],
    result_path: Path | None,
    repo_root: Path,
    dropzone: Path,
    policy: Mapping[str, Any],
    issue_ids_from_ledger: Sequence[str],
) -> WorkOrderReceipt:
    work_order_id = first_value(work_order, WORK_ORDER_ID_KEYS)
    case_id = first_value(work_order, CASE_ID_KEYS)
    route = first_value(work_order, ROUTE_KEYS) or "unspecified"
    if not work_order_id or not case_id:
        raise BackflowExecutionError("every work order requires work_order_id and case_id")
    source_hash = row_sha256(work_order)
    declared_issue_ids: list[str] = []
    for key in BLOCKER_ID_KEYS:
        declared_issue_ids.extend(split_ids(work_order.get(key)))
    source_issue_ids = sorted(set(declared_issue_ids) | set(issue_ids_from_ledger))

    if result_path is None:
        status = (
            "manual_pending"
            if route in set(policy.get("always_manual_routes") or [])
            else "pending"
        )
        return WorkOrderReceipt(
            work_order_id,
            case_id,
            route,
            source_hash,
            None,
            status,
            tuple(),
            tuple(),
            ("result_manifest_missing",),
        )

    result = load_structured(result_path)
    result_hash = sha256_file(result_path)
    reasons: list[str] = []
    if str(result.get("work_order_id") or "").strip() != work_order_id:
        reasons.append("work_order_id_mismatch")
    result_case = str(result.get("case_id") or "").strip()
    if result_case and result_case != case_id:
        reasons.append("case_id_mismatch")
    result_source_hash = str(result.get("source_work_order_sha256") or "").strip().lower()
    if result_source_hash != source_hash:
        reasons.append("source_work_order_sha256_mismatch")

    status = first_value(result, STATUS_KEYS).lower()
    passed_statuses = {str(item).lower() for item in policy.get("passed_statuses") or []}
    failed_statuses = {str(item).lower() for item in policy.get("failed_statuses") or []}
    manual_statuses = {str(item).lower() for item in policy.get("manual_statuses") or []}
    if status not in passed_statuses | failed_statuses | manual_statuses:
        reasons.append("unsupported_execution_status")

    resolved = split_ids(result.get("resolved_blocker_ids"))
    unknown_resolved = sorted(set(resolved) - set(source_issue_ids))
    if unknown_resolved:
        reasons.append("resolved_blocker_not_owned_by_work_order")
    if policy.get("require_resolved_blocker_for_pass", True) and status in passed_statuses:
        if source_issue_ids and not resolved:
            reasons.append("passed_result_has_no_resolved_blocker")

    checks = result.get("checks") or []
    if not isinstance(checks, list):
        reasons.append("checks_must_be_list")
        checks = []
    check_statuses = [
        str(item.get("status") or "").strip().lower()
        for item in checks
        if isinstance(item, Mapping)
    ]
    if policy.get("require_checks_for_pass", True) and status in passed_statuses:
        if not checks or any(item not in passed_statuses for item in check_statuses):
            reasons.append("required_checks_not_all_passed")

    route_is_manual = route in set(policy.get("always_manual_routes") or [])
    if (
        route_is_manual
        and status in passed_statuses
        and policy.get("require_manual_attestation", True)
    ):
        attestation = result.get("manual_attestation")
        if not isinstance(attestation, Mapping):
            reasons.append("manual_attestation_missing")
        else:
            reviewer = str(attestation.get("reviewer") or "").strip()
            signed = bool(attestation.get("signed"))
            if not reviewer or not signed:
                reasons.append("manual_attestation_incomplete")

    artifacts_payload = result.get("produced_artifacts") or []
    if not isinstance(artifacts_payload, list):
        reasons.append("produced_artifacts_must_be_list")
        artifacts_payload = []
    artifacts: list[ArtifactRecord] = []
    for item in artifacts_payload:
        if not isinstance(item, Mapping):
            artifacts.append(ArtifactRecord("", "", "reject", None, "artifact_not_mapping"))
            continue
        try:
            artifacts.append(classify_artifact(repo_root, dropzone, item, policy))
        except BackflowExecutionError as exc:
            artifacts.append(ArtifactRecord("", "", "reject", None, str(exc)))
    if any(item.disposition == "reject" for item in artifacts):
        reasons.append("artifact_rejected")

    if reasons:
        receipt_status = "failed"
    elif status in passed_statuses:
        receipt_status = "engineering_pass"
    elif status in failed_statuses:
        receipt_status = "failed"
    else:
        receipt_status = "manual_pending" if route_is_manual else "pending"

    return WorkOrderReceipt(
        work_order_id,
        case_id,
        route,
        source_hash,
        result_hash,
        receipt_status,
        tuple(sorted(set(resolved))),
        tuple(artifacts),
        tuple(sorted(set(reasons))),
    )


def load_review_decision(review_dir: Path, case_id: str) -> dict[str, Any] | None:
    for suffix in (".yaml", ".yml", ".json"):
        path = review_dir / f"{case_id}{suffix}"
        if path.is_file():
            payload = load_structured(path)
            payload["_source_path"] = path.as_posix()
            payload["_source_sha256"] = sha256_file(path)
            return payload
    return None


def verify_review_decision(
    decision: Mapping[str, Any] | None,
    case_generation_sha256: str,
) -> tuple[str, list[str]]:
    if decision is None:
        return "pending", ["review_decision_missing"]
    status = str(decision.get("decision") or "pending").strip().lower()
    reasons: list[str] = []
    if status not in {"accepted", "rejected", "pending"}:
        return "invalid", ["unsupported_review_decision"]
    if status in {"accepted", "rejected"}:
        if str(decision.get("reviewed_case_generation_sha256") or "").strip().lower() != (
            case_generation_sha256
        ):
            reasons.append("review_hash_mismatch")
        if not str(decision.get("reviewer") or "").strip():
            reasons.append("reviewer_missing")
        if not str(decision.get("reviewed_at") or "").strip():
            reasons.append("reviewed_at_missing")
    if reasons:
        return "invalid", reasons
    return status, []


def git_baseline_check(repo_root: Path, baseline_commit: str | None) -> dict[str, Any]:
    if not baseline_commit:
        return {"checked": False, "reason": "baseline_not_declared"}
    try:
        head = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        ancestor = subprocess.run(
            ["git", "-C", str(repo_root), "merge-base", "--is-ancestor", baseline_commit, "HEAD"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
    except (OSError, subprocess.CalledProcessError):
        return {"checked": False, "reason": "git_unavailable"}
    if not ancestor:
        raise BackflowExecutionError(
            f"declared BF1 baseline {baseline_commit} is not an ancestor of current HEAD {head}"
        )
    return {"checked": True, "head": head, "baseline": baseline_commit, "ancestor": True}


def build_generation_lock(
    output_dir: Path,
    files: Sequence[Path],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    rows = []
    for path in sorted(files, key=lambda item: item.relative_to(output_dir).as_posix()):
        relpath = path.relative_to(output_dir).as_posix()
        rows.append({"path": relpath, "sha256": sha256_file(path), "size": path.stat().st_size})
    aggregate = sha256_object(rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "R5_bundle17r_bf2_generation_lock",
        "metadata": dict(metadata),
        "artifacts": rows,
        "aggregate_sha256": aggregate,
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }


def _manifest_input_path(manifest: Mapping[str, Any], name: str) -> str:
    inputs = manifest.get("inputs")
    if not isinstance(inputs, Mapping):
        raise BackflowExecutionError("manifest.inputs must be a mapping")
    value = str(inputs.get(name) or "").strip()
    if not value:
        raise BackflowExecutionError(f"manifest input is missing: {name}")
    return normalize_relpath(value)


def run_execution(
    repo_root: Path,
    manifest_path: Path,
    output_dir: Path | None = None,
    *,
    fail_on_manual_route: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    manifest = load_yaml(manifest_path)
    if manifest.get("schema_version") != "r5_bundle17r_bf2_execution_manifest_v1":
        raise BackflowExecutionError("unsupported BF2 execution manifest schema_version")

    policy_value = str(manifest.get("policy_path") or "").strip()
    policy_path = resolve_under(repo_root, policy_value) if policy_value else None
    policy = load_policy(policy_path)
    baseline_result = git_baseline_check(
        repo_root, str(manifest.get("source_baseline_commit") or "")
    )

    lock_rel = _manifest_input_path(manifest, "generation_lock")
    lock_path = resolve_under(repo_root, lock_rel)
    lock = load_json(lock_path)
    locked_hashes = extract_lock_records(lock)
    if not locked_hashes:
        raise BackflowExecutionError(
            "BF1 generation lock contains no recognizable path/SHA-256 pairs"
        )

    input_names = ("work_orders", "issue_ledger", "case_matrix")
    input_paths = {name: _manifest_input_path(manifest, name) for name in input_names}
    input_validation = [
        verify_locked_input(
            repo_root,
            relpath,
            locked_hashes,
            require_coverage=bool(policy.get("require_input_lock_coverage", True)),
        )
        for relpath in input_paths.values()
    ]
    input_validation.append(
        {"path": lock_rel, "sha256": sha256_file(lock_path), "lock_covered": True}
    )

    work_order_fields, work_orders = load_csv(resolve_under(repo_root, input_paths["work_orders"]))
    issue_fields, issue_rows = load_csv(resolve_under(repo_root, input_paths["issue_ledger"]))
    case_fields, source_case_rows = load_csv(resolve_under(repo_root, input_paths["case_matrix"]))
    if not work_orders:
        raise BackflowExecutionError("BF1 work-order CSV is empty")
    by_work_order, issue_index = index_issues(issue_rows)

    dropzone_rel = normalize_relpath(str(manifest.get("result_dropzone") or ""))
    dropzone = resolve_under(repo_root, dropzone_rel)
    results = discover_results(dropzone)

    work_order_ids: set[str] = set()
    receipts: list[WorkOrderReceipt] = []
    for row in work_orders:
        work_order_id = first_value(row, WORK_ORDER_ID_KEYS)
        if not work_order_id:
            raise BackflowExecutionError("work-order row has no work_order_id")
        if work_order_id in work_order_ids:
            raise BackflowExecutionError(f"duplicate work_order_id: {work_order_id}")
        work_order_ids.add(work_order_id)
        receipts.append(
            build_receipt(
                row,
                results.get(work_order_id),
                repo_root,
                dropzone,
                policy,
                by_work_order.get(work_order_id, []),
            )
        )
    orphan_results = sorted(set(results) - work_order_ids)
    if orphan_results:
        raise BackflowExecutionError(
            f"result manifests do not match BF1 work orders: {orphan_results}"
        )

    receipt_dicts = [item.to_dict() for item in receipts]
    receipt_by_work_order = {item["work_order_id"]: item for item in receipt_dicts}

    updated_issues: list[dict[str, Any]] = []
    resolved_issue_ids: set[str] = set()
    for source_row in issue_rows:
        row: dict[str, Any] = dict(source_row)
        issue_id = first_value(source_row, ISSUE_ID_KEYS)
        work_order_id = first_value(source_row, WORK_ORDER_ID_KEYS)
        receipt = receipt_by_work_order.get(work_order_id)
        resolved = bool(
            receipt
            and receipt["receipt_status"] == "engineering_pass"
            and issue_id in set(receipt["resolved_blocker_ids"])
        )
        if resolved:
            resolved_issue_ids.add(issue_id)
        row.update(
            {
                "bf2_source_occurrence_preserved": "true",
                "bf2_resolution_status": "resolved" if resolved else "unresolved",
                "bf2_work_order_id": work_order_id,
                "bf2_receipt_sha256": receipt.get("receipt_sha256", "") if receipt else "",
            }
        )
        updated_issues.append(row)

    case_ids: set[str] = set()
    for row in source_case_rows:
        case_id = first_value(row, CASE_ID_KEYS)
        if case_id:
            case_ids.add(case_id)
    for receipt in receipt_dicts:
        case_ids.add(str(receipt["case_id"]))
    for issue in issue_rows:
        case_id = first_value(issue, CASE_ID_KEYS)
        if case_id:
            case_ids.add(case_id)
    if not case_ids:
        raise BackflowExecutionError("no case IDs were found")

    source_case_by_id = {
        first_value(row, CASE_ID_KEYS): dict(row)
        for row in source_case_rows
        if first_value(row, CASE_ID_KEYS)
    }
    issues_by_case: dict[str, list[str]] = defaultdict(list)
    for issue_id, row in issue_index.items():
        case_id = first_value(row, CASE_ID_KEYS)
        if case_id:
            issues_by_case[case_id].append(issue_id)
        else:
            work_order_id = first_value(row, WORK_ORDER_ID_KEYS)
            receipt = receipt_by_work_order.get(work_order_id)
            if receipt:
                issues_by_case[str(receipt["case_id"])].append(issue_id)
    receipts_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for receipt in receipt_dicts:
        receipts_by_case[str(receipt["case_id"])].append(receipt)

    review_dir_value = str(manifest.get("review_decision_dir") or "").strip()
    review_dir = (
        resolve_under(repo_root, review_dir_value)
        if review_dir_value
        else dropzone / "reviews"
    )

    case_rows: list[dict[str, Any]] = []
    handoffs: list[dict[str, Any]] = []
    promotion_rows: list[dict[str, Any]] = []
    archive_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    review_statuses: dict[str, str] = {}

    for receipt in receipt_dicts:
        for artifact in receipt["artifacts"]:
            row = {
                "case_id": receipt["case_id"],
                "work_order_id": receipt["work_order_id"],
                "receipt_sha256": receipt["receipt_sha256"],
                **artifact,
            }
            if artifact["disposition"] == "repo_candidate":
                promotion_rows.append(row)
            elif artifact["disposition"] == "archive_only":
                archive_rows.append(row)
            else:
                rejected_rows.append(row)

    for case_id in sorted(case_ids):
        source = dict(source_case_by_id.get(case_id, {}))
        source.setdefault("case_id", case_id)
        issue_ids = sorted(set(issues_by_case.get(case_id, [])))
        unresolved = sorted(set(issue_ids) - resolved_issue_ids)
        case_receipts = sorted(
            receipts_by_case.get(case_id, []),
            key=lambda item: str(item["work_order_id"]),
        )
        engineering_pass = bool(case_receipts) and not unresolved and all(
            item["receipt_status"] == "engineering_pass" for item in case_receipts
        )
        case_payload = {
            "schema_version": SCHEMA_VERSION,
            "case_id": case_id,
            "source_blocker_occurrence_ids": issue_ids,
            "resolved_blocker_occurrence_ids": sorted(set(issue_ids) & resolved_issue_ids),
            "unresolved_blocker_occurrence_ids": unresolved,
            "work_order_receipts": [
                {
                    "work_order_id": item["work_order_id"],
                    "receipt_sha256": item["receipt_sha256"],
                    "receipt_status": item["receipt_status"],
                }
                for item in case_receipts
            ],
            "promotable_artifacts": sorted(
                [
                    {
                        "promotion_target": row["promotion_target"],
                        "source_sha256": row["source_sha256"],
                    }
                    for row in promotion_rows
                    if str(row["case_id"]) == case_id
                ],
                key=lambda item: str(item["promotion_target"]),
            ),
            "engineering_pass": engineering_pass,
        }
        case_generation_sha = sha256_object(case_payload)
        decision = load_review_decision(review_dir, case_id)
        review_status, review_reasons = verify_review_decision(decision, case_generation_sha)
        if not engineering_pass:
            review_status = "not_eligible"
            review_reasons = ["engineering_gate_not_passed"]
        review_statuses[case_id] = review_status
        handoff = {
            "schema_version": "r5_bundle17r_bf2_case_review_handoff_v1",
            "case_id": case_id,
            "case_generation_sha256": case_generation_sha,
            "engineering_pass": engineering_pass,
            "review_status": review_status,
            "review_reasons": review_reasons,
            "sample_quality_allowed": False,
            "p2_allowed": False,
            "case_payload": case_payload,
        }
        handoff["handoff_sha256"] = sha256_object(handoff)
        handoffs.append(handoff)
        source.update(
            {
                "bf2_source_blocker_count": len(issue_ids),
                "bf2_resolved_blocker_count": len(issue_ids) - len(unresolved),
                "bf2_unresolved_blocker_count": len(unresolved),
                "bf2_work_order_count": len(case_receipts),
                "bf2_engineering_pass": str(engineering_pass).lower(),
                "bf2_case_generation_sha256": case_generation_sha,
                "bf2_review_status": review_status,
                "bf2_sample_quality_allowed": "false",
                "bf2_p2_allowed": "false",
            }
        )
        case_rows.append(source)

    blocker_count = len(issue_rows)
    unresolved_count = blocker_count - len(resolved_issue_ids)
    engineering_pass_count = sum(row["bf2_engineering_pass"] == "true" for row in case_rows)
    accepted_review_count = sum(status == "accepted" for status in review_statuses.values())
    if unresolved_count or engineering_pass_count < len(case_rows):
        next_stage = "R5_bundle17r_targeted_backflow"
        decision = "needs_targeted_backflow"
    elif accepted_review_count < len(case_rows):
        next_stage = "R5_bundle17r_human_review"
        decision = "ready_for_exact_hash_human_review"
    else:
        next_stage = "R5_bundle17r_reviewed_candidate"
        decision = "reviewed_candidate_requires_separate_activation"

    target_output = output_dir or resolve_under(
        repo_root,
        normalize_relpath(str(manifest.get("output_dir") or "")),
    )
    target_output.mkdir(parents=True, exist_ok=True)

    metadata = {
        "bundle_id": str(manifest.get("bundle_id") or "R5_bundle17r_BF2"),
        "source_baseline_commit": str(manifest.get("source_baseline_commit") or ""),
        "as_of": str(manifest.get("as_of") or ""),
        "manifest_sha256": sha256_file(manifest_path),
        "baseline_check": baseline_result,
        "input_validation": input_validation,
    }
    receipts_payload = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "R5_bundle17r_bf2_execution_receipts",
        "metadata": metadata,
        "receipts": sorted(receipt_dicts, key=lambda item: item["work_order_id"]),
        "summary": {
            "work_order_count": len(receipt_dicts),
            "engineering_pass_count": sum(
                item["receipt_status"] == "engineering_pass" for item in receipt_dicts
            ),
            "pending_count": sum(
                item["receipt_status"] in {"pending", "manual_pending"} for item in receipt_dicts
            ),
            "failed_count": sum(item["receipt_status"] == "failed" for item in receipt_dicts),
        },
    }

    written: list[Path] = []
    receipts_path = target_output / "R5_bundle17r_bf2_execution_receipts.json"
    dump_json(receipts_path, receipts_payload)
    written.append(receipts_path)

    issue_out_fields = list(issue_fields)
    for name in (
        "bf2_source_occurrence_preserved",
        "bf2_resolution_status",
        "bf2_work_order_id",
        "bf2_receipt_sha256",
    ):
        if name not in issue_out_fields:
            issue_out_fields.append(name)
    issue_path = target_output / "R5_bundle17r_bf2_issue_ledger.csv"
    dump_csv(issue_path, issue_out_fields, updated_issues)
    written.append(issue_path)

    case_out_fields = list(case_fields)
    if "case_id" not in case_out_fields:
        case_out_fields.insert(0, "case_id")
    for name in (
        "bf2_source_blocker_count",
        "bf2_resolved_blocker_count",
        "bf2_unresolved_blocker_count",
        "bf2_work_order_count",
        "bf2_engineering_pass",
        "bf2_case_generation_sha256",
        "bf2_review_status",
        "bf2_sample_quality_allowed",
        "bf2_p2_allowed",
    ):
        if name not in case_out_fields:
            case_out_fields.append(name)
    case_path = target_output / "R5_bundle17r_bf2_case_matrix.csv"
    dump_csv(case_path, case_out_fields, case_rows)
    written.append(case_path)

    inventory_fields = [
        "case_id",
        "work_order_id",
        "receipt_sha256",
        "source_path",
        "source_sha256",
        "disposition",
        "promotion_target",
        "reason",
    ]
    inventory_path = target_output / "R5_bundle17r_bf2_artifact_inventory.csv"
    inventory_rows = sorted(
        promotion_rows + archive_rows + rejected_rows,
        key=lambda row: (str(row["case_id"]), str(row["work_order_id"]), str(row["source_path"])),
    )
    dump_csv(inventory_path, inventory_fields, inventory_rows)
    written.append(inventory_path)

    promotion_manifest = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "R5_bundle17r_bf2_promotion_manifest",
        "entries": sorted(
            promotion_rows,
            key=lambda row: (str(row["promotion_target"]), str(row["source_sha256"])),
        ),
        "mutation_authorized": False,
        "instruction": (
            "Copy only after exact-hash human review; this manifest never mutates the repo."
        ),
    }
    promotion_path = target_output / "R5_bundle17r_bf2_promotion_manifest.yaml"
    dump_yaml(promotion_path, promotion_manifest)
    written.append(promotion_path)

    archive_manifest = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "R5_bundle17r_bf2_archive_manifest",
        "entries": sorted(archive_rows, key=lambda row: str(row["source_path"])),
        "repository_commit_allowed": False,
    }
    archive_path = target_output / "R5_bundle17r_bf2_archive_manifest.yaml"
    dump_yaml(archive_path, archive_manifest)
    written.append(archive_path)

    rejected_path = target_output / "R5_bundle17r_bf2_rejected_artifacts.csv"
    dump_csv(rejected_path, inventory_fields, rejected_rows)
    written.append(rejected_path)

    handoff_dir = target_output / "review_handoffs"
    for handoff in handoffs:
        handoff_path = handoff_dir / f"{handoff['case_id']}.yaml"
        dump_yaml(handoff_path, handoff)
        written.append(handoff_path)

    status_proposal = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "R5_bundle17r_bf2_status_proposal",
        "decision": decision,
        "next_stage": next_stage,
        "case_count": len(case_rows),
        "engineering_pass_count": engineering_pass_count,
        "exact_hash_review_accepted_count": accepted_review_count,
        "source_blocker_occurrence_count": blocker_count,
        "resolved_blocker_occurrence_count": len(resolved_issue_ids),
        "unresolved_blocker_occurrence_count": unresolved_count,
        "canonical_state_mutation_allowed": False,
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
    status_path = target_output / "R5_bundle17r_bf2_status_proposal.yaml"
    dump_yaml(status_path, status_proposal)
    written.append(status_path)

    readout_lines = [
        "# R5 Bundle 17R-BF2 close readout",
        "",
        f"- Decision: `{decision}`",
        f"- Next stage proposal: `{next_stage}`",
        f"- Cases: {len(case_rows)}",
        f"- Engineering-pass cases: {engineering_pass_count}",
        f"- Exact-hash reviews accepted: {accepted_review_count}",
        f"- Source blocker occurrences: {blocker_count}",
        f"- Resolved blocker occurrences: {len(resolved_issue_ids)}",
        f"- Unresolved blocker occurrences: {unresolved_count}",
        f"- Repo-candidate artifacts: {len(promotion_rows)}",
        f"- Archive-only artifacts: {len(archive_rows)}",
        f"- Rejected artifacts: {len(rejected_rows)}",
        "- Canonical workflow-state mutation: **not authorized**",
        "- Sample-quality release: **not authorized**",
        "- P2 release: **not authorized**",
        "",
        "The source issue ledger is occurrence-preserving.  A blocker is marked resolved only when",
        (
            "its owning work order has an exact-hash engineering-pass receipt.  "
            "ZIP files, screenshots,"
        ),
        (
            "logs, caches, temporary files and secret-like paths are never placed "
            "in the promotion manifest."
        ),
        "",
    ]
    readout_path = target_output / "R5_bundle17r_bf2_close_readout.md"
    readout_path.write_text("\n".join(readout_lines), encoding="utf-8")
    written.append(readout_path)

    validation = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "R5_bundle17r_bf2_validation_report",
        "input_lock_valid": True,
        "source_blocker_occurrences_preserved": len(updated_issues) == len(issue_rows),
        "orphan_result_count": 0,
        "rejected_artifact_count": len(rejected_rows),
        "manual_or_pending_receipt_count": sum(
            item["receipt_status"] in {"pending", "manual_pending"} for item in receipt_dicts
        ),
        "fail_closed": True,
    }
    validation_path = target_output / "R5_bundle17r_bf2_validation_report.json"
    dump_json(validation_path, validation)
    written.append(validation_path)

    lock_metadata = {
        "bundle_id": metadata["bundle_id"],
        "source_baseline_commit": metadata["source_baseline_commit"],
        "source_bf1_generation_lock_sha256": sha256_file(lock_path),
        "manifest_sha256": metadata["manifest_sha256"],
    }
    generation_lock = build_generation_lock(target_output, written, lock_metadata)
    generation_lock_path = target_output / "R5_bundle17r_bf2_generation_lock.json"
    dump_json(generation_lock_path, generation_lock)
    written.append(generation_lock_path)

    manual_count = validation["manual_or_pending_receipt_count"]
    if fail_on_manual_route and manual_count:
        raise BackflowExecutionError(
            f"{manual_count} work orders still require manual or pending execution routes"
        )

    return {
        "output_dir": target_output,
        "status_proposal": status_proposal,
        "generation_lock": generation_lock,
        "written_files": written,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compile exact-hash Bundle 17R backflow execution receipts without state mutation."
        )
    )
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--fail-on-manual-route", action="store_true")
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
        result = run_execution(
            args.repo_root,
            manifest_path,
            output_dir,
            fail_on_manual_route=args.fail_on_manual_route,
        )
    except (BackflowExecutionError, OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"ERROR: {exc}")
        return 2
    proposal = result["status_proposal"]
    print(
        "OK: "
        f"decision={proposal['decision']} "
        f"resolved={proposal['resolved_blocker_occurrence_count']} "
        f"unresolved={proposal['unresolved_blocker_occurrence_count']} "
        f"output={result['output_dir']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
