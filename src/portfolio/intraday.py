from __future__ import annotations

import hashlib
import importlib
import io
import json
import uuid
from collections import defaultdict
from contextlib import redirect_stdout
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.utils.tushare_client import get_tushare_pro

from .accounting import build_ledger_cycles
from .kline import (
    KLINECHARTS_VERSION,
    TECHNICAL_INDICATOR_NAMES,
    KlineNotFoundError,
)
from .models import (
    Instrument,
    LedgerCycle,
    MinuteBarObservation,
    ZERO,
    decimal_to_text,
    row_decimal,
)
from .store import PortfolioStore


SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
CHART_QUANTUM = Decimal("0.000001")
SUPPORTED_INTRADAY_ASSET_TYPES = {"equity", "etf"}
SOURCE_REASON_CODES = {
    "missing_credentials",
    "permission_denied",
    "empty_response",
    "invalid_response",
    "dependency_missing",
    "network_error",
    "upstream_error",
}


class IntradayFetchError(RuntimeError):
    """分钟行情源均未返回可用数据。"""

    def __init__(self, message: str, provider_attempts: list[dict[str, str]]) -> None:
        super().__init__(message)
        self.provider_attempts = provider_attempts


@dataclass(frozen=True)
class IntradayFetchBatch:
    bars: tuple[MinuteBarObservation, ...]
    frequency_minutes: int
    source: str
    refresh_batch_id: str
    fetched_at: str
    provider_attempts: tuple[dict[str, str], ...] = ()


def _records(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    if isinstance(frame, list):
        return [dict(item) for item in frame]
    if hasattr(frame, "to_dict"):
        return list(frame.to_dict(orient="records"))
    raise ValueError(f"无法识别分钟行情返回类型: {type(frame).__name__}")


def _decimal(value: Any, *, field: str) -> Decimal:
    if value is None or str(value).strip().lower() in {"", "nan", "none"}:
        raise ValueError(f"{field} 缺失")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{field} 数值格式无效") from exc
    if not result.is_finite():
        raise ValueError(f"{field} 必须是有限数值")
    return result


def _bar_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif hasattr(value, "to_pydatetime"):
        parsed = value.to_pydatetime()
    else:
        raw = str(value or "").strip()
        parsed = None
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y%m%d%H%M%S%f",
            "%Y%m%d%H%M%S",
        ):
            try:
                parsed = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            try:
                parsed = datetime.fromisoformat(raw)
            except ValueError as exc:
                raise ValueError("分钟结束时间格式无效") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=SHANGHAI_TZ)
    return parsed.astimezone(SHANGHAI_TZ)


def _session(value: time) -> str | None:
    plain = value.replace(tzinfo=None)
    if time(9, 30) <= plain <= time(11, 30):
        return "am"
    if time(13, 0) <= plain <= time(15, 0):
        return "pm"
    return None


def _reason_code(exc: Exception) -> str:
    text = str(exc).lower()
    if "token" in text or "credential" in text or "凭据" in text:
        return "missing_credentials"
    if "权限" in text or "permission" in text or "积分" in text:
        return "permission_denied"
    if isinstance(exc, (ImportError, ModuleNotFoundError)):
        return "dependency_missing"
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return "network_error"
    if isinstance(exc, ValueError):
        return "invalid_response"
    return "upstream_error"


def _attempt(provider: str, status: str, reason: str = "") -> dict[str, str]:
    result = {"provider": provider, "status": status}
    if reason:
        result["reason"] = reason if reason in SOURCE_REASON_CODES else "upstream_error"
    return result


def _dedupe_key(payload: dict[str, Any]) -> str:
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"minute_bar|{normalized}".encode("utf-8")).hexdigest()


def _chart_number(value: Decimal) -> float:
    return float(value.quantize(CHART_QUANTUM, rounding=ROUND_HALF_UP))


def _read(row: Any, key: str, default: Any = "") -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (IndexError, KeyError):
        return default


