#!/usr/bin/env python3
"""Check active docs and skill contracts for workflow-definition drift."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ALLOWED_WORKFLOW_TYPES = {
    "segment_to_stock_closed_loop",
    "stock_first_closed_loop",
    "segment_stock_interlock",
    "refresh_existing_research",
    "comparison_readiness_gate",
}

ACTIVE_ROOTS = [
    ROOT / "AGENTS.md",
    ROOT / "README.md",
    ROOT / "docs",
    ROOT / ".agents",
    ROOT / "src",
    ROOT / "tests",
]

EXCLUDED_PARTS = {
    ".git",
    ".conda",
    ".pytest_cache",
    "__pycache__",
    "data",
}

EXCLUDED_PREFIXES = {
    Path("docs/plans"),
    Path("docs/logs"),
    Path("docs/codex_tasks"),
    Path("docs/references/project_learning"),
    Path("reports/workflow_runs"),
}

TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".yaml",
    ".yml",
    ".toml",
    ".txt",
    ".csv",
    ".json",
}

WORKFLOW_TYPE_RE = re.compile(r"^\s*workflow_type\s*:\s*([A-Za-z0-9_-]+)?\s*$")
GATE_TABLE_RE = re.compile(r"^\|\s*(G(?:[0-9]|10))\s*\|")
HIGH_GATE_RE = re.compile(r"\bG1[1-9]\b")
FORBIDDEN_SKILL_HEADINGS = [
    "## 永久工作流类型",
    "## Workflow state 最小字段",
    "## 质量门禁列表",
]


def rel(path: Path) -> Path:
    return path.relative_to(ROOT)


def is_excluded(path: Path) -> bool:
    relative = rel(path)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return True
    return any(relative == prefix or prefix in relative.parents for prefix in EXCLUDED_PREFIXES)


def iter_files() -> list[Path]:
    files: list[Path] = []
    for root in ACTIVE_ROOTS:
        if not root.exists():
            continue
        if root.is_file():
            candidates = [root]
        else:
            candidates = [path for path in root.rglob("*") if path.is_file()]
        for path in candidates:
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if is_excluded(path):
                continue
            files.append(path)
    return sorted(files)


def add_item(
    items: list[dict[str, object]],
    severity: str,
    path: Path,
    line: int,
    rule: str,
    message: str,
) -> None:
    items.append(
        {
            "severity": severity,
            "path": str(rel(path)).replace("\\", "/"),
            "line": line,
            "rule": rule,
            "message": message,
        }
    )


def check_file(path: Path, items: list[dict[str, object]]) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return

    relative = rel(path).as_posix()
    is_research_kernel = relative == "docs/workflows/RESEARCH_WORKFLOW.md"
    is_skill = len(path.parts) >= 3 and path.name == "SKILL.md" and ".agents" in path.parts

    for line_no, line in enumerate(lines, start=1):
        match = WORKFLOW_TYPE_RE.match(line)
        if match:
            value = match.group(1)
            if value and value not in ALLOWED_WORKFLOW_TYPES:
                add_item(
                    items,
                    "error",
                    path,
                    line_no,
                    "workflow_type_enum",
                    f"non-canonical workflow_type: {value}",
                )

        if HIGH_GATE_RE.search(line):
            add_item(
                items,
                "error",
                path,
                line_no,
                "global_gate_above_g10",
                "global gate ids above G10 are not allowed on active contract surfaces",
            )

        if GATE_TABLE_RE.match(line) and not is_research_kernel:
            add_item(
                items,
                "error",
                path,
                line_no,
                "global_gate_table_outside_kernel",
                "global gate table rows must live only in docs/workflows/RESEARCH_WORKFLOW.md",
            )

        if len(line) > 500:
            add_item(
                items,
                "warning",
                path,
                line_no,
                "markdown_long_line",
                "line exceeds 500 characters",
            )

    if is_skill:
        text = "\n".join(lines)
        for heading in FORBIDDEN_SKILL_HEADINGS:
            if heading in text:
                add_item(
                    items,
                    "warning",
                    path,
                    1,
                    "skill_redefines_global_workflow_facts",
                    f"SKILL.md contains forbidden heading: {heading}",
                )


def main() -> int:
    items: list[dict[str, object]] = []
    for path in iter_files():
        check_file(path, items)

    errors = sum(1 for item in items if item["severity"] == "error")
    warnings = sum(1 for item in items if item["severity"] == "warning")
    print(json.dumps({"errors": errors, "warnings": warnings, "items": items}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
