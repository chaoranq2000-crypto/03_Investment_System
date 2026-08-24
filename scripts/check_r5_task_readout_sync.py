#!/usr/bin/env python3
"""Check an explicitly supplied legacy task/readout compatibility contract."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class PatchExpectation:
    patch_id: str
    task_card_path: str
    readout_path: str
    blocking_for_next: bool
    notes: str = ""
    companion_paths: tuple[str, ...] = ()
    close_readout_relation: str = "standard_patch_readout_path"


def load_expectations(path: Path) -> tuple[PatchExpectation, ...]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    rows = data.get("expectations") if isinstance(data, dict) else data
    if not isinstance(rows, list) or not rows:
        raise ValueError("expectations input must contain a non-empty expectations list")

    expectations: list[PatchExpectation] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"expectations[{index}] must be a mapping")
        required = {
            "patch_id",
            "task_card_path",
            "readout_path",
            "blocking_for_next",
        }
        missing = sorted(required - set(row))
        if missing:
            raise ValueError(
                f"expectations[{index}] missing required fields: {', '.join(missing)}"
            )
        if not isinstance(row["blocking_for_next"], bool):
            raise ValueError(
                f"expectations[{index}].blocking_for_next must be boolean"
            )
        expectations.append(
            PatchExpectation(
                patch_id=str(row["patch_id"]),
                task_card_path=str(row["task_card_path"]),
                readout_path=str(row["readout_path"]),
                blocking_for_next=row["blocking_for_next"],
                notes=str(row.get("notes") or ""),
                companion_paths=tuple(str(value) for value in row.get("companion_paths") or ()),
                close_readout_relation=str(
                    row.get("close_readout_relation")
                    or "standard_patch_readout_path"
                ),
            )
        )
    return tuple(expectations)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _has_command_evidence(text: str) -> bool:
    required_markers = ["## commands_run", "## exit_code"]
    output_markers = ["## stdout_or_stderr_summary", "## stdout_stderr_summary"]
    return all(marker in text for marker in required_markers) and any(marker in text for marker in output_markers)


def _status_line(text: str) -> str:
    for line in text.splitlines():
        if line.lower().startswith("status:"):
            return line.split(":", 1)[1].strip().strip("`")
    return "unknown"


def _canonical_status(path: str, canonical_index_text: str) -> str:
    needle = f"`{path}`"
    for line in canonical_index_text.splitlines():
        if needle in line:
            cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
            if len(cells) >= 2:
                return cells[1]
    return "not_listed"


def evaluate_row(root: Path, expectation: PatchExpectation, canonical_index_text: str) -> dict[str, Any]:
    task_path = root / expectation.task_card_path
    readout_path = root / expectation.readout_path
    task_exists = task_path.exists()
    readout_exists = readout_path.exists()
    readout_text = _read_text(readout_path)
    command_evidence = _has_command_evidence(readout_text)
    companion_status = {
        path: (root / path).exists()
        for path in expectation.companion_paths
    }

    if task_exists and readout_exists and command_evidence:
        status = "completed_with_command_evidence"
    elif task_exists and not readout_exists:
        status = "task_card_exists_readout_missing"
    elif readout_exists and not task_exists:
        status = "readout_exists_task_card_missing"
    elif task_exists and readout_exists:
        status = "readout_exists_without_full_command_evidence"
    else:
        status = "task_card_and_readout_missing"

    row = {
        **asdict(expectation),
        "task_card_exists": task_exists,
        "readout_exists": readout_exists,
        "readout_status": _status_line(readout_text) if readout_exists else "missing",
        "command_evidence": command_evidence,
        "status": status,
        "close_readout_relation": expectation.close_readout_relation,
        "canonical_status": _canonical_status(expectation.readout_path, canonical_index_text),
        "companion_artifacts": companion_status,
    }
    row["companion_paths"] = list(expectation.companion_paths)
    return row


def build_matrix(
    root: Path,
    expectations: tuple[PatchExpectation, ...],
    canonical_index_path: Path | None = None,
) -> dict[str, Any]:
    canonical_index_text = _read_text(canonical_index_path) if canonical_index_path else ""
    rows = [evaluate_row(root, item, canonical_index_text) for item in expectations]
    blocking_missing = [
        row["patch_id"]
        for row in rows
        if row["blocking_for_next"] and row["status"] != "completed_with_command_evidence"
    ]
    return {
        "artifact_type": "r5_after_patch48_status_matrix",
        "schema_version": "r5_after_patch48_status_matrix_v0.1",
        "generated_from": "scripts/check_r5_task_readout_sync.py",
        "expectation_source": "explicit_input",
        "status": "pass" if not blocking_missing else "fail",
        "blocking_missing": blocking_missing,
        "rows": rows,
    }


def write_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check an explicit legacy task/readout compatibility contract."
    )
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--expectations",
        type=Path,
        required=True,
        help="Explicit YAML/JSON expectation contract; no legacy table is implied.",
    )
    parser.add_argument(
        "--canonical-index",
        type=Path,
        help="Optional explicit historical index used only for compatibility labels.",
    )
    parser.add_argument("--json", type=Path, help="Output path; YAML is written when the suffix is .yaml/.yml.")
    args = parser.parse_args(argv)

    root = args.repo_root.resolve()
    expectations_path = (
        args.expectations.resolve()
        if args.expectations.is_absolute()
        else (root / args.expectations).resolve()
    )
    canonical_index_path = None
    if args.canonical_index:
        canonical_index_path = (
            args.canonical_index.resolve()
            if args.canonical_index.is_absolute()
            else (root / args.canonical_index).resolve()
        )
    payload = build_matrix(
        root,
        load_expectations(expectations_path),
        canonical_index_path,
    )
    if args.json:
        write_payload(args.json, payload)
    print(
        "r5_task_readout_sync_status={status} checked={checked} blocking_missing={missing}".format(
            status=payload["status"],
            checked=len(payload["rows"]),
            missing=len(payload["blocking_missing"]),
        )
    )
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
