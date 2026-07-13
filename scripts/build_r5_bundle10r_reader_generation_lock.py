#!/usr/bin/env python3
from __future__ import annotations

import argparse

from src.report.r5_bundle10r_contracts import dump_yaml, load_yaml
from src.report.r5_reader_generation import build_reader_generation_lock


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Bundle 10R Reader-generation lock")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--binding", required=True)
    parser.add_argument("--human-review-handoff", required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--artifact", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--generation-label", default="r5_bundle10r_reader")
    parser.add_argument("--generation-id-prefix", default="reader_gen_r5_bundle10r")
    args = parser.parse_args()

    binding = load_yaml(args.binding)
    handoff = load_yaml(args.human_review_handoff)
    lock = build_reader_generation_lock(
        args.repo_root,
        args.artifact,
        model_generation_id=binding["expected_model_generation_id"],
        model_aggregate_sha256=binding["expected_model_aggregate_sha256"],
        evidence_generation_id=binding["expected_evidence_generation_id"],
        created_at=args.created_at,
        human_review_status=handoff.get("status") or "pending",
        generation_label=args.generation_label,
        generation_id_prefix=args.generation_id_prefix,
    )
    if lock["missing_artifact_count"]:
        dump_yaml(lock, args.output)
        raise SystemExit(f"missing Reader artifacts: {lock['missing_artifacts']}")
    dump_yaml(lock, args.output)
    print(f"generation_id={lock['generation_id']} artifacts={lock['artifact_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
