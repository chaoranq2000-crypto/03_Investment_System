#!/usr/bin/env python3
"""Reconcile claimed R5 Patch 1-12 completion against actual artifacts."""
from __future__ import annotations

import argparse
import py_compile
import re
from pathlib import Path
from typing import Any

import yaml


DEFAULT_VALIDATIONS = {
    "markdown": ["exists", "line_count_gt_one"],
    "readout": ["exists", "line_count_gt_one"],
    "yaml": ["exists", "line_count_gt_one", "yaml_parse"],
    "python": ["exists", "line_count_gt_one", "py_compile"],
    "pytest": ["exists", "line_count_gt_one", "py_compile", "pytest_collectable"],
    "csv": ["exists", "line_count_gt_one"],
}


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data


def _line_count(path: Path) -> int | None:
    if not path.exists():
        return None
    return len(path.read_text(encoding="utf-8").splitlines())


def _yaml_parse(path: Path) -> tuple[str, str | None]:
    try:
        load_yaml(path)
    except Exception as exc:  # noqa: BLE001
        return "fail", str(exc)
    return "pass", None


def _py_compile(path: Path) -> tuple[str, str | None]:
    try:
        py_compile.compile(str(path), doraise=True)
    except py_compile.PyCompileError as exc:
        return "fail", exc.msg
    return "pass", None


def _pytest_collectable(path: Path) -> tuple[str, str | None]:
    text = path.read_text(encoding="utf-8")
    has_function = re.search(r"^\s*def\s+test_", text, flags=re.MULTILINE)
    has_class = re.search(r"^\s*class\s+Test[A-Za-z0-9_]*", text, flags=re.MULTILINE)
    if has_function or has_class:
        return "pass", None
    return "fail", "no def test_ or pytest-style Test class found"


def _readout_status(repo_root: Path, readout_path: str | None, blocking: bool) -> dict[str, Any]:
    if not readout_path:
        return {
            "path": None,
            "exists": False,
            "line_count": None,
            "status": "fail" if blocking else "warn",
            "notes": ["related_readout is not configured"],
        }
    path = repo_root / readout_path
    line_count = _line_count(path)
    notes: list[str] = []
    if not path.exists():
        notes.append("related_readout does not exist")
    elif line_count is not None and line_count <= 1:
        notes.append("related_readout has one line or less")
    return {
        "path": readout_path,
        "exists": path.exists(),
        "line_count": line_count,
        "status": "pass" if not notes else ("fail" if blocking else "warn"),
        "notes": notes,
    }


def validate_artifact(repo_root: Path, artifact: dict[str, Any]) -> dict[str, Any]:
    rel_path = str(artifact["path"])
    superseded_by = artifact.get("superseded_by")
    resolved_path = str(superseded_by or rel_path)
    artifact_type = str(artifact.get("artifact_type", "markdown"))
    required = bool(artifact.get("required", True))
    validations = list(artifact.get("validation") or DEFAULT_VALIDATIONS.get(artifact_type, ["exists"]))
    path = repo_root / resolved_path
    exists = path.exists()
    line_count = _line_count(path)
    notes: list[str] = []
    parse_status = "not_applicable"
    compile_status = "not_applicable"
    test_collectable = "not_applicable"

    for validation in validations:
        if validation == "exists":
            if not exists:
                notes.append("missing file")
        elif validation == "line_count_gt_one":
            if not exists:
                continue
            if line_count is None or line_count <= 1:
                notes.append(f"line_count is {line_count}; expected greater than 1")
        elif validation == "yaml_parse":
            if not exists:
                continue
            parse_status, error = _yaml_parse(path)
            if error:
                notes.append(f"yaml_parse failed: {error}")
        elif validation == "py_compile":
            if not exists:
                continue
            compile_status, error = _py_compile(path)
            if error:
                notes.append(f"py_compile failed: {error}")
        elif validation == "pytest_collectable":
            if not exists:
                continue
            test_collectable, error = _pytest_collectable(path)
            if error:
                notes.append(error)
        else:
            notes.append(f"unknown validation: {validation}")

    if notes:
        status = "fail" if required else "warn"
    else:
        status = "pass"

    return {
        "path": rel_path,
        "resolved_path": resolved_path,
        "superseded_by": superseded_by,
        "artifact_type": artifact_type,
        "required": required,
        "exists": exists,
        "line_count": line_count,
        "parse_status": parse_status,
        "compile_status": compile_status,
        "test_collectable": test_collectable,
        "status": status,
        "notes": notes,
    }


def reconcile_inventory(repo_root: Path, config: dict[str, Any]) -> dict[str, Any]:
    patches = config.get("patches")
    if not isinstance(patches, list):
        patches = [config]

    patch_results: list[dict[str, Any]] = []
    blocking_failures = 0
    total_artifacts = 0
    failed_artifacts = 0
    warn_artifacts = 0

    for patch in patches:
        expected = patch.get("expected_artifacts") or []
        if not isinstance(expected, list):
            raise ValueError(f"{patch.get('patch_id', '<unknown>')} expected_artifacts must be a list")
        artifacts = [validate_artifact(repo_root, item) for item in expected]
        readout = _readout_status(
            repo_root,
            patch.get("related_readout"),
            bool(patch.get("blocking_if_missing", True)),
        )
        patch_failed = any(item["status"] == "fail" for item in artifacts) or readout["status"] == "fail"
        patch_warned = any(item["status"] == "warn" for item in artifacts) or readout["status"] == "warn"
        if patch_failed:
            patch_status = "validation_failed"
            blocking_failures += 1
        elif patch_warned:
            patch_status = "validated_with_warnings"
        else:
            patch_status = "validated_complete"

        total_artifacts += len(artifacts)
        failed_artifacts += sum(1 for item in artifacts if item["status"] == "fail")
        warn_artifacts += sum(1 for item in artifacts if item["status"] == "warn")

        patch_results.append(
            {
                "patch_id": patch.get("patch_id"),
                "claimed_status": patch.get("claimed_status", "claimed_complete"),
                "superseded_by": patch.get("superseded_by"),
                "validated_status": patch_status,
                "blocking_if_missing": bool(patch.get("blocking_if_missing", True)),
                "related_readout": readout,
                "artifacts": artifacts,
            }
        )

    overall_status = "validated_complete" if blocking_failures == 0 else "claimed_complete_but_validation_failed"
    return {
        "inventory_status": overall_status,
        "accepted": blocking_failures == 0,
        "summary": {
            "patches_checked": len(patch_results),
            "blocking_patch_failures": blocking_failures,
            "artifacts_checked": total_artifacts,
            "artifact_failures": failed_artifacts,
            "artifact_warnings": warn_artifacts,
        },
        "patches": patch_results,
    }


def write_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile R5 Patch 1-12 expected artifacts.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--repo-root", default=".", type=Path)
    parser.add_argument("--strict", action="store_true", help="Return non-zero if inventory is not accepted.")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    config = load_yaml(args.config)
    report = reconcile_inventory(repo_root, config)
    write_report(report, args.out)

    summary = report["summary"]
    print(
        "inventory_status={status} accepted={accepted} patches_checked={patches} "
        "artifact_failures={failures}".format(
            status=report["inventory_status"],
            accepted=str(report["accepted"]).lower(),
            patches=summary["patches_checked"],
            failures=summary["artifact_failures"],
        )
    )
    if args.strict and not report["accepted"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
