from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_r5_financial_history_pack.py"
EXAMPLE_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/assets/r5_financial_history_pack.example.yaml"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_financial_history_pack", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_example() -> dict:
    return yaml.safe_load(EXAMPLE_PATH.read_text(encoding="utf-8"))


def test_example_financial_history_pack_is_accepted_with_todos(capsys):
    validator = load_validator()

    assert validator.main(["--input", str(EXAMPLE_PATH)]) == 0
    assert "outcome: accepted_with_todos" in capsys.readouterr().out


def test_non_null_metric_requires_evidence_or_metric_id():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    row = data["income_statement"][0]
    row["value"] = 100.0
    row["missing_reason"] = None
    row["evidence_id"] = None
    row["metric_id"] = None

    errors = validator.validate_financial_history_pack(data)

    assert any("requires evidence_id or metric_id" in error for error in errors)


def test_null_metric_requires_missing_reason_or_missing_item():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["missing_items"] = []
    data["income_statement"][0].pop("missing_reason")

    errors = validator.validate_financial_history_pack(data)

    assert any("requires missing_reason" in error for error in errors)


def test_ready_status_forbids_empty_sections_and_hidden_todos():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["status"] = "ready"
    data["balance_sheet"] = []

    errors = validator.validate_financial_history_pack(data)

    assert any("status ready requires non-empty balance_sheet" in error for error in errors)
    assert any("status ready cannot contain hidden TODO" in error for error in errors)
