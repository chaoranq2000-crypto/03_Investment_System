from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from src.research.r5_bundle13r_evidence_backflow import validate_generation_lock, write_bundle13r_outputs

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = ROOT / "tests" / "fixtures" / "r5_bundle13r" / "bundle12r_context"
CONTRACT = ROOT / "tests" / "fixtures" / "r5_bundle13r" / "r5_bundle13r_fixture_contract.yaml"
READY = ROOT / "tests" / "fixtures" / "r5_bundle13r" / "reviewed_backfill_ready.yaml"
PARTIAL = ROOT / "tests" / "fixtures" / "r5_bundle13r" / "reviewed_backfill_partial.yaml"


def test_writer_produces_self_contained_valid_lock(tmp_path: Path):
    written = write_bundle13r_outputs(
        context_dir=CONTEXT,
        reviewed_backfill_path=READY,
        contract_path=CONTRACT,
        output_dir=tmp_path,
        verify_bundle12r_hashes=False,
    )
    assert written["result"]["decision"] == "ready_for_bundle12r_rerun"
    assert validate_generation_lock(tmp_path / "R5_bundle13r_generation_lock.yaml") == []
    for path in tmp_path.iterdir():
        if path.is_file() and path.suffix in {".csv", ".md", ".yaml"}:
            assert b"\r\n" not in path.read_bytes(), path.name


def test_strict_cli_returns_zero_when_ready_for_bundle12r_rerun(tmp_path: Path):
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_r5_bundle13r_evidence_backflow.py"),
        "--bundle12r-context-dir",
        str(CONTEXT),
        "--reviewed-backfill",
        str(READY),
        "--contract",
        str(CONTRACT),
        "--output-dir",
        str(tmp_path / "ready"),
        "--skip-upstream-hash-check",
        "--strict",
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    assert "decision=ready_for_bundle12r_rerun" in completed.stdout


def test_strict_cli_returns_two_for_incomplete_backflow(tmp_path: Path):
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_r5_bundle13r_evidence_backflow.py"),
        "--bundle12r-context-dir",
        str(CONTEXT),
        "--reviewed-backfill",
        str(PARTIAL),
        "--contract",
        str(CONTRACT),
        "--output-dir",
        str(tmp_path / "partial"),
        "--skip-upstream-hash-check",
        "--strict",
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    assert completed.returncode == 2, completed.stderr
    assert "decision=backflow_execution_in_progress" in completed.stdout


def test_lock_validator_detects_tampering(tmp_path: Path):
    write_bundle13r_outputs(
        context_dir=CONTEXT,
        reviewed_backfill_path=READY,
        contract_path=CONTRACT,
        output_dir=tmp_path,
        verify_bundle12r_hashes=False,
    )
    target = tmp_path / "R5_bundle13r_promoted_operating_evidence_input.yaml"
    target.write_text(target.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")
    assert any("hash mismatch" in row for row in validate_generation_lock(tmp_path / "R5_bundle13r_generation_lock.yaml"))
