"""Separate SQLite store for normalized review data."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

from .artifact_io import canonical_json_bytes
from .behavior_hypothesis_candidates import (
    _canonical_timestamp,
    project_behavior_hypothesis_state,
    replay_validate_behavior_hypothesis_candidate,
    validate_behavior_hypothesis_review_event,
)
from .behavior_observation_protocols import (
    project_observation_protocol_state,
    replay_validate_observation_protocol,
    validate_observation_protocol_review_event,
)
from .models import (
    CanonicalTradeEvent,
    DecisionRecord,
    FeeCorrectionRecord,
    FeeProfileRecord,
    FeeProjectionRecord,
    MARKET_FALLBACK_POLICY_VERSION,
    MARKET_FALLBACK_POLICY_VERSION_V2,
    MARKET_PROVIDER_ALLOWLIST_SHA256,
    MARKET_PROVIDER_ALLOWLIST_VERSION,
    OPERATION_CHECKPOINT_SCHEMA_VERSION,
    OPERATION_CHECKPOINT_SCHEMA_VERSION_V2,
    PUBLIC_INFORMATION_POLICY_VERSION,
    OperationCheckpointRecord,
    OperationCheckpointRecordV2,
    ReviewRunRecord,
    ReviewRunStatusEvent,
    SourceDefinition,
    canonical_json,
    operation_checkpoint_from_mapping,
    sha256_text,
)
from .portfolio_context import PortfolioContext, PortfolioSnapshot, calculate_portfolio_metrics
from .time_utils import utc_iso


SCHEMA_VERSION = 2
APPLICATION_ID = 0x49525657  # ASCII "IRVW"
P2H_STAGE1_SCHEMA_VERSION = 1
P2H_STAGE2_SLICE_A_SCHEMA_VERSION = 1
PRODUCT_COMPLETION_SCHEMA_VERSION = 1
REVIEWABILITY_SCHEMA_VERSION = 1
REVIEWABILITY_SCHEMA_VERSION_V1 = REVIEWABILITY_SCHEMA_VERSION
REVIEWABILITY_SCHEMA_VERSION_V2 = 2

_IMMUTABLE_READ_CONTEXT_PATHS: ContextVar[frozenset[str]] = ContextVar(
    "investment_review_immutable_read_context_paths",
    default=frozenset(),
)


def _immutable_context_path(path: str | Path) -> str:
    return str(Path(path).resolve(strict=False)).casefold()


@contextmanager
def immutable_review_store_read_context(
    path: str | Path,
) -> Iterator[None]:
    """Make nested ``ReviewStore(path)`` instances immutable and non-writable.

    Receipt validation reconstructs a store internally.  The acceptance
    service uses this context so those nested readers inherit the same
    immutable/query-only boundary as the explicit acceptance store.
    """

    selected = _immutable_context_path(path)
    current = _IMMUTABLE_READ_CONTEXT_PATHS.get()
    token = _IMMUTABLE_READ_CONTEXT_PATHS.set(current | {selected})
    try:
        yield
    finally:
        _IMMUTABLE_READ_CONTEXT_PATHS.reset(token)


class ReviewStoreError(RuntimeError):
    """Base error for the review store."""


class DataConflictError(ReviewStoreError):
    """Same source record ID was observed with different content."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_file_state(path: Path) -> tuple[int, int, int, int, str] | None:
    """Read a file identity/content snapshot without accepting an in-read race."""

    if not path.exists():
        return None
    before = path.stat()
    digest = _sha256_file(path)
    after = path.stat()
    if (
        not os.path.samestat(before, after)
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
    ):
        raise OSError(f"File changed while hashing: {path}")
    return (
        int(after.st_dev),
        int(after.st_ino),
        int(after.st_size),
        int(after.st_mtime_ns),
        digest,
    )


if os.name == "nt":
    _FILE_READ_ATTRIBUTES = 0x0080
    _FILE_SHARE_READ = 0x00000001
    _FILE_SHARE_WRITE = 0x00000002
    _OPEN_EXISTING = 3
    _FILE_ATTRIBUTE_NORMAL = 0x00000080
    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    _WINDOWS_EPOCH_100NS = 116444736000000000

    class _Win32FileTime(ctypes.Structure):
        _fields_ = [
            ("dwLowDateTime", wintypes.DWORD),
            ("dwHighDateTime", wintypes.DWORD),
        ]

    class _Win32ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", _Win32FileTime),
            ("ftLastAccessTime", _Win32FileTime),
            ("ftLastWriteTime", _Win32FileTime),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _CREATE_FILE_W = _KERNEL32.CreateFileW
    _CREATE_FILE_W.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    _CREATE_FILE_W.restype = wintypes.HANDLE
    _GET_FILE_INFORMATION_BY_HANDLE = _KERNEL32.GetFileInformationByHandle
    _GET_FILE_INFORMATION_BY_HANDLE.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_Win32ByHandleFileInformation),
    ]
    _GET_FILE_INFORMATION_BY_HANDLE.restype = wintypes.BOOL
    _CLOSE_HANDLE = _KERNEL32.CloseHandle
    _CLOSE_HANDLE.argtypes = [wintypes.HANDLE]
    _CLOSE_HANDLE.restype = wintypes.BOOL


class _HeldUpgradeFile:
    """Keep one upgrade input bound to its original filesystem object.

    On Windows the handle deliberately omits ``FILE_SHARE_DELETE``.  As long as
    it is open, the candidate path cannot be renamed away or replaced between
    SQLite's ``mode=rw`` open and the next pathname check.  The POSIX fallback
    keeps an fd open and rebinds the path to that fd at every gate; it does not
    claim Windows delete-share semantics.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle: int | None = None
        self._fd: int | None = None
        self._closed = False
        if os.name == "nt":
            handle = _CREATE_FILE_W(
                str(path),
                _FILE_READ_ATTRIBUTES,
                _FILE_SHARE_READ | _FILE_SHARE_WRITE,
                None,
                _OPEN_EXISTING,
                _FILE_ATTRIBUTE_NORMAL,
                None,
            )
            if handle in (None, _INVALID_HANDLE_VALUE):
                error = ctypes.get_last_error()
                raise OSError(error, f"CreateFileW no-delete hold failed: {path}")
            self._handle = int(handle)
        else:
            flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
            self._fd = os.open(path, flags)
        self._initial_handle_state = self._read_handle_state()

    def _read_handle_state(self) -> tuple[int, int, int, int]:
        if self._closed:
            raise OSError(f"Upgrade file hold was already closed: {self.path}")
        if os.name == "nt":
            if self._handle is None:
                raise OSError(f"Missing Win32 upgrade handle: {self.path}")
            information = _Win32ByHandleFileInformation()
            if not _GET_FILE_INFORMATION_BY_HANDLE(
                self._handle, ctypes.byref(information)
            ):
                error = ctypes.get_last_error()
                raise OSError(
                    error,
                    f"GetFileInformationByHandle failed: {self.path}",
                )
            file_index = (
                int(information.nFileIndexHigh) << 32
            ) | int(information.nFileIndexLow)
            size = (int(information.nFileSizeHigh) << 32) | int(
                information.nFileSizeLow
            )
            filetime = (
                int(information.ftLastWriteTime.dwHighDateTime) << 32
            ) | int(information.ftLastWriteTime.dwLowDateTime)
            mtime_ns = (filetime - _WINDOWS_EPOCH_100NS) * 100
            return (
                int(information.dwVolumeSerialNumber),
                file_index,
                size,
                mtime_ns,
            )
        if self._fd is None:
            raise OSError(f"Missing POSIX upgrade descriptor: {self.path}")
        stat_result = os.fstat(self._fd)
        return (
            int(stat_result.st_dev),
            int(stat_result.st_ino),
            int(stat_result.st_size),
            int(stat_result.st_mtime_ns),
        )

    @staticmethod
    def _read_path_identity(path: Path) -> tuple[int, int]:
        if os.name == "nt":
            transient = _HeldUpgradeFile(path)
            try:
                return transient._initial_handle_state[:2]
            finally:
                transient.close()
        stat_result = path.stat()
        return (int(stat_result.st_dev), int(stat_result.st_ino))

    def assert_initial_snapshot(
        self,
        expected: tuple[int, int, int, int, str],
        *,
        stage: str,
    ) -> None:
        current = self._read_handle_state()
        if current != self._initial_handle_state:
            raise ReviewStoreError(
                f"Reviewability held handle changed during {stage}: {self.path}."
            )
        if os.name == "nt":
            # CPython's Windows st_ino is the 64-bit file index returned by
            # BY_HANDLE_FILE_INFORMATION.  Volume identity is independently
            # rebound by opening the same absolute path below.
            snapshot_matches_handle = (
                expected[1] == current[1]
                and expected[2] == current[2]
                and expected[3] == current[3]
            )
        else:
            snapshot_matches_handle = expected[:4] == current
        if not snapshot_matches_handle or _stable_file_state(self.path) != expected:
            raise ReviewStoreError(
                f"Reviewability before snapshot is not bound to held handle at "
                f"{stage}: {self.path}."
            )
        if self._read_path_identity(self.path) != current[:2]:
            raise ReviewStoreError(
                f"Reviewability path is not bound to held handle at {stage}: "
                f"{self.path}."
            )

    def assert_current_binding(self, *, stage: str) -> None:
        current = self.assert_held_identity(stage=stage)
        if self._read_path_identity(self.path) != current[:2]:
            raise ReviewStoreError(
                f"Reviewability path-to-held-handle binding changed at {stage}: "
                f"{self.path}."
            )

    def assert_held_identity(self, *, stage: str) -> tuple[int, int, int, int]:
        current = self._read_handle_state()
        if current[:2] != self._initial_handle_state[:2]:
            raise ReviewStoreError(
                f"Reviewability held handle identity changed at {stage}: "
                f"{self.path}."
            )
        return current

    def assert_held_identity_and_size(self, *, stage: str) -> None:
        current = self.assert_held_identity(stage=stage)
        if current[:3] != self._initial_handle_state[:3]:
            raise ReviewStoreError(
                f"Reviewability held handle identity or size changed at {stage}: "
                f"{self.path}."
            )

    def close(self) -> None:
        if self._closed:
            return
        if os.name == "nt":
            if self._handle is not None:
                _CLOSE_HANDLE(self._handle)
                self._handle = None
        elif self._fd is not None:
            os.close(self._fd)
            self._fd = None
        self._closed = True


class _ReviewabilityUpgradeFileGuard:
    def __init__(
        self,
        path: Path,
        *,
        expected_main: tuple[int, int, int, int, str],
        expected_wal: tuple[int, int, int, int, str] | None,
        expected_shm: tuple[int, int, int, int, str] | None,
    ) -> None:
        self.path = path
        self.expected_main = expected_main
        self.expected_wal = expected_wal
        self.expected_shm = expected_shm
        self._files: dict[str, _HeldUpgradeFile] = {}
        self._writer_open = False
        self._writer_conn: sqlite3.Connection | None = None
        self._marker_committed = False
        self._checkpoint_complete = False
        self._checkpoint_result: tuple[int, int, int] | None = None
        self._auxiliary_terminal_absent = False
        targets = [
            ("main", path, expected_main),
            ("wal", Path(f"{path}-wal"), expected_wal),
            ("shm", Path(f"{path}-shm"), expected_shm),
        ]
        try:
            for label, target, expected in targets:
                if expected is None:
                    continue
                held = _HeldUpgradeFile(target)
                self._files[label] = held
                held.assert_initial_snapshot(expected, stage="initial_no_delete_hold")
        except Exception:
            self.close()
            raise

    @staticmethod
    def _strict_path_present(path: Path, *, stage: str) -> bool:
        try:
            path.stat()
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise ReviewStoreError(
                f"Reviewability auxiliary path is unreadable at {stage}: "
                f"{path}: {exc}"
            ) from exc
        return True

    def assert_current(self, *, stage: str) -> None:
        main = self._files.get("main")
        if main is None:
            raise ReviewStoreError(
                f"Reviewability held main file is missing at {stage}."
            )
        main.assert_current_binding(stage=f"{stage}:main")
        auxiliary = {
            label: self._files.get(label) for label in ("wal", "shm")
        }
        wal_path = Path(f"{self.path}-wal")
        shm_path = Path(f"{self.path}-shm")
        if self._auxiliary_terminal_absent:
            for label, held in auxiliary.items():
                if held is not None:
                    held.assert_held_identity_and_size(stage=f"{stage}:{label}")
            wal_present = self._strict_path_present(
                wal_path, stage=f"{stage}:wal"
            )
            shm_present = self._strict_path_present(
                shm_path, stage=f"{stage}:shm"
            )
            if wal_present or shm_present:
                raise ReviewStoreError(
                    "Reviewability WAL/SHM reappeared after the terminal "
                    f"absent transition at {stage}."
                )
            return
        for label, held in auxiliary.items():
            if held is not None:
                held.assert_current_binding(stage=f"{stage}:{label}")

    def mark_marker_committed(self, *, stage: str) -> None:
        if not self._writer_open:
            raise ReviewStoreError(
                f"Reviewability marker commit lacks an active writer at {stage}."
            )
        if self._marker_committed:
            raise ReviewStoreError(
                f"Reviewability marker commit was recorded twice at {stage}."
            )
        self.assert_current(stage=stage)
        self._marker_committed = True

    def note_writer_open(
        self,
        conn: sqlite3.Connection,
        *,
        stage: str,
    ) -> None:
        if self._auxiliary_terminal_absent:
            raise ReviewStoreError(
                f"Reviewability writer reopened after terminal absence at {stage}."
            )
        if self._writer_open:
            raise ReviewStoreError(
                f"Reviewability upgrade opened overlapping writers at {stage}."
            )
        try:
            conn.in_transaction
        except sqlite3.ProgrammingError as exc:
            raise ReviewStoreError(
                f"Reviewability writer is already closed at {stage}."
            ) from exc
        self.assert_current(stage=stage)
        self.assert_sqlite_main_binding(conn, stage=stage)
        self._writer_open = True
        self._writer_conn = conn

    def record_checkpoint_result(
        self,
        result: Sequence[Any] | None,
        *,
        stage: str,
    ) -> bool:
        if not self._writer_open:
            raise ReviewStoreError(
                f"Reviewability WAL checkpoint lacks an active writer at {stage}."
            )
        if not self._marker_committed:
            raise ReviewStoreError(
                f"Reviewability WAL checkpoint preceded marker commit at {stage}."
            )
        self.assert_current(stage=stage)
        try:
            normalized = tuple(int(value) for value in result)
        except (TypeError, ValueError) as exc:
            raise ReviewStoreError(
                f"Reviewability WAL checkpoint result is incomplete at {stage}."
            ) from exc
        if len(normalized) != 3:
            raise ReviewStoreError(
                f"Reviewability WAL checkpoint result is incomplete at {stage}."
            )
        self._checkpoint_result = normalized
        self._checkpoint_complete = normalized == (0, 0, 0)
        return self._checkpoint_complete

    @staticmethod
    def _assert_connection_closed(
        conn: sqlite3.Connection,
        *,
        stage: str,
    ) -> None:
        try:
            conn.in_transaction
        except sqlite3.ProgrammingError:
            return
        raise ReviewStoreError(
            f"Reviewability writer remained open at {stage}."
        )

    def assert_after_writer_close(
        self,
        conn: sqlite3.Connection,
        *,
        stage: str,
    ) -> None:
        if not self._writer_open:
            raise ReviewStoreError(
                f"Reviewability writer-close proof has no active writer at {stage}."
            )
        if self._writer_conn is not conn:
            raise ReviewStoreError(
                f"Reviewability writer-close proof changed connection at {stage}."
            )
        self._assert_connection_closed(conn, stage=stage)
        self._writer_open = False
        self._writer_conn = None
        main = self._files.get("main")
        if main is None:
            raise ReviewStoreError(
                f"Reviewability held main file is missing at {stage}."
            )
        main.assert_current_binding(stage=f"{stage}:main")

        auxiliary = {
            label: self._files.get(label) for label in ("wal", "shm")
        }
        for label, held in auxiliary.items():
            if held is not None:
                held.assert_held_identity(stage=f"{stage}:{label}")

        wal_path = Path(f"{self.path}-wal")
        shm_path = Path(f"{self.path}-shm")
        wal_exists = self._strict_path_present(wal_path, stage=f"{stage}:wal")
        shm_exists = self._strict_path_present(shm_path, stage=f"{stage}:shm")
        if self._auxiliary_terminal_absent:
            for label, held in auxiliary.items():
                if held is not None:
                    held.assert_held_identity_and_size(stage=f"{stage}:{label}")
            if wal_exists or shm_exists:
                raise ReviewStoreError(
                    "Reviewability WAL/SHM reappeared after the terminal "
                    f"absent transition at {stage}."
                )
            return
        if wal_exists != shm_exists:
            raise ReviewStoreError(
                f"Reviewability WAL/SHM disappeared one-sided at {stage}."
            )
        if wal_exists:
            if auxiliary["wal"] is None or auxiliary["shm"] is None:
                raise ReviewStoreError(
                    f"Reviewability unheld WAL/SHM remained after writer close at {stage}."
                )
            if self._checkpoint_complete:
                auxiliary["wal"].assert_held_identity_and_size(
                    stage=f"{stage}:wal"
                )
                auxiliary["shm"].assert_held_identity_and_size(
                    stage=f"{stage}:shm"
                )
            auxiliary["wal"].assert_current_binding(stage=f"{stage}:wal")
            auxiliary["shm"].assert_current_binding(stage=f"{stage}:shm")
            return

        if not self._marker_committed:
            raise ReviewStoreError(
                f"Reviewability WAL/SHM disappeared before marker commit at {stage}."
            )
        if not self._checkpoint_complete:
            raise ReviewStoreError(
                "Reviewability WAL/SHM disappeared before an exact "
                f"(0, 0, 0) checkpoint at {stage}."
            )
        expected_pair = self.expected_wal is not None or self.expected_shm is not None
        if expected_pair:
            if self.expected_wal is None or self.expected_shm is None:
                raise ReviewStoreError(
                    f"Reviewability entrance WAL/SHM was not paired at {stage}."
                )
            if (
                self.expected_wal[2] != 0
                or self.expected_wal[4] != hashlib.sha256(b"").hexdigest()
                or self.expected_shm[2] != 32768
            ):
                raise ReviewStoreError(
                    "Reviewability terminal absence requires the entrance zero-WAL "
                    f"and 32768-byte SHM pair at {stage}."
                )
            if auxiliary["wal"] is None or auxiliary["shm"] is None:
                raise ReviewStoreError(
                    f"Reviewability entrance WAL/SHM holds are missing at {stage}."
                )
            auxiliary["wal"].assert_held_identity_and_size(
                stage=f"{stage}:wal"
            )
            auxiliary["shm"].assert_held_identity_and_size(
                stage=f"{stage}:shm"
            )
        self._auxiliary_terminal_absent = True

    def sqlite_rw_uri(self) -> str:
        if os.name == "nt":
            return f"{self.path.resolve().as_uri()}?mode=rw"
        main = self._files.get("main")
        if main is None or main._fd is None:
            raise ReviewStoreError(
                "Non-Windows reviewability upgrade lacks a held main descriptor."
            )
        for descriptor_root in (Path("/proc/self/fd"), Path("/dev/fd")):
            descriptor_path = descriptor_root / str(main._fd)
            if descriptor_path.exists():
                return f"{descriptor_path.as_uri()}?mode=rw"
        raise ReviewStoreError(
            "Non-Windows reviewability upgrade cannot bind SQLite mode=rw to "
            "the held main descriptor; failing closed."
        )

    def assert_sqlite_main_binding(
        self,
        conn: sqlite3.Connection,
        *,
        stage: str,
    ) -> None:
        main_paths = [
            Path(str(row[2]))
            for row in conn.execute("PRAGMA database_list").fetchall()
            if str(row[1]) == "main" and str(row[2])
        ]
        if len(main_paths) != 1:
            raise ReviewStoreError(
                f"Reviewability SQLite main path drifted at {stage}."
            )
        if os.name == "nt":
            if main_paths[0].resolve(strict=False) != self.path.resolve(strict=False):
                raise ReviewStoreError(
                    f"Reviewability SQLite main path drifted at {stage}."
                )
            return
        main = self._files.get("main")
        if main is None:
            raise ReviewStoreError(
                f"Reviewability held main descriptor is missing at {stage}."
            )
        try:
            reported = main_paths[0].stat()
        except OSError as exc:
            raise ReviewStoreError(
                f"Reviewability SQLite main identity is unreadable at {stage}: {exc}"
            ) from exc
        if (int(reported.st_dev), int(reported.st_ino)) != (
            main._read_handle_state()[:2]
        ):
            raise ReviewStoreError(
                f"Reviewability SQLite main handle drifted at {stage}."
            )

    def close(self) -> None:
        for held in reversed(list(self._files.values())):
            held.close()
        self._files.clear()


_CURRENT_REVIEWABILITY_UPGRADE_GUARD: ContextVar[
    _ReviewabilityUpgradeFileGuard | None
] = ContextVar("current_reviewability_upgrade_guard", default=None)


def _hold_reviewability_upgrade_files(method: Any) -> Any:
    """Acquire no-delete holds before the first immutable upgrade gate."""

    @wraps(method)
    def guarded(self: Any, *args: Any, **kwargs: Any) -> Any:
        if not self.path.is_file():
            raise ReviewStoreError(
                "Reviewability v2 upgrade requires an existing explicit candidate."
            )
        before_main = _stable_file_state(self.path)
        wal_path = Path(f"{self.path}-wal")
        shm_path = Path(f"{self.path}-shm")
        before_wal = _stable_file_state(wal_path)
        before_shm = _stable_file_state(shm_path)
        if before_main is None:
            raise ReviewStoreError(
                "Reviewability candidate disappeared before upgrade."
            )
        auxiliary_unpaired = (before_wal is None) != (before_shm is None)
        auxiliary_invalid = bool(
            before_wal is not None
            and before_shm is not None
            and (
                before_wal[2] != 0
                or before_wal[4] != hashlib.sha256(b"").hexdigest()
                or before_shm[2] != 32768
            )
        )
        if auxiliary_unpaired or auxiliary_invalid:
            raise ReviewStoreError(
                "Reviewability v2 upgrade requires either absent auxiliaries or "
                "a stable zero-WAL and 32768-byte SHM pair."
            )
        try:
            guard = _ReviewabilityUpgradeFileGuard(
                self.path,
                expected_main=before_main,
                expected_wal=before_wal,
                expected_shm=before_shm,
            )
        except ReviewStoreError:
            raise
        except OSError as exc:
            raise ReviewStoreError(
                "Reviewability upgrade no-delete hold could not be proven: "
                f"{exc}"
            ) from exc
        token = _CURRENT_REVIEWABILITY_UPGRADE_GUARD.set(guard)
        try:
            return method(self, *args, **kwargs)
        finally:
            # This is deliberately the final action after exact-v2 validation,
            # DDL comparison and byte-for-byte v1 replay in the wrapped method.
            try:
                _CURRENT_REVIEWABILITY_UPGRADE_GUARD.reset(token)
            finally:
                guard.close()

    return guarded


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS data_sources (
    source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    uri TEXT NOT NULL,
    timezone TEXT NOT NULL,
    read_only INTEGER NOT NULL CHECK (read_only IN (0, 1)),
    config_json TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_config_versions (
    source_id TEXT NOT NULL REFERENCES data_sources(source_id),
    fingerprint TEXT NOT NULL,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (source_id, fingerprint)
);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    market TEXT,
    occurred_at TEXT NOT NULL,
    known_at TEXT NOT NULL,
    status TEXT NOT NULL,
    thesis TEXT NOT NULL,
    trigger_text TEXT,
    invalidation_text TEXT,
    expected_horizon TEXT,
    portfolio_role TEXT,
    direct_reason TEXT,
    risk_notes TEXT,
    raw_note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_runs (
    run_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES data_sources(source_id),
    source_fingerprint TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    seen_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    error_text TEXT,
    manifest_json TEXT NOT NULL,
    FOREIGN KEY (source_id, source_fingerprint)
        REFERENCES source_config_versions(source_id, fingerprint)
);

CREATE TABLE IF NOT EXISTS trade_events (
    event_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES data_sources(source_id),
    source_record_id TEXT,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    known_at TEXT NOT NULL,
    account TEXT,
    market TEXT,
    symbol TEXT NOT NULL,
    side TEXT,
    quantity TEXT,
    price TEXT,
    gross_amount TEXT,
    cash_amount TEXT,
    fees TEXT,
    currency TEXT NOT NULL,
    raw_payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    first_ingest_run_id TEXT REFERENCES ingest_runs(run_id),
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_run_events (
    run_id TEXT NOT NULL REFERENCES ingest_runs(run_id) ON DELETE CASCADE,
    event_id TEXT NOT NULL REFERENCES trade_events(event_id),
    outcome TEXT NOT NULL CHECK (outcome IN ('INSERTED', 'SKIPPED')),
    payload_sha256 TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    PRIMARY KEY (run_id, event_id)
);

CREATE TABLE IF NOT EXISTS decision_event_links (
    decision_id TEXT NOT NULL REFERENCES decisions(decision_id) ON DELETE CASCADE,
    event_id TEXT NOT NULL REFERENCES trade_events(event_id) ON DELETE CASCADE,
    relation TEXT NOT NULL DEFAULT 'execution',
    created_at TEXT NOT NULL,
    PRIMARY KEY (decision_id, event_id, relation)
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    source_id TEXT REFERENCES data_sources(source_id),
    source_record_id TEXT,
    observed_at TEXT NOT NULL,
    known_at TEXT NOT NULL,
    account TEXT,
    nav TEXT,
    cash TEXT,
    gross_exposure TEXT,
    net_exposure TEXT,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS position_snapshot_items (
    snapshot_id TEXT NOT NULL REFERENCES portfolio_snapshots(snapshot_id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    market TEXT,
    quantity TEXT NOT NULL,
    cost_basis TEXT,
    market_price TEXT,
    market_value TEXT,
    currency TEXT NOT NULL DEFAULT 'CNY',
    payload_json TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, symbol, market)
);

CREATE TABLE IF NOT EXISTS behavior_hypothesis_candidates (
    candidate_id TEXT PRIMARY KEY,
    canonical_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    knowledge_at TEXT NOT NULL,
    subject_scope_kind TEXT NOT NULL,
    subject_scope_refs_json TEXT NOT NULL,
    pattern_family TEXT NOT NULL,
    source_verification_status TEXT NOT NULL CHECK (
        source_verification_status = 'verified'
    ),
    payload_json TEXT NOT NULL,
    inserted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS behavior_hypothesis_review_events (
    review_event_id TEXT PRIMARY KEY,
    canonical_hash TEXT NOT NULL UNIQUE,
    candidate_id TEXT NOT NULL REFERENCES behavior_hypothesis_candidates(candidate_id),
    event_type TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    knowledge_at TEXT NOT NULL,
    evidence_cutoff TEXT NOT NULL,
    reviewer_ref TEXT NOT NULL,
    supersedes_event_id TEXT REFERENCES behavior_hypothesis_review_events(review_event_id),
    supersedes_candidate_id TEXT REFERENCES behavior_hypothesis_candidates(candidate_id),
    payload_json TEXT NOT NULL,
    inserted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS behavior_observation_protocols (
    protocol_id TEXT PRIMARY KEY,
    canonical_hash TEXT NOT NULL UNIQUE,
    candidate_id TEXT NOT NULL REFERENCES behavior_hypothesis_candidates(candidate_id),
    created_at TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    knowledge_at TEXT NOT NULL,
    expiry_at TEXT NOT NULL,
    stage1_event_set_hash TEXT NOT NULL,
    stage1_projection_hash TEXT NOT NULL,
    source_verification_status TEXT NOT NULL CHECK (
        source_verification_status = 'verified'
    ),
    payload_json TEXT NOT NULL,
    inserted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS behavior_observation_protocol_review_events (
    protocol_review_event_id TEXT PRIMARY KEY,
    canonical_hash TEXT NOT NULL UNIQUE,
    protocol_id TEXT NOT NULL REFERENCES behavior_observation_protocols(protocol_id),
    event_type TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    knowledge_at TEXT NOT NULL,
    evidence_cutoff TEXT NOT NULL,
    reviewer_ref TEXT NOT NULL,
    supersedes_event_id TEXT REFERENCES behavior_observation_protocol_review_events(
        protocol_review_event_id
    ),
    superseded_by_protocol_id TEXT REFERENCES behavior_observation_protocols(protocol_id),
    payload_json TEXT NOT NULL,
    inserted_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trade_events_symbol_time
    ON trade_events(symbol, occurred_at);
CREATE INDEX IF NOT EXISTS idx_trade_events_known_at
    ON trade_events(known_at);
CREATE INDEX IF NOT EXISTS idx_trade_events_source_record
    ON trade_events(source_id, source_record_id);
CREATE INDEX IF NOT EXISTS idx_ingest_run_events_event
    ON ingest_run_events(event_id, run_id);
CREATE INDEX IF NOT EXISTS idx_decisions_symbol_time
    ON decisions(symbol, occurred_at);
CREATE INDEX IF NOT EXISTS idx_snapshots_observed_at
    ON portfolio_snapshots(observed_at);
CREATE INDEX IF NOT EXISTS idx_behavior_candidates_scope
    ON behavior_hypothesis_candidates(subject_scope_kind, pattern_family);
CREATE INDEX IF NOT EXISTS idx_behavior_candidates_dual_time
    ON behavior_hypothesis_candidates(effective_at, knowledge_at, created_at);
CREATE INDEX IF NOT EXISTS idx_behavior_review_events_candidate_time
    ON behavior_hypothesis_review_events(
        candidate_id, effective_at, knowledge_at, reviewed_at, review_event_id
    );
CREATE INDEX IF NOT EXISTS idx_observation_protocols_candidate_time
    ON behavior_observation_protocols(
        candidate_id, effective_at, knowledge_at, created_at, protocol_id
    );
CREATE INDEX IF NOT EXISTS idx_observation_protocol_events_protocol_time
    ON behavior_observation_protocol_review_events(
        protocol_id, effective_at, knowledge_at, reviewed_at,
        protocol_review_event_id
    );
"""


