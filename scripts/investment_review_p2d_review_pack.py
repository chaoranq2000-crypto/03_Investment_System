"""Standalone launcher for the P2D review fact-pack builder."""

from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.investment_review.review_pack import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
