from __future__ import annotations

import csv
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "ingest"))

from pdf_candidate_extractor import extract_candidates_from_page_map  # noqa: E402


def test_pdf_candidate_extractor_requires_locator_fields(tmp_path: Path) -> None:
    page_map = tmp_path / "page_map.yaml"
    page_map.write_text(
        yaml.safe_dump(
            [{"page_no": 2, "text": "公司披露数据中心液冷温控产品，营业收入仍需表格核验。"}],
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    result = extract_candidates_from_page_map(
        page_map_path=page_map,
        manifest_row={
            "evidence_id": "ev_annual_001",
            "source_type": "annual_report",
            "source_name": "szse",
            "reliability_rank": "A",
            "entity_type": "company",
            "entity_id": "cn_002837_invic",
            "company_id": "cn_002837_invic",
            "stock_code": "002837",
        },
        output_dir=tmp_path,
    )
    rows = list(csv.DictReader(Path(result["claim_candidates_path"]).open("r", encoding="utf-8", newline="")))
    assert rows
    assert all(row["evidence_id"] == "ev_annual_001" for row in rows)
    assert any(row["page_no_or_section"] == "page:2" for row in rows)
    assert any("液冷" in row["claim_text"] for row in rows)
