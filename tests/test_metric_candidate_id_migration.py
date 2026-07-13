from __future__ import annotations

import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from migrate_metric_candidate_ids_to_company_prefix import migrate  # noqa: E402


def test_metric_candidate_id_migration_preserves_rows_and_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "metrics.csv"
    fields = ["metric_candidate_id", "entity_id", "company_id", "stock_code", "metric_name", "period", "value"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "metric_candidate_id": "metric_income_002837_20251231_total_revenue_a1b2c3d4",
                "entity_id": "cn_002837_invic",
                "company_id": "cn_002837_invic",
                "stock_code": "002837",
                "metric_name": "total_revenue",
                "period": "20251231",
                "value": "100",
            }
        )
    first = migrate(path)
    second = migrate(path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert first == {"rows": 1, "changed": 1, "unique": 1}
    assert second == {"rows": 1, "changed": 0, "unique": 1}
    assert rows[0]["metric_candidate_id"] == (
        "metric_company_cn_002837_invic_total_revenue_20251231_a1b2c3d4"
    )
    assert rows[0]["value"] == "100"
