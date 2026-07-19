#!/usr/bin/env python3
"""Build the immutable local-input handoff for R5 Overnight Mission 01.

The source BF2 worktree is read-only.  This utility copies only the mission's
declared input surface into ``.local/night_shift/inputs/<input_set_sha>`` and
records source paths, timestamps, sizes, and SHA-256 digests.  Runtime outputs
remain untracked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Sequence


SCHEMA_VERSION = "r5_night_shift_input_manifest_v1"
BASELINE_SCHEMA_VERSION = "r5_night_shift_baseline_v1"

REQUIRED_INPUTS = (
    "reports/p1_6/r5_bundle17r_bf2/bf2_execution_manifest.yaml",
    "reports/p1_6/r5_bundle17r_bf2/source_bf1/run_a/"
    "R5_bundle17r_backflow_generation_lock.json",
    "reports/p1_6/r5_bundle17r_bf2/source_bf1/run_a/"
    "R5_bundle17r_backflow_work_orders.csv",
    "reports/p1_6/r5_bundle17r_bf2/source_bf1/run_a/"
    "R5_bundle17r_backflow_issue_ledger.csv",
    "reports/p1_6/r5_bundle17r_bf2/source_bf1/run_a/"
    "R5_bundle17r_backflow_case_matrix.csv",
    "reports/p1_6/r5_bundle17r_bf2/source_bf1/run_a/"
    "R5_bundle17r_backflow_compilation.json",
    "reports/p1_6/r5_bundle17r_bf2/source_bf1/run_a/"
    "R5_bundle17r_backflow_dependency_graph.json",
    "reports/p1_6/r5_bundle17r_bf2/source_bf1/run_a/"
    "R5_bundle17r_backflow_execution_batches.yaml",
    ".local/R5_bundle17r_bf2_ex1_manifest.yaml",
    ".local/R5_bundle17r_bf2_execution_manifest_ex1.yaml",
    "reports/p1_6/r5_bundle17r_bf2/run_verified_c/"
    "R5_bundle17r_bf2_execution_receipts.json",
    "reports/p1_6/r5_bundle17r_bf2/run_verified_c/"
    "R5_bundle17r_bf2_generation_lock.json",
    "reports/p1_6/r5_bundle17r_bf2/run_verified_c/"
    "R5_bundle17r_bf2_rejected_artifacts.csv",
    "reports/p1_6/r5_bundle17r_bf2/run_verified_c/"
    "R5_bundle17r_bf2_status_proposal.yaml",
    "reports/p1_6/r5_bundle17r_bf2/run_verified_c/"
    "R5_bundle17r_bf2_validation_report.json",
)

INPUT_GLOBS = (
    "reports/p1_6/r5_bundle17r_bf2/source_bf1/run_a/work_order_handoffs/*.yaml",
    ".local/r5_bundle17r_verified_result_specs/*/spec.yaml",
    ".local/r5_bundle17r_backflow_results_fixed_run_a/*/result.yaml",
)


class HandoffError(RuntimeError):
    """Raised when an immutable handoff cannot be built safely."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise HandoffError(f"git {' '.join(args)} failed in {repo}: {detail}")
    return completed.stdout.strip()


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink()


def discover_inputs(source_root: Path) -> list[Path]:
    discovered: set[Path] = set()
    for relative in REQUIRED_INPUTS:
        path = source_root / PurePosixPath(relative)
        if not path.is_file():
            raise HandoffError(f"required BF2 input is missing: {relative}")
        if path.is_symlink():
            raise HandoffError(f"symlink input is not allowed: {relative}")
        discovered.add(path.resolve())
    for pattern in INPUT_GLOBS:
        matches = sorted(source_root.glob(pattern))
        if not matches:
            raise HandoffError(f"BF2 input glob matched no files: {pattern}")
        for path in matches:
            if not path.is_file() or path.is_symlink():
                raise HandoffError(f"invalid BF2 input: {path}")
            discovered.add(path.resolve())
    return sorted(discovered, key=lambda item: item.relative_to(source_root).as_posix())


