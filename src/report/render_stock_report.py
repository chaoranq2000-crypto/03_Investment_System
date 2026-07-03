from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from stock_report_writer import render_report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render stock_report_sample_quality_draft.md.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--template", default="templates/stock_report_sample_quality.md")
    parser.add_argument("--output", default="")
    args = parser.parse_args(argv)
    run_dir = Path(args.run_dir)
    output = Path(args.output) if args.output else run_dir / "stock_report_sample_quality_draft.md"
    result = render_report(run_dir=run_dir, template_path=Path(args.template), output_path=output)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
