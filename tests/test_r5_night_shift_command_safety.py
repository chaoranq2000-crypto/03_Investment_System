from __future__ import annotations

import pytest

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
