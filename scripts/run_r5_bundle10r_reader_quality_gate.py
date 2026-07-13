#!/usr/bin/env python3
from __future__ import annotations

import argparse

from src.quality.r5_bundle10r_reader_gate import evaluate_reader_candidate
from src.report.r5_bundle10r_contracts import dump_yaml, load_yaml


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Bundle 10R non-compensating Reader gate")
    parser.add_argument("--payload", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--appendix", required=True)
    parser.add_argument("--binding", required=True)
    parser.add_argument("--reader-contract", required=True)
    parser.add_argument("--quality-contract", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    report = open(args.report, encoding="utf-8").read()
    result = evaluate_reader_candidate(
        load_yaml(args.payload),
        report,
        load_yaml(args.appendix),
        load_yaml(args.binding),
        load_yaml(args.reader_contract),
        load_yaml(args.quality_contract),
    )
    dump_yaml(result, args.output)
    print(
        f"decision={result['decision']} score={result['score']} "
        f"truth={len(result['truthfulness_blockers'])} core={len(result['core_section_blockers'])} "
        f"candidate={len(result['candidate_blockers'])}"
    )
    return 0 if result["decision"] == "candidate_ready_for_human_review" else 2


if __name__ == "__main__":
    raise SystemExit(main())
