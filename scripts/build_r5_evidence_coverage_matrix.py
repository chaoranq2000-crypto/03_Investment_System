#!/usr/bin/env python3
"""Build Bundle 8 evidence coverage matrix and source-only handoff packs."""

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
    parser.add_argument("--output")
    parser.add_argument("--industry-output")
    parser.add_argument("--peer-output")
    parser.add_argument("--company-output")
    parser.add_argument("--as-of-date")
    parser.add_argument(
        "--allow-blocked",
        action="store_true",
        help="Write blocked artifacts and return zero for planning/debug only.",
    )
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    _bootstrap(root)
    from src.research.r5_evidence_coverage import (  # pylint: disable=import-outside-toplevel
        build_coverage_matrix,
        build_evidence_packs,
        load_yaml,
        validate_coverage_matrix,
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
    if not source_path.is_absolute():
        source_path = root / source_path
    output = Path(args.output) if args.output else run / "evidence_coverage_matrix.yaml"
    industry_output = (
        Path(args.industry_output)
        if args.industry_output
        else run / "industry_evidence_pack.yaml"
    )
    peer_output = Path(args.peer_output) if args.peer_output else run / "peer_operating_pack.yaml"
    company_output = (
        Path(args.company_output)
        if args.company_output
        else run / "company_operating_evidence_pack.yaml"
    )
    output = output if output.is_absolute() else root / output
    industry_output = industry_output if industry_output.is_absolute() else root / industry_output
    peer_output = peer_output if peer_output.is_absolute() else root / peer_output
    company_output = company_output if company_output.is_absolute() else root / company_output

    config = load_yaml(config_path)
    catalog = load_yaml(source_path)
    matrix = build_coverage_matrix(
        config,
        catalog,
        workflow_id=str(catalog.get("workflow_id") or run.name),
        as_of_date=args.as_of_date,
        source_catalog_path=_relative(source_path, root),
    )
    write_yaml(output, matrix)
    packs = build_evidence_packs(catalog, matrix, config)
    write_yaml(industry_output, packs["industry_evidence_pack"])
    write_yaml(peer_output, packs["peer_operating_pack"])
    write_yaml(company_output, packs["company_operating_evidence_pack"])

    gate = validate_coverage_matrix(matrix, config, catalog)
    print(
        "bundle8_evidence_coverage "
        f"decision={matrix['summary']['decision']} "
        f"covered={matrix['summary']['covered_requirements']}/"
        f"{matrix['summary']['total_requirements']} "
        f"blockers={matrix['summary']['blocking_requirements_open']} "
        f"validator={gate['decision']}"
    )
    passed = gate["decision"] == "pass"
    return 0 if passed or args.allow_blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
