from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/validate_r5_reviewed_input_dropzone.py"
FIXTURE_ROOT = REPO_ROOT / "tests/fixtures/r5_reviewed_inputs"
FIXTURE_WORKFLOW = "wf_fixture_r5_bundle4"
FIXTURE_STOCK = "000000"
CRITICAL_TOKENS = {
    "TODO_MARKET_DATA",
    "TODO_PEER_DATA",
    "TODO_MODEL_INPUT",
    "TODO_SOURCE_REQUIRED",
    "MISSING_DISCLOSURE",
    "LOW_CONFIDENCE_CLUE_ONLY",
}


def load_validator():
    spec = importlib.util.spec_from_file_location("r5_bundle4_fixture_validator", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def scenario_records(name: str):
    validator = load_validator()
    rows = []
    for path in validator.iter_input_files(FIXTURE_ROOT / name):
        rows.extend((path, row) for row in validator.read_dropzone_file(path))
    return rows


def flattened_text(value) -> str:
    if isinstance(value, dict):
        return "\n".join(flattened_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(flattened_text(item) for item in value)
    return "" if value is None else str(value)


def assert_positive_accepted_metadata(row: dict) -> None:
    assert row["workflow_id"] == FIXTURE_WORKFLOW
    assert row["stock_code"] == FIXTURE_STOCK
    assert str(row["input_id"]).startswith("fixture_")
    assert str(row["source_evidence_id"]).startswith("ev_fixture_")
    assert row["source_rank"] in {"A", "B", "C"}
    assert row["reviewer"] == "fixture_reviewer"
    assert row["reviewed_at"]
    assert row["as_of_date"]
    assert row["no_live_api"] is True
    assert row["sample_quality_allowed"] is False
    limitations = flattened_text(row.get("limitations")).lower()
    assert "synthetic test data" in limitations
    assert "not research evidence" in limitations
    text = flattened_text(row)
    assert not any(token in text for token in CRITICAL_TOKENS)


def test_positive_fixture_matrix_passes_current_dropzone_contract():
    validator = load_validator()

    core = validator.validate_root(FIXTURE_ROOT / "accepted_core_complete")
    complete = validator.validate_root(FIXTURE_ROOT / "accepted_all_complete")
    mixed = validator.validate_root(FIXTURE_ROOT / "mixed_status")

    assert core["status"] == "pass"
    assert core["accepted_count"] == 8
    assert complete["status"] == "pass"
    assert complete["accepted_count"] == 9
    assert mixed["status"] == "pass"
    assert mixed["accepted_count"] == 1
    assert mixed["accepted_degraded_count"] == 1
    assert mixed["pending_count"] == 1
    assert mixed["rejected_count"] == 1


def test_core_and_all_complete_types_are_explicit():
    core_types = {row["input_type"] for _, row in scenario_records("accepted_core_complete")}
    all_types = {row["input_type"] for _, row in scenario_records("accepted_all_complete")}

    assert core_types == {"market_snapshot", "peer_snapshot", "forecast_assumptions", "valuation_inputs"}
    assert all_types == core_types | {"business_disclosure"}


def test_positive_accepted_rows_are_synthetic_reviewed_and_todo_free():
    for scenario in ["accepted_core_complete", "accepted_all_complete"]:
        for _, row in scenario_records(scenario):
            assert row["review_status"] == "accepted"
            assert_positive_accepted_metadata(row)


def test_mixed_status_only_accepted_row_is_fully_activating():
    rows = [row for _, row in scenario_records("mixed_status")]
    assert Counter(row["review_status"] for row in rows) == Counter(
        {"accepted": 1, "accepted_degraded": 1, "pending": 1, "rejected": 1}
    )
    accepted = [row for row in rows if row["review_status"] == "accepted"]
    assert [row["input_type"] for row in accepted] == ["market_snapshot"]
    assert all(row.get("sample_quality_allowed") is False for row in rows)


def test_invalid_fixture_shapes_encode_the_intended_boundary():
    duplicate_rows = [row for _, row in scenario_records("invalid_duplicate_input_id")]
    duplicate_ids = Counter(row["input_id"] for row in duplicate_rows)
    assert duplicate_ids["fixture_duplicate_001"] == 2

    workflow_rows = [row for _, row in scenario_records("invalid_cross_workflow")]
    assert {row["workflow_id"] for row in workflow_rows} == {
        FIXTURE_WORKFLOW,
        "wf_fixture_r5_bundle4_other",
    }

    stock_rows = [row for _, row in scenario_records("invalid_cross_stock")]
    assert {row["stock_code"] for row in stock_rows} == {FIXTURE_STOCK, "fixture_other_stock"}

    template_rows = [row for _, row in scenario_records("invalid_template_as_evidence")]
    assert any(row.get("template_only") is True for row in template_rows)
    assert any(row.get("not_evidence") is True for row in template_rows)

    mismatch_rows = scenario_records("invalid_folder_type_mismatch")
    assert len(mismatch_rows) == 1
    path, row = mismatch_rows[0]
    assert path.parent.name == "market_snapshot"
    assert row["input_type"] == "peer_snapshot"


def test_non_identity_invalid_scenarios_retain_fixture_identity():
    scenarios = [
        "invalid_duplicate_input_id",
        "invalid_template_as_evidence",
        "invalid_folder_type_mismatch",
    ]
    for scenario in scenarios:
        for _, row in scenario_records(scenario):
            assert row["workflow_id"] == FIXTURE_WORKFLOW
            assert row["stock_code"] == FIXTURE_STOCK


def test_legacy_negative_fixtures_remain_present():
    assert (FIXTURE_ROOT / "invalid_missing_evidence/business_disclosure/bad_missing_evidence.yaml").is_file()
    assert (FIXTURE_ROOT / "invalid_accepted_todo/valuation_inputs/bad_todo.yaml").is_file()


def test_fixture_identity_is_absent_from_real_reviewed_input_dropzone():
    real_dropzone = REPO_ROOT / "data/reviewed_inputs"
    fixture_path = real_dropzone / FIXTURE_WORKFLOW
    assert not fixture_path.exists()
    for path in real_dropzone.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            assert FIXTURE_WORKFLOW not in text
            assert "ev_fixture_" not in text
