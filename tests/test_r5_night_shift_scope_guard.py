from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.maintenance.night_shift.contracts import capture_tree_snapshot, enforce_task_scope
from src.maintenance.night_shift.models import ContractError


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_pre_and_post_tree_snapshots_enforce_allowed_paths(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    (repo / "src").mkdir()
    (repo / "reports").mkdir()
    (repo / "src/allowed.py").write_text("before\n", encoding="utf-8")
    (repo / "reports/read_only.md").write_text("immutable\n", encoding="utf-8")
    git(repo, "add", "src/allowed.py", "reports/read_only.md")
    before = capture_tree_snapshot(repo)

    (repo / "src/allowed.py").write_text("after\n", encoding="utf-8")
    after = capture_tree_snapshot(repo)
    result = enforce_task_scope(
        before,
        after,
        allowed_paths=["src/**"],
        forbidden_paths=["reports/**"],
    )
    assert result["changed_paths"] == ["src/allowed.py"]

    before_forbidden = after
    (repo / "reports/read_only.md").write_text("mutated\n", encoding="utf-8")
    after_forbidden = capture_tree_snapshot(repo)
    with pytest.raises(ContractError, match="scope violation"):
        enforce_task_scope(
            before_forbidden,
            after_forbidden,
            allowed_paths=["src/**"],
            forbidden_paths=["reports/**"],
        )
