#!/usr/bin/env python3
"""Run the isolated end-to-end Bundle 4 reviewed-input fixture smoke."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_r5_reviewed_input_dry_run_from_registries as dry_run_builder  # noqa: E402
import promote_r5_reviewed_inputs_to_registries as promoter  # noqa: E402
import r5_reviewed_input_registry_io as registry_io  # noqa: E402

FIXTURE_WORKFLOW = "wf_fixture_r5_bundle4"
FIXTURE_STOCK = "000000"
REAL_WORKFLOW = promoter.REAL_WORKFLOW_ID
SCENARIOS = [
    "empty_or_pending",
    "accepted_core_complete",
    "accepted_all_complete",
    "mixed_status",
    "invalid_input",
    "idempotent_rerun",
]
REVIEWED_FLAGS = [
    "reviewed_market_inputs_available",
    "reviewed_peer_inputs_available",
    "reviewed_forecast_assumptions_available",
    "reviewed_valuation_inputs_available",
    "reviewed_business_disclosure_available",
]
ALL_TODOS = [
    "TODO_MARKET_DATA",
    "TODO_PEER_DATA",
    "TODO_MODEL_INPUT",
    "MISSING_DISCLOSURE",
    "TODO_SOURCE_REQUIRED",
]


def _real_registry_hashes(repo_root: Path) -> dict[str, str | None]:
    run_dir = repo_root / "reports/workflow_runs" / REAL_WORKFLOW
    return {
        name: registry_io.file_sha256(run_dir / filename)
        for name, filename in promoter.REGISTRY_FILENAMES.items()
    }


def _registry_actions(promotion: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "action": item.get("action"),
            "before_hash": item.get("before_hash"),
            "after_hash": item.get("after_hash"),
        }
        for name, item in (promotion.get("registry_results") or {}).items()
    }


def _reviewed_flags(dry_run: dict[str, Any]) -> dict[str, bool]:
    return {flag: bool(dry_run.get(flag)) for flag in REVIEWED_FLAGS}


def _stable_blockers(promotion: dict[str, Any], dry_run: dict[str, Any]) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    for issue in promotion.get("validation_issues") or []:
        if isinstance(issue, dict):
            blockers.append(
                {
                    "id": str(issue.get("issue_id") or "promotion_validation"),
                    "reason": str(issue.get("description") or issue.get("reason") or "promotion validation failed"),
                }
            )
    for blocker in dry_run.get("blockers") or []:
        if isinstance(blocker, dict):
            blockers.append(
                {
                    "id": str(blocker.get("registry") or "registry_validation"),
                    "reason": str(blocker.get("reason") or "registry validation failed"),
                }
            )
    deduped = {(row["id"], row["reason"]): row for row in blockers}
    return [deduped[key] for key in sorted(deduped)]


def _expectation_met(
    scenario: str,
    promotion: dict[str, Any],
    dry_run: dict[str, Any],
    actions: dict[str, dict[str, Any]],
) -> bool:
    flags = _reviewed_flags(dry_run)
    if scenario == "empty_or_pending":
        return (
            promotion.get("promotion_status") == "no_accepted_inputs"
            and not any(flags.values())
            and set(dry_run.get("remaining_todos") or []) == set(ALL_TODOS)
            and all(item.get("action") == "unchanged" for item in actions.values())
        )
    if scenario == "accepted_core_complete":
        return (
            flags
            == {
                "reviewed_market_inputs_available": True,
                "reviewed_peer_inputs_available": True,
                "reviewed_forecast_assumptions_available": True,
                "reviewed_valuation_inputs_available": True,
                "reviewed_business_disclosure_available": False,
            }
            and dry_run.get("remaining_todos") == ["MISSING_DISCLOSURE"]
            and promotion.get("registries_changed") is True
        )
    if scenario == "accepted_all_complete":
        return all(flags.values()) and not dry_run.get("remaining_todos") and promotion.get("registries_changed") is True
    if scenario == "mixed_status":
        return (
            flags
            == {
                "reviewed_market_inputs_available": True,
                "reviewed_peer_inputs_available": False,
                "reviewed_forecast_assumptions_available": False,
                "reviewed_valuation_inputs_available": False,
                "reviewed_business_disclosure_available": False,
            }
            and promotion.get("accepted_count") == 1
            and promotion.get("accepted_degraded_count") == 1
        )
    if scenario == "invalid_input":
        return (
            promotion.get("validation_status") != "pass"
            and promotion.get("registries_changed") is False
            and not any(flags.values())
            and all(
                item.get("action") in {"blocked", "unchanged"}
                and item.get("before_hash") == item.get("after_hash")
                for item in actions.values()
            )
        )
    if scenario == "idempotent_rerun":
        return (
            promotion.get("validation_status") == "pass"
            and promotion.get("registries_changed") is False
            and all(
                item.get("action") == "unchanged"
                and item.get("before_hash")
                and item.get("before_hash") == item.get("after_hash")
                for item in actions.values()
            )
        )
    return False


def _run_one(
    *,
    scenario: str,
    repo_root: Path,
    fixture_root: Path,
    work_root: Path,
) -> dict[str, Any]:
    scenario_dir = work_root / scenario
    if scenario_dir.exists():
        raise FileExistsError(f"smoke scenario directory already exists: {scenario}")
    scenario_dir.mkdir(parents=True)
    run_dir = scenario_dir / "run"
    if scenario == "empty_or_pending":
        dropzone_root = scenario_dir / "empty_dropzone"
        dropzone_root.mkdir()
    elif scenario == "invalid_input":
        dropzone_root = fixture_root / "invalid_cross_stock"
    else:
        fixture_name = "accepted_core_complete" if scenario == "idempotent_rerun" else scenario
        dropzone_root = fixture_root / fixture_name

    promotion = promoter.promote_reviewed_inputs(
        repo_root=repo_root,
        workflow_id=FIXTURE_WORKFLOW,
        stock_code=FIXTURE_STOCK,
        dropzone_root=dropzone_root,
        output_run_dir=run_dir,
        fixture_mode=True,
        dry_run=False,
    )
    first_promotion = promotion
    if scenario == "idempotent_rerun":
        promotion = promoter.promote_reviewed_inputs(
            repo_root=repo_root,
            workflow_id=FIXTURE_WORKFLOW,
            stock_code=FIXTURE_STOCK,
            dropzone_root=dropzone_root,
            output_run_dir=run_dir,
            fixture_mode=True,
            dry_run=False,
        )
    promotion_path = scenario_dir / "promotion_result.json"
    promoter.write_result(promotion_path, promotion)
    dry_run = dry_run_builder.build_dry_run_from_registries(
        run_dir,
        True,
        promotion_result_path=promotion_path,
        repo_root=repo_root,
    )
    actions = _registry_actions(promotion)
    expectation_met = _expectation_met(scenario, promotion, dry_run, actions)
    blockers = _stable_blockers(promotion, dry_run)
    steps = [
        {"name": "dropzone_validation", "status": promotion.get("validation_status")},
        {"name": "registry_promotion", "status": promotion.get("promotion_status")},
        {"name": "registry_validation_and_dry_run", "status": dry_run.get("validation_status")},
        {
            "name": "fixture_gate_decision",
            "status": "pass"
            if dry_run.get("sample_quality_report_allowed") is False and dry_run.get("p2_allowed") is False
            else "fail",
        },
        {"name": "expectation_check", "status": "pass" if expectation_met else "fail"},
    ]
    if scenario == "idempotent_rerun":
        steps.insert(
            2,
            {
                "name": "first_materialization",
                "status": first_promotion.get("promotion_status"),
            },
        )
    return {
        "status": "pass" if expectation_met else "fail",
        "expectation_met": expectation_met,
        "steps": steps,
        "reviewed_flags": _reviewed_flags(dry_run),
        "remaining_todos": list(dry_run.get("remaining_todos") or []),
        "allowed_report_level": dry_run.get("allowed_report_level"),
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
        "accepted_count": int(promotion.get("accepted_count") or 0),
        "accepted_degraded_count": int(promotion.get("accepted_degraded_count") or 0),
        "accepted_input_ids": list(promotion.get("accepted_input_ids") or []),
        "accepted_degraded_input_ids": list(promotion.get("accepted_degraded_input_ids") or []),
        "registries_changed": bool(promotion.get("registries_changed")),
        "registry_actions": actions,
        "blockers": blockers,
    }


def run_smoke(
    *,
    repo_root: Path,
    fixture_root: Path,
    work_root: Path,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    fixture_root = fixture_root.resolve()
    work_root = work_root.resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    before_real = _real_registry_hashes(repo_root)
    scenarios = {
        scenario: _run_one(
            scenario=scenario,
            repo_root=repo_root,
            fixture_root=fixture_root,
            work_root=work_root,
        )
        for scenario in SCENARIOS
    }
    after_real = _real_registry_hashes(repo_root)
    real_unchanged = before_real == after_real
    overall_pass = real_unchanged and all(item["expectation_met"] for item in scenarios.values())
    return {
        "artifact_type": "r5_bundle4_reviewed_input_smoke_result",
        "schema_version": "r5_bundle4_reviewed_input_smoke_result.v1",
        "fixture_mode": True,
        "base_workflow_id": REAL_WORKFLOW,
        "temporary_workflow_id": FIXTURE_WORKFLOW,
        "no_live_api": True,
        "scenarios": scenarios,
        "real_workflow_unchanged": real_unchanged,
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
        "overall_status": "pass" if overall_pass else "fail",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the isolated R5 Bundle 4 reviewed-input smoke.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run_smoke(
        repo_root=args.repo_root,
        fixture_root=args.fixture_root,
        work_root=args.work_root,
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "r5_bundle4_smoke_status={status} scenarios={scenarios} real_workflow_unchanged={real} "
        "sample_quality_allowed=false p2_allowed=false".format(
            status=result["overall_status"],
            scenarios=len(result["scenarios"]),
            real=str(result["real_workflow_unchanged"]).lower(),
        )
    )
    return 0 if result["overall_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
