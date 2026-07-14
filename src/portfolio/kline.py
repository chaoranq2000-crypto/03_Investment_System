from __future__ import annotations

import hashlib
import json
import uuid
from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
from zoneinfo import ZoneInfo

from .accounting import build_ledger_cycles
from .models import (
    AdjustmentFactorObservation,
    DailyBarObservation,
    Instrument,
    LedgerCycle,
    ZERO,
    decimal_to_text,
    row_decimal,
)
from .store import PortfolioStore


VALID_KLINE_RANGES = {"3m", "1y", "cycle"}
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
CHART_QUANTUM = Decimal("0.000001")
KLINECHARTS_VERSION = "10.0.0"
TECHNICAL_INDICATOR_NAMES = (
    "VOL",
    "OBV",
    "VR",
    "EMV",
    "PVT",
    "AVP",
    "MACD",
    "DMI",
    "DMA",
    "TRIX",
    "SAR",
    "BBI",
    "KDJ",
    "RSI",
    "WR",
    "BIAS",
    "CCI",
    "MTM",
    "ROC",
    "PSY",
    "AO",
    "MA",
    "EMA",
    "SMA",
    "BOLL",
    "CR",
    "BRAR",
)


class KlineFetchError(RuntimeError):
    """K 线或复权因子的上游响应不可用。"""


class KlineNotFoundError(LookupError):
    """证券或持仓周期不存在。"""


class KlineRefreshBusyError(RuntimeError):
    """另一个显式刷新任务正在运行。"""


