from __future__ import annotations

import csv
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "ingest"))

from mineru_parse_runner import run_parse_job  # noqa: E402


def test_mineru_parse_runner_writes_normalized_outputs(tmp_path: Path) -> None:
    raw_pdf = tmp_path / "fixture.pdf"
    raw_pdf.write_text("公司主营业务包括数据中心温控和液冷解决方案。营业收入见年度报告。", encoding="utf-8")
    manifest = tmp_path / "data" / "manifests" / "evidence_manifest.csv"
    manifest.parent.mkdir(parents=True)
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "evidence_id",
                "source_type",
                "source_name",
                "reliability_rank",
                "entity_type",
                "entity_id",
                "company_id",
                "stock_code",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "evidence_id": "ev_fixture_001",
                "source_type": "annual_report",
                "source_name": "manual",
                "reliability_rank": "A",
                "entity_type": "company",
                "entity_id": "cn_002837_invic",
                "company_id": "cn_002837_invic",
                "stock_code": "002837",
            }
        )
    job = {
        "job_id": "job_fixture",
        "run_id": "wf_fixture",
        "evidence_id": "ev_fixture_001",
        "raw_pdf_path": str(raw_pdf),
        "normalization": {
            "processed_text_path": "data/processed/text/ev_fixture_001.md",
            "content_json_path": "data/processed/layout/ev_fixture_001_content.json",
            "middle_json_path": "data/processed/layout/ev_fixture_001_middle.json",
            "tables_path": "data/processed/tables/ev_fixture_001_tables.json",
            "page_map_path": "data/processed/page_maps/ev_fixture_001_page_map.yaml",
            "parse_log_path": "data/processed/logs/ev_fixture_001_parse_log.json",
        },
        "candidate_generation": {"generate_claim_candidates": True, "generate_metric_candidates": True},
    }
    job_path = tmp_path / "job.yaml"
    job_path.write_text(yaml.safe_dump(job, allow_unicode=True), encoding="utf-8")

    result = run_parse_job(job_path, tmp_path)

    assert result["page_count"] == 1
    assert (tmp_path / "data/processed/text/ev_fixture_001.md").exists()
    assert (tmp_path / "data/processed/page_maps/ev_fixture_001_page_map.yaml").exists()
    assert (tmp_path / "data/processed/tables/ev_fixture_001_tables.json").exists()
    assert result["candidate_info"]["claim_candidates"] >= 1