def _build_batch(
    instrument: Instrument,
    trade_date: date,
    *,
    frequency_minutes: int,
    source: str,
    records: list[dict[str, Any]],
) -> IntradayFetchBatch:
    if frequency_minutes not in {1, 5}:
        raise ValueError("分钟行情频率只支持 1 或 5 分钟")
    if not records:
        raise LookupError("分钟行情为空")

    parsed: dict[datetime, dict[str, Decimal]] = {}
    for raw in records:
        raw_code = str(raw.get("ts_code") or raw.get("code") or "").strip()
        if raw_code and raw_code.upper() not in {
            instrument.ts_code,
            _baostock_code(instrument.ts_code).upper(),
        }:
            raise ValueError("分钟行情证券代码不匹配")
        end_time = _bar_time(raw.get("trade_time") or raw.get("time"))
        if end_time.date() != trade_date:
            raise ValueError("分钟行情交易日不匹配")
        if _session(end_time.timetz()) is None:
            raise ValueError("分钟行情时间超出 A 股交易时段")
        values = {
            "open": _decimal(raw.get("open"), field="open"),
            "high": _decimal(raw.get("high"), field="high"),
            "low": _decimal(raw.get("low"), field="low"),
            "close": _decimal(raw.get("close"), field="close"),
            "volume_shares": _decimal(
                raw.get("vol", raw.get("volume")), field="volume"
            ),
            "amount_cny": _decimal(raw.get("amount"), field="amount"),
        }
        if any(values[key] <= ZERO for key in ("open", "high", "low", "close")):
            raise ValueError("分钟 OHLC 必须为正")
        if values["volume_shares"] < ZERO or values["amount_cny"] < ZERO:
            raise ValueError("分钟成交量和成交额不能为负")
        if values["high"] < max(
            values["open"], values["close"], values["low"]
        ):
            raise ValueError("分钟最高价关系无效")
        if values["low"] > min(
            values["open"], values["close"], values["high"]
        ):
            raise ValueError("分钟最低价关系无效")
        if end_time in parsed:
            raise ValueError("分钟行情包含重复结束时间")
        parsed[end_time] = values

    refresh_batch_id = str(uuid.uuid4())
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    bars: list[MinuteBarObservation] = []
    for end_time, values in sorted(parsed.items()):
        payload = {
            "ts_code": instrument.ts_code,
            "bar_time": end_time.isoformat(),
            "frequency_minutes": frequency_minutes,
            **{key: decimal_to_text(value) for key, value in values.items()},
            "source": source,
        }
        bars.append(
            MinuteBarObservation(
                ts_code=instrument.ts_code,
                bar_time=end_time,
                frequency_minutes=frequency_minutes,
                source=source,
                refresh_batch_id=refresh_batch_id,
                dedupe_key=_dedupe_key(payload),
                fetched_at=fetched_at,
                **values,
            )
        )
    return IntradayFetchBatch(
        bars=tuple(bars),
        frequency_minutes=frequency_minutes,
        source=source,
        refresh_batch_id=refresh_batch_id,
        fetched_at=fetched_at,
    )


class TushareIntradayProvider:
    def __init__(self, pro: Any) -> None:
        self.pro = pro

    def fetch(self, instrument: Instrument, *, trade_date: date) -> IntradayFetchBatch:
        endpoints = {"equity": "stk_mins", "etf": "etf_mins"}
        endpoint = endpoints.get(instrument.asset_type)
        if endpoint is None:
            raise ValueError("不支持的分钟行情资产类型")
        request = {
            "ts_code": instrument.ts_code,
            "freq": "1min",
            "start_date": f"{trade_date.isoformat()} 09:00:00",
            "end_date": f"{trade_date.isoformat()} 15:30:00",
        }
        frame = getattr(self.pro, endpoint)(
            **request,
            fields="ts_code,trade_time,open,high,low,close,vol,amount",
        )
        return _build_batch(
            instrument,
            trade_date,
            frequency_minutes=1,
            source=f"tushare.{endpoint}",
            records=_records(frame),
        )


