#!/usr/bin/env python3
"""Deterministic and transactional file I/O for R5 reviewed-input registries.

The promotion workflow builds and validates every candidate registry in memory
before calling :func:`commit_registry_bytes`.  This module then stages changed
files beside their targets, flushes them to disk, and replaces the targets only
after every staging write succeeds.  If staging or replacement fails, the
saved target bytes are restored and any temporary files are removed.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

import yaml

RegistryAction = Literal["created", "updated", "unchanged"]


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML mapping from *path*.

    A missing path represents an empty registry and therefore returns an empty
    dictionary.  Existing YAML must have a mapping at its document root;
    scalars, sequences, and empty documents are rejected rather than silently
    converted into an empty registry.
    """

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}

    payload = yaml.safe_load(raw)
    if not isinstance(payload, Mapping):
        raise ValueError(
            f"YAML document must contain a mapping: {path} "
            f"(found {type(payload).__name__})"
        )
    return dict(payload)


def dump_yaml_bytes(payload: dict[str, Any]) -> bytes:
    """Serialize *payload* to deterministic UTF-8 YAML ending in a newline."""

    rendered = yaml.safe_dump(
        payload,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        line_break="\n",
    )
    if not rendered.endswith("\n"):
        rendered += "\n"
    return rendered.encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    """Return the lowercase hexadecimal SHA-256 digest of *data*."""

    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str | None:
    """Return the SHA-256 digest for *path*, or ``None`` when it is absent."""

    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None
    return sha256_bytes(data)


def planned_action(path: Path, after_bytes: bytes) -> RegistryAction:
    """Classify how writing *after_bytes* would affect *path*."""

    try:
        before_bytes = path.read_bytes()
    except FileNotFoundError:
        return "created"
    return "unchanged" if before_bytes == after_bytes else "updated"


def _stage_bytes(target: Path, data: bytes) -> Path:
    """Write and fsync *data* to a unique temporary file beside *target*."""

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        # fdopen owns the descriptor once entered.  If it failed before taking
        # ownership, closing an already-closed descriptor is harmlessly
        # ignored here.
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        raise
    return temporary_path


def _restore_target(target: Path, before_bytes: bytes | None) -> None:
    """Restore one target to its captured pre-commit byte state."""

    if before_bytes is None:
        try:
            target.unlink()
        except FileNotFoundError:
            pass
        return

    try:
        if target.read_bytes() == before_bytes:
            return
    except FileNotFoundError:
        pass

    # Recovery deliberately writes the saved bytes directly.  It therefore
    # remains usable when os.replace itself is the failing operation.
    with target.open("wb") as stream:
        stream.write(before_bytes)
        stream.flush()
        os.fsync(stream.fileno())


def _cleanup_temporary_files(paths: list[Path]) -> list[OSError]:
    """Unlink explicit temporary paths and return any cleanup errors."""

    errors: list[OSError] = []
    for path in paths:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            errors.append(exc)
    return errors


def commit_registry_bytes(candidates: dict[Path, bytes]) -> None:
    """Commit registry candidates as one rollback-protected transaction.

    Candidate paths are handled in stable lexical order.  Byte-identical
    targets are left untouched.  Every changed candidate is first written and
    fsynced to a temporary file in its target directory; only after all staging
    writes succeed are the temporary files moved into place with
    :func:`os.replace`.

    On any staging or replacement failure, all candidate targets are restored
    from their captured pre-commit bytes.  Targets that did not exist before
    the call are removed individually, and all remaining temporary files are
    individually cleaned up.  The original failure is re-raised unless
    rollback itself fails, in which case a ``RuntimeError`` reports that the
    transaction could not be fully restored.
    """

    ordered_candidates = sorted(candidates.items(), key=lambda item: str(item[0]))
    for target, data in ordered_candidates:
        if not isinstance(target, Path):
            raise TypeError(
                f"registry target must be a pathlib.Path, got {type(target).__name__}"
            )
        if not isinstance(data, bytes):
            raise TypeError(f"registry payload for {target} must be bytes")

    before_by_target: dict[Path, bytes | None] = {}
    changed_candidates: list[tuple[Path, bytes]] = []
    for target, after_bytes in ordered_candidates:
        try:
            before_bytes: bytes | None = target.read_bytes()
        except FileNotFoundError:
            before_bytes = None
        before_by_target[target] = before_bytes
        if before_bytes is None or before_bytes != after_bytes:
            changed_candidates.append((target, after_bytes))

    staged_by_target: dict[Path, Path] = {}
    try:
        for target, after_bytes in changed_candidates:
            staged_by_target[target] = _stage_bytes(target, after_bytes)

        for target, _after_bytes in changed_candidates:
            temporary_path = staged_by_target[target]
            os.replace(temporary_path, target)
            del staged_by_target[target]
    except Exception as commit_error:
        rollback_errors: list[Exception] = []
        for target, _after_bytes in changed_candidates:
            try:
                _restore_target(target, before_by_target[target])
            except Exception as exc:  # pragma: no cover - exceptional filesystem failure
                rollback_errors.append(exc)

        rollback_errors.extend(_cleanup_temporary_files(list(staged_by_target.values())))
        staged_by_target.clear()
        if rollback_errors:
            details = "; ".join(str(error) for error in rollback_errors)
            raise RuntimeError(
                f"registry commit failed and rollback was incomplete: {details}"
            ) from commit_error
        raise
    finally:
        _cleanup_temporary_files(list(staged_by_target.values()))
