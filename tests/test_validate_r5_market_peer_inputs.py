from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_r5_market_peer_inputs.py"
HISTORICAL_RUN = "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


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


def _inputs(historical_blob_file) -> tuple[Path, Path]:
    market_path = historical_blob_file(
        f"{HISTORICAL_RUN}/R5_market_snapshot_stub.yaml",
        "market_peer_inputs/R5_market_snapshot_stub.yaml",
    )
    peer_path = historical_blob_file(
        f"{HISTORICAL_RUN}/R5_peer_snapshot_stub.yaml",
        "market_peer_inputs/R5_peer_snapshot_stub.yaml",
    )
    return market_path, peer_path


def test_source_gapped_todo_stubs_are_accepted(historical_blob_file):
    validator = load_validator()
    market_path, peer_path = _inputs(historical_blob_file)
    errors = validator.validate_inputs(load_yaml(market_path), load_yaml(peer_path))

    assert errors == []


def test_sample_quality_candidate_requires_reviewed_inputs(historical_blob_file):
    validator = load_validator()
    market_path, peer_path = _inputs(historical_blob_file)
    errors = validator.validate_inputs(
        load_yaml(market_path), load_yaml(peer_path), level="sample_quality_candidate"
    )

    assert any("reviewed market snapshot" in error for error in errors)
    assert any("reviewed peer snapshot" in error for error in errors)


def test_todo_market_stub_cannot_carry_unreviewed_numeric_values(historical_blob_file):
    validator = load_validator()
    market_path, peer_path = _inputs(historical_blob_file)
    market = copy.deepcopy(load_yaml(market_path))
    peer = load_yaml(peer_path)
    market["market_fields"]["current_price"] = 99.9

    errors = validator.validate_inputs(market, peer)

    assert any("current_price" in error for error in errors)


def test_cli_accepts_source_gapped_stubs(capsys, historical_blob_file):
    validator = load_validator()
    market_path, peer_path = _inputs(historical_blob_file)

    assert validator.main(["--market", str(market_path), "--peer", str(peer_path)]) == 0
    assert "accepted_with_todos" in capsys.readouterr().out