def _baostock_code(ts_code: str) -> str:
    code, _, exchange = ts_code.partition(".")
    normalized_exchange = exchange.lower()
    if normalized_exchange not in {"sh", "sz", "bj"}:
        raise ValueError("无法转换 BaoStock 证券代码")
    return f"{normalized_exchange}.{code}"


class BaostockIntradayProvider:
    def __init__(self, module: Any | None = None) -> None:
        self.module = module

    def fetch(self, instrument: Instrument, *, trade_date: date) -> IntradayFetchBatch:
        module = self.module or importlib.import_module("baostock")
        output = io.StringIO()
        with redirect_stdout(output):
            login = module.login()
        if str(login.error_code) != "0":
            raise ConnectionError("BaoStock 登录失败")
        fields = "date,time,code,open,high,low,close,volume,amount,adjustflag"
        try:
            response = module.query_history_k_data_plus(
                _baostock_code(instrument.ts_code),
                fields,
                start_date=trade_date.isoformat(),
                end_date=trade_date.isoformat(),
                frequency="5",
                adjustflag="3",
            )
            if str(response.error_code) != "0":
                raise ConnectionError("BaoStock 分钟行情请求失败")
            records: list[dict[str, Any]] = []
            names = fields.split(",")
            while response.next():
                records.append(dict(zip(names, response.get_row_data(), strict=True)))
        finally:
            with redirect_stdout(output):
                module.logout()
        return _build_batch(
            instrument,
            trade_date,
            frequency_minutes=5,
            source="baostock.history_k_data_plus",
            records=records,
        )


class FallbackIntradayProvider:
    def __init__(
        self,
        providers: list[tuple[str, Any]],
        *,
        initial_attempts: list[dict[str, str]] | None = None,
    ) -> None:
        self.providers = providers
        self.initial_attempts = list(initial_attempts or [])

    def fetch(self, instrument: Instrument, *, trade_date: date) -> IntradayFetchBatch:
        attempts = list(self.initial_attempts)
        for provider_name, provider in self.providers:
            try:
                batch = provider.fetch(instrument, trade_date=trade_date)
            except LookupError:
                attempts.append(_attempt(provider_name, "failed", "empty_response"))
                continue
            except Exception as exc:
                attempts.append(_attempt(provider_name, "failed", _reason_code(exc)))
                continue
            attempts.append(_attempt(provider_name, "success"))
            return replace(batch, provider_attempts=tuple(attempts))
        raise IntradayFetchError("分钟行情源均不可用", attempts)


def build_intraday_provider(
    env_file: str | Path = ".env.local",
) -> FallbackIntradayProvider:
    providers: list[tuple[str, Any]] = []
    attempts: list[dict[str, str]] = []
    try:
        providers.append(
            ("tushare.1m", TushareIntradayProvider(get_tushare_pro(env_file)))
        )
    except Exception as exc:
        attempts.append(_attempt("tushare.1m", "failed", _reason_code(exc)))
    providers.append(("baostock.5m", BaostockIntradayProvider()))
    return FallbackIntradayProvider(providers, initial_attempts=attempts)


