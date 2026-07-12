"""Consistent display formatting for R5 reader-facing reports."""

from __future__ import annotations

from datetime import date, datetime


def cny(value: float, *, scale: str = "亿元") -> str:
    divisors = {"亿元": 100_000_000, "百万元": 1_000_000, "万元": 10_000, "元": 1}
    if scale not in divisors:
        raise ValueError(f"unsupported CNY scale: {scale}")
    return f"{value / divisors[scale]:.2f}"


def pct(value: float, decimals: int = 1) -> str:
    if decimals not in (1, 2):
        raise ValueError("percent decimals must be 1 or 2")
    return f"{value:.{decimals}f}%"


def multiple(value: float) -> str:
    return f"{value:.1f}x"


def eps(value: float, decimals: int = 2) -> str:
    if decimals not in (2, 3):
        raise ValueError("EPS decimals must be 2 or 3")
    return f"{value:.{decimals}f}"


def iso_date(value: str | date | datetime) -> str:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    return date.fromisoformat(value).isoformat()
