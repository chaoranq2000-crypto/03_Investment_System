#!/usr/bin/env python3
"""Check active docs/skills for workflow interface drift.

This is intentionally lightweight. It is not a Markdown linter and does not
inspect historical plans/logs/tasks.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

CANONICAL_WORKFLOW = Path("docs/workflows/RESEARCH_WORKFLOW.md")
RETENTION_MANIFEST = Path("docs/meta/DOCS_REPORTS_RETENTION_DEPENDENCY_MANIFEST.yaml")
TARGET_PATHS = [
    Path("README.md"),
    Path("AGENTS.md"),
    Path("docs/index.md"),
    Path("docs/workflows"),
    Path("docs/meta"),
    Path("docs/policies"),
    Path("docs/architecture"),
    Path(".agents/skills"),
]
EXCLUDED_PARTS = {
    "docs/plans",
    "docs/logs",
    "docs/codex_tasks",
    "reports",
    "data",
    "notebooks",
    ".git",
    ".venv",
    "venv",
}
TEXT_SUFFIXES = {".md", ".txt", ".yaml", ".yml", ".toml", ".py", ".csv"}

CANONICAL_WORKFLOW_TYPES = {
    "segment_to_stock_closed_loop",
    "stock_first_closed_loop",
    "segment_stock_interlock",
    "refresh_existing_research",
    "comparison_readiness_gate",
}
CANONICAL_GATES = {f"G{i}" for i in range(11)}


def git_output(*args: str, input_text: str | None = None) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=REPO_ROOT,
        input=input_text,
        text=True,
        encoding="utf-8",
    )


def rel(path: Path) -> Path:
    return path.relative_to(REPO_ROOT)


def is_excluded(path: Path) -> bool:
    as_posix = str(rel(path)).replace("\\", "/")
    return any(as_posix == part or as_posix.startswith(part + "/") for part in EXCLUDED_PARTS)


def iter_target_files() -> list[Path]:
    files: list[Path] = []
    for target in TARGET_PATHS:
        root = REPO_ROOT / target
        if not root.exists():
            continue
        if root.is_file():
            if root.suffix in TEXT_SUFFIXES and not is_excluded(root):
                files.append(root)
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in TEXT_SUFFIXES and not is_excluded(path):
                files.append(path)
    script = REPO_ROOT / "scripts" / "check_doc_drift.py"
    if script.exists():
        files.append(script)
    return sorted(set(files))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def fail(errors: list[str], path: Path, message: str) -> None:
    errors.append(f"{rel(path)}: {message}")


def check_canonical_workflow(errors: list[str]) -> None:
    path = REPO_ROOT / CANONICAL_WORKFLOW
    if not path.exists():
        errors.append(f"{CANONICAL_WORKFLOW}: missing canonical workflow file")
        return
    text = read(path)

    for workflow_type in sorted(CANONICAL_WORKFLOW_TYPES):
        if workflow_type not in text:
            fail(errors, path, f"missing canonical workflow_type {workflow_type!r}")

    gate_ids = set(re.findall(r"\bG\d+\b", text))
    missing = CANONICAL_GATES - gate_ids
    if missing:
        fail(errors, path, f"missing canonical gate ids: {', '.join(sorted(missing))}")

    unexpected = {gate for gate in gate_ids if re.fullmatch(r"G\d+", gate) and gate not in CANONICAL_GATES}
    if unexpected:
        fail(errors, path, f"unexpected global gate ids: {', '.join(sorted(unexpected))}")

    if re.search(r"workflow_type\s*:\s*stock_report_production", text):
        fail(errors, path, "must not define stock_report_production as workflow_type")


def check_active_files(errors: list[str]) -> None:
    gate_table_line = re.compile(r"^\s*\|\s*G\d+\b", re.MULTILINE)
    stock_report_workflow_type = re.compile(r"workflow_type\s*:\s*stock_report_production")
    high_gate_ids = re.compile(r"(?<![A-Za-z0-9_-])G(?:1[1-9]|[2-9]\d)\b")

    for path in iter_target_files():
        text = read(path)
        relative = rel(path)
        is_canonical = relative == CANONICAL_WORKFLOW

        if stock_report_workflow_type.search(text):
            fail(errors, path, "active docs must not write stock_report_production as workflow_type")

        if not is_canonical and gate_table_line.search(text):
            fail(errors, path, "global gate table appears outside RESEARCH_WORKFLOW.md")

        high_gates = sorted(set(high_gate_ids.findall(text)))
        if high_gates:
            fail(errors, path, f"unexpected global gate ids outside G0-G10: {', '.join(high_gates)}")

        if relative.match(".agents/skills/*/SKILL.md"):
            if "workflow_type:" in text and "does not redefine" not in text and "不重新定义" not in text:
                fail(errors, path, "SKILL.md mentions workflow_type without anti-redefinition guardrail")


def check_retention_manifest(
    errors: list[str], *, manifest: dict | None = None
) -> None:
    """Validate current protection and retirement boundaries, not old execution receipts."""
    path = REPO_ROOT / RETENTION_MANIFEST
    if manifest is None:
        if not path.is_file():
            fail(errors, path, "missing canonical retention manifest")
            return
        try:
            manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            fail(errors, path, f"invalid YAML: {exc}")
            return
    if not isinstance(manifest, dict):
        fail(errors, path, "manifest must be a mapping")
        return
    if manifest.get("schema_version") != "docs_reports_retention_dependency_manifest_v2":
        fail(errors, path, "unexpected schema_version")
    if manifest.get("status") != "active":
        fail(errors, path, "current retention manifest must be active")
    expected_authority = {
        "project_rules": "AGENTS.md",
        "research_workflow": "docs/workflows/RESEARCH_WORKFLOW.md",
        "document_ownership": "docs/meta/DOC_OWNERSHIP_MATRIX.md",
        "current_run_pointer": "config/r5_readout_canonical_index.yaml.current_runs",
    }
    if manifest.get("authority") != expected_authority:
        fail(errors, path, "current authority chain drifted")
    control = manifest.get("deletion_control", {})
    if control != {
        "codex_delete_authorized": False,
        "directories_authorized": False,
        "execution_actor": "user_manual_delete",
        "prior_approvals_apply_to_new_candidates": False,
    }:
        fail(errors, path, "deletion requires the current manual boundary; old approvals cannot be reused")

    def literal(value, *, prefix=False):
        if not isinstance(value, str) or not value:
            fail(errors, path, "path must be a non-empty string")
            return None
        pure = PurePosixPath(value)
        normalized = pure.as_posix() + ("/" if prefix else "")
        if (
            value != normalized or pure.is_absolute() or PureWindowsPath(value).drive
            or any(part in {".", ".."} for part in pure.parts)
            or any(token in value for token in ("*", "?", "[", "]", "{", "}"))
            or not (REPO_ROOT / pure).resolve().is_relative_to(REPO_ROOT.resolve())
        ):
            fail(errors, path, f"unsafe or non-literal path: {value}")
            return None
        return value

    protected_exact, protected_prefixes = set(), set()
    for row in manifest.get("protected_paths", []):
        if not isinstance(row, dict) or row.get("status") not in {"KEEP_ACTIVE", "KEEP_EVIDENCE"}:
            fail(errors, path, "invalid protected path entry")
            continue
        prefix = "path_prefix" in row
        value = literal(row.get("path_prefix" if prefix else "path"), prefix=prefix)
        if value:
            (protected_prefixes if prefix else protected_exact).add(value)
    if RETENTION_MANIFEST.as_posix() not in protected_exact:
        fail(errors, path, "canonical manifest must protect itself")

    def is_protected(value):
        return value in protected_exact or any(value.startswith(p) for p in protected_prefixes)

    retired = manifest.get("retired_paths", [])
    if not isinstance(retired, list) or not retired or not all(isinstance(x, str) for x in retired):
        fail(errors, path, "retired_paths must be a non-empty string list")
        return
    if len(retired) != len(set(retired)):
        fail(errors, path, "duplicate retired path")
    for value in retired:
        if literal(value) is None:
            continue
        if is_protected(value):
            fail(errors, path, f"protected path is retired: {value}")
        if (REPO_ROOT / value).exists():
            fail(errors, path, f"retired path has reappeared: {value}")
    retired_set = set(retired)
    for row in manifest.get("allowed_retired_references", []):
        source = literal(row.get("source_path"))
        if not source or not (REPO_ROOT / source).is_file():
            fail(errors, path, "declared current reference source is missing")
        if row.get("relation") not in {
            "git_history_only", "historical_cross_reference", "historical_metadata_only",
            "negative_assertion_only", "retained_evidence_reference", "retirement_assertion_only",
        }:
            fail(errors, path, "retired reference cannot be a current physical dependency")
        targets = row.get("targets", [])
        if not targets or not set(targets) <= retired_set or len(targets) != len(set(targets)):
            fail(errors, path, "retired reference targets must be unique registered paths")

    invariants = {row.get("id"): row for row in manifest.get("protected_invariants", [])}
    human = invariants.get("C-HUMAN-005", {})
    database = invariants.get("formal_portfolio_database", {})
    if human.get("status") != "pending" or human.get("effective_machine_value") is not None or human.get("mutation_authorized") is not False:
        fail(errors, path, "C-HUMAN-005 invariant drifted")
    if database.get("access") != "read_only" or database.get("copy_delete_rebuild_authorized") is not False or database.get("tracked_or_manifested_content") is not False:
        fail(errors, path, "formal database protection drifted")

    history = manifest.get("history", {})
    snapshot = history.get("snapshot", {})
    if history.get("storage") != "git_history" or history.get("current_selection_allowed") is not False:
        fail(errors, path, "history cannot select current runs")
    commit = snapshot.get("commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or snapshot.get("path") != RETENTION_MANIFEST.as_posix():
        fail(errors, path, "invalid historical snapshot identity")
    else:
        try:
            payload = subprocess.check_output(
                ["git", "show", f"{commit}:{RETENTION_MANIFEST.as_posix()}"], cwd=REPO_ROOT
            )
            oid = hashlib.sha1(f"blob {len(payload)}\0".encode() + payload, usedforsecurity=False).hexdigest()
            if (oid != snapshot.get("blob_oid") or len(payload) != snapshot.get("git_blob_bytes")
                or hashlib.sha256(payload).hexdigest() != snapshot.get("content_sha256")):
                fail(errors, path, "historical snapshot integrity mismatch")
        except (OSError, subprocess.CalledProcessError):
            fail(errors, path, "historical snapshot is not recoverable from Git")

    seen_candidates = set()
    for row in manifest.get("manual_delete_candidates", []):
        value = literal(row.get("path"))
        if not value:
            continue
        if value in seen_candidates or value in retired_set or is_protected(value):
            fail(errors, path, f"candidate conflicts with retired/protected paths: {value}")
        seen_candidates.add(value)
        if row.get("status") != "READY_FOR_MANUAL_DELETE" or not row.get("reason"):
            fail(errors, path, f"candidate requires a scoped readiness reason: {value}")
        if not re.fullmatch(r"[0-9a-f]{40}", str(row.get("recovery_commit", ""))):
            fail(errors, path, f"candidate requires a fixed Git recovery commit: {value}")
        if not re.fullmatch(r"[0-9a-f]{40}", str(row.get("blob_oid", ""))) or not re.fullmatch(r"[0-9a-f]{64}", str(row.get("content_sha256", ""))):
            fail(errors, path, f"candidate recovery hashes are missing: {value}")
        references = row.get("inbound_references", [])
        if not references:
            fail(errors, path, f"candidate dependency evidence is missing: {value}")
        for reference in references:
            source = literal(reference.get("source_path"))
            relation = reference.get("relation")
            if relation == "self_reference":
                if source != value:
                    fail(errors, path, "candidate self-reference points elsewhere")
            elif relation not in {"git_history_only", "historical_cross_reference", "retirement_assertion_only"}:
                fail(errors, path, "candidate still has a current physical dependency")
            elif source and not (REPO_ROOT / source).is_file():
                fail(errors, path, f"candidate reference source is missing: {source}")
        if (REPO_ROOT / value).is_file():
            oid = git_output("hash-object", f"--path={value}", "--", value).strip()
            if oid != row.get("blob_oid"):
                fail(errors, path, f"candidate changed since dependency audit: {value}")



def main() -> int:
    errors: list[str] = []
    check_canonical_workflow(errors)
    check_active_files(errors)
    check_retention_manifest(errors)

    if errors:
        print("Doc drift check failed:\n")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Doc drift check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
