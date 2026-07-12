#!/usr/bin/env python3
"""Build Bundle 8 analysis_pack_v2 and deterministic analysis subpacks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _bootstrap(repo_root: Path) -> None:
    text = str(repo_root)
    if text not in sys.path:
        sys.path.insert(0, text)


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


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
    parser.add_argument("--output")
    parser.add_argument(
        "--allow-blocked",
        action="store_true",
        help="Write blocked artifacts and return zero for planning/debug only.",
    )
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    _bootstrap(root)
    from src.research.r5_analysis_engine import (  # pylint: disable=import-outside-toplevel
        build_analysis_pack,
        build_analysis_subpacks,
        load_yaml,
        validate_analysis_pack,
        write_yaml,
    )

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
    output = Path(args.output) if args.output else run / "analysis_pack_v2.yaml"
    paths = [source_path, coverage_path, inputs_path, output]
    source_path, coverage_path, inputs_path, output = [
        path if path.is_absolute() else root / path for path in paths
    ]

    config = load_yaml(config_path)
    source_catalog = load_yaml(source_path)
    coverage_matrix = load_yaml(coverage_path)
    analysis_inputs = load_yaml(inputs_path)
    pack = build_analysis_pack(
        config,
        source_catalog,
        coverage_matrix,
        analysis_inputs,
        source_catalog_path=_relative(source_path, root),
        coverage_matrix_path=_relative(coverage_path, root),
        analysis_inputs_path=_relative(inputs_path, root),
    )
    write_yaml(output, pack)
    subpacks = build_analysis_subpacks(pack)
    output_names = {
        "thesis_tree": "thesis_tree.yaml",
        "business_driver_tree": "business_driver_tree.yaml",
        "segment_economics": "segment_economics.yaml",
        "competitive_position_matrix": "competitive_position_matrix.yaml",
        "risk_counterevidence_pack": "risk_counterevidence_pack.yaml",
    }
    for key, filename in output_names.items():
        write_yaml(run / filename, subpacks[key])

    gate = validate_analysis_pack(
        pack,
        config,
        source_catalog,
        coverage_matrix,
        analysis_inputs,
    )
    print(
        "bundle8_analysis_pack "
        f"decision={pack['summary']['decision']} "
        f"complete={pack['summary']['complete_units']}/"
        f"{pack['summary']['required_complete_units']} "
        f"blockers={pack['summary']['blocker_count']} "
        f"validator={gate['decision']}"
    )
    passed = gate["decision"] == "pass"
    return 0 if passed or args.allow_blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
