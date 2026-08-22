"""Lightweight point-in-time context for periodic investment reviews.

The adapter deliberately returns only a small operation-relevant slice.  It
does not write market data, research evidence, or the formal portfolio store.
"""

from __future__ import annotations

import importlib
import io
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable
from zoneinfo import ZoneInfo


SHANGHAI = ZoneInfo("Asia/Shanghai")
ZERO = Decimal("0")

_P1_SECTOR_INDEX = {
    "医药生物": ("sh.000933", "中证医药"),
}


class PeriodicContextError(RuntimeError):
    """Raised when the bounded public-data context cannot be obtained."""


def _decimal(value: object) -> Decimal | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        result = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise PeriodicContextError(f"invalid BaoStock decimal: {value!r}") from exc
    return result if result.is_finite() else None


def _text(value: Decimal | None, places: int = 2) -> str | None:
    if value is None:
        return None
    quantized = value.quantize(Decimal(1).scaleb(-places))
    return "0" if quantized == ZERO else format(quantized.normalize(), "f")


def _pct_change(current: Decimal | None, previous: Decimal | None) -> Decimal | None:
    if current is None or previous in (None, ZERO):
        return None
    return (current - previous) / previous * Decimal("100")


def _baostock_code(ts_code: str) -> str:
    code, _, exchange = ts_code.strip().upper().partition(".")
    if exchange not in {"SH", "SZ", "BJ"}:
        raise PeriodicContextError(f"unsupported A-share code: {ts_code}")
    return f"{exchange.lower()}.{code}"


def _rows(result: Any) -> list[dict[str, str]]:
    if str(getattr(result, "error_code", "")) not in {"", "0"}:
        raise PeriodicContextError(
            "BaoStock query failed: "
            f"{getattr(result, 'error_code', '')} "
            f"{getattr(result, 'error_msg', '')}"
        )
    fields = list(getattr(result, "fields", []) or [])
    rows: list[dict[str, str]] = []
    while result.next():
        values = list(result.get_row_data())
        rows.append(dict(zip(fields, values, strict=False)))
    return rows


def _quarter_candidates(day: date, count: int = 8) -> Iterable[tuple[int, int]]:
    quarter = (day.month - 1) // 3 + 1
    year = day.year
    for _ in range(count):
        yield year, quarter
        quarter -= 1
        if quarter == 0:
            year -= 1
            quarter = 4


def _profit_rows(module: Any, code: str, day: date) -> list[dict[str, str]]:
    accepted: list[dict[str, str]] = []
    for year, quarter in _quarter_candidates(day):
        for row in _rows(module.query_profit_data(code=code, year=year, quarter=quarter)):
            published = str(row.get("pubDate") or "")
            if published and published <= day.isoformat():
                accepted.append(row)
    accepted.sort(
        key=lambda row: (
            str(row.get("statDate") or ""),
            str(row.get("pubDate") or ""),
        ),
        reverse=True,
    )
    if not accepted:
        return []
    latest = accepted[0]
    stat_date = str(latest.get("statDate") or "")
    comparable = next(
        (
            row
            for row in accepted[1:]
            if str(row.get("statDate") or "")[4:] == stat_date[4:]
        ),
        accepted[1] if len(accepted) > 1 else None,
    )
    return [latest, comparable] if comparable is not None else [latest]


def _daily_rows(
    module: Any,
    *,
    code: str,
    start: date,
    end: date,
    full_fields: bool,
) -> list[dict[str, str]]:
    fields = (
        "date,code,open,high,low,close,preclose,volume,amount,turn,"
        "tradestatus,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM,isST"
        if full_fields
        else "date,code,close,preclose,pctChg"
    )
    rows = _rows(
        module.query_history_k_data_plus(
            code,
            fields,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            frequency="d",
            adjustflag="3",
        )
    )
    return [
        row
        for row in rows
        if str(row.get("tradestatus") or "1") != "0"
        and str(row.get("date") or "") <= end.isoformat()
    ]


