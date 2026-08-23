#!/usr/bin/env python3
"""Run the active Research control-plane smoke checks through one wrapper.

The filename is retained for compatibility; legacy Patch/Bundle manifests are
not inputs to the default command.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def default_steps(python: str, strict: bool) -> list[dict[str, Any]]:
    del strict  # Current control-plane checks are always blocking.
    current_state = (
        "reports/workflow_runs/"
        "wf_20260725_stock_first_002837_v1_policy_refresh/workflow_state.yaml"
    )
    return [
        {
            "name": "r5_artifact_format_guard",
            "command": [
                python,
                "scripts/check_r5_artifact_format.py",
                "--strict",
            ],
            "artifact_outputs": [],
            "trust_boundary_note": "current artifact format and gate-of-gates checks remain blocking",
        },
        {
            "name": "doc_drift",
            "command": [python, "scripts/check_doc_drift.py"],
            "artifact_outputs": [],
            "trust_boundary_note": "canonical documentation owners and retention manifest must agree",
        },
        {
            "name": "current_pointer_truthfulness",
            "command": [
                python,
                "scripts/check_r5_readout_truthfulness.py",
                "--rules",
                "config/r5_readout_truthfulness_rules.yaml",
                "--strict",
            ],
            "artifact_outputs": [],
            "trust_boundary_note": "only current_runs may select an active state/readout",
        },
        {
            "name": "current_workflow_state",
            "command": [
                python,
                ".agents/skills/research-orchestrator/scripts/validate_workflow_state.py",
                current_state,
            ],
            "artifact_outputs": [],
            "trust_boundary_note": "canonical workflow-state validator remains authoritative",
        },
        {
            "name": "source_route_quality",
            "command": [
                python,
                "scripts/run_source_route_quality_gate.py",
                "--import-check",
            ],
            "artifact_outputs": ["reports/quality/source_route_quality_report.yaml"],
            "trust_boundary_note": "operational adapter proof is read from reports/quality",
        },
        {
            "name": "active_routing_retirement",
            "command": [
                python,
                "-m",
                "pytest",
                "-q",
                "tests/test_r5_v1_active_routing_retirement.py",
                "--tb=short",
            ],
            "artifact_outputs": [],
            "trust_boundary_note": "retired governance paths cannot re-enter active routing",
        },
        {
            "name": "research_pack_contracts",
            "command": [
                python,
                "-m",
                "pytest",
                "-q",
                "tests/test_validate_r5_stock_research_pack.py",
                "tests/test_validate_segment_exposure.py",
                "tests/test_validate_quality_issues.py",
                "tests/test_validate_r5_forecast_model.py",
                "tests/test_validate_r5_valuation_pack.py",
                "--tb=short",
            ],
            "artifact_outputs": [],
            "trust_boundary_note": "current research pack validators retain fail-closed semantics",
        },
        {
            "name": "current_research_fixture_smoke",
            "command": [
                python,
                "-m",
                "pytest",
                "-q",
                "tests/test_compose_r5_report_from_pack.py",
                "tests/test_r5_mvp_fixture_smoke.py",
                "tests/test_r5_stock_led_smoke_dry_run.py",
                "--tb=short",
            ],
            "artifact_outputs": [],
            "trust_boundary_note": "composer and stock-led fixtures remain part of the current smoke contract",
        },
    ]

def _tail(text: str, limit: int = 20) -> str:
    return "\n".join(text.splitlines()[-limit:])


def summarize_output(stdout: str, stderr: str, limit: int = 10) -> str:
    lines = [line for line in [*stdout.splitlines(), *stderr.splitlines()] if line.strip()]
    return "\n".join(lines[-limit:])


def run_step(step: dict[str, Any], cwd: Path) -> dict[str, Any]:
    start = time.perf_counter()
    completed = subprocess.run(
        step["command"],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    duration = time.perf_counter() - start
    return {
        "name": step["name"],
        "command": step["command"],
        "exit_code": completed.returncode,
        "duration_seconds": round(duration, 3),
        "summary": summarize_output(completed.stdout, completed.stderr),
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "artifact_outputs": step.get("artifact_outputs", []),
        "trust_boundary_note": step.get("trust_boundary_note", ""),
    }


def run_steps(steps: list[dict[str, Any]], cwd: Path) -> dict[str, Any]:
    results = [run_step(step, cwd) for step in steps]
    failures = [result for result in results if result["exit_code"] != 0]
    return {
        "status": "fail" if failures else "pass",
        "failed": len(failures),
        "checked": len(results),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(cwd),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "platform": platform.platform(),
        "steps": results,
        "results": results,
    }


def write_json(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def emit_report(report: dict[str, Any]) -> None:
    print(f"research_control_smoke_status={report['status']} checked={report['checked']} failed={report['failed']}")
    for result in report["results"]:
        print(f"[{result['name']}] exit_code={result['exit_code']} duration={result['duration_seconds']}s")
        if result["summary"]:
            print(result["summary"])
        if result["stderr"]:
            print(result["stderr"], file=sys.stderr, end="" if result["stderr"].endswith("\n") else "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the active Research control-plane smoke suite.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--strict", action="store_true", help="Run advisory gates in blocking mode.")
    parser.add_argument("--json", type=Path, help="Optional JSON output path.")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    report = run_steps(default_steps(args.python, args.strict), repo_root)
    if args.json:
        write_json(args.json, report)
    emit_report(report)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
