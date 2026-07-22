from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / ".agents/skills/quality-review/scripts/validate_quality_issues.py"
EXAMPLE_PATH = REPO_ROOT / ".agents/skills/quality-review/assets/r5_quality_issues.example.csv"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_quality_issues", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_example_quality_issues_are_valid():
    validator = load_validator()
    rows = validator.load_issues(EXAMPLE_PATH)
    errors = validator.validate_quality_issues(rows)
    assert errors == []
    assert validator.derive_outcome(rows, errors) == "accepted_with_todos"


def test_active_high_issue_blocks_accepted_outcome():
    validator = load_validator()
    rows = copy.deepcopy(validator.load_issues(EXAMPLE_PATH))
    rows[0]["severity"] = "high"
    rows[0]["status"] = "open"
    errors = validator.validate_quality_issues(rows, expected_outcome="accepted")
    assert any("active high or critical severity" in error for error in errors)
    assert validator.derive_outcome(rows, []) == "needs_fix"


def test_high_issue_row_cannot_have_accepted_blocking_decision():
    validator = load_validator()
    rows = copy.deepcopy(validator.load_issues(EXAMPLE_PATH))
    rows[0]["severity"] = "high"
    rows[0]["blocking_decision"] = "accepted"
    errors = validator.validate_quality_issues(rows)
    assert any("high or critical severity cannot have accepted" in error for error in errors)


def test_trading_instruction_issue_must_be_high():
    validator = load_validator()
    rows = copy.deepcopy(validator.load_issues(EXAMPLE_PATH))
    rows[0]["description"] = "direct trading instruction appears in the artifact"
    rows[0]["severity"] = "medium"
    errors = validator.validate_quality_issues(rows)
    assert any("direct trading instruction" in error for error in errors)


def test_missing_required_value_is_reported():
    validator = load_validator()
    rows = copy.deepcopy(validator.load_issues(EXAMPLE_PATH))
    rows[0]["next_action"] = ""
    assert any("next_action is required" in error for error in validator.validate_quality_issues(rows))


def test_invalid_severity_is_reported():
    validator = load_validator()
    rows = copy.deepcopy(validator.load_issues(EXAMPLE_PATH))
    rows[0]["severity"] = "fatal"
    assert any("severity is invalid" in error for error in validator.validate_quality_issues(rows))


def test_critical_severity_is_valid_and_blocks_accepted():
    validator = load_validator()
    rows = copy.deepcopy(validator.load_issues(EXAMPLE_PATH))
    rows[0]["severity"] = "critical"
    rows[0]["status"] = "open"
    errors = validator.validate_quality_issues(rows, expected_outcome="accepted")
    assert any("high or critical" in error for error in errors)


def test_invalid_gate_id_is_reported():
    validator = load_validator()
    rows = copy.deepcopy(validator.load_issues(EXAMPLE_PATH))
    rows[0]["gate_id"] = "G11"
    assert any("gate_id is invalid" in error for error in validator.validate_quality_issues(rows))


def test_missing_r5_no_advice_gate_is_reported():
    validator = load_validator()
    rows = [
        row
        for row in validator.load_issues(EXAMPLE_PATH)
        if row["local_check_id"] != "R5-G10"
    ]
    assert any("R5-G10 No-Advice Gate" in error for error in validator.validate_quality_issues(rows))


def test_all_r5_gates_must_be_represented():
    validator = load_validator()
    rows = [
        row
        for row in validator.load_issues(EXAMPLE_PATH)
        if row["local_check_id"] != "R5-G1"
    ]
    assert any("missing R5 gates" in error for error in validator.validate_quality_issues(rows))


def test_active_gate_id_is_canonical_and_local_ids_are_separate():
    validator = load_validator()
    assert validator._valid_gate_id("G0")
    assert validator._valid_gate_id("G1")
    assert validator._valid_gate_id("G10")
    assert not validator._valid_gate_id("G11")
    assert not validator._valid_gate_id("QR-DL-1")
    assert not validator._valid_gate_id("R5-G11")
    assert validator._valid_local_check_id("QR-DL-1")
    assert validator._valid_local_check_id("R5-G11")


def test_global_only_issue_list_does_not_require_the_r5_rubric():
    validator = load_validator()
    row = copy.deepcopy(validator.load_issues(EXAMPLE_PATH)[0])
    row["gate_id"] = "G0"
    row["local_check_id"] = ""
    row["mapped_global_gate_ids"] = ""
    errors = validator.validate_quality_issues([row])
    assert errors == []


def test_r5_mapping_drift_is_rejected():
    validator = load_validator()
    rows = copy.deepcopy(validator.load_issues(EXAMPLE_PATH))
    rows[0]["mapped_global_gate_ids"] = "G7"
    errors = validator.validate_quality_issues(rows)
    assert any("R5-G1 mapping must be G1" in error for error in errors)


def test_cli_validates_example(capsys):
    validator = load_validator()
    assert validator.main([str(EXAMPLE_PATH), "--expected-decision", "accepted_with_todos"]) == 0
    captured = capsys.readouterr()
    assert "outcome: accepted_with_todos" in captured.out