class IntradayService:
    def __init__(self, store: PortfolioStore, *, account_id: str = "default") -> None:
        self.store = store
        self.account_id = account_id

    def _context(
        self,
        ts_code: str,
        *,
        cycle_id: str | None,
        as_of: date,
    ) -> tuple[Instrument, LedgerCycle]:
        normalized_code = ts_code.strip().upper()
        instrument = self.store.instrument(normalized_code)
        if instrument is None:
            raise KlineNotFoundError(f"证券未登记: {normalized_code}")
        cycles = [
            item
            for item in build_ledger_cycles(self.store.ledger(self.account_id, as_of))
            if item.ts_code == normalized_code
        ]
        if cycle_id:
            cycle = next((item for item in cycles if item.cycle_id == cycle_id), None)
            if cycle is None:
                raise KlineNotFoundError(
                    f"{normalized_code} 在 {as_of.isoformat()} 前不存在周期 {cycle_id}"
                )
            return instrument, cycle
        active = [item for item in cycles if not item.is_closed]
        if not active:
            raise KlineNotFoundError(
                f"{normalized_code} 当前没有未清仓周期；查看历史清仓需提供 cycle_id"
            )
        return instrument, active[-1]

    @staticmethod
    def _trade_dates(cycle: LedgerCycle, as_of: date) -> list[dict[str, Any]]:
        grouped: dict[date, list[Any]] = defaultdict(list)
        for entry in cycle.entries:
            if str(_read(entry, "event_type")).upper() not in {"BUY", "SELL"}:
                continue
            event_day = date.fromisoformat(str(_read(entry, "event_date")))
            if event_day <= as_of:
                grouped[event_day].append(entry)
        return [
            {
                "trade_date": event_day.isoformat(),
                "trade_count": len(entries),
                "with_time_count": sum(bool(str(_read(item, "event_time")).strip()) for item in entries),
            }
            for event_day, entries in sorted(grouped.items(), reverse=True)
        ]

    @classmethod
    def _resolve_trade_date(
        cls,
        cycle: LedgerCycle,
        selected: date | None,
        as_of: date,
    ) -> date:
        if selected is None:
            trade_dates = cls._trade_dates(cycle, as_of)
            selected = (
                date.fromisoformat(trade_dates[0]["trade_date"])
                if trade_dates
                else min(cycle.closed_on or as_of, as_of)
            )
        if selected > as_of:
            raise ValueError("trade_date 不能晚于 as_of")
        return selected

    @staticmethod
    def _entry_payload(entry: Any) -> dict[str, Any]:
        return {
            "entry_id": _read(entry, "entry_id", None),
            "event_date": str(_read(entry, "event_date")),
            "event_time": str(_read(entry, "event_time")),
            "event_type": str(_read(entry, "event_type")).upper(),
            "ts_code": str(_read(entry, "ts_code")),
            "quantity": decimal_to_text(row_decimal(entry, "quantity")),
            "price": decimal_to_text(row_decimal(entry, "price")),
            "gross_amount": decimal_to_text(row_decimal(entry, "gross_amount")),
            "fees": decimal_to_text(row_decimal(entry, "fees")),
            "total_cost": decimal_to_text(row_decimal(entry, "total_cost")),
            "external_id": str(_read(entry, "external_id")),
            "source_row": _read(entry, "source_row", None),
            "note": str(_read(entry, "note")),
        }

    @staticmethod
    def _operation_groups(
        cycle: LedgerCycle,
        trade_date: date,
        rows: list[dict[str, Any]],
        frequency_minutes: int | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        entries = [
            item
            for item in cycle.entries
            if str(_read(item, "event_type")).upper() in {"BUY", "SELL"}
            and date.fromisoformat(str(_read(item, "event_date"))) == trade_date
        ]
        bars_by_session: dict[str, list[datetime]] = {"am": [], "pm": []}
        for row in rows:
            session = _session(row["bar_time"].timetz())
            if session:
                bars_by_session[session].append(row["bar_time"])

        mapped: dict[tuple[datetime, str], list[Any]] = defaultdict(list)
        unlocated: list[dict[str, Any]] = []
        for entry in entries:
            raw_time = str(_read(entry, "event_time")).strip()
            if not raw_time:
                unlocated.append(
                    {"reason": "missing_event_time", **IntradayService._entry_payload(entry)}
                )
                continue
            try:
                event_clock = datetime.strptime(raw_time, "%H:%M:%S").time()
            except ValueError:
                unlocated.append(
                    {"reason": "invalid_event_time", **IntradayService._entry_payload(entry)}
                )
                continue
            session = _session(event_clock)
            if session is None:
                unlocated.append(
                    {"reason": "outside_session", **IntradayService._entry_payload(entry)}
                )
                continue
            event_datetime = datetime.combine(
                trade_date, event_clock, tzinfo=SHANGHAI_TZ
            )
            target = next(
                (
                    bar_time
                    for bar_time in bars_by_session[session]
                    if bar_time >= event_datetime
                ),
                None,
            )
            if target is None:
                unlocated.append(
                    {"reason": "missing_bar", **IntradayService._entry_payload(entry)}
                )
                continue
            mapped[(target, str(_read(entry, "event_type")).upper())].append(entry)

        labels = {"BUY": "买入", "SELL": "卖出"}
        priority = {"BUY": 0, "SELL": 1}
        groups: list[dict[str, Any]] = []
        for (bar_time, event_type), items in sorted(
            mapped.items(), key=lambda item: (item[0][0], priority[item[0][1]])
        ):
            quantity = sum((row_decimal(item, "quantity") for item in items), ZERO)
            gross = sum((row_decimal(item, "gross_amount") for item in items), ZERO)
            fees = sum((row_decimal(item, "fees") for item in items), ZERO)
            weighted = sum(
                (
                    row_decimal(item, "price") * row_decimal(item, "quantity")
                    for item in items
                ),
                ZERO,
            )
            actual_price = (
                None
                if quantity <= ZERO
                else (gross / quantity if gross > ZERO else weighted / quantity)
            )
            groups.append(
                {
                    "group_id": (
                        f"{cycle.cycle_id}:{bar_time.isoformat()}:{event_type}"
                    ),
                    "event_date": trade_date.isoformat(),
                    "event_type": event_type,
                    "label": labels[event_type],
                    "entry_count": len(items),
                    "quantity": decimal_to_text(quantity),
                    "fees": decimal_to_text(fees),
                    "gross_amount": decimal_to_text(gross),
                    "actual_price": decimal_to_text(actual_price),
                    "marker_price": (
                        _chart_number(actual_price) if actual_price is not None else None
                    ),
                    "mapped_bar_time": bar_time.isoformat(),
                    "timestamp": int(bar_time.timestamp() * 1000),
                    "mapping_status": f"mapped_{frequency_minutes}m_bucket",
                    "entries": [IntradayService._entry_payload(item) for item in items],
                }
            )
        return groups, unlocated

    def get_payload(
        self,
        ts_code: str,
        *,
        trade_date: date | None = None,
        cycle_id: str | None = None,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        target_as_of = as_of or date.today()
        instrument, cycle = self._context(
            ts_code, cycle_id=cycle_id, as_of=target_as_of
        )
        selected_date = self._resolve_trade_date(cycle, trade_date, target_as_of)
        rows, metadata = self.store.latest_minute_bars(
            instrument.ts_code, selected_date
        )
        frequency = int(metadata["frequency_minutes"]) if metadata else None
        operation_groups, unlocated = self._operation_groups(
            cycle, selected_date, rows, frequency
        )
        unsupported = instrument.asset_type not in SUPPORTED_INTRADAY_ASSET_TYPES
        status = "unsupported" if unsupported else ("ready" if rows else "missing")
        attempts = metadata["provider_attempts"] if metadata else []
        mapped_count = sum(item["entry_count"] for item in operation_groups)
        mapping_status = (
            "none"
            if mapped_count == 0
            else ("partial" if unlocated else "complete")
        )
        if selected_date < cycle.opened_on:
            date_scope = "pre_open_context"
        elif cycle.closed_on is not None and selected_date > cycle.closed_on:
            date_scope = "post_close_context"
        else:
            date_scope = "cycle"
        return {
            "view": "intraday",
            "status": status,
            "chart_status": status,
            "instrument": {
                "ts_code": instrument.ts_code,
                "name": instrument.name,
                "asset_type": instrument.asset_type,
                "price_precision": 4,
                "volume_precision": 0,
            },
            "trade_date": selected_date.isoformat(),
            "date_scope": date_scope,
            "period": {
                "type": "minute",
                "span": frequency,
                "label": f"{frequency} 分钟" if frequency else None,
                "as_of": target_as_of.isoformat(),
            },
            "cycle": {
                "cycle_id": cycle.cycle_id,
                "cycle_number": cycle.cycle_number,
                "opened_on": cycle.opened_on.isoformat(),
                "closed_on": cycle.closed_on.isoformat() if cycle.closed_on else None,
                "opening_event_type": cycle.opening_event_type,
                "status": "closed" if cycle.is_closed else "open",
            },
            "available_trade_dates": self._trade_dates(cycle, target_as_of),
            "bars": [
                {
                    "timestamp": int(item["bar_time"].timestamp() * 1000),
                    "bar_time": item["bar_time"].isoformat(),
                    "open": _chart_number(item["open_price"]),
                    "high": _chart_number(item["high_price"]),
                    "low": _chart_number(item["low_price"]),
                    "close": _chart_number(item["close_price"]),
                    "volume": _chart_number(item["volume_shares"]),
                    "turnover": _chart_number(item["amount_cny"]),
                }
                for item in rows
            ],
            "technical_indicators": {
                "available": list(TECHNICAL_INDICATOR_NAMES),
                "default_selected": ["VOL"],
                "intraday_average": {
                    "name": "INTRADAY_AVG",
                    "formula": "cumulative_turnover / cumulative_volume",
                    "zero_volume": "carry_previous_valid_average",
                    "before_first_valid": "empty",
                },
                "calculation": {
                    "mode": "client_side",
                    "engine": "klinecharts",
                    "engine_version": KLINECHARTS_VERSION,
                    "parameter_profile": "library_defaults",
                    "input_period": f"{frequency}m" if frequency else None,
                    "input_price_adjustment": "none",
                    "persisted": False,
                },
                "boundary": "指标和日内均价由原始分钟行情派生，不是交易信号。",
            },
            "operation_groups": operation_groups,
            "unlocated_operations": unlocated,
            "operation_mapping": {
                "status": mapping_status,
                "mapped_count": mapped_count,
                "unlocated_count": len(unlocated),
            },
            "coverage": {
                "bar_count": len(rows),
                "first_bar_time": rows[0]["bar_time"].isoformat() if rows else None,
                "last_bar_time": rows[-1]["bar_time"].isoformat() if rows else None,
                "mapped_operation_count": mapped_count,
                "unlocated_operation_count": len(unlocated),
                "gaps": (
                    [{"code": "MISSING_BARS", "message": "所选日期没有本地分钟行情缓存"}]
                    if not rows and not unsupported
                    else []
                ),
            },
            "source": {
                "provider": metadata["source"] if metadata else None,
                "frequency_minutes": frequency,
                "fetched_at": metadata["fetched_at"] if metadata else None,
                "provider_attempts": attempts,
                "fallback_reason": next(
                    (
                        item.get("reason")
                        for item in attempts
                        if item.get("status") == "failed"
                    ),
                    None,
                ),
            },
            "boundary": "仅展示行情与交割单事实，不构成交易建议。",
        }

    def refresh(
        self,
        provider: Any,
        ts_code: str,
        *,
        trade_date: date,
        cycle_id: str | None = None,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        target_as_of = as_of or date.today()
        instrument, cycle = self._context(
            ts_code, cycle_id=cycle_id, as_of=target_as_of
        )
        selected_date = self._resolve_trade_date(cycle, trade_date, target_as_of)
        if instrument.asset_type not in SUPPORTED_INTRADAY_ASSET_TYPES:
            return self.get_payload(
                instrument.ts_code,
                trade_date=selected_date,
                cycle_id=cycle.cycle_id,
                as_of=target_as_of,
            )
        batch = provider.fetch(instrument, trade_date=selected_date)
        inserted = self.store.add_minute_batch(
            batch.bars,
            trade_date=selected_date,
            frequency_minutes=batch.frequency_minutes,
            source=batch.source,
            refresh_batch_id=batch.refresh_batch_id,
            provider_attempts=list(batch.provider_attempts),
            fetched_at=batch.fetched_at,
        )
        payload = self.get_payload(
            instrument.ts_code,
            trade_date=selected_date,
            cycle_id=cycle.cycle_id,
            as_of=target_as_of,
        )
        payload["refresh"] = {
            "refresh_batch_id": batch.refresh_batch_id,
            "trade_date": selected_date.isoformat(),
            "fetched_bars": len(batch.bars),
            **inserted,
        }
        return payload
