#!/usr/bin/env python3
from __future__ import annotations

import argparse

from src.report.r5_bundle10r_contracts import dump_yaml, load_yaml, sha256_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a truthful Bundle 10R human-review handoff")
    parser.add_argument("--report", required=True)
    parser.add_argument("--appendix", required=True)
    parser.add_argument("--scorecard", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report-schema-version", default="v4")
    parser.add_argument("--supersedes-report-sha256")
    args = parser.parse_args()

    scorecard = load_yaml(args.scorecard)
    if scorecard.get("decision") != "candidate_ready_for_human_review":
        raise SystemExit("automated candidate gate must pass before human-review handoff")
    handoff = {
        "artifact_type": "R5_bundle10r_human_review_handoff",
        "schema_version": 1,
        **({"report_schema_version": args.report_schema_version} if args.report_schema_version != "v4" else {}),
        "status": "pending",
        "automated_candidate_decision": scorecard.get("decision"),
        "input_model_generation_id": scorecard.get("input_model_generation_id"),
        "input_hashes": {
            "report_sha256": sha256_file(args.report),
            "appendix_sha256": sha256_file(args.appendix),
            "scorecard_sha256": sha256_file(args.scorecard),
        },
        "review_checklist": [
            "core thesis is company-specific and supported",
            "forecast assumptions and causal bridge are understandable",
            "valuation explains market-implied expectations and method limits",
            "counterevidence and falsification conditions are decision-useful",
            "technical, sentiment, and future events are dated and conditional",
            "no claim boundary is stronger than its evidence",
            "no direct trading instruction or target price appears",
        ],
        "reviewer": None,
        "reviewed_at": None,
        "decision": None,
        "comments": None,
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
    if args.report_schema_version != "v4":
        handoff["review_checklist"].append(
            "narrative reads like coherent analyst research rather than a repeated audit scaffold"
        )
    if args.supersedes_report_sha256:
        handoff["supersedes_report_sha256"] = args.supersedes_report_sha256
    dump_yaml(handoff, args.output)
    print("human_review_status=pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
