"""Typed Git targets for safe Windows night-shift publication."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .models import ContractError


WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class GitTarget:
    """A repository worktree and a Git ref kept as separate typed values."""

    worktree_root: Path
    branch: str

    @classmethod
    def create(cls, worktree_root: str | Path, branch: str) -> "GitTarget":
        root_text = str(worktree_root).strip()
        branch_text = str(branch).strip()
        if not root_text:
            raise ContractError("git_target.worktree_root: must not be empty")
        if CONTROL_CHARACTERS.search(root_text):
            raise ContractError("git_target.worktree_root: contains a control character")
        normalized_root = root_text.replace("\\", "/")
        if "codex/" in normalized_root.casefold():
            raise ContractError(
                "git_target.worktree_root: contains a branch fragment; path and branch "
                "must be separate"
            )
        root = Path(root_text)
        if not root.is_absolute() and not WINDOWS_DRIVE.match(root_text):
            raise ContractError("git_target.worktree_root: must be an absolute path")

        if not branch_text:
            raise ContractError("git_target.branch: must not be empty")
        if CONTROL_CHARACTERS.search(branch_text):
            raise ContractError("git_target.branch: contains a control character")
        if WINDOWS_DRIVE.match(branch_text) or "\\" in branch_text:
            raise ContractError(
                "git_target.branch: contains a Windows path; path and branch must be separate"
            )
        if branch_text.startswith(("/", "-")) or branch_text.endswith(("/", ".")):
            raise ContractError("git_target.branch: malformed Git branch ref")
        if any(token in branch_text for token in ("..", "@{", "//")):
            raise ContractError("git_target.branch: malformed Git branch ref")
        if any(char.isspace() for char in branch_text):
            raise ContractError("git_target.branch: whitespace is not allowed")
        return cls(worktree_root=root, branch=branch_text)

    def git_argv(self, *arguments: str) -> tuple[str, ...]:
        """Return an argv vector with cwd and ref still represented separately."""

        return ("git", "-C", str(self.worktree_root), *arguments)

    def push_argv(self, *, remote: str = "origin") -> tuple[str, ...]:
        if not remote or CONTROL_CHARACTERS.search(remote) or any(
            character.isspace() for character in remote
        ):
            raise ContractError("git_target.remote: malformed remote name")
        return self.git_argv("push", remote, self.branch)


def assert_no_git_mutation(arguments: Sequence[str]) -> None:
    """Fail before execution when an argv would widen the Night02 publication scope."""

    lowered = [str(item).casefold() for item in arguments]
    if "--force" in lowered or "--force-with-lease" in lowered or "-f" in lowered:
        raise ContractError("force push is not allowed")
    if "merge" in lowered and "main" in lowered:
        raise ContractError("merge main is not allowed")
    if "push" in lowered and "main" in lowered:
        raise ContractError("push to main is not allowed")