def portable_records(source_root: Path, paths: Iterable[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        stat = path.stat()
        records.append(
            {
                "logical_path": path.relative_to(source_root).as_posix(),
                "sha256": sha256_file(path),
                "size_bytes": stat.st_size,
            }
        )
    return records


def compute_input_set_sha(records: Sequence[dict[str, Any]]) -> str:
    return hashlib.sha256(canonical_json_bytes(list(records))).hexdigest()


def copy_immutable_inputs(
    source_root: Path,
    target_root: Path,
    paths: Sequence[Path],
    input_set_sha: str,
) -> list[dict[str, Any]]:
    input_root = target_root / ".local" / "night_shift" / "inputs" / input_set_sha
    records: list[dict[str, Any]] = []
    for source in paths:
        relative = source.relative_to(source_root)
        destination = input_root / relative
        source_hash = sha256_file(source)
        if destination.exists():
            if not destination.is_file() or sha256_file(destination) != source_hash:
                raise HandoffError(
                    f"immutable input destination conflicts with source: {destination}"
                )
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        copied_hash = sha256_file(destination)
        if copied_hash != source_hash:
            raise HandoffError(f"copied input hash mismatch: {relative.as_posix()}")
        stat = source.stat()
        records.append(
            {
                "source_absolute_path": str(source),
                "logical_path": relative.as_posix(),
                "destination_relative_path": destination.relative_to(target_root).as_posix(),
                "size_bytes": stat.st_size,
                "mtime_utc": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
                "sha256": source_hash,
            }
        )
    return records


def build_handoff(
    source_root: Path,
    target_root: Path,
    *,
    expected_sha: str,
    source_branch: str,
    target_branch: str,
    run_id: str,
    package_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    source_root = source_root.resolve()
    target_root = target_root.resolve()
    if source_root == target_root:
        raise HandoffError("source and isolated worktree must be different paths")

    actual_source_branch = git(source_root, "branch", "--show-current")
    source_head = git(source_root, "rev-parse", "HEAD")
    remote_head = git(
        source_root,
        "rev-parse",
        f"refs/remotes/origin/{source_branch}",
    )
    actual_target_branch = git(target_root, "branch", "--show-current")
    target_head = git(target_root, "rev-parse", "HEAD")
    if actual_source_branch != source_branch:
        raise HandoffError(
            f"source branch mismatch: expected {source_branch}, got {actual_source_branch}"
        )
    if actual_target_branch != target_branch:
        raise HandoffError(
            f"target branch mismatch: expected {target_branch}, got {actual_target_branch}"
        )
    for label, value in (
        ("source HEAD", source_head),
        ("remote source HEAD", remote_head),
        ("target baseline HEAD", target_head),
    ):
        if value != expected_sha:
            raise HandoffError(f"{label} mismatch: expected {expected_sha}, got {value}")

    paths = discover_inputs(source_root)
    portable = portable_records(source_root, paths)
    input_set_sha = compute_input_set_sha(portable)
    records = copy_immutable_inputs(
        source_root, target_root, paths, input_set_sha
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "input_set_sha256": input_set_sha,
        "source_root": str(source_root),
        "isolated_worktree": str(target_root),
        "source_commit": source_head,
        "source_branch": source_branch,
        "file_count": len(records),
        "total_size_bytes": sum(item["size_bytes"] for item in records),
        "files": records,
    }
    source_status = git(source_root, "status", "--short").splitlines()
    baseline = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "run_id": run_id,
        "expected_source_sha": expected_sha,
        "local_source_sha": source_head,
        "remote_source_sha": remote_head,
        "target_baseline_sha": target_head,
        "source_branch": source_branch,
        "target_branch": target_branch,
        "source_worktree": str(source_root),
        "isolated_worktree_path": str(target_root),
        "isolated_worktree": True,
        "dirty_source_preserved": bool(source_status),
        "source_status": source_status,
        "input_set_sha256": input_set_sha,
        "package_sha256": package_sha256.lower(),
    }
    night_root = target_root / ".local" / "night_shift"
    atomic_write_json(night_root / "input_manifest.json", manifest)
    atomic_write_json(night_root / "baseline.json", baseline)

    report_dir = target_root / "reports" / "p1_6" / "r5_night_shift" / run_id
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "preflight.md"
    report_path.write_text(
        "\n".join(
            [
                "# R5 Overnight Mission 01 preflight",
                "",
                f"- Run ID: `{run_id}`",
                f"- Source branch: `{source_branch}`",
                f"- Target branch: `{target_branch}`",
                f"- Expected/local/remote SHA: `{expected_sha}`",
                "- Isolated worktree: `true`",
                f"- Source dirty state preserved: `{str(bool(source_status)).lower()}`",
                f"- Immutable input set: `{input_set_sha}`",
                f"- Input files: `{len(records)}`",
                f"- Input bytes: `{sum(item['size_bytes'] for item in records)}`",
                f"- Package SHA-256: `{package_sha256.lower()}`",
                "- Canonical/sample-quality/P2 mutation: `false`",
                "",
                "The source worktree was read only; no source-local BF2 artifact was staged.",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    return manifest, baseline, report_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--target-root", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--source-branch", required=True)
    parser.add_argument("--target-branch", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--package-sha256", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest, _, report_path = build_handoff(
            args.source_root,
            args.target_root,
            expected_sha=args.expected_sha,
            source_branch=args.source_branch,
            target_branch=args.target_branch,
            run_id=args.run_id,
            package_sha256=args.package_sha256,
        )
    except (HandoffError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(
        "OK: "
        f"input_set={manifest['input_set_sha256']} "
        f"files={manifest['file_count']} "
        f"report={report_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
