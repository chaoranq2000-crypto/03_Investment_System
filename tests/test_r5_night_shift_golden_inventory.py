from __future__ import annotations

from pathlib import Path

from src.maintenance.night_shift.strategic import build_golden_case_inventory


def test_golden_inventory_records_real_lineage_and_generation_gaps() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    inventory = build_golden_case_inventory(repo_root)
    assert inventory["case_count"] == 4
    assert inventory["conclusion"] == "generation_and_quality_contract_gap_confirmed"
    for case in inventory["cases"]:
        assert len(case["artifact_lineage"]) == 9
        assert all(item["present"] for item in case["artifact_lineage"])
        assert case["compatibility"]["generation_id_complete"] is False
        assert case["compatibility"]["human_review_status"] == "pending"
        assert case["compatibility"]["sample_quality_allowed"] is False
        assert case["compatibility"]["p2_allowed"] is False
