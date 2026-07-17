from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from src.research.r5_bundle17r_backflow_execution import row_sha256


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_yaml(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=True), encoding="utf-8")


def build_fixture(root: Path, *, route: str = "auto") -> dict[str, Any]:
    policy = {
        "require_input_lock_coverage": True,
        "passed_statuses": ["passed", "engineering_pass"],
        "failed_statuses": ["failed"],
        "manual_statuses": ["pending", "manual_pending"],
        "always_manual_routes": ["manual", "human_review", "evidence_review"],
        "allowed_repo_prefixes": ["src/", "docs/", "reports/", "tests/"],
        "repo_candidate_extensions": [".py", ".md", ".json", ".yaml", ".csv"],
        "archive_extensions": [".zip", ".png", ".log"],
        "reject_path_patterns": ["__pycache__", "*.pyc", ".env", "secret", "token"],
        "require_checks_for_pass": True,
        "require_resolved_blocker_for_pass": True,
        "require_manual_attestation": True,
    }
    write_yaml(root / "config/policy.yaml", policy)

    work_order = {
        "work_order_id": "WO-001",
        "case_id": "CASE-A",
        "execution_route": route,
        "blocker_ids": "BLK-001",
        "owner": "stock-deep-dive",
    }
    write_csv(
        root / "reports/bf1/work_orders.csv",
        list(work_order),
        [work_order],
    )
    write_csv(
        root / "reports/bf1/issues.csv",
        ["blocker_id", "case_id", "work_order_id", "description"],
        [
            {
                "blocker_id": "BLK-001",
                "case_id": "CASE-A",
                "work_order_id": "WO-001",
                "description": "missing operating bridge",
            }
        ],
    )
    write_csv(
        root / "reports/bf1/cases.csv",
        ["case_id", "company_name", "engineering_pass"],
        [{"case_id": "CASE-A", "company_name": "Example", "engineering_pass": "false"}],
    )

    locked_files = [
        root / "reports/bf1/work_orders.csv",
        root / "reports/bf1/issues.csv",
        root / "reports/bf1/cases.csv",
    ]
    lock = {
        "schema_version": "fixture",
        "artifacts": [
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
            }
            for path in locked_files
        ],
    }
    lock_path = root / "reports/bf1/generation_lock.json"
    lock_path.write_text(json.dumps(lock, sort_keys=True), encoding="utf-8")

    manifest = {
        "schema_version": "r5_bundle17r_bf2_execution_manifest_v1",
        "bundle_id": "fixture-bf2",
        "source_baseline_commit": "",
        "as_of": "2026-07-17",
        "policy_path": "config/policy.yaml",
        "inputs": {
            "generation_lock": "reports/bf1/generation_lock.json",
            "work_orders": "reports/bf1/work_orders.csv",
            "issue_ledger": "reports/bf1/issues.csv",
            "case_matrix": "reports/bf1/cases.csv",
        },
        "result_dropzone": ".local/results",
        "review_decision_dir": ".local/results/reviews",
        "output_dir": "reports/bf2",
    }
    manifest_path = root / "manifest.yaml"
    write_yaml(manifest_path, manifest)
    return {
        "root": root,
        "manifest_path": manifest_path,
        "work_order": work_order,
        "work_order_sha256": row_sha256(work_order),
    }


def add_passed_result(
    fixture: dict[str, Any],
    *,
    artifact_name: str = "fix.py",
    declared_disposition: str = "repo_candidate",
    promotion_target: str = "src/research/fix.py",
    source_hash_override: str | None = None,
    artifact_hash_override: str | None = None,
    status: str = "passed",
    manual_attestation: bool = False,
) -> Path:
    root: Path = fixture["root"]
    result_dir = root / ".local/results/WO-001"
    result_dir.mkdir(parents=True, exist_ok=True)
    artifact = result_dir / artifact_name
    artifact.write_bytes(b"print('fixed')\n" if artifact.suffix != ".zip" else b"PK fixture")
    payload: dict[str, Any] = {
        "schema_version": "r5_bundle17r_work_order_result_v1",
        "work_order_id": "WO-001",
        "case_id": "CASE-A",
        "source_work_order_sha256": source_hash_override or fixture["work_order_sha256"],
        "execution_status": status,
        "resolved_blocker_ids": ["BLK-001"] if status == "passed" else [],
        "checks": [{"id": "focused_tests", "status": "passed"}] if status == "passed" else [],
        "produced_artifacts": [
            {
                "source_root": "dropzone",
                "path": f"WO-001/{artifact_name}",
                "sha256": artifact_hash_override or sha256_file(artifact),
                "disposition": declared_disposition,
                "promotion_target": promotion_target,
            }
        ],
    }
    if manual_attestation:
        payload["manual_attestation"] = {"reviewer": "human@example", "signed": True}
    result_path = result_dir / "result.yaml"
    write_yaml(result_path, payload)
    return result_path
