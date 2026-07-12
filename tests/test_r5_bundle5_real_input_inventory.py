from __future__ import annotations

import csv
import importlib.util
import shutil
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/build_r5_bundle5_real_input_inventory.py"
WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
STOCK_CODE = "002837"


def load_builder():
    spec = importlib.util.spec_from_file_location("r5_bundle5_inventory_builder_test", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BUILDER = load_builder()


def item_by_type(inventory: dict, input_type: str) -> dict:
    return next(item for item in inventory["items"] if item["input_type"] == input_type)


def test_current_real_workflow_has_all_reviewed_core_input_types_after_promotion() -> None:
    inventory = BUILDER.build_inventory(
        REPO_ROOT,
        WORKFLOW_ID,
        STOCK_CODE,
        Path("data/reviewed_inputs") / WORKFLOW_ID,
    )

    assert inventory["status"] == "ready_for_later_promotion_card"
    assert inventory["dropzone_validation"]["status"] == "pass"
    assert inventory["dropzone_validation"]["record_count"] == 22
    assert inventory["dropzone_validation"]["accepted_count"] == 22
    assert inventory["dropzone_validation"]["interpretation"] == "records_present_review_inventory_required"
    assert inventory["summary"]["valid_accepted_core_input_type_count"] == 5
    assert inventory["summary"]["missing_or_invalid_core_input_type_count"] == 0
    assert inventory["summary"]["review_ledger"]["accepted_count"] == 22
    assert {item["input_type"] for item in inventory["items"]} == {
        *BUILDER.CORE_INPUT_TYPES,
        *BUILDER.OPTIONAL_INPUT_TYPES,
    }
    expected_counts = {
        "business_disclosure": 9,
        "market_snapshot": 1,
        "peer_snapshot": 6,
        "forecast_assumptions": 5,
        "valuation_inputs": 1,
    }
    for input_type, expected_count in expected_counts.items():
        item = item_by_type(inventory, input_type)
        assert item["blocking"] is False
        assert item["valid_accepted_count"] == expected_count
        assert all(record["accepted_valid"] is True for record in item["records"])
        assert item["request_ids"]
        assert item["missing_fields"] == []
    business = item_by_type(inventory, "business_disclosure")
    assert business["evidence_candidates"]
    assert all(candidate["candidate_only"] is True for candidate in business["evidence_candidates"])
    assert any(
        "annual_report_002837_invic_2025_0f8fcf" in alias["evidence_ids"]
        and "ev_annual_report_002837_20260421_ce7f64" in alias["evidence_ids"]
        for alias in inventory["provenance_aliases"]
    )
    assert inventory["quality_decision"] == {
        "g1_evidence_gate": "pass",
        "card_5_1_stop_condition_triggered": False,
        "card_5_2_allowed": True,
        "promotion_allowed": False,
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
    }


def write_synthetic_repo(
    tmp_path: Path,
    *,
    invalid_fixture: bool = False,
    include_evidence: bool = True,
    include_dropzone_record: bool = True,
    source_type: str = "annual_report",
) -> Path:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy2(
        REPO_ROOT / "scripts/validate_r5_reviewed_input_dropzone.py",
        repo / "scripts/validate_r5_reviewed_input_dropzone.py",
    )
    workflow_dir = repo / "reports/workflow_runs" / WORKFLOW_ID
    workflow_dir.mkdir(parents=True)
    queue = {
        "summary": {"request_count": 5, "source_gap_count": 5},
        "requests": [
            {
                "request_id": "req_business",
                "source_gap_id": "R5_002837_GAP_BUSINESS_001",
                "source_type": "annual_report",
                "required_for_pack": ["business_breakdown_pack"],
            },
            {
                "request_id": "req_market",
                "source_gap_id": "R5_002837_GAP_MARKET_001",
                "source_type": "market_data_snapshot",
                "required_for_pack": ["valuation_pack"],
            },
            {
                "request_id": "req_peer",
                "source_gap_id": "R5_002837_GAP_VALUATION_001",
                "source_type": "peer_snapshot",
                "required_for_pack": ["peer_comparison_pack", "valuation_pack"],
            },
            {
                "request_id": "req_forecast",
                "source_gap_id": "R5_002837_GAP_FORECAST_001",
                "source_type": "structured_financial_data",
                "required_for_pack": ["forecast_model_pack"],
            },
            {
                "request_id": "req_sentiment",
                "source_gap_id": "R5_002837_GAP_SENTIMENT_001",
                "source_type": "news_or_event_source",
                "required_for_pack": ["sentiment_event_pack"],
            },
        ],
    }
    (workflow_dir / "R5_evidence_request_queue.yaml").write_text(
        yaml.safe_dump(queue, sort_keys=False), encoding="utf-8"
    )
    (workflow_dir / "R5_evidence_request_review_ledger.yaml").write_text(
        yaml.safe_dump(
            {"summary": {"request_count": 5, "pending_count": 5, "accepted_count": 0}},
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    if include_evidence:
        raw_path = repo / "data/raw/annual_reports/002837_real.pdf"
        raw_path.parent.mkdir(parents=True)
        raw_path.write_bytes(b"real official filing bytes")
        manifest_path = repo / "data/manifests/evidence_manifest.csv"
        manifest_path.parent.mkdir(parents=True)
        fields = [
            "evidence_id",
            "stock_code",
            "company_id",
            "entity_id",
            "title",
            "source_name",
            "source_type",
            "raw_file_path",
            "file_hash",
            "reliability_rank",
            "review_status",
            "parse_status",
            "publish_date",
            "notes",
        ]
        with manifest_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow(
                {
                    "evidence_id": "ev_real_002837_annual",
                    "stock_code": STOCK_CODE,
                    "company_id": "cn_002837_invic",
                    "entity_id": "cn_002837_invic",
                    "title": "002837 official disclosure",
                    "source_name": "local_fixture" if invalid_fixture else "szse",
                    "source_type": source_type,
                    "raw_file_path": "data/raw/annual_reports/002837_real.pdf",
                    "file_hash": "a" * 64,
                    "reliability_rank": "A",
                    "review_status": "reviewed",
                    "parse_status": "parsed",
                    "publish_date": "2026-04-21",
                    "notes": "synthetic unit-test evidence metadata",
                }
            )

    dropzone_root = repo / "data/reviewed_inputs" / WORKFLOW_ID
    dropzone_root.mkdir(parents=True)
    if not include_dropzone_record:
        return repo

    dropzone = dropzone_root / "business_disclosure"
    dropzone.mkdir()
    record = {
        "input_id": "input_real_business_001",
        "workflow_id": WORKFLOW_ID,
        "stock_code": STOCK_CODE,
        "input_type": "business_disclosure",
        "source_evidence_id": "ev_real_002837_annual",
        "source_rank": "A",
        "as_of_date": "2026-04-21",
        "review_status": "accepted",
        "reviewer": "authorized_reviewer",
        "reviewed_at": "2026-07-11T12:00:00+08:00",
        "capture_method": "manual_official_filing_review",
        "no_live_api": True,
        "limitations": "One official filing; no inference beyond disclosed facts.",
        "sample_quality_allowed": False,
    }
    (dropzone / "accepted.yaml").write_text(
        yaml.safe_dump({"records": [record]}, sort_keys=False), encoding="utf-8"
    )
    return repo


@pytest.mark.parametrize("source_type", ["annual_report", "interim_report", "quarterly_report"])
def test_card_5_2_allowed_with_empty_dropzone_and_real_official_anchor(
    tmp_path: Path,
    source_type: str,
) -> None:
    repo = write_synthetic_repo(
        tmp_path,
        include_dropzone_record=False,
        source_type=source_type,
    )

    inventory = BUILDER.build_inventory(
        repo,
        WORKFLOW_ID,
        STOCK_CODE,
        Path("data/reviewed_inputs") / WORKFLOW_ID,
    )

    assert inventory["dropzone_validation"]["record_count"] == 0
    assert inventory["quality_decision"]["card_5_1_stop_condition_triggered"] is False
    assert inventory["quality_decision"]["card_5_2_allowed"] is True
    assert inventory["quality_decision"]["g1_evidence_gate"] == "fail"
    assert inventory["quality_decision"]["promotion_allowed"] is False
    assert inventory["quality_decision"]["sample_quality_report_allowed"] is False
    assert inventory["quality_decision"]["p2_allowed"] is False


def test_card_5_2_not_allowed_without_real_official_anchor(tmp_path: Path) -> None:
    repo = write_synthetic_repo(
        tmp_path,
        include_evidence=False,
        include_dropzone_record=False,
    )

    inventory = BUILDER.build_inventory(
        repo,
        WORKFLOW_ID,
        STOCK_CODE,
        Path("data/reviewed_inputs") / WORKFLOW_ID,
    )

    assert item_by_type(inventory, "business_disclosure")["evidence_candidates"] == []
    assert inventory["quality_decision"]["card_5_1_stop_condition_triggered"] is True
    assert inventory["quality_decision"]["card_5_2_allowed"] is False


def test_card_5_2_not_allowed_for_fixture_official_anchor(tmp_path: Path) -> None:
    repo = write_synthetic_repo(
        tmp_path,
        invalid_fixture=True,
        include_dropzone_record=False,
    )

    inventory = BUILDER.build_inventory(
        repo,
        WORKFLOW_ID,
        STOCK_CODE,
        Path("data/reviewed_inputs") / WORKFLOW_ID,
    )

    assert item_by_type(inventory, "business_disclosure")["evidence_candidates"] == []
    assert inventory["quality_decision"]["card_5_1_stop_condition_triggered"] is True
    assert inventory["quality_decision"]["card_5_2_allowed"] is False


def test_valid_accepted_record_requires_resolvable_physical_evidence(tmp_path: Path) -> None:
    repo = write_synthetic_repo(tmp_path)
    inventory = BUILDER.build_inventory(
        repo,
        WORKFLOW_ID,
        STOCK_CODE,
        Path("data/reviewed_inputs") / WORKFLOW_ID,
    )

    business = item_by_type(inventory, "business_disclosure")
    assert business["valid_accepted_count"] == 1
    assert business["blocking"] is False
    assert business["records"][0]["accepted_valid"] is True
    assert business["records"][0]["conflicts"] == []
    assert inventory["status"] == "blocked_source_gapped"
    assert inventory["quality_decision"]["promotion_allowed"] is False


def test_fixture_evidence_cannot_satisfy_accepted_coverage(tmp_path: Path) -> None:
    repo = write_synthetic_repo(tmp_path, invalid_fixture=True)
    inventory = BUILDER.build_inventory(
        repo,
        WORKFLOW_ID,
        STOCK_CODE,
        Path("data/reviewed_inputs") / WORKFLOW_ID,
    )

    business = item_by_type(inventory, "business_disclosure")
    assert business["valid_accepted_count"] == 0
    assert business["blocking"] is True
    assert "fixture_evidence:ev_real_002837_annual" in business["records"][0]["conflicts"]
    assert inventory["quality_decision"]["g1_evidence_gate"] == "fail"
