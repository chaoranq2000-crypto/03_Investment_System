from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from src.investment_review import strategy_market_data as market_module
from src.investment_review.artifact_io import canonical_json_bytes
from src.investment_review.strategy_market_data import (
    EASTMONEY_ENDPOINT,
    TENCENT_ENDPOINT,
    EastmoneyFetch,
    EastmoneyKlineProvider,
    IndexSpec,
    StrategyMarketDataError,
    TencentKlineProvider,
    build_strategy_market_cache,
    extract_strategy_symbols,
)
from src.portfolio.models import ClosePrice, Instrument


FETCHED_AT = "2026-08-02T08:00:00Z"
START = date(2026, 3, 30)
END = date(2026, 4, 1)


class _EmptyBaoResult:
    fields = [
        "date",
        "code",
        "open",
        "high",
        "low",
        "close",
        "preclose",
        "volume",
        "amount",
        "pctChg",
    ]
    error_code = "0"
    error_msg = ""

    def next(self) -> bool:
        return False

    def get_row_data(self) -> list[str]:
        return []


class _EmptyBaoStock:
    def __init__(self) -> None:
        self.logged_out = False
        self.requests: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def login(self) -> SimpleNamespace:
        return SimpleNamespace(error_code="0", error_msg="")

    def logout(self) -> None:
        self.logged_out = True

    def query_history_k_data_plus(self, *args: object, **kwargs: object) -> _EmptyBaoResult:
        self.requests.append((args, kwargs))
        return _EmptyBaoResult()


class _FailingCloseProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_range(self, instrument: Instrument, **_: object) -> list[ClosePrice]:
        self.calls.append(instrument.ts_code)
        raise RuntimeError("expired credential SECRET_VALUE")


class _FailingKlineProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch(self, instrument: Instrument, **_: object) -> object:
        self.calls.append(instrument.ts_code)
        raise RuntimeError("expired credential SECRET_VALUE")


class _FakeEastmoney:
    def __init__(self, close: str = "10.5") -> None:
        self.close = close
        self.calls: list[str] = []

    def fetch(self, ts_code: str, **_: object) -> EastmoneyFetch:
        self.calls.append(ts_code)
        rows = (
            {
                "trade_date": "2026-03-30",
                "open": "10",
                "close": self.close,
                "high": "11",
                "low": "9.8",
                "volume": "1000",
                "volume_unit": "provider_native",
                "amount": "10500",
                "amount_unit": "cny",
                "pct_chg": "5",
                "adjustment": "raw",
                "source": "eastmoney.push2his.kline",
            },
        )
        response = canonical_json_bytes(list(rows))
        return EastmoneyFetch(
            rows=rows,
            endpoint=f"{EASTMONEY_ENDPOINT}?token=SECRET_VALUE",
            request={
                "secid": market_module._eastmoney_secid(ts_code),
                "fqt": "0",
                "token": "SECRET_VALUE",
            },
            response_sha256=hashlib.sha256(response).hexdigest(),
        )


def _build_fallback_cache(
    tmp_path: Path,
    *,
    eastmoney: _FakeEastmoney | None = None,
) -> dict[str, object]:
    return build_strategy_market_cache(
        cache_root=tmp_path / "allowed" / "strategy_cache",
        allowed_root=tmp_path / "allowed",
        symbols=(
            Instrument("000001.SZ", "平安银行", "equity"),
            Instrument("510300.SH", "沪深300ETF", "etf"),
            Instrument("127113.SZ", "转债样本", "unknown"),
        ),
        indices=(IndexSpec("000300.SH", "沪深300"),),
        start_date=START,
        end_date=END,
        fetched_at=FETCHED_AT,
        close_provider=_FailingCloseProvider(),
        kline_provider=_FailingKlineProvider(),
        baostock_module=_EmptyBaoStock(),
        eastmoney_provider=eastmoney or _FakeEastmoney(),
    )


