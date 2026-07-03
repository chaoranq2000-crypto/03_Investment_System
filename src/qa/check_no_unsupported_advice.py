from __future__ import annotations

import re


ADVICE_PATTERNS = [
    r"买入",
    r"卖出",
    r"持有",
    r"加仓",
    r"减仓",
    r"仓位",
    r"立即交易",
    r"目标价",
]


def find_unsupported_advice(text: str) -> list[str]:
    hits = []
    for pattern in ADVICE_PATTERNS:
        if re.search(pattern, text):
            hits.append(pattern)
    return hits
