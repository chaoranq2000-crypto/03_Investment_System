"""Strict deterministic JSON and atomic artifact I/O helpers."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping


class ArtifactIOError(ValueError):
    """Raised when an artifact cannot be serialized or loaded safely."""


def _reject_floats(value: Any, path: str = "$") -> None:
    if isinstance(value, float):
        raise ArtifactIOError(f"binary float is not allowed at {path}")
    if isinstance(value, Mapping):
        for key, item in value.items():
            _reject_floats(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_floats(item, f"{path}[{index}]")


def canonical_json_bytes(value: Any) -> bytes:
    """Return strict UTF-8 canonical JSON bytes without wall-clock metadata."""

    _reject_floats(value)
    try:
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ArtifactIOError(str(exc)) from exc
    return rendered.encode("utf-8")


def pretty_json_bytes(value: Any) -> bytes:
    """Return stable human-readable JSON bytes with a final newline."""

    _reject_floats(value)
    try:
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ArtifactIOError(str(exc)) from exc
    return (rendered + "\n").encode("utf-8")


def atomic_write_bytes(path: str | Path, data: bytes) -> Path:
    """Atomically replace one explicit path using a temporary sibling file."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        descriptor, raw_path = tempfile.mkstemp(
            prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
        )
        temporary = Path(raw_path)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
        temporary = None
        return output
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def atomic_create_bytes(path: str | Path, data: bytes) -> Path:
    """Atomically create one new path and refuse to replace an existing artifact."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        descriptor, raw_path = tempfile.mkstemp(
            prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
        )
        temporary = Path(raw_path)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, output)
        return output
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def load_json_object(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ArtifactIOError("artifact root must be a JSON object")
    _reject_floats(payload)
    return payload
