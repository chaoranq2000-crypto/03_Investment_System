from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Mapping


TABLE_KEYWORDS = (
    "营业收入",
    "毛利率",
    "净利润",
    "分行业",
    "分产品",
    "客户",
    "供应商",
    "资产",
    "负债",
    "现金流",
)


def _looks_like_table_line(text: str) -> bool:
    compact = text.strip()
    if not compact:
        return False
    has_keyword = any(keyword in compact for keyword in TABLE_KEYWORDS)
    has_digit = bool(re.search(r"\d", compact))
    has_spacing = bool(re.search(r"\s{2,}|\t|\|", compact))
    return has_digit and (has_keyword or has_spacing)


def build_table_inventory(
    *,
    evidence_id: str,
    pages: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    inventory: list[dict[str, object]] = []
    for page in pages:
        page_no = int(page.get("page_no", 0) or 0)
        text = str(page.get("text", ""))
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for index, line in enumerate(lines, start=1):
            if not _looks_like_table_line(line):
                continue
            inventory.append(
                {
                    "table_id": f"{evidence_id}_p{page_no}_t{index}",
                    "evidence_id": evidence_id,
                    "page_no": page_no,
                    "table_title": line[:80],
                    "parse_status": "line_inventory",
                    "text_excerpt": line[:240],
                }
            )
    return inventory


def write_table_inventory(path: Path, inventory: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
