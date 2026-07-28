"""In-process and CLI runner for lightweight periodic investment reports.

This module installs no operating-system scheduler.  It only coordinates
idempotent report generation inside the current process and records a compact
latest-run status in the existing review sidecar.
"""

from __future__ import annotations

import argparse
import json
import threading
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from zoneinfo import ZoneInfo

from .periodic_reports import (
    PeriodicContextResolver,
    PeriodicReportError,
    PeriodicReportStore,
    _parse_date,
    _read_only_connection,
    generate_daily_range,
    generate_periodic_summaries,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")
PERIODIC_AUTOMATION_META_KEY = "periodic_automation_status"
PERIODIC_AUTOMATION_ENV = "INVESTMENT_REVIEW_PERIODIC_AUTOMATION"
PERIODIC_AUTOMATION_INTERVAL_ENV = (
    "INVESTMENT_REVIEW_PERIODIC_AUTOMATION_INTERVAL_SECONDS"
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _boolean(value: object, *, name: str) -> bool:
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


def _status_counts(items: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        status = str(item.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _compact_daily_result(result: Mapping[str, Any]) -> dict[str, Any]:
    if result.get("status") == "up_to_date":
        return dict(result)
    coverage = [
        {
            "trade_date": item.get("trade_date"),
            "portfolio_reports": item.get("portfolio_reports"),
            "instrument_reports": item.get("instrument_reports"),
            "operation_count": item.get("operation_count"),
            "no_trade_day": item.get("no_trade_day"),
        }
        for item in result.get("coverage", [])
        if isinstance(item, Mapping)
    ]
    receipts = [
        item
        for item in result.get("store_receipts", [])
        if isinstance(item, Mapping)
    ]
    return {
        "status": result.get("status"),
        "period": result.get("period"),
        "report_count": result.get("report_count", 0),
        "coverage": coverage,
        "receipt_status_counts": _status_counts(receipts),
        "context_error_count": len(result.get("context_errors", [])),
    }


def _compact_summary_result(result: Mapping[str, Any]) -> dict[str, Any]:
    if result.get("status") == "not_available":
        return dict(result)
    reports = [
        item for item in result.get("reports", []) if isinstance(item, Mapping)
    ]
    receipts = [
        item
        for item in result.get("store_receipts", [])
        if isinstance(item, Mapping)
    ]
    subject_counts = {"portfolio": 0, "instrument": 0}
    for item in reports:
        subject_type = str(item.get("subject", {}).get("type") or "")
        if subject_type in subject_counts:
            subject_counts[subject_type] += 1
    return {
        "status": result.get("status"),
        "period_type": result.get("period_type"),
        "selected_window": result.get("selected_window"),
        "report_count": result.get("report_count", len(reports)),
        "subject_counts": subject_counts,
        "operation_count": sum(
            int(item.get("operation_count") or 0) for item in reports
        ),
        "daily_source_count": sum(
            int(item.get("daily_source_count") or 0) for item in reports
        ),
        "receipt_status_counts": _status_counts(receipts),
        "orders_executed": False,
        "broker_accessed": False,
    }


@dataclass(frozen=True)
class PeriodicAutomationConfig:
    enabled: bool = True
    interval_seconds: float = 900.0
    startup_catch_up: bool = True


def periodic_automation_config(
    *,
    environ: Mapping[str, str] | None = None,
    enabled_override: bool | None = None,
) -> PeriodicAutomationConfig:
    values = dict(environ or {})
    enabled = (
        bool(enabled_override)
        if enabled_override is not None
        else _boolean(
            values.get(PERIODIC_AUTOMATION_ENV, "1"),
            name=PERIODIC_AUTOMATION_ENV,
        )
    )
    if not enabled:
        return PeriodicAutomationConfig(enabled=False)
    raw_interval = values.get(PERIODIC_AUTOMATION_INTERVAL_ENV, "900")
    try:
        interval = float(raw_interval)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{PERIODIC_AUTOMATION_INTERVAL_ENV} must be numeric"
        ) from exc
    if not 30 <= interval <= 86400:
        raise ValueError(
            f"{PERIODIC_AUTOMATION_INTERVAL_ENV} must be between 30 and 86400"
        )
    return PeriodicAutomationConfig(
        enabled=True,
        interval_seconds=interval,
        startup_catch_up=True,
    )


class PeriodicReportRunner:
    """Generate missing daily reports and due natural summaries idempotently."""

    def __init__(
        self,
        *,
        portfolio_db: str | Path,
        review_db: str | Path,
        repo_root: str | Path | None = None,
        account_id: str = "default",
        context_resolver: PeriodicContextResolver | None = None,
    ) -> None:
        self.portfolio_db = Path(portfolio_db).expanduser().resolve(strict=True)
        self.review_db = Path(review_db).expanduser().resolve(strict=True)
        self.repo_root = (
            Path(repo_root).expanduser().resolve(strict=True)
            if repo_root is not None
            else Path.cwd().resolve()
        )
        if self.portfolio_db == self.review_db:
            raise PeriodicReportError("formal source and review sidecar must differ")
        if not self.review_db.is_relative_to(self.repo_root):
            raise PeriodicReportError(
                "periodic review sidecar must remain inside the selected checkout"
            )
        self.account_id = account_id
        self.context_resolver = context_resolver
        self.store = PeriodicReportStore(self.review_db)
        self.store.initialize()

    def _latest_formal_trade_date(self, through: date) -> date | None:
        with _read_only_connection(self.portfolio_db) as connection:
            row = connection.execute(
                "SELECT MAX(trade_date) FROM close_prices WHERE trade_date <= ?",
                (through.isoformat(),),
            ).fetchone()
        return date.fromisoformat(row[0]) if row is not None and row[0] else None

    def _latest_stored_portfolio_daily_date(self) -> date | None:
        rows = self.store.list(
            subject_type="portfolio",
            subject_id=self.account_id,
            period_type="daily",
            limit=1,
        )
        return _parse_date(rows[0]["period"]["end"]) if rows else None

    @staticmethod
    def _daily_cutoff_day(now: datetime) -> date:
        local = now.astimezone(SHANGHAI)
        if local.timetz().replace(tzinfo=None) < time(15, 10):
            return local.date() - timedelta(days=1)
        return local.date()

    @staticmethod
    def _completed_week(day: date) -> tuple[date, date]:
        days_since_friday = (day.weekday() - 4) % 7
        friday = day - timedelta(days=days_since_friday)
        return friday - timedelta(days=4), friday

    @staticmethod
    def _completed_month(day: date) -> tuple[date, date]:
        current_start = day.replace(day=1)
        previous_end = current_start - timedelta(days=1)
        return previous_end.replace(day=1), previous_end

    def _record_status(self, value: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(value)
        self.store.set_meta(PERIODIC_AUTOMATION_META_KEY, payload)
        return payload

    def status(self) -> dict[str, Any]:
        return self.store.get_json_meta(PERIODIC_AUTOMATION_META_KEY) or {
            "enabled": False,
            "state": "never_run",
            "latest": None,
            "last_success": None,
            "last_failure": None,
            "os_scheduler_installed": False,
        }

    def run_once(
        self,
        *,
        trigger: str,
        now: datetime | None = None,
        start_date: str | date | None = None,
    ) -> dict[str, Any]:
        selected_now = now or _utc_now()
        if selected_now.tzinfo is None or selected_now.utcoffset() is None:
            raise ValueError("periodic runner clock must be timezone-aware")
        started_at = _iso_utc(selected_now)
        running = {
            "enabled": True,
            "state": "running",
            "trigger": str(trigger),
            "started_at": started_at,
            "latest": None,
            "last_success": self.status().get("last_success"),
            "last_failure": self.status().get("last_failure"),
            "os_scheduler_installed": False,
        }
        self._record_status(running)
        try:
            cutoff_day = self._daily_cutoff_day(selected_now)
            latest_trade = self._latest_formal_trade_date(cutoff_day)
            last_stored = self._latest_stored_portfolio_daily_date()
            selected_start = (
                _parse_date(start_date)
                if start_date is not None
                else (
                    last_stored + timedelta(days=1)
                    if last_stored is not None
                    else latest_trade
                )
            )
            daily: dict[str, Any]
            if (
                latest_trade is None
                or selected_start is None
                or selected_start > latest_trade
            ):
                daily = {
                    "status": "up_to_date",
                    "latest_formal_trade_date": (
                        latest_trade.isoformat() if latest_trade else None
                    ),
                    "latest_stored_portfolio_daily_date": (
                        last_stored.isoformat() if last_stored else None
                    ),
                    "report_count": 0,
                }
            else:
                daily = _compact_daily_result(
                    generate_daily_range(
                        portfolio_db=self.portfolio_db,
                        review_db=self.review_db,
                        start_date=selected_start,
                        end_date=latest_trade,
                        output_dir=None,
                        account_id=self.account_id,
                        context_resolver=self.context_resolver,
                    )
                )

            summaries: list[dict[str, Any]] = []
            week_start, week_end = self._completed_week(cutoff_day)
            month_start, month_end = self._completed_month(cutoff_day)
            for period_type, period_start, period_end in (
                ("weekly", week_start, week_end),
                ("monthly", month_start, month_end),
            ):
                try:
                    result = generate_periodic_summaries(
                        review_db=self.review_db,
                        period_type=period_type,
                        start_date=period_start,
                        end_date=period_end,
                    )
                except PeriodicReportError as exc:
                    if "no stored daily reports" not in str(exc):
                        raise
                    result = {
                        "status": "not_available",
                        "period_type": period_type,
                        "selected_window": {
                            "start": period_start.isoformat(),
                            "end": period_end.isoformat(),
                        },
                        "report_count": 0,
                        "reason": str(exc),
                    }
                summaries.append(_compact_summary_result(result))
            completed_at = _iso_utc(_utc_now())
            latest = {
                "status": "succeeded",
                "trigger": str(trigger),
                "started_at": started_at,
                "completed_at": completed_at,
                "daily": daily,
                "summaries": summaries,
                "orders_executed": False,
                "broker_accessed": False,
            }
            return self._record_status(
                {
                    "enabled": True,
                    "state": "succeeded",
                    "latest": latest,
                    "last_success": latest,
                    "last_failure": running.get("last_failure"),
                    "os_scheduler_installed": False,
                }
            )
        except Exception as exc:
            failed_at = _iso_utc(_utc_now())
            failure = {
                "status": "failed",
                "trigger": str(trigger),
                "started_at": started_at,
                "completed_at": failed_at,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            return self._record_status(
                {
                    "enabled": True,
                    "state": "failed",
                    "latest": failure,
                    "last_success": running.get("last_success"),
                    "last_failure": failure,
                    "os_scheduler_installed": False,
                }
            )


class PeriodicReportAutomationCoordinator:
    """Small process-local loop; it never installs a scheduler or service."""

    def __init__(
        self,
        *,
        portfolio_db: str | Path,
        review_db: str | Path,
        repo_root: str | Path | None = None,
        account_id: str = "default",
        config: PeriodicAutomationConfig | None = None,
        clock: Callable[[], datetime] | None = None,
        runner: PeriodicReportRunner | None = None,
    ) -> None:
        self.config = config or PeriodicAutomationConfig()
        self.clock = clock or _utc_now
        self.runner = runner or PeriodicReportRunner(
            portfolio_db=portfolio_db,
            review_db=review_db,
            repo_root=repo_root,
            account_id=account_id,
        )
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._run_count = 0

    def run_once(self, *, trigger: str = "manual") -> dict[str, Any]:
        if not self.config.enabled:
            return self.status()
        if not self._lock.acquire(blocking=False):
            value = self.status()
            value["state"] = "running"
            return value
        try:
            result = self.runner.run_once(
                trigger=trigger,
                now=self.clock(),
            )
            self._run_count += 1
            return result
        finally:
            self._lock.release()

    def request(self) -> dict[str, Any]:
        if self.config.enabled:
            self._wake.set()
        return self.status()

    def _worker(self) -> None:
        if self.config.startup_catch_up and not self._stop.is_set():
            self.run_once(trigger="startup_catch_up")
        while not self._stop.is_set():
            self._wake.wait(self.config.interval_seconds)
            self._wake.clear()
            if not self._stop.is_set():
                self.run_once(trigger="periodic_check")

    def start(self) -> dict[str, Any]:
        if not self.config.enabled:
            return self.status()
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._worker,
                name="investment-review-periodic-reports",
                daemon=True,
            )
            self._thread.start()
        return self.status()

    def stop(self, *, timeout: float = 30.0) -> dict[str, Any]:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        return self.status()

    def status(self) -> dict[str, Any]:
        stored = self.runner.status()
        return {
            **stored,
            "enabled": self.config.enabled,
            "worker_alive": bool(self._thread and self._thread.is_alive()),
            "run_count": self._run_count,
            "interval_seconds": self.config.interval_seconds,
            "os_scheduler_installed": False,
        }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portfolio-db", required=True)
    parser.add_argument("--review-db", required=True)
    parser.add_argument("--repo-root")
    parser.add_argument("--account", default="default")
    parser.add_argument("--as-of")
    parser.add_argument("--start-date")
    parser.add_argument("--trigger", default="cli_catch_up")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    selected_now = (
        datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
        if args.as_of
        else _utc_now()
    )
    runner = PeriodicReportRunner(
        portfolio_db=args.portfolio_db,
        review_db=args.review_db,
        repo_root=args.repo_root,
        account_id=args.account,
    )
    result = runner.run_once(
        trigger=args.trigger,
        now=selected_now,
        start_date=args.start_date,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("state") == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
