from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.report.r5_reader_report_writer import build_reader_report, load_yaml, validate_citations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(ROOT))
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    run = root / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"
    report = build_reader_report(load_yaml(run / "R5_bundle6_reader_section_payloads.yaml"), load_yaml(run / "R5_bundle6_forecast_bridge.yaml"), load_yaml(run / "R5_bundle6_valuation_reasoning_pack.yaml"))
    appendix = load_yaml(run / "R5_stock_research_report_traceability_v2.yaml")
    unresolved = validate_citations(report, appendix)
    if unresolved:
        raise SystemExit(f"citation resolution failed: {unresolved}")
    output = run / "R5_stock_research_report_reader_v2.md"
    output.write_text(report, encoding="utf-8")
    print(f"reader_report={output.relative_to(root).as_posix()} sha256={hashlib.sha256(output.read_bytes()).hexdigest()} citations_resolved=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
