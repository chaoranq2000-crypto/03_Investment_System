from __future__ import annotations

import copy
import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = (
    ROOT
    / ".agents"
    / "skills"
    / "research-orchestrator"
    / "scripts"
    / "validate_workflow_state.py"
)
TEMPLATE_PATH = (
    ROOT
    / ".agents"
    / "skills"
    / "research-orchestrator"
    / "assets"
    / "workflow_state_template.yaml"
)
LEGACY_STATE_PATH = (
    ROOT
    / "reports"
    / "workflow_runs"
    / "wf_20260703_stock_first_002837_invic"
    / "workflow_state.yaml"
)


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_workflow_state", VALIDATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_validator(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(VALIDATOR_PATH), str(path)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def write_state(tmp_path: Path, state: dict) -> Path:
    path = tmp_path / "workflow_state.yaml"
    path.write_text(
        yaml.safe_dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return path


def template_state() -> dict:
    return yaml.safe_load(TEMPLATE_PATH.read_text(encoding="utf-8"))


def test_versioned_template_and_singleton_names_are_canonical() -> None:
    validator = load_validator()
    assert validator.CURRENT_ASSET_NAMES == (
        "workflow_state.yaml",
        "open_todos.csv",
        "quality_gate_report.md",
        "workflow_readout.md",
    )
    result = run_validator(TEMPLATE_PATH)
    assert result.returncode == 0, result.stderr
    assert "legacy compatibility" not in result.stdout


def test_versioned_state_accepts_only_mapped_canonical_gates(tmp_path: Path) -> None:
    state = template_state()
    state["quality_gates"] = [
        {"gate_id": "G0", "status": "pass"},
        {
            "gate_id": "G9",
            "local_check_id": "R5-G10",
            "mapped_global_gate_ids": ["G9"],
            "status": "pass",
        },
        {"gate_id": "G10", "status": "not_checked"},
    ]
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("gate_id", "status"),
    [
        ("G11", "pass"),
        ("G6_G7", "pass"),
        ("R5-G10", "pass"),
        ("G7", "fail_needs_fix"),
    ],
)
def test_versioned_state_rejects_legacy_gate_values(
    tmp_path: Path, gate_id: str, status: str
) -> None:
    state = template_state()
    state["quality_gates"] = [{"gate_id": gate_id, "status": status}]
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1


def test_versioned_state_rejects_duplicate_canonical_gate(tmp_path: Path) -> None:
    state = template_state()
    state["quality_gates"] = [
        {"gate_id": "G7", "status": "pass"},
        {"gate_id": "G7", "status": "not_checked"},
    ]
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "duplicate canonical quality gate" in result.stderr


def test_versioned_state_rejects_night_mission_status(tmp_path: Path) -> None:
    state = template_state()
    state["status"] = "review_intake_ready"
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "invalid status" in result.stderr


def test_protected_legacy_state_remains_read_only_compatible() -> None:
    before = hashlib.sha256(LEGACY_STATE_PATH.read_bytes()).hexdigest()
    result = run_validator(LEGACY_STATE_PATH)
    after = hashlib.sha256(LEGACY_STATE_PATH.read_bytes()).hexdigest()
    assert result.returncode == 0, result.stderr
    assert "legacy compatibility" in result.stdout
    assert after == before


def test_unknown_state_schema_version_fails(tmp_path: Path) -> None:
    state = copy.deepcopy(template_state())
    state["state_schema_version"] = "r5_v2"
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "unsupported state_schema_version" in result.stderr