_PRODUCT_COMPLETION_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS fee_profiles (
    profile_id TEXT PRIMARY KEY,
    profile_key TEXT NOT NULL,
    method TEXT NOT NULL,
    method_version TEXT NOT NULL,
    sample_count INTEGER NOT NULL CHECK (sample_count >= 0),
    rate TEXT,
    currency TEXT NOT NULL,
    fallback_level TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    inserted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fee_projections (
    projection_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES trade_events(event_id),
    status TEXT NOT NULL CHECK (status IN ('actual', 'estimated', 'unknown')),
    amount TEXT,
    currency TEXT NOT NULL,
    source_fees TEXT,
    method TEXT,
    method_version TEXT,
    sample_count INTEGER NOT NULL CHECK (sample_count >= 0),
    profile_id TEXT REFERENCES fee_profiles(profile_id),
    reason_code TEXT,
    projected_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    inserted_at TEXT NOT NULL,
    UNIQUE (event_id, projected_at)
);

CREATE TABLE IF NOT EXISTS fee_corrections (
    correction_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES trade_events(event_id),
    status TEXT NOT NULL CHECK (status IN ('actual', 'unknown')),
    amount TEXT,
    currency TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    known_at TEXT NOT NULL,
    reviewer_ref TEXT NOT NULL,
    reason TEXT NOT NULL,
    supersedes_correction_id TEXT REFERENCES fee_corrections(correction_id),
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    inserted_at TEXT NOT NULL,
    UNIQUE (event_id, effective_at, known_at)
);

CREATE TABLE IF NOT EXISTS review_runs (
    run_id TEXT PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    scope TEXT NOT NULL CHECK (
        scope IN ('sync', 'catch_up', 'single', 'weekly', 'monthly')
    ),
    requested_at TEXT NOT NULL,
    source_cutoff TEXT,
    trigger TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    inserted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_run_status_events (
    run_event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES review_runs(run_id),
    status TEXT NOT NULL CHECK (
        status IN ('queued', 'running', 'succeeded', 'partial', 'blocked', 'failed')
    ),
    occurred_at TEXT NOT NULL,
    known_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    inserted_at TEXT NOT NULL,
    UNIQUE (run_id, occurred_at, known_at)
);

CREATE INDEX IF NOT EXISTS idx_fee_profiles_key_time
    ON fee_profiles(profile_key, computed_at, profile_id);
CREATE INDEX IF NOT EXISTS idx_fee_projections_event_time
    ON fee_projections(event_id, projected_at, projection_id);
CREATE INDEX IF NOT EXISTS idx_fee_corrections_event_time
    ON fee_corrections(event_id, effective_at, known_at, correction_id);
CREATE INDEX IF NOT EXISTS idx_review_runs_scope_time
    ON review_runs(scope, requested_at, run_id);
CREATE INDEX IF NOT EXISTS idx_review_run_events_run_time
    ON review_run_status_events(run_id, occurred_at, known_at, run_event_id);
"""

_REVIEWABILITY_SCHEMA_SQL = """
CREATE TABLE operation_review_checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    checkpoint_key TEXT NOT NULL UNIQUE,
    content_id TEXT NOT NULL UNIQUE,
    episode_id TEXT NOT NULL,
    position_case_id TEXT NOT NULL,
    review_kind TEXT NOT NULL CHECK (
        review_kind IN ('operation_review', 'active_checkpoint', 'postmortem')
    ),
    checkpoint_type TEXT NOT NULL CHECK (
        checkpoint_type IN (
            'entry', 'active_checkpoint', 'adjustment', 'exit', 'postmortem'
        )
    ),
    perspective TEXT NOT NULL CHECK (perspective IN ('user', 'system')),
    as_of TEXT NOT NULL,
    knowledge_cutoff TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    user_known_at TEXT,
    system_observed_at TEXT,
    recorded_at TEXT NOT NULL,
    operation_status TEXT NOT NULL CHECK (
        operation_status IN ('ready', 'partial', 'blocked')
    ),
    decision_status TEXT NOT NULL CHECK (
        decision_status IN (
            'complete', 'partial', 'not_recorded', 'not_applicable', 'blocked'
        )
    ),
    snapshot_status TEXT NOT NULL CHECK (
        snapshot_status IN ('available', 'partial', 'missing', 'blocked')
    ),
    market_status TEXT NOT NULL CHECK (
        market_status IN (
            'available', 'partial', 'missing', 'stale', 'insufficient',
            'failed', 'withheld'
        )
    ),
    lifecycle_status TEXT NOT NULL CHECK (
        lifecycle_status IN ('open', 'closed', 'ambiguous', 'unknown')
    ),
    outcome_status TEXT NOT NULL CHECK (
        outcome_status IN ('interim', 'final', 'not_applicable', 'missing')
    ),
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    inserted_at TEXT NOT NULL,
    row_integrity_sha256 TEXT NOT NULL,
    UNIQUE (
        episode_id, review_kind, checkpoint_type, perspective, as_of,
        knowledge_cutoff
    )
);

CREATE TABLE operation_checkpoint_gaps (
    checkpoint_id TEXT NOT NULL REFERENCES operation_review_checkpoints(
        checkpoint_id
    ) ON DELETE CASCADE,
    gap_id TEXT NOT NULL,
    axis TEXT NOT NULL CHECK (
        axis IN (
            'operation', 'decision', 'snapshot_cash_valuation', 'market',
            'lifecycle', 'outcome'
        )
    ),
    code TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (
        severity IN ('info', 'warning', 'blocker')
    ),
    blocks_axis INTEGER NOT NULL CHECK (blocks_axis IN (0, 1)),
    owner TEXT NOT NULL,
    next_step TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (checkpoint_id, gap_id)
);

CREATE INDEX idx_operation_checkpoints_case_time
    ON operation_review_checkpoints(
        position_case_id, as_of, knowledge_cutoff, checkpoint_id
    );
CREATE INDEX idx_operation_checkpoints_episode_time
    ON operation_review_checkpoints(
        episode_id, as_of, knowledge_cutoff, checkpoint_id
    );
CREATE INDEX idx_operation_checkpoint_gaps_axis
    ON operation_checkpoint_gaps(axis, severity, checkpoint_id, gap_id);
"""

_CORE_TABLES = frozenset(
    {
        "schema_meta",
        "data_sources",
        "source_config_versions",
        "decisions",
        "ingest_runs",
        "trade_events",
        "ingest_run_events",
        "decision_event_links",
        "portfolio_snapshots",
        "position_snapshot_items",
        "behavior_hypothesis_candidates",
        "behavior_hypothesis_review_events",
        "behavior_observation_protocols",
        "behavior_observation_protocol_review_events",
    }
)

_CORE_INDEXES = frozenset(
    {
        "idx_trade_events_symbol_time",
        "idx_trade_events_known_at",
        "idx_trade_events_source_record",
        "idx_ingest_run_events_event",
        "idx_decisions_symbol_time",
        "idx_snapshots_observed_at",
        "idx_behavior_candidates_scope",
        "idx_behavior_candidates_dual_time",
        "idx_behavior_review_events_candidate_time",
        "idx_observation_protocols_candidate_time",
        "idx_observation_protocol_events_protocol_time",
    }
)

_PRODUCT_COMPLETION_TABLES = frozenset(
    {
        "fee_profiles",
        "fee_projections",
        "fee_corrections",
        "review_runs",
        "review_run_status_events",
    }
)

_PRODUCT_COMPLETION_INDEXES = frozenset(
    {
        "idx_fee_profiles_key_time",
        "idx_fee_projections_event_time",
        "idx_fee_corrections_event_time",
        "idx_review_runs_scope_time",
        "idx_review_run_events_run_time",
    }
)

_REVIEWABILITY_TABLES = frozenset(
    {
        "operation_review_checkpoints",
        "operation_checkpoint_gaps",
    }
)

_REVIEWABILITY_INDEXES = frozenset(
    {
        "idx_operation_checkpoints_case_time",
        "idx_operation_checkpoints_episode_time",
        "idx_operation_checkpoint_gaps_axis",
    }
)
_REVIEWABILITY_FOUNDATION_TABLES = (
    _CORE_TABLES | _PRODUCT_COMPLETION_TABLES | _REVIEWABILITY_TABLES
)
_REVIEWABILITY_FOUNDATION_INDEXES = (
    _CORE_INDEXES | _PRODUCT_COMPLETION_INDEXES | _REVIEWABILITY_INDEXES
)

def _normalized_schema_sql(value: object) -> str | None:
    """Normalize formatting without discarding any SQLite constraint text."""

    if value is None:
        return None
    return " ".join(str(value).strip().split())


def _pragma_manifest_rows(
    conn: sqlite3.Connection,
    pragma: str,
    object_name: str,
) -> list[dict[str, Any]]:
    cursor = conn.execute(f'PRAGMA {pragma}("{object_name}")')
    column_names = tuple(item[0] for item in cursor.description or ())
    return [
        {
            name: row[name] if isinstance(row, sqlite3.Row) else row[index]
            for index, name in enumerate(column_names)
        }
        for row in cursor.fetchall()
    ]


def _reviewability_schema_manifest(
    conn: sqlite3.Connection,
    *,
    reviewability_schema_version: int = REVIEWABILITY_SCHEMA_VERSION_V1,
) -> dict[str, Any]:
    """Describe the common DDL plus the selected closed semantic contract.

    Reviewability v2 deliberately reuses the exact v1 SQLite objects.  The
    manifest nevertheless binds the semantic feature markers so a marker-only
    upgrade cannot silently reinterpret either contract.
    """

    if reviewability_schema_version == REVIEWABILITY_SCHEMA_VERSION_V1:
        checkpoint_contract_version = OPERATION_CHECKPOINT_SCHEMA_VERSION
        market_policy_version = MARKET_FALLBACK_POLICY_VERSION
        public_information_policy_version: str | None = None
    elif reviewability_schema_version == REVIEWABILITY_SCHEMA_VERSION_V2:
        checkpoint_contract_version = OPERATION_CHECKPOINT_SCHEMA_VERSION_V2
        market_policy_version = MARKET_FALLBACK_POLICY_VERSION_V2
        public_information_policy_version = PUBLIC_INFORMATION_POLICY_VERSION
    else:
        raise ValueError(
            "Unsupported reviewability schema version for manifest: "
            f"{reviewability_schema_version}"
        )

    object_rows = conn.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE type IN ('table', 'index', 'trigger', 'view') "
        "AND name NOT LIKE 'sqlite_%' "
        "ORDER BY type, name"
    ).fetchall()
    objects = [
        {
            "type": str(row["type"]),
            "name": str(row["name"]),
            "tbl_name": str(row["tbl_name"]),
            "sql": _normalized_schema_sql(row["sql"]),
        }
        for row in object_rows
    ]
    table_names = sorted(
        str(row["name"]) for row in object_rows if row["type"] == "table"
    )
    if set(table_names) != set(_REVIEWABILITY_FOUNDATION_TABLES):
        raise ValueError(
            "Reviewability foundation contains missing or unexpected tables"
        )

    tables: dict[str, Any] = {}
    for table_name in table_names:
        table_row = next(
            row
            for row in object_rows
            if row["type"] == "table" and row["name"] == table_name
        )
        index_entries: list[dict[str, Any]] = []
        index_list = _pragma_manifest_rows(conn, "index_list", table_name)
        for index_row in sorted(index_list, key=lambda item: str(item["name"])):
            index_name = str(index_row["name"])
            schema_row = conn.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_master "
                "WHERE type = 'index' AND name = ?",
                (index_name,),
            ).fetchone()
            if schema_row is None:
                raise ValueError(f"Missing SQLite index metadata: {index_name}")
            index_entries.append(
                {
                    "index_list": index_row,
                    "sqlite_master": {
                        "type": str(schema_row["type"]),
                        "name": str(schema_row["name"]),
                        "tbl_name": str(schema_row["tbl_name"]),
                        "sql": _normalized_schema_sql(schema_row["sql"]),
                    },
                    "index_xinfo": sorted(
                        _pragma_manifest_rows(conn, "index_xinfo", index_name),
                        key=lambda item: int(item["seqno"]),
                    ),
                }
            )

        tables[table_name] = {
            "sqlite_master": {
                "type": str(table_row["type"]),
                "name": str(table_row["name"]),
                "tbl_name": str(table_row["tbl_name"]),
                "sql": _normalized_schema_sql(table_row["sql"]),
            },
            "table_xinfo": sorted(
                _pragma_manifest_rows(conn, "table_xinfo", table_name),
                key=lambda item: int(item["cid"]),
            ),
            "foreign_key_list": sorted(
                _pragma_manifest_rows(conn, "foreign_key_list", table_name),
                key=lambda item: (int(item["id"]), int(item["seq"])),
            ),
            "indexes": index_entries,
        }

    result = {
        "schema_version": reviewability_schema_version,
        "checkpoint_contract_version": checkpoint_contract_version,
        "market_policy_version": market_policy_version,
        "market_provider_allowlist_version": MARKET_PROVIDER_ALLOWLIST_VERSION,
        "market_provider_allowlist_sha256": MARKET_PROVIDER_ALLOWLIST_SHA256,
        "required_explicit_indexes": sorted(_REVIEWABILITY_FOUNDATION_INDEXES),
        "objects": objects,
        "tables": tables,
    }
    if public_information_policy_version is not None:
        result["public_information_policy_version"] = (
            public_information_policy_version
        )
    return result


def _expected_reviewability_schema_manifest(
    *, reviewability_schema_version: int = REVIEWABILITY_SCHEMA_VERSION_V1
) -> dict[str, Any]:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.executescript(
            _SCHEMA_SQL
            + "\n"
            + _PRODUCT_COMPLETION_SCHEMA_SQL
            + "\n"
            + _REVIEWABILITY_SCHEMA_SQL
        )
        return _reviewability_schema_manifest(
            conn,
            reviewability_schema_version=reviewability_schema_version,
        )
    finally:
        conn.close()


_REVIEWABILITY_SCHEMA_MANIFEST = _expected_reviewability_schema_manifest(
    reviewability_schema_version=REVIEWABILITY_SCHEMA_VERSION_V1
)
_COMPUTED_REVIEWABILITY_SCHEMA_MANIFEST_SHA256 = sha256_text(
    canonical_json(_REVIEWABILITY_SCHEMA_MANIFEST)
)
REVIEWABILITY_SCHEMA_MANIFEST_SHA256 = (
    "e1241c55fe615a0389b9f7ee2c8d0e7071d7c45487800d67b00d29f53dcceab0"
)
if (
    _COMPUTED_REVIEWABILITY_SCHEMA_MANIFEST_SHA256
    != REVIEWABILITY_SCHEMA_MANIFEST_SHA256
):
    raise RuntimeError(
        "reviewability_schema_version=1 DDL changed without a version/hash update: "
        f"{_COMPUTED_REVIEWABILITY_SCHEMA_MANIFEST_SHA256}"
    )

_REVIEWABILITY_SCHEMA_MANIFEST_V2 = _expected_reviewability_schema_manifest(
    reviewability_schema_version=REVIEWABILITY_SCHEMA_VERSION_V2
)
_COMPUTED_REVIEWABILITY_SCHEMA_MANIFEST_SHA256_V2 = sha256_text(
    canonical_json(_REVIEWABILITY_SCHEMA_MANIFEST_V2)
)
# This constant is intentionally populated from the reviewed deterministic
# manifest below.  Import-time equality makes any later DDL/metadata drift fail
# closed before a candidate can be opened writable.
REVIEWABILITY_SCHEMA_MANIFEST_SHA256_V2 = (
    "352a9abff69da24e50bc0add0f0dcd802f500463b41cc826f6a140a02f2a4094"
)
if (
    _COMPUTED_REVIEWABILITY_SCHEMA_MANIFEST_SHA256_V2
    != REVIEWABILITY_SCHEMA_MANIFEST_SHA256_V2
):
    raise RuntimeError(
        "reviewability_schema_version=2 contract metadata or DDL changed without "
        "a version/hash update: "
        f"{_COMPUTED_REVIEWABILITY_SCHEMA_MANIFEST_SHA256_V2}"
    )


class ReviewStore:
    def __init__(
        self,
        path: str | Path = "data/db/investment_review.sqlite3",
        *,
        immutable_reads: bool = False,
        allow_writes: bool = True,
    ) -> None:
        self.path = Path(path)
        inherited_immutable = (
            _immutable_context_path(self.path)
            in _IMMUTABLE_READ_CONTEXT_PATHS.get()
        )
        self.immutable_reads = bool(immutable_reads or inherited_immutable)
        self.allow_writes = bool(allow_writes and not inherited_immutable)

    def _connect(self, *, read_only: bool = False) -> sqlite3.Connection:
        if read_only:
            if not self.path.exists():
                raise FileNotFoundError(self.path)
            query = "mode=ro&immutable=1" if self.immutable_reads else "mode=ro"
            uri = f"{self.path.resolve().as_uri()}?{query}"
            conn = sqlite3.connect(uri, uri=True)
            if self.immutable_reads:
                conn.execute("PRAGMA query_only = ON")
        else:
            if not self.allow_writes:
                raise ReviewStoreError(
                    "review store is locked to immutable read-only acceptance mode"
                )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    @contextmanager
    def connection(self, *, read_only: bool = False) -> Iterator[sqlite3.Connection]:
        conn = self._connect(read_only=read_only)
        try:
            yield conn
        finally:
            conn.close()

    def initialize(self) -> dict[str, Any]:
        if not self.allow_writes:
            raise ReviewStoreError(
                "review store is locked to immutable read-only acceptance mode"
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            application_id = conn.execute("PRAGMA application_id").fetchone()[0]
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            }
            if tables and application_id != APPLICATION_ID:
                raise ReviewStoreError(
                    "Refusing to initialize an unmarked or legacy SQLite database: "
                    f"{self.path}. Create a new v{SCHEMA_VERSION} sidecar and reimport; "
                    "automatic legacy migration cannot reconstruct event-run lineage."
                )
            if not tables and application_id not in (0, APPLICATION_ID):
                raise ReviewStoreError(
                    f"Unexpected SQLite application_id for review database: {application_id}"
                )
            if tables:
                version_row = conn.execute(
                    "SELECT value FROM schema_meta WHERE key='schema_version'"
                ).fetchone() if "schema_meta" in tables else None
                schema_version = int(version_row[0]) if version_row else None
                user_version = conn.execute("PRAGMA user_version").fetchone()[0]
                if schema_version != SCHEMA_VERSION or user_version != SCHEMA_VERSION:
                    raise ReviewStoreError(
                        f"Review database is legacy or inconsistent "
                        f"(schema_version={schema_version}, user_version={user_version}). "
                        f"Create a new v{SCHEMA_VERSION} sidecar and reimport."
                    )
                feature_row = conn.execute(
                    "SELECT value FROM schema_meta "
                    "WHERE key='p2h_stage1_schema_version'"
                ).fetchone()
                if (
                    feature_row is not None
                    and int(feature_row[0]) != P2H_STAGE1_SCHEMA_VERSION
                ):
                    raise ReviewStoreError(
                        "Unsupported P2H Stage 1 feature schema: "
                        f"{feature_row[0]}"
                    )
                stage2_row = conn.execute(
                    "SELECT value FROM schema_meta "
                    "WHERE key='p2h_stage2_slice_a_schema_version'"
                ).fetchone()
                if (
                    stage2_row is not None
                    and int(stage2_row[0]) != P2H_STAGE2_SLICE_A_SCHEMA_VERSION
                ):
                    raise ReviewStoreError(
                        "Unsupported P2H Stage 2 Slice A feature schema: "
                        f"{stage2_row[0]}"
                    )
                indexes = {
                    str(row[0])
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='index' AND name NOT LIKE 'sqlite_%'"
                    ).fetchall()
                }
                journal_mode = str(
                    conn.execute("PRAGMA journal_mode").fetchone()[0]
                ).lower()
                if (
                    _CORE_TABLES.issubset(tables)
                    and _CORE_INDEXES.issubset(indexes)
                    and feature_row is not None
                    and int(feature_row[0]) == P2H_STAGE1_SCHEMA_VERSION
                    and stage2_row is not None
                    and int(stage2_row[0]) == P2H_STAGE2_SLICE_A_SCHEMA_VERSION
                    and journal_mode == "wal"
                ):
                    return {"database": str(self.path), "schema_version": SCHEMA_VERSION}
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(_SCHEMA_SQL)

            now = _now()
            conn.execute(f"PRAGMA application_id = {APPLICATION_ID}")
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            conn.execute(
                "INSERT INTO schema_meta(key, value) VALUES('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(SCHEMA_VERSION),),
            )
            conn.execute(
                "INSERT INTO schema_meta(key, value) VALUES('initialized_at', ?) "
                "ON CONFLICT(key) DO NOTHING",
                (now,),
            )
            conn.execute(
                "INSERT INTO schema_meta(key, value) "
                "VALUES('p2h_stage1_schema_version', ?) "
                "ON CONFLICT(key) DO NOTHING",
                (str(P2H_STAGE1_SCHEMA_VERSION),),
            )
            conn.execute(
                "INSERT INTO schema_meta(key, value) "
                "VALUES('p2h_stage2_slice_a_schema_version', ?) "
                "ON CONFLICT(key) DO NOTHING",
                (str(P2H_STAGE2_SLICE_A_SCHEMA_VERSION),),
            )
            conn.commit()
        finally:
            conn.close()
        return {"database": str(self.path), "schema_version": SCHEMA_VERSION}

    def initialize_product_completion(self) -> dict[str, Any]:
        """Explicitly opt an initialized v2 candidate into additive product tables.

        Core ``initialize`` intentionally never enables this feature. Callers must
        select the candidate sidecar first and then invoke this method explicitly;
        legacy v1 stores remain rejected by the normal v2 boundary.
        """

        self._ensure_initialized()
        with self.connection() as conn:
            feature_row = conn.execute(
                "SELECT value FROM schema_meta "
                "WHERE key='product_completion_schema_version'"
            ).fetchone()
            if (
                feature_row is not None
                and int(feature_row[0]) != PRODUCT_COMPLETION_SCHEMA_VERSION
            ):
                raise ReviewStoreError(
                    "Unsupported product-completion feature schema: "
                    f"{feature_row[0]}"
                )
            tables = {
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            indexes = {
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='index' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            }
            if feature_row is not None:
                if not _PRODUCT_COMPLETION_TABLES.issubset(tables) or not (
                    _PRODUCT_COMPLETION_INDEXES.issubset(indexes)
                ):
                    raise ReviewStoreError(
                        "Product-completion feature marker exists but its additive "
                        "schema is incomplete; refusing silent repair."
                    )
                return {
                    "database": str(self.path),
                    "schema_version": SCHEMA_VERSION,
                    "product_completion_schema_version": (
                        PRODUCT_COMPLETION_SCHEMA_VERSION
                    ),
                }
            if _PRODUCT_COMPLETION_TABLES.intersection(tables):
                raise ReviewStoreError(
                    "Unmarked product-completion tables already exist; refusing "
                    "to adopt or modify them."
                )
            marker_sql = (
                "INSERT INTO schema_meta(key, value) "
                "VALUES('product_completion_schema_version', "
                f"'{PRODUCT_COMPLETION_SCHEMA_VERSION}') "
                "ON CONFLICT(key) DO NOTHING;"
            )
            try:
                conn.executescript(
                    "BEGIN IMMEDIATE;\n"
                    + _PRODUCT_COMPLETION_SCHEMA_SQL
                    + "\n"
                    + marker_sql
                    + "\nCOMMIT;"
                )
            except Exception:
                if conn.in_transaction:
                    conn.rollback()
                raise
        return {
            "database": str(self.path),
            "schema_version": SCHEMA_VERSION,
            "product_completion_schema_version": PRODUCT_COMPLETION_SCHEMA_VERSION,
        }

    def initialize_reviewability_candidate(self) -> dict[str, Any]:
        """Create or verify a new, explicitly selected v3 candidate sidecar.

        Existing core/product sidecars without the v3 marker are inspected through
        ``mode=ro`` and refused before any writable connection is opened.  This is
        deliberately stricter than ``initialize_product_completion``: user and v2
        candidate sidecars must never be upgraded into reviewability candidates.
        """

        if self.path.exists():
            return self._validate_existing_reviewability_candidate()

        self.path.parent.mkdir(parents=True, exist_ok=True)
        create_flags = os.O_CREAT | os.O_EXCL | os.O_RDWR
        if hasattr(os, "O_BINARY"):
            create_flags |= os.O_BINARY
        owned_fd: int | None = None
        conn: sqlite3.Connection | None = None
        try:
            owned_fd = os.open(self.path, create_flags, 0o600)
        except FileExistsError:
            # Another actor won the creation race.  The path is now "existing" and
            # therefore may only pass through the same immutable read-only gate.
            return self._validate_existing_reviewability_candidate()

        owned_stat = os.fstat(owned_fd)

        def require_owned_path() -> None:
            try:
                current_stat = os.stat(self.path)
            except OSError as exc:
                raise ReviewStoreError(
                    "New reviewability candidate path disappeared during initialization."
                ) from exc
            if not os.path.samestat(owned_stat, current_stat):
                raise ReviewStoreError(
                    "New reviewability candidate path identity changed during initialization."
                )

        try:
            require_owned_path()
            uri = f"{self.path.resolve().as_uri()}?mode=rw"
            conn = sqlite3.connect(uri, uri=True)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            require_owned_path()
            application_id = int(conn.execute("PRAGMA application_id").fetchone()[0])
            tables = {
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            }
            if tables or application_id not in (0, APPLICATION_ID):
                raise ReviewStoreError(
                    "Reviewability candidate initialization requires a new or empty "
                    "explicit path."
                )
            journal_mode = str(
                conn.execute("PRAGMA journal_mode = WAL").fetchone()[0]
            ).lower()
            if journal_mode != "wal":
                raise ReviewStoreError(
                    "New reviewability candidate could not enable WAL journal mode."
                )
            require_owned_path()
            initialized_at = _now()
            marker_sql = f"""
INSERT INTO schema_meta(key, value)
VALUES('schema_version', '{SCHEMA_VERSION}');
INSERT INTO schema_meta(key, value)
VALUES('initialized_at', '{initialized_at}');
INSERT INTO schema_meta(key, value)
VALUES('p2h_stage1_schema_version', '{P2H_STAGE1_SCHEMA_VERSION}');
INSERT INTO schema_meta(key, value)
VALUES('p2h_stage2_slice_a_schema_version', '{P2H_STAGE2_SLICE_A_SCHEMA_VERSION}');
INSERT INTO schema_meta(key, value)
VALUES('product_completion_schema_version', '{PRODUCT_COMPLETION_SCHEMA_VERSION}');
INSERT INTO schema_meta(key, value)
VALUES('reviewability_schema_version', '{REVIEWABILITY_SCHEMA_VERSION}');
INSERT INTO schema_meta(key, value)
VALUES(
    'reviewability_checkpoint_contract_version',
    '{OPERATION_CHECKPOINT_SCHEMA_VERSION}'
);
INSERT INTO schema_meta(key, value)
VALUES(
    'reviewability_market_policy_version',
    '{MARKET_FALLBACK_POLICY_VERSION}'
);
INSERT INTO schema_meta(key, value)
VALUES(
    'reviewability_market_provider_allowlist_version',
    '{MARKET_PROVIDER_ALLOWLIST_VERSION}'
);
INSERT INTO schema_meta(key, value)
VALUES(
    'reviewability_market_provider_allowlist_sha256',
    '{MARKET_PROVIDER_ALLOWLIST_SHA256}'
);
INSERT INTO schema_meta(key, value)
VALUES(
    'reviewability_schema_manifest_sha256',
    '{REVIEWABILITY_SCHEMA_MANIFEST_SHA256}'
);
"""
            conn.executescript(
                "BEGIN IMMEDIATE;\n"
                + _SCHEMA_SQL
                + "\n"
                + _PRODUCT_COMPLETION_SCHEMA_SQL
                + "\n"
                + _REVIEWABILITY_SCHEMA_SQL
                + "\n"
                + marker_sql
                + f"\nPRAGMA application_id = {APPLICATION_ID};"
                + f"\nPRAGMA user_version = {SCHEMA_VERSION};"
                + "\nCOMMIT;"
            )
            require_owned_path()
            self._validate_reviewability_candidate(
                conn, expected_version=REVIEWABILITY_SCHEMA_VERSION_V1
            )
            require_owned_path()
        except Exception:
            if conn is not None and conn.in_transaction:
                conn.rollback()
            raise
        finally:
            if conn is not None:
                conn.close()
            os.close(owned_fd)
        return self._reviewability_init_result(REVIEWABILITY_SCHEMA_VERSION_V1)

    def _validate_existing_reviewability_candidate(
        self,
        *,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        conn: sqlite3.Connection | None = None
        validated_version: int | None = None
        wal_path = Path(f"{self.path}-wal")
        shm_path = Path(f"{self.path}-shm")
        try:
            wal_before = _stable_file_state(wal_path)
            shm_before = _stable_file_state(shm_path)
            if (
                (wal_before is not None and wal_before[2] > 0)
                or (shm_before is not None and wal_before is None)
            ):
                raise ReviewStoreError(
                    "Existing reviewability candidate has a nonempty WAL or "
                    "unpaired SHM; refusing immutable validation."
                )
            before_stat = self.path.stat()
            before_sha256 = _sha256_file(self.path)
            uri = f"{self.path.resolve().as_uri()}?mode=ro&immutable=1"
            conn = sqlite3.connect(uri, uri=True)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only = ON")
            validated_version = self._validate_reviewability_candidate(
                conn, expected_version=expected_version
            )
            after_stat = self.path.stat()
            after_sha256 = _sha256_file(self.path)
            wal_after = _stable_file_state(wal_path)
            shm_after = _stable_file_state(shm_path)
            if (
                (wal_after is not None and wal_after[2] > 0)
                or wal_after != wal_before
                or shm_after != shm_before
                or not os.path.samestat(before_stat, after_stat)
                or before_stat.st_size != after_stat.st_size
                or before_stat.st_mtime_ns != after_stat.st_mtime_ns
                or before_sha256 != after_sha256
            ):
                raise ReviewStoreError(
                    "Existing reviewability candidate changed during immutable "
                    "validation."
                )
        except (
            ReviewStoreError,
            sqlite3.DatabaseError,
            OSError,
            TypeError,
            ValueError,
        ) as exc:
            raise ReviewStoreError(
                "Existing database is not a complete reviewability candidate; "
                f"refusing silent upgrade or repair. Cause: {exc}"
            ) from exc
        finally:
            if conn is not None:
                conn.close()
        if validated_version is None:
            raise ReviewStoreError(
                "Existing reviewability candidate version was not proven."
            )
        return self._reviewability_init_result(validated_version)

    def _reviewability_init_result(self, reviewability_version: int) -> dict[str, Any]:
        if reviewability_version == REVIEWABILITY_SCHEMA_VERSION_V1:
            checkpoint_version = OPERATION_CHECKPOINT_SCHEMA_VERSION
            market_policy_version = MARKET_FALLBACK_POLICY_VERSION
            public_information_policy_version: str | None = None
            manifest_sha256 = REVIEWABILITY_SCHEMA_MANIFEST_SHA256
        elif reviewability_version == REVIEWABILITY_SCHEMA_VERSION_V2:
            checkpoint_version = OPERATION_CHECKPOINT_SCHEMA_VERSION_V2
            market_policy_version = MARKET_FALLBACK_POLICY_VERSION_V2
            public_information_policy_version = PUBLIC_INFORMATION_POLICY_VERSION
            manifest_sha256 = REVIEWABILITY_SCHEMA_MANIFEST_SHA256_V2
        else:
            raise ReviewStoreError(
                f"Unsupported reviewability schema version: {reviewability_version}"
            )
        result = {
            "database": str(self.path),
            "schema_version": SCHEMA_VERSION,
            "product_completion_schema_version": PRODUCT_COMPLETION_SCHEMA_VERSION,
            "reviewability_schema_version": reviewability_version,
            "checkpoint_contract_version": checkpoint_version,
            "market_policy_version": market_policy_version,
            "market_provider_allowlist_version": MARKET_PROVIDER_ALLOWLIST_VERSION,
            "market_provider_allowlist_sha256": MARKET_PROVIDER_ALLOWLIST_SHA256,
            "schema_manifest_sha256": manifest_sha256,
        }
        if public_information_policy_version is not None:
            result["public_information_policy_version"] = (
                public_information_policy_version
            )
        return result

    @staticmethod
    def _reviewability_ddl_fingerprint(conn: sqlite3.Connection) -> str:
        manifest = _reviewability_schema_manifest(
            conn,
            reviewability_schema_version=REVIEWABILITY_SCHEMA_VERSION_V1,
        )
        return sha256_text(
            canonical_json(
                {
                    "required_explicit_indexes": manifest[
                        "required_explicit_indexes"
                    ],
                    "objects": manifest["objects"],
                    "tables": manifest["tables"],
                }
            )
        )

    @staticmethod
    def _assert_reviewability_upgrade_path_state(
        path: Path,
        *,
        expected_main: tuple[int, int, int, int, str],
        expected_wal: tuple[int, int, int, int, str] | None,
        expected_shm: tuple[int, int, int, int, str] | None,
        stage: str,
        lock_active: bool = False,
        conn: sqlite3.Connection | None = None,
        upgrade_guard: _ReviewabilityUpgradeFileGuard | None = None,
    ) -> None:
        """Fail closed on candidate replacement or pre-upgrade file drift.

        A Windows WAL write lock makes the SHM bytes unreadable and may create
        an empty WAL/SHM pair.  While that lock is active, preserve the exact
        main-file state, require a zero-byte WAL, and compare SHM filesystem
        identity/size.  Before the lock, all three stable content snapshots
        must match byte-for-byte.
        """

        try:
            if upgrade_guard is not None:
                upgrade_guard.assert_current(stage=stage)
            current_main = _stable_file_state(path)
            wal_path = Path(f"{path}-wal")
            shm_path = Path(f"{path}-shm")
            if current_main != expected_main:
                raise ReviewStoreError(
                    f"Reviewability candidate main identity changed at {stage}."
                )
            if conn is not None:
                if upgrade_guard is not None:
                    upgrade_guard.assert_sqlite_main_binding(conn, stage=stage)
                else:
                    main_paths = [
                        Path(str(row[2])).resolve(strict=False)
                        for row in conn.execute("PRAGMA database_list").fetchall()
                        if str(row[1]) == "main" and str(row[2])
                    ]
                    if main_paths != [path.resolve(strict=False)]:
                        raise ReviewStoreError(
                            f"Reviewability SQLite main path drifted at {stage}."
                        )
            if not lock_active:
                if (
                    _stable_file_state(wal_path) != expected_wal
                    or _stable_file_state(shm_path) != expected_shm
                ):
                    raise ReviewStoreError(
                        f"Reviewability WAL/SHM state changed at {stage}."
                    )
                return

            current_wal = _stable_file_state(wal_path)
            if current_wal is not None and (
                current_wal[2] != 0
                or current_wal[4]
                != hashlib.sha256(b"").hexdigest()
            ):
                raise ReviewStoreError(
                    f"Reviewability WAL gained content before marker writes at {stage}."
                )
            if expected_wal is not None and current_wal is not None and (
                current_wal[:3] != expected_wal[:3]
            ):
                raise ReviewStoreError(
                    f"Reviewability WAL identity changed at {stage}."
                )
            if expected_wal is not None and current_wal is None:
                raise ReviewStoreError(
                    f"Reviewability WAL disappeared at {stage}."
                )

            if shm_path.exists():
                shm_stat = shm_path.stat()
                current_shm_identity = (
                    int(shm_stat.st_dev),
                    int(shm_stat.st_ino),
                    int(shm_stat.st_size),
                )
                if expected_shm is not None:
                    if current_shm_identity != expected_shm[:3]:
                        raise ReviewStoreError(
                            f"Reviewability SHM identity changed at {stage}."
                        )
                elif current_shm_identity[2] != 32768:
                    raise ReviewStoreError(
                        f"Reviewability lock-created SHM size is invalid at {stage}."
                    )
            elif expected_shm is not None:
                raise ReviewStoreError(
                    f"Reviewability SHM disappeared at {stage}."
                )
        except ReviewStoreError:
            raise
        except (OSError, sqlite3.DatabaseError) as exc:
            raise ReviewStoreError(
                f"Reviewability candidate state could not be proven at {stage}: {exc}"
            ) from exc

    @staticmethod
    def _assert_reviewability_upgrade_held_state(
        path: Path,
        *,
        upgrade_guard: _ReviewabilityUpgradeFileGuard,
        stage: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        """Rebind path and held identities after legitimate marker writes."""

        try:
            upgrade_guard.assert_current(stage=stage)
            if conn is not None:
                upgrade_guard.assert_sqlite_main_binding(conn, stage=stage)
        except ReviewStoreError:
            raise
        except (OSError, sqlite3.DatabaseError) as exc:
            raise ReviewStoreError(
                "Reviewability held upgrade identity could not be proven at "
                f"{stage}: {exc}"
            ) from exc

    @staticmethod
    def _update_exact_marker(
        conn: sqlite3.Connection,
        *,
        key: str,
        expected: str,
        replacement: str,
    ) -> None:
        cursor = conn.execute(
            "UPDATE schema_meta SET value = ? WHERE key = ? AND value = ?",
            (replacement, key, expected),
        )
        if cursor.rowcount != 1:
            raise ReviewStoreError(
                "Reviewability marker upgrade precondition failed for " f"{key}."
            )

    @_hold_reviewability_upgrade_files
    def upgrade_reviewability_candidate_v2(self) -> dict[str, Any]:
        """Explicitly upgrade one exact v1 candidate to v2 without any DDL.

        This is intentionally not called by any initializer.  The caller must
        select the candidate path explicitly.  Every precondition is rechecked
        under the same ``BEGIN IMMEDIATE`` transaction that changes the five
        semantic markers, and every pre-existing v1 checkpoint is replayed
        before and after the marker change.
        """

        _upgrade_guard = _CURRENT_REVIEWABILITY_UPGRADE_GUARD.get()
        if _upgrade_guard is None:
            raise ReviewStoreError("Reviewability upgrade file guard is missing.")
        before_main = _upgrade_guard.expected_main
        before_wal = _upgrade_guard.expected_wal
        before_shm = _upgrade_guard.expected_shm

        # Immutable validation proves that this is an exact v1 candidate before
        # any writable SQLite handle is opened.
        self._validate_existing_reviewability_candidate(
            expected_version=REVIEWABILITY_SCHEMA_VERSION_V1
        )
        immutable_uri = f"{self.path.resolve().as_uri()}?mode=ro&immutable=1"
        immutable_conn = sqlite3.connect(immutable_uri, uri=True)
        immutable_conn.row_factory = sqlite3.Row
        immutable_conn.execute("PRAGMA query_only = ON")
        try:
            self._validate_reviewability_candidate(
                immutable_conn, expected_version=REVIEWABILITY_SCHEMA_VERSION_V1
            )
            immutable_records = self._read_validated_operation_checkpoints(
                immutable_conn
            )
            if any(
                record.to_dict()["schema_version"]
                != OPERATION_CHECKPOINT_SCHEMA_VERSION
                for record in immutable_records
            ):
                raise ReviewStoreError(
                    "Exact v1 upgrade precondition rejects non-v1 checkpoint rows."
                )
            before_checkpoint_bytes = [
                record.canonical_bytes for record in immutable_records
            ]
            before_ddl_sha256 = self._reviewability_ddl_fingerprint(immutable_conn)
        finally:
            immutable_conn.close()

        self._assert_reviewability_upgrade_path_state(
            self.path,
            expected_main=before_main,
            expected_wal=before_wal,
            expected_shm=before_shm,
            stage="after_immutable_validation",
            upgrade_guard=_upgrade_guard,
        )
        self._assert_reviewability_upgrade_path_state(
            self.path,
            expected_main=before_main,
            expected_wal=before_wal,
            expected_shm=before_shm,
            stage="before_rw_open",
            upgrade_guard=_upgrade_guard,
        )

        uri = _upgrade_guard.sqlite_rw_uri()
        conn = sqlite3.connect(uri, uri=True)
        committed = False
        checkpoint_complete = False
        try:
            _upgrade_guard.note_writer_open(conn, stage="after_rw_open")
            self._assert_reviewability_upgrade_path_state(
                self.path,
                expected_main=before_main,
                expected_wal=before_wal,
                expected_shm=before_shm,
                stage="after_rw_open",
                conn=conn,
                upgrade_guard=_upgrade_guard,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 5000")
            self._assert_reviewability_upgrade_path_state(
                self.path,
                expected_main=before_main,
                expected_wal=before_wal,
                expected_shm=before_shm,
                stage="after_rw_pragmas",
                conn=conn,
                upgrade_guard=_upgrade_guard,
            )
            conn.execute("BEGIN IMMEDIATE")
            self._assert_reviewability_upgrade_path_state(
                self.path,
                expected_main=before_main,
                expected_wal=before_wal,
                expected_shm=before_shm,
                stage="locked_before_validation",
                lock_active=True,
                conn=conn,
                upgrade_guard=_upgrade_guard,
            )
            self._validate_reviewability_candidate(
                conn, expected_version=REVIEWABILITY_SCHEMA_VERSION_V1
            )
            locked_records = self._read_validated_operation_checkpoints(conn)
            if [record.canonical_bytes for record in locked_records] != (
                before_checkpoint_bytes
            ):
                raise ReviewStoreError(
                    "Checkpoint rows changed between immutable and locked upgrade gates."
                )
            duplicate_semantic_rows = conn.execute(
                "SELECT episode_id, review_kind, checkpoint_type, perspective, "
                "as_of, knowledge_cutoff, COUNT(*) AS row_count "
                "FROM operation_review_checkpoints "
                "GROUP BY episode_id, review_kind, checkpoint_type, perspective, "
                "as_of, knowledge_cutoff HAVING COUNT(*) != 1"
            ).fetchall()
            if duplicate_semantic_rows:
                raise ReviewStoreError(
                    "Operation checkpoint semantic tuple is not uniquely closed."
                )
            locked_ddl_sha256 = self._reviewability_ddl_fingerprint(conn)
            if locked_ddl_sha256 != before_ddl_sha256:
                raise ReviewStoreError(
                    "Reviewability DDL changed before the marker upgrade lock."
                )
            self._assert_reviewability_upgrade_path_state(
                self.path,
                expected_main=before_main,
                expected_wal=before_wal,
                expected_shm=before_shm,
                stage="locked_before_marker_writes",
                lock_active=True,
                conn=conn,
                upgrade_guard=_upgrade_guard,
            )

            public_marker = conn.execute(
                "SELECT value FROM schema_meta WHERE "
                "key='reviewability_public_information_policy_version'"
            ).fetchone()
            if public_marker is not None:
                raise ReviewStoreError(
                    "Public-information marker already exists; exact v1 gate failed."
                )
            self._update_exact_marker(
                conn,
                key="reviewability_schema_version",
                expected=str(REVIEWABILITY_SCHEMA_VERSION_V1),
                replacement=str(REVIEWABILITY_SCHEMA_VERSION_V2),
            )
            self._update_exact_marker(
                conn,
                key="reviewability_checkpoint_contract_version",
                expected=OPERATION_CHECKPOINT_SCHEMA_VERSION,
                replacement=OPERATION_CHECKPOINT_SCHEMA_VERSION_V2,
            )
            self._update_exact_marker(
                conn,
                key="reviewability_market_policy_version",
                expected=MARKET_FALLBACK_POLICY_VERSION,
                replacement=MARKET_FALLBACK_POLICY_VERSION_V2,
            )
            self._update_exact_marker(
                conn,
                key="reviewability_schema_manifest_sha256",
                expected=REVIEWABILITY_SCHEMA_MANIFEST_SHA256,
                replacement=REVIEWABILITY_SCHEMA_MANIFEST_SHA256_V2,
            )
            inserted = conn.execute(
                "INSERT INTO schema_meta(key, value) VALUES(?, ?)",
                (
                    "reviewability_public_information_policy_version",
                    PUBLIC_INFORMATION_POLICY_VERSION,
                ),
            )
            if inserted.rowcount != 1:
                raise ReviewStoreError(
                    "Public-information marker insertion was not exact."
                )
            self._validate_reviewability_candidate(
                conn, expected_version=REVIEWABILITY_SCHEMA_VERSION_V2
            )
            upgraded_records = self._read_validated_operation_checkpoints(conn)
            if [record.canonical_bytes for record in upgraded_records] != (
                before_checkpoint_bytes
            ):
                raise ReviewStoreError(
                    "Immutable v1 checkpoint replay changed during marker upgrade."
                )
            after_locked_ddl_sha256 = self._reviewability_ddl_fingerprint(conn)
            if after_locked_ddl_sha256 != before_ddl_sha256:
                raise ReviewStoreError(
                    "Reviewability v2 marker upgrade attempted to change DDL."
                )
            conn.commit()
            committed = True
            self._assert_reviewability_upgrade_held_state(
                self.path,
                upgrade_guard=_upgrade_guard,
                stage="after_marker_commit",
                conn=conn,
            )
            _upgrade_guard.mark_marker_committed(stage="after_marker_commit")
            checkpoint_result = conn.execute(
                "PRAGMA wal_checkpoint(TRUNCATE)"
            ).fetchone()
            self._assert_reviewability_upgrade_held_state(
                self.path,
                upgrade_guard=_upgrade_guard,
                stage="after_marker_checkpoint",
                conn=conn,
            )
            checkpoint_complete = _upgrade_guard.record_checkpoint_result(
                checkpoint_result,
                stage="after_marker_checkpoint",
            )
        except ReviewStoreError:
            if conn.in_transaction:
                conn.rollback()
            raise
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            if not committed:
                raise
        finally:
            conn.close()
        _upgrade_guard.assert_after_writer_close(
            conn,
            stage="after_rw_close",
        )

        # A marker transaction can commit before SQLite reports a busy WAL
        # checkpoint.  Close the first handle, then perform one deterministic
        # recovery checkpoint under an exact-v2 gate.  This prevents callers
        # from mistaking an already-committed upgrade for a safe v1 retry.
        if not checkpoint_complete:
            self._assert_reviewability_upgrade_held_state(
                self.path,
                upgrade_guard=_upgrade_guard,
                stage="before_recovery_rw_open",
            )
            recovery = sqlite3.connect(uri, uri=True)
            recovery.row_factory = sqlite3.Row
            recovery.execute("PRAGMA foreign_keys = ON")
            recovery.execute("PRAGMA busy_timeout = 5000")
            try:
                _upgrade_guard.note_writer_open(
                    recovery,
                    stage="after_recovery_rw_open",
                )
                self._assert_reviewability_upgrade_held_state(
                    self.path,
                    upgrade_guard=_upgrade_guard,
                    stage="after_recovery_rw_open",
                    conn=recovery,
                )
                self._validate_reviewability_candidate(
                    recovery, expected_version=REVIEWABILITY_SCHEMA_VERSION_V2
                )
                recovery_result = recovery.execute(
                    "PRAGMA wal_checkpoint(TRUNCATE)"
                ).fetchone()
                self._assert_reviewability_upgrade_held_state(
                    self.path,
                    upgrade_guard=_upgrade_guard,
                    stage="after_recovery_checkpoint",
                    conn=recovery,
                )
                checkpoint_complete = _upgrade_guard.record_checkpoint_result(
                    recovery_result,
                    stage="after_recovery_checkpoint",
                )
            finally:
                recovery.close()
            _upgrade_guard.assert_after_writer_close(
                recovery,
                stage="after_recovery_close",
            )
            if not checkpoint_complete:
                raise ReviewStoreError(
                    "Reviewability v2 markers committed but WAL truncation remains "
                    "incomplete; do not retry the marker upgrade."
                )

        self._assert_reviewability_upgrade_held_state(
            self.path,
            upgrade_guard=_upgrade_guard,
            stage="before_final_exact_v2_validation",
        )
        result = self._validate_existing_reviewability_candidate(
            expected_version=REVIEWABILITY_SCHEMA_VERSION_V2
        )
        self._assert_reviewability_upgrade_held_state(
            self.path,
            upgrade_guard=_upgrade_guard,
            stage="after_final_exact_v2_validation",
        )
        final_replay_uri = (
            f"{self.path.resolve().as_uri()}?mode=ro&immutable=1"
        )
        final_replay = sqlite3.connect(final_replay_uri, uri=True)
        final_replay.row_factory = sqlite3.Row
        final_replay.execute("PRAGMA query_only = ON")
        try:
            self._assert_reviewability_upgrade_held_state(
                self.path,
                upgrade_guard=_upgrade_guard,
                stage="final_replay_connection",
                conn=final_replay,
            )
            after_records = self._read_validated_operation_checkpoints(final_replay)
            after_checkpoint_bytes = [
                record.canonical_bytes for record in after_records
            ]
            after_ddl_sha256 = self._reviewability_ddl_fingerprint(final_replay)
        finally:
            final_replay.close()
        if after_checkpoint_bytes != before_checkpoint_bytes:
            raise ReviewStoreError(
                "Immutable v1 checkpoint replay changed after marker upgrade."
            )
        if after_ddl_sha256 != before_ddl_sha256:
            raise ReviewStoreError(
                "Reviewability DDL changed after marker upgrade."
            )
        after_main = _stable_file_state(self.path)
        if after_main is None:
            raise ReviewStoreError("Reviewability candidate disappeared after upgrade.")
        self._assert_reviewability_upgrade_held_state(
            self.path,
            upgrade_guard=_upgrade_guard,
            stage="final_exact_v2_ddl_v1_replay",
        )
        result.update(
            {
                "status": "UPGRADED",
                "before_size": before_main[2],
                "before_sha256": before_main[4],
                "after_size": after_main[2],
                "after_sha256": after_main[4],
                "ddl_sha256": after_ddl_sha256,
                "preserved_v1_checkpoint_count": len(after_records),
            }
        )
        return result

    @staticmethod
    def _validate_reviewability_candidate(
        conn: sqlite3.Connection,
        *,
        expected_version: int | None = None,
    ) -> int:
        journal_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        if journal_mode != "wal":
            # An immutable SQLite connection deliberately ignores WAL semantics and
            # reports ``delete`` even when the persistent database header is in WAL
            # mode.  Existing candidates are opened immutable so validation cannot
            # create or update a ``-shm`` file.  In that one case, validate the two
            # persistent header mode bytes (write/read version at offsets 18/19)
            # instead of weakening the WAL invariant.
            database_rows = conn.execute("PRAGMA database_list").fetchall()
            main_paths = [
                Path(str(row[2]))
                for row in database_rows
                if str(row[1]) == "main" and str(row[2])
            ]
            header_is_wal = False
            if len(main_paths) == 1:
                try:
                    with main_paths[0].open("rb") as database_file:
                        header = database_file.read(20)
                    header_is_wal = (
                        len(header) == 20
                        and header[:16] == b"SQLite format 3\x00"
                        and header[18:20] == b"\x02\x02"
                    )
                except OSError:
                    header_is_wal = False
            if header_is_wal:
                journal_mode = "wal"
        if journal_mode != "wal":
            raise ReviewStoreError(
                "Reviewability candidate must preserve WAL journal mode."
            )
        quick_check = [
            str(row[0]) for row in conn.execute("PRAGMA quick_check").fetchall()
        ]
        if quick_check != ["ok"]:
            raise ReviewStoreError(
                "Reviewability candidate SQLite quick_check did not return ok."
            )
        application_id = int(conn.execute("PRAGMA application_id").fetchone()[0])
        user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if application_id != APPLICATION_ID or user_version != SCHEMA_VERSION:
            raise ReviewStoreError(
                "Existing database is not the required review v2 foundation."
            )
        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        indexes = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        if not _CORE_TABLES.issubset(tables) or not _CORE_INDEXES.issubset(indexes):
            raise ReviewStoreError("Reviewability candidate core schema is incomplete.")
        if not _PRODUCT_COMPLETION_TABLES.issubset(tables) or not (
            _PRODUCT_COMPLETION_INDEXES.issubset(indexes)
        ):
            raise ReviewStoreError(
                "Reviewability candidate product-completion schema is incomplete."
            )
        if not _REVIEWABILITY_TABLES.issubset(tables) or not (
            _REVIEWABILITY_INDEXES.issubset(indexes)
        ):
            raise ReviewStoreError(
                "Reviewability marker/schema is incomplete; refusing silent repair."
            )

        marker_keys = (
            "schema_version",
            "initialized_at",
            "p2h_stage1_schema_version",
            "p2h_stage2_slice_a_schema_version",
            "product_completion_schema_version",
            "reviewability_schema_version",
            "reviewability_checkpoint_contract_version",
            "reviewability_market_policy_version",
            "reviewability_public_information_policy_version",
            "reviewability_market_provider_allowlist_version",
            "reviewability_market_provider_allowlist_sha256",
            "reviewability_schema_manifest_sha256",
        )
        markers = {
            str(row["key"]): str(row["value"])
            for row in conn.execute(
                "SELECT key, value FROM schema_meta "
                f"WHERE key IN ({','.join('?' for _ in marker_keys)})",
                marker_keys,
            ).fetchall()
        }
        common_expected_markers = {
            "schema_version": str(SCHEMA_VERSION),
            "p2h_stage1_schema_version": str(P2H_STAGE1_SCHEMA_VERSION),
            "p2h_stage2_slice_a_schema_version": str(
                P2H_STAGE2_SLICE_A_SCHEMA_VERSION
            ),
            "product_completion_schema_version": str(
                PRODUCT_COMPLETION_SCHEMA_VERSION
            ),
            "reviewability_market_provider_allowlist_version": (
                MARKET_PROVIDER_ALLOWLIST_VERSION
            ),
            "reviewability_market_provider_allowlist_sha256": (
                MARKET_PROVIDER_ALLOWLIST_SHA256
            ),
        }
        initialized_at = markers.pop("initialized_at", None)
        try:
            initialized_at_is_valid = (
                initialized_at is not None
                and utc_iso(initialized_at, "UTC") == initialized_at
            )
        except (TypeError, ValueError):
            initialized_at_is_valid = False
        if not initialized_at_is_valid:
            raise ReviewStoreError(
                "Reviewability candidate initialized_at marker is missing or invalid."
            )
        try:
            actual_version = int(markers.get("reviewability_schema_version", ""))
        except (TypeError, ValueError):
            actual_version = -1
        if expected_version is not None and actual_version != expected_version:
            raise ReviewStoreError(
                "Reviewability feature marker version does not match the required "
                f"exact precondition: expected={expected_version}, actual={actual_version}."
            )
        if actual_version == REVIEWABILITY_SCHEMA_VERSION_V1:
            version_expected_markers = {
                "reviewability_schema_version": str(
                    REVIEWABILITY_SCHEMA_VERSION_V1
                ),
                "reviewability_checkpoint_contract_version": (
                    OPERATION_CHECKPOINT_SCHEMA_VERSION
                ),
                "reviewability_market_policy_version": (
                    MARKET_FALLBACK_POLICY_VERSION
                ),
                "reviewability_schema_manifest_sha256": (
                    REVIEWABILITY_SCHEMA_MANIFEST_SHA256
                ),
            }
            expected_manifest = _REVIEWABILITY_SCHEMA_MANIFEST
            expected_manifest_sha256 = REVIEWABILITY_SCHEMA_MANIFEST_SHA256
        elif actual_version == REVIEWABILITY_SCHEMA_VERSION_V2:
            version_expected_markers = {
                "reviewability_schema_version": str(
                    REVIEWABILITY_SCHEMA_VERSION_V2
                ),
                "reviewability_checkpoint_contract_version": (
                    OPERATION_CHECKPOINT_SCHEMA_VERSION_V2
                ),
                "reviewability_market_policy_version": (
                    MARKET_FALLBACK_POLICY_VERSION_V2
                ),
                "reviewability_public_information_policy_version": (
                    PUBLIC_INFORMATION_POLICY_VERSION
                ),
                "reviewability_schema_manifest_sha256": (
                    REVIEWABILITY_SCHEMA_MANIFEST_SHA256_V2
                ),
            }
            expected_manifest = _REVIEWABILITY_SCHEMA_MANIFEST_V2
            expected_manifest_sha256 = REVIEWABILITY_SCHEMA_MANIFEST_SHA256_V2
        else:
            raise ReviewStoreError(
                "Unsupported reviewability feature marker version."
            )
        expected_markers = {
            **common_expected_markers,
            **version_expected_markers,
        }
        if markers != expected_markers:
            raise ReviewStoreError(
                "Reviewability feature markers do not match the frozen exact contract."
            )

        try:
            actual_manifest = _reviewability_schema_manifest(
                conn,
                reviewability_schema_version=actual_version,
            )
        except (sqlite3.DatabaseError, TypeError, ValueError) as exc:
            raise ReviewStoreError(
                "Reviewability schema manifest could not be reconstructed."
            ) from exc
        actual_manifest_sha256 = sha256_text(canonical_json(actual_manifest))
        if (
            actual_manifest != expected_manifest
            or actual_manifest_sha256 != expected_manifest_sha256
        ):
            raise ReviewStoreError(
                "Reviewability schema structure or constraints drifted from the "
                "frozen manifest."
            )
        return actual_version

    def _ensure_reviewability_initialized(self) -> int:
        self._ensure_initialized()
        with self.connection(read_only=True) as conn:
            return self._validate_reviewability_candidate(conn)

    def _ensure_initialized(self) -> None:
        if not self.path.is_file():
            raise ReviewStoreError(
                f"Review database is not initialized: {self.path}. Run the init command first."
            )
        with self.connection(read_only=True) as conn:
            application_id = conn.execute("PRAGMA application_id").fetchone()[0]
            if application_id != APPLICATION_ID:
                raise ReviewStoreError(
                    f"Not an investment-review database: {self.path}. "
                    "Refusing to create or modify schema implicitly."
                )
            version_row = conn.execute(
                "SELECT value FROM schema_meta WHERE key='schema_version'"
            ).fetchone()
            version = int(version_row[0]) if version_row else None
            if version != SCHEMA_VERSION:
                raise ReviewStoreError(
                    f"Review database schema_version={version}; create a new v{SCHEMA_VERSION} "
                    "sidecar and reimport."
                )

    def _ensure_p2h_stage1_initialized(self) -> None:
        self._ensure_initialized()
        with self.connection(read_only=True) as conn:
            feature_row = conn.execute(
                "SELECT value FROM schema_meta "
                "WHERE key='p2h_stage1_schema_version'"
            ).fetchone()
            tables = {
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        required = {
            "behavior_hypothesis_candidates",
            "behavior_hypothesis_review_events",
        }
        if (
            feature_row is None
            or int(feature_row[0]) != P2H_STAGE1_SCHEMA_VERSION
            or not required.issubset(tables)
        ):
            raise ReviewStoreError(
                "P2H Stage 1 tables are not initialized; run the init command first."
            )

    def _ensure_p2h_stage2_slice_a_initialized(self) -> None:
        self._ensure_p2h_stage1_initialized()
        with self.connection(read_only=True) as conn:
            feature_row = conn.execute(
                "SELECT value FROM schema_meta "
                "WHERE key='p2h_stage2_slice_a_schema_version'"
            ).fetchone()
            tables = {
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        required = {
            "behavior_observation_protocols",
            "behavior_observation_protocol_review_events",
        }
        if (
            feature_row is None
            or int(feature_row[0]) != P2H_STAGE2_SLICE_A_SCHEMA_VERSION
            or not required.issubset(tables)
        ):
            raise ReviewStoreError(
                "P2H Stage 2 Slice A tables are not initialized; run the init "
                "command first."
            )

    def _ensure_product_completion_initialized(self) -> None:
        self._ensure_initialized()
        with self.connection(read_only=True) as conn:
            feature_row = conn.execute(
                "SELECT value FROM schema_meta "
                "WHERE key='product_completion_schema_version'"
            ).fetchone()
            tables = {
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        required = {
            "fee_profiles",
            "fee_projections",
            "fee_corrections",
            "review_runs",
            "review_run_status_events",
        }
        if (
            feature_row is None
            or int(feature_row[0]) != PRODUCT_COMPLETION_SCHEMA_VERSION
            or not required.issubset(tables)
        ):
            raise ReviewStoreError(
                "Product-completion tables are not initialized; run the init "
                "command first."
            )

    @staticmethod
    def _upsert_source(conn: sqlite3.Connection, source: SourceDefinition) -> None:
        source.validate()
        now = _now()
        conn.execute(
            """
            INSERT INTO data_sources(
                source_id, name, kind, uri, timezone, read_only,
                config_json, fingerprint, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
                name=excluded.name,
                kind=excluded.kind,
                uri=excluded.uri,
                timezone=excluded.timezone,
                read_only=excluded.read_only,
                config_json=excluded.config_json,
                fingerprint=excluded.fingerprint,
                updated_at=excluded.updated_at
            """,
            (
                source.source_id,
                source.name,
                source.kind,
                source.uri,
                source.timezone,
                1 if source.read_only else 0,
                canonical_json(dict(source.config)),
                source.fingerprint,
                now,
                now,
            ),
        )

    @staticmethod
    def _register_source_version(conn: sqlite3.Connection, source: SourceDefinition) -> None:
        conn.execute(
            """
            INSERT OR IGNORE INTO source_config_versions(
                source_id, fingerprint, config_json, created_at
            ) VALUES (?, ?, ?, ?)
            """,
            (
                source.source_id,
                source.fingerprint,
                canonical_json(dict(source.config)),
                _now(),
            ),
        )

    @classmethod
    def _register_failed_source_attempt(
        cls, conn: sqlite3.Connection, source: SourceDefinition
    ) -> None:
        exists = conn.execute(
            "SELECT 1 FROM data_sources WHERE source_id = ?", (source.source_id,)
        ).fetchone()
        if exists is None:
            cls._upsert_source(conn, source)
        cls._register_source_version(conn, source)

    def import_events(
        self,
        source: SourceDefinition,
        events: Sequence[CanonicalTradeEvent],
        *,
        manifest: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Atomically import canonical events and detect source-record drift."""

        self._ensure_initialized()
        for event in events:
            event.validate()
            if event.source_id != source.source_id:
                raise ReviewStoreError(
                    f"Event {event.event_id} belongs to {event.source_id}, expected {source.source_id}"
                )

        event_ids = [event.event_id for event in events]
        if len(set(event_ids)) != len(event_ids):
            raise ReviewStoreError("Input contains duplicate canonical event IDs")

        run_id = f"run_{uuid.uuid4().hex}"
        started = _now()
        inserted = 0
        skipped = 0

        try:
            with self.connection() as conn:
                with conn:
                    self._upsert_source(conn, source)
                    self._register_source_version(conn, source)
                    conn.execute(
                        """
                        INSERT INTO ingest_runs(
                            run_id, source_id, source_fingerprint,
                            started_at, status, manifest_json
                        ) VALUES (?, ?, ?, ?, 'RUNNING', ?)
                        """,
                        (
                            run_id,
                            source.source_id,
                            source.fingerprint,
                            started,
                            canonical_json(manifest or {}),
                        ),
                    )

                    previous_run = conn.execute(
                        """
                        SELECT r.run_id
                        FROM ingest_runs r
                        WHERE r.source_id = ? AND r.status = 'COMPLETED'
                          AND EXISTS (
                              SELECT 1 FROM ingest_run_events l WHERE l.run_id = r.run_id
                          )
                        ORDER BY r.finished_at DESC, r.run_id DESC
                        LIMIT 1
                        """,
                        (source.source_id,),
                    ).fetchone()
                    if previous_run is not None:
                        previous_ids = {
                            row[0]
                            for row in conn.execute(
                                "SELECT event_id FROM ingest_run_events WHERE run_id = ?",
                                (previous_run[0],),
                            ).fetchall()
                        }
                        missing_ids = previous_ids.difference(event_ids)
                        if missing_ids:
                            raise DataConflictError(
                                "Source snapshot removed or replaced previously observed records: "
                                f"previous_run={previous_run[0]}, missing_count={len(missing_ids)}"
                            )

                    for event in events:
                        existing = conn.execute(
                            """
                            SELECT payload_sha256, source_id, source_record_id,
                                   event_type, occurred_at, known_at, account, market,
                                   symbol, side, quantity, price, gross_amount,
                                   cash_amount, fees, currency
                            FROM trade_events WHERE event_id = ?
                            """,
                            (event.event_id,),
                        ).fetchone()
                        if existing is not None:
                            expected = {
                                "payload_sha256": event.payload_sha256,
                                "source_id": event.source_id,
                                "source_record_id": event.source_record_id,
                                "event_type": event.event_type,
                                "occurred_at": event.occurred_at,
                                "known_at": event.known_at,
                                "account": event.account,
                                "market": event.market,
                                "symbol": event.symbol,
                                "side": event.side,
                                "quantity": str(event.quantity) if event.quantity is not None else None,
                                "price": str(event.price) if event.price is not None else None,
                                "gross_amount": str(event.gross_amount) if event.gross_amount is not None else None,
                                "cash_amount": str(event.cash_amount) if event.cash_amount is not None else None,
                                "fees": str(event.fees) if event.fees is not None else None,
                                "currency": event.currency,
                            }
                            actual = dict(existing)
                            if actual != expected:
                                raise DataConflictError(
                                    "Source record changed after an earlier import: "
                                    f"event_id={event.event_id}, source_record_id={event.source_record_id!r}"
                                )
                            conn.execute(
                                """
                                INSERT INTO ingest_run_events(
                                    run_id, event_id, outcome, payload_sha256, observed_at
                                ) VALUES (?, ?, 'SKIPPED', ?, ?)
                                """,
                                (run_id, event.event_id, event.payload_sha256, _now()),
                            )
                            skipped += 1
                            continue

                        conn.execute(
                            """
                            INSERT INTO trade_events(
                                event_id, source_id, source_record_id, event_type,
                                occurred_at, known_at, account, market, symbol, side,
                                quantity, price, gross_amount, cash_amount, fees, currency,
                                raw_payload_json, payload_sha256,
                                first_ingest_run_id, ingested_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                event.event_id,
                                event.source_id,
                                event.source_record_id,
                                event.event_type,
                                event.occurred_at,
                                event.known_at,
                                event.account,
                                event.market,
                                event.symbol,
                                event.side,
                                str(event.quantity) if event.quantity is not None else None,
                                str(event.price) if event.price is not None else None,
                                str(event.gross_amount) if event.gross_amount is not None else None,
                                str(event.cash_amount) if event.cash_amount is not None else None,
                                str(event.fees) if event.fees is not None else None,
                                event.currency,
                                canonical_json(dict(event.raw_payload)),
                                event.payload_sha256,
                                run_id,
                                _now(),
                            ),
                        )
                        conn.execute(
                            """
                            INSERT INTO ingest_run_events(
                                run_id, event_id, outcome, payload_sha256, observed_at
                            ) VALUES (?, ?, 'INSERTED', ?, ?)
                            """,
                            (run_id, event.event_id, event.payload_sha256, _now()),
                        )
                        inserted += 1

                    conn.execute(
                        """
                        UPDATE ingest_runs
                        SET finished_at=?, status='COMPLETED', seen_count=?,
                            inserted_count=?, skipped_count=?
                        WHERE run_id=?
                        """,
                        (_now(), len(events), inserted, skipped, run_id),
                    )
        except Exception as exc:
            # Record the failed attempt without retaining any partial event rows.
            with self.connection() as conn:
                with conn:
                    self._register_failed_source_attempt(conn, source)
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO ingest_runs(
                            run_id, source_id, source_fingerprint,
                            started_at, finished_at, status,
                            seen_count, inserted_count, skipped_count,
                            error_text, manifest_json
                        ) VALUES (?, ?, ?, ?, ?, 'FAILED', ?, 0, 0, ?, ?)
                        """,
                        (
                            run_id,
                            source.source_id,
                            source.fingerprint,
                            started,
                            _now(),
                            len(events),
                            str(exc),
                            canonical_json(manifest or {}),
                        ),
                    )
            raise

        return {
            "run_id": run_id,
            "source_id": source.source_id,
            "seen": len(events),
            "inserted": inserted,
            "skipped": skipped,
            "status": "COMPLETED",
        }

    def add_decision(self, decision: DecisionRecord) -> str:
        self._ensure_initialized()
        decision.validate()
        now = _now()
        with self.connection() as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO decisions(
                        decision_id, symbol, market, occurred_at, known_at, status,
                        thesis, trigger_text, invalidation_text, expected_horizon,
                        portfolio_role, direct_reason, risk_notes, raw_note,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        decision.decision_id,
                        decision.symbol,
                        decision.market,
                        decision.occurred_at,
                        decision.known_at,
                        decision.status,
                        decision.thesis,
                        decision.trigger_text,
                        decision.invalidation_text,
                        decision.expected_horizon,
                        decision.portfolio_role,
                        decision.direct_reason,
                        decision.risk_notes,
                        decision.raw_note,
                        now,
                        now,
                    ),
                )
        return decision.decision_id

    def link_decision_event(
        self, decision_id: str, event_id: str, relation: str = "execution"
    ) -> None:
        self._ensure_initialized()
        with self.connection() as conn:
            with conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO decision_event_links(
                        decision_id, event_id, relation, created_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (decision_id, event_id, relation, _now()),
                )

    def save_portfolio_snapshot(
        self, source: SourceDefinition, snapshot: PortfolioSnapshot
    ) -> dict[str, Any]:
        """Persist one immutable portfolio snapshot in the sidecar review DB."""

        self._ensure_initialized()
        source.validate()
        snapshot.validate()
        if not source.read_only:
            raise ReviewStoreError("Portfolio snapshot source must be read-only")
        if snapshot.source_id != source.source_id:
            raise ReviewStoreError("Snapshot source_id does not match source definition")
        snapshot_id = snapshot.resolved_snapshot_id
        payload = snapshot.to_dict()
        payload_sha256 = snapshot.payload_sha256
        metrics = calculate_portfolio_metrics(snapshot)
        now = _now()
        with self.connection() as conn:
            with conn:
                self._upsert_source(conn, source)
                self._register_source_version(conn, source)
                existing = conn.execute(
                    "SELECT payload_sha256 FROM portfolio_snapshots WHERE snapshot_id = ?",
                    (snapshot_id,),
                ).fetchone()
                if existing is not None:
                    if existing["payload_sha256"] != payload_sha256:
                        raise DataConflictError(
                            f"Portfolio snapshot {snapshot_id} was observed with different content"
                        )
                    return {"snapshot_id": snapshot_id, "status": "SKIPPED"}
                conn.execute(
                    """
                    INSERT INTO portfolio_snapshots(
                        snapshot_id, source_id, source_record_id, observed_at, known_at,
                        account, nav, cash, gross_exposure, net_exposure,
                        payload_json, payload_sha256, ingested_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot_id,
                        source.source_id,
                        snapshot.source_record_id,
                        snapshot.observed_at,
                        snapshot.known_at,
                        snapshot.account,
                        str(snapshot.net_asset_value),
                        str(snapshot.cash),
                        metrics["gross_exposure"],
                        metrics["net_exposure"],
                        canonical_json(payload),
                        payload_sha256,
                        now,
                    ),
                )
                for position in snapshot.positions:
                    conn.execute(
                        """
                        INSERT INTO position_snapshot_items(
                            snapshot_id, symbol, market, quantity, cost_basis,
                            market_price, market_value, currency, payload_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            snapshot_id,
                            position.symbol,
                            position.market or "",
                            str(position.quantity),
                            str(position.cost_basis) if position.cost_basis is not None else None,
                            str(position.price) if position.price is not None else None,
                            str(position.market_value) if position.market_value is not None else None,
                            position.currency,
                            canonical_json(position.to_dict()),
                        ),
                    )
        return {"snapshot_id": snapshot_id, "status": "INSERTED"}

    def load_portfolio_snapshot(self, snapshot_id: str) -> PortfolioSnapshot:
        self._ensure_initialized()
        with self.connection(read_only=True) as conn:
            row = conn.execute(
                "SELECT payload_json FROM portfolio_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
        if row is None:
            raise ReviewStoreError(f"Portfolio snapshot not found: {snapshot_id}")
        payload = json.loads(row["payload_json"])
        return PortfolioSnapshot.from_dict(payload, default_source_id=payload.get("source_id"), timezone="UTC")

    def get_decision(self, decision_id: str) -> dict[str, Any]:
        self._ensure_initialized()
        with self.connection(read_only=True) as conn:
            row = conn.execute(
                "SELECT * FROM decisions WHERE decision_id = ?", (decision_id,)
            ).fetchone()
        if row is None:
            raise ReviewStoreError(f"Decision not found: {decision_id}")
        return dict(row)

    def build_decision_portfolio_context(
        self,
        *,
        decision_id: str,
        before_snapshot_id: str,
        after_snapshot_id: str | None = None,
    ) -> PortfolioContext:
        decision = self.get_decision(decision_id)
        return PortfolioContext(
            reference_type="decision",
            reference_id=decision_id,
            reference_symbol=decision["symbol"],
            reference_occurred_at=decision["occurred_at"],
            before_snapshot=self.load_portfolio_snapshot(before_snapshot_id),
            after_snapshot=(
                self.load_portfolio_snapshot(after_snapshot_id) if after_snapshot_id else None
            ),
        )

    def list_events(
        self,
        *,
        limit: int = 50,
        symbol: str | None = None,
        include_raw: bool = False,
    ) -> list[dict[str, Any]]:
        self._ensure_initialized()
        columns = "*" if include_raw else (
            "event_id, source_id, source_record_id, event_type, occurred_at, known_at, "
            "account, market, symbol, side, quantity, price, gross_amount, cash_amount, "
            "fees, currency, payload_sha256, first_ingest_run_id, ingested_at"
        )
        query = f"SELECT {columns} FROM trade_events"
        params: list[Any] = []
        if symbol:
            query += " WHERE symbol = ?"
            params.append(symbol.strip().upper())
        query += " ORDER BY occurred_at DESC, event_id DESC LIMIT ?"
        params.append(max(1, min(int(limit), 1000)))
        with self.connection(read_only=True) as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def list_episode_projection_inputs(
        self,
        *,
        account: str | None = None,
        symbol: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return all canonical event inputs plus explicit Decision links for P2C."""

        self._ensure_initialized()
        filters: list[str] = []
        params: list[Any] = []
        if account:
            filters.append("account = ?")
            params.append(account.strip())
        if symbol:
            filters.append("symbol = ?")
            params.append(symbol.strip().upper())
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        with self.connection(read_only=True) as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM trade_events
                {where}
                ORDER BY account, market, symbol, occurred_at, source_record_id, event_id
                """,
                params,
            ).fetchall()
            event_ids = [str(row["event_id"]) for row in rows]
            links: dict[str, list[dict[str, Any]]] = {event_id: [] for event_id in event_ids}
            if event_ids:
                placeholders = ",".join("?" for _ in event_ids)
                for link in conn.execute(
                    f"""
                    SELECT l.event_id, l.relation,
                           d.decision_id, d.symbol, d.market,
                           d.occurred_at, d.known_at, d.status
                    FROM decision_event_links l
                    JOIN decisions d ON d.decision_id = l.decision_id
                    WHERE l.event_id IN ({placeholders})
                    ORDER BY l.event_id, d.decision_id, l.relation
                    """,
                    event_ids,
                ):
                    links[str(link["event_id"])].append(
                        {
                            "decision_id": link["decision_id"],
                            "event_id": link["event_id"],
                            "relation": link["relation"],
                            "symbol": link["symbol"],
                            "market": link["market"],
                            "occurred_at": link["occurred_at"],
                            "known_at": link["known_at"],
                            "status": link["status"],
                            "link_source": "decision_event_links",
                        }
                    )
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["raw_payload"] = json.loads(item.pop("raw_payload_json"))
            item["decision_refs"] = links[str(item["event_id"])]
            result.append(item)
        return result

    def list_event_observation_evidence(
        self,
        *,
        event_ids: Sequence[str] | None = None,
        account: str | None = None,
        symbol: str | None = None,
    ) -> list[dict[str, Any]]:
        """Read immutable ingest-time evidence without changing P2C projections.

        ``trade_events.known_at`` is part of the legacy canonical event and is not
        reinterpreted here.  This query exposes the separate evidence needed by a
        versioned knowledge-provenance projection: the first ``INSERTED``
        observation, its ingest run, the event's stored ingest time, and the exact
        raw payload.  Missing linkage remains explicit as ``None``.
        """

        self._ensure_initialized()
        normalized_event_ids: list[str] | None = None
        if event_ids is not None:
            normalized_event_ids = sorted(
                {
                    str(event_id).strip()
                    for event_id in event_ids
                    if str(event_id).strip()
                }
            )
            if not normalized_event_ids:
                return []

        filters: list[str] = []
        params: list[Any] = []
        if normalized_event_ids is not None:
            placeholders = ",".join("?" for _ in normalized_event_ids)
            filters.append(f"e.event_id IN ({placeholders})")
            params.extend(normalized_event_ids)
        if account:
            filters.append("e.account = ?")
            params.append(account.strip())
        if symbol:
            filters.append("e.symbol = ?")
            params.append(symbol.strip().upper())
        where = f"WHERE {' AND '.join(filters)}" if filters else ""

        with self.connection(read_only=True) as conn:
            rows = conn.execute(
                f"""
                SELECT
                    e.event_id,
                    e.source_id,
                    e.source_record_id,
                    e.event_type,
                    e.occurred_at,
                    e.known_at,
                    e.account,
                    e.market,
                    e.symbol,
                    e.payload_sha256,
                    e.raw_payload_json,
                    e.first_ingest_run_id,
                    e.ingested_at,
                    l.outcome AS first_ingest_outcome,
                    l.payload_sha256 AS first_observation_payload_sha256,
                    l.observed_at AS first_inserted_observed_at,
                    r.source_id AS first_ingest_source_id,
                    r.source_fingerprint AS first_ingest_source_fingerprint,
                    r.started_at AS first_ingest_started_at,
                    r.finished_at AS first_ingest_finished_at,
                    r.status AS first_ingest_status,
                    r.manifest_json AS first_ingest_manifest_json
                FROM trade_events e
                LEFT JOIN ingest_run_events l
                  ON l.run_id = e.first_ingest_run_id
                 AND l.event_id = e.event_id
                 AND l.outcome = 'INSERTED'
                LEFT JOIN ingest_runs r
                  ON r.run_id = e.first_ingest_run_id
                {where}
                ORDER BY
                    e.account, e.market, e.symbol, e.occurred_at,
                    e.source_record_id, e.event_id
                """,
                params,
            ).fetchall()

        evidence: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            raw_payload_json = item.pop("raw_payload_json")
            manifest_json = item.pop("first_ingest_manifest_json")
            try:
                raw_payload = json.loads(raw_payload_json)
            except (TypeError, json.JSONDecodeError) as exc:
                raise ReviewStoreError(
                    "Stored event raw payload is not valid JSON: "
                    f"event_id={item['event_id']}"
                ) from exc
            if not isinstance(raw_payload, dict):
                raise ReviewStoreError(
                    "Stored event raw payload must be a JSON object: "
                    f"event_id={item['event_id']}"
                )

            first_ingest_manifest: dict[str, Any] | None = None
            if manifest_json is not None:
                try:
                    decoded_manifest = json.loads(manifest_json)
                except (TypeError, json.JSONDecodeError) as exc:
                    raise ReviewStoreError(
                        "Stored first-ingest manifest is not valid JSON: "
                        f"event_id={item['event_id']}"
                    ) from exc
                if not isinstance(decoded_manifest, dict):
                    raise ReviewStoreError(
                        "Stored first-ingest manifest must be a JSON object: "
                        f"event_id={item['event_id']}"
                    )
                first_ingest_manifest = decoded_manifest

            first_ingest = {
                "run_id": item.pop("first_ingest_run_id"),
                "outcome": item.pop("first_ingest_outcome"),
                "observed_at": item.pop("first_inserted_observed_at"),
                "observation_payload_sha256": item.pop(
                    "first_observation_payload_sha256"
                ),
                "source_id": item.pop("first_ingest_source_id"),
                "source_fingerprint": item.pop("first_ingest_source_fingerprint"),
                "started_at": item.pop("first_ingest_started_at"),
                "finished_at": item.pop("first_ingest_finished_at"),
                "status": item.pop("first_ingest_status"),
                "manifest": first_ingest_manifest,
            }
            item["raw_payload"] = raw_payload
            item["first_ingest"] = first_ingest
            evidence.append(item)
        return evidence

    @staticmethod
    def _product_payload(value: object, record_type: type[Any]) -> dict[str, Any]:
        if isinstance(value, record_type):
            record = value
        else:
            candidate = value
            if not isinstance(candidate, Mapping) and hasattr(candidate, "to_dict"):
                candidate = candidate.to_dict()
            if not isinstance(candidate, Mapping):
                raise ReviewStoreError(
                    f"Expected {record_type.__name__} or a mapping payload"
                )
            record = record_type.from_mapping(candidate)
        return record.to_dict()

    def _save_fee_profile_conn(
        self,
        conn: sqlite3.Connection,
        profile: FeeProfileRecord | Mapping[str, Any] | object,
    ) -> dict[str, Any]:
        payload = self._product_payload(profile, FeeProfileRecord)
        payload_json = canonical_json(payload)
        payload_sha256 = sha256_text(payload_json)
        profile_id = payload["profile_id"]
        existing = conn.execute(
            "SELECT payload_json, payload_sha256 FROM fee_profiles "
            "WHERE profile_id = ?",
            (profile_id,),
        ).fetchone()
        if existing is not None:
            if (
                existing["payload_json"] == payload_json
                and existing["payload_sha256"] == payload_sha256
            ):
                return {
                    "profile_id": profile_id,
                    "payload_sha256": payload_sha256,
                    "status": "SKIPPED",
                }
            raise DataConflictError(
                "Fee profile changed after creation: "
                f"profile_id={profile_id}"
            )
        conn.execute(
            """
            INSERT INTO fee_profiles(
                profile_id, profile_key, method, method_version,
                sample_count, rate, currency, fallback_level,
                computed_at, payload_json, payload_sha256, inserted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_id,
                payload["profile_key"],
                payload["method"],
                payload["method_version"],
                payload["sample_count"],
                payload["rate"],
                payload["currency"],
                payload["fallback_level"],
                payload["computed_at"],
                payload_json,
                payload_sha256,
                _now(),
            ),
        )
        return {
            "profile_id": profile_id,
            "payload_sha256": payload_sha256,
            "status": "INSERTED",
        }

    def save_fee_profile(
        self, profile: FeeProfileRecord | Mapping[str, Any] | object
    ) -> dict[str, Any]:
        """Create one immutable fee profile or idempotently replay it."""

        self._ensure_product_completion_initialized()
        with self.connection() as conn:
            with conn:
                return self._save_fee_profile_conn(conn, profile)

    def list_fee_profiles(
        self, *, profile_key: str | None = None
    ) -> list[dict[str, Any]]:
        self._ensure_product_completion_initialized()
        where = " WHERE profile_key = ?" if profile_key is not None else ""
        params: Sequence[Any] = (profile_key,) if profile_key is not None else ()
        with self.connection(read_only=True) as conn:
            rows = conn.execute(
                "SELECT payload_json FROM fee_profiles"
                + where
                + " ORDER BY computed_at, profile_id",
                params,
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def _save_fee_projection_conn(
        self,
        conn: sqlite3.Connection,
        projection: FeeProjectionRecord | Mapping[str, Any] | object,
    ) -> dict[str, Any]:
        payload = self._product_payload(projection, FeeProjectionRecord)
        payload_json = canonical_json(payload)
        payload_sha256 = sha256_text(payload_json)
        projection_id = payload["projection_id"]
        event_id = payload["event_id"]
        existing = conn.execute(
            "SELECT payload_json, payload_sha256 FROM fee_projections "
            "WHERE projection_id = ?",
            (projection_id,),
        ).fetchone()
        if existing is not None:
            if (
                existing["payload_json"] == payload_json
                and existing["payload_sha256"] == payload_sha256
            ):
                return {
                    "projection_id": projection_id,
                    "event_id": event_id,
                    "payload_sha256": payload_sha256,
                    "status": "SKIPPED",
                }
            raise DataConflictError(
                "Fee projection changed after creation: "
                f"projection_id={projection_id}"
            )
        if conn.execute(
            "SELECT 1 FROM trade_events WHERE event_id = ?", (event_id,)
        ).fetchone() is None:
            raise ReviewStoreError(f"Trade event not found: {event_id}")
        profile_id = payload["profile_id"]
        profile_row = None
        if profile_id is not None:
            profile_row = conn.execute(
                "SELECT payload_json FROM fee_profiles WHERE profile_id = ?",
                (profile_id,),
            ).fetchone()
            if profile_row is None:
                raise ReviewStoreError(f"Fee profile not found: {profile_id}")
        if payload["status"] == "estimated":
            profile_payload = json.loads(profile_row["payload_json"])
            compared_fields = (
                "method",
                "method_version",
                "sample_count",
                "currency",
            )
            mismatches = [
                field
                for field in compared_fields
                if profile_payload[field] != payload[field]
            ]
            if mismatches:
                raise ReviewStoreError(
                    "FEE_PROFILE_PROJECTION_MISMATCH: "
                    + ", ".join(mismatches)
                )
        concurrent = conn.execute(
            "SELECT projection_id FROM fee_projections "
            "WHERE event_id = ? AND projected_at = ?",
            (event_id, payload["projected_at"]),
        ).fetchone()
        if concurrent is not None:
            raise ReviewStoreError(
                "AMBIGUOUS_FEE_PROJECTION_TIME: another projection already "
                f"exists for event_id={event_id} at {payload['projected_at']}"
            )
        conn.execute(
            """
            INSERT INTO fee_projections(
                projection_id, event_id, status, amount, currency,
                source_fees, method, method_version, sample_count,
                profile_id, reason_code, projected_at, payload_json,
                payload_sha256, inserted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                projection_id,
                event_id,
                payload["status"],
                payload["amount"],
                payload["currency"],
                payload["source_fees"],
                payload["method"],
                payload["method_version"],
                payload["sample_count"],
                profile_id,
                payload["reason_code"],
                payload["projected_at"],
                payload_json,
                payload_sha256,
                _now(),
            ),
        )
        return {
            "projection_id": projection_id,
            "event_id": event_id,
            "payload_sha256": payload_sha256,
            "status": "INSERTED",
        }

    def save_fee_projection(
        self, projection: FeeProjectionRecord | Mapping[str, Any] | object
    ) -> dict[str, Any]:
        """Create one immutable actual/estimated/unknown fee projection."""

        self._ensure_product_completion_initialized()
        with self.connection() as conn:
            with conn:
                return self._save_fee_projection_conn(conn, projection)

    def save_fee_plan(
        self,
        profiles: Sequence[FeeProfileRecord | Mapping[str, Any] | object],
        projections: Sequence[FeeProjectionRecord | Mapping[str, Any] | object],
    ) -> dict[str, list[dict[str, Any]]]:
        """Atomically create or replay one complete deterministic fee plan."""

        self._ensure_product_completion_initialized()
        with self.connection() as conn:
            with conn:
                # Lock before the idempotence reads so concurrent deterministic
                # plans converge to INSERTED/SKIPPED instead of racing inserts.
                conn.execute("BEGIN IMMEDIATE")
                profile_results = [
                    self._save_fee_profile_conn(conn, profile) for profile in profiles
                ]
                projection_results = [
                    self._save_fee_projection_conn(conn, projection)
                    for projection in projections
                ]
        return {
            "profiles": profile_results,
            "projections": projection_results,
        }

    def list_fee_projections(
        self, *, event_id: str | None = None
    ) -> list[dict[str, Any]]:
        self._ensure_product_completion_initialized()
        where = " WHERE event_id = ?" if event_id is not None else ""
        params: Sequence[Any] = (event_id,) if event_id is not None else ()
        with self.connection(read_only=True) as conn:
            rows = conn.execute(
                "SELECT payload_json FROM fee_projections"
                + where
                + " ORDER BY event_id, projected_at, projection_id",
                params,
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def append_fee_correction(
        self, correction: FeeCorrectionRecord | Mapping[str, Any] | object
    ) -> dict[str, Any]:
        """Append a human fee correction without replacing any prior row."""

        self._ensure_product_completion_initialized()
        payload = self._product_payload(correction, FeeCorrectionRecord)
        payload_json = canonical_json(payload)
        payload_sha256 = sha256_text(payload_json)
        correction_id = payload["correction_id"]
        event_id = payload["event_id"]
        with self.connection() as conn:
            with conn:
                existing = conn.execute(
                    "SELECT payload_json, payload_sha256 FROM fee_corrections "
                    "WHERE correction_id = ?",
                    (correction_id,),
                ).fetchone()
                if existing is not None:
                    if (
                        existing["payload_json"] == payload_json
                        and existing["payload_sha256"] == payload_sha256
                    ):
                        return {
                            "correction_id": correction_id,
                            "event_id": event_id,
                            "payload_sha256": payload_sha256,
                            "status": "SKIPPED",
                        }
                    raise DataConflictError(
                        "Fee correction changed after creation: "
                        f"correction_id={correction_id}"
                    )
                if conn.execute(
                    "SELECT 1 FROM trade_events WHERE event_id = ?", (event_id,)
                ).fetchone() is None:
                    raise ReviewStoreError(f"Trade event not found: {event_id}")
                current = conn.execute(
                    "SELECT correction_id, effective_at, known_at "
                    "FROM fee_corrections WHERE event_id = ? "
                    "ORDER BY effective_at DESC, known_at DESC, correction_id DESC "
                    "LIMIT 1",
                    (event_id,),
                ).fetchone()
                supersedes_id = payload["supersedes_correction_id"]
                if current is None and supersedes_id is not None:
                    raise ReviewStoreError(
                        "Cannot supersede a missing fee correction: "
                        f"correction_id={supersedes_id}"
                    )
                if current is not None:
                    if supersedes_id != current["correction_id"]:
                        raise ReviewStoreError(
                            "A new fee correction must supersede the current correction "
                            f"{current['correction_id']}"
                        )
                    if (
                        payload["effective_at"] < current["effective_at"]
                        or payload["known_at"] < current["known_at"]
                    ):
                        raise ReviewStoreError(
                            "A superseding fee correction cannot precede its parent"
                        )
                concurrent = conn.execute(
                    "SELECT correction_id FROM fee_corrections "
                    "WHERE event_id = ? AND effective_at = ? AND known_at = ?",
                    (event_id, payload["effective_at"], payload["known_at"]),
                ).fetchone()
                if concurrent is not None:
                    raise ReviewStoreError(
                        "AMBIGUOUS_FEE_CORRECTION_TIME: another correction already "
                        f"exists for event_id={event_id} at the same dual time"
                    )
                conn.execute(
                    """
                    INSERT INTO fee_corrections(
                        correction_id, event_id, status, amount, currency,
                        effective_at, known_at, reviewer_ref, reason,
                        supersedes_correction_id, payload_json, payload_sha256,
                        inserted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        correction_id,
                        event_id,
                        payload["status"],
                        payload["amount"],
                        payload["currency"],
                        payload["effective_at"],
                        payload["known_at"],
                        payload["reviewer_ref"],
                        payload["reason"],
                        supersedes_id,
                        payload_json,
                        payload_sha256,
                        _now(),
                    ),
                )
        return {
            "correction_id": correction_id,
            "event_id": event_id,
            "payload_sha256": payload_sha256,
            "status": "INSERTED",
        }

    def list_fee_corrections(
        self, *, event_id: str | None = None
    ) -> list[dict[str, Any]]:
        self._ensure_product_completion_initialized()
        where = " WHERE event_id = ?" if event_id is not None else ""
        params: Sequence[Any] = (event_id,) if event_id is not None else ()
        with self.connection(read_only=True) as conn:
            rows = conn.execute(
                "SELECT payload_json FROM fee_corrections"
                + where
                + " ORDER BY event_id, effective_at, known_at, correction_id",
                params,
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def get_effective_fee(
        self,
        event_id: str,
        *,
        as_of: str | None = None,
        knowledge_cutoff: str | None = None,
    ) -> dict[str, Any]:
        """Project the visible fee without mutating source or derived history."""

        self._ensure_product_completion_initialized()
        normalized_as_of = utc_iso(as_of, "UTC") if as_of is not None else None
        normalized_cutoff = (
            utc_iso(knowledge_cutoff, "UTC")
            if knowledge_cutoff is not None
            else None
        )
        with self.connection(read_only=True) as conn:
            if conn.execute(
                "SELECT 1 FROM trade_events WHERE event_id = ?", (event_id,)
            ).fetchone() is None:
                raise ReviewStoreError(f"Trade event not found: {event_id}")
            projection_filters = ["event_id = ?"]
            projection_params: list[Any] = [event_id]
            if normalized_as_of is not None:
                projection_filters.append("projected_at <= ?")
                projection_params.append(normalized_as_of)
            if normalized_cutoff is not None:
                projection_filters.append("projected_at <= ?")
                projection_params.append(normalized_cutoff)
            projection_row = conn.execute(
                "SELECT payload_json FROM fee_projections WHERE "
                + " AND ".join(projection_filters)
                + " ORDER BY projected_at DESC, projection_id DESC LIMIT 1",
                projection_params,
            ).fetchone()
            correction_filters = ["event_id = ?"]
            correction_params: list[Any] = [event_id]
            if normalized_as_of is not None:
                correction_filters.append("effective_at <= ?")
                correction_params.append(normalized_as_of)
            if normalized_cutoff is not None:
                correction_filters.append("known_at <= ?")
                correction_params.append(normalized_cutoff)
            correction_row = conn.execute(
                "SELECT payload_json FROM fee_corrections WHERE "
                + " AND ".join(correction_filters)
                + " ORDER BY effective_at DESC, known_at DESC, correction_id DESC LIMIT 1",
                correction_params,
            ).fetchone()
        projection = (
            json.loads(projection_row["payload_json"])
            if projection_row is not None
            else None
        )
        if correction_row is not None:
            correction = json.loads(correction_row["payload_json"])
            return {
                **correction,
                "source": "correction",
                "base_projection_id": (
                    projection["projection_id"] if projection is not None else None
                ),
            }
        if projection is not None:
            return {**projection, "source": "projection"}
        return {
            "event_id": event_id,
            "status": "unknown",
            "amount": None,
            "currency": "CNY",
            "reason_code": "no_fee_projection",
            "source": "missing",
        }

    def save_review_run(
        self, run: ReviewRunRecord | Mapping[str, Any] | object
    ) -> dict[str, Any]:
        """Create deterministic review-run request metadata."""

        self._ensure_product_completion_initialized()
        payload = self._product_payload(run, ReviewRunRecord)
        payload_json = canonical_json(payload)
        payload_sha256 = sha256_text(payload_json)
        run_id = payload["run_id"]
        run_key = payload["run_key"]
        with self.connection() as conn:
            with conn:
                existing = conn.execute(
                    "SELECT run_key, payload_json, payload_sha256 FROM review_runs "
                    "WHERE run_id = ?",
                    (run_id,),
                ).fetchone()
                if existing is not None:
                    if (
                        existing["payload_json"] == payload_json
                        and existing["payload_sha256"] == payload_sha256
                    ):
                        return {
                            "run_id": run_id,
                            "run_key": run_key,
                            "payload_sha256": payload_sha256,
                            "status": "SKIPPED",
                        }
                    raise DataConflictError(
                        f"Review run changed after creation: run_id={run_id}"
                    )
                key_owner = conn.execute(
                    "SELECT run_id FROM review_runs WHERE run_key = ?", (run_key,)
                ).fetchone()
                if key_owner is not None:
                    raise DataConflictError(
                        "Review run key already belongs to "
                        f"run_id={key_owner['run_id']}"
                    )
                conn.execute(
                    """
                    INSERT INTO review_runs(
                        run_id, run_key, scope, requested_at, source_cutoff,
                        trigger, payload_json, payload_sha256, inserted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        run_key,
                        payload["scope"],
                        payload["requested_at"],
                        payload["source_cutoff"],
                        payload["trigger"],
                        payload_json,
                        payload_sha256,
                        _now(),
                    ),
                )
        return {
            "run_id": run_id,
            "run_key": run_key,
            "payload_sha256": payload_sha256,
            "status": "INSERTED",
        }

    def append_review_run_status(
        self, event: ReviewRunStatusEvent | Mapping[str, Any] | object
    ) -> dict[str, Any]:
        """Append one status event; no run row or prior event is overwritten."""

        self._ensure_product_completion_initialized()
        payload = self._product_payload(event, ReviewRunStatusEvent)
        payload_json = canonical_json(payload)
        payload_sha256 = sha256_text(payload_json)
        run_event_id = payload["run_event_id"]
        run_id = payload["run_id"]
        with self.connection() as conn:
            with conn:
                existing = conn.execute(
                    "SELECT payload_json, payload_sha256 "
                    "FROM review_run_status_events WHERE run_event_id = ?",
                    (run_event_id,),
                ).fetchone()
                if existing is not None:
                    if (
                        existing["payload_json"] == payload_json
                        and existing["payload_sha256"] == payload_sha256
                    ):
                        return {
                            "run_event_id": run_event_id,
                            "run_id": run_id,
                            "payload_sha256": payload_sha256,
                            "status": "SKIPPED",
                        }
                    raise DataConflictError(
                        "Review run status event changed after creation: "
                        f"run_event_id={run_event_id}"
                    )
                if conn.execute(
                    "SELECT 1 FROM review_runs WHERE run_id = ?", (run_id,)
                ).fetchone() is None:
                    raise ReviewStoreError(f"Review run not found: {run_id}")
                concurrent = conn.execute(
                    "SELECT run_event_id FROM review_run_status_events "
                    "WHERE run_id = ? AND occurred_at = ? AND known_at = ?",
                    (run_id, payload["occurred_at"], payload["known_at"]),
                ).fetchone()
                if concurrent is not None:
                    raise ReviewStoreError(
                        "AMBIGUOUS_REVIEW_RUN_STATUS_TIME: another status event "
                        "already uses the same dual time"
                    )
                conn.execute(
                    """
                    INSERT INTO review_run_status_events(
                        run_event_id, run_id, status, occurred_at, known_at,
                        payload_json, payload_sha256, inserted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_event_id,
                        run_id,
                        payload["status"],
                        payload["occurred_at"],
                        payload["known_at"],
                        payload_json,
                        payload_sha256,
                        _now(),
                    ),
                )
        return {
            "run_event_id": run_event_id,
            "run_id": run_id,
            "payload_sha256": payload_sha256,
            "status": "INSERTED",
        }

    def get_review_run(
        self,
        run_ref: str,
        *,
        as_of: str | None = None,
        knowledge_cutoff: str | None = None,
    ) -> dict[str, Any]:
        """Return run metadata plus a cutoff-safe status-ledger projection."""

        self._ensure_product_completion_initialized()
        normalized_as_of = utc_iso(as_of, "UTC") if as_of is not None else None
        normalized_cutoff = (
            utc_iso(knowledge_cutoff, "UTC")
            if knowledge_cutoff is not None
            else None
        )
        with self.connection(read_only=True) as conn:
            run_rows = conn.execute(
                "SELECT payload_json FROM review_runs "
                "WHERE run_id = ? OR run_key = ? ORDER BY run_id",
                (run_ref, run_ref),
            ).fetchall()
            if not run_rows:
                raise ReviewStoreError(f"Review run not found: {run_ref}")
            if len(run_rows) != 1:
                raise ReviewStoreError(f"Ambiguous review run reference: {run_ref}")
            run = json.loads(run_rows[0]["payload_json"])
            filters = ["run_id = ?"]
            params: list[Any] = [run["run_id"]]
            if normalized_as_of is not None:
                filters.append("occurred_at <= ?")
                params.append(normalized_as_of)
            if normalized_cutoff is not None:
                filters.append("known_at <= ?")
                params.append(normalized_cutoff)
            event_rows = conn.execute(
                "SELECT payload_json FROM review_run_status_events WHERE "
                + " AND ".join(filters)
                + " ORDER BY occurred_at, known_at, run_event_id",
                params,
            ).fetchall()
        history = [json.loads(row["payload_json"]) for row in event_rows]
        current = history[-1] if history else None
        return {
            "run": run,
            "status": current["status"] if current is not None else "unknown",
            "status_event": current,
            "history": history,
        }

    def list_review_runs(
        self,
        *,
        scope: str | None = None,
        status: str | None = None,
        as_of: str | None = None,
        knowledge_cutoff: str | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_product_completion_initialized()
        where = " WHERE scope = ?" if scope is not None else ""
        params: Sequence[Any] = (scope,) if scope is not None else ()
        with self.connection(read_only=True) as conn:
            rows = conn.execute(
                "SELECT run_id FROM review_runs"
                + where
                + " ORDER BY requested_at, run_id",
                params,
            ).fetchall()
        result = [
            self.get_review_run(
                str(row["run_id"]),
                as_of=as_of,
                knowledge_cutoff=knowledge_cutoff,
            )
            for row in rows
        ]
        if status is not None:
            result = [item for item in result if item["status"] == status]
        return result

    @staticmethod
    def _operation_checkpoint_projection(
        record: OperationCheckpointRecord | OperationCheckpointRecordV2,
    ) -> dict[str, Any]:
        payload = record.to_dict()
        axes = payload["status_axes"]
        times = payload["time_provenance"]
        return {
            "checkpoint_id": record.checkpoint_id,
            "checkpoint_key": record.checkpoint_key,
            "content_id": record.content_id,
            "episode_id": payload["episode_id"],
            "position_case_id": payload["position_case_id"],
            "review_kind": payload["review_kind"],
            "checkpoint_type": payload["checkpoint_type"],
            "perspective": payload["perspective"],
            "as_of": payload["as_of"],
            "knowledge_cutoff": payload["knowledge_cutoff"],
            "effective_at": times["effective_at"]["value"],
            "user_known_at": times["user_known_at"]["value"],
            "system_observed_at": times["system_observed_at"]["value"],
            "recorded_at": times["recorded_at"]["value"],
            "operation_status": axes["operation"]["status"],
            "decision_status": axes["decision"]["status"],
            "snapshot_status": axes["snapshot_cash_valuation"]["status"],
            "market_status": axes["market"]["status"],
            "lifecycle_status": axes["lifecycle"]["status"],
            "outcome_status": axes["outcome"]["status"],
        }

    @staticmethod
    def _operation_checkpoint_row_integrity_sha256(
        *,
        projection: Mapping[str, Any],
        payload_sha256: str,
        inserted_at: str,
        checkpoint_schema_version: str = OPERATION_CHECKPOINT_SCHEMA_VERSION,
    ) -> str:
        if checkpoint_schema_version == OPERATION_CHECKPOINT_SCHEMA_VERSION:
            row_schema_version = "investment_review.operation_checkpoint_row.v1"
        elif checkpoint_schema_version == OPERATION_CHECKPOINT_SCHEMA_VERSION_V2:
            row_schema_version = "investment_review.operation_checkpoint_row.v2"
        else:
            raise ReviewStoreError(
                "Unsupported operation checkpoint row-integrity version."
            )
        return sha256_text(
            canonical_json(
                {
                    "schema_version": row_schema_version,
                    "projection": dict(projection),
                    "payload_sha256": payload_sha256,
                    "inserted_at": inserted_at,
                }
            )
        )

    @staticmethod
    def _validate_operation_checkpoint_row(
        row: sqlite3.Row,
        gap_rows: Sequence[sqlite3.Row],
    ) -> OperationCheckpointRecord | OperationCheckpointRecordV2:
        """Reconstruct one row and reject every payload/projection divergence."""

        raw_payload = row["payload_json"]
        if not isinstance(raw_payload, str):
            raise ReviewStoreError("Operation checkpoint payload_json is not text.")
        try:
            decoded = json.loads(raw_payload)
            if not isinstance(decoded, dict):
                raise TypeError("payload root must be an object")
            record = operation_checkpoint_from_mapping(decoded)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ReviewStoreError(
                "Operation checkpoint canonical payload failed validation."
            ) from exc

        canonical_payload = record.canonical_bytes.decode("utf-8")
        expected_payload_sha256 = sha256_text(canonical_payload)
        if raw_payload != canonical_payload:
            raise ReviewStoreError(
                "Operation checkpoint payload_json is not canonical."
            )
        if row["payload_sha256"] != expected_payload_sha256:
            raise ReviewStoreError(
                "Operation checkpoint payload_sha256 does not match canonical payload."
            )

        projection = ReviewStore._operation_checkpoint_projection(record)
        for column, expected in projection.items():
            if row[column] != expected:
                raise ReviewStoreError(
                    "Operation checkpoint projection drifted from canonical payload: "
                    f"{column}"
                )
        inserted_at = row["inserted_at"]
        if (
            not isinstance(inserted_at, str)
            or utc_iso(inserted_at, "UTC") != inserted_at
        ):
            raise ReviewStoreError(
                "Operation checkpoint inserted_at is not canonical UTC."
            )
        expected_row_integrity = (
            ReviewStore._operation_checkpoint_row_integrity_sha256(
                projection=projection,
                payload_sha256=expected_payload_sha256,
                inserted_at=inserted_at,
                checkpoint_schema_version=str(decoded.get("schema_version") or ""),
            )
        )
        if row["row_integrity_sha256"] != expected_row_integrity:
            raise ReviewStoreError(
                "Operation checkpoint row integrity hash does not match."
            )

        expected_gaps = {
            str(gap["gap_id"]): gap for gap in record.to_dict()["gaps"]
        }
        actual_gap_ids = [str(item["gap_id"]) for item in gap_rows]
        if len(actual_gap_ids) != len(set(actual_gap_ids)):
            raise ReviewStoreError(
                "Operation checkpoint gap projection contains duplicate gap IDs."
            )
        if set(actual_gap_ids) != set(expected_gaps):
            raise ReviewStoreError(
                "Operation checkpoint gap projection is not exactly closed."
            )

        for gap_row in gap_rows:
            gap_id = str(gap_row["gap_id"])
            expected_gap = expected_gaps[gap_id]
            canonical_gap = canonical_json(expected_gap)
            raw_gap_payload = gap_row["payload_json"]
            if not isinstance(raw_gap_payload, str):
                raise ReviewStoreError(
                    f"Operation checkpoint gap payload is not text: {gap_id}"
                )
            try:
                decoded_gap = json.loads(raw_gap_payload)
            except json.JSONDecodeError as exc:
                raise ReviewStoreError(
                    f"Operation checkpoint gap payload is invalid JSON: {gap_id}"
                ) from exc
            if decoded_gap != expected_gap or raw_gap_payload != canonical_gap:
                raise ReviewStoreError(
                    f"Operation checkpoint gap payload drifted: {gap_id}"
                )
            expected_projection = {
                "checkpoint_id": record.checkpoint_id,
                "gap_id": gap_id,
                "axis": expected_gap["axis"],
                "code": expected_gap["code"],
                "severity": expected_gap["severity"],
                "blocks_axis": int(expected_gap["blocks_axis"]),
                "owner": expected_gap["owner"],
                "next_step": expected_gap["next_step"],
                "payload_json": canonical_gap,
            }
            for column, expected in expected_projection.items():
                if gap_row[column] != expected:
                    raise ReviewStoreError(
                        "Operation checkpoint gap projection drifted: "
                        f"{gap_id}.{column}"
                    )
        return record

    @staticmethod
    def _read_validated_operation_checkpoints(
        conn: sqlite3.Connection,
    ) -> list[OperationCheckpointRecord | OperationCheckpointRecordV2]:
        """Load the complete checkpoint set so omitted/corrupt rows cannot hide."""

        rows = conn.execute(
            "SELECT * FROM operation_review_checkpoints ORDER BY checkpoint_id"
        ).fetchall()
        gap_rows = conn.execute(
            "SELECT * FROM operation_checkpoint_gaps "
            "ORDER BY checkpoint_id, gap_id"
        ).fetchall()
        checkpoint_ids = {str(row["checkpoint_id"]) for row in rows}
        orphan_gap_ids = sorted(
            {
                str(row["checkpoint_id"])
                for row in gap_rows
                if str(row["checkpoint_id"]) not in checkpoint_ids
            }
        )
        if orphan_gap_ids:
            raise ReviewStoreError(
                "Operation checkpoint gap projection contains orphan rows: "
                + ", ".join(orphan_gap_ids)
            )
        gaps_by_checkpoint: dict[str, list[sqlite3.Row]] = {
            checkpoint_id: [] for checkpoint_id in checkpoint_ids
        }
        for gap_row in gap_rows:
            gaps_by_checkpoint[str(gap_row["checkpoint_id"])].append(gap_row)
        return [
            ReviewStore._validate_operation_checkpoint_row(
                row,
                gaps_by_checkpoint[str(row["checkpoint_id"])],
            )
            for row in rows
        ]

    @staticmethod
    def _existing_operation_checkpoint_receipt(
        stored_records: Sequence[
            OperationCheckpointRecord | OperationCheckpointRecordV2
        ],
        record: OperationCheckpointRecord | OperationCheckpointRecordV2,
        payload_sha256: str,
    ) -> dict[str, Any] | None:
        existing = [
            stored
            for stored in stored_records
            if (
                stored.checkpoint_id == record.checkpoint_id
                or stored.checkpoint_key == record.checkpoint_key
                or stored.content_id == record.content_id
            )
        ]
        if len(existing) == 1 and (
            existing[0].canonical_bytes == record.canonical_bytes
        ):
            return {
                "checkpoint_id": record.checkpoint_id,
                "checkpoint_key": record.checkpoint_key,
                "content_id": record.content_id,
                "payload_sha256": payload_sha256,
                "status": "SKIPPED",
            }
        if existing:
            raise DataConflictError(
                "Operation checkpoint identity or key changed after creation: "
                f"checkpoint_key={record.checkpoint_key}"
            )
        record_payload = record.to_dict()
        semantic_tuple = (
            record_payload["episode_id"],
            record_payload["review_kind"],
            record_payload["checkpoint_type"],
            record_payload["perspective"],
            record_payload["as_of"],
            record_payload["knowledge_cutoff"],
        )
        semantic_collisions = [
            stored
            for stored in stored_records
            if (
                stored.to_dict()["episode_id"],
                stored.to_dict()["review_kind"],
                stored.to_dict()["checkpoint_type"],
                stored.to_dict()["perspective"],
                stored.to_dict()["as_of"],
                stored.to_dict()["knowledge_cutoff"],
            )
            == semantic_tuple
        ]
        if semantic_collisions:
            raise DataConflictError(
                "Operation checkpoint storage tuple already belongs to another "
                "immutable identity; v2 requires a new knowledge_cutoff."
            )
        return None

    def save_operation_checkpoint(
        self,
        checkpoint: (
            OperationCheckpointRecord
            | OperationCheckpointRecordV2
            | Mapping[str, Any]
        ),
    ) -> dict[str, Any]:
        """Create one immutable checkpoint under the exact selected feature marker."""

        reviewability_version = self._ensure_reviewability_initialized()
        record = operation_checkpoint_from_mapping(
            checkpoint.to_dict()
            if isinstance(
                checkpoint, (OperationCheckpointRecord, OperationCheckpointRecordV2)
            )
            else checkpoint
        )
        payload = record.to_dict()
        payload_json = record.canonical_bytes.decode("utf-8")
        payload_sha256 = sha256_text(payload_json)
        projection = self._operation_checkpoint_projection(record)
        inserted_at = _now()
        row_integrity_sha256 = self._operation_checkpoint_row_integrity_sha256(
            projection=projection,
            payload_sha256=payload_sha256,
            inserted_at=inserted_at,
            checkpoint_schema_version=str(payload["schema_version"]),
        )

        # The idempotent path is genuinely read-only.  A second check under an
        # IMMEDIATE transaction below closes the race before the create-only insert.
        with self.connection(read_only=True) as conn:
            existing_receipt = self._existing_operation_checkpoint_receipt(
                self._read_validated_operation_checkpoints(conn),
                record,
                payload_sha256,
            )
        if existing_receipt is not None:
            return existing_receipt
        if (
            reviewability_version == REVIEWABILITY_SCHEMA_VERSION_V1
            and payload["schema_version"] != OPERATION_CHECKPOINT_SCHEMA_VERSION
        ):
            raise ReviewStoreError(
                "Reviewability v1 candidate cannot create a v2 checkpoint before "
                "the explicit marker upgrade."
            )
        if (
            reviewability_version == REVIEWABILITY_SCHEMA_VERSION_V2
            and payload["schema_version"] != OPERATION_CHECKPOINT_SCHEMA_VERSION_V2
        ):
            raise ReviewStoreError(
                "Reviewability v2 candidate may replay old v1 checkpoints but must "
                "not create a new v1 checkpoint."
            )

        with self.connection() as conn:
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                locked_version = self._validate_reviewability_candidate(conn)
                if (
                    locked_version is not None
                    and locked_version != reviewability_version
                ):
                    raise ReviewStoreError(
                        "Reviewability marker changed before the checkpoint write lock."
                    )
                existing_receipt = self._existing_operation_checkpoint_receipt(
                    self._read_validated_operation_checkpoints(conn),
                    record,
                    payload_sha256,
                )
                if existing_receipt is not None:
                    return existing_receipt
                conn.execute(
                    """
                    INSERT INTO operation_review_checkpoints(
                        checkpoint_id, checkpoint_key, content_id, episode_id,
                        position_case_id, review_kind, checkpoint_type,
                        perspective, as_of, knowledge_cutoff, effective_at,
                        user_known_at, system_observed_at, recorded_at,
                        operation_status, decision_status, snapshot_status,
                        market_status, lifecycle_status, outcome_status,
                        payload_json, payload_sha256, inserted_at,
                        row_integrity_sha256
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        projection["checkpoint_id"],
                        projection["checkpoint_key"],
                        projection["content_id"],
                        projection["episode_id"],
                        projection["position_case_id"],
                        projection["review_kind"],
                        projection["checkpoint_type"],
                        projection["perspective"],
                        projection["as_of"],
                        projection["knowledge_cutoff"],
                        projection["effective_at"],
                        projection["user_known_at"],
                        projection["system_observed_at"],
                        projection["recorded_at"],
                        projection["operation_status"],
                        projection["decision_status"],
                        projection["snapshot_status"],
                        projection["market_status"],
                        projection["lifecycle_status"],
                        projection["outcome_status"],
                        payload_json,
                        payload_sha256,
                        inserted_at,
                        row_integrity_sha256,
                    ),
                )
                for gap in payload["gaps"]:
                    conn.execute(
                        """
                        INSERT INTO operation_checkpoint_gaps(
                            checkpoint_id, gap_id, axis, code, severity,
                            blocks_axis, owner, next_step, payload_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            record.checkpoint_id,
                            gap["gap_id"],
                            gap["axis"],
                            gap["code"],
                            gap["severity"],
                            int(gap["blocks_axis"]),
                            gap["owner"],
                            gap["next_step"],
                            canonical_json(gap),
                        ),
                    )
        return {
            "checkpoint_id": record.checkpoint_id,
            "checkpoint_key": record.checkpoint_key,
            "content_id": record.content_id,
            "payload_sha256": payload_sha256,
            "status": "INSERTED",
        }

    def get_operation_checkpoint(self, checkpoint_ref: str) -> dict[str, Any]:
        self._ensure_reviewability_initialized()
        with self.connection(read_only=True) as conn:
            records = self._read_validated_operation_checkpoints(conn)
        matches = [
            record
            for record in records
            if checkpoint_ref
            in {
                record.checkpoint_id,
                record.checkpoint_key,
                record.content_id,
            }
        ]
        if not matches:
            raise ReviewStoreError(
                f"Operation checkpoint not found: {checkpoint_ref}"
            )
        if len(matches) != 1:
            raise ReviewStoreError(
                f"Ambiguous operation checkpoint reference: {checkpoint_ref}"
            )
        return matches[0].to_dict()

    def list_operation_checkpoints(
        self,
        *,
        episode_id: str | None = None,
        position_case_id: str | None = None,
        perspective: str | None = None,
        as_of: str | None = None,
        knowledge_cutoff: str | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_reviewability_initialized()
        normalized_as_of = utc_iso(as_of, "UTC") if as_of is not None else None
        normalized_cutoff = (
            utc_iso(knowledge_cutoff, "UTC")
            if knowledge_cutoff is not None
            else None
        )
        with self.connection(read_only=True) as conn:
            records = self._read_validated_operation_checkpoints(conn)
        result: list[dict[str, Any]] = []
        for record in records:
            payload = record.to_dict()
            if episode_id is not None and payload["episode_id"] != episode_id:
                continue
            if (
                position_case_id is not None
                and payload["position_case_id"] != position_case_id
            ):
                continue
            if perspective is not None and payload["perspective"] != perspective:
                continue
            if normalized_as_of is not None and payload["as_of"] > normalized_as_of:
                continue
            if (
                normalized_cutoff is not None
                and payload["knowledge_cutoff"] > normalized_cutoff
            ):
                continue
            result.append(payload)
        result.sort(
            key=lambda item: (
                item["as_of"],
                item["knowledge_cutoff"],
                item["checkpoint_id"],
            )
        )
        return result

    @staticmethod
    def _p2h_payload_json(value: Mapping[str, Any]) -> str:
        return canonical_json_bytes(value).decode("utf-8")

    def save_behavior_hypothesis_candidate(
        self,
        candidate: Mapping[str, Any],
        *,
        source_artifacts: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Create one source-verified candidate or idempotently replay it."""

        self._ensure_p2h_stage1_initialized()
        candidate_id = str(candidate.get("candidate_id") or "")
        canonical_hash = str(candidate.get("canonical_hash") or "")
        payload_json = self._p2h_payload_json(candidate)
        with self.connection() as conn:
            with conn:
                existing = conn.execute(
                    "SELECT canonical_hash, payload_json "
                    "FROM behavior_hypothesis_candidates WHERE candidate_id = ?",
                    (candidate_id,),
                ).fetchone()
                if existing is not None:
                    if (
                        existing["canonical_hash"] == canonical_hash
                        and existing["payload_json"] == payload_json
                    ):
                        return {
                            "candidate_id": candidate_id,
                            "canonical_hash": canonical_hash,
                            "status": "SKIPPED",
                            "source_verification": "verified",
                        }
                    raise DataConflictError(
                        "Behavior hypothesis candidate changed after creation: "
                        f"candidate_id={candidate_id}"
                    )

                validation = replay_validate_behavior_hypothesis_candidate(
                    candidate,
                    source_artifacts=source_artifacts,
                )
                if (
                    validation["validation_status"] != "accepted"
                    or validation["source_verification"]["status"] != "verified"
                ):
                    raise ReviewStoreError(
                        "Behavior hypothesis candidate failed source replay: "
                        + ", ".join(validation["finding_codes"])
                    )
                hash_owner = conn.execute(
                    "SELECT candidate_id FROM behavior_hypothesis_candidates "
                    "WHERE canonical_hash = ?",
                    (canonical_hash,),
                ).fetchone()
                if hash_owner is not None:
                    raise DataConflictError(
                        "Behavior hypothesis canonical hash already belongs to "
                        f"candidate_id={hash_owner['candidate_id']}"
                    )
                scope = candidate["subject_scope"]
                conn.execute(
                    """
                    INSERT INTO behavior_hypothesis_candidates(
                        candidate_id, canonical_hash, created_at, effective_at,
                        knowledge_at, subject_scope_kind, subject_scope_refs_json,
                        pattern_family, source_verification_status, payload_json,
                        inserted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'verified', ?, ?)
                    """,
                    (
                        candidate_id,
                        canonical_hash,
                        candidate["created_at"],
                        candidate["effective_at"],
                        candidate["knowledge_at"],
                        scope["kind"],
                        canonical_json(scope["refs"]),
                        candidate["pattern_family"],
                        payload_json,
                        _now(),
                    ),
                )
        return {
            "candidate_id": candidate_id,
            "canonical_hash": canonical_hash,
            "status": "INSERTED",
            "source_verification": "verified",
        }

    def save_behavior_hypothesis_review_event(
        self, event: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Create one immutable review event or idempotently replay it."""

        self._ensure_p2h_stage1_initialized()
        event_id = str(event.get("review_event_id") or "")
        canonical_hash = str(event.get("canonical_hash") or "")
        candidate_id = str(event.get("candidate_id") or "")
        payload_json = self._p2h_payload_json(event)
        with self.connection() as conn:
            with conn:
                existing = conn.execute(
                    "SELECT canonical_hash, payload_json "
                    "FROM behavior_hypothesis_review_events "
                    "WHERE review_event_id = ?",
                    (event_id,),
                ).fetchone()
                if existing is not None:
                    if (
                        existing["canonical_hash"] == canonical_hash
                        and existing["payload_json"] == payload_json
                    ):
                        return {
                            "review_event_id": event_id,
                            "candidate_id": candidate_id,
                            "canonical_hash": canonical_hash,
                            "status": "SKIPPED",
                        }
                    raise DataConflictError(
                        "Behavior hypothesis review event changed after creation: "
                        f"review_event_id={event_id}"
                    )

                validation = validate_behavior_hypothesis_review_event(event)
                if validation["validation_status"] != "accepted":
                    raise ReviewStoreError(
                        "Behavior hypothesis review event failed validation: "
                        + ", ".join(validation["finding_codes"])
                    )
                candidate_row = conn.execute(
                    "SELECT knowledge_at FROM behavior_hypothesis_candidates "
                    "WHERE candidate_id = ?",
                    (candidate_id,),
                ).fetchone()
                if candidate_row is None:
                    raise ReviewStoreError(
                        f"Behavior hypothesis candidate not found: {candidate_id}"
                    )
                if event["evidence_cutoff"] < candidate_row["knowledge_at"]:
                    raise ReviewStoreError(
                        "Review evidence_cutoff cannot precede candidate knowledge_at"
                    )
                supersedes_event_id = event.get("supersedes_event_id")
                if supersedes_event_id is not None:
                    parent_event = conn.execute(
                        "SELECT candidate_id FROM behavior_hypothesis_review_events "
                        "WHERE review_event_id = ?",
                        (supersedes_event_id,),
                    ).fetchone()
                    if parent_event is None:
                        raise ReviewStoreError(
                            "Superseded review event not found: "
                            f"{supersedes_event_id}"
                        )
                supersedes_candidate_id = event.get("supersedes_candidate_id")
                if supersedes_candidate_id is not None:
                    parent_candidate = conn.execute(
                        "SELECT 1 FROM behavior_hypothesis_candidates "
                        "WHERE candidate_id = ?",
                        (supersedes_candidate_id,),
                    ).fetchone()
                    if parent_candidate is None:
                        raise ReviewStoreError(
                            "Superseded candidate not found: "
                            f"{supersedes_candidate_id}"
                        )
                hash_owner = conn.execute(
                    "SELECT review_event_id "
                    "FROM behavior_hypothesis_review_events "
                    "WHERE canonical_hash = ?",
                    (canonical_hash,),
                ).fetchone()
                if hash_owner is not None:
                    raise DataConflictError(
                        "Behavior hypothesis event canonical hash already belongs to "
                        f"review_event_id={hash_owner['review_event_id']}"
                    )
                conn.execute(
                    """
                    INSERT INTO behavior_hypothesis_review_events(
                        review_event_id, canonical_hash, candidate_id, event_type,
                        reviewed_at, effective_at, knowledge_at, evidence_cutoff,
                        reviewer_ref, supersedes_event_id, supersedes_candidate_id,
                        payload_json, inserted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        canonical_hash,
                        candidate_id,
                        event["event_type"],
                        event["reviewed_at"],
                        event["effective_at"],
                        event["knowledge_at"],
                        event["evidence_cutoff"],
                        event["reviewer_ref"],
                        supersedes_event_id,
                        supersedes_candidate_id,
                        payload_json,
                        _now(),
                    ),
                )
        return {
            "review_event_id": event_id,
            "candidate_id": candidate_id,
            "canonical_hash": canonical_hash,
            "status": "INSERTED",
        }

    def get_behavior_hypothesis_candidate(
        self, candidate_id: str
    ) -> dict[str, Any]:
        self._ensure_p2h_stage1_initialized()
        with self.connection(read_only=True) as conn:
            row = conn.execute(
                "SELECT payload_json FROM behavior_hypothesis_candidates "
                "WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
        if row is None:
            raise ReviewStoreError(
                f"Behavior hypothesis candidate not found: {candidate_id}"
            )
        return json.loads(row["payload_json"])

    def list_behavior_hypothesis_review_events(
        self,
        *,
        candidate_id: str | None = None,
        event_type: str | None = None,
        as_of: str | None = None,
        knowledge_cutoff: str | None = None,
        reviewed_from: str | None = None,
        reviewed_to: str | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_p2h_stage1_initialized()
        filters: list[str] = []
        params: list[Any] = []
        values = {
            "effective_at": (
                _canonical_timestamp(as_of, "as_of") if as_of is not None else None
            ),
            "knowledge_at": (
                _canonical_timestamp(knowledge_cutoff, "knowledge_cutoff")
                if knowledge_cutoff is not None
                else None
            ),
            "reviewed_from": (
                _canonical_timestamp(reviewed_from, "reviewed_from")
                if reviewed_from is not None
                else None
            ),
            "reviewed_to": (
                _canonical_timestamp(reviewed_to, "reviewed_to")
                if reviewed_to is not None
                else None
            ),
        }
        if candidate_id is not None:
            filters.append("candidate_id = ?")
            params.append(candidate_id)
        if event_type is not None:
            filters.append("event_type = ?")
            params.append(event_type)
        if values["effective_at"] is not None:
            filters.append("effective_at <= ?")
            params.append(values["effective_at"])
        if values["knowledge_at"] is not None:
            filters.append("knowledge_at <= ?")
            params.append(values["knowledge_at"])
        if values["reviewed_from"] is not None:
            filters.append("reviewed_at >= ?")
            params.append(values["reviewed_from"])
        if values["reviewed_to"] is not None:
            filters.append("reviewed_at <= ?")
            params.append(values["reviewed_to"])
        where = " WHERE " + " AND ".join(filters) if filters else ""
        with self.connection(read_only=True) as conn:
            rows = conn.execute(
                "SELECT payload_json FROM behavior_hypothesis_review_events"
                + where
                + " ORDER BY effective_at, knowledge_at, reviewed_at, review_event_id",
                params,
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def list_behavior_hypothesis_candidates(
        self,
        *,
        candidate_id: str | None = None,
        status: str | None = None,
        pattern_family: str | None = None,
        scope_kind: str | None = None,
        scope_ref: str | None = None,
        as_of: str | None = None,
        knowledge_cutoff: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query candidates with strict deterministic event-ledger projection."""

        self._ensure_p2h_stage1_initialized()
        filters: list[str] = []
        params: list[Any] = []
        temporal = {
            "effective_at": (
                _canonical_timestamp(as_of, "as_of") if as_of is not None else None
            ),
            "knowledge_at": (
                _canonical_timestamp(knowledge_cutoff, "knowledge_cutoff")
                if knowledge_cutoff is not None
                else None
            ),
            "created_from": (
                _canonical_timestamp(created_from, "created_from")
                if created_from is not None
                else None
            ),
            "created_to": (
                _canonical_timestamp(created_to, "created_to")
                if created_to is not None
                else None
            ),
        }
        for column, value in (
            ("candidate_id", candidate_id),
            ("pattern_family", pattern_family),
            ("subject_scope_kind", scope_kind),
        ):
            if value is not None:
                filters.append(f"{column} = ?")
                params.append(value)
        if temporal["effective_at"] is not None:
            filters.append("effective_at <= ?")
            params.append(temporal["effective_at"])
        if temporal["knowledge_at"] is not None:
            filters.append("knowledge_at <= ?")
            params.append(temporal["knowledge_at"])
        if temporal["created_from"] is not None:
            filters.append("created_at >= ?")
            params.append(temporal["created_from"])
        if temporal["created_to"] is not None:
            filters.append("created_at <= ?")
            params.append(temporal["created_to"])
        where = " WHERE " + " AND ".join(filters) if filters else ""
        with self.connection(read_only=True) as conn:
            rows = conn.execute(
                "SELECT payload_json FROM behavior_hypothesis_candidates"
                + where
                + " ORDER BY created_at, candidate_id",
                params,
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            candidate = json.loads(row["payload_json"])
            if scope_ref is not None and scope_ref not in candidate["subject_scope"]["refs"]:
                continue
            events = self.list_behavior_hypothesis_review_events(
                candidate_id=candidate["candidate_id"],
                as_of=temporal["effective_at"],
                knowledge_cutoff=temporal["knowledge_at"],
            )
            projection = project_behavior_hypothesis_state(
                candidate,
                events,
                as_of=temporal["effective_at"] or "9999-12-31T23:59:59Z",
                knowledge_cutoff=(
                    temporal["knowledge_at"] or "9999-12-31T23:59:59Z"
                ),
            )
            projected_status = projection["status"]
            if status is not None and status != projected_status:
                continue
            result.append(
                {
                    "candidate": candidate,
                    "projected_status": projected_status,
                    "projection": projection,
                    "visible_review_event_ids": [
                        event["review_event_id"] for event in events
                    ],
                }
            )
        return result

    def project_behavior_hypothesis_candidate(
        self,
        candidate_id: str,
        *,
        as_of: str,
        knowledge_cutoff: str,
    ) -> dict[str, Any]:
        candidate = self.get_behavior_hypothesis_candidate(candidate_id)
        events = self.list_behavior_hypothesis_review_events(
            candidate_id=candidate_id,
            as_of=as_of,
            knowledge_cutoff=knowledge_cutoff,
        )
        return project_behavior_hypothesis_state(
            candidate,
            events,
            as_of=as_of,
            knowledge_cutoff=knowledge_cutoff,
        )

    def replay_behavior_hypothesis_candidate(
        self,
        candidate_id: str,
        *,
        source_artifacts: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        return replay_validate_behavior_hypothesis_candidate(
            self.get_behavior_hypothesis_candidate(candidate_id),
            source_artifacts=source_artifacts,
        )

    def save_observation_protocol(
        self,
        protocol: Mapping[str, Any],
        *,
        candidate_source_artifacts: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Create one source-replayed protocol or idempotently replay it."""

        self._ensure_p2h_stage2_slice_a_initialized()
        protocol_id = str(protocol.get("protocol_id") or "")
        canonical_hash = str(protocol.get("canonical_hash") or "")
        binding = protocol.get("candidate_binding")
        if not isinstance(binding, Mapping):
            raise ReviewStoreError("Observation protocol candidate_binding is required")
        candidate_id = str(binding.get("candidate_id") or "")
        payload_json = self._p2h_payload_json(protocol)
        with self.connection(read_only=True) as conn:
            existing_before_replay = conn.execute(
                "SELECT canonical_hash, payload_json "
                "FROM behavior_observation_protocols WHERE protocol_id = ?",
                (protocol_id,),
            ).fetchone()
        if existing_before_replay is not None and (
            existing_before_replay["canonical_hash"] != canonical_hash
            or existing_before_replay["payload_json"] != payload_json
        ):
            raise DataConflictError(
                "Observation protocol changed after creation: "
                f"protocol_id={protocol_id}"
            )
        candidate = self.get_behavior_hypothesis_candidate(candidate_id)
        complete_events = self.list_behavior_hypothesis_review_events(
            candidate_id=candidate_id
        )
        validation = replay_validate_observation_protocol(
            protocol,
            candidate=candidate,
            review_events=complete_events,
            candidate_source_artifacts=candidate_source_artifacts,
        )
        if (
            validation["validation_status"] != "accepted"
            or validation["source_verification"]["status"] != "verified"
        ):
            raise ReviewStoreError(
                "Observation protocol failed Stage 1 source replay: "
                + ", ".join(validation["finding_codes"])
            )

        accepted_projection = binding["accepted_projection"]
        with self.connection() as conn:
            with conn:
                existing = conn.execute(
                    "SELECT canonical_hash, payload_json "
                    "FROM behavior_observation_protocols WHERE protocol_id = ?",
                    (protocol_id,),
                ).fetchone()
                if existing is not None:
                    if (
                        existing["canonical_hash"] == canonical_hash
                        and existing["payload_json"] == payload_json
                    ):
                        return {
                            "protocol_id": protocol_id,
                            "candidate_id": candidate_id,
                            "canonical_hash": canonical_hash,
                            "status": "SKIPPED",
                            "source_verification": "verified",
                        }
                    raise DataConflictError(
                        "Observation protocol changed after creation: "
                        f"protocol_id={protocol_id}"
                    )
                hash_owner = conn.execute(
                    "SELECT protocol_id FROM behavior_observation_protocols "
                    "WHERE canonical_hash = ?",
                    (canonical_hash,),
                ).fetchone()
                if hash_owner is not None:
                    raise DataConflictError(
                        "Observation protocol canonical hash already belongs to "
                        f"protocol_id={hash_owner['protocol_id']}"
                    )
                conn.execute(
                    """
                    INSERT INTO behavior_observation_protocols(
                        protocol_id, canonical_hash, candidate_id, created_at,
                        effective_at, knowledge_at, expiry_at,
                        stage1_event_set_hash, stage1_projection_hash,
                        source_verification_status, payload_json, inserted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'verified', ?, ?)
                    """,
                    (
                        protocol_id,
                        canonical_hash,
                        candidate_id,
                        protocol["created_at"],
                        protocol["effective_at"],
                        protocol["knowledge_at"],
                        protocol["expiry_at"],
                        binding["review_event_set_hash"],
                        accepted_projection["projection_hash"],
                        payload_json,
                        _now(),
                    ),
                )
        return {
            "protocol_id": protocol_id,
            "candidate_id": candidate_id,
            "canonical_hash": canonical_hash,
            "status": "INSERTED",
            "source_verification": "verified",
        }

    def get_observation_protocol(self, protocol_id: str) -> dict[str, Any]:
        self._ensure_p2h_stage2_slice_a_initialized()
        with self.connection(read_only=True) as conn:
            row = conn.execute(
                "SELECT payload_json FROM behavior_observation_protocols "
                "WHERE protocol_id = ?",
                (protocol_id,),
            ).fetchone()
        if row is None:
            raise ReviewStoreError(f"Observation protocol not found: {protocol_id}")
        return json.loads(row["payload_json"])

    def list_observation_protocols(
        self,
        *,
        protocol_id: str | None = None,
        candidate_id: str | None = None,
        status: str | None = None,
        as_of: str | None = None,
        knowledge_cutoff: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_p2h_stage2_slice_a_initialized()
        filters: list[str] = []
        params: list[Any] = []
        for column, value in (
            ("protocol_id", protocol_id),
            ("candidate_id", candidate_id),
        ):
            if value is not None:
                filters.append(f"{column} = ?")
                params.append(value)
        normalized_as_of = (
            _canonical_timestamp(as_of, "as_of") if as_of is not None else None
        )
        normalized_cutoff = (
            _canonical_timestamp(knowledge_cutoff, "knowledge_cutoff")
            if knowledge_cutoff is not None
            else None
        )
        if normalized_as_of is not None:
            filters.append("effective_at <= ?")
            params.append(normalized_as_of)
        if normalized_cutoff is not None:
            filters.append("knowledge_at <= ?")
            params.append(normalized_cutoff)
        if created_from is not None:
            filters.append("created_at >= ?")
            params.append(_canonical_timestamp(created_from, "created_from"))
        if created_to is not None:
            filters.append("created_at <= ?")
            params.append(_canonical_timestamp(created_to, "created_to"))
        where = " WHERE " + " AND ".join(filters) if filters else ""
        with self.connection(read_only=True) as conn:
            rows = conn.execute(
                "SELECT payload_json FROM behavior_observation_protocols"
                + where
                + " ORDER BY created_at, protocol_id",
                params,
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            protocol = json.loads(row["payload_json"])
            events = self.list_observation_protocol_review_events(
                protocol_id=protocol["protocol_id"],
                as_of=normalized_as_of,
                knowledge_cutoff=normalized_cutoff,
            )
            projection = project_observation_protocol_state(
                protocol,
                events,
                as_of=normalized_as_of or "9999-12-31T23:59:59Z",
                knowledge_cutoff=normalized_cutoff or "9999-12-31T23:59:59Z",
            )
            if status is not None and projection["status"] != status:
                continue
            result.append(
                {
                    "protocol": protocol,
                    "projected_status": projection["status"],
                    "projection": projection,
                    "visible_review_event_ids": [
                        event["protocol_review_event_id"] for event in events
                    ],
                }
            )
        return result

    def save_observation_protocol_review_event(
        self, event: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Create one immutable human protocol-lifecycle event."""

        self._ensure_p2h_stage2_slice_a_initialized()
        event_id = str(event.get("protocol_review_event_id") or "")
        canonical_hash = str(event.get("canonical_hash") or "")
        protocol_id = str(event.get("protocol_id") or "")
        payload_json = self._p2h_payload_json(event)
        with self.connection(read_only=True) as conn:
            existing_before_validation = conn.execute(
                "SELECT canonical_hash, payload_json "
                "FROM behavior_observation_protocol_review_events "
                "WHERE protocol_review_event_id = ?",
                (event_id,),
            ).fetchone()
        if existing_before_validation is not None and (
            existing_before_validation["canonical_hash"] != canonical_hash
            or existing_before_validation["payload_json"] != payload_json
        ):
            raise DataConflictError(
                "Observation protocol review event changed after creation: "
                f"protocol_review_event_id={event_id}"
            )
        validation = validate_observation_protocol_review_event(event)
        if validation["validation_status"] != "accepted":
            raise ReviewStoreError(
                "Observation protocol review event failed validation: "
                + ", ".join(validation["finding_codes"])
            )
        with self.connection() as conn:
            with conn:
                existing = conn.execute(
                    "SELECT canonical_hash, payload_json "
                    "FROM behavior_observation_protocol_review_events "
                    "WHERE protocol_review_event_id = ?",
                    (event_id,),
                ).fetchone()
                if existing is not None:
                    if (
                        existing["canonical_hash"] == canonical_hash
                        and existing["payload_json"] == payload_json
                    ):
                        return {
                            "protocol_review_event_id": event_id,
                            "protocol_id": protocol_id,
                            "canonical_hash": canonical_hash,
                            "status": "SKIPPED",
                        }
                    raise DataConflictError(
                        "Observation protocol review event changed after creation: "
                        f"protocol_review_event_id={event_id}"
                    )
                protocol_row = conn.execute(
                    "SELECT effective_at, knowledge_at "
                    "FROM behavior_observation_protocols WHERE protocol_id = ?",
                    (protocol_id,),
                ).fetchone()
                if protocol_row is None:
                    raise ReviewStoreError(
                        f"Observation protocol not found: {protocol_id}"
                    )
                if event["effective_at"] < protocol_row["effective_at"]:
                    raise ReviewStoreError(
                        "Protocol event effective_at cannot precede the protocol"
                    )
                if event["knowledge_at"] < protocol_row["knowledge_at"]:
                    raise ReviewStoreError(
                        "Protocol event knowledge_at cannot precede the protocol"
                    )
                if event["event_type"] != "note_added":
                    concurrent = conn.execute(
                        "SELECT protocol_review_event_id "
                        "FROM behavior_observation_protocol_review_events "
                        "WHERE protocol_id = ? AND event_type != 'note_added' "
                        "AND effective_at = ? AND knowledge_at = ? AND reviewed_at = ?",
                        (
                            protocol_id,
                            event["effective_at"],
                            event["knowledge_at"],
                            event["reviewed_at"],
                        ),
                    ).fetchone()
                    if concurrent is not None:
                        raise ReviewStoreError(
                            "CONCURRENT_PROTOCOL_STATE_EVENTS: another state event "
                            "already uses the same semantic time"
                        )
                supersedes_event_id = event.get("supersedes_event_id")
                if supersedes_event_id is not None:
                    prior = conn.execute(
                        "SELECT protocol_id "
                        "FROM behavior_observation_protocol_review_events "
                        "WHERE protocol_review_event_id = ?",
                        (supersedes_event_id,),
                    ).fetchone()
                    if prior is None or prior["protocol_id"] != protocol_id:
                        raise ReviewStoreError(
                            "Superseded protocol event is missing or belongs to "
                            "another protocol"
                        )
                replacement_id = event.get("superseded_by_protocol_id")
                if replacement_id is not None:
                    replacement = conn.execute(
                        "SELECT 1 FROM behavior_observation_protocols "
                        "WHERE protocol_id = ?",
                        (replacement_id,),
                    ).fetchone()
                    if replacement is None:
                        raise ReviewStoreError(
                            "Replacement observation protocol not found: "
                            f"{replacement_id}"
                        )
                hash_owner = conn.execute(
                    "SELECT protocol_review_event_id "
                    "FROM behavior_observation_protocol_review_events "
                    "WHERE canonical_hash = ?",
                    (canonical_hash,),
                ).fetchone()
                if hash_owner is not None:
                    raise DataConflictError(
                        "Observation protocol event canonical hash already belongs to "
                        f"protocol_review_event_id={hash_owner['protocol_review_event_id']}"
                    )
                conn.execute(
                    """
                    INSERT INTO behavior_observation_protocol_review_events(
                        protocol_review_event_id, canonical_hash, protocol_id,
                        event_type, reviewed_at, effective_at, knowledge_at,
                        evidence_cutoff, reviewer_ref, supersedes_event_id,
                        superseded_by_protocol_id, payload_json, inserted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        canonical_hash,
                        protocol_id,
                        event["event_type"],
                        event["reviewed_at"],
                        event["effective_at"],
                        event["knowledge_at"],
                        event["evidence_cutoff"],
                        event["reviewer_ref"],
                        supersedes_event_id,
                        replacement_id,
                        payload_json,
                        _now(),
                    ),
                )
        return {
            "protocol_review_event_id": event_id,
            "protocol_id": protocol_id,
            "canonical_hash": canonical_hash,
            "status": "INSERTED",
        }

    def list_observation_protocol_review_events(
        self,
        *,
        protocol_id: str | None = None,
        event_type: str | None = None,
        as_of: str | None = None,
        knowledge_cutoff: str | None = None,
        reviewed_from: str | None = None,
        reviewed_to: str | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_p2h_stage2_slice_a_initialized()
        filters: list[str] = []
        params: list[Any] = []
        values = {
            "effective_at": (
                _canonical_timestamp(as_of, "as_of") if as_of is not None else None
            ),
            "knowledge_at": (
                _canonical_timestamp(knowledge_cutoff, "knowledge_cutoff")
                if knowledge_cutoff is not None
                else None
            ),
            "reviewed_from": (
                _canonical_timestamp(reviewed_from, "reviewed_from")
                if reviewed_from is not None
                else None
            ),
            "reviewed_to": (
                _canonical_timestamp(reviewed_to, "reviewed_to")
                if reviewed_to is not None
                else None
            ),
        }
        if protocol_id is not None:
            filters.append("protocol_id = ?")
            params.append(protocol_id)
        if event_type is not None:
            filters.append("event_type = ?")
            params.append(event_type)
        if values["effective_at"] is not None:
            filters.append("effective_at <= ?")
            params.append(values["effective_at"])
        if values["knowledge_at"] is not None:
            filters.append("knowledge_at <= ?")
            params.append(values["knowledge_at"])
        if values["reviewed_from"] is not None:
            filters.append("reviewed_at >= ?")
            params.append(values["reviewed_from"])
        if values["reviewed_to"] is not None:
            filters.append("reviewed_at <= ?")
            params.append(values["reviewed_to"])
        where = " WHERE " + " AND ".join(filters) if filters else ""
        with self.connection(read_only=True) as conn:
            rows = conn.execute(
                "SELECT payload_json "
                "FROM behavior_observation_protocol_review_events"
                + where
                + " ORDER BY effective_at, knowledge_at, reviewed_at, "
                "protocol_review_event_id",
                params,
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def project_observation_protocol(
        self,
        protocol_id: str,
        *,
        as_of: str,
        knowledge_cutoff: str,
    ) -> dict[str, Any]:
        protocol = self.get_observation_protocol(protocol_id)
        events = self.list_observation_protocol_review_events(
            protocol_id=protocol_id,
            as_of=as_of,
            knowledge_cutoff=knowledge_cutoff,
        )
        return project_observation_protocol_state(
            protocol,
            events,
            as_of=as_of,
            knowledge_cutoff=knowledge_cutoff,
        )

    def replay_observation_protocol(
        self,
        protocol_id: str,
        *,
        candidate_source_artifacts: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        protocol = self.get_observation_protocol(protocol_id)
        candidate_id = protocol["candidate_binding"]["candidate_id"]
        return replay_validate_observation_protocol(
            protocol,
            candidate=self.get_behavior_hypothesis_candidate(candidate_id),
            review_events=self.list_behavior_hypothesis_review_events(
                candidate_id=candidate_id
            ),
            candidate_source_artifacts=candidate_source_artifacts,
        )

    def status(self) -> dict[str, Any]:
        self._ensure_initialized()
        with self.connection(read_only=True) as conn:
            tables = {
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            count_tables = [
                table
                for table in [
                    "data_sources",
                    "source_config_versions",
                    "ingest_runs",
                    "ingest_run_events",
                    "trade_events",
                    "decisions",
                    "decision_event_links",
                    "portfolio_snapshots",
                    "position_snapshot_items",
                    "behavior_hypothesis_candidates",
                    "behavior_hypothesis_review_events",
                    "behavior_observation_protocols",
                    "behavior_observation_protocol_review_events",
                ]
                if table in tables
            ]
            product_tables = [
                "fee_profiles",
                "fee_projections",
                "fee_corrections",
                "review_runs",
                "review_run_status_events",
            ]
            count_tables.extend(table for table in product_tables if table in tables)
            reviewability_tables = [
                "operation_review_checkpoints",
                "operation_checkpoint_gaps",
            ]
            count_tables.extend(
                table for table in reviewability_tables if table in tables
            )
            counts = {
                table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in count_tables
            }
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            version_row = conn.execute(
                "SELECT value FROM schema_meta WHERE key='schema_version'"
            ).fetchone()
            p2h_row = conn.execute(
                "SELECT value FROM schema_meta "
                "WHERE key='p2h_stage1_schema_version'"
            ).fetchone()
            p2h_stage2_row = conn.execute(
                "SELECT value FROM schema_meta "
                "WHERE key='p2h_stage2_slice_a_schema_version'"
            ).fetchone()
            product_row = conn.execute(
                "SELECT value FROM schema_meta "
                "WHERE key='product_completion_schema_version'"
            ).fetchone()
            reviewability_row = conn.execute(
                "SELECT value FROM schema_meta "
                "WHERE key='reviewability_schema_version'"
            ).fetchone()
            checkpoint_contract_row = conn.execute(
                "SELECT value FROM schema_meta "
                "WHERE key='reviewability_checkpoint_contract_version'"
            ).fetchone()
            market_policy_row = conn.execute(
                "SELECT value FROM schema_meta "
                "WHERE key='reviewability_market_policy_version'"
            ).fetchone()
            public_information_policy_row = conn.execute(
                "SELECT value FROM schema_meta "
                "WHERE key='reviewability_public_information_policy_version'"
            ).fetchone()
            market_allowlist_row = conn.execute(
                "SELECT value FROM schema_meta "
                "WHERE key='reviewability_market_provider_allowlist_version'"
            ).fetchone()
            market_allowlist_hash_row = conn.execute(
                "SELECT value FROM schema_meta "
                "WHERE key='reviewability_market_provider_allowlist_sha256'"
            ).fetchone()
            reviewability_manifest_row = conn.execute(
                "SELECT value FROM schema_meta "
                "WHERE key='reviewability_schema_manifest_sha256'"
            ).fetchone()
            reviewability_signals = (
                reviewability_row is not None
                or checkpoint_contract_row is not None
                or market_policy_row is not None
                or public_information_policy_row is not None
                or market_allowlist_row is not None
                or market_allowlist_hash_row is not None
                or reviewability_manifest_row is not None
                or bool(_REVIEWABILITY_TABLES.intersection(tables))
            )
            if reviewability_signals:
                self._validate_reviewability_candidate(conn)
        return {
            "database": str(self.path),
            "schema_version": int(version_row[0]) if version_row else None,
            "p2h_stage1_schema_version": int(p2h_row[0]) if p2h_row else None,
            "p2h_stage2_slice_a_schema_version": (
                int(p2h_stage2_row[0]) if p2h_stage2_row else None
            ),
            "product_completion_schema_version": (
                int(product_row[0]) if product_row else None
            ),
            "reviewability_schema_version": (
                int(reviewability_row[0]) if reviewability_row else None
            ),
            "reviewability_checkpoint_contract_version": (
                str(checkpoint_contract_row[0])
                if checkpoint_contract_row
                else None
            ),
            "reviewability_market_policy_version": (
                str(market_policy_row[0]) if market_policy_row else None
            ),
            "reviewability_public_information_policy_version": (
                str(public_information_policy_row[0])
                if public_information_policy_row
                else None
            ),
            "reviewability_market_provider_allowlist_version": (
                str(market_allowlist_row[0]) if market_allowlist_row else None
            ),
            "reviewability_market_provider_allowlist_sha256": (
                str(market_allowlist_hash_row[0])
                if market_allowlist_hash_row
                else None
            ),
            "reviewability_schema_manifest_sha256": (
                str(reviewability_manifest_row[0])
                if reviewability_manifest_row
                else None
            ),
            "integrity_check": integrity,
            "counts": counts,
        }
