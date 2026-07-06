#!/usr/bin/env python3
"""Check active docs/skills for workflow interface drift.

This is intentionally lightweight. It is not a Markdown linter and does not
inspect historical plans/logs/tasks.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

CANONICAL_WORKFLOW = Path("docs/workflows/RESEARCH_WORKFLOW.md")
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
    high_gate_ids = re.compile(r"\bG(?:1[1-9]|[2-9]\d)\b")

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


def main() -> int:
    errors: list[str] = []
    check_canonical_workflow(errors)
    check_active_files(errors)

    if errors:
        print("Doc drift check failed:\n")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Doc drift check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
