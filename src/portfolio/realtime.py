from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Iterable, Protocol
from urllib.request import Request, urlopen

from .models import Instrument


CHINA_TZ = timezone(timedelta(hours=8))


class RealtimeFetchError(RuntimeError):
    """盘中行情源不可用或返回内容无法解析。"""


@dataclass(frozen=True)
class RealtimeQuote:
    ts_code: str
    name: str
    price: Decimal
    pre_close: Decimal | None
    pct_chg: Decimal | None
    quote_time: str
    source: str


@dataclass(frozen=True)
class RealtimeFetchResult:
    quotes: dict[str, RealtimeQuote]
    missing: list[str]
    errors: list[str]
    providers: list[str]
    fetched_at: str


class RealtimeProvider(Protocol):
    name: str

    def fetch_many(self, instruments: list[Instrument]) -> dict[str, RealtimeQuote]: ...


def _decimal(value: str) -> Decimal | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _vendor_symbol(instrument: Instrument) -> str:
    code = instrument.ts_code.split(".", 1)[0]
    exchange = instrument.exchange.upper()
    if exchange == "SH":
        return f"sh{code}"
    if exchange == "SZ":
        return f"sz{code}"
    if exchange == "BJ":
        return f"bj{code}"
    if code.startswith(("6", "9")):
        return f"sh{code}"
    if code.startswith("8"):
        return f"bj{code}"
    return f"sz{code}"


def _quote_timestamp(raw_date_time: str) -> str:
    text = raw_date_time.strip()
    if len(text) == 14 and text.isdigit():
        parsed = datetime.strptime(text, "%Y%m%d%H%M%S")
        return parsed.replace(tzinfo=CHINA_TZ).isoformat()
    return text


def parse_tencent_response(
    text: str, symbol_map: dict[str, Instrument]
) -> dict[str, RealtimeQuote]:
    quotes: dict[str, RealtimeQuote] = {}
    for line in text.strip().split(";"):
        if "=" not in line or '"' not in line:
            continue
        vendor_symbol = line.split("=", 1)[0].rsplit("_", 1)[-1]
        instrument = symbol_map.get(vendor_symbol)
        if instrument is None:
            continue
        values = line.split('"', 2)[1].split("~")
        if len(values) < 35:
            continue
        price = _decimal(values[3])
        if price is None or price <= 0:
            continue
        quotes[instrument.ts_code] = RealtimeQuote(
            ts_code=instrument.ts_code,
            name=values[1] or instrument.name,
            price=price,
            pre_close=_decimal(values[4]),
            pct_chg=_decimal(values[32]),
            quote_time=_quote_timestamp(values[30]),
            source="tencent.quote",
        )
    return quotes


def parse_sina_response(
    text: str, symbol_map: dict[str, Instrument]
) -> dict[str, RealtimeQuote]:
    quotes: dict[str, RealtimeQuote] = {}
    for line in text.strip().splitlines():
        if "=" not in line or '"' not in line:
            continue
        vendor_symbol = line.split("=", 1)[0].rsplit("_", 1)[-1]
        instrument = symbol_map.get(vendor_symbol)
        if instrument is None:
            continue
        values = line.split('"', 2)[1].split(",")
        if len(values) < 32:
            continue
        price = _decimal(values[3])
        pre_close = _decimal(values[2])
        if price is None or price <= 0:
            continue
        pct_chg = (
            (price - pre_close) / pre_close * Decimal("100")
            if pre_close is not None and pre_close > 0
            else None
        )
        quote_time = f"{values[30]}T{values[31]}+08:00" if values[30] and values[31] else ""
        quotes[instrument.ts_code] = RealtimeQuote(
            ts_code=instrument.ts_code,
            name=values[0] or instrument.name,
            price=price,
            pre_close=pre_close,
            pct_chg=pct_chg,
            quote_time=quote_time,
            source="sina.quote",
        )
    return quotes


class TencentRealtimeProvider:
    name = "tencent.quote"

    def __init__(self, *, timeout_seconds: int = 10) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch_many(self, instruments: list[Instrument]) -> dict[str, RealtimeQuote]:
        if not instruments:
            return {}
        symbol_map = {_vendor_symbol(item): item for item in instruments}
        url = "https://qt.gtimg.cn/q=" + ",".join(symbol_map)
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                text = response.read().decode("gbk", errors="replace")
        except Exception as exc:
            raise RealtimeFetchError(f"腾讯行情请求失败: {type(exc).__name__}: {exc}") from exc
        quotes = parse_tencent_response(text, symbol_map)
        if not quotes:
            raise RealtimeFetchError("腾讯行情未返回可用报价")
        return quotes


class SinaRealtimeProvider:
    name = "sina.quote"

    def __init__(self, *, timeout_seconds: int = 10) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch_many(self, instruments: list[Instrument]) -> dict[str, RealtimeQuote]:
        if not instruments:
            return {}
        symbol_map = {_vendor_symbol(item): item for item in instruments}
        url = "https://hq.sinajs.cn/list=" + ",".join(symbol_map)
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://finance.sina.com.cn/",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                text = response.read().decode("gbk", errors="replace")
        except Exception as exc:
            raise RealtimeFetchError(f"新浪行情请求失败: {type(exc).__name__}: {exc}") from exc
        quotes = parse_sina_response(text, symbol_map)
        if not quotes:
            raise RealtimeFetchError("新浪行情未返回可用报价")
        return quotes


class FallbackRealtimeProvider:
    def __init__(self, providers: Iterable[RealtimeProvider] | None = None) -> None:
        self.providers = list(providers or (TencentRealtimeProvider(), SinaRealtimeProvider()))

    def fetch_many(self, instruments: list[Instrument]) -> RealtimeFetchResult:
        remaining = {item.ts_code: item for item in instruments}
        quotes: dict[str, RealtimeQuote] = {}
        errors: list[str] = []
        used: list[str] = []
        for provider in self.providers:
            if not remaining:
                break
            try:
                fetched = provider.fetch_many(list(remaining.values()))
            except Exception as exc:
                errors.append(f"{provider.name}: {type(exc).__name__}: {exc}")
                continue
            accepted = {
                ts_code: quote
                for ts_code, quote in fetched.items()
                if ts_code in remaining and quote.price > 0
            }
            if accepted:
                used.append(provider.name)
                quotes.update(accepted)
                for ts_code in accepted:
                    remaining.pop(ts_code, None)
        return RealtimeFetchResult(
            quotes=quotes,
            missing=sorted(remaining),
            errors=errors,
            providers=used,
            fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
