#!/usr/bin/env python3
"""Check R5 task cards against readout artifacts for Patch 43-48."""
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


PATCH_EXPECTATIONS: tuple[PatchExpectation, ...] = (
    PatchExpectation(
        patch_id="R5_PATCH_43",
        task_card_path="codex_tasks/r5_after_patch36/R5_PATCH_43_VALUATION_INPUT_REGISTRY_AND_INTERLOCK.md",
        readout_path="reports/p1_6/R5_PATCH_43_VALUATION_INPUT_REGISTRY_AND_INTERLOCK_READOUT.md",
        blocking_for_next=True,
        notes="valuation registry/interlock readout with command evidence",
    ),
    PatchExpectation(
        patch_id="R5_PATCH_44",
        task_card_path="codex_tasks/r5_after_patch36/R5_PATCH_44_002837_REVIEWED_INPUT_DRY_RUN.md",
        readout_path="reports/p1_6/R5_PATCH_44_002837_REVIEWED_INPUT_DRY_RUN_READOUT.md",
        blocking_for_next=True,
        notes="002837 reviewed-input dry run readout with command evidence",
    ),
    PatchExpectation(
        patch_id="R5_PATCH_45",
        task_card_path="codex_tasks/r5_after_patch36/R5_PATCH_45_R5_PACK_PROMOTION_GATE.md",
        readout_path="reports/p1_6/R5_PATCH_45_R5_PACK_PROMOTION_GATE_READOUT.md",
        blocking_for_next=True,
        notes="pack promotion gate readout with command evidence",
    ),
    PatchExpectation(
        patch_id="R5_PATCH_46",
        task_card_path="codex_tasks/r5_after_patch36/R5_PATCH_46_QUALITY_GATE_SCORECARD_V2.md",
        readout_path="reports/p1_6/R5_PATCH_46_QUALITY_GATE_SCORECARD_V2_READOUT.md",
        blocking_for_next=True,
        notes="quality scorecard v2 readout with command evidence",
    ),
    PatchExpectation(
        patch_id="R5_PATCH_47",
        task_card_path="codex_tasks/r5_after_patch36/R5_PATCH_47_COMPOSER_RESEARCH_DRAFT_PLUS_MODE.md",
        readout_path="reports/p1_6/R5_PATCH_47_COMPOSER_RESEARCH_DRAFT_PLUS_MODE_READOUT.md",
        blocking_for_next=True,
        notes="composer draft-plus readout with command evidence",
    ),
    PatchExpectation(
        patch_id="R5_PATCH_48",
        task_card_path="codex_tasks/r5_after_patch36/R5_PATCH_48_PILOT_READINESS_DECISION.md",
        readout_path="reports/p1_6/R5_AFTER_PATCH36_REVIEWED_INPUT_CLOSE_READOUT.md",
        blocking_for_next=True,
        notes="Patch 48 is represented by the after-Patch36 close readout, not a patch-numbered readout",
        companion_paths=("reports/p1_6/r5_reviewed_input_pilot_gate_result.json",),
    ),
)


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

    readout_name = Path(expectation.readout_path).name
    close_readout_relation = (
        "close_readout_exists_under_non_patch_filename"
        if expectation.patch_id == "R5_PATCH_48" and readout_exists and not readout_name.startswith("R5_PATCH_48")
        else "standard_patch_readout_path"
    )

    row = {
        **asdict(expectation),
        "task_card_exists": task_exists,
        "readout_exists": readout_exists,
        "readout_status": _status_line(readout_text) if readout_exists else "missing",
        "command_evidence": command_evidence,
        "status": status,
        "close_readout_relation": close_readout_relation,
        "canonical_status": _canonical_status(expectation.readout_path, canonical_index_text),
        "companion_artifacts": companion_status,
    }
    row["companion_paths"] = list(expectation.companion_paths)
    return row


def build_matrix(root: Path) -> dict[str, Any]:
    canonical_index_text = _read_text(root / "reports/p1_6/R5_READOUT_CANONICAL_INDEX.md")
    rows = [evaluate_row(root, item, canonical_index_text) for item in PATCH_EXPECTATIONS]
    blocking_missing = [
        row["patch_id"]
        for row in rows
        if row["blocking_for_next"] and row["status"] != "completed_with_command_evidence"
    ]
    return {
        "artifact_type": "r5_after_patch48_status_matrix",
        "schema_version": "r5_after_patch48_status_matrix_v0.1",
        "generated_from": "scripts/check_r5_task_readout_sync.py",
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
    parser = argparse.ArgumentParser(description="Check R5 Patch 43-48 task/readout sync.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--json", type=Path, help="Output path; YAML is written when the suffix is .yaml/.yml.")
    args = parser.parse_args(argv)

    payload = build_matrix(args.repo_root.resolve())
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