def test_cache_target_must_be_dedicated_child_of_allowed_root(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    with pytest.raises(StrategyMarketDataError, match="dedicated child"):
        build_strategy_market_cache(
            cache_root=tmp_path / "outside",
            allowed_root=allowed,
            symbols=(Instrument("000001.SZ", "平安银行", "equity"),),
            start_date=START,
            end_date=END,
            fetched_at=FETCHED_AT,
            eastmoney_provider=_FakeEastmoney(),
        )
    with pytest.raises(StrategyMarketDataError, match="dedicated child"):
        build_strategy_market_cache(
            cache_root=allowed,
            allowed_root=allowed,
            symbols=(Instrument("000001.SZ", "平安银行", "equity"),),
            start_date=START,
            end_date=END,
            fetched_at=FETCHED_AT,
            eastmoney_provider=_FakeEastmoney(),
        )
    assert not (tmp_path / "outside").exists()


def test_manifest_is_deterministic_credential_free_and_updates_by_request(
    tmp_path: Path,
) -> None:
    eastmoney = _FakeEastmoney()
    first = _build_fallback_cache(tmp_path, eastmoney=eastmoney)
    first_manifest_bytes = Path(first["manifest_path"]).read_bytes()
    first_artifact_path = Path(first["artifact_path"])
    first_artifact_bytes = first_artifact_path.read_bytes()

    second = _build_fallback_cache(tmp_path, eastmoney=eastmoney)
    assert Path(second["manifest_path"]).read_bytes() == first_manifest_bytes
    assert Path(second["artifact_path"]) == first_artifact_path

    artifact_text = Path(second["artifact_path"]).read_text(encoding="utf-8")
    assert "SECRET_VALUE" not in artifact_text
    assert "credential" not in artifact_text.casefold()
    artifact = second["artifact"]
    assert all(item["status"] == "ready" for item in artifact["instruments"])
    assert artifact["instruments"][2]["ohlcv_status"] == "raw_ready"
    assert artifact["indices"][0]["status"] == "ready"
    assert eastmoney.calls.count("000300.SH") == 2

    manifest = second["manifest"]
    material = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    assert manifest["manifest_sha256"] == hashlib.sha256(canonical_json_bytes(material)).hexdigest()

    eastmoney.close = "10.6"
    updated = _build_fallback_cache(tmp_path, eastmoney=eastmoney)
    assert Path(updated["artifact_path"]) == first_artifact_path
    assert first_artifact_path.read_bytes() != first_artifact_bytes
    assert len(updated["manifest"]["entries"]) == 1
    assert (
        updated["manifest"]["entries"][0]["path"]
        == Path(updated["artifact_path"]).relative_to(Path(updated["cache_root"])).as_posix()
    )


def test_existing_entries_link_cannot_escape_cache_root(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    cache = allowed / "cache"
    outside = tmp_path / "outside"
    cache.mkdir(parents=True)
    outside.mkdir()
    try:
        (cache / "entries").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable on this Windows host")

    with pytest.raises(StrategyMarketDataError, match="escapes cache_root"):
        build_strategy_market_cache(
            cache_root=cache,
            allowed_root=allowed,
            symbols=(Instrument("000001.SZ", "平安银行", "equity"),),
            start_date=START,
            end_date=END,
            fetched_at=FETCHED_AT,
            eastmoney_provider=_FakeEastmoney(),
        )
    assert list(outside.iterdir()) == []


def test_corrupted_existing_artifact_is_rejected_before_provider_call(
    tmp_path: Path,
) -> None:
    eastmoney = _FakeEastmoney()
    first = _build_fallback_cache(tmp_path, eastmoney=eastmoney)
    Path(first["artifact_path"]).write_text("{}\n", encoding="utf-8")
    call_count = len(eastmoney.calls)

    with pytest.raises(StrategyMarketDataError, match="artifact hash"):
        _build_fallback_cache(tmp_path, eastmoney=eastmoney)
    assert len(eastmoney.calls) == call_count


def test_tushare_is_reused_and_convertible_bond_ohlcv_gap_is_explicit(
    tmp_path: Path,
) -> None:
    class CloseProvider:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def fetch_range(self, instrument: Instrument, **_: object) -> list[ClosePrice]:
            self.calls.append(instrument.ts_code)
            return [
                ClosePrice(
                    ts_code=instrument.ts_code,
                    trade_date=START,
                    close=Decimal("10"),
                    source="tushare.cb_daily"
                    if instrument.ts_code.startswith("127")
                    else "tushare.daily",
                )
            ]

    class KlineProvider:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def fetch(self, instrument: Instrument, **_: object) -> object:
            self.calls.append(instrument.ts_code)
            bar = SimpleNamespace(
                trade_date=START,
                open=Decimal("9.8"),
                high=Decimal("10.2"),
                low=Decimal("9.7"),
                close=Decimal("10"),
                volume_lots=Decimal("100"),
                amount_k_cny=Decimal("1000"),
                source="tushare.daily",
            )
            factor = SimpleNamespace(
                trade_date=START,
                adj_factor=Decimal("1.2"),
                source="tushare.adj_factor",
            )
            return SimpleNamespace(
                bars=(bar,),
                factors=(factor,),
                bar_source="tushare.daily",
                factor_source="tushare.adj_factor",
            )

    close = CloseProvider()
    kline = KlineProvider()
    result = build_strategy_market_cache(
        cache_root=tmp_path / "allowed" / "cache",
        allowed_root=tmp_path / "allowed",
        symbols=(
            Instrument("000001.SZ", "平安银行", "equity"),
            Instrument("127113.SZ", "转债样本", "unknown"),
        ),
        start_date=START,
        end_date=END,
        fetched_at=FETCHED_AT,
        close_provider=close,
        kline_provider=kline,
    )

    assert close.calls == ["000001.SZ", "127113.SZ"]
    assert kline.calls == ["000001.SZ"]
    by_code = {item["instrument"]["ts_code"]: item for item in result["artifact"]["instruments"]}
    assert by_code["000001.SZ"]["ohlcv_status"] == "raw_with_adjustment_factors_ready"
    assert by_code["127113.SZ"]["close_status"] == "ready"
    assert by_code["127113.SZ"]["ohlcv_status"] == "unsupported_or_unavailable"


def test_eastmoney_provider_records_sanitized_request_and_raw_response_hash() -> None:
    raw = json.dumps(
        {"data": {"klines": ["2026-03-30,10,10.5,11,9.8,1000,10500,12,5,0.5,1.2"]}}
    ).encode("utf-8")
    captured: dict[str, object] = {}

    def fetch_bytes(url: str, timeout: float) -> bytes:
        captured.update(url=url, timeout=timeout)
        return raw

    provider = EastmoneyKlineProvider(fetch_bytes, timeout_seconds=2.5)
    result = provider.fetch("127113.SZ", start_date=START, end_date=END)

    assert result.endpoint == EASTMONEY_ENDPOINT
    assert result.response_sha256 == hashlib.sha256(raw).hexdigest()
    assert result.rows[0]["close"] == "10.5"
    query = parse_qs(urlparse(str(captured["url"])).query)
    assert query["secid"] == ["0.127113"]
    assert query["beg"] == ["20260330"]
    assert query["end"] == ["20260401"]
    assert query["fqt"] == ["0"]
    assert "token" not in str(captured["url"]).casefold()


def test_tencent_is_used_after_eastmoney_failure_with_bounded_sanitized_request(
    tmp_path: Path,
) -> None:
    raw = json.dumps(
        {
            "code": 0,
            "data": {
                "sz127113": {
                    "day": [
                        [
                            "2026-03-30",
                            "100",
                            "120",
                            "130",
                            "98",
                            "1234",
                            {"cqr": "2026-03-30", "FHcontent": "corporate-action metadata"},
                        ]
                    ]
                }
            },
        }
    ).encode("utf-8")
    captured: dict[str, object] = {}

    def fetch_bytes(url: str, timeout: float) -> bytes:
        captured.update(url=url, timeout=timeout)
        return raw

    class FailingEastmoney:
        def fetch(self, *_: object, **__: object) -> object:
            raise ConnectionError("remote disconnected SECRET_VALUE")

    result = build_strategy_market_cache(
        cache_root=tmp_path / "allowed" / "cache",
        allowed_root=tmp_path / "allowed",
        symbols=(Instrument("127113.SZ", "转债样本", "unknown"),),
        start_date=START,
        end_date=END,
        fetched_at=FETCHED_AT,
        eastmoney_provider=FailingEastmoney(),
        tencent_provider=TencentKlineProvider(fetch_bytes, timeout_seconds=2.5),
    )

    instrument = result["artifact"]["instruments"][0]
    assert instrument["bars"][0]["close"] == "120"
    assert instrument["bars"][0]["amount"] is None
    assert [item["source"] for item in instrument["attempts"]] == [
        "eastmoney",
        "tencent",
    ]
    query = parse_qs(urlparse(str(captured["url"])).query)
    assert query["param"][0].startswith("sz127113,day,2026-03-30,2026-04-01,")
    assert str(captured["url"]).startswith(TENCENT_ENDPOINT)
    artifact_text = Path(result["artifact_path"]).read_text(encoding="utf-8")
    assert "SECRET_VALUE" not in artifact_text
    assert "token" not in artifact_text.casefold()


def _formal_db(path: Path) -> Path:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE instruments (
            ts_code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            asset_type TEXT NOT NULL
        );
        CREATE TABLE ledger_entries (
            entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL,
            event_date TEXT NOT NULL,
            event_time TEXT NOT NULL DEFAULT '',
            event_type TEXT NOT NULL,
            ts_code TEXT NOT NULL,
            quantity TEXT NOT NULL DEFAULT '0'
        );
        INSERT INTO instruments VALUES ('000001.SZ', '平安银行', 'equity');
        INSERT INTO instruments VALUES ('510300.SH', '沪深300ETF', 'etf');
        INSERT INTO ledger_entries
        (account_id, event_date, event_time, event_type, ts_code, quantity)
        VALUES
        ('acct', '2026-01-02', '09:30:00', 'BUY', '000001.SZ', '100'),
        ('acct', '2026-01-03', '09:30:00', 'BUY', '510300.SH', '100'),
        ('acct', '2026-01-04', '09:30:00', 'SELL', '510300.SH', '100');
        """
    )
    connection.commit()
    connection.close()
    return path


def test_symbol_extraction_uses_immutable_read_only_uri_and_never_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _formal_db(tmp_path / "portfolio.sqlite3")
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    original_connect = market_module.sqlite3.connect
    calls: list[tuple[object, bool]] = []

    def spy_connect(database_arg: object, *args: object, **kwargs: object) -> sqlite3.Connection:
        calls.append((database_arg, bool(kwargs.get("uri"))))
        return original_connect(database_arg, *args, **kwargs)

    monkeypatch.setattr(market_module.sqlite3, "connect", spy_connect)
    symbols = extract_strategy_symbols(
        database,
        account_id="acct",
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28),
    )

    assert [item.ts_code for item in symbols] == ["000001.SZ"]
    assert len(calls) == 1
    assert "mode=ro&immutable=1" in str(calls[0][0])
    assert calls[0][1] is True
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before


def test_request_limits_are_enforced_before_fetch(tmp_path: Path) -> None:
    with pytest.raises(StrategyMarketDataError, match="date range"):
        build_strategy_market_cache(
            cache_root=tmp_path / "allowed" / "cache",
            allowed_root=tmp_path / "allowed",
            symbols=(Instrument("000001.SZ", "平安银行", "equity"),),
            start_date=date(2010, 1, 1),
            end_date=date(2026, 1, 1),
            fetched_at=FETCHED_AT,
            eastmoney_provider=_FakeEastmoney(),
        )
