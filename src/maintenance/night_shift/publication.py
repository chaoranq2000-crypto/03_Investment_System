"""Stale-baseline detection and non-self-referential publication receipts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from .models import ContractError
from .receipts import canonical_json_bytes, git_value, sha256_bytes


SHA1_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def require_sha1(value: str, *, field: str) -> str:
    normalized = str(value or "").strip().casefold()
    if not SHA1_PATTERN.fullmatch(normalized):
        raise ContractError(f"{field}: expected a 40-character hexadecimal Git SHA")
    return normalized


def require_sha256(value: str, *, field: str) -> str:
    normalized = str(value or "").strip().casefold()
    if not SHA256_PATTERN.fullmatch(normalized):
        raise ContractError(f"{field}: expected a 64-character hexadecimal SHA-256")
    return normalized


def resolve_baseline(*, tracked_source_commit: str, final_remote_head: str) -> dict[str, Any]:
    tracked = require_sha1(tracked_source_commit, field="tracked_source_commit")
    remote = require_sha1(final_remote_head, field="final_remote_head")
    return {
        "tracked_source_commit": tracked,
        "final_remote_head": remote,
        "stale": tracked != remote,
        "resolved_source_commit": remote,
        "resolution_policy": "final_remote_head",
    }


def build_implementation_identity(repo_root: Path) -> dict[str, Any]:
    commit_sha = git_value(repo_root, "rev-parse", "HEAD")
    tree_sha = git_value(repo_root, "rev-parse", "HEAD^{tree}")
    if commit_sha is None or tree_sha is None:
        raise ContractError(f"cannot resolve implementation identity in {repo_root}")
    return {
        "schema_version": "r5_night_shift_implementation_identity_v1",
        "implementation_sha": require_sha1(commit_sha, field="implementation_sha"),
        "implementation_tree_sha": require_sha1(tree_sha, field="implementation_tree_sha"),
        "publication_head": None,
        "identity_phase": "pre_publication",
    }


def build_publication_identity(
    *,
    implementation_receipt_sha256: str,
    local_head: str,
    remote_head: str,
    ci_status: str,
    ci_run_id: str | None = None,
) -> dict[str, Any]:
    local = require_sha1(local_head, field="local_head")
    remote = require_sha1(remote_head, field="remote_head")
    if local != remote:
        raise ContractError(f"publication head mismatch: local={local}, remote={remote}")
    if ci_status not in {"success", "pending", "failure", "cancelled"}:
        raise ContractError(f"ci_status: unsupported value {ci_status!r}")
    receipt: dict[str, Any] = {
        "schema_version": "r5_night_shift_publication_identity_v1",
        "implementation_receipt_sha256": require_sha256(
            implementation_receipt_sha256,
            field="implementation_receipt_sha256",
        ),
        "publication_head": remote,
        "remote_sha_equals_local": True,
        "ci_status": ci_status,
        "ci_run_id": ci_run_id,
        "identity_phase": "post_push",
    }
    receipt["stable_receipt_sha256"] = sha256_bytes(canonical_json_bytes(receipt))
    return receipt


def validate_stable_digest(receipt: Mapping[str, Any]) -> str:
    supplied = require_sha256(
        str(receipt.get("stable_receipt_sha256") or ""),
        field="stable_receipt_sha256",
    )
    projection = {
        key: value for key, value in receipt.items() if key != "stable_receipt_sha256"
    }
    calculated = sha256_bytes(canonical_json_bytes(projection))
    if supplied != calculated:
        raise ContractError(
            f"stable_receipt_sha256 mismatch: supplied={supplied}, calculated={calculated}"
        )
    return supplied
