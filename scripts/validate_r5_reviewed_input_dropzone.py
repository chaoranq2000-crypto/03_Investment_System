#!/usr/bin/env python3
"""Validate reviewed-input dropzone files before R5 registry promotion."""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

import yaml

ALLOWED_INPUT_TYPES = {
    "market_snapshot",
    "peer_snapshot",
    "forecast_assumptions",
    "business_disclosure",
    "valuation_inputs",
    "sentiment_event_sources",
}
ALLOWED_REVIEW_STATUSES = {"pending", "accepted", "rejected", "accepted_degraded"}
ACCEPTED_STATUSES = {"accepted", "accepted_degraded"}
FORBIDDEN_ACCEPTED_TOKENS = {
    "TODO_MARKET_DATA",
    "TODO_PEER_DATA",
    "TODO_MODEL_INPUT",
    "TODO_SOURCE_REQUIRED",
    "MISSING_DISCLOSURE",
    "LOW_CONFIDENCE_CLUE_ONLY",
}
CORE_FIELDS = ["input_id", "workflow_id", "stock_code", "input_type", "review_status"]
ACCEPTED_REQUIRED_FIELDS = [
    "source_evidence_id",
    "source_rank",
    "as_of_date",
    "review_status",
    "reviewer",
    "reviewed_at",
    "limitations",
]
FALSE_VALUES = {"false", "0", "no", "n"}
NULL_VALUES = {"", "null", "none", "nan", "na", "n/a", "~"}


def _issue(issue_id: str, severity: str, path: str, description: str) -> dict[str, str]:
    return {"issue_id": issue_id, "severity": severity, "path": path, "description": description}


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(f"{key}: {_text(item)}" for key, item in value.items())
    if isinstance(value, list):
        return "\n".join(_text(item) for item in value)
    return "" if value is None else str(value)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in NULL_VALUES
    return False


def _is_false(value: Any) -> bool:
    if value is False:
        return True
    if isinstance(value, str):
        return value.strip().lower() in FALSE_VALUES
    return False


def _is_true(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return False


def _rows_from_yaml(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return []
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        if isinstance(data.get("records"), list):
            rows = data["records"]
        elif isinstance(data.get("inputs"), list):
            rows = data["inputs"]
        else:
            rows = [data]
    else:
        raise ValueError("YAML root must be a mapping, list, or empty file")
    return [row for row in rows if isinstance(row, dict)]


def _rows_from_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def read_dropzone_file(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _rows_from_csv(path)
    if suffix in {".yaml", ".yml"}:
        return _rows_from_yaml(path)
    return []


def iter_input_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".csv", ".yaml", ".yml"}
    )


def validate_record(record: dict[str, Any], path: Path, row_index: int) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    location = f"{path.as_posix()}[{row_index}]"
    for field in CORE_FIELDS:
        if _is_missing(record.get(field)):
            issues.append(_issue("R5DROP-CORE-001", "high", f"{location}.{field}", f"{field} is required"))

    input_type = record.get("input_type")
    if input_type not in ALLOWED_INPUT_TYPES:
        issues.append(_issue("R5DROP-TYPE-001", "high", f"{location}.input_type", "input_type is not allowed"))

    review_status = str(record.get("review_status") or "")
    if review_status not in ALLOWED_REVIEW_STATUSES:
        issues.append(_issue("R5DROP-STATUS-001", "high", f"{location}.review_status", "review_status is not allowed"))

    if review_status in ACCEPTED_STATUSES:
        for field in ACCEPTED_REQUIRED_FIELDS:
            if _is_missing(record.get(field)):
                issues.append(_issue("R5DROP-ACCEPTED-REQ-001", "high", f"{location}.{field}", f"{field} is required for accepted rows"))
        if _is_missing(record.get("source_evidence_id")):
            issues.append(_issue("R5DROP-EVIDENCE-001", "high", f"{location}.source_evidence_id", "accepted rows require source_evidence_id"))
        if "evidence_id" in record and _is_missing(record.get("evidence_id")):
            issues.append(_issue("R5DROP-EVIDENCE-002", "high", f"{location}.evidence_id", "accepted rows cannot carry evidence_id null"))
        if not _is_true(record.get("no_live_api")):
            issues.append(_issue("R5DROP-NOLIVE-001", "high", f"{location}.no_live_api", "accepted rows require no_live_api true"))
        text = _text(record)
        found_tokens = sorted(token for token in FORBIDDEN_ACCEPTED_TOKENS if token in text)
        if found_tokens:
            issues.append(_issue("R5DROP-TODO-001", "high", location, "accepted rows cannot contain " + ", ".join(found_tokens)))
        if review_status == "accepted_degraded" and not _is_false(record.get("sample_quality_allowed")):
            issues.append(
                _issue(
                    "R5DROP-DEGRADED-001",
                    "high",
                    f"{location}.sample_quality_allowed",
                    "accepted_degraded rows require sample_quality_allowed false",
                )
            )
    return issues


def validate_root(root: Path) -> dict[str, Any]:
    checked_files: list[str] = []
    issues: list[dict[str, str]] = []
    counts = {
        "accepted_count": 0,
        "accepted_degraded_count": 0,
        "pending_count": 0,
        "rejected_count": 0,
    }
    for path in iter_input_files(root):
        checked_files.append(path.as_posix())
        try:
            rows = read_dropzone_file(path)
        except Exception as exc:  # noqa: BLE001
            issues.append(_issue("R5DROP-LOAD-001", "high", path.as_posix(), f"ERROR: {exc}"))
            continue
        for idx, record in enumerate(rows):
            status = str(record.get("review_status") or "")
            if status == "accepted":
                counts["accepted_count"] += 1
            elif status == "accepted_degraded":
                counts["accepted_degraded_count"] += 1
            elif status == "pending":
                counts["pending_count"] += 1
            elif status == "rejected":
                counts["rejected_count"] += 1
            issues.extend(validate_record(record, path, idx))

    failed_count = sum(1 for issue in issues if issue["severity"] == "high")
    return {
        "artifact_type": "R5_reviewed_input_dropzone_validation",
        "schema_version": "r5_reviewed_input_dropzone_validation_v0.1",
        "status": "pass" if failed_count == 0 else "fail",
        "checked_files": checked_files,
        **counts,
        "failed_count": failed_count,
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate R5 reviewed-input dropzone files.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--json", type=Path, help="Write validation JSON to this path.")
    args = parser.parse_args(argv)

    result = validate_root(args.root)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(payload + "\n", encoding="utf-8")
    print(
        "r5_reviewed_input_dropzone_status={status} checked_files={checked} accepted={accepted} accepted_degraded={degraded} pending={pending} rejected={rejected} failed={failed}".format(
            status=result["status"],
            checked=len(result["checked_files"]),
            accepted=result["accepted_count"],
            degraded=result["accepted_degraded_count"],
            pending=result["pending_count"],
            rejected=result["rejected_count"],
            failed=result["failed_count"],
        )
    )
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
