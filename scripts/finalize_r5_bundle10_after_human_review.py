from __future__ import annotations

import argparse
import csv
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from validate_r5_bundle10_human_review_submission import (  # noqa: E402
    DEFAULT_WORKFLOW_ID,
    load_yaml,
    validate_submission,
)


FINAL_DATE = "2026-07-13"
HUMAN_TODO_IDS = {"R5B10-G11-001", "R5B10-QR-HUMAN-001"}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_yaml_atomic(path: Path, data: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(yaml.safe_dump(dict(data), allow_unicode=True, sort_keys=False), encoding="utf-8")
    temporary.replace(path)


def write_json_atomic(path: Path, data: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(dict(data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_csv_atomic(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def finalized_handoff(
    handoff: Mapping[str, Any],
    submission: Mapping[str, Any],
    submission_path: Path,
) -> dict[str, Any]:
    result = deepcopy(dict(handoff))
    submitted_rows = {
        str(row["check_id"]): row for row in submission["required_checklist"]
    }
    result["external_reviewer"] = submission["external_reviewer"]
    result["reviewed_at"] = submission["reviewed_at"]
    result["status"] = "passed_external_human_review"
    result["blocking_comments"] = list(submission.get("blocking_comments") or [])
    result["nonblocking_comments"] = list(submission.get("nonblocking_comments") or [])
    for row in result["required_checklist"]:
        submitted = submitted_rows[str(row["check_id"])]
        row["status"] = submitted["status"]
        row["comment"] = submitted.get("comment")
    result["signoff_fields"] = {
        "decision": submission["decision"],
        "reviewer_name": submission["external_reviewer"],
        "reviewed_at": submission["reviewed_at"],
        "report_sha256_confirmed": submission["report_sha256_confirmed"],
        "blocking_comment_count": len(submission.get("blocking_comments") or []),
    }
    result["external_review_submission_path"] = submission_path.as_posix()
    result["sample_quality_report_allowed"] = True
    result["p2_allowed"] = False
    result["boundary"] = (
        "External human review passed for the exact report hash; P2 remains a separate readiness decision."
    )
    return result


def finalized_state(
    state: Mapping[str, Any],
    submission: Mapping[str, Any],
    report_hash: str,
) -> dict[str, Any]:
    result = deepcopy(dict(state))
    result.update(
        {
            "status": "accepted_with_todos",
            "quality_target": "R5_sample_quality_ready",
            "updated_at": FINAL_DATE,
            "current_stage": "T10_close_readout",
            "next_stage": None,
            "active_skill": "research-orchestrator",
            "required_next_skill": None,
            "external_action_required": None,
        }
    )
    completed = result.setdefault("completed_stages", [])
    for stage in ("R5_bundle10_external_human_review", "R5_bundle10_final_close"):
        if stage not in completed:
            completed.append(stage)

    for artifact in result.setdefault("artifacts", []):
        if not isinstance(artifact, dict):
            continue
        if str(artifact.get("path", "")).endswith("R5_stock_research_report_reader_v3_human_review.yaml"):
            artifact["status"] = "passed_external_human_review"
        if str(artifact.get("path", "")).endswith("R5_stock_research_report_reader_v3.md"):
            artifact["status"] = "R5_sample_quality_ready"

    workflow_id = result["workflow_id"]
    extra_artifacts = (
        (
            "R5_reader_external_human_review_submission",
            "R5_stock_research_report_reader_v3_human_review_submission.yaml",
            "quality-review",
            "T9",
            "passed_external_human_review",
        ),
        (
            "R5_bundle10_human_review_submission_validation",
            "R5_bundle10_human_review_submission_validation.json",
            "quality-review",
            "T9",
            "pass",
        ),
        (
            "R5_bundle10_final_close_validation",
            "R5_bundle10_final_close_validation.json",
            "quality-review",
            "T10",
            "pass",
        ),
        (
            "bundle10_final_close_readout",
            "bundle10_final_close_readout.md",
            "research-orchestrator",
            "T10",
            "accepted_with_todos",
        ),
    )
    existing = {
        str(row.get("path")) for row in result["artifacts"] if isinstance(row, Mapping)
    }
    for artifact_type, name, skill, stage, status in extra_artifacts:
        path = f"reports/workflow_runs/{workflow_id}/{name}"
        if path not in existing:
            result["artifacts"].append(
                {
                    "artifact_type": artifact_type,
                    "path": path,
                    "created_by_skill": skill,
                    "stage": stage,
                    "status": status,
                    "required": True,
                }
            )
            existing.add(path)

    for todo in result.setdefault("open_todos", []):
        if isinstance(todo, dict) and todo.get("issue_id") in HUMAN_TODO_IDS:
            todo["status"] = "resolved_external_human_review"
            todo["resolved_at"] = submission["reviewed_at"]
            todo["notes"] = "External human review passed for the exact Reader SHA256."

    snapshot = result.setdefault("reader_candidate_snapshot", {})
    snapshot.update(
        {
            "report_sha256": report_hash,
            "decision": "R5_sample_quality_ready",
            "quality_band": "sample_quality_ready_with_todos",
            "human_review_status": "passed_external",
            "external_reviewer": submission["external_reviewer"],
            "reviewed_at": submission["reviewed_at"],
            "sample_quality_report_allowed": True,
            "p2_allowed": False,
        }
    )
    internal = result.setdefault("bundle10_internal_completion", {})
    internal.update(
        {
            "decision": "R5_sample_quality_ready",
            "internal_execution_complete": True,
            "bundle_closed": True,
            "external_human_review": "passed",
            "sample_quality_allowed": True,
            "p2_allowed": False,
            "next_gate": None,
        }
    )
    result["bundle10_close"] = {
        "decision": "accepted_with_todos",
        "bundle_closed": True,
        "closed_at": submission["reviewed_at"],
        "reader_report_sha256": report_hash,
        "external_reviewer": submission["external_reviewer"],
        "external_human_review": "passed",
        "sample_quality_allowed": True,
        "p2_allowed": False,
        "remaining_todos_visible": True,
    }
    backflow = result.setdefault("quality_backflow", {})
    backflow.update(
        {
            "decision": "R5_sample_quality_ready",
            "quality_band": "sample_quality_ready_with_todos",
            "current_first_route": None,
            "current_first_stage": None,
            "sample_quality_report_allowed": True,
            "p2_allowed": False,
        }
    )
    gates = result.setdefault("quality_gates", [])
    gates[:] = [
        row
        for row in gates
        if not (isinstance(row, Mapping) and row.get("gate_id") == "R5_BUNDLE10_FINAL")
    ]
    gates.append(
        {
            "gate_id": "R5_BUNDLE10_FINAL",
            "status": "accepted_with_todos",
            "checked_by": "quality-review",
            "notes": "Automated truthfulness and Reader gates plus hash-bound external human review passed; P2 remains false.",
            "current_scope": "bundle10_final_close",
        }
    )
    return result


def update_todo_rows(
    rows: list[dict[str, str]],
    submission: Mapping[str, Any],
) -> list[dict[str, str]]:
    result = deepcopy(rows)
    for row in result:
        if row.get("issue_id") in HUMAN_TODO_IDS:
            row["status"] = "resolved_external_human_review"
            row["resolved_at"] = str(submission["reviewed_at"])
            row["notes"] = "External human review passed for the exact Reader SHA256."
    return result


def update_quality_issue_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    result = deepcopy(rows)
    for row in result:
        if row.get("issue_id") in HUMAN_TODO_IDS:
            row["blocking_decision"] = "accepted"
            row["next_action"] = "none"
            row["status"] = "resolved"
    return result


def update_manifest_rows(
    rows: list[dict[str, str]],
    workflow_id: str,
) -> list[dict[str, str]]:
    result = deepcopy(rows)
    numbers = [
        int(row["artifact_id"].split("_")[-1])
        for row in result
        if row.get("artifact_id", "").startswith("art_")
    ]
    next_number = max(numbers, default=0) + 1
    specs = (
        (
            "bundle10_human_review_submission",
            "R5_stock_research_report_reader_v3_human_review_submission.yaml",
            "quality-review",
            "T9",
            "external human review passed",
        ),
        (
            "bundle10_human_review_submission_validation",
            "R5_bundle10_human_review_submission_validation.json",
            "quality-review",
            "T9",
            "hash-bound human submission validation pass",
        ),
        (
            "bundle10_final_close_validation",
            "R5_bundle10_final_close_validation.json",
            "quality-review",
            "T10",
            "final close state validation pass",
        ),
        (
            "bundle10_final_close_readout",
            "bundle10_final_close_readout.md",
            "research-orchestrator",
            "T10",
            "accepted with TODOs; sample quality true; P2 false",
        ),
    )
    existing = {row["path"] for row in result}
    for artifact_type, name, skill, stage, notes in specs:
        path = f"reports/workflow_runs/{workflow_id}/{name}"
        if path in existing:
            continue
        result.append(
            {
                "artifact_id": f"art_{next_number:03d}",
                "artifact_type": artifact_type,
                "path": path,
                "created_by_skill": skill,
                "stage": stage,
                "required": "True",
                "exists": "True",
                "status": "current",
                "notes": notes,
            }
        )
        next_number += 1
        existing.add(path)
    return result


def build_final_validation(
    state: Mapping[str, Any],
    handoff: Mapping[str, Any],
    submission_validation: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    if submission_validation.get("eligible_for_bundle10_final_close") is not True:
        errors.append("human review submission is not eligible for final close")
    if handoff.get("status") != "passed_external_human_review":
        errors.append("human review handoff is not passed")
    if handoff.get("sample_quality_report_allowed") is not True or handoff.get("p2_allowed") is not False:
        errors.append("handoff sample/P2 boundary is invalid")
    if state.get("status") != "accepted_with_todos" or state.get("current_stage") != "T10_close_readout":
        errors.append("canonical state is not at accepted close readout")
    close = state.get("bundle10_close") or {}
    if close.get("bundle_closed") is not True or close.get("external_human_review") != "passed":
        errors.append("Bundle 10 is not closed with human review passed")
    if close.get("sample_quality_allowed") is not True or close.get("p2_allowed") is not False:
        errors.append("final sample/P2 boundary is invalid")
    return {
        "artifact_type": "R5_bundle10_final_close_validation",
        "schema_version": "v0.1",
        "workflow_id": state.get("workflow_id"),
        "decision": "pass" if not errors else "fail",
        "sample_quality_allowed": close.get("sample_quality_allowed"),
        "p2_allowed": close.get("p2_allowed"),
        "errors": errors,
    }


def render_final_readout(
    state: Mapping[str, Any],
    handoff: Mapping[str, Any],
) -> str:
    open_todo_count = sum(
        1
        for row in state.get("open_todos") or []
        if isinstance(row, Mapping) and not str(row.get("status", "")).startswith("resolved")
    )
    return f"""# R5 Bundle 10 Final Close Readout

- workflow_id: `{state['workflow_id']}`
- final_status: `accepted_with_todos`
- Reader SHA256: `{handoff['reader_report_sha256']}`
- external_reviewer: `{handoff['external_reviewer']}`
- reviewed_at: `{handoff['reviewed_at']}`
- external_human_review: `passed`
- sample_quality_allowed: `true`
- p2_allowed: `false`
- remaining_visible_todos: `{open_todo_count}`

真实性门、Reader 质量门与哈希绑定的真实外部人工评审均已通过，Bundle 10 可关闭并允许样例级状态。现有披露、同业可比性、内在估值方法、情绪来源及远端 CI 等 TODO 仍保留；本关闭不等于 P2 readiness，也不形成交易动作、配置比例或收益承诺。
"""


def finalize_bundle10(run: Path, submission_path: Path) -> dict[str, Any]:
    submission_validation = validate_submission(run, submission_path)
    if submission_validation.get("eligible_for_bundle10_final_close") is not True:
        raise ValueError(
            "human review submission is not eligible for final close: "
            + "; ".join(submission_validation.get("errors") or [])
        )
    expected_name = "R5_stock_research_report_reader_v3_human_review_submission.yaml"
    if submission_path.resolve().parent != run.resolve() or submission_path.name != expected_name:
        raise ValueError(f"final submission must be stored as {run / expected_name}")

    submission = load_yaml(submission_path)
    handoff_path = run / "R5_stock_research_report_reader_v3_human_review.yaml"
    state_path = run / "workflow_state.yaml"
    handoff = finalized_handoff(load_yaml(handoff_path), submission, submission_path)
    state = finalized_state(
        load_yaml(state_path), submission, str(submission_validation["report_sha256"])
    )
    final_validation = build_final_validation(state, handoff, submission_validation)
    if final_validation["decision"] != "pass":
        raise ValueError("in-memory final close validation failed: " + "; ".join(final_validation["errors"]))

    todo_fields, todo_rows = read_csv(run / "open_todos.csv")
    issue_fields, issue_rows = read_csv(run / "R5_bundle10_quality_issues.csv")
    manifest_fields, manifest_rows = read_csv(run / "artifact_manifest.csv")
    todo_rows = update_todo_rows(todo_rows, submission)
    issue_rows = update_quality_issue_rows(issue_rows)
    manifest_rows = update_manifest_rows(manifest_rows, str(state["workflow_id"]))

    write_json_atomic(run / "R5_bundle10_human_review_submission_validation.json", submission_validation)
    write_yaml_atomic(handoff_path, handoff)
    write_yaml_atomic(state_path, state)
    write_csv_atomic(run / "open_todos.csv", todo_fields, todo_rows)
    write_csv_atomic(run / "R5_bundle10_quality_issues.csv", issue_fields, issue_rows)
    write_csv_atomic(run / "artifact_manifest.csv", manifest_fields, manifest_rows)
    write_json_atomic(run / "R5_bundle10_final_close_validation.json", final_validation)
    (run / "bundle10_final_close_readout.md").write_text(
        render_final_readout(state, handoff), encoding="utf-8"
    )

    run_log = run / "run_log.md"
    marker = "## Bundle 10 final close after external human review"
    text = run_log.read_text(encoding="utf-8")
    if marker not in text:
        text = text.rstrip() + f"""

{marker}

| Step | Status | Notes |
|---|---|---|
| External human review | pass | Reviewer and timezone-aware timestamp recorded; exact Reader hash confirmed. |
| Bundle 10 close | accepted_with_todos | Sample quality allowed; remaining TODOs visible. |
| P2 | false | Separate readiness decision; not entered by this close. |
"""
        run_log.write_text(text + "\n", encoding="utf-8")
    return final_validation


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finalize Bundle 10 after a validated real external human review.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--workflow-id", default=DEFAULT_WORKFLOW_ID)
    parser.add_argument("--submission", required=True)
    parser.add_argument("--confirm-finalize", action="store_true")
    args = parser.parse_args(argv)
    if not args.confirm_finalize:
        parser.error("--confirm-finalize is required; this command mutates canonical workflow state")
    root = Path(args.repo_root).resolve()
    run = root / "reports/workflow_runs" / args.workflow_id
    submission = Path(args.submission)
    if not submission.is_absolute():
        submission = root / submission
    result = finalize_bundle10(run, submission)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
