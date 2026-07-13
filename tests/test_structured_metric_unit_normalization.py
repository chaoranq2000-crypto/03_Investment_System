from __future__ import annotations

import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from normalize_structured_metric_candidate_units import normalize  # noqa: E402


def test_unit_normalization_fills_units_and_removes_numeric_codes(tmp_path: Path) -> None:
    path = tmp_path / "metrics.csv"
    fields = [
        "metric_candidate_id",
        "source_name",
        "metric_category",
        "metric_name",
        "unit",
        "original_unit_text",
        "currency",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(
            [
                {
                    "metric_candidate_id": "metric_company_x_close_20260710_aaaaaa",
                    "source_name": "tushare",
                    "metric_category": "daily",
                    "metric_name": "close",
                    "unit": "",
                    "notes": "draft",
                },
                {
                    "metric_candidate_id": "metric_company_x_update_flag_20260710_bbbbbb",
                    "source_name": "tushare",
                    "metric_category": "income",
                    "metric_name": "update_flag",
                    "unit": "",
                    "notes": "draft",
                },
            ]
        )
    result = normalize(path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert result == {
        "rows_before": 2,
        "rows_after": 1,
        "units_changed": 1,
        "nonmetric_rows_removed": 1,
    }
    assert rows[0]["unit"] == "CNY_per_share"
    assert rows[0]["currency"] == "CNY"
