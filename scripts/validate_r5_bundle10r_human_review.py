#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.report.r5_bundle10r_contracts import load_yaml, sha256_file


REQUIRED_ATTESTATIONS = (
    "human_review_confirmed",
    "report_read_in_full",
    "traceability_consulted_as_needed",
    "automated_gate_not_substitute",
    "no_direct_advice_confirmed",
)


def _issue(code: str, detail: str) -> dict[str, str]:
    return {"code": code, "detail": detail}


def validate(
    *,
    report: str | Path,
    appendix: str | Path,
    scorecard: str | Path,
    handoff: str | Path,
    reader_lock: str | Path,
    submission: str | Path,
) -> dict[str, Any]:
    paths = {
        "report_sha256": Path(report),
        "appendix_sha256": Path(appendix),
        "scorecard_sha256": Path(scorecard),
        "handoff_sha256": Path(handoff),
        "generation_lock_sha256": Path(reader_lock),
    }
    scorecard_doc = load_yaml(scorecard)
    handoff_doc = load_yaml(handoff)
    lock_doc = load_yaml(reader_lock)
    submission_doc = load_yaml(submission)
    issues: list[dict[str, str]] = []

    if submission_doc.get("decision") != "accepted":
        issues.append(_issue("human_review_not_accepted", repr(submission_doc.get("decision"))))
    if not str(submission_doc.get("reviewer") or "").strip():
        issues.append(_issue("human_reviewer_missing", "reviewer is empty"))
    try:
        reviewed_at = datetime.fromisoformat(str(submission_doc.get("reviewed_at") or ""))
        if reviewed_at.tzinfo is None or reviewed_at.utcoffset() is None:
            raise ValueError("timezone offset missing")
    except ValueError as exc:
        issues.append(_issue("reviewed_at_invalid", str(exc)))

    attestations = submission_doc.get("attestation") or {}
    for key in REQUIRED_ATTESTATIONS:
        if attestations.get(key) is not True:
            issues.append(_issue("human_attestation_missing", key))

    expected_checks = list(handoff_doc.get("review_checklist") or [])
    checklist = submission_doc.get("review_checklist") or []
    actual_checks = [item.get("check") for item in checklist if isinstance(item, dict)]
    if actual_checks != expected_checks:
        issues.append(_issue("review_checklist_mismatch", "submission checklist does not match the handoff"))
    if not checklist:
        issues.append(_issue("review_checklist_missing", "review checklist is empty"))
    for item in checklist:
        if not isinstance(item, dict) or item.get("status") != "pass":
            issues.append(_issue("review_check_not_passed", repr(item)))

    submitted_hashes = submission_doc.get("input_hashes") or {}
    verified_hash_count = 0
    for key, path in paths.items():
        actual = sha256_file(path)
        expected = submitted_hashes.get(key)
        if actual != expected:
            issues.append(_issue("review_input_hash_mismatch", f"{key}: expected={expected}; actual={actual}"))
        else:
            verified_hash_count += 1

    if scorecard_doc.get("decision") != "candidate_ready_for_human_review":
        issues.append(_issue("automated_candidate_not_ready", repr(scorecard_doc.get("decision"))))
    for key in ("truthfulness_blockers", "core_section_blockers", "candidate_blockers"):
        if scorecard_doc.get(key) != []:
            issues.append(_issue("automated_blocker_present", key))

    if lock_doc.get("missing_artifact_count") != 0:
        issues.append(_issue("reader_lock_has_missing_artifacts", repr(lock_doc.get("missing_artifact_count"))))
    locked_verified = 0
    artifacts = lock_doc.get("artifacts") or []
    for artifact in artifacts:
        artifact_path = REPO_ROOT / str(artifact.get("path") or "")
        if not artifact_path.is_file():
            issues.append(_issue("locked_artifact_missing", str(artifact_path)))
            continue
        actual = sha256_file(artifact_path)
        if actual != artifact.get("sha256"):
            issues.append(_issue("locked_artifact_hash_mismatch", str(artifact_path)))
        else:
            locked_verified += 1

    for key in ("sample_quality_allowed", "p2_allowed"):
        if submission_doc.get(key) is not False:
            issues.append(_issue("prohibited_scope_enabled", key))

    return {
        "artifact_type": "R5_bundle10r_human_review_validation",
        "schema_version": 1,
        "decision": "pass" if not issues else "needs_fix",
        "issue_count": len(issues),
        "issues": issues,
        "verified_input_hash_count": verified_hash_count,
        "verified_locked_artifact_count": locked_verified,
        "reviewer": submission_doc.get("reviewer"),
        "reviewed_at": submission_doc.get("reviewed_at"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Bundle 10R Reader v5 human-review submission")
    parser.add_argument("--report", required=True)
    parser.add_argument("--appendix", required=True)
    parser.add_argument("--scorecard", required=True)
    parser.add_argument("--handoff", required=True)
    parser.add_argument("--reader-lock", required=True)
    parser.add_argument("--submission", required=True)
    args = parser.parse_args()
    result = validate(
        report=args.report,
        appendix=args.appendix,
        scorecard=args.scorecard,
        handoff=args.handoff,
        reader_lock=args.reader_lock,
        submission=args.submission,
    )
    print(
        f"decision={result['decision']} issues={result['issue_count']} "
        f"input_hashes={result['verified_input_hash_count']} locked={result['verified_locked_artifact_count']}"
    )
    return 0 if result["decision"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
