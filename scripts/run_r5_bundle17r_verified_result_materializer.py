#!/usr/bin/env python3
"""CLI wrapper for Bundle 17R-BF2-EX1 verified result materialization."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.research.r5_bundle17r_verified_result_materializer import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
