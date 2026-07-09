from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/run_r5_core_asset_preflight.py"
ASSET_DIR = REPO_ROOT / ".agents/skills/stock-deep-dive/assets"


def load_preflight():
    spec = importlib.util.spec_from_file_location("run_r5_core_asset_preflight", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def default_paths():
    return {
        "financial": ASSET_DIR / "r5_financial_history_pack.example.yaml",
        "business": ASSET_DIR / "r5_business_breakdown_pack.example.yaml",
        "forecast": ASSET_DIR / "r5_forecast_model_pack.example.yaml",
        "valuation": ASSET_DIR / "r5_valuation_pack.example.yaml",
    }


def test_todo_examples_produce_executable_with_todos_state():
    preflight = load_preflight()
    result = preflight.run_preflight(default_paths())

    assert result["core_asset_state"] == "R5_CORE_ASSET_SCHEMAS_EXECUTABLE_WITH_TODOS"
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False
    assert result["blockers"] == []
    assert "TODO_MODEL_INPUT" in result["known_todos"]


def test_missing_input_fails_closed(tmp_path: Path):
    preflight = load_preflight()
    paths = default_paths()
    paths["financial"] = tmp_path / "missing.yaml"

    result = preflight.run_preflight(paths)

    assert result["core_asset_state"] == "needs_fix"
    assert result["sample_quality_report_allowed"] is False
    assert result["blockers"]


def test_malformed_yaml_fails_closed(tmp_path: Path):
    preflight = load_preflight()
    bad = tmp_path / "bad.yaml"
    bad.write_text("- not-a-mapping\n", encoding="utf-8")
    paths = default_paths()
    paths["valuation"] = bad

    result = preflight.run_preflight(paths)

    assert result["core_asset_state"] == "needs_fix"
    assert result["p2_allowed"] is False
    assert result["blockers"]


def test_cli_writes_json_result(tmp_path: Path, capsys):
    preflight = load_preflight()
    output = tmp_path / "preflight.json"

    assert preflight.main(["--json", str(output)]) == 0
    payload = yaml.safe_load(output.read_text(encoding="utf-8"))

    assert payload["core_asset_state"] == "R5_CORE_ASSET_SCHEMAS_EXECUTABLE_WITH_TODOS"
    assert "r5_core_asset_state=R5_CORE_ASSET_SCHEMAS_EXECUTABLE_WITH_TODOS" in capsys.readouterr().out
