#!/usr/bin/env python3
"""Validate the current-run pointer and its state/readout truthfulness.

The filename is retained for compatibility. Legacy R5/Patch/Bundle readout
classification is intentionally outside the active control plane.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


DEFAULT_RULES: dict[str, Any] = {
    "canonical_index_path": "config/r5_readout_canonical_index.yaml",
    "required_pointer_fields": ["workflow_id", "state_path", "readout_path"],
    "forbidden_top_level_keys": ["readouts", "policy_migrations"],
    "required_authority": {
        "project_rules": "AGENTS.md",
        "research_workflow": "docs/workflows/RESEARCH_WORKFLOW.md",
        "document_ownership": "docs/meta/DOC_OWNERSHIP_MATRIX.md",
        "retention_manifest": "docs/meta/DOCS_REPORTS_RETENTION_DEPENDENCY_MANIFEST.yaml",
    },
}


def load_rules(path: Path | None) -> dict[str, Any]:
    if path is None:
        return dict(DEFAULT_RULES)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    merged = dict(DEFAULT_RULES)
    merged.update(data)
    return merged


def _load_mapping(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data


def _safe_relative_path(value: object) -> PurePosixPath:
    text = str(value)
    pure = PurePosixPath(text)
    if (
        text != pure.as_posix()
        or pure.is_absolute()
        or ".." in pure.parts
        or not pure.parts
        or pure.parts[0] == ".git"
    ):
        raise ValueError(f"unsafe repository path: {text}")
    return pure


def _readout_field(readout: str, label: str) -> str | None:
    match = re.search(
        rf"(?m)^\s*-\s*{re.escape(label)}:\s*`([^`]+)`\s*$",
        readout,
    )
    return match.group(1) if match else None


def _check_pointer(
    repo_root: Path,
    pointer_name: str,
    pointer: object,
    required_fields: set[str],
) -> dict[str, Any]:
    issues: list[str] = []
    if not isinstance(pointer, dict):
        return {"pointer": pointer_name, "status": "fail", "issues": ["pointer must be a mapping"]}

    if set(pointer) != required_fields:
        issues.append(
            "pointer fields must be exactly " + ", ".join(sorted(required_fields))
        )

    workflow_id = str(pointer.get("workflow_id", ""))
    try:
        state_rel = _safe_relative_path(pointer.get("state_path", ""))
        readout_rel = _safe_relative_path(pointer.get("readout_path", ""))
    except ValueError as exc:
        return {"pointer": pointer_name, "status": "fail", "issues": [str(exc)]}

    expected_root = PurePosixPath("reports/workflow_runs") / workflow_id
    if state_rel != expected_root / "workflow_state.yaml":
        issues.append("state_path must be the run-scoped workflow_state.yaml")
    if readout_rel != expected_root / "workflow_readout.md":
        issues.append("readout_path must be the run-scoped workflow_readout.md")

    state_path = repo_root.joinpath(*state_rel.parts)
    readout_path = repo_root.joinpath(*readout_rel.parts)
    if not state_path.is_file():
        issues.append(f"missing state_path: {state_rel.as_posix()}")
    if not readout_path.is_file():
        issues.append(f"missing readout_path: {readout_rel.as_posix()}")

    state: dict[str, Any] = {}
    if state_path.is_file():
        try:
            state = _load_mapping(state_path)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            issues.append(f"invalid workflow state: {exc}")

    status = str(state.get("status", ""))
    if state and state.get("workflow_id") != workflow_id:
        issues.append("workflow_id differs between pointer and state")
    if state and not status:
        issues.append("workflow state status is missing")

    if readout_path.is_file():
        readout = readout_path.read_text(encoding="utf-8")
        readout_workflow_id = _readout_field(readout, "Workflow")
        readout_status = _readout_field(readout, "Derived automatic status")
        if readout_workflow_id != workflow_id:
            issues.append("workflow_id differs between state and readout")
        if status and readout_status != status:
            issues.append("workflow status differs between state and readout")

    artifacts = state.get("artifacts", []) if state else []
    artifact_paths = {
        str(row.get("path"))
        for row in artifacts
        if isinstance(row, dict) and row.get("status") == "current"
    }
    for required_path in (state_rel.as_posix(), readout_rel.as_posix()):
        if state and required_path not in artifact_paths:
            issues.append(f"current artifact registry is missing {required_path}")

    return {
        "pointer": pointer_name,
        "workflow_id": workflow_id,
        "workflow_status": status,
        "p2_ready": state.get("p2_ready") if state else None,
        "status": "fail" if issues else "pass",
        "issues": issues,
    }


def check_current_pointers(repo_root: Path, rules: dict[str, Any]) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    index_rel = _safe_relative_path(rules["canonical_index_path"])
    index_path = repo_root.joinpath(*index_rel.parts)
    if not index_path.is_file():
        return {
            "truthfulness_status": "fail",
            "checked": 0,
            "failed": 1,
            "issues": [f"missing canonical pointer index: {index_rel.as_posix()}"],
            "results": [],
        }

    index = _load_mapping(index_path)
    issues: list[str] = []
    for key in rules.get("forbidden_top_level_keys", []):
        if key in index:
            issues.append(f"legacy top-level key remains active: {key}")

    required_authority = rules.get("required_authority", {})
    if index.get("authority") != required_authority:
        issues.append("authority mapping does not match the current canonical owners")
    else:
        for raw_path in required_authority.values():
            authority_rel = _safe_relative_path(raw_path)
            if not repo_root.joinpath(*authority_rel.parts).is_file():
                issues.append(f"missing authority file: {authority_rel.as_posix()}")

    history = index.get("history")
    if not isinstance(history, dict):
        issues.append("history boundary must be a mapping")
    else:
        if history.get("storage") != "git_history":
            issues.append("legacy provenance storage must be git_history")
        if history.get("current_selection_allowed") is not False:
            issues.append("legacy history must not select a current run")

    current_runs = index.get("current_runs")
    if not isinstance(current_runs, dict) or not current_runs:
        issues.append("current_runs must be a non-empty mapping")
        current_runs = {}

    required_fields = set(rules.get("required_pointer_fields", []))
    results = [
        _check_pointer(repo_root, name, pointer, required_fields)
        for name, pointer in sorted(current_runs.items())
    ]
    failed = sum(result["status"] == "fail" for result in results) + bool(issues)
    return {
        "truthfulness_status": "fail" if failed else "pass",
        "checked": len(results),
        "failed": int(failed),
        "issues": issues,
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the active current-run pointer and readout projection."
    )
    parser.add_argument("--repo-root", default=".", type=Path)
    parser.add_argument("--rules", type=Path, help="Optional YAML rules file.")
    parser.add_argument("--json", type=Path, help="Optional JSON report path.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero on failure.")
    args = parser.parse_args(argv)

    rules = load_rules(args.rules)
    report = check_current_pointers(args.repo_root, rules)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(
        "truthfulness_status={status} checked={checked} failed={failed}".format(
            status=report["truthfulness_status"],
            checked=report["checked"],
            failed=report["failed"],
        )
    )
    for issue in report["issues"]:
        print(issue)
    for result in report["results"]:
        for issue in result["issues"]:
            print(f"{result['pointer']}: {issue}")

    if args.strict and report["truthfulness_status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
