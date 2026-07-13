from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.report.r5_reader_report_writer import build_traceability_appendix, load_yaml  # noqa: E402


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a traceability appendix from an R5 reader pack.")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--workflow-run", required=True)
    parser.add_argument("--pack", default="R5_bundle10_reader_pack.yaml")
    parser.add_argument("--output", default="R5_stock_research_report_traceability_v3.yaml")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    run = resolve_path(root, args.workflow_run)
    pack = load_yaml(resolve_path(run, args.pack))
    appendix = build_traceability_appendix(pack)
    output = resolve_path(run, args.output)
    output.write_text(yaml.safe_dump(appendix, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"traceability_appendix={output.relative_to(root).as_posix()} records={len(appendix['records'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
