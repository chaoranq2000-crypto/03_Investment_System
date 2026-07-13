#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from src.report.r5_bundle10r_contracts import dump_yaml, load_yaml, validate_model_generation_lock
from src.report.r5_reader_payload_v4 import normalize_reader_payload
from src.report.r5_reader_writer_v4 import render_reader_report as render_reader_report_v4
from src.report.r5_reader_writer_v5 import render_reader_report as render_reader_report_v5
from src.report.r5_traceability_v4 import build_traceability_appendix


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Bundle 10R normalized payload, Reader, and traceability appendix")
    parser.add_argument("--reader-input", required=True)
    parser.add_argument("--reader-contract", required=True)
    parser.add_argument("--binding", required=True)
    parser.add_argument("--model-lock", required=True)
    parser.add_argument("--payload-output", required=True)
    parser.add_argument("--report-output", required=True)
    parser.add_argument("--appendix-output", required=True)
    parser.add_argument("--writer-version", choices=("v4", "v5"), default="v4")
    parser.add_argument("--narrative-plan", help="Optional v5 chapter plan merged into the normalized payload")
    args = parser.parse_args()

    binding = load_yaml(args.binding)
    model_lock = load_yaml(args.model_lock)
    check = validate_model_generation_lock(model_lock, binding)
    if check["decision"] != "pass":
        raise SystemExit("model generation is stale or invalid")

    reader_input = load_yaml(args.reader_input)
    if args.narrative_plan:
        if args.writer_version != "v5":
            raise SystemExit("--narrative-plan requires --writer-version v5")
        narrative_plan = load_yaml(args.narrative_plan)
        reader_input["narrative_chapters"] = narrative_plan.get("narrative_chapters") or []

    payload = normalize_reader_payload(
        reader_input,
        model_generation_id=model_lock["generation_id"],
        model_aggregate_sha256=model_lock["aggregate_sha256"],
        reader_contract=load_yaml(args.reader_contract),
        schema_version=args.writer_version,
    )
    renderer = render_reader_report_v5 if args.writer_version == "v5" else render_reader_report_v4
    report = renderer(payload)
    appendix = build_traceability_appendix(payload, report, schema_version=args.writer_version)
    dump_yaml(payload, args.payload_output)
    Path(args.report_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_output).write_text(report, encoding="utf-8", newline="\n")
    dump_yaml(appendix, args.appendix_output)
    print(f"sections={len(payload['sections'])} refs={appendix['used_display_reference_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
