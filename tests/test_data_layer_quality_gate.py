from __future__ import annotations

import csv
import sys
from pathlib import Path

import yaml


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

OPEN_TODO_HEADER = [
    "issue_id",
    "severity",
    "stage",
    "target_artifact",
    "description",
    "fix_owner_skill",
    "status",
    "created_at",
    "resolved_at",
    "notes",
]

DATA_LAYER_RUN_DIR = ROOT / "reports/workflow_runs/wf_20260703_data_layer_002837_invic"
FORMATTED_ARTIFACTS = [
    DATA_LAYER_RUN_DIR / "data_layer_quality_report.md",
    DATA_LAYER_RUN_DIR / "data_layer_issue_list.csv",
    DATA_LAYER_RUN_DIR / "open_todos.csv",
    DATA_LAYER_RUN_DIR / "source_gap_report.md",
    DATA_LAYER_RUN_DIR / "workflow_readout.md",
    DATA_LAYER_RUN_DIR / "workflow_state.yaml",
    DATA_LAYER_RUN_DIR / "valuation_snapshot.yaml",
    DATA_LAYER_RUN_DIR / "technical_snapshot.yaml",
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
    assert result["blocking_issue_count"] == 0
    assert result["accepted_todo_count"] == 0
    assert result["high_issues"] == 0
    assert (run_dir / "data_layer_quality_report.md").exists()


def test_data_layer_quality_gate_accepts_with_visible_todos(tmp_path: Path) -> None:
    run_dir = build_good_run(tmp_path)
    write_csv(
        run_dir / "open_todos.csv",
        OPEN_TODO_HEADER,
        [
            {
                "issue_id": "DL-GAP-001",
                "severity": "medium",
                "stage": "DL5 Data Packs",
                "target_artifact": "peer_market_snapshot.csv",
                "description": "peer_market_snapshot.csv not generated",
                "fix_owner_skill": "evidence-ingest",
                "status": "accepted_todo",
                "created_at": "2026-07-03",
                "notes": "Keep TODO_PEER_DATA before peer comparison",
            },
            {
                "issue_id": "DL-GAP-003",
                "severity": "low",
                "stage": "DL5 Data Packs",
                "target_artifact": "valuation_snapshot.yaml",
                "description": "pe_forward missing from fixture",
                "fix_owner_skill": "evidence-ingest",
                "status": "accepted_todo",
                "created_at": "2026-07-03",
                "notes": "Field remains TODO_MARKET_DATA",
            },
        ],
    )
    result = review_data_layer_run(
        run_dir=run_dir,
        repo_root=tmp_path,
        source_registry_path=ROOT / "config/source_registry.yaml",
    )
    assert result["final_status"] == "accepted_with_todos"
    assert result["blocking_issue_count"] == 0
    assert result["accepted_todo_count"] == 2
    assert result["medium_issues"] == 1
    assert result["low_issues"] == 1

    report = (run_dir / "data_layer_quality_report.md").read_text(encoding="utf-8")
    issue_list = (run_dir / "data_layer_issue_list.csv").read_text(encoding="utf-8")
    assert "final_status: accepted_with_todos" in report
    assert "## Blocking Issues\n\nNone." in report
    assert "DL-GAP-001" in report
    assert "DL-GAP-003" in report
    assert "issue_class" in issue_list
    assert "accepted_todo" in issue_list


def test_data_layer_quality_gate_flags_token_value_field(tmp_path: Path) -> None:
    run_dir = build_good_run(tmp_path)
    (run_dir / "bad_readout.md").write_text("token_value: should_not_exist\n", encoding="utf-8")
    result = review_data_layer_run(
        run_dir=run_dir,
        repo_root=tmp_path,
        source_registry_path=ROOT / "config/source_registry.yaml",
    )
    assert result["final_status"] == "blocked"
    assert result["blocking_issue_count"] == 1
    assert result["accepted_todo_count"] == 0
    assert result["high_issues"] == 1
    issues = (run_dir / "data_layer_issue_list.csv").read_text(encoding="utf-8")
    assert "blocking_issue" in issues
    assert "token_value" in issues


def test_current_data_layer_artifacts_are_readable_and_posix() -> None:
    report = (DATA_LAYER_RUN_DIR / "data_layer_quality_report.md").read_text(encoding="utf-8")
    assert report.startswith("# Data Layer Quality Report\n")
    assert "## Summary" in report
    assert "## Blocking Issues" in report
    assert "## Accepted Todos" in report

    issue_rows = (DATA_LAYER_RUN_DIR / "data_layer_issue_list.csv").read_text(encoding="utf-8").splitlines()
    with (DATA_LAYER_RUN_DIR / "data_layer_issue_list.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        parsed_issue_rows = list(csv.DictReader(handle))
    assert len(issue_rows) == 1 + len(parsed_issue_rows)
    assert len(parsed_issue_rows) == 3

    for file_name in ["workflow_state.yaml", "valuation_snapshot.yaml", "technical_snapshot.yaml"]:
        parsed = yaml.safe_load((DATA_LAYER_RUN_DIR / file_name).read_text(encoding="utf-8"))
        assert isinstance(parsed, dict)

    for path in FORMATTED_ARTIFACTS:
        assert "\\" not in path.read_text(encoding="utf-8"), path