def _records(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    if isinstance(frame, list):
        return [dict(item) for item in frame]
    if hasattr(frame, "to_dict"):
        return list(frame.to_dict(orient="records"))
    raise KlineFetchError(f"无法识别 Tushare 返回类型: {type(frame).__name__}")


def _decimal(value: Any, *, field: str) -> Decimal:
    if value is None or str(value).strip().lower() in {"", "nan", "none"}:
        raise KlineFetchError(f"{field} 缺失")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise KlineFetchError(f"{field} 数值格式无效: {value!r}") from exc
    if not result.is_finite():
        raise KlineFetchError(f"{field} 必须是有限数值: {value!r}")
    return result


def _trade_date(value: Any, *, field: str = "trade_date") -> date:
    raw = str(value or "").strip().replace("-", "")
    if len(raw) != 8 or not raw.isdigit():
        raise KlineFetchError(f"{field} 格式无效: {value!r}")
    return datetime.strptime(raw, "%Y%m%d").date()


def _dedupe_key(kind: str, payload: dict[str, Any]) -> str:
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{kind}|{normalized}".encode("utf-8")).hexdigest()


def _shift_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def _timestamp_ms(value: date) -> int:
    localized = datetime.combine(value, time.min, tzinfo=SHANGHAI_TZ)
    return int(localized.timestamp() * 1000)


def _chart_number(value: Decimal) -> float:
    return float(value.quantize(CHART_QUANTUM, rounding=ROUND_HALF_UP))


def _read(row: Any, key: str, default: Any = "") -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (IndexError, KeyError):
        return default


@dataclass(frozen=True)
class KlineFetchBatch:
    bars: tuple[DailyBarObservation, ...]
    factors: tuple[AdjustmentFactorObservation, ...]
    refresh_batch_id: str
    fetched_at: str
    bar_source: str
    factor_source: str


class TushareKlineProvider:
    def __init__(self, pro: Any) -> None:
        self.pro = pro

    @staticmethod
    def _endpoints(instrument: Instrument) -> tuple[str, str]:
        if instrument.asset_type == "equity":
            return "daily", "adj_factor"
        if instrument.asset_type == "etf":
            return "fund_daily", "fund_adj"
        raise KlineFetchError(
            f"{instrument.ts_code} 的资产类型为 {instrument.asset_type!r}，"
            "无法确定股票或 ETF 复权接口"
        )

    def fetch(
        self,
        instrument: Instrument,
        *,
        start_date: date,
        end_date: date,
    ) -> KlineFetchBatch:
        if start_date > end_date:
            raise ValueError("K 线开始日期不能晚于结束日期")
        bar_endpoint_name, factor_endpoint_name = self._endpoints(instrument)
        request = {
            "ts_code": instrument.ts_code,
            "start_date": start_date.strftime("%Y%m%d"),
            "end_date": end_date.strftime("%Y%m%d"),
        }
        try:
            bar_frame = getattr(self.pro, bar_endpoint_name)(
                **request,
                fields="ts_code,trade_date,open,high,low,close,vol,amount",
            )
        except Exception as exc:  # Tushare SDK 对接口错误统一抛 Exception
            raise KlineFetchError(
                f"{instrument.ts_code} {bar_endpoint_name} 调用失败: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        try:
            factor_frame = getattr(self.pro, factor_endpoint_name)(
                **request,
                fields="ts_code,trade_date,adj_factor",
            )
        except Exception as exc:  # Tushare SDK 对接口错误统一抛 Exception
            raise KlineFetchError(
                f"{instrument.ts_code} {factor_endpoint_name} 调用失败: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        parsed_bars: dict[date, dict[str, Decimal]] = {}
        for raw in _records(bar_frame):
            trade_day = _trade_date(raw.get("trade_date"))
            if not start_date <= trade_day <= end_date:
                continue
            values = {
                "open": _decimal(raw.get("open"), field=f"{trade_day} open"),
                "high": _decimal(raw.get("high"), field=f"{trade_day} high"),
                "low": _decimal(raw.get("low"), field=f"{trade_day} low"),
                "close": _decimal(raw.get("close"), field=f"{trade_day} close"),
                "volume_lots": _decimal(raw.get("vol"), field=f"{trade_day} vol"),
                "amount_k_cny": _decimal(raw.get("amount"), field=f"{trade_day} amount"),
            }
            if any(values[key] <= ZERO for key in ("open", "high", "low", "close")):
                raise KlineFetchError(f"{instrument.ts_code} {trade_day} OHLC 必须为正")
            if values["volume_lots"] < ZERO or values["amount_k_cny"] < ZERO:
                raise KlineFetchError(
                    f"{instrument.ts_code} {trade_day} 成交量和成交额不能为负"
                )
            if values["high"] < max(values["open"], values["close"], values["low"]):
                raise KlineFetchError(f"{instrument.ts_code} {trade_day} 最高价关系无效")
            if values["low"] > min(values["open"], values["close"], values["high"]):
                raise KlineFetchError(f"{instrument.ts_code} {trade_day} 最低价关系无效")
            previous = parsed_bars.get(trade_day)
            if previous is not None and previous != values:
                raise KlineFetchError(
                    f"{instrument.ts_code} {trade_day} 返回了冲突的重复 K 线"
                )
            parsed_bars[trade_day] = values

        parsed_factors: dict[date, Decimal] = {}
        for raw in _records(factor_frame):
            trade_day = _trade_date(raw.get("trade_date"))
            if not start_date <= trade_day <= end_date:
                continue
            factor = _decimal(raw.get("adj_factor"), field=f"{trade_day} adj_factor")
            if factor <= ZERO:
                raise KlineFetchError(
                    f"{instrument.ts_code} {trade_day} 复权因子必须为正"
                )
            previous = parsed_factors.get(trade_day)
            if previous is not None and previous != factor:
                raise KlineFetchError(
                    f"{instrument.ts_code} {trade_day} 返回了冲突的复权因子"
                )
            parsed_factors[trade_day] = factor

        missing_factors = sorted(set(parsed_bars) - set(parsed_factors))
        if missing_factors:
            preview = ", ".join(item.isoformat() for item in missing_factors[:10])
            suffix = "…" if len(missing_factors) > 10 else ""
            raise KlineFetchError(
                f"{instrument.ts_code} 缺少 {len(missing_factors)} 个交易日的复权因子: "
                f"{preview}{suffix}"
            )

        refresh_batch_id = str(uuid.uuid4())
        fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        bar_source = f"tushare.{bar_endpoint_name}"
        factor_source = f"tushare.{factor_endpoint_name}"
        bars: list[DailyBarObservation] = []
        for trade_day, values in sorted(parsed_bars.items()):
            payload = {
                "ts_code": instrument.ts_code,
                "trade_date": trade_day.isoformat(),
                **{key: decimal_to_text(value) for key, value in values.items()},
                "source": bar_source,
            }
            bars.append(
                DailyBarObservation(
                    ts_code=instrument.ts_code,
                    trade_date=trade_day,
                    source=bar_source,
                    refresh_batch_id=refresh_batch_id,
                    dedupe_key=_dedupe_key("daily_bar", payload),
                    fetched_at=fetched_at,
                    **values,
                )
            )

        factors: list[AdjustmentFactorObservation] = []
        for trade_day, factor in sorted(parsed_factors.items()):
            payload = {
                "ts_code": instrument.ts_code,
                "trade_date": trade_day.isoformat(),
                "adj_factor": decimal_to_text(factor),
                "source": factor_source,
            }
            factors.append(
                AdjustmentFactorObservation(
                    ts_code=instrument.ts_code,
                    trade_date=trade_day,
                    adj_factor=factor,
                    source=factor_source,
                    refresh_batch_id=refresh_batch_id,
                    dedupe_key=_dedupe_key("adjustment_factor", payload),
                    fetched_at=fetched_at,
                )
            )
        return KlineFetchBatch(
            bars=tuple(bars),
            factors=tuple(factors),
            refresh_batch_id=refresh_batch_id,
            fetched_at=fetched_at,
            bar_source=bar_source,
            factor_source=factor_source,
        )


class KlineService:
    def __init__(self, store: PortfolioStore, *, account_id: str = "default") -> None:
        self.store = store
        self.account_id = account_id

    @staticmethod
    def _validate_range(range_key: str) -> str:
        normalized = range_key.strip().lower()
        if normalized not in VALID_KLINE_RANGES:
            raise ValueError("range 必须是 3m、1y 或 cycle")
        return normalized

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
    def _fetch_window(cycle: LedgerCycle, range_key: str, as_of: date) -> tuple[date, date]:
        if cycle.closed_on is None:
            end_date = as_of
        else:
            end_date = min(as_of, cycle.closed_on + timedelta(days=90))
        if range_key == "cycle":
            return cycle.opened_on - timedelta(days=180), end_date
        months = 3 if range_key == "3m" else 12
        anchor = cycle.closed_on if cycle.closed_on is not None else end_date
        return _shift_months(anchor, -months) - timedelta(days=30), end_date

    @staticmethod
    def _select_display_bars(
        rows: list[dict[str, Any]],
        cycle: LedgerCycle,
        range_key: str,
        as_of: date,
    ) -> tuple[list[dict[str, Any]], date, date, int, int]:
        eligible = [item for item in rows if item["trade_date"] <= as_of]
        if not eligible:
            start, end = KlineService._fetch_window(cycle, range_key, as_of)
            return [], start, end, 0, 0

        if cycle.closed_on is None:
            effective_end = eligible[-1]["trade_date"]
        else:
            through_close = [
                item for item in eligible if item["trade_date"] <= cycle.closed_on
            ]
            after_close = [
                item for item in eligible if item["trade_date"] > cycle.closed_on
            ][:20]
            bounded = [*through_close, *after_close]
            effective_end = (
                bounded[-1]["trade_date"] if bounded else min(cycle.closed_on, as_of)
            )
            eligible = [item for item in eligible if item["trade_date"] <= effective_end]

        if range_key == "cycle":
            before_open = [
                item for item in eligible if item["trade_date"] < cycle.opened_on
            ][-60:]
            from_open = [
                item for item in eligible if item["trade_date"] >= cycle.opened_on
            ]
            selected = [*before_open, *from_open]
            desired_start = (
                before_open[0]["trade_date"] if before_open else cycle.opened_on
            )
        else:
            desired_start = _shift_months(effective_end, -3 if range_key == "3m" else -12)
            selected = [
                item for item in eligible if item["trade_date"] >= desired_start
            ]
            if (
                cycle.opening_event_type == "OPENING"
                and desired_start <= cycle.opened_on <= effective_end
                and not any(item["trade_date"] == cycle.opened_on for item in selected)
            ):
                prior = [
                    item for item in eligible if item["trade_date"] < cycle.opened_on
                ]
                if prior and prior[-1] not in selected:
                    selected.insert(0, prior[-1])
                    desired_start = prior[-1]["trade_date"]

        pre_open_count = sum(
            item["trade_date"] < cycle.opened_on for item in selected
        )
        post_close_count = (
            sum(item["trade_date"] > cycle.closed_on for item in selected)
            if cycle.closed_on is not None
            else 0
        )
        return selected, desired_start, effective_end, pre_open_count, post_close_count

    @staticmethod
    def _operation_groups(
        cycle: LedgerCycle,
        display_rows: list[dict[str, Any]],
        factor_map: dict[date, Decimal],
        anchor_factor: Decimal | None,
        desired_start: date,
        effective_end: date,
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        grouped: dict[tuple[date, str], list[Any]] = defaultdict(list)
        for entry in cycle.entries:
            event_type = str(_read(entry, "event_type")).upper()
            if event_type not in {"OPENING", "BUY", "SELL"}:
                continue
            event_day = date.fromisoformat(str(_read(entry, "event_date")))
            grouped[(event_day, event_type)].append(entry)

        rows_by_date = {item["trade_date"]: item for item in display_rows}
        display_dates = sorted(rows_by_date)
        labels = {"OPENING": "期初", "BUY": "买入", "SELL": "卖出"}
        priority = {"OPENING": 0, "BUY": 1, "SELL": 2}
        result: list[dict[str, Any]] = []
        gaps: list[dict[str, str]] = []

        for (event_day, event_type), entries in sorted(
            grouped.items(), key=lambda item: (item[0][0], priority[item[0][1]])
        ):
            total_quantity = sum((row_decimal(item, "quantity") for item in entries), ZERO)
            total_fees = sum((row_decimal(item, "fees") for item in entries), ZERO)
            total_gross = sum((row_decimal(item, "gross_amount") for item in entries), ZERO)
            total_cost = sum((row_decimal(item, "total_cost") for item in entries), ZERO)
            if total_quantity <= ZERO:
                actual_price = None
            elif event_type == "OPENING":
                actual_price = total_cost / total_quantity
            elif total_gross > ZERO:
                actual_price = total_gross / total_quantity
            else:
                weighted = sum(
                    (
                        row_decimal(item, "price") * row_decimal(item, "quantity")
                        for item in entries
                    ),
                    ZERO,
                )
                actual_price = weighted / total_quantity

            in_range = desired_start <= event_day <= effective_end
            if (
                event_type == "OPENING"
                and display_dates
                and desired_start <= event_day
                and effective_end < event_day
                and event_day - display_dates[-1] <= timedelta(days=7)
            ):
                # 期初快照可能落在周末/休市日；允许映射到此前最近一根日 K。
                in_range = True
            mapped_day: date | None = None
            mapping_status = "outside_range"
            if in_range and event_type == "OPENING":
                candidates = [item for item in display_dates if item <= event_day]
                if candidates:
                    mapped_day = candidates[-1]
                    mapping_status = "mapped_previous_bar" if mapped_day != event_day else "exact"
                else:
                    mapping_status = "missing_bar"
            elif in_range:
                if event_day in rows_by_date:
                    mapped_day = event_day
                    mapping_status = "exact"
                else:
                    mapping_status = "missing_bar"

            adjusted_price: Decimal | None = None
            if mapped_day is not None and actual_price is not None:
                factor = factor_map.get(mapped_day)
                if factor is None or anchor_factor is None:
                    mapping_status = "missing_factor"
                else:
                    adjusted_price = actual_price * factor / anchor_factor

            if in_range and mapping_status in {"missing_bar", "missing_factor"}:
                gaps.append(
                    {
                        "code": mapping_status.upper(),
                        "date": event_day.isoformat(),
                        "event_type": event_type,
                    }
                )

            original_entries = []
            for entry in entries:
                original_entries.append(
                    {
                        "entry_id": _read(entry, "entry_id", None),
                        "event_date": str(_read(entry, "event_date")),
                        "event_time": str(_read(entry, "event_time")),
                        "quantity": decimal_to_text(row_decimal(entry, "quantity")),
                        "price": decimal_to_text(row_decimal(entry, "price")),
                        "gross_amount": decimal_to_text(
                            row_decimal(entry, "gross_amount")
                        ),
                        "fees": decimal_to_text(row_decimal(entry, "fees")),
                        "total_cost": decimal_to_text(row_decimal(entry, "total_cost")),
                        "external_id": str(_read(entry, "external_id")),
                        "source_row": _read(entry, "source_row", None),
                        "note": str(_read(entry, "note")),
                    }
                )

            result.append(
                {
                    "group_id": f"{cycle.cycle_id}:{event_day.isoformat()}:{event_type}",
                    "event_date": event_day.isoformat(),
                    "event_type": event_type,
                    "label": labels[event_type],
                    "entry_count": len(entries),
                    "quantity": decimal_to_text(total_quantity),
                    "fees": decimal_to_text(total_fees),
                    "gross_amount": decimal_to_text(total_gross),
                    "actual_price": decimal_to_text(actual_price),
                    "adjusted_price": (
                        _chart_number(adjusted_price) if adjusted_price is not None else None
                    ),
                    "mapped_trade_date": (
                        mapped_day.isoformat() if mapped_day is not None else None
                    ),
                    "timestamp": _timestamp_ms(mapped_day) if mapped_day is not None else None,
                    "in_range": in_range,
                    "mapping_status": mapping_status,
                    "entries": original_entries,
                }
            )
        return result, gaps

    def get_payload(
        self,
        ts_code: str,
        *,
        range_key: str = "3m",
        cycle_id: str | None = None,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        normalized_range = self._validate_range(range_key)
        target_as_of = as_of or date.today()
        instrument, cycle = self._context(
            ts_code, cycle_id=cycle_id, as_of=target_as_of
        )
        fetch_start, fetch_end = self._fetch_window(cycle, normalized_range, target_as_of)
        raw_rows = self.store.latest_daily_bars(
            instrument.ts_code, fetch_start, fetch_end
        )
        factor_rows = self.store.latest_adjustment_factors(
            instrument.ts_code, fetch_start, fetch_end
        )
        factor_map = {item["trade_date"]: item["adj_factor"] for item in factor_rows}
        (
            display_rows,
            desired_start,
            effective_end,
            pre_open_count,
            post_close_count,
        ) = self._select_display_bars(raw_rows, cycle, normalized_range, target_as_of)

        missing_factor_dates = [
            item["trade_date"] for item in display_rows if item["trade_date"] not in factor_map
        ]
        anchor_date = display_rows[-1]["trade_date"] if display_rows else None
        anchor_factor = factor_map.get(anchor_date) if anchor_date is not None else None
        adjusted_bars: list[dict[str, Any]] = []
        if display_rows and not missing_factor_dates and anchor_factor is not None:
            for item in display_rows:
                factor = factor_map[item["trade_date"]]
                adjusted_bars.append(
                    {
                        "timestamp": _timestamp_ms(item["trade_date"]),
                        "trade_date": item["trade_date"].isoformat(),
                        "open": _chart_number(item["open_price"] * factor / anchor_factor),
                        "high": _chart_number(item["high_price"] * factor / anchor_factor),
                        "low": _chart_number(item["low_price"] * factor / anchor_factor),
                        "close": _chart_number(item["close_price"] * factor / anchor_factor),
                        "volume": _chart_number(item["volume_lots"]),
                        "turnover": _chart_number(item["amount_k_cny"] * Decimal("1000")),
                    }
                )

        operation_groups, operation_gaps = self._operation_groups(
            cycle,
            display_rows,
            factor_map,
            anchor_factor,
            desired_start,
            effective_end,
        )
        gaps: list[dict[str, Any]] = []
        if not display_rows:
            gaps.append({"code": "MISSING_BARS", "message": "所选区间没有本地 K 线缓存"})
        if missing_factor_dates:
            gaps.append(
                {
                    "code": "MISSING_ADJ_FACTOR",
                    "dates": [item.isoformat() for item in missing_factor_dates],
                    "message": "展示区间存在缺失复权因子的交易日",
                }
            )
        gaps.extend(operation_gaps)
        if not display_rows:
            status = "missing"
        elif gaps:
            status = "incomplete"
        else:
            status = "ready"

        fetched_values = [
            str(item.get("fetched_at") or "") for item in [*raw_rows, *factor_rows]
        ]
        fetched_at = max((item for item in fetched_values if item), default=None)
        return {
            "status": status,
            "instrument": {
                "ts_code": instrument.ts_code,
                "name": instrument.name,
                "asset_type": instrument.asset_type,
                "price_precision": 4,
                "volume_precision": 0,
            },
            "range": {
                "key": normalized_range,
                "requested_start": desired_start.isoformat(),
                "requested_end": effective_end.isoformat(),
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
            "bars": adjusted_bars,
            "technical_indicators": {
                "available": list(TECHNICAL_INDICATOR_NAMES),
                "default_selected": ["VOL"],
                "calculation": {
                    "mode": "client_side",
                    "engine": "klinecharts",
                    "engine_version": KLINECHARTS_VERSION,
                    "parameter_profile": "library_defaults",
                    "input_period": "1d",
                    "input_price_adjustment": "qfq",
                    "input_fields": [
                        "open",
                        "high",
                        "low",
                        "close",
                        "volume",
                        "turnover",
                    ],
                    "persisted": False,
                },
                "boundary": "指标由同批前复权 K 线在浏览器内派生，不是交易信号。",
            },
            "operation_groups": operation_groups,
            "coverage": {
                "bar_count": len(display_rows),
                "first_trade_date": (
                    display_rows[0]["trade_date"].isoformat() if display_rows else None
                ),
                "last_trade_date": (
                    display_rows[-1]["trade_date"].isoformat() if display_rows else None
                ),
                "pre_open_bar_count": pre_open_count,
                "post_close_bar_count": post_close_count,
                "missing_factor_dates": [
                    item.isoformat() for item in missing_factor_dates
                ],
                "out_of_range_operation_group_count": sum(
                    not item["in_range"] for item in operation_groups
                ),
                "gaps": gaps,
            },
            "adjustment": {
                "mode": "qfq",
                "formula": "raw_price * factor_on_date / anchor_factor",
                "anchor_date": anchor_date.isoformat() if anchor_date else None,
                "anchor_factor": decimal_to_text(anchor_factor),
            },
            "sources": {
                "bars": sorted({str(item["source"]) for item in display_rows}),
                "factors": sorted({str(item["source"]) for item in factor_rows}),
                "operations": "ledger_entries",
            },
            "fetched_at": fetched_at,
            "boundary": "仅展示行情与已记录操作，不构成交易建议。",
        }

    def refresh(
        self,
        provider: TushareKlineProvider,
        ts_code: str,
        *,
        range_key: str = "3m",
        cycle_id: str | None = None,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        normalized_range = self._validate_range(range_key)
        target_as_of = as_of or date.today()
        instrument, cycle = self._context(
            ts_code, cycle_id=cycle_id, as_of=target_as_of
        )
        start_date, end_date = self._fetch_window(cycle, normalized_range, target_as_of)
        batch = provider.fetch(instrument, start_date=start_date, end_date=end_date)
        inserted = {"new_bar_observations": 0, "new_factor_observations": 0}
        if batch.bars:
            inserted = self.store.add_kline_batch(batch.bars, batch.factors)
        payload = self.get_payload(
            instrument.ts_code,
            range_key=normalized_range,
            cycle_id=cycle.cycle_id,
            as_of=target_as_of,
        )
        payload["refresh"] = {
            "refresh_batch_id": batch.refresh_batch_id,
            "requested_start": start_date.isoformat(),
            "requested_end": end_date.isoformat(),
            "fetched_bars": len(batch.bars),
            "fetched_factors": len(batch.factors),
            **inserted,
        }
        return payload
