from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "ingest"))

from official_disclosure_pull import main as official_main  # noqa: E402
from structured_api_pull import main as structured_main  # noqa: E402


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_structured_api_pull_fixture_writes_manifest_and_metrics(tmp_path: Path) -> None:
    fixture = tmp_path / "income_fixture.csv"
    fixture.write_text(
        "ts_code,end_date,total_revenue,n_income_attr_p\n"
        "002837.SZ,20251231,1000,120\n"
        "002837.SZ,20241231,800,90\n",
        encoding="utf-8",
    )

    structured_main(
        [
            "--repo-root",
            str(tmp_path),
            "--source-name",
            "local_fixture",
            "--api-name",
            "income",
            "--stock-code",
            "002837",
            "--company-id",
            "company_002837",
            "--input-csv",
            str(fixture),
            "--as-of-date",
            "2026-07-02",
            "--publish-date",
            "2026-07-02",
            "--unit",
            "CNY",
        ]
    )

    manifest = read_csv(tmp_path / "data" / "manifests" / "evidence_manifest.csv")
    assert len(manifest) == 1
    assert manifest[0]["ingest_mode"] == "structured_api_pull"
    assert manifest[0]["material_claim_allowed"] == "metric_only"
    assert manifest[0]["raw_file_path"].startswith("data/raw/market_data/")
    assert manifest[0]["processed_table_path"].startswith("data/processed/normalized/")

    metrics = read_csv(tmp_path / "data" / "manifests" / "metrics_draft.csv")
    metric_names = {row["metric_name"] for row in metrics}
    assert {"total_revenue", "n_income_attr_p"}.issubset(metric_names)
    assert {row["review_status"] for row in metrics} == {"draft"}

    assert not list((tmp_path / "reports").glob("**/*_stock_deep_dive.md"))


def test_official_disclosure_local_file_writes_manifest(tmp_path: Path) -> None:
    local_file = tmp_path / "dummy_annual_report.pdf"
    local_file.write_bytes(b"%PDF-1.4 dummy annual report fixture")

    official_main(
        [
            "--repo-root",
            str(tmp_path),
            "--stock-code",
            "002837",
            "--company-id",
            "company_002837",
            "--company-name",
            "Invic",
            "--source-name",
            "manual",
            "--source-type",
            "annual_report",
            "--filing-type",
            "annual_report",
            "--title",
            "Invic annual report fixture",
            "--publisher",
            "manual fixture",
            "--publish-date",
            "2026-04-30",
            "--local-file",
            str(local_file),
        ]
    )

    manifest = read_csv(tmp_path / "data" / "manifests" / "evidence_manifest.csv")
    assert len(manifest) == 1
    row = manifest[0]
    assert row["source_type"] == "annual_report"
    assert row["reliability_rank"] == "A"
    assert row["material_claim_allowed"] == "requires_extraction_and_review"
    assert row["raw_file_path"].startswith("data/raw/annual_reports/")
    assert row["source_url"] == ""

    log_files = list((tmp_path / "data" / "processed" / "logs").glob("*__ingest_log.json"))
    assert len(log_files) == 1
    log_payload = json.loads(log_files[0].read_text(encoding="utf-8"))
    assert log_payload["result"] == "SUCCESS"

    assert not list((tmp_path / "reports").glob("**/*_stock_deep_dive.md"))
