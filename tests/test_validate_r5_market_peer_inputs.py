from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_r5_market_peer_inputs.py"
MARKET_PATH = REPO_ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_market_snapshot_stub.yaml"
PEER_PATH = REPO_ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_peer_snapshot_stub.yaml"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_r5_market_peer_inputs", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_source_gapped_todo_stubs_are_accepted():
    validator = load_validator()
    errors = validator.validate_inputs(load_yaml(MARKET_PATH), load_yaml(PEER_PATH))

    assert errors == []


def test_sample_quality_candidate_requires_reviewed_inputs():
    validator = load_validator()
    errors = validator.validate_inputs(load_yaml(MARKET_PATH), load_yaml(PEER_PATH), level="sample_quality_candidate")

    assert any("reviewed market snapshot" in error for error in errors)
    assert any("reviewed peer snapshot" in error for error in errors)


def test_todo_market_stub_cannot_carry_unreviewed_numeric_values():
    validator = load_validator()
    market = copy.deepcopy(load_yaml(MARKET_PATH))
    peer = load_yaml(PEER_PATH)
    market["market_fields"]["current_price"] = 99.9

    errors = validator.validate_inputs(market, peer)

    assert any("current_price" in error for error in errors)


def test_cli_accepts_source_gapped_stubs(capsys):
    validator = load_validator()

    assert validator.main(["--market", str(MARKET_PATH), "--peer", str(PEER_PATH)]) == 0
    assert "accepted_with_todos" in capsys.readouterr().out
