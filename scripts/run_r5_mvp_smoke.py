#!/usr/bin/env python3
"""Run the R5 MVP smoke checks through one wrapper command."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def default_steps(python: str, strict: bool) -> list[dict[str, Any]]:
    inventory_command = [
        python,
        "scripts/r5_patch_inventory_check.py",
        "--config",
        "config/r5_patch_1_12_expected_artifacts.yaml",
        "--out",
        "reports/p1_6/r5_patch_1_12_inventory_status.yaml",
    ]
    truthfulness_command = [
        python,
        "scripts/check_r5_readout_truthfulness.py",
        "--rules",
        "config/r5_readout_truthfulness_rules.yaml",
        "--glob",
        "reports/p1_6/R5_PATCH_*_READOUT.md",
    ]
    if strict:
        inventory_command.append("--strict")
        truthfulness_command.append("--strict")

    return [
        {
            "name": "r5_artifact_format_guard",
            "command": [python, "scripts/check_r5_artifact_format.py", "--strict"],
        },
        {
            "name": "r5_patch_inventory_check",
            "command": inventory_command,
        },
        {
            "name": "r5_pack_validators",
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
        },
        {
            "name": "r5_composer_fixture_smoke",
            "command": [
                python,
                "-m",
                "pytest",
                "-q",
                "tests/test_compose_r5_report_from_pack.py",
                "tests/test_r5_mvp_fixture_smoke.py",
                "--tb=short",
            ],
        },
        {
            "name": "r5_quality_fixture_smoke",
            "command": [
                python,
                "-m",
                "pytest",
                "-q",
                "tests/test_r5_stock_led_smoke_dry_run.py",
                "--tb=short",
            ],
        },
        {
            "name": "r5_readout_truthfulness_gate",
            "command": truthfulness_command,
        },
    ]


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
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def run_steps(steps: list[dict[str, Any]], cwd: Path) -> dict[str, Any]:
    results = [run_step(step, cwd) for step in steps]
    failures = [result for result in results if result["exit_code"] != 0]
    return {
        "status": "fail" if failures else "pass",
        "failed": len(failures),
        "checked": len(results),
        "results": results,
    }


def write_json(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def emit_report(report: dict[str, Any]) -> None:
    print(f"r5_mvp_smoke_status={report['status']} checked={report['checked']} failed={report['failed']}")
    for result in report["results"]:
        print(f"[{result['name']}] exit_code={result['exit_code']} duration={result['duration_seconds']}s")
        if result["summary"]:
            print(result["summary"])
        if result["stderr"]:
            print(result["stderr"], file=sys.stderr, end="" if result["stderr"].endswith("\n") else "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the R5 MVP smoke suite.")
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
