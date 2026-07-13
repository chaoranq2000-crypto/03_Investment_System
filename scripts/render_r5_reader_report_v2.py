from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.report.r5_reader_report_writer import (  # noqa: E402
    build_reader_report,
    build_traceability_appendix,
    load_yaml,
    validate_citations,
)


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a pack-driven R5 reader report.")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--workflow-run", required=True)
    parser.add_argument("--pack", default="R5_bundle10_reader_pack.yaml")
    parser.add_argument("--report", default="R5_stock_research_report_reader_v3.md")
    parser.add_argument("--appendix", default="R5_stock_research_report_traceability_v3.yaml")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    run = resolve_path(root, args.workflow_run)
    pack_path = resolve_path(run, args.pack)
    report_path = resolve_path(run, args.report)
    appendix_path = resolve_path(run, args.appendix)

    pack = load_yaml(pack_path)
    report = build_reader_report(pack)
    appendix = build_traceability_appendix(pack)
    unresolved = validate_citations(report, appendix)
    if unresolved:
        raise SystemExit(f"citation resolution failed: {unresolved}")

    report_path.write_text(report, encoding="utf-8")
    appendix_path.write_text(
        yaml.safe_dump(appendix, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(
        f"reader_report={report_path.relative_to(root).as_posix()} "
        f"sha256={hashlib.sha256(report_path.read_bytes()).hexdigest()} "
        f"appendix={appendix_path.relative_to(root).as_posix()} "
        "citations_resolved=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
