from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from .models import ClosePrice, Instrument


class PriceFetchError(RuntimeError):
    """收盘价抓取不完整或数据格式异常。"""


def _records(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    if isinstance(frame, list):
        return [dict(item) for item in frame]
    if hasattr(frame, "to_dict"):
        return list(frame.to_dict(orient="records"))
    raise PriceFetchError(f"无法识别 Tushare 返回类型: {type(frame).__name__}")


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None or str(value).strip().lower() in {"", "nan", "none"}:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise PriceFetchError(f"行情数值格式无效: {value!r}") from exc


class TushareCloseProvider:
    def __init__(self, pro: Any) -> None:
        self.pro = pro

    def _endpoints(self, instrument: Instrument) -> list[str]:
        if instrument.asset_type == "etf":
            return ["fund_daily"]
        if instrument.asset_type == "equity":
            return ["daily"]
        return ["daily", "fund_daily"]

    def fetch_one(
        self,
        instrument: Instrument,
        *,
        as_of: date,
        lookback_days: int = 60,
    ) -> ClosePrice | None:
        start_date = (as_of - timedelta(days=lookback_days)).strftime("%Y%m%d")
        end_date = as_of.strftime("%Y%m%d")
        errors: list[str] = []
        for endpoint_name in self._endpoints(instrument):
            endpoint = getattr(self.pro, endpoint_name)
            try:
                frame = endpoint(
                    ts_code=instrument.ts_code,
                    start_date=start_date,
                    end_date=end_date,
                    fields="ts_code,trade_date,close,pre_close,pct_chg",
                )
            except Exception as exc:  # Tushare SDK 统一抛出 Exception
                errors.append(f"{endpoint_name}: {type(exc).__name__}: {exc}")
                continue
            rows = []
            for row in _records(frame):
                raw_date = str(row.get("trade_date", "")).replace("-", "")
                if len(raw_date) != 8 or not raw_date.isdigit():
                    continue
                trade_date = datetime.strptime(raw_date, "%Y%m%d").date()
                if trade_date <= as_of:
                    rows.append((trade_date, row))
            if not rows:
                continue
            trade_date, row = max(rows, key=lambda item: item[0])
            close = _optional_decimal(row.get("close"))
            if close is None or close <= 0:
                raise PriceFetchError(
                    f"{instrument.ts_code} {trade_date.isoformat()} 的收盘价无效: {close}"
                )
            return ClosePrice(
                ts_code=instrument.ts_code,
                trade_date=trade_date,
                close=close,
                pre_close=_optional_decimal(row.get("pre_close")),
                pct_chg=_optional_decimal(row.get("pct_chg")),
                source=f"tushare.{endpoint_name}",
                fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
        if errors:
            raise PriceFetchError(f"{instrument.ts_code} 行情抓取失败；" + " | ".join(errors))
        return None

    def fetch_many(
        self,
        instruments: list[Instrument],
        *,
        as_of: date,
        lookback_days: int = 60,
    ) -> tuple[list[ClosePrice], list[str]]:
        prices: list[ClosePrice] = []
        missing: list[str] = []
        for instrument in instruments:
            quote = self.fetch_one(instrument, as_of=as_of, lookback_days=lookback_days)
            if quote is None:
                missing.append(instrument.ts_code)
            else:
                prices.append(quote)
        return prices, missing
