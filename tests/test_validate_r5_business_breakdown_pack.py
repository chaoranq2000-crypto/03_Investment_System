from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_r5_business_breakdown_pack.py"
EXAMPLE_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/assets/r5_business_breakdown_pack.example.yaml"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_business_breakdown_pack", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_example() -> dict:
    return yaml.safe_load(EXAMPLE_PATH.read_text(encoding="utf-8"))


def test_example_business_breakdown_is_accepted_with_todos(capsys):
    validator = load_validator()

    assert validator.main(["--input", str(EXAMPLE_PATH)]) == 0
    assert "outcome: accepted_with_todos" in capsys.readouterr().out


def test_non_null_revenue_pct_requires_evidence_or_metric_id():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["business_lines"][0]["revenue_pct"]["value"] = 0.25
    data["business_lines"][0]["revenue_pct"]["missing_reason"] = None

    errors = validator.validate_business_breakdown_pack(data)

    assert any("revenue_pct.value requires evidence_id or metric_id" in error for error in errors)


def test_ready_status_fails_with_missing_disclosure():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["status"] = "ready"

    errors = validator.validate_business_breakdown_pack(data)

    assert any("cannot remain null when status is ready" in error for error in errors)
    assert any("status ready cannot contain hidden MISSING_DISCLOSURE" in error for error in errors)


def test_product_clues_alone_cannot_set_high_confidence():
    validator = load_validator()
    data = copy.deepcopy(load_example())
    data["business_lines"][0]["confidence"] = "high"

    errors = validator.validate_business_breakdown_pack(data)

    assert any("cannot be high" in error for error in errors)
