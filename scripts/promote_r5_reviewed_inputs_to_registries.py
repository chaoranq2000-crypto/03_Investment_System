#!/usr/bin/env python3
"""Promote accepted R5 reviewed-input rows into registry-ready status."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import validate_r5_reviewed_input_dropzone as dropzone  # noqa: E402

WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
INPUT_TYPE_FLAGS = {
    "market_snapshot": "reviewed_market_inputs_available",
    "peer_snapshot": "reviewed_peer_inputs_available",
    "forecast_assumptions": "reviewed_forecast_assumptions_available",
    "business_disclosure": "reviewed_business_disclosure_available",
    "valuation_inputs": "reviewed_valuation_inputs_available",
}


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def collect_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in dropzone.iter_input_files(root):
        records.extend(dropzone.read_dropzone_file(path))
    return [row for row in records if isinstance(row, dict)]


def _promotion_level(flags: dict[str, bool], remaining_todos: list[str]) -> str:
    core_ready = all(
        flags[key]
        for key in [
            "reviewed_market_inputs_available",
            "reviewed_peer_inputs_available",
            "reviewed_forecast_assumptions_available",
            "reviewed_valuation_inputs_available",
        ]
    )
    all_ready = core_ready and flags["reviewed_business_disclosure_available"]
    if all_ready and not remaining_todos:
        return "sample_quality_candidate"
    if core_ready:
        return "reviewed_input_research_draft"
    return "source_gapped_research_draft"


def build_promotion_result(
    *,
    repo_root: Path,
    workflow_id: str,
    dropzone_root: Path | None = None,
) -> dict[str, Any]:
    run_dir = repo_root / "reports/workflow_runs" / workflow_id
    staging_path = run_dir / "R5_reviewed_input_staging_result.yaml"
    staging = load_yaml(staging_path)
    actual_dropzone_root = dropzone_root or repo_root / "data/reviewed_inputs" / workflow_id
    validation = dropzone.validate_root(actual_dropzone_root)
    records = collect_records(actual_dropzone_root)
    accepted_records = [row for row in records if row.get("review_status") == "accepted"]
    accepted_degraded_records = [row for row in records if row.get("review_status") == "accepted_degraded"]
    accepted_types = {str(row.get("input_type")) for row in accepted_records}
    flags = {
        flag: input_type in accepted_types
        for input_type, flag in INPUT_TYPE_FLAGS.items()
    }
    remaining_todos = list(staging.get("remaining_todos") or [])

    if validation["status"] != "pass":
        promotion_status = "blocked_invalid_dropzone"
        registries_changed = False
        allowed_report_level = "blocked"
    elif not accepted_records:
        promotion_status = "no_accepted_inputs"
        registries_changed = False
        allowed_report_level = "source_gapped_research_draft"
    else:
        promotion_status = "accepted_inputs_ready_for_registry_promotion"
        registries_changed = True
        allowed_report_level = _promotion_level(flags, remaining_todos)

    return {
        "artifact_type": "R5_reviewed_input_registry_promotion_result",
        "schema_version": "r5_reviewed_input_registry_promotion_result_v0.1",
        "workflow_id": workflow_id,
        "stock_code": "002837",
        "no_live_api": True,
        "dropzone_root": str(actual_dropzone_root),
        "staging_result_path": str(staging_path),
        "validation_status": validation["status"],
        "validation_issues": validation["issues"],
        "promotion_status": promotion_status,
        "registries_changed": registries_changed,
        "allowed_report_level": allowed_report_level,
        "sample_quality_report_allowed": allowed_report_level == "sample_quality_candidate",
        "p2_allowed": False,
        "accepted_count": len(accepted_records),
        "accepted_degraded_count": len(accepted_degraded_records),
        "accepted_input_ids": [str(row.get("input_id")) for row in accepted_records],
        "accepted_degraded_input_ids": [str(row.get("input_id")) for row in accepted_degraded_records],
        "reviewed_flags_from_accepted_rows": flags,
        "remaining_todos": remaining_todos,
        "registry_paths": {
            "market_peer": str(run_dir / "R5_market_peer_input_registry.yaml"),
            "forecast_assumptions": str(run_dir / "R5_forecast_assumption_registry.yaml"),
            "evidence_ledger": str(run_dir / "R5_evidence_request_review_ledger.yaml"),
        },
        "notes": [
            "Only review_status=accepted rows can unblock reviewed flags.",
            "accepted_degraded rows are carried as limitations and do not allow sample-quality.",
            "Pending and rejected rows keep source-gap visibility.",
        ],
    }


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote accepted R5 reviewed inputs to registries.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--workflow-id", default=WORKFLOW_ID)
    parser.add_argument("--dropzone-root", type=Path)
    parser.add_argument("--json", type=Path, required=True, help="Output path; YAML is written for .yaml/.yml.")
    args = parser.parse_args(argv)

    result = build_promotion_result(
        repo_root=args.repo_root.resolve(),
        workflow_id=args.workflow_id,
        dropzone_root=args.dropzone_root,
    )
    write_yaml(args.json, result)
    print(
        "r5_reviewed_input_promotion_status={status} registries_changed={changed} allowed_report_level={level} accepted={accepted} accepted_degraded={degraded}".format(
            status=result["promotion_status"],
            changed=str(result["registries_changed"]).lower(),
            level=result["allowed_report_level"],
            accepted=result["accepted_count"],
            degraded=result["accepted_degraded_count"],
        )
    )
    return 0 if result["validation_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
