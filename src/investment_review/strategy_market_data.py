"""Bounded, read-only market-data acquisition for strategy validation.

This module deliberately sits outside the formal portfolio database.  It can
read the symbols needed by a strategy run from that database, but every market
response is written only to a caller-selected cache directory.  Provider
credentials and exception messages are never persisted.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .artifact_io import (
    atomic_write_bytes,
    canonical_json_bytes,
    load_json_object,
    pretty_json_bytes,
)
from src.portfolio.models import Instrument, decimal_to_text


CACHE_SCHEMA_VERSION = "investment_review.strategy_market_cache.v1"
EASTMONEY_ENDPOINT = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
TENCENT_ENDPOINT = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
MAX_SYMBOLS_PER_REQUEST = 64
MAX_INDICES_PER_REQUEST = 8
MAX_CALENDAR_DAYS = 4_000
MAX_OBSERVATIONS_PER_SERIES = 5_000
MAX_RESPONSE_BYTES = 5_000_000
MAX_HTTP_TIMEOUT_SECONDS = 30.0


class StrategyMarketDataError(RuntimeError):
    """The bounded market-data request or cache target is unsafe or invalid."""


@dataclass(frozen=True)
class IndexSpec:
    ts_code: str
    name: str = ""


@dataclass(frozen=True)
class EastmoneyFetch:
    rows: tuple[dict[str, str | None], ...]
    endpoint: str
    request: dict[str, str]
    response_sha256: str


@dataclass(frozen=True)
class TencentFetch:
    rows: tuple[dict[str, str | None], ...]
    endpoint: str
    request: dict[str, str]
    response_sha256: str


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_timestamp(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise StrategyMarketDataError("fetched_at is required")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StrategyMarketDataError("fetched_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise StrategyMarketDataError("fetched_at must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _decimal_text(value: Any, *, field: str, optional: bool = False) -> str | None:
    raw = str(value if value is not None else "").strip()
    if raw.lower() in {"", "none", "nan", "null", "-"}:
        if optional:
            return None
        raise StrategyMarketDataError(f"{field} is missing")
    try:
        result = Decimal(raw)
    except InvalidOperation as exc:
        raise StrategyMarketDataError(f"{field} is not numeric") from exc
    if not result.is_finite():
        raise StrategyMarketDataError(f"{field} must be finite")
    return decimal_to_text(result)


def _normalize_ts_code(value: str) -> str:
    raw = str(value or "").strip().upper()
    if raw.startswith(("SH.", "SZ.", "BJ.")):
        exchange, code = raw.split(".", 1)
        raw = f"{code}.{exchange}"
    code, separator, exchange = raw.partition(".")
    if separator != "." or not code.isdigit() or exchange not in {"SH", "SZ", "BJ"}:
        raise StrategyMarketDataError(f"unsupported A-share code: {value!r}")
    return f"{code}.{exchange}"


def _normalize_symbols(symbols: Iterable[Instrument | Mapping[str, Any]]) -> tuple[Instrument, ...]:
    normalized: dict[str, Instrument] = {}
    for raw in symbols:
        if isinstance(raw, Instrument):
            instrument = raw
        else:
            instrument = Instrument(
                ts_code=str(raw.get("ts_code") or ""),
                name=str(raw.get("name") or ""),
                asset_type=str(raw.get("asset_type") or "unknown"),
            )
        code = _normalize_ts_code(instrument.ts_code)
        candidate = Instrument(
            code,
            instrument.name.strip(),
            instrument.asset_type.strip() or "unknown",
        )
        previous = normalized.get(code)
        if previous is not None and previous != candidate:
            raise StrategyMarketDataError(f"conflicting instrument metadata: {code}")
        normalized[code] = candidate
    result = tuple(normalized[key] for key in sorted(normalized))
    if not result:
        raise StrategyMarketDataError("at least one symbol is required")
    if len(result) > MAX_SYMBOLS_PER_REQUEST:
        raise StrategyMarketDataError(
            f"symbol count exceeds bounded limit {MAX_SYMBOLS_PER_REQUEST}"
        )
    return result


def _normalize_indices(
    indices: Iterable[IndexSpec | str | Mapping[str, Any]],
) -> tuple[IndexSpec, ...]:
    normalized: dict[str, IndexSpec] = {}
    for raw in indices:
        if isinstance(raw, IndexSpec):
            spec = raw
        elif isinstance(raw, str):
            spec = IndexSpec(raw)
        else:
            spec = IndexSpec(str(raw.get("ts_code") or ""), str(raw.get("name") or ""))
        code = _normalize_ts_code(spec.ts_code)
        candidate = IndexSpec(code, spec.name.strip())
        previous = normalized.get(code)
        if previous is not None and previous != candidate:
            raise StrategyMarketDataError(f"conflicting index metadata: {code}")
        normalized[code] = candidate
    result = tuple(normalized[key] for key in sorted(normalized))
    if len(result) > MAX_INDICES_PER_REQUEST:
        raise StrategyMarketDataError(
            f"index count exceeds bounded limit {MAX_INDICES_PER_REQUEST}"
        )
    return result


def _validate_window(start_date: date, end_date: date) -> None:
    if start_date > end_date:
        raise StrategyMarketDataError("start_date cannot be later than end_date")
    span = (end_date - start_date).days + 1
    if span > MAX_CALENDAR_DAYS:
        raise StrategyMarketDataError(
            f"date range exceeds bounded limit {MAX_CALENDAR_DAYS} calendar days"
        )


def _resolve_cache_root(cache_root: str | Path, allowed_root: str | Path) -> Path:
    allowed = Path(allowed_root).expanduser().resolve()
    target = Path(cache_root).expanduser().resolve()
    if target == allowed or allowed not in target.parents:
        raise StrategyMarketDataError(
            "cache_root must be a dedicated child directory of allowed_root"
        )
    return target


def _guard_cache_output(target: Path, relative_path: Path) -> Path:
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise StrategyMarketDataError("cache output path is unsafe")
    candidate = target / relative_path
    resolved_parent = candidate.parent.resolve()
    if resolved_parent != target and target not in resolved_parent.parents:
        raise StrategyMarketDataError("cache output parent escapes cache_root")
    if candidate.exists():
        resolved_candidate = candidate.resolve()
        if resolved_candidate != target and target not in resolved_candidate.parents:
            raise StrategyMarketDataError("cache output path escapes cache_root")
    return candidate


def extract_strategy_symbols(
    portfolio_db: str | Path,
    *,
    account_id: str = "default",
    start_date: date | None = None,
    end_date: date,
) -> tuple[Instrument, ...]:
    """Return symbols active at the window start or touched during the window.

    The formal database is opened through an immutable read-only SQLite URI and
    ``query_only`` is enabled as a second guard.  A before/after hash check also
    makes accidental source mutation visible.
    """

    source = Path(portfolio_db).expanduser().resolve()
    if not source.is_file():
        raise StrategyMarketDataError(f"portfolio database does not exist: {source}")
    if start_date is not None and start_date > end_date:
        raise StrategyMarketDataError("start_date cannot be later than end_date")
    before_sha256 = _sha256_file(source)
    uri = source.as_uri() + "?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        query_only = int(connection.execute("PRAGMA query_only").fetchone()[0])
        if query_only != 1:
            raise StrategyMarketDataError("formal database query_only guard is inactive")
        rows = connection.execute(
            """
            SELECT l.entry_id, l.event_date, l.event_type, l.ts_code, l.quantity,
                   i.name, i.asset_type
            FROM ledger_entries AS l
            JOIN instruments AS i ON i.ts_code = l.ts_code
            WHERE l.account_id = ? AND l.event_date <= ?
            ORDER BY l.event_date, l.event_time, l.entry_id
            """,
            (account_id, end_date.isoformat()),
        ).fetchall()
    except sqlite3.Error as exc:
        raise StrategyMarketDataError(
            f"formal database symbol extraction failed: {type(exc).__name__}"
        ) from exc
    finally:
        connection.close()
    after_sha256 = _sha256_file(source)
    if before_sha256 != after_sha256:
        raise StrategyMarketDataError("formal database changed during read-only extraction")

    positions: dict[str, Decimal] = {}
    metadata: dict[str, Instrument] = {}
    required: set[str] = set()
    for row in rows:
        code = _normalize_ts_code(str(row["ts_code"]))
        metadata[code] = Instrument(code, str(row["name"]), str(row["asset_type"]))
        event_day = date.fromisoformat(str(row["event_date"]))
        event_type = str(row["event_type"]).upper()
        quantity = Decimal(str(row["quantity"] or "0"))
        if start_date is None or event_day >= start_date:
            required.add(code)
        if start_date is not None and event_day >= start_date:
            continue
        if event_type in {"OPENING", "BUY"}:
            positions[code] = positions.get(code, Decimal("0")) + quantity
        elif event_type == "SELL":
            positions[code] = positions.get(code, Decimal("0")) - quantity
    required.update(code for code, quantity in positions.items() if quantity != 0)
    return tuple(metadata[code] for code in sorted(required))


def _eastmoney_secid(ts_code: str) -> str:
    code, exchange = _normalize_ts_code(ts_code).split(".", 1)
    market = "1" if exchange == "SH" else "0"
    return f"{market}.{code}"


class EastmoneyKlineProvider:
    """Small public HTTP fallback for unadjusted daily OHLCV."""

    def __init__(
        self,
        fetch_bytes: Callable[[str, float], bytes] | None = None,
        *,
        timeout_seconds: float = 15.0,
    ) -> None:
        if timeout_seconds <= 0 or timeout_seconds > MAX_HTTP_TIMEOUT_SECONDS:
            raise StrategyMarketDataError(
                f"timeout_seconds must be within (0, {MAX_HTTP_TIMEOUT_SECONDS}]"
            )
        self._fetch_bytes = fetch_bytes or self._download
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _download(url: str, timeout_seconds: float) -> bytes:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise StrategyMarketDataError("Eastmoney response exceeds bounded byte limit")
        return payload

    def fetch(self, ts_code: str, *, start_date: date, end_date: date) -> EastmoneyFetch:
        _validate_window(start_date, end_date)
        span = (end_date - start_date).days + 1
        request_fields = {
            "secid": _eastmoney_secid(ts_code),
            "klt": "101",
            "fqt": "0",
            "beg": start_date.strftime("%Y%m%d"),
            "end": end_date.strftime("%Y%m%d"),
            "lmt": str(min(MAX_OBSERVATIONS_PER_SERIES, span + 64)),
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        }
        raw = self._fetch_bytes(
            EASTMONEY_ENDPOINT + "?" + urlencode(request_fields),
            self.timeout_seconds,
        )
        if len(raw) > MAX_RESPONSE_BYTES:
            raise StrategyMarketDataError("Eastmoney response exceeds bounded byte limit")
        response_sha256 = _sha256_bytes(raw)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StrategyMarketDataError("Eastmoney returned invalid JSON") from exc
        if not isinstance(payload, Mapping):
            raise StrategyMarketDataError("Eastmoney response root is malformed")
        data = payload.get("data") or {}
        if not isinstance(data, Mapping):
            raise StrategyMarketDataError("Eastmoney response data is malformed")
        raw_rows = data.get("klines") or []
        if not isinstance(raw_rows, list):
            raise StrategyMarketDataError("Eastmoney kline payload is malformed")
        if len(raw_rows) > MAX_OBSERVATIONS_PER_SERIES:
            raise StrategyMarketDataError("Eastmoney response exceeds bounded row limit")
        rows: dict[str, dict[str, str | None]] = {}
        for raw_row in raw_rows:
            fields = str(raw_row).split(",")
            if len(fields) < 11:
                continue
            trade_date = fields[0]
            try:
                parsed_date = date.fromisoformat(trade_date)
            except ValueError:
                continue
            if not start_date <= parsed_date <= end_date:
                continue
            rows[trade_date] = {
                "trade_date": trade_date,
                "open": _decimal_text(fields[1], field="eastmoney.open"),
                "close": _decimal_text(fields[2], field="eastmoney.close"),
                "high": _decimal_text(fields[3], field="eastmoney.high"),
                "low": _decimal_text(fields[4], field="eastmoney.low"),
                "volume": _decimal_text(fields[5], field="eastmoney.volume", optional=True),
                "volume_unit": "provider_native",
                "amount": _decimal_text(fields[6], field="eastmoney.amount", optional=True),
                "amount_unit": "cny",
                "pct_chg": _decimal_text(fields[8], field="eastmoney.pct_chg", optional=True),
                "adjustment": "raw",
                "source": "eastmoney.push2his.kline",
            }
        return EastmoneyFetch(
            rows=tuple(rows[key] for key in sorted(rows)),
            endpoint=EASTMONEY_ENDPOINT,
            request=dict(sorted(request_fields.items())),
            response_sha256=response_sha256,
        )


def _tencent_code(ts_code: str) -> str:
    code, exchange = _normalize_ts_code(ts_code).split(".", 1)
    return f"{exchange.lower()}{code}"


class TencentKlineProvider:
    """Bounded public Tencent raw-day fallback used after Eastmoney."""

    def __init__(
        self,
        fetch_bytes: Callable[[str, float], bytes] | None = None,
        *,
        timeout_seconds: float = 15.0,
    ) -> None:
        if timeout_seconds <= 0 or timeout_seconds > MAX_HTTP_TIMEOUT_SECONDS:
            raise StrategyMarketDataError(
                f"timeout_seconds must be within (0, {MAX_HTTP_TIMEOUT_SECONDS}]"
            )
        self._fetch_bytes = fetch_bytes or EastmoneyKlineProvider._download
        self.timeout_seconds = timeout_seconds

    def fetch(self, ts_code: str, *, start_date: date, end_date: date) -> TencentFetch:
        _validate_window(start_date, end_date)
        span = (end_date - start_date).days + 1
        provider_code = _tencent_code(ts_code)
        param = ",".join(
            (
                provider_code,
                "day",
                start_date.isoformat(),
                end_date.isoformat(),
                str(min(MAX_OBSERVATIONS_PER_SERIES, span + 64)),
                "",
            )
        )
        request_fields = {"param": param}
        raw = self._fetch_bytes(
            TENCENT_ENDPOINT + "?" + urlencode(request_fields),
            self.timeout_seconds,
        )
        if len(raw) > MAX_RESPONSE_BYTES:
            raise StrategyMarketDataError("Tencent response exceeds bounded byte limit")
        response_sha256 = _sha256_bytes(raw)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StrategyMarketDataError("Tencent returned invalid JSON") from exc
        if not isinstance(payload, Mapping):
            raise StrategyMarketDataError("Tencent response root is malformed")
        data = payload.get("data") or {}
        if not isinstance(data, Mapping):
            raise StrategyMarketDataError("Tencent response data is malformed")
        series = data.get(provider_code) or {}
        if not isinstance(series, Mapping):
            raise StrategyMarketDataError("Tencent symbol payload is malformed")
        raw_rows = series.get("day") or []
        if not isinstance(raw_rows, list):
            raise StrategyMarketDataError("Tencent day payload is malformed")
        if len(raw_rows) > MAX_OBSERVATIONS_PER_SERIES:
            raise StrategyMarketDataError("Tencent response exceeds bounded row limit")
        rows: dict[str, dict[str, str | None]] = {}
        for raw_row in raw_rows:
            if not isinstance(raw_row, (list, tuple)) or len(raw_row) < 6:
                continue
            trade_date = str(raw_row[0])
            try:
                parsed_date = date.fromisoformat(trade_date)
            except ValueError:
                continue
            if not start_date <= parsed_date <= end_date:
                continue
            rows[trade_date] = {
                "trade_date": trade_date,
                "open": _decimal_text(raw_row[1], field="tencent.open"),
                "close": _decimal_text(raw_row[2], field="tencent.close"),
                "high": _decimal_text(raw_row[3], field="tencent.high"),
                "low": _decimal_text(raw_row[4], field="tencent.low"),
                "volume": _decimal_text(raw_row[5], field="tencent.volume", optional=True),
                "volume_unit": "provider_native",
                "amount": (
                    _decimal_text(raw_row[6], field="tencent.amount", optional=True)
                    if len(raw_row) > 6
                    and isinstance(raw_row[6], (str, int, float, Decimal))
                    and not isinstance(raw_row[6], bool)
                    else None
                ),
                "amount_unit": "provider_native",
                "pct_chg": None,
                "adjustment": "raw",
                "source": "tencent.ifzq.fqkline.day",
            }
        return TencentFetch(
            rows=tuple(rows[key] for key in sorted(rows)),
            endpoint=TENCENT_ENDPOINT,
            request=request_fields,
            response_sha256=response_sha256,
        )


def _coverage(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    dates = sorted(str(row["trade_date"]) for row in rows if row.get("trade_date"))
    return {
        "row_count": len(dates),
        "observed_start": dates[0] if dates else None,
        "observed_end": dates[-1] if dates else None,
    }


def _normalized_response_hash(rows: Sequence[Mapping[str, Any]]) -> str:
    return _sha256_bytes(canonical_json_bytes(list(rows)))


def _normalize_public_bars(
    rows: Sequence[Mapping[str, Any]],
    *,
    start_date: date,
    end_date: date,
    source: str,
    volume_unit: str,
    amount_unit: str,
) -> list[dict[str, Any]]:
    if len(rows) > MAX_OBSERVATIONS_PER_SERIES:
        raise StrategyMarketDataError("public provider response exceeds bounded row limit")
    normalized: dict[str, dict[str, Any]] = {}
    for row in rows:
        raw_date = str(row.get("trade_date") or "")
        try:
            trade_date = date.fromisoformat(raw_date)
        except ValueError:
            continue
        if not start_date <= trade_date <= end_date:
            continue
        candidate = {
            "trade_date": raw_date,
            "open": _decimal_text(row.get("open"), field=f"{source}.open"),
            "close": _decimal_text(row.get("close"), field=f"{source}.close"),
            "high": _decimal_text(row.get("high"), field=f"{source}.high"),
            "low": _decimal_text(row.get("low"), field=f"{source}.low"),
            "volume": _decimal_text(row.get("volume"), field=f"{source}.volume", optional=True),
            "volume_unit": volume_unit,
            "amount": _decimal_text(row.get("amount"), field=f"{source}.amount", optional=True),
            "amount_unit": amount_unit,
            "pct_chg": _decimal_text(row.get("pct_chg"), field=f"{source}.pct_chg", optional=True),
            "adjustment": "raw",
            "source": source,
        }
        previous = normalized.get(raw_date)
        if previous is not None and previous != candidate:
            raise StrategyMarketDataError(f"{source} returned conflicting duplicate bars")
        normalized[raw_date] = candidate
    return [normalized[key] for key in sorted(normalized)]


def _validated_sha256(value: Any, *, field: str) -> str:
    raw = str(value or "").strip().lower()
    if len(raw) != 64 or any(character not in "0123456789abcdef" for character in raw):
        raise StrategyMarketDataError(f"{field} must be a SHA-256 digest")
    return raw


def _sanitized_eastmoney_request(value: Mapping[str, Any]) -> dict[str, str]:
    allowed = {
        "secid",
        "klt",
        "fqt",
        "beg",
        "end",
        "lmt",
        "fields1",
        "fields2",
    }
    return {str(key): str(item) for key, item in sorted(value.items()) if str(key) in allowed}


def _sanitized_tencent_request(value: Mapping[str, Any]) -> dict[str, str]:
    return {"param": str(value["param"])} if "param" in value else {}


def _safe_failure(
    source: str,
    endpoint: str,
    request: Mapping[str, str],
    exc: Exception,
) -> dict[str, Any]:
    return {
        "source": source,
        "endpoint": endpoint,
        "request": dict(sorted(request.items())),
        "status": "error",
        "error_type": type(exc).__name__,
    }


def _tushare_request(ts_code: str, start_date: date, end_date: date) -> dict[str, str]:
    return {
        "ts_code": ts_code,
        "start_date": start_date.strftime("%Y%m%d"),
        "end_date": end_date.strftime("%Y%m%d"),
    }


def _safe_tushare_source(value: Any) -> str:
    raw = str(value or "").strip().lower()
    suffix = raw.removeprefix("tushare.")
    if (
        raw.startswith("tushare.")
        and suffix
        and all(character.isalnum() or character == "_" for character in suffix)
    ):
        return raw
    return "tushare.provider"


def _fetch_instrument(
    instrument: Instrument,
    *,
    start_date: date,
    end_date: date,
    close_provider: Any | None,
    kline_provider: Any | None,
    eastmoney_provider: EastmoneyKlineProvider | Any | None,
    tencent_provider: TencentKlineProvider | Any | None,
) -> dict[str, Any]:
    closes: list[dict[str, Any]] = []
    bars: list[dict[str, Any]] = []
    factors: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    request = _tushare_request(instrument.ts_code, start_date, end_date)

    if close_provider is not None:
        try:
            fetched = close_provider.fetch_range(
                instrument, start_date=start_date, end_date=end_date
            )
            if len(fetched) > MAX_OBSERVATIONS_PER_SERIES:
                raise StrategyMarketDataError("Tushare close response exceeds bounded row limit")
            closes = [
                {
                    "trade_date": row.trade_date.isoformat(),
                    "close": decimal_to_text(row.close),
                    "pre_close": decimal_to_text(row.pre_close),
                    "pct_chg": decimal_to_text(row.pct_chg),
                    "source": _safe_tushare_source(row.source),
                }
                for row in sorted(fetched, key=lambda item: item.trade_date)
                if start_date <= row.trade_date <= end_date
            ]
            sources = sorted({str(row["source"]) for row in closes})
            attempts.append(
                {
                    "source": "tushare",
                    "endpoint": ",".join(sources) if sources else "close_provider",
                    "request": request,
                    "status": "success" if closes else "empty",
                    "response_sha256": _normalized_response_hash(closes),
                    "response_hash_basis": "normalized_rows",
                }
            )
        except Exception as exc:  # provider libraries expose heterogeneous errors
            attempts.append(_safe_failure("tushare", "close_provider", request, exc))

    if kline_provider is not None and instrument.asset_type in {"equity", "etf"}:
        try:
            batch = kline_provider.fetch(instrument, start_date=start_date, end_date=end_date)
            if (
                len(batch.bars) > MAX_OBSERVATIONS_PER_SERIES
                or len(batch.factors) > MAX_OBSERVATIONS_PER_SERIES
            ):
                raise StrategyMarketDataError("Tushare kline response exceeds bounded row limit")
            bars = [
                {
                    "trade_date": row.trade_date.isoformat(),
                    "open": decimal_to_text(row.open),
                    "high": decimal_to_text(row.high),
                    "low": decimal_to_text(row.low),
                    "close": decimal_to_text(row.close),
                    "volume": decimal_to_text(row.volume_lots),
                    "volume_unit": "lot",
                    "amount": decimal_to_text(row.amount_k_cny),
                    "amount_unit": "thousand_cny",
                    "adjustment": "raw",
                    "source": _safe_tushare_source(row.source),
                }
                for row in sorted(batch.bars, key=lambda item: item.trade_date)
                if start_date <= row.trade_date <= end_date
            ]
            factors = [
                {
                    "trade_date": row.trade_date.isoformat(),
                    "adj_factor": decimal_to_text(row.adj_factor),
                    "source": _safe_tushare_source(row.source),
                }
                for row in sorted(batch.factors, key=lambda item: item.trade_date)
                if start_date <= row.trade_date <= end_date
            ]
            normalized = {"bars": bars, "adjustment_factors": factors}
            sources = sorted(
                {str(row["source"]) for row in bars} | {str(row["source"]) for row in factors}
            )
            attempts.append(
                {
                    "source": "tushare",
                    "endpoint": ",".join(sources) if sources else "kline_provider",
                    "request": request,
                    "status": "success" if bars else "empty",
                    "response_sha256": _sha256_bytes(canonical_json_bytes(normalized)),
                    "response_hash_basis": "normalized_rows",
                }
            )
        except Exception as exc:  # provider libraries expose heterogeneous errors
            attempts.append(_safe_failure("tushare", "kline_provider", request, exc))

    if not bars and eastmoney_provider is not None:
        eastmoney_request = {
            "ts_code": instrument.ts_code,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "adjustment": "raw",
        }
        try:
            fetched = eastmoney_provider.fetch(
                instrument.ts_code, start_date=start_date, end_date=end_date
            )
            bars = _normalize_public_bars(
                fetched.rows,
                start_date=start_date,
                end_date=end_date,
                source="eastmoney.push2his.kline",
                volume_unit="provider_native",
                amount_unit="cny",
            )
            attempts.append(
                {
                    "source": "eastmoney",
                    "endpoint": EASTMONEY_ENDPOINT,
                    "request": _sanitized_eastmoney_request(fetched.request),
                    "status": "success" if bars else "empty",
                    "response_sha256": _validated_sha256(
                        fetched.response_sha256, field="eastmoney.response_sha256"
                    ),
                    "response_hash_basis": "raw_response_bytes",
                }
            )
        except Exception as exc:  # network clients expose heterogeneous errors
            attempts.append(_safe_failure("eastmoney", EASTMONEY_ENDPOINT, eastmoney_request, exc))

    if not bars and tencent_provider is not None:
        tencent_request = {
            "ts_code": instrument.ts_code,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "adjustment": "raw",
        }
        try:
            fetched = tencent_provider.fetch(
                instrument.ts_code, start_date=start_date, end_date=end_date
            )
            bars = _normalize_public_bars(
                fetched.rows,
                start_date=start_date,
                end_date=end_date,
                source="tencent.ifzq.fqkline.day",
                volume_unit="provider_native",
                amount_unit="provider_native",
            )
            attempts.append(
                {
                    "source": "tencent",
                    "endpoint": TENCENT_ENDPOINT,
                    "request": _sanitized_tencent_request(fetched.request),
                    "status": "success" if bars else "empty",
                    "response_sha256": _validated_sha256(
                        fetched.response_sha256, field="tencent.response_sha256"
                    ),
                    "response_hash_basis": "raw_response_bytes",
                }
            )
        except Exception as exc:  # network clients expose heterogeneous errors
            attempts.append(_safe_failure("tencent", TENCENT_ENDPOINT, tencent_request, exc))

    if not closes and bars:
        closes = [
            {
                "trade_date": str(row["trade_date"]),
                "close": row.get("close"),
                "pre_close": None,
                "pct_chg": row.get("pct_chg"),
                "source": row.get("source"),
            }
            for row in bars
        ]

    closes_by_date = {
        str(row["trade_date"]): Decimal(str(row["close"]))
        for row in closes
        if row.get("close") is not None
    }
    bars_by_date = {
        str(row["trade_date"]): Decimal(str(row["close"]))
        for row in bars
        if row.get("close") is not None
    }
    source_conflicts = [
        trade_date
        for trade_date in sorted(closes_by_date.keys() & bars_by_date.keys())
        if closes_by_date[trade_date] != bars_by_date[trade_date]
    ]

    is_convertible_bond = instrument.ts_code.split(".", 1)[0].startswith(
        ("110", "111", "113", "118", "123", "127", "128")
    )
    if source_conflicts:
        ohlcv_status = "source_conflict"
    elif bars:
        ohlcv_status = "raw_with_adjustment_factors_ready" if factors else "raw_ready"
    elif is_convertible_bond:
        ohlcv_status = "unsupported_or_unavailable"
    else:
        ohlcv_status = "missing"
    return {
        "instrument": {
            "ts_code": instrument.ts_code,
            "name": instrument.name,
            "asset_type": instrument.asset_type,
        },
        "status": "source_conflict" if source_conflicts else "ready" if closes else "missing",
        "close_status": "ready" if closes else "missing",
        "ohlcv_status": ohlcv_status,
        "adjustment_status": (
            "raw_with_factors" if factors else "raw_only" if bars else "unavailable"
        ),
        "close_prices": closes,
        "bars": bars,
        "adjustment_factors": factors,
        "coverage": {
            "close": _coverage(closes),
            "ohlcv": _coverage(bars),
            "adjustment_factor": _coverage(factors),
            "source_conflict_dates": source_conflicts,
        },
        "attempts": attempts,
    }


def _baostock_code(ts_code: str) -> str:
    code, exchange = _normalize_ts_code(ts_code).split(".", 1)
    return f"{exchange.lower()}.{code}"


def _baostock_rows(result: Any) -> list[dict[str, str]]:
    if str(getattr(result, "error_code", "")) not in {"", "0"}:
        raise StrategyMarketDataError("BaoStock query failed")
    fields = list(getattr(result, "fields", []) or [])
    rows: list[dict[str, str]] = []
    while result.next():
        rows.append(dict(zip(fields, list(result.get_row_data()), strict=False)))
        if len(rows) > MAX_OBSERVATIONS_PER_SERIES:
            raise StrategyMarketDataError("BaoStock response exceeds bounded row limit")
    return rows


def _normalize_baostock_bars(
    rows: Sequence[Mapping[str, Any]], start_date: date, end_date: date
) -> list[dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for row in rows:
        raw_date = str(row.get("date") or "")
        try:
            trade_date = date.fromisoformat(raw_date)
        except ValueError:
            continue
        if not start_date <= trade_date <= end_date:
            continue
        normalized[raw_date] = {
            "trade_date": raw_date,
            "open": _decimal_text(row.get("open"), field="baostock.open"),
            "high": _decimal_text(row.get("high"), field="baostock.high"),
            "low": _decimal_text(row.get("low"), field="baostock.low"),
            "close": _decimal_text(row.get("close"), field="baostock.close"),
            "pre_close": _decimal_text(
                row.get("preclose"), field="baostock.preclose", optional=True
            ),
            "volume": _decimal_text(row.get("volume"), field="baostock.volume", optional=True),
            "volume_unit": "share",
            "amount": _decimal_text(row.get("amount"), field="baostock.amount", optional=True),
            "amount_unit": "cny",
            "pct_chg": _decimal_text(row.get("pctChg"), field="baostock.pctChg", optional=True),
            "adjustment": "raw",
            "source": "baostock.query_history_k_data_plus",
        }
    return [normalized[key] for key in sorted(normalized)]


def _fetch_indices(
    indices: Sequence[IndexSpec],
    *,
    start_date: date,
    end_date: date,
    baostock_module: Any | None,
    eastmoney_provider: EastmoneyKlineProvider | Any | None,
    tencent_provider: TencentKlineProvider | Any | None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    login_ok = False
    login_error: Exception | None = None
    if indices and baostock_module is not None:
        try:
            login = baostock_module.login()
            if str(getattr(login, "error_code", "")) not in {"", "0"}:
                raise StrategyMarketDataError("BaoStock login failed")
            login_ok = True
        except Exception as exc:  # provider libraries expose heterogeneous errors
            login_error = exc
    try:
        for spec in indices:
            bars: list[dict[str, Any]] = []
            attempts: list[dict[str, Any]] = []
            provider_code = _baostock_code(spec.ts_code)
            request = {
                "code": provider_code,
                "fields": "date,code,open,high,low,close,preclose,volume,amount,pctChg",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "frequency": "d",
                "adjustflag": "3",
            }
            if login_error is not None:
                attempts.append(
                    _safe_failure(
                        "baostock",
                        "query_history_k_data_plus",
                        request,
                        login_error,
                    )
                )
            elif login_ok:
                try:
                    response = baostock_module.query_history_k_data_plus(
                        provider_code,
                        request["fields"],
                        start_date=request["start_date"],
                        end_date=request["end_date"],
                        frequency="d",
                        adjustflag="3",
                    )
                    bars = _normalize_baostock_bars(_baostock_rows(response), start_date, end_date)
                    attempts.append(
                        {
                            "source": "baostock",
                            "endpoint": "query_history_k_data_plus",
                            "request": request,
                            "status": "success" if bars else "empty",
                            "response_sha256": _normalized_response_hash(bars),
                            "response_hash_basis": "normalized_rows",
                        }
                    )
                except Exception as exc:  # provider libraries expose heterogeneous errors
                    attempts.append(
                        _safe_failure("baostock", "query_history_k_data_plus", request, exc)
                    )
            if not bars and eastmoney_provider is not None:
                fallback_request = {
                    "ts_code": spec.ts_code,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "adjustment": "raw",
                }
                try:
                    fetched = eastmoney_provider.fetch(
                        spec.ts_code, start_date=start_date, end_date=end_date
                    )
                    bars = _normalize_public_bars(
                        fetched.rows,
                        start_date=start_date,
                        end_date=end_date,
                        source="eastmoney.push2his.kline",
                        volume_unit="provider_native",
                        amount_unit="cny",
                    )
                    attempts.append(
                        {
                            "source": "eastmoney",
                            "endpoint": EASTMONEY_ENDPOINT,
                            "request": _sanitized_eastmoney_request(fetched.request),
                            "status": "success" if bars else "empty",
                            "response_sha256": _validated_sha256(
                                fetched.response_sha256,
                                field="eastmoney.response_sha256",
                            ),
                            "response_hash_basis": "raw_response_bytes",
                        }
                    )
                except Exception as exc:  # network clients expose heterogeneous errors
                    attempts.append(
                        _safe_failure("eastmoney", EASTMONEY_ENDPOINT, fallback_request, exc)
                    )
            if not bars and tencent_provider is not None:
                fallback_request = {
                    "ts_code": spec.ts_code,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "adjustment": "raw",
                }
                try:
                    fetched = tencent_provider.fetch(
                        spec.ts_code, start_date=start_date, end_date=end_date
                    )
                    bars = _normalize_public_bars(
                        fetched.rows,
                        start_date=start_date,
                        end_date=end_date,
                        source="tencent.ifzq.fqkline.day",
                        volume_unit="provider_native",
                        amount_unit="provider_native",
                    )
                    attempts.append(
                        {
                            "source": "tencent",
                            "endpoint": TENCENT_ENDPOINT,
                            "request": _sanitized_tencent_request(fetched.request),
                            "status": "success" if bars else "empty",
                            "response_sha256": _validated_sha256(
                                fetched.response_sha256,
                                field="tencent.response_sha256",
                            ),
                            "response_hash_basis": "raw_response_bytes",
                        }
                    )
                except Exception as exc:  # network clients expose heterogeneous errors
                    attempts.append(
                        _safe_failure("tencent", TENCENT_ENDPOINT, fallback_request, exc)
                    )
            results.append(
                {
                    "index": {"ts_code": spec.ts_code, "name": spec.name},
                    "status": "ready" if bars else "missing",
                    "bars": bars,
                    "coverage": _coverage(bars),
                    "attempts": attempts,
                }
            )
    finally:
        if login_ok:
            try:
                baostock_module.logout()
            except Exception:
                pass
    return results


def _validate_existing_manifest(
    manifest: Mapping[str, Any], *, cache_root: Path
) -> list[dict[str, Any]]:
    if manifest.get("schema_version") != CACHE_SCHEMA_VERSION:
        raise StrategyMarketDataError("existing cache manifest has an incompatible schema")
    expected_manifest_sha = _sha256_bytes(
        canonical_json_bytes(
            {key: value for key, value in manifest.items() if key != "manifest_sha256"}
        )
    )
    if manifest.get("manifest_sha256") != expected_manifest_sha:
        raise StrategyMarketDataError("existing cache manifest hash is invalid")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise StrategyMarketDataError("existing cache manifest entries are invalid")
    validated: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise StrategyMarketDataError("existing cache manifest entry is invalid")
        request_sha = str(entry.get("request_sha256") or "")
        artifact_sha = str(entry.get("artifact_sha256") or "")
        relative_path = str(entry.get("path") or "")
        expected = f"entries/{request_sha}.json"
        if (
            len(request_sha) != 64
            or any(character not in "0123456789abcdef" for character in request_sha)
            or len(artifact_sha) != 64
            or any(character not in "0123456789abcdef" for character in artifact_sha)
            or relative_path.replace("\\", "/") != expected
        ):
            raise StrategyMarketDataError("existing cache manifest path is unsafe")
        artifact_path = _guard_cache_output(cache_root, Path(relative_path))
        if not artifact_path.is_file() or _sha256_file(artifact_path) != artifact_sha:
            raise StrategyMarketDataError("existing cache artifact hash is invalid")
        validated.append(
            {
                key: entry[key]
                for key in (
                    "request_sha256",
                    "request",
                    "payload_sha256",
                    "artifact_sha256",
                    "path",
                    "fetched_at",
                    "coverage",
                    "sources",
                )
                if key in entry
            }
        )
    return validated


def build_strategy_market_cache(
    *,
    cache_root: str | Path,
    allowed_root: str | Path,
    symbols: Iterable[Instrument | Mapping[str, Any]],
    indices: Iterable[IndexSpec | str | Mapping[str, Any]] = (),
    start_date: date,
    end_date: date,
    fetched_at: str,
    close_provider: Any | None = None,
    kline_provider: Any | None = None,
    baostock_module: Any | None = None,
    eastmoney_provider: EastmoneyKlineProvider | Any | None = None,
    tencent_provider: TencentKlineProvider | Any | None = None,
) -> dict[str, Any]:
    """Fetch one bounded request and atomically create/update its cache manifest."""

    target = _resolve_cache_root(cache_root, allowed_root)
    _validate_window(start_date, end_date)
    normalized_symbols = _normalize_symbols(symbols)
    normalized_indices = _normalize_indices(indices)
    timestamp = _normalized_timestamp(fetched_at)
    manifest_path = _guard_cache_output(target, Path("manifest.json"))
    existing_entries: list[dict[str, Any]] = []
    if manifest_path.exists():
        existing_entries = _validate_existing_manifest(
            load_json_object(manifest_path), cache_root=target
        )
    if all(
        provider is None
        for provider in (
            close_provider,
            kline_provider,
            baostock_module,
            eastmoney_provider,
            tencent_provider,
        )
    ):
        raise StrategyMarketDataError("at least one market-data provider is required")

    request = {
        "symbols": [
            {
                "ts_code": item.ts_code,
                "name": item.name,
                "asset_type": item.asset_type,
            }
            for item in normalized_symbols
        ],
        "indices": [{"ts_code": item.ts_code, "name": item.name} for item in normalized_indices],
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "limits": {
            "max_symbols": MAX_SYMBOLS_PER_REQUEST,
            "max_indices": MAX_INDICES_PER_REQUEST,
            "max_calendar_days": MAX_CALENDAR_DAYS,
            "max_observations_per_series": MAX_OBSERVATIONS_PER_SERIES,
            "max_response_bytes": MAX_RESPONSE_BYTES,
        },
    }
    request_sha256 = _sha256_bytes(canonical_json_bytes(request))
    instrument_data = [
        _fetch_instrument(
            instrument,
            start_date=start_date,
            end_date=end_date,
            close_provider=close_provider,
            kline_provider=kline_provider,
            eastmoney_provider=eastmoney_provider,
            tencent_provider=tencent_provider,
        )
        for instrument in normalized_symbols
    ]
    index_data = _fetch_indices(
        normalized_indices,
        start_date=start_date,
        end_date=end_date,
        baostock_module=baostock_module,
        eastmoney_provider=eastmoney_provider,
        tencent_provider=tencent_provider,
    )
    payload_material = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "request": request,
        "request_sha256": request_sha256,
        "fetched_at": timestamp,
        "instruments": instrument_data,
        "indices": index_data,
        "coverage": {
            "requested_start": start_date.isoformat(),
            "requested_end": end_date.isoformat(),
            "instrument_ready_count": sum(item["status"] == "ready" for item in instrument_data),
            "instrument_count": len(instrument_data),
            "index_ready_count": sum(item["status"] == "ready" for item in index_data),
            "index_count": len(index_data),
        },
    }
    payload_sha256 = _sha256_bytes(canonical_json_bytes(payload_material))
    artifact = {**payload_material, "payload_sha256": payload_sha256}
    artifact_bytes = pretty_json_bytes(artifact)
    artifact_sha256 = _sha256_bytes(artifact_bytes)
    # One stable file per request bounds cache growth; content integrity remains
    # explicit through payload_sha256 and artifact_sha256 in the manifest.
    relative_path = Path("entries") / f"{request_sha256}.json"
    artifact_path = _guard_cache_output(target, relative_path)
    atomic_write_bytes(artifact_path, artifact_bytes)

    source_receipts = []
    for item in [*instrument_data, *index_data]:
        for attempt in item["attempts"]:
            receipt = {
                key: attempt[key]
                for key in (
                    "source",
                    "endpoint",
                    "status",
                    "response_sha256",
                    "response_hash_basis",
                    "error_type",
                )
                if key in attempt
            }
            if receipt not in source_receipts:
                source_receipts.append(receipt)
    source_receipts.sort(
        key=lambda item: (
            str(item.get("source")),
            str(item.get("endpoint")),
            str(item.get("status")),
            str(item.get("response_sha256")),
        )
    )
    manifest_entry = {
        "request_sha256": request_sha256,
        "request": request,
        "payload_sha256": payload_sha256,
        "artifact_sha256": artifact_sha256,
        "path": relative_path.as_posix(),
        "fetched_at": timestamp,
        "coverage": payload_material["coverage"],
        "sources": source_receipts,
    }
    entries_by_request = {
        str(entry["request_sha256"]): entry
        for entry in existing_entries
        if str(entry.get("request_sha256")) != request_sha256
    }
    entries_by_request[request_sha256] = manifest_entry
    manifest_material = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "updated_at": timestamp,
        "entries": [entries_by_request[key] for key in sorted(entries_by_request)],
    }
    manifest = {
        **manifest_material,
        "manifest_sha256": _sha256_bytes(canonical_json_bytes(manifest_material)),
    }
    atomic_write_bytes(manifest_path, pretty_json_bytes(manifest))
    return {
        "cache_root": target,
        "manifest_path": manifest_path,
        "artifact_path": artifact_path,
        "manifest": manifest,
        "artifact": artifact,
    }


def default_eastmoney_provider() -> EastmoneyKlineProvider:
    """Return the dependency-free public fallback provider."""

    return EastmoneyKlineProvider()


def default_tencent_provider() -> TencentKlineProvider:
    """Return the dependency-free Tencent public fallback provider."""

    return TencentKlineProvider()


def load_baostock_module() -> Any:
    """Import BaoStock lazily so the core module stays dependency-light."""

    return importlib.import_module("baostock")