def _intraday_rows(module: Any, code: str, day: date) -> list[dict[str, Any]]:
    fields = "date,time,code,open,high,low,close,volume,amount,adjustflag"
    rows = _rows(
        module.query_history_k_data_plus(
            code,
            fields,
            start_date=day.isoformat(),
            end_date=day.isoformat(),
            frequency="5",
            adjustflag="3",
        )
    )
    result: list[dict[str, Any]] = []
    for row in rows:
        raw_time = str(row.get("time") or "")
        try:
            parsed = datetime.strptime(raw_time[:14], "%Y%m%d%H%M%S").replace(
                tzinfo=SHANGHAI
            )
        except ValueError:
            continue
        result.append(
            {
                "bar_end_at": parsed.isoformat(timespec="seconds"),
                "open_cny": _text(_decimal(row.get("open")), 4),
                "high_cny": _text(_decimal(row.get("high")), 4),
                "low_cny": _text(_decimal(row.get("low")), 4),
                "close_cny": _text(_decimal(row.get("close")), 4),
                "volume_shares": _text(_decimal(row.get("volume")), 0),
                "source_ref": (
                    f"baostock.query_history_k_data_plus:{code}:"
                    f"{day.isoformat()}:5m:{parsed.strftime('%H:%M')}"
                ),
            }
        )
    return result


def _fundamental_context(
    rows: list[dict[str, str]],
    *,
    valuation_row: dict[str, str] | None,
    code: str,
) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}
    loss_change_pct: Decimal | None = None
    if rows:
        latest = rows[0]
        previous = rows[1] if len(rows) > 1 else None
        net_profit = _decimal(latest.get("netProfit"))
        prior_profit = _decimal(previous.get("netProfit")) if previous else None
        metrics = {
            "statement_date": latest.get("statDate"),
            "published_date": latest.get("pubDate"),
            "roe_avg_pct": _text(
                (_decimal(latest.get("roeAvg")) or ZERO) * Decimal("100"), 4
            ),
            "net_margin_pct": _text(
                (_decimal(latest.get("npMargin")) or ZERO) * Decimal("100"), 4
            ),
            "gross_margin_pct": _text(
                (_decimal(latest.get("gpMargin")) or ZERO) * Decimal("100"), 4
            ),
            "net_profit_cny": _text(net_profit, 2),
            "eps_ttm_cny": _text(_decimal(latest.get("epsTTM")), 6),
        }
        comparison = ""
        if previous is not None and net_profit is not None and prior_profit is not None:
            change = _pct_change(abs(net_profit), abs(prior_profit))
            loss_change_pct = (
                change if net_profit < ZERO and prior_profit < ZERO else None
            )
            comparison = (
                f"；相较 {previous.get('statDate')}，亏损绝对额变化 "
                f"{_text(change, 2)}%"
                if net_profit < ZERO and prior_profit < ZERO
                else f"；相较 {previous.get('statDate')}，净利润变化 {_text(change, 2)}%"
            )
        observations.append(
            {
                "type": "fact",
                "text": (
                    f"截至 {latest.get('statDate')}，ROE {metrics['roe_avg_pct']}%，"
                    f"净利率 {metrics['net_margin_pct']}%，"
                    f"净利润 {metrics['net_profit_cny']} 元{comparison}。"
                ),
                "available_at": latest.get("pubDate"),
                "source_ref": (
                    f"baostock.query_profit_data:{code}:"
                    f"{latest.get('statDate')}:published:{latest.get('pubDate')}"
                ),
            }
        )
    valuation: dict[str, Any] = {}
    if valuation_row:
        valuation = {
            "trade_date": valuation_row.get("date"),
            "pe_ttm": _text(_decimal(valuation_row.get("peTTM")), 6),
            "pb_mrq": _text(_decimal(valuation_row.get("pbMRQ")), 6),
            "ps_ttm": _text(_decimal(valuation_row.get("psTTM")), 6),
            "pcf_ncf_ttm": _text(_decimal(valuation_row.get("pcfNcfTTM")), 6),
        }
        observations.append(
            {
                "type": "fact",
                "text": (
                    f"{valuation['trade_date']} 估值快照：PE(TTM) "
                    f"{valuation['pe_ttm']}、PB {valuation['pb_mrq']}、"
                    f"PS(TTM) {valuation['ps_ttm']}。"
                ),
                "available_at": valuation["trade_date"],
                "source_ref": (
                    f"baostock.query_history_k_data_plus:{code}:"
                    f"{valuation['trade_date']}:daily_valuation"
                ),
            }
        )
    loss_making = bool(rows and (_decimal(rows[0].get("netProfit")) or ZERO) < ZERO)
    if loss_making:
        latest_metrics = metrics
        profit_wan = _text(
            (_decimal(latest_metrics.get("net_profit_cny")) or ZERO)
            / Decimal("10000"),
            2,
        )
        comparison_text = (
            f"，同比亏损扩大 {_text(loss_change_pct, 2)}%"
            if loss_change_pct is not None and loss_change_pct > ZERO
            else ""
        )
        ps_text = valuation.get("ps_ttm") or "MISSING"
        summary = (
            f"最新可得财务快照净利润 {profit_wan} 万元{comparison_text}；"
            f"负 PE 不具备常规可比意义，PS(TTM) {ps_text} 倍也不能单独"
            "证明便宜，短期上涨不能证明基本面反转。"
        )
    elif rows:
        summary = "最新可得财务快照为盈利；估值仍需结合增长持续性与同业比较。"
    else:
        summary = "报告截止前没有取得可核对的轻量财务快照。"
    return {
        "status": "available" if rows and valuation_row else "partial",
        "scope": "latest_public_snapshot_before_report_cutoff",
        "summary": summary,
        "metrics": metrics,
        "valuation": valuation,
        "observations": observations,
        "source_refs": [item["source_ref"] for item in observations],
    }


