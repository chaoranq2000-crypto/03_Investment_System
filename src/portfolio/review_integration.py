"""Failure-isolated bridge from portfolio commits to investment-review sync.

The portfolio database remains the authoritative source.  This module only
selects an explicitly configured review sidecar and invokes the review sync
service after the portfolio transaction has already committed.  It never
creates or initializes a sidecar and it never lets review failures escape back
into the portfolio import path.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Mapping


REVIEW_DATABASE_ENV = "INVESTMENT_REVIEW_DB"

SyncHook = Callable[..., Mapping[str, Any]]

# Deliberately replaceable in tests.  Production leaves this as ``None`` so the
# review service is imported lazily only after a successful portfolio commit.
POST_COMMIT_SYNC_HOOK: SyncHook | None = None


def _containing_checkout(path: Path) -> Path | None:
    for parent in (path.parent, *path.parents):
        if (parent / ".git").exists():
            return parent.resolve(strict=False)
    return None


def configured_review_database(
    explicit_path: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> Path | None:
    """Return the explicitly selected absolute sidecar path, if any.

    There is intentionally no current-working-directory or linked-worktree
    fallback.  In particular, running a command from another checkout must not
    make that checkout's existing sidecar an implicit write target.
    """

    raw_value: str | Path | None = explicit_path
    if raw_value is None:
        raw_value = (os.environ if environ is None else environ).get(REVIEW_DATABASE_ENV)
    if raw_value is None or not str(raw_value).strip():
        return None
    candidate = Path(str(raw_value).strip()).expanduser()
    if not candidate.is_absolute():
        raise ValueError(f"{REVIEW_DATABASE_ENV} must be an absolute path")
    resolved = candidate.resolve(strict=False)
    current_checkout = Path(__file__).resolve().parents[2]
    candidate_checkout = _containing_checkout(resolved)
    if candidate_checkout is not None and candidate_checkout != current_checkout:
        raise ValueError(
            f"{REVIEW_DATABASE_ENV} belongs to a different checkout: "
            f"{candidate_checkout}"
        )
    return resolved


def _default_post_commit_sync(
    *,
    portfolio_db: Path,
    review_db: Path,
    trigger: str,
) -> Mapping[str, Any]:
    """Load the P2 sync service only when an initialized sidecar is selected."""

    from src.investment_review.sync_service import sync_after_portfolio_commit

    return sync_after_portfolio_commit(
        portfolio_db,
        explicit_review_db=review_db,
    )


def trigger_post_commit_review_sync(
    portfolio_db: str | Path,
    *,
    review_db: str | Path | None = None,
) -> dict[str, Any]:
    """Run one best-effort catch-up after a committed statement import.

    Every return value is suitable for inclusion in the existing JSON summary.
    Configuration and review-side failures are visible but never raised.
    """

    try:
        selected_review_db = configured_review_database(review_db)
    except Exception as exc:
        return {
            "status": "failed",
            "trigger": "portfolio_statement_post_commit",
            "reason": "invalid_review_database_configuration",
            "error": str(exc),
        }

    if selected_review_db is None:
        return {
            "status": "disabled",
            "trigger": "portfolio_statement_post_commit",
            "reason": f"{REVIEW_DATABASE_ENV} is not configured",
        }
    try:
        review_db_exists = selected_review_db.is_file()
        source = Path(portfolio_db).resolve(strict=False)
    except Exception as exc:
        return {
            "status": "failed",
            "trigger": "portfolio_statement_post_commit",
            "review_db": str(selected_review_db),
            "reason": "review_sync_path_check_failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

    if not review_db_exists:
        return {
            "status": "not_initialized",
            "trigger": "portfolio_statement_post_commit",
            "review_db": str(selected_review_db),
            "reason": "configured review sidecar does not exist",
        }

    if source == selected_review_db:
        return {
            "status": "failed",
            "trigger": "portfolio_statement_post_commit",
            "review_db": str(selected_review_db),
            "reason": "portfolio_and_review_database_must_be_separate",
        }

    hook = POST_COMMIT_SYNC_HOOK or _default_post_commit_sync
    try:
        result = dict(
            hook(
                portfolio_db=source,
                review_db=selected_review_db,
                trigger="portfolio_statement_post_commit",
            )
        )
    except Exception as exc:  # review failures must not roll back portfolio state
        return {
            "status": "failed",
            "trigger": "portfolio_statement_post_commit",
            "review_db": str(selected_review_db),
            "reason": "review_sync_failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

    result.setdefault("status", "succeeded")
    result.setdefault("trigger", "portfolio_statement_post_commit")
    result.setdefault("review_db", str(selected_review_db))
    return result
