from __future__ import annotations

from dataclasses import replace

import pytest

from src.maintenance.night_shift.contracts import (
    authorize_packaged_task,
    lint_executable_contract,
    validate_allowed_paths,
)
from src.maintenance.night_shift.models import ContractError, Task

from tests.test_r5_night_shift_contract import task


def authorized_task() -> Task:
    base = Task.from_mapping(task("ns02_t21_contract_lint"), path="task")
    return authorize_packaged_task(base, package_digest_sha256="a" * 64)


@pytest.mark.parametrize("paths", [[], ["**"], ["."], ["<resolved_path>"], ["../escape.py"]])
def test_empty_placeholder_or_repository_wide_paths_fail(paths: list[str]) -> None:
    with pytest.raises(ContractError):
        validate_allowed_paths(paths)


def test_lint_requires_commands_and_all_authority_fields() -> None:
    broken = replace(
        authorized_task(),
        acceptance_commands=(),
        path_authority="",
        review_state="proposed",
    )
    result = lint_executable_contract(broken)
    assert result["passed"] is False
    assert any("acceptance_commands" in item for item in result["errors"])
    assert any("path_authority" in item for item in result["errors"])
    assert any("review_state" in item for item in result["errors"])
