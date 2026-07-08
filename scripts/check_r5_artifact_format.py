#!/usr/bin/env python3
"""Guard R5 artifacts against formatting and parser regressions."""
from __future__ import annotations

import argparse
import ast
import json
import py_compile
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


@dataclass(frozen=True)
class ArtifactRule:
    path: str
    artifact_type: str
    min_lines: int = 2
    min_headings: int = 0
    requires_cli_help: bool = False


@dataclass
class ArtifactResult:
    path: str
    artifact_type: str
    status: str
    line_count: int | None
    issues: list[str]


R5_YAML_RULES = [
    ArtifactRule("templates/r5_stock_research_pack.yaml", "yaml", min_lines=8),
    ArtifactRule("benchmarks/r5_report_quality_rubric.yaml", "yaml", min_lines=8),
    ArtifactRule(
        ".agents/skills/stock-deep-dive/assets/r5_stock_research_pack.valid.example.yaml",
        "yaml",
        min_lines=8,
    ),
    ArtifactRule(
        ".agents/skills/stock-deep-dive/assets/r5_stock_research_pack.example.yaml",
        "yaml",
        min_lines=8,
    ),
]

R5_MARKDOWN_RULES = [
    ArtifactRule("templates/r5_stock_research_note.md", "markdown", min_lines=8, min_headings=8),
    ArtifactRule(
        "docs/workflows/R5_SAMPLE_QUALITY_STOCK_REPORT_SPEC.md",
        "markdown",
        min_lines=8,
        min_headings=6,
    ),
    ArtifactRule("docs/workflows/R5_MVP_RESTRUCTURE_PLAN.md", "markdown", min_lines=8, min_headings=6),
]

R5_PYTHON_RULES = [
    ArtifactRule(".agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py", "python"),
    ArtifactRule(".agents/skills/segment-company-mapping/scripts/validate_segment_exposure.py", "python"),
    ArtifactRule(".agents/skills/quality-review/scripts/validate_quality_issues.py", "python"),
    ArtifactRule("src/research/forecast_model_builder.py", "python"),
    ArtifactRule("src/research/technical_snapshot_builder.py", "python"),
    ArtifactRule("src/report/stock_report_writer.py", "python"),
    ArtifactRule("src/qa/stock_report_quality_review.py", "python"),
]

R5_GATE_OF_GATES_RULES = [
    ArtifactRule("scripts/check_r5_artifact_format.py", "python", min_lines=8, requires_cli_help=True),
    ArtifactRule("scripts/r5_patch_inventory_check.py", "python", min_lines=8, requires_cli_help=True),
    ArtifactRule("scripts/check_r5_readout_truthfulness.py", "python", min_lines=8, requires_cli_help=True),
    ArtifactRule("scripts/run_r5_mvp_smoke.py", "python", min_lines=8, requires_cli_help=True),
    ArtifactRule("scripts/r5_readiness_gate.py", "python", min_lines=8, requires_cli_help=True),
]

R5_TEST_RULES = [
    ArtifactRule("tests/test_r5_patch0_artifacts_parse.py", "pytest"),
    ArtifactRule("tests/test_validate_r5_stock_research_pack.py", "pytest"),
    ArtifactRule("tests/test_validate_segment_exposure.py", "pytest"),
    ArtifactRule("tests/test_stock_report_writer.py", "pytest"),
    ArtifactRule("tests/test_stock_report_quality_review.py", "pytest"),
]

DEFAULT_RULES = [*R5_GATE_OF_GATES_RULES, *R5_YAML_RULES, *R5_MARKDOWN_RULES, *R5_PYTHON_RULES, *R5_TEST_RULES]


def _line_count(text: str) -> int:
    return len(text.splitlines())


def _has_literal_newline_blob(text: str, line_count: int) -> bool:
    literal_count = text.count("\\n")
    return literal_count >= 6 and literal_count >= max(6, line_count * 2)


def _check_common(path: Path, text: str, rule: ArtifactRule, issues: list[str]) -> None:
    line_count = _line_count(text)
    if line_count < rule.min_lines:
        issues.append(f"line_count {line_count} is below minimum {rule.min_lines}")
    if text.startswith("#!") and line_count < 2:
        issues.append("shebang is not followed by a real newline")
    first_line = text.splitlines()[0] if text.splitlines() else ""
    if first_line.startswith("#!") and re.search(r"\b(from|import|def|class)\b", first_line):
        issues.append("shebang line appears to swallow Python code")
    if _has_literal_newline_blob(text, line_count):
        issues.append("large-scale literal \\\\n sequence detected instead of real line breaks")
    if path.suffix == ".py" and line_count <= 1:
        issues.append("python artifact is a one-line blob")
    if path.suffix == ".py" and line_count <= 2 and re.search(r"\b(import|def|class)\b.+\b(import|def|class)\b", text):
        issues.append("python artifact appears to contain a one-line import/def/class blob")
    if path.suffix in {".yaml", ".yml"} and line_count <= 1:
        issues.append("yaml artifact is a one-line blob")


