#!/usr/bin/env python3
from __future__ import annotations

import argparse

from src.report.r5_bundle10r_contracts import load_yaml


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Bundle 10R close boundary")
    parser.add_argument("--scorecard", required=True)
    parser.add_argument("--reader-lock", required=True)
    parser.add_argument("--human-review-handoff", required=True)
    args = parser.parse_args()

    scorecard = load_yaml(args.scorecard)
    lock = load_yaml(args.reader_lock)
    handoff = load_yaml(args.human_review_handoff)
    issues: list[str] = []
    if scorecard.get("decision") != "candidate_ready_for_human_review":
        issues.append("candidate gate did not pass")
    if scorecard.get("truthfulness_blockers"):
        issues.append("truthfulness blockers remain")
    if scorecard.get("core_section_blockers"):
        issues.append("core-section blockers remain")
    if scorecard.get("candidate_blockers"):
        issues.append("candidate blockers remain")
    if int(lock.get("missing_artifact_count", -1)) != 0:
        issues.append("Reader generation lock has missing artifacts")
    if handoff.get("status") not in {"pending", "accepted", "rejected", "revision_required"}:
        issues.append("invalid human-review status")
    if lock.get("sample_quality_allowed") is not False or lock.get("p2_allowed") is not False:
        issues.append("close lock improperly enables sample quality or P2")
    print(f"decision={'pass' if not issues else 'needs_fix'} issues={len(issues)}")
    for issue in issues:
        print(f"- {issue}")
    return 0 if not issues else 2


if __name__ == "__main__":
    raise SystemExit(main())
