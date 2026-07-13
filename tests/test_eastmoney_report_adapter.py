from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "ingest"))

from adapters.eastmoney_report_adapter import main  # noqa: E402


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_fixture_ingest_preserves_analyst_view_boundary(tmp_path: Path) -> None:
    fixture = tmp_path / "report.json"
    fixture.write_text(
        json.dumps(
            {
                "hits": 1,
                "size": 1,
                "data": [
                    {
                        "title": "测试报告",
                        "stockName": "英维克",
                        "stockCode": "002837",
                        "orgSName": "测试券商",
                        "publishDate": "2026-04-24 00:00:00.000",
                        "infoCode": "AP_TEST_001",
                        "predictThisYearEps": "1.20",
                        "predictThisYearPe": "50.0",
                        "predictNextYearEps": "1.50",
                        "predictNextYearPe": "40.0",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "--repo-root",
                str(tmp_path),
                "--stock-code",
                "002837",
                "--company-id",
                "cn_002837_invic",
                "--company-name",
                "英维克",
                "--as-of-date",
                "2026-07-13",
                "--fixture-json",
                str(fixture),
                "--mode",
                "fixture",
            ]
        )
        == 0
    )
    manifest = read_csv(tmp_path / "data/manifests/evidence_manifest.csv")
    assert manifest[0]["source_name"] == "eastmoney_push2"
    assert manifest[0]["source_type"] == "third_party_research"
    assert manifest[0]["material_claim_allowed"] == "false"
    assert manifest[0]["allowed_claim_types"] == "analyst_view;estimate"
    metrics = read_csv(tmp_path / "data/manifests/metrics_draft.csv")
    assert {row["metric_name"] for row in metrics} == {
        "analyst_eps_estimate",
        "analyst_pe_estimate",
    }
    assert {row["period"] for row in metrics} == {"2026", "2027"}
    assert all(row["is_estimate"] == "true" for row in metrics)
    assert all(row["review_status"] == "draft" for row in metrics)
    assert all(row["metric_candidate_id"].startswith("metric_company_") for row in metrics)
    normalized = read_csv(tmp_path / manifest[0]["processed_table_path"])
    assert "rating_name" not in normalized[0]


def test_live_mode_requires_explicit_network_permission(tmp_path: Path, capsys) -> None:
    assert (
        main(
            [
                "--repo-root",
                str(tmp_path),
                "--stock-code",
                "002837",
                "--as-of-date",
                "2026-07-13",
                "--mode",
                "live",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"result": "BLOCKED", "reason": "live mode requires --allow-network"}