def _market_context(
    *,
    stock_row: dict[str, str] | None,
    benchmarks: list[tuple[str, str, dict[str, str] | None]],
    sector: tuple[str, str, dict[str, str] | None] | None,
    code: str,
) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    stock_change = _decimal(stock_row.get("pctChg")) if stock_row else None
    if stock_row:
        observations.append(
            {
                "type": "fact",
                "text": f"标的当日涨跌幅 {_text(stock_change, 2)}%。",
                "timing": "end_of_day_retrospective",
                "source_ref": (
                    f"baostock.query_history_k_data_plus:{code}:"
                    f"{stock_row.get('date')}:daily"
                ),
            }
        )
    benchmark_metrics: list[dict[str, Any]] = []
    for benchmark_code, name, row in benchmarks:
        change = _decimal(row.get("pctChg")) if row else None
        benchmark_metrics.append(
            {"name": name, "code": benchmark_code, "change_pct": _text(change, 2)}
        )
        if row:
            observations.append(
                {
                    "type": "fact",
                    "text": f"{name}当日涨跌幅 {_text(change, 2)}%。",
                    "timing": "end_of_day_retrospective",
                    "source_ref": (
                        f"baostock.query_history_k_data_plus:{benchmark_code}:"
                        f"{row.get('date')}:daily"
                    ),
                }
            )
    sector_metric: dict[str, Any] | None = None
    if sector is not None:
        sector_code, sector_name, row = sector
        sector_change = _decimal(row.get("pctChg")) if row else None
        sector_metric = {
            "name": sector_name,
            "code": sector_code,
            "change_pct": _text(sector_change, 2),
            "stock_relative_pct_points": _text(
                stock_change - sector_change
                if stock_change is not None and sector_change is not None
                else None,
                2,
            ),
        }
        if row:
            observations.append(
                {
                    "type": "fact",
                    "text": (
                        f"{sector_name}当日涨跌幅 {_text(sector_change, 2)}%，"
                        f"标的相对板块 {_text(stock_change - sector_change, 2)} 个百分点。"
                    ),
                    "timing": "end_of_day_retrospective",
                    "source_ref": (
                        f"baostock.query_history_k_data_plus:{sector_code}:"
                        f"{row.get('date')}:daily"
                    ),
                }
            )
    benchmark_text = "、".join(
        f"{item['name']} {item['change_pct']}%"
        for item in benchmark_metrics
        if item.get("change_pct") is not None
    )
    sector_text = (
        f"{sector_metric['name']} {sector_metric['change_pct']}%，"
        f"标的相对板块 {sector_metric['stock_relative_pct_points']} 个百分点"
        if sector_metric and sector_metric.get("change_pct") is not None
        else "板块数据缺失"
    )
    summary = (
        f"标的当日 { _text(stock_change, 2) }%，大盘为 {benchmark_text}；"
        f"{sector_text}。这些结果只解释交易环境，不直接证明用户当时的动机。"
    )
    return {
        "status": "available" if stock_row and observations else "partial",
        "scope": "report_day_delta",
        "summary": summary,
        "stock_change_pct": _text(stock_change, 2),
        "benchmarks": benchmark_metrics,
        "sector": sector_metric,
        "observations": observations,
        "source_refs": [item["source_ref"] for item in observations],
    }


