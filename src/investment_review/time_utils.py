"""Timestamp parsing helpers.

Every persisted timestamp is normalized to UTC while the input timezone is
kept explicit in source configuration.  The review model keeps both
``occurred_at`` and ``known_at`` to prevent hindsight leakage.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class TimestampError(ValueError):
    """Raised when a source timestamp cannot be parsed safely."""


_FORMATS = (
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y%m%d %H%M%S",
    "%Y%m%d%H%M%S",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y%m%d",
)


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise TimestampError(f"Unknown timezone: {name!r}") from exc


def parse_datetime(value: object, default_timezone: str = "Asia/Shanghai") -> datetime:
    """Parse a supported value and return an aware UTC datetime."""

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    else:
        text = str(value).strip()
        if not text:
            raise TimestampError("Timestamp is empty")

        normalized = text.replace("／", "/").replace("年", "-").replace("月", "-").replace("日", " ").strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"

        parsed = None
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            pass

        if parsed is None:
            for fmt in _FORMATS:
                try:
                    parsed = datetime.strptime(normalized, fmt)
                    break
                except ValueError:
                    continue

        if parsed is None:
            raise TimestampError(f"Unsupported timestamp format: {text!r}")

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_zone(default_timezone))
    return parsed.astimezone(timezone.utc)


def utc_iso(value: object, default_timezone: str = "Asia/Shanghai") -> str:
    """Return an RFC 3339 UTC timestamp using ``Z`` notation."""

    parsed = parse_datetime(value, default_timezone)
    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")


def ensure_known_not_before_occurred(occurred_at: str, known_at: str) -> None:
    occurred = parse_datetime(occurred_at, "UTC")
    known = parse_datetime(known_at, "UTC")
    if known < occurred:
        raise TimestampError(
            f"known_at ({known_at}) cannot be earlier than occurred_at ({occurred_at})"
        )
