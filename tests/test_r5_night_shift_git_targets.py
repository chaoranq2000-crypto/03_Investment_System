from __future__ import annotations

from pathlib import Path

import pytest

from src.maintenance.night_shift.models import ContractError
from src.maintenance.night_shift.targets import GitTarget, assert_no_git_mutation


def test_windows_worktree_path_and_branch_remain_separate(tmp_path: Path) -> None:
    root = tmp_path / "work tree 研究"
    target = GitTarget.create(root, "codex/r5-night02-contract-recovery")
    assert target.worktree_root == root
    assert target.branch == "codex/r5-night02-contract-recovery"
    assert target.git_argv("status") == ("git", "-C", str(root), "status")
    assert target.push_argv()[-2:] == ("origin", target.branch)


@pytest.mark.parametrize(
    ("root", "branch", "needle"),
    [
        (r"C:\Projects\night02codex/r5-night02", "codex/r5-night02", "branch fragment"),
        (r"C:\Projects\night02", r"C:\Projects\night02", "Windows path"),
        (r"C:\Projects\night02", "codex\\r5-night02", "Windows path"),
        (r"C:\Projects\night02", "codex/r5 night02", "whitespace"),
    ],
)
def test_malformed_path_branch_targets_fail_before_git(
    root: str, branch: str, needle: str
) -> None:
    with pytest.raises(ContractError, match=needle):
        GitTarget.create(root, branch)


@pytest.mark.parametrize(
    "argv",
    [
        ("git", "push", "--force", "origin", "codex/topic"),
        ("git", "push", "origin", "main"),
        ("git", "merge", "main"),
    ],
)
def test_mutating_forbidden_git_targets_is_rejected(argv: tuple[str, ...]) -> None:
    with pytest.raises(ContractError):
        assert_no_git_mutation(argv)
