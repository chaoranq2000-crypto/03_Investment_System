from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

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
