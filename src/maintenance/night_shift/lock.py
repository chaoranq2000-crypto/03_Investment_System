"""Single-writer lock with explicit stale-lock recovery."""

from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


class LockError(RuntimeError):
    """Raised when the night-shift single-writer lock cannot be used safely."""


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _parse_timestamp(value: Any, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise LockError(f"lock.{field}: invalid ISO-8601 timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        raise LockError(f"lock.{field}: timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class LockRecord:
    run_id: str
    pid: int
    host: str
    branch: str
    started_at: str
    heartbeat_at: str

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "LockRecord":
        required = {"run_id", "pid", "host", "branch", "started_at", "heartbeat_at"}
        missing = sorted(required - set(value))
        if missing:
            raise LockError(f"lock: missing field(s): {', '.join(missing)}")
        pid = value["pid"]
        if isinstance(pid, bool) or not isinstance(pid, int):
            raise LockError("lock.pid: must be an integer")
        _parse_timestamp(value["started_at"], "started_at")
        _parse_timestamp(value["heartbeat_at"], "heartbeat_at")
        return cls(
            run_id=str(value["run_id"]),
            pid=pid,
            host=str(value["host"]),
            branch=str(value["branch"]),
            started_at=str(value["started_at"]),
            heartbeat_at=str(value["heartbeat_at"]),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "pid": self.pid,
            "host": self.host,
            "branch": self.branch,
            "started_at": self.started_at,
            "heartbeat_at": self.heartbeat_at,
        }


class RunLock:
    def __init__(
        self,
        path: Path,
        *,
        stale_after: timedelta = timedelta(minutes=15),
        now: Callable[[], datetime] = utc_now,
        pid_exists: Callable[[int], bool] = process_exists,
        host: str | None = None,
        pid: int | None = None,
    ) -> None:
        self.path = path
        self.stale_after = stale_after
        self._now = now
        self._pid_exists = pid_exists
        self.host = host or socket.gethostname()
        self.pid = pid if pid is not None else os.getpid()

    def read(self) -> LockRecord:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LockError(f"cannot read existing lock {self.path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise LockError(f"lock {self.path} must contain a JSON object")
        return LockRecord.from_mapping(payload)

    def _is_stale(self, record: LockRecord) -> bool:
        heartbeat = _parse_timestamp(record.heartbeat_at, "heartbeat_at")
        current = self._now()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        timed_out = current.astimezone(timezone.utc) - heartbeat > self.stale_after
        same_host = record.host.casefold() == self.host.casefold()
        return timed_out and same_host and not self._pid_exists(record.pid)

    def _create(self, record: LockRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = (
            json.dumps(record.to_mapping(), ensure_ascii=False, sort_keys=True, indent=2)
            + "\n"
        ).encode("utf-8")
        descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            if self.path.exists():
                self.path.unlink()
            raise

    def acquire(
        self,
        *,
        run_id: str,
        branch: str,
        recover_stale: bool = False,
    ) -> tuple[LockRecord, Path | None]:
        current = self._now()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        timestamp = current.astimezone(timezone.utc).isoformat()
        record = LockRecord(
            run_id=run_id,
            pid=self.pid,
            host=self.host,
            branch=branch,
            started_at=timestamp,
            heartbeat_at=timestamp,
        )
        try:
            self._create(record)
            return record, None
        except FileExistsError:
            existing = self.read()
            if not recover_stale or not self._is_stale(existing):
                raise LockError(
                    f"lock already held by run={existing.run_id} pid={existing.pid} "
                    f"host={existing.host}"
                )
            stale_suffix = _parse_timestamp(
                existing.heartbeat_at, "heartbeat_at"
            ).strftime("%Y%m%dT%H%M%SZ")
            archived = self.path.with_name(
                f"{self.path.name}.stale.{existing.run_id}.{stale_suffix}.json"
            )
            if archived.exists():
                raise LockError(f"stale lock archive already exists: {archived}")
            os.replace(self.path, archived)
            try:
                self._create(record)
            except BaseException:
                if not self.path.exists() and archived.exists():
                    os.replace(archived, self.path)
                raise
            return record, archived

    def heartbeat(self, run_id: str) -> LockRecord:
        current = self.read()
        if current.run_id != run_id:
            raise LockError(
                f"lock belongs to run {current.run_id!r}, not requested run {run_id!r}"
            )
        timestamp = self._now()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        updated = LockRecord(
            run_id=current.run_id,
            pid=current.pid,
            host=current.host,
            branch=current.branch,
            started_at=current.started_at,
            heartbeat_at=timestamp.astimezone(timezone.utc).isoformat(),
        )
        temporary = self.path.with_name(f".{self.path.name}.{self.pid}.tmp")
        if temporary.exists():
            raise LockError(f"heartbeat temporary path already exists: {temporary}")
        temporary.write_text(
            json.dumps(updated.to_mapping(), sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, self.path)
        return updated

    def release(self, run_id: str) -> None:
        current = self.read()
        if current.run_id != run_id:
            raise LockError(
                f"lock belongs to run {current.run_id!r}, not requested run {run_id!r}"
            )
        self.path.unlink()
