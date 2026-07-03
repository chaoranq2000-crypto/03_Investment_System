from __future__ import annotations

import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "qa"))

from data_layer_quality_review import review_data_layer_run  # noqa: E402


HEADER = [
    "evidence_id",
    "source_type",
    "source_name",
    "source_group",
    "title",
    "publisher",
    "publish_date",
    "retrieved_at",
    "ingested_at",
    "as_of_date",
    "entity_type",
    "entity_id",
    "segment_id",
    "company_id",
    "stock_code",
    "source_url",
    "raw_file_path",
    "raw_archive_policy",
    "file_hash",
    "content_hash",
    "api_params_hash",
    "processed_text_path",
    "processed_table_path",
    "page_map_path",
    "page_count",
    "language",
    "file_format",
    "ingest_mode",
    "reliability_rank",
    "material_claim_allowed",
    "allowed_claim_types",
    "license_note",
    "stale_after",
    "status",
    "parse_status",
    "candidate_status",
    "review_status",
    "previous_evidence_id",
    "superseded_by",
    "notes",
]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_good_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run"
    raw_path = tmp_path / "data/raw/market_data/snapshot.csv"
    table_path = tmp_path / "data/processed/normalized/snapshot.csv"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    table_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text("ts_code,end_date,total_revenue\n002837.SZ,20251231,1000\n", encoding="utf-8")
    table_path.write_text("ts_code,end_date,total_revenue\n002837.SZ,20251231,1000\n", encoding="utf-8")
    write_csv(
        run_dir / "evidence_manifest.csv",
        HEADER,
        [
            {
                "evidence_id": "ev_structured_financial_data_002837_20260701_abcdef",
                "source_type": "structured_financial_data",
                "source_name": "local_fixture",
                "source_group": "structured_database",
                "title": "fixture",
                "publisher": "local_fixture",
                "publish_date": "2026-07-01",
                "retrieved_at": "2026-07-01T00:00:00Z",
                "ingested_at": "2026-07-01T00:00:00Z",
                "as_of_date": "2026-07-01",
                "entity_type": "company",
                "entity_id": "cn_002837_invic",
                "company_id": "cn_002837_invic",
                "stock_code": "002837",
                "raw_file_path": "data/raw/market_data/snapshot.csv",
                "raw_archive_policy": "snapshot_archived",
                "file_hash": "a" * 64,
                "content_hash": "a" * 64,
                "api_params_hash": "b" * 64,
                "processed_table_path": "data/processed/normalized/snapshot.csv",
                "language": "zh-CN",
                "file_format": "csv",
                "ingest_mode": "structured_api_pull",
                "reliability_rank": "B",
                "material_claim_allowed": "metric_only",
                "allowed_claim_types": "metric_statement",
                "license_note": "local fixture",
                "stale_after": "90d",
                "status": "active",
                "parse_status": "parsed",
                "candidate_status": "generated",
                "review_status": "draft",
            }
        ],
    )
    (run_dir / "financial_metric_pack.csv").write_text("metric,value\nrevenue,1000\n", encoding="utf-8")
    (run_dir / "valuation_snapshot.yaml").write_text("as_of_date: 2026-07-01\n", encoding="utf-8")
    (run_dir / "technical_snapshot.yaml").write_text("as_of_date: 2026-07-01\n", encoding="utf-8")
    (run_dir / "source_gap_report.md").write_text("# Source Gap Report\n\nNo high gaps.\n", encoding="utf-8")
    return run_dir


def test_data_layer_quality_gate_accepts_traceable_metric_only_run(tmp_path: Path) -> None:
    run_dir = build_good_run(tmp_path)
    result = review_data_layer_run(
        run_dir=run_dir,
        repo_root=tmp_path,
        source_registry_path=ROOT / "config/source_registry.yaml",
    )
    assert result["final_status"] == "accepted"
    assert result["high_issues"] == 0
    assert (run_dir / "data_layer_quality_report.md").exists()


def test_data_layer_quality_gate_flags_token_value_field(tmp_path: Path) -> None:
    run_dir = build_good_run(tmp_path)
    (run_dir / "bad_readout.md").write_text("token_value: should_not_exist\n", encoding="utf-8")
    result = review_data_layer_run(
        run_dir=run_dir,
        repo_root=tmp_path,
        source_registry_path=ROOT / "config/source_registry.yaml",
    )
    assert result["final_status"] == "needs_fix"
    assert result["high_issues"] == 1
    issues = (run_dir / "data_layer_issue_list.csv").read_text(encoding="utf-8")
    assert "token_value" in issues
