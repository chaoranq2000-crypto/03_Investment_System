from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.report.r5_section_payload_builder import build_payloads, load_inputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(ROOT))
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    run_dir = root / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"
    output = run_dir / "R5_bundle6_reader_section_payloads.yaml"
    output.write_text(yaml.safe_dump(build_payloads(load_inputs(run_dir)), allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"reader_section_payloads={output.relative_to(root).as_posix()} status=ready sample_quality=false p2=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
