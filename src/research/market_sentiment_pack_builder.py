from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import yaml


def build_market_sentiment_pack(
    *,
    output_path: Path,
    as_of_date: str,
    stock_code: str,
    clue_source: str = "TODO_SOURCE_REQUIRED",
) -> dict[str, object]:
    pack = {
        "stock_code": stock_code,
        "as_of_date": as_of_date,
        "macro_sentiment": {
            "status": "TODO_SOURCE_REQUIRED",
            "source": clue_source,
            "claim_type": "clue",
        },
        "industry_sentiment": {
            "status": "LOW_CONFIDENCE_CLUE_ONLY",
            "source": clue_source,
            "claim_type": "clue",
        },
        "company_sentiment": {
            "status": "TODO_SOURCE_REQUIRED",
            "source": clue_source,
            "claim_type": "clue",
        },
        "notes": "Sentiment clues must not be written as facts.",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(pack, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return pack


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a minimal market sentiment pack.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--stock-code", required=True)
    parser.add_argument("--clue-source", default="TODO_SOURCE_REQUIRED")
    args = parser.parse_args(argv)
    print(
        build_market_sentiment_pack(
            output_path=Path(args.output),
            as_of_date=args.as_of_date,
            stock_code=args.stock_code,
            clue_source=args.clue_source,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
