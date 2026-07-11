from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/validate_r5_reviewed_input_dropzone.py"
FIXTURE_ROOT = REPO_ROOT / "tests/fixtures/r5_reviewed_inputs"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_reviewed_input_dropzone", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_pending_rows_may_preserve_todos_without_unblocking():
    validator = load_validator()
    result = validator.validate_root(FIXTURE_ROOT / "valid_pending")

    assert result["status"] == "pass"
    assert result["pending_count"] == 1
    assert result["accepted_count"] == 0


def test_accepted_degraded_requires_sample_quality_false():
    validator = load_validator()
    result = validator.validate_root(FIXTURE_ROOT / "valid_accepted_degraded")

    assert result["status"] == "pass"
    assert result["accepted_degraded_count"] == 1
    assert result["accepted_count"] == 0


def test_accepted_rows_reject_todo_tokens():
    validator = load_validator()
    result = validator.validate_root(FIXTURE_ROOT / "invalid_accepted_todo")

    assert result["status"] == "fail"
    assert any(issue["issue_id"] == "R5DROP-TODO-001" for issue in result["issues"])


def test_accepted_rows_require_source_evidence_id():
    validator = load_validator()
    result = validator.validate_root(FIXTURE_ROOT / "invalid_missing_evidence")

    assert result["status"] == "fail"
    assert any(issue["issue_id"] == "R5DROP-EVIDENCE-001" for issue in result["issues"])


def issue_ids(result):
    return {issue["issue_id"] for issue in result["issues"]}


def accepted_record(**overrides):
    record = {
        "input_id": "fixture_temp_market_001",
        "workflow_id": "wf_fixture_r5_bundle4",
        "stock_code": "000000",
        "input_type": "market_snapshot",
        "as_of_date": "2026-06-30",
        "source_evidence_id": "ev_fixture_temp_market_001",
        "source_rank": "B",
        "review_status": "accepted",
        "reviewer": "fixture_reviewer",
        "reviewed_at": "2026-07-10T09:00:00+08:00",
        "capture_method": "synthetic_fixture",
        "no_live_api": True,
        "limitations": ["synthetic test data", "not research evidence"],
        "sample_quality_allowed": False,
    }
    record.update(overrides)
    return record


def write_records(root: Path, records: list[dict], folder: str = "market_snapshot") -> Path:
    target = root / folder / "records.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump({"records": records}, sort_keys=False), encoding="utf-8")
    return target


def test_bundle4_positive_summary_is_deterministic_and_relative():
    validator = load_validator()
    root = FIXTURE_ROOT / "accepted_core_complete"

    first = validator.validate_root(root)
    second = validator.validate_root(root)

    assert first == second
    assert first["status"] == "pass"
    assert first["record_count"] == 8
    assert first["unique_workflow_ids"] == ["wf_fixture_r5_bundle4"]
    assert first["unique_stock_codes"] == ["000000"]
    assert first["duplicate_input_ids"] == []
    assert first["counts_by_input_type"] == {
        "forecast_assumptions": 5,
        "market_snapshot": 1,
        "peer_snapshot": 1,
        "valuation_inputs": 1,
    }
    assert all(not Path(path).is_absolute() for path in first["checked_files"])


def test_bundle4_invalid_fixture_issue_ids_are_stable():
    validator = load_validator()
    expectations = {
        "invalid_duplicate_input_id": {"R5DROP-ID-001"},
        "invalid_cross_workflow": {"R5DROP-WORKFLOW-001"},
        "invalid_cross_stock": {"R5DROP-STOCK-001"},
        "invalid_template_as_evidence": {"R5DROP-TEMPLATE-001", "R5DROP-NOTEVID-001"},
        "invalid_folder_type_mismatch": {"R5DROP-FOLDER-001"},
    }

    for scenario, expected in expectations.items():
        result = validator.validate_root(FIXTURE_ROOT / scenario)
        assert result["status"] == "fail"
        assert expected <= issue_ids(result)


def test_placeholder_evidence_fails_closed(tmp_path: Path):
    validator = load_validator()
    write_records(tmp_path, [accepted_record(source_evidence_id="ev_TODO_placeholder")])

    result = validator.validate_root(tmp_path)

    assert result["status"] == "fail"
    assert "R5DROP-EVIDENCE-003" in issue_ids(result)


def test_malformed_accepted_dates_fail_closed(tmp_path: Path):
    validator = load_validator()
    write_records(tmp_path, [accepted_record(as_of_date="2026-99-99", reviewed_at="not-a-timestamp")])

    result = validator.validate_root(tmp_path)

    assert result["status"] == "fail"
    assert {"R5DROP-DATE-001", "R5DROP-DATETIME-001"} <= issue_ids(result)


def test_unsupported_source_rank_fails_closed(tmp_path: Path):
    validator = load_validator()
    write_records(tmp_path, [accepted_record(source_rank="Z")])

    result = validator.validate_root(tmp_path)

    assert result["status"] == "fail"
    assert "R5DROP-RANK-001" in issue_ids(result)


def test_unknown_optional_fields_remain_compatible(tmp_path: Path):
    validator = load_validator()
    write_records(tmp_path, [accepted_record(future_optional_field={"nested": "value"})])

    result = validator.validate_root(tmp_path)

    assert result["status"] == "pass"
    assert result["accepted_count"] == 1


def test_issue_paths_are_relative_to_validated_root():
    validator = load_validator()

    result = validator.validate_root(FIXTURE_ROOT / "invalid_folder_type_mismatch")

    folder_issue = next(issue for issue in result["issues"] if issue["issue_id"] == "R5DROP-FOLDER-001")
    assert folder_issue["path"].startswith("market_snapshot/")
    assert str(FIXTURE_ROOT) not in folder_issue["path"]