def _technical_context(rows: list[dict[str, str]], *, code: str) -> dict[str, Any]:
    closes = [_decimal(row.get("close")) for row in rows]
    volumes = [_decimal(row.get("volume")) for row in rows]
    latest = rows[-1] if rows else None
    latest_close = closes[-1] if closes else None

    def return_for(sessions: int) -> str | None:
        if len(closes) <= sessions or latest_close is None:
            return None
        return _text(_pct_change(latest_close, closes[-sessions - 1]), 2)

    volume_ratio = None
    if len(volumes) >= 6 and volumes[-1] is not None:
        prior = [value for value in volumes[-6:-1] if value is not None]
        average = sum(prior, ZERO) / Decimal(len(prior)) if prior else None
        if average not in (None, ZERO):
            volume_ratio = volumes[-1] / average
    metrics = {
        "trade_date": latest.get("date") if latest else None,
        "close_cny": _text(latest_close, 4),
        "return_3_session_pct": return_for(3),
        "return_5_session_pct": return_for(5),
        "return_20_session_pct": return_for(20),
        "volume_vs_prior_5d_avg": _text(volume_ratio, 2),
        "day_open_cny": _text(_decimal(latest.get("open")), 4) if latest else None,
        "day_high_cny": _text(_decimal(latest.get("high")), 4) if latest else None,
        "day_low_cny": _text(_decimal(latest.get("low")), 4) if latest else None,
    }
    summary = (
        f"截至收盘，3/5/20 个交易日涨跌幅分别为 "
        f"{metrics['return_3_session_pct']}%/{metrics['return_5_session_pct']}%/"
        f"{metrics['return_20_session_pct']}%；这是概率性趋势描述，不是买卖保证。"
        if latest
        else "缺少报告日之前的日线，无法形成轻量趋势判断。"
    )
    return {
        "status": "available" if latest else "missing",
        "scope": "report_cutoff_technical_delta",
        "summary": summary,
        "metrics": metrics,
        "observations": [],
        "source_refs": (
            [
                f"baostock.query_history_k_data_plus:{code}:"
                f"through:{latest.get('date')}:daily"
            ]
            if latest
            else []
        ),
    }


def fetch_p1_decision_context(
    *,
    ts_code: str,
    name: str,
    industry_name: str,
    report_date: date,
    module: Any | None = None,
) -> dict[str, Any]:
    """Fetch a bounded, read-only P1 context slice from BaoStock."""

    selected = module or importlib.import_module("baostock")
    output = io.StringIO()
    with redirect_stdout(output):
        login = selected.login()
    if str(getattr(login, "error_code", "")) not in {"", "0"}:
        raise PeriodicContextError("BaoStock login failed")

    code = _baostock_code(ts_code)
    start = report_date - timedelta(days=60)
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )
    try:
        stock_rows = _daily_rows(
            selected,
            code=code,
            start=start,
            end=report_date,
            full_fields=True,
        )
        profit_rows = _profit_rows(selected, code, report_date)
        intraday = _intraday_rows(selected, code, report_date)
        benchmarks: list[tuple[str, str, dict[str, str] | None]] = []
        for benchmark_code, benchmark_name in (
            ("sz.399001", "深证成指"),
            ("sh.000300", "沪深300"),
        ):
            rows = _daily_rows(
                selected,
                code=benchmark_code,
                start=report_date,
                end=report_date,
                full_fields=False,
            )
            benchmarks.append(
                (benchmark_code, benchmark_name, rows[-1] if rows else None)
            )
        sector_spec = _P1_SECTOR_INDEX.get(industry_name)
        sector: tuple[str, str, dict[str, str] | None] | None = None
        if sector_spec:
            sector_code, sector_name = sector_spec
            rows = _daily_rows(
                selected,
                code=sector_code,
                start=report_date,
                end=report_date,
                full_fields=False,
            )
            sector = (sector_code, sector_name, rows[-1] if rows else None)
    finally:
        with redirect_stdout(output):
            selected.logout()

    latest = stock_rows[-1] if stock_rows else None
    return {
        "schema_version": "investment_review.periodic_context.v1",
        "subject": {"ts_code": ts_code, "name": name, "industry_name": industry_name},
        "as_of": report_date.isoformat(),
        "fetched_at": fetched_at,
        "provider": "baostock",
        "fundamental_and_valuation": _fundamental_context(
            profit_rows,
            valuation_row=latest,
            code=code,
        ),
        "market_and_sector": _market_context(
            stock_row=latest,
            benchmarks=benchmarks,
            sector=sector,
            code=code,
        ),
        "technical_and_trend": _technical_context(stock_rows, code=code),
        "intraday_bars": intraday,
        "timing_policy": (
            "operation motives may use only completed intraday bars no later than "
            "the operation; report-day close and index/sector outcomes are retrospective"
        ),
    }
