from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from src.maintenance.night_shift.night03 import Night03Error
from src.maintenance.night_shift.night03_execution import validate_approved_command
from src.maintenance.night_shift.models import ContractError
from src.maintenance.night_shift.receipts import parse_trusted_command


def test_package_style_quoted_python_command_is_structurally_safe() -> None:
    argv = parse_trusted_command(
        'python -c "import subprocess; s=subprocess.check_output([\'git\',\'rev-parse\',\'HEAD\'], text=True).strip(); assert len(s) == 40"'
    )
    assert argv[1] == "-c"


@pytest.mark.parametrize(
    "command",
    [
        "python -V && git status",
        'python -c "import requests; requests.get(\'https://example.com\')"',
        "python -m pip install unsafe",
        "python <resolved_command>",
        "git push --force origin codex/topic",
        "git merge main",
        "git push origin main",
    ],
)
def test_shell_network_and_mutating_git_commands_are_rejected(command: str) -> None:
    with pytest.raises(ContractError):
        parse_trusted_command(command)


def test_night03_requires_exact_command_hash_and_read_only_execution_boundary() -> None:
    command = "python -m pytest -q tests/test_r5_night_shift_command_safety.py"
    digest = hashlib.sha256(command.encode("utf-8")).hexdigest()
    argv = validate_approved_command(command, approved_command_sha256=digest)
    assert Path(argv[0]).name.casefold().startswith("python")
    assert argv[1:3] == ["-m", "pytest"]
    with pytest.raises(Night03Error, match="exact-hash mismatch"):
        validate_approved_command(command, approved_command_sha256="0" * 64)
    push = "git push origin branch"
    with pytest.raises(Night03Error, match="forbidden fragment"):
        validate_approved_command(
            push,
            approved_command_sha256=hashlib.sha256(push.encode("utf-8")).hexdigest(),
        )
