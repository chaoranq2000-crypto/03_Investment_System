#!/usr/bin/env python3
"""Check active docs/skills for workflow interface drift.

This is intentionally lightweight. It is not a Markdown linter and does not
inspect historical plans/logs/tasks.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

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
RETENTION_STATUSES = {
    "KEEP_ACTIVE",
    "KEEP_EVIDENCE",
    "LEGACY_BOUND",
    "READY_FOR_MANUAL_DELETE",
    "USER_DECISION",
}


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


def check_retention_manifest(errors: list[str]) -> None:
    path = REPO_ROOT / RETENTION_MANIFEST
    if not path.is_file():
        errors.append(f"{RETENTION_MANIFEST}: missing canonical retention manifest")
        return
    try:
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        fail(errors, path, f"invalid YAML: {exc}")
        return
    if not isinstance(manifest, dict):
        fail(errors, path, "manifest must be a mapping")
        return
    if manifest.get("schema_version") != "docs_reports_retention_dependency_manifest_v1":
        fail(errors, path, "unexpected schema_version")
    if set(manifest.get("status_definitions", {})) != RETENTION_STATUSES:
        fail(errors, path, "status vocabulary must be exact")

    control = manifest.get("deletion_control", {})
    if control.get("codex_delete_authorized") is not False:
        fail(errors, path, "Codex deletion must remain unauthorized")
    if control.get("directories_authorized") is not False:
        fail(errors, path, "directory deletion must remain unauthorized")

    ready_items: list[dict[str, object]] = []
    ready_closure_by_path: dict[str, str] = {}
    candidate_status: dict[str, str] = {}
    seen: set[str] = set()
    for group in manifest.get("candidate_groups", []):
        if not isinstance(group, dict) or group.get("status") not in RETENTION_STATUSES:
            fail(errors, path, "candidate group has invalid status")
            continue
        for item in group.get("items", []):
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                fail(errors, path, "candidate item must have a string path")
                continue
            value = item["path"]
            pure = PurePosixPath(value)
            if value != pure.as_posix() or pure.is_absolute() or ".." in pure.parts:
                fail(errors, path, f"unsafe candidate path: {value}")
            if any(token in value for token in ("*", "?", "[", "]", "{", "}")):
                fail(errors, path, f"candidate path is not literal: {value}")
            if value in seen:
                fail(errors, path, f"duplicate candidate path: {value}")
            seen.add(value)
            candidate_status[value] = str(group.get("status"))
            recovery = item.get("recovery_basis", {})
            if not isinstance(recovery, dict) or recovery.get("kind") != "git_blob":
                fail(errors, path, f"candidate lacks Git recovery basis: {value}")
            if not isinstance(item.get("blob_oid"), str):
                fail(errors, path, f"candidate lacks blob OID: {value}")
            if not isinstance(item.get("byte_count"), int):
                fail(errors, path, f"candidate lacks byte count: {value}")
            if not re.fullmatch(r"[0-9a-f]{64}", str(item.get("content_sha256", ""))):
                fail(errors, path, f"candidate lacks SHA-256: {value}")
            if group.get("status") == "READY_FOR_MANUAL_DELETE":
                closure_id = item.get("closure_id", group.get("closure_id"))
                if not isinstance(closure_id, str) or not closure_id:
                    fail(errors, path, f"READY candidate lacks closure id: {value}")
                else:
                    ready_closure_by_path[value] = closure_id
                ready_items.append(item)

    ready_paths = {str(item["path"]) for item in ready_items}
    for protected in manifest.get("protected_paths", []):
        if not isinstance(protected, dict):
            fail(errors, path, "protected path entry must be a mapping")
            continue
        exact = protected.get("path")
        if isinstance(exact, str) and exact in ready_paths:
            fail(errors, path, f"protected path is marked READY: {exact}")
        prefix = protected.get("path_prefix")
        if isinstance(prefix, str):
            normalized = prefix.rstrip("/") + "/"
            conflict = next(
                (candidate for candidate in ready_paths if candidate.startswith(normalized)),
                None,
            )
            if conflict:
                fail(errors, path, f"protected prefix contains READY path: {conflict}")

    expected_summary = {
        "file_count": len(ready_items),
        "byte_count": sum(int(item.get("byte_count", -1)) for item in ready_items),
    }
    if (
        manifest.get("summary", {}).get("READY_FOR_MANUAL_DELETE_ALL_PHASES")
        != expected_summary
    ):
        fail(errors, path, "READY aggregate does not match exact item list")

    resolution = manifest.get("classification_resolution", {})
    scope = resolution.get("scope", {}) if isinstance(resolution, dict) else {}
    baseline = scope.get("baseline_commit")
    if baseline != manifest.get("audit", {}).get("baseline_commit"):
        fail(errors, path, "classification baseline must equal audit baseline")
        return

    protected_exact: dict[str, str] = {}
    protected_prefixes: list[tuple[str, str]] = []
    for entry in manifest.get("protected_paths", []):
        if not isinstance(entry, dict) or entry.get("status") not in RETENTION_STATUSES:
            continue
        if isinstance(entry.get("path"), str):
            exact = entry["path"]
            previous = protected_exact.setdefault(exact, entry["status"])
            if previous != entry["status"]:
                fail(errors, path, f"conflicting protected exact status: {exact}")
        elif isinstance(entry.get("path_prefix"), str):
            protected_prefixes.append((entry["path_prefix"], entry["status"]))

    defaults: list[tuple[str, str]] = []
    rule_ids: set[str] = set()
    for rule in manifest.get("classification_defaults", []):
        if not isinstance(rule, dict):
            fail(errors, path, "classification default must be a mapping")
            continue
        rule_id = rule.get("rule_id")
        prefix = rule.get("path_prefix")
        status = rule.get("status")
        if not isinstance(rule_id, str) or rule_id in rule_ids:
            fail(errors, path, f"invalid or duplicate classification rule id: {rule_id}")
            continue
        rule_ids.add(rule_id)
        if not isinstance(prefix, str) or not prefix.endswith("/"):
            fail(errors, path, f"classification rule must use a directory prefix: {rule_id}")
            continue
        if any(token in prefix for token in ("*", "?", "[", "]", "{", "}")):
            fail(errors, path, f"classification prefix must be literal: {prefix}")
        if status not in RETENTION_STATUSES:
            fail(errors, path, f"classification rule has invalid status: {rule_id}")
            continue
        defaults.append((prefix, status))

    def longest_prefix_status(
        relative: str,
        rules: list[tuple[str, str]],
        label: str,
    ) -> str | None:
        matches = [(len(prefix), status) for prefix, status in rules if relative.startswith(prefix)]
        if not matches:
            return None
        longest = max(length for length, _ in matches)
        statuses = {status for length, status in matches if length == longest}
        if len(statuses) != 1:
            fail(errors, path, f"equal-specificity {label} conflict: {relative}")
            return None
        return statuses.pop()

    def effective_status(relative: str) -> str | None:
        if relative in candidate_status:
            return candidate_status[relative]
        if relative in protected_exact:
            return protected_exact[relative]
        protected = longest_prefix_status(relative, protected_prefixes, "protected prefix")
        if protected is not None:
            return protected
        return longest_prefix_status(relative, defaults, "classification prefix")

    try:
        inventory_rows = [
            line for line in git_output("ls-tree", "-r", "--name-only", str(baseline), "--", "docs", "reports").splitlines()
            if line
        ]
        size_rows = git_output(
            "cat-file",
            "--batch-check=%(objectsize)",
            input_text="".join(f"{baseline}:{relative}\n" for relative in inventory_rows),
        ).splitlines()
    except (OSError, subprocess.CalledProcessError) as exc:
        fail(errors, path, f"cannot read classification baseline: {exc}")
        return
    if len(inventory_rows) != len(size_rows):
        fail(errors, path, "baseline path/size vectors have different lengths")
        return

    effective: dict[str, tuple[str, int]] = {}
    for relative, size_text in zip(inventory_rows, size_rows, strict=True):
        status = effective_status(relative)
        if status is None:
            fail(errors, path, f"unclassified baseline path: {relative}")
            continue
        effective[relative] = (status, int(size_text))

    expected_count = int(scope.get("expected_file_count", -1))
    expected_bytes = int(scope.get("expected_git_blob_bytes", -1))
    if len(inventory_rows) != expected_count:
        fail(errors, path, "baseline inventory file count drifted")
    if sum(int(size) for size in size_rows) != expected_bytes:
        fail(errors, path, "baseline inventory byte count drifted")
    manifest_self = scope.get("manifest_self", {})
    if manifest_self.get("path") != RETENTION_MANIFEST.as_posix():
        fail(errors, path, "manifest self exception is missing")
    if protected_exact.get(RETENTION_MANIFEST.as_posix()) != "KEEP_ACTIVE":
        fail(errors, path, "manifest self must be explicitly KEEP_ACTIVE")

    calculated: dict[str, dict[str, int]] = {}
    for status in RETENTION_STATUSES:
        rows = [size for value, size in effective.values() if value == status]
        calculated[status] = {
            "file_count": len(rows),
            "git_blob_bytes": sum(rows),
        }
    if resolution.get("effective_summary") != calculated:
        fail(errors, path, "effective docs/reports classification summary drifted")
    if sum(row["file_count"] for row in calculated.values()) != expected_count:
        fail(errors, path, "effective classification does not cover every baseline file")

    ready_by_path = {str(item["path"]): item for item in ready_items}
    for target, item in ready_by_path.items():
        for reference in item.get("inbound_references", []):
            source = reference.get("source_path")
            relation = reference.get("relation")
            if relation == "self_reference" and source != target:
                fail(errors, path, f"invalid self reference: {target}")
            if relation == "closure_internal":
                if source not in ready_by_path:
                    fail(errors, path, f"closure-internal source is not READY: {source}")
                elif ready_closure_by_path.get(source) != ready_closure_by_path.get(target):
                    fail(errors, path, f"closure-internal edge crosses closures: {source} -> {target}")

    grouped: dict[str, list[str]] = {}
    for relative, closure_id in ready_closure_by_path.items():
        grouped.setdefault(closure_id, []).append(relative)
    declared_rows = manifest.get("manual_delete_closures", [])
    if not isinstance(declared_rows, list):
        fail(errors, path, "manual delete closures must be a list")
        declared_rows = []
    declared: dict[str, dict[str, object]] = {}
    for row in declared_rows:
        if not isinstance(row, dict) or not isinstance(row.get("closure_id"), str):
            fail(errors, path, "manual delete closure must have a string id")
            continue
        closure_id = str(row["closure_id"])
        if closure_id in declared:
            fail(errors, path, f"duplicate manual delete closure: {closure_id}")
            continue
        declared[closure_id] = row
    if set(declared) != set(grouped):
        fail(errors, path, "manual delete closure id set drifted")
    for closure_id, rows in grouped.items():
        rows.sort()
        declared_row = declared.get(closure_id, {})
        expected = {
            "all_or_none": True,
            "file_count": len(rows),
            "byte_count": sum(int(ready_by_path[relative]["byte_count"]) for relative in rows),
            "first_path": rows[0],
        }
        if any(declared_row.get(key) != value for key, value in expected.items()):
            fail(errors, path, f"manual delete closure aggregate drifted: {closure_id}")

    phase2 = manifest.get("phase2_retirement", {})
    if not isinstance(phase2, dict) or phase2.get("status") != "awaiting_user_approval":
        fail(errors, path, "Phase 2 must remain at the user approval gate")
        return
    gate = phase2.get("approval_gate", {})
    if gate.get("user_approved") is not False:
        fail(errors, path, "Phase 2 approval must remain false")
    if gate.get("approved_closure_ids") != [] or gate.get("approved_exact_paths") != []:
        fail(errors, path, "Phase 2 approval lists must remain empty")
    if gate.get("codex_quarantine_move_authorized") is not False:
        fail(errors, path, "Phase 2 quarantine move must remain unauthorized")
    phase2_closures = phase2.get("closures", {})
    if not isinstance(phase2_closures, dict):
        fail(errors, path, "Phase 2 closures must be a mapping")
        return
    phase2_paths: set[str] = set()
    for closure_id, row in phase2_closures.items():
        exact_paths = row.get("exact_paths", []) if isinstance(row, dict) else []
        if not isinstance(exact_paths, list) or len(exact_paths) != len(set(exact_paths)):
            fail(errors, path, f"Phase 2 closure path list is invalid: {closure_id}")
            continue
        expected_paths = {
            relative
            for relative, candidate_closure in ready_closure_by_path.items()
            if candidate_closure == closure_id
        }
        if set(exact_paths) != expected_paths:
            fail(errors, path, f"Phase 2 exact path closure drifted: {closure_id}")
        if phase2_paths.intersection(exact_paths):
            fail(errors, path, f"Phase 2 closures overlap: {closure_id}")
        phase2_paths.update(exact_paths)
    scope_total = phase2.get("scope", {}).get("total", {})
    if len(phase2_paths) != scope_total.get("file_count"):
        fail(errors, path, "Phase 2 scope file count drifted")
    if sum(int(ready_by_path[relative]["byte_count"]) for relative in phase2_paths) != scope_total.get(
        "git_blob_bytes"
    ):
        fail(errors, path, "Phase 2 scope byte count drifted")


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
