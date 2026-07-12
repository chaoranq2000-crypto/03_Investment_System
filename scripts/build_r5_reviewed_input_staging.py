#!/usr/bin/env python3
"""Build a reviewed-input staging result for an R5 workflow."""
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
TODO_TOKENS = [
    "TODO_MARKET_DATA",
    "TODO_PEER_DATA",
    "TODO_MODEL_INPUT",
    "MISSING_DISCLOSURE",
    "TODO_SOURCE_REQUIRED",
    "LOW_CONFIDENCE_CLUE_ONLY",
]
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
        for row in dropzone.read_dropzone_file(path):
            if isinstance(row, dict):
                records.append(row)
    return records


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_text(item) for item in value)
    return "" if value is None else str(value)


def remaining_todos_from_inputs(*items: dict[str, Any]) -> list[str]:
    text = "\n".join(_text(item) for item in items)
    return [token for token in TODO_TOKENS if token in text]


def build_staging_result(
    *,
    repo_root: Path,
    workflow_id: str,
    dropzone_root: Path | None = None,
) -> dict[str, Any]:
    run_dir = repo_root / "reports/workflow_runs" / workflow_id
    actual_dropzone_root = dropzone_root or repo_root / "data/reviewed_inputs" / workflow_id
    validation = dropzone.validate_root(actual_dropzone_root)
    records = collect_records(actual_dropzone_root)
    accepted_records = [row for row in records if row.get("review_status") == "accepted"]
    accepted_degraded_records = [row for row in records if row.get("review_status") == "accepted_degraded"]
    accepted_input_types = {str(row.get("input_type")) for row in accepted_records}

    flags = {
        flag: input_type in accepted_input_types
        for input_type, flag in INPUT_TYPE_FLAGS.items()
    }
    previous_dry_run = load_yaml(run_dir / "R5_reviewed_input_dry_run_result.yaml")
    evidence_ledger = load_yaml(run_dir / "R5_evidence_request_review_ledger.yaml")
    remaining_todos = remaining_todos_from_inputs(previous_dry_run, evidence_ledger)

    has_core_accepted = all(
        flags[key]
        for key in [
            "reviewed_market_inputs_available",
            "reviewed_peer_inputs_available",
            "reviewed_forecast_assumptions_available",
            "reviewed_valuation_inputs_available",
        ]
    )
    if validation["status"] != "pass":
        allowed_report_level = "blocked"
    elif has_core_accepted:
        allowed_report_level = "reviewed_input_research_draft"
    else:
        allowed_report_level = "source_gapped_research_draft"

    sample_quality_allowed = False
    return {
        "artifact_type": "R5_reviewed_input_staging_result",
        "schema_version": "r5_reviewed_input_staging_result_v0.1",
        "workflow_id": workflow_id,
        "stock_code": "002837",
        "no_live_api": True,
        "dropzone_root": str(actual_dropzone_root.relative_to(repo_root) if actual_dropzone_root.is_absolute() and repo_root in actual_dropzone_root.parents else actual_dropzone_root),
        "validation_status": validation["status"],
        "validation_issues": validation["issues"],
        **flags,
        "accepted_count": validation["accepted_count"],
        "accepted_degraded_count": validation["accepted_degraded_count"],
        "pending_count": validation["pending_count"],
        "rejected_count": validation["rejected_count"],
        "accepted_input_ids": [str(row.get("input_id")) for row in accepted_records],
        "accepted_degraded_input_ids": [str(row.get("input_id")) for row in accepted_degraded_records],
        "remaining_todos": remaining_todos,
        "allowed_report_level": allowed_report_level,
        "sample_quality_report_allowed": sample_quality_allowed,
        "p2_allowed": False,
        "inputs": {
            "dropzone_root": str(actual_dropzone_root),
            "evidence_request_review_ledger": str(run_dir / "R5_evidence_request_review_ledger.yaml"),
            "previous_reviewed_input_dry_run": str(run_dir / "R5_reviewed_input_dry_run_result.yaml"),
        },
        "notes": [
            "Accepted-only flags are derived only from review_status=accepted rows.",
            "accepted_degraded rows may preserve limitations but do not allow sample-quality.",
            "Templates are not evidence and are not counted as accepted inputs.",
            "Reviewed-input staging is capped at research-draft level; a later independent quality gate is required for any higher level.",
        ],
    }


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build R5 reviewed-input staging result.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--workflow-id", default=WORKFLOW_ID)
    parser.add_argument("--dropzone-root", type=Path)
    parser.add_argument("--json", type=Path, required=True, help="Output path; YAML is written for .yaml/.yml.")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    result = build_staging_result(repo_root=repo_root, workflow_id=args.workflow_id, dropzone_root=args.dropzone_root)
    write_yaml(args.json, result)
    print(
        "r5_reviewed_input_staging_status={status} allowed_report_level={level} accepted={accepted} accepted_degraded={degraded} pending={pending} sample_quality_allowed={sample} p2_allowed={p2}".format(
            status=result["validation_status"],
            level=result["allowed_report_level"],
            accepted=result["accepted_count"],
            degraded=result["accepted_degraded_count"],
            pending=result["pending_count"],
            sample=str(result["sample_quality_report_allowed"]).lower(),
            p2=str(result["p2_allowed"]).lower(),
        )
    )
    return 0 if result["validation_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
