from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.maintenance.night_shift.models import ContractError
from src.maintenance.night_shift.receipts import (
    build_receipt,
    execute_acceptance,
    expand_repository_globs,
    parse_trusted_command,
    run_acceptance_commands,
    write_failure_packet,
)


def test_trusted_commands_capture_output_hashes_and_stop_on_failure(tmp_path: Path) -> None:
    commands = [
        'python -c "print(123)"',
        'python -c "raise SystemExit(7)"',
        'python -c "raise SystemExit(9)"',
    ]
    receipts, exit_code = run_acceptance_commands(commands, cwd=tmp_path)
    assert exit_code == 7
    assert len(receipts) == 2
    assert receipts[0].exit_code == 0
    assert receipts[0].stdout_length in {4, 5}
    assert len(receipts[0].stdout_sha256) == 64


def test_pytest_glob_expands_deterministically_without_a_shell(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_r5_night_shift_b.py").write_text("def test_b(): pass\n", encoding="utf-8")
    (tests / "test_r5_night_shift_a.py").write_text("def test_a(): pass\n", encoding="utf-8")
    argv = parse_trusted_command("python -m pytest -q tests/test_r5_night_shift_*.py")
    expanded = expand_repository_globs(argv, cwd=tmp_path)
    assert expanded[-2:] == [
        "tests/test_r5_night_shift_a.py",
        "tests/test_r5_night_shift_b.py",
    ]
    receipts, exit_code = run_acceptance_commands(
        ["python -m pytest -q tests/test_r5_night_shift_*.py"], cwd=tmp_path
    )
    assert exit_code == 0
    assert receipts[0].argv[-2:] == tuple(expanded[-2:])


def test_pytest_glob_cannot_escape_repository(tmp_path: Path) -> None:
    argv = parse_trusted_command("python -m pytest ../tests/test_*.py")
    with pytest.raises(ContractError, match="repository-relative"):
        expand_repository_globs(argv, cwd=tmp_path)


@pytest.mark.parametrize(
    "command",
    [
        "powershell Get-ChildItem",
        "python <resolved_command>",
        "python -V && git status",
        "git push origin main",
    ],
)
def test_untrusted_or_unresolved_commands_are_rejected(command: str) -> None:
    with pytest.raises(ContractError):
        parse_trusted_command(command)


def test_receipt_stable_hash_excludes_only_time_fields(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("stable\n", encoding="utf-8")
    command_receipts, exit_code = run_acceptance_commands(
        ['python -c "print(123)"'], cwd=tmp_path
    )
    first = build_receipt(
        run_id="run-a",
        task_id="ns01_t40_receipt",
        attempt=1,
        executor="test",
        cwd=tmp_path,
        commands=command_receipts,
        exit_code=exit_code,
        artifacts=["artifact.txt"],
        started_at=datetime(2026, 7, 19, 0, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 7, 19, 0, 1, tzinfo=timezone.utc),
        terminal_status="passed",
        reason="",
    )
    second = build_receipt(
        run_id="run-a",
        task_id="ns01_t40_receipt",
        attempt=1,
        executor="test",
        cwd=tmp_path,
        commands=command_receipts,
        exit_code=exit_code,
        artifacts=["artifact.txt"],
        started_at=datetime(2026, 7, 19, 1, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 7, 19, 1, 1, tzinfo=timezone.utc),
        terminal_status="passed",
        reason="",
    )
    assert first["stable_receipt_sha256"] == second["stable_receipt_sha256"]
    assert first["started_at"] != second["started_at"]


def test_execute_acceptance_requires_artifacts_and_writes_failure_packet(tmp_path: Path) -> None:
    ticks = iter(
        [
            datetime(2026, 7, 19, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 19, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=1),
        ]
    )
    receipt_path = tmp_path / "receipt.json"
    receipt = execute_acceptance(
        run_id="run-a",
        task_id="ns01_t40_receipt",
        attempt=1,
        executor="test",
        cwd=tmp_path,
        commands=['python -c "print(123)"'],
        artifacts=["missing.txt"],
        receipt_path=receipt_path,
        now=lambda: next(ticks),
    )
    assert receipt["terminal_status"] == "failed_retryable"
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["exit_code"] == 0

    failure_path = tmp_path / "failure.md"
    write_failure_packet(
        failure_path,
        run_id="run-a",
        task_id="ns01_t40_receipt",
        failure_type="missing_artifact",
        observed="missing.txt absent",
        expected="missing.txt present",
        next_action="restore the declared artifact",
    )
    assert "Research blocker resolved: `false`" in failure_path.read_text(encoding="utf-8")
