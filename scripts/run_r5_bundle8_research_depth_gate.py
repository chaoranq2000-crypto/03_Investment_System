#!/usr/bin/env python3
"""Run the combined Bundle 8 evidence + analysis gate without state mutation."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Any

import yaml


def _bootstrap(repo_root: Path) -> None:
    text = str(repo_root)
    if text not in sys.path:
        sys.path.insert(0, text)


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _render_readout(report: dict[str, Any]) -> str:
    evidence = report["subgates"]["evidence_coverage"]
    analysis = report["subgates"]["analysis_pack"]
    deferred = report["scope_boundaries"]["deferred"]
    return "\n".join(
        [
            "# R5 Bundle 8 Research Depth Gate",
            "",
            f"- Decision: `{report['decision']}`",
            f"- Workflow: `{report['workflow_id']}`",
            f"- As of: `{report['as_of_date']}`",
            f"- Evidence gate: `{evidence['decision']}`",
            f"- Analysis gate: `{analysis['decision']}`",
            f"- Evidence errors: {len(evidence['errors'])}",
            f"- Analysis errors: {len(analysis['errors'])}",
            "",
            "## Scope boundary",
            "",
            "This gate only decides whether M3/M4 research inputs are ready. "
            "It does not regenerate the reader report, mutate canonical workflow "
            "state, or close Bundle 8.",
            "",
            "Deferred to later bundles:",
            *[f"- `{item}`" for item in deferred],
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument(
        "--workflow-run",
        default="reports/workflow_runs/wf_20260703_stock_first_002837_invic",
    )
    parser.add_argument("--config", default="config/r5_bundle8_research_depth.yaml")
    parser.add_argument("--source-catalog")
    parser.add_argument("--coverage-matrix")
    parser.add_argument("--analysis-inputs")
    parser.add_argument("--analysis-pack")
    parser.add_argument("--report-output")
    parser.add_argument("--readout-output")
    parser.add_argument("--as-of-date", default=dt.date.today().isoformat())
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    _bootstrap(root)
    from src.research.r5_analysis_engine import validate_analysis_pack
    from src.research.r5_evidence_coverage import validate_coverage_matrix

    run = Path(args.workflow_run)
    if not run.is_absolute():
        run = root / run
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = root / config_path
    source_path = (
        Path(args.source_catalog)
        if args.source_catalog
        else run / "R5_bundle8_evidence_source_catalog.yaml"
    )
    coverage_path = (
        Path(args.coverage_matrix)
        if args.coverage_matrix
        else run / "evidence_coverage_matrix.yaml"
    )
    inputs_path = (
        Path(args.analysis_inputs)
        if args.analysis_inputs
        else run / "R5_bundle8_analysis_inputs_v2.yaml"
    )
    analysis_path = (
        Path(args.analysis_pack)
        if args.analysis_pack
        else run / "analysis_pack_v2.yaml"
    )
    report_path = (
        Path(args.report_output)
        if args.report_output
        else run / "R5_bundle8_research_depth_gate.yaml"
    )
    readout_path = (
        Path(args.readout_output)
        if args.readout_output
        else run / "R5_bundle8_research_depth_gate.md"
    )
    source_path = source_path if source_path.is_absolute() else root / source_path
    coverage_path = coverage_path if coverage_path.is_absolute() else root / coverage_path
    inputs_path = inputs_path if inputs_path.is_absolute() else root / inputs_path
    analysis_path = analysis_path if analysis_path.is_absolute() else root / analysis_path
    report_path = report_path if report_path.is_absolute() else root / report_path
    readout_path = readout_path if readout_path.is_absolute() else root / readout_path

    config = _load(config_path)
    source_catalog = _load(source_path)
    coverage = _load(coverage_path)
    analysis_inputs = _load(inputs_path)
    analysis = _load(analysis_path)
    evidence_gate = validate_coverage_matrix(coverage, config, source_catalog)
    analysis_gate = validate_analysis_pack(
        analysis,
        config,
        source_catalog,
        coverage,
        analysis_inputs,
    )
    passed = evidence_gate["decision"] == "pass" and analysis_gate["decision"] == "pass"
    report = {
        "artifact_type": "R5_bundle8_research_depth_gate",
        "schema_version": "v0.1",
        "bundle_id": config.get("bundle_id", "R5_BUNDLE_8_RESEARCH_DEPTH"),
        "workflow_id": coverage.get("workflow_id") or analysis.get("workflow_id") or run.name,
        "as_of_date": args.as_of_date,
        "decision": (
            "bundle8_research_depth_inputs_ready"
            if passed
            else "bundle8_research_depth_inputs_blocked"
        ),
        "subgates": {
            "evidence_coverage": evidence_gate,
            "analysis_pack": analysis_gate,
        },
        "scope_boundaries": {
            "workflow_state_mutated": False,
            "reader_regenerated": False,
            "bundle_closed": False,
            "deferred": [
                "segment_forecast_model",
                "reverse_valuation",
                "scenario_valuation",
                "technical_snapshot",
                "market_sentiment_pack",
                "catalyst_calendar",
                "reader_report_writer",
                "end_to_end_sample_benchmark",
            ],
        },
    }
    _write(report_path, report)
    readout_path.parent.mkdir(parents=True, exist_ok=True)
    readout_path.write_text(_render_readout(report), encoding="utf-8")
    print(
        "bundle8_research_depth_gate "
        f"decision={report['decision']} "
        f"evidence={evidence_gate['decision']} analysis={analysis_gate['decision']}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
