from __future__ import annotations

from pathlib import Path


def repository_root(anchor: str | Path | None = None) -> Path:
    """Return the checkout root that contains this portfolio package."""
    current = Path(anchor).resolve() if anchor is not None else Path(__file__).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return Path.cwd().resolve()


def primary_worktree_root(project_root: str | Path | None = None) -> Path:
    """Resolve a linked worktree to the primary checkout that owns the private runtime."""
    root = Path(project_root).resolve() if project_root is not None else repository_root()
    git_pointer = root / ".git"
    if not git_pointer.is_file():
        return root

    try:
        first_line = git_pointer.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, IndexError, UnicodeError):
        return root
    prefix = "gitdir:"
    if not first_line.lower().startswith(prefix):
        return root

    linked_git_dir = Path(first_line[len(prefix) :].strip())
    if not linked_git_dir.is_absolute():
        linked_git_dir = root / linked_git_dir
    linked_git_dir = linked_git_dir.resolve()

    worktrees_dir = linked_git_dir.parent
    common_git_dir = worktrees_dir.parent
    if worktrees_dir.name.lower() != "worktrees" or common_git_dir.name.lower() != ".git":
        return root
    return common_git_dir.parent.resolve()


def default_database_path(project_root: str | Path | None = None) -> Path:
    return primary_worktree_root(project_root) / "data" / "db" / "portfolio.sqlite3"


def canonical_database_path(
    path: str | Path,
    project_root: str | Path | None = None,
) -> Path:
    """Prevent a linked worktree's reserved formal filename from becoming a second ledger."""
    local_root = Path(project_root).resolve() if project_root is not None else repository_root()
    requested = Path(path)
    if not requested.is_absolute():
        requested = Path.cwd() / requested
    requested = requested.resolve()

    local_reserved = (local_root / "data" / "db" / "portfolio.sqlite3").resolve()
    primary_reserved = default_database_path(local_root).resolve()
    if local_reserved != primary_reserved and requested == local_reserved:
        return primary_reserved
    return requested


def default_env_file_path(project_root: str | Path | None = None) -> Path:
    return primary_worktree_root(project_root) / ".env.local"