def _check_yaml(path: Path, issues: list[str]) -> None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except Exception as exc:  # noqa: BLE001
        issues.append(f"yaml_parse failed: {exc}")
        return
    if data is None:
        issues.append("yaml_parse returned empty document")


def _check_python(path: Path, issues: list[str]) -> None:
    source = path.read_text(encoding="utf-8")
    try:
        py_compile.compile(str(path), doraise=True)
    except py_compile.PyCompileError as exc:
        issues.append(f"py_compile failed: {exc.msg}")
        return
    try:
        module = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        issues.append(f"ast_parse failed: {exc}")
        return
    if not module.body:
        issues.append("python module AST is empty")
    elif all(
        isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant)
        for node in module.body
    ):
        issues.append("python module contains only comments/docstrings/constants")


def _check_cli_help(repo_root: Path, path: Path, issues: list[str]) -> None:
    rel_path = path.relative_to(repo_root)
    try:
        completed = subprocess.run(
            [sys.executable, str(rel_path), "--help"],
            cwd=str(repo_root),
            text=True,
            capture_output=True,
            check=False,
            timeout=20,
        )
    except Exception as exc:  # noqa: BLE001
        issues.append(f"--help execution failed: {exc}")
        return
    if completed.returncode != 0:
        tail = "\n".join([*completed.stdout.splitlines(), *completed.stderr.splitlines()][-5:])
        issues.append(f"--help exit_code {completed.returncode}; tail={tail}")


def _check_markdown(text: str, rule: ArtifactRule, issues: list[str]) -> None:
    heading_count = len(re.findall(r"^#{1,6}\s+", text, flags=re.MULTILINE))
    if heading_count < rule.min_headings:
        issues.append(f"heading_count {heading_count} is below minimum {rule.min_headings}")


def _check_pytest(text: str, issues: list[str]) -> None:
    if not re.search(r"^\s*def\s+test_", text, flags=re.MULTILINE) and not re.search(
        r"^\s*class\s+Test[A-Za-z0-9_]*", text, flags=re.MULTILINE
    ):
        issues.append("pytest file has no test function or pytest-style Test class")


def check_artifact(repo_root: Path, rule: ArtifactRule) -> ArtifactResult:
    path = repo_root / rule.path
    issues: list[str] = []
    if not path.exists():
        return ArtifactResult(rule.path, rule.artifact_type, "fail", None, ["file does not exist"])

    text = path.read_text(encoding="utf-8")
    _check_common(path, text, rule, issues)
    if rule.artifact_type == "yaml":
        _check_yaml(path, issues)
    elif rule.artifact_type == "python":
        _check_python(path, issues)
        if rule.requires_cli_help:
            _check_cli_help(repo_root, path, issues)
    elif rule.artifact_type == "markdown":
        _check_markdown(text, rule, issues)
    elif rule.artifact_type == "pytest":
        _check_python(path, issues)
        _check_pytest(text, issues)
    else:
        issues.append(f"unknown artifact_type: {rule.artifact_type}")

    return ArtifactResult(
        path=rule.path,
        artifact_type=rule.artifact_type,
        status="fail" if issues else "pass",
        line_count=_line_count(text),
        issues=issues,
    )


def run_checks(repo_root: Path, rules: Iterable[ArtifactRule] = DEFAULT_RULES) -> dict[str, Any]:
    results = [check_artifact(repo_root, rule) for rule in rules]
    failed = [result for result in results if result.status == "fail"]
    return {
        "status": "fail" if failed else "pass",
        "checked": len(results),
        "failed": len(failed),
        "passed": len(results) - len(failed),
        "summary": {
            "checked": len(results),
            "failed": len(failed),
            "passed": len(results) - len(failed),
        },
        "artifacts": [asdict(result) for result in results],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check R5 artifact formatting and parseability.")
    parser.add_argument("--repo-root", default=".", help="Repository root. Defaults to the current directory.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero if any artifact fails.")
    parser.add_argument("--json", type=Path, help="Optional path for a JSON report.")
    args = parser.parse_args(argv)

    report = run_checks(Path(args.repo_root).resolve())
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        "status={status} checked={checked} passed={passed} failed={failed}".format(
            status=report["status"],
            checked=report["summary"]["checked"],
            passed=report["summary"]["passed"],
            failed=report["summary"]["failed"],
        )
    )
    for artifact in report["artifacts"]:
        if artifact["status"] == "fail":
            print(f"{artifact['path']}: {', '.join(artifact['issues'])}")

    if args.strict and report["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
