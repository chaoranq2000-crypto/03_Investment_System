from __future__ import annotations

import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import yaml

from src.research.r5_bundle12r_operating_evidence import (
    validate_generation_lock,
    write_bundle12r_outputs,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config" / "r5_bundle12r_operating_evidence_contract.yaml"
READY = ROOT / "tests" / "fixtures" / "r5_bundle12r" / "ready_manufacturing.yaml"
GAP = ROOT / "tests" / "fixtures" / "r5_bundle12r" / "invic_gap_template.yaml"


def test_writer_is_deterministic_relocatable_and_lock_validates(tmp_path: Path) -> None:
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"
    first = write_bundle12r_outputs(READY, CONTRACT, first_output)
    second = write_bundle12r_outputs(READY, CONTRACT, second_output)
    first_lock = (first_output / "R5_bundle12r_generation_lock.yaml").read_bytes()
    second_lock = (second_output / "R5_bundle12r_generation_lock.yaml").read_bytes()
    assert first_lock == second_lock
    assert first["generation_lock"]["artifact_hashes"] == second["generation_lock"]["artifact_hashes"]
    assert validate_generation_lock(first_output / "R5_bundle12r_generation_lock.yaml") == []
    assert validate_generation_lock(second_output / "R5_bundle12r_generation_lock.yaml") == []


def test_strict_cli_passes_ready_fixture(tmp_path: Path) -> None:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_r5_bundle12r_operating_evidence_gate.py"),
        "--input",
        str(READY),
        "--contract",
        str(CONTRACT),
        "--output-dir",
        str(tmp_path / "ready"),
        "--strict",
    ]
    completed = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert "decision=operating_evidence_ready" in completed.stdout


def test_strict_cli_returns_two_for_gap_fixture_but_writes_backflow(tmp_path: Path) -> None:
    output = tmp_path / "gap"
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_r5_bundle12r_operating_evidence_gate.py"),
        "--input",
        str(GAP),
        "--contract",
        str(CONTRACT),
        "--output-dir",
        str(output),
        "--strict",
    ]
    completed = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    assert completed.returncode == 2
    backflow = yaml.safe_load((output / "R5_bundle12r_backflow_plan.yaml").read_text(encoding="utf-8"))
    assert backflow["decision"] == "backflow_required"
    assert backflow["actions"]


def test_lock_validator_detects_tampering(tmp_path: Path) -> None:
    output = tmp_path / "out"
    write_bundle12r_outputs(READY, CONTRACT, output)
    result_path = output / "R5_bundle12r_operating_evidence_result.yaml"
    result_path.write_text(result_path.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")
    issues = validate_generation_lock(output / "R5_bundle12r_generation_lock.yaml")
    assert any("hash mismatch" in issue for issue in issues)


def test_lock_validator_detects_metadata_and_manifest_tampering(tmp_path: Path) -> None:
    output = tmp_path / "out"
    write_bundle12r_outputs(READY, CONTRACT, output)
    lock_path = output / "R5_bundle12r_generation_lock.yaml"
    original = yaml.safe_load(lock_path.read_text(encoding="utf-8"))

    mutations = []
    changed_decision = deepcopy(original)
    changed_decision["decision"] = "needs_backflow"
    mutations.append(changed_decision)
    changed_generation = deepcopy(original)
    changed_generation["generation_id"] = "op_evidence_gen_r5_bundle12r_0000000000000000"
    mutations.append(changed_generation)
    removed_artifact = deepcopy(original)
    removed_artifact["artifact_hashes"].pop("R5_bundle12r_coverage_report.yaml")
    mutations.append(removed_artifact)
    changed_boundary = deepcopy(original)
    changed_boundary["preserves_bundle11r_exact_hash_review"] = False
    mutations.append(changed_boundary)

    for mutated in mutations:
        lock_path.write_text(yaml.safe_dump(mutated, allow_unicode=True, sort_keys=False), encoding="utf-8")
        assert validate_generation_lock(lock_path)
