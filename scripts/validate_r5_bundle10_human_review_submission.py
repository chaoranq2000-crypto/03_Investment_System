from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


DEFAULT_WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
REQUIRED_CHECK_IDS = tuple(f"HR-{number}" for number in range(1, 7))
ALLOWED_REVIEW_DECISIONS = {"pass", "needs_fix", "reject"}
ALLOWED_CHECK_STATUSES = {"pass", "needs_fix"}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_reviewed_at(value: Any) -> bool:
    if not _nonempty_text(value):
        return False
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def validate_submission(run: Path, submission_path: Path) -> dict[str, Any]:
    handoff = load_yaml(run / "R5_stock_research_report_reader_v3_human_review.yaml")
    scorecard = load_yaml(run / "R5_stock_research_report_reader_v3_quality_scorecard.yaml")
    submission = load_yaml(submission_path)
    report = run / "R5_stock_research_report_reader_v3.md"
    appendix = run / "R5_stock_research_report_traceability_v3.yaml"
    report_hash = sha256(report)
    appendix_hash = sha256(appendix)
    errors: list[str] = []

    handoff_status = handoff.get("status")
    if handoff_status not in {
        "pending_external_human_review",
        "passed_external_human_review",
    }:
        errors.append("current handoff is neither pending nor passed external human review")
    if handoff.get("reader_report_sha256") != report_hash:
        errors.append("pending handoff report hash does not match current Reader")
    if handoff.get("traceability_appendix_sha256") != appendix_hash:
        errors.append("pending handoff appendix hash does not match current traceability appendix")
    if scorecard.get("decision") != "candidate_ready_for_human_review":
        errors.append("automated Reader gate is not candidate_ready_for_human_review")
    if scorecard.get("truthfulness_status") != "pass" or scorecard.get("critical_blocker_count") != 0:
        errors.append("automated truthfulness/blocker gate is not clean")

    if submission.get("artifact_type") != "R5_reader_external_human_review_submission":
        errors.append("submission artifact_type is invalid")
    if submission.get("workflow_id") != handoff.get("workflow_id"):
        errors.append("submission workflow_id does not match handoff")
    if submission.get("reviewer_type") != "human":
        errors.append("reviewer_type must be human")
    if not _nonempty_text(submission.get("external_reviewer")):
        errors.append("external_reviewer is required")
    if not _valid_reviewed_at(submission.get("reviewed_at")):
        errors.append("reviewed_at must be an ISO-8601 timestamp with timezone")
    if submission.get("report_sha256_confirmed") != report_hash:
        errors.append("submission report hash does not match current Reader")
    if submission.get("traceability_appendix_sha256_confirmed") != appendix_hash:
        errors.append("submission appendix hash does not match current traceability appendix")

    decision = submission.get("decision")
    if decision not in ALLOWED_REVIEW_DECISIONS:
        errors.append("decision must be pass, needs_fix or reject")
    checklist = submission.get("required_checklist")
    rows = checklist if isinstance(checklist, list) else []
    by_id: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            errors.append("checklist row must be a mapping")
            continue
        check_id = str(row.get("check_id") or "")
        if check_id in by_id:
            errors.append(f"duplicate checklist id: {check_id}")
        by_id[check_id] = row
    if set(by_id) != set(REQUIRED_CHECK_IDS):
        errors.append("submission must contain exactly HR-1 through HR-6")
    invalid_statuses = {
        check_id: row.get("status")
        for check_id, row in by_id.items()
        if row.get("status") not in ALLOWED_CHECK_STATUSES
    }
    if invalid_statuses:
        errors.append(f"checklist contains pending or invalid statuses: {invalid_statuses}")

    blocking_comments = submission.get("blocking_comments")
    if not isinstance(blocking_comments, list):
        errors.append("blocking_comments must be a list")
        blocking_comments = []
    nonblocking_comments = submission.get("nonblocking_comments")
    if not isinstance(nonblocking_comments, list):
        errors.append("nonblocking_comments must be a list")

    attestation = submission.get("attestation")
    if not isinstance(attestation, Mapping):
        errors.append("attestation is required")
        attestation = {}
    required_attestations = {
        "external_human_review_confirmed": True,
        "report_read_in_full": True,
        "traceability_consulted_as_needed": True,
        "automated_agent_generated": False,
    }
    for key, expected in required_attestations.items():
        if attestation.get(key) is not expected:
            errors.append(f"attestation {key} must be {str(expected).lower()}")

    if handoff_status == "pending_external_human_review":
        if handoff.get("external_reviewer") is not None or handoff.get("reviewed_at") is not None:
            errors.append("pending handoff must not contain reviewer identity or timestamp")
        if handoff.get("sample_quality_report_allowed") is not False or handoff.get("p2_allowed") is not False:
            errors.append("pending handoff must keep sample quality and P2 false")
    elif handoff_status == "passed_external_human_review":
        if handoff.get("external_reviewer") != submission.get("external_reviewer"):
            errors.append("finalized handoff reviewer does not match submission")
        if handoff.get("reviewed_at") != submission.get("reviewed_at"):
            errors.append("finalized handoff reviewed_at does not match submission")
        if handoff.get("blocking_comments") != blocking_comments:
            errors.append("finalized handoff blocking comments do not match submission")
        if handoff.get("nonblocking_comments") != nonblocking_comments:
            errors.append("finalized handoff nonblocking comments do not match submission")
        handoff_rows = {
            str(row.get("check_id")): row
            for row in handoff.get("required_checklist") or []
            if isinstance(row, Mapping)
        }
        for check_id, row in by_id.items():
            handoff_row = handoff_rows.get(check_id) or {}
            if handoff_row.get("status") != row.get("status"):
                errors.append(f"finalized handoff checklist status mismatch: {check_id}")
            if handoff_row.get("comment") != row.get("comment"):
                errors.append(f"finalized handoff checklist comment mismatch: {check_id}")
        signoff = handoff.get("signoff_fields")
        if not isinstance(signoff, Mapping):
            errors.append("finalized handoff signoff_fields are missing")
            signoff = {}
        expected_signoff = {
            "decision": submission.get("decision"),
            "reviewer_name": submission.get("external_reviewer"),
            "reviewed_at": submission.get("reviewed_at"),
            "report_sha256_confirmed": submission.get("report_sha256_confirmed"),
            "blocking_comment_count": len(blocking_comments),
        }
        for key, expected in expected_signoff.items():
            if signoff.get(key) != expected:
                errors.append(f"finalized handoff signoff mismatch: {key}")
        if handoff.get("sample_quality_report_allowed") is not True or handoff.get("p2_allowed") is not False:
            errors.append("finalized handoff must allow sample quality and keep P2 false")

    checklist_pass = bool(by_id) and all(row.get("status") == "pass" for row in by_id.values())
    if decision == "pass" and not checklist_pass:
        errors.append("pass decision requires all six checklist rows to pass")
    if decision == "pass" and blocking_comments:
        errors.append("pass decision requires zero blocking comments")
    if decision in {"needs_fix", "reject"} and checklist_pass and not blocking_comments:
        errors.append("needs_fix/reject decision requires a failed check or blocking comment")

    return {
        "artifact_type": "R5_bundle10_human_review_submission_validation",
        "schema_version": "v0.1",
        "workflow_id": handoff.get("workflow_id"),
        "submission_path": submission_path.as_posix(),
        "reviewer": submission.get("external_reviewer"),
        "reviewed_at": submission.get("reviewed_at"),
        "external_review_decision": decision,
        "handoff_status": handoff_status,
        "report_sha256": report_hash,
        "traceability_appendix_sha256": appendix_hash,
        "checklist_pass_count": sum(
            1 for row in by_id.values() if row.get("status") == "pass"
        ),
        "blocking_comment_count": len(blocking_comments),
        "decision": "pass" if not errors else "fail",
        "eligible_for_bundle10_final_close": not errors and decision == "pass",
        "errors": errors,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a real external Bundle 10 human-review submission.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--workflow-id", default=DEFAULT_WORKFLOW_ID)
    parser.add_argument("--submission", required=True)
    parser.add_argument("--output", default="")
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    run = root / "reports/workflow_runs" / args.workflow_id
    submission = Path(args.submission)
    if not submission.is_absolute():
        submission = root / submission
    result = validate_submission(run, submission)
    if args.output:
        output = Path(args.output)
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
