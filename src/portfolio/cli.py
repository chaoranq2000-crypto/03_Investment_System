from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import unicodedata
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Sequence

from src.utils.tushare_client import get_tushare_pro

from .industries import IndustryFetchError, TushareIndustryProvider
from .importer import parse_date_value, parse_opening_snapshot, parse_statement
from .intraday import IntradayFetchError, IntradayService, build_intraday_provider
from .kline import KlineFetchError, KlineNotFoundError, KlineService, TushareKlineProvider
from .models import ImportIssue, decimal_to_text
from .prices import PriceFetchError, TushareCloseProvider
from .store import PortfolioStore
from .web import serve_dashboard


def _sheet(value: str | None) -> str | int | None:
    if value is None:
        return None
    return int(value) if value.isdigit() else value


def _quantized(value: Decimal | None, places: int, *, grouping: bool = False) -> str:
    if value is None:
        return "MISSING"
    quantum = Decimal("1").scaleb(-places)
    rounded = value.quantize(quantum, rounding=ROUND_HALF_UP)
    return f"{rounded:,.{places}f}" if grouping else f"{rounded:.{places}f}"


def _raw(value: Any) -> Any:
    if isinstance(value, Decimal):
        return decimal_to_text(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _raw(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_raw(item) for item in value]
    return value


def _display_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(char) in {"W", "F", "A"} else 1 for char in text)


def _pad(text: str, width: int, *, right: bool) -> str:
    padding = " " * max(0, width - _display_width(text))
    return padding + text if right else text + padding


def render_table(headers: list[str], rows: list[list[str]], right_columns: set[int]) -> str:
    widths = [
        max([_display_width(header), *(_display_width(row[index]) for row in rows)])
        for index, header in enumerate(headers)
    ]
    lines = [
        "  ".join(_pad(header, widths[index], right=index in right_columns) for index, header in enumerate(headers)),
        "  ".join("-" * width for width in widths),
    ]
    lines.extend(
        "  ".join(
            _pad(value, widths[index], right=index in right_columns)
            for index, value in enumerate(row)
        )
        for row in rows
    )
    return "\n".join(lines)


def _issue_lines(issues: list[ImportIssue]) -> list[str]:
    lines: list[str] = []
    for issue in issues:
        context = " ".join(item for item in (issue.ts_code, issue.raw_event) if item)
        lines.append(
            f"[{issue.severity}] 第 {issue.row_number} 行"
            f"{f' ({context})' if context else ''}: {issue.message}"
        )
    return lines


def _emit(text: str, output: str | None = None) -> None:
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + ("" if text.endswith("\n") else "\n"), encoding="utf-8")
        print(f"已写入: {path.resolve()}")
    else:
        print(text)


def command_init(args: argparse.Namespace, store: PortfolioStore) -> int:
    print(f"持仓数据库已就绪: {store.path.resolve()}")
    print(f"账户: {args.account} ({args.account_name})")
    return 0


def command_import_opening(args: argparse.Namespace, store: PortfolioStore) -> int:
    parsed = parse_opening_snapshot(
        args.input,
        account_id=args.account,
        sheet=_sheet(args.sheet),
    )
    if parsed.issues:
        print("\n".join(_issue_lines(parsed.issues)))
    if parsed.errors:
        print(f"期初快照存在 {len(parsed.errors)} 个错误，未写入数据库。", file=sys.stderr)
        return 2
    outcome = store.apply_opening_snapshot(
        account_id=args.account,
        instruments=parsed.instruments.values(),
        entries=parsed.entries,
        prices=parsed.prices,
        source_name=parsed.source_name,
        source_sha256=parsed.source_sha256,
        total_rows=parsed.total_rows,
    )
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0


def command_import_statement(args: argparse.Namespace, store: PortfolioStore) -> int:
    parsed = parse_statement(
        args.input,
        account_id=args.account,
        broker=args.broker,
        sheet=_sheet(args.sheet),
    )
    if parsed.issues:
        print("\n".join(_issue_lines(parsed.issues)))
    if parsed.errors:
        print(f"交割单存在 {len(parsed.errors)} 个错误，未写入数据库。", file=sys.stderr)
        return 2
    if not parsed.entries:
        print("交割单中没有可导入的成交或红利记录。", file=sys.stderr)
        return 2

    if args.included_in_opening:
        preview = store.preview_included_statement(args.account, parsed.entries)
        disposition = "included_in_opening"
    elif args.historical_closed:
        preview = store.preview_historical_closed_statement(args.account, parsed.entries)
        disposition = "historical_closed_ledger"
    else:
        preview = store.preview_statement(args.account, parsed.entries)
        disposition = "post_baseline_ledger"
    summary = {
        "mode": "apply" if args.apply else "preview",
        "disposition": disposition,
        "source": parsed.source_name,
        "source_sha256": parsed.source_sha256,
        "data_rows": parsed.total_rows,
        "accepted_entries": preview["accepted_entries"],
        "duplicate_entries": preview["duplicate_entries"],
        "skipped_rows": parsed.skipped_rows,
    }
    if not args.apply:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print("预览通过；确认后在同一命令末尾添加 --apply。")
        return 0

    if args.included_in_opening:
        outcome = store.record_included_statement(
            account_id=args.account,
            instruments=parsed.instruments.values(),
            entries=parsed.entries,
            broker=args.broker,
            source_name=parsed.source_name,
            source_sha256=parsed.source_sha256,
            total_rows=parsed.total_rows,
            skipped_rows=parsed.skipped_rows,
        )
    elif args.historical_closed:
        outcome = store.apply_historical_closed_statement(
            account_id=args.account,
            instruments=parsed.instruments.values(),
            entries=parsed.entries,
            broker=args.broker,
            source_name=parsed.source_name,
            source_sha256=parsed.source_sha256,
            total_rows=parsed.total_rows,
            skipped_rows=parsed.skipped_rows,
        )
    else:
        outcome = store.apply_statement(
            account_id=args.account,
            instruments=parsed.instruments.values(),
            entries=parsed.entries,
            broker=args.broker,
            source_name=parsed.source_name,
            source_sha256=parsed.source_sha256,
            total_rows=parsed.total_rows,
            skipped_rows=parsed.skipped_rows,
        )
    summary.update(outcome)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def command_refresh_prices(args: argparse.Namespace, store: PortfolioStore) -> int:
    as_of = parse_date_value(args.as_of, field="行情截止日") if args.as_of else date.today()
    if args.lookback_days < 1:
        raise ValueError("--lookback-days 必须大于 0")
    instruments = store.instruments_for_open_positions(args.account, as_of)
    if not instruments:
        print("当前没有需要更新行情的持仓。")
        return 0
    pro = get_tushare_pro(args.env_file)
    provider = TushareCloseProvider(pro)
    prices, missing = provider.fetch_many(
        instruments,
        as_of=as_of,
        lookback_days=args.lookback_days,
    )
    if missing and not args.allow_partial:
        raise PriceFetchError(
            "以下证券在回看窗口内没有收盘价，未写入任何行情: " + ", ".join(missing)
        )
    inserted = store.add_close_prices(prices)
    payload = {
        "requested_as_of": as_of.isoformat(),
        "fetched": len(prices),
        "new_observations": inserted,
        "missing": missing,
        "quotes": [
            {
                "ts_code": item.ts_code,
                "trade_date": item.trade_date.isoformat(),
                "close": decimal_to_text(item.close),
                "pct_chg": decimal_to_text(item.pct_chg),
                "source": item.source,
            }
            for item in prices
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def command_refresh_kline(args: argparse.Namespace, store: PortfolioStore) -> int:
    as_of = parse_date_value(args.as_of, field="K 线截止日") if args.as_of else date.today()
    provider = TushareKlineProvider(get_tushare_pro(args.env_file))
    payload = KlineService(store, account_id=args.account).refresh(
        provider,
        args.code,
        range_key=args.range,
        cycle_id=args.cycle_id,
        as_of=as_of,
    )
    print(json.dumps(_raw(payload), ensure_ascii=False, indent=2))
    return 0


def command_refresh_intraday(args: argparse.Namespace, store: PortfolioStore) -> int:
    trade_date = parse_date_value(args.date, field="分时交易日")
    as_of = parse_date_value(args.as_of, field="分时截止日") if args.as_of else date.today()
    payload = IntradayService(store, account_id=args.account).refresh(
        build_intraday_provider(args.env_file),
        args.code,
        trade_date=trade_date,
        cycle_id=args.cycle_id,
        as_of=as_of,
    )
    print(json.dumps(_raw(payload), ensure_ascii=False, indent=2))
    return 0


def command_refresh_industries(args: argparse.Namespace, store: PortfolioStore) -> int:
    instruments = store.instruments_for_open_positions(args.account)
    if not instruments:
        print("当前没有需要更新行业分类的持仓。")
        return 0
    provider = TushareIndustryProvider(get_tushare_pro(args.env_file))
    classifications, missing = provider.fetch_many(instruments)
    updated = store.set_industries(classifications)
    print(
        json.dumps(
            _raw({
                "fetched": len(classifications),
                "updated": updated,
                "missing": missing,
                "classifications": [
                    {
                        "ts_code": item.ts_code,
                        "industry_name": item.industry_name,
                        "source": item.source,
                        "method": item.method,
                        "source_date": item.source_date,
                        "confidence": item.confidence,
                        "classified_weight_coverage": item.classified_weight_coverage,
                        "constituent_count_coverage": item.constituent_count_coverage,
                        "top_industry_weight": item.top_industry_weight,
                    }
                    for item in classifications
                ],
            }),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_set_cash(args: argparse.Namespace, store: PortfolioStore) -> int:
    as_of = parse_date_value(args.as_of, field="现金余额日期") if args.as_of else date.today()
    snapshot = store.set_cash_balance(
        args.account,
        args.amount,
        as_of,
        source="user_provided",
        note=args.note,
    )
    print(json.dumps(_raw(snapshot), ensure_ascii=False, indent=2))
    return 0


def command_cash(args: argparse.Namespace, store: PortfolioStore) -> int:
    rows = store.cash_history(args.account, args.limit)
    if args.format == "json":
        _emit(json.dumps(rows, ensure_ascii=False, indent=2), args.output)
        return 0
    headers = ["余额日期", "现金余额", "来源", "备注", "记录时间"]
    table_rows = [
        [
            row["as_of_date"],
            _quantized(Decimal(row["amount"]), 2, grouping=True),
            row["source"],
            row["note"],
            row["recorded_at"],
        ]
        for row in rows
    ]
    _emit(render_table(headers, table_rows, right_columns={1}), args.output)
    return 0


def _portfolio_table(positions: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    headers = [
        "证券",
        "代码",
        "行业",
        "数量",
        "成本价",
        "收盘价",
        "收盘日",
        "市值",
        "浮动盈亏",
        "收益率",
        "基准日后已实现",
    ]
    rows = [
        [
            row["name"],
            row["ts_code"],
            row["industry_name"],
            _quantized(row["quantity"], 0, grouping=True),
            _quantized(row["average_cost"], 4),
            _quantized(row["close"], 4),
            row["price_date"] or "MISSING",
            _quantized(row["market_value"], 3, grouping=True),
            _quantized(row["unrealized_pnl"], 3, grouping=True),
            f"{_quantized(row['return_pct'], 2)}%" if row["return_pct"] is not None else "MISSING",
            _quantized(row["realized_pnl"], 3, grouping=True),
        ]
        for row in positions
    ]
    table = render_table(headers, rows, right_columns={3, 4, 5, 7, 8, 9, 10})
    summary_lines = [
        "",
        f"持仓数量: {summary['position_count']}",
        f"剩余成本: {_quantized(summary['remaining_cost'], 3, grouping=True)} CNY",
        f"证券市值: {_quantized(summary['market_value'], 3, grouping=True)} CNY",
        f"现金余额: {_quantized(summary['cash_balance'], 2, grouping=True)} CNY",
        f"总资产: {_quantized(summary['total_assets'], 3, grouping=True)} CNY",
        f"浮动盈亏: {_quantized(summary['unrealized_pnl'], 3, grouping=True)} CNY",
        (
            f"浮动收益率: {_quantized(summary['unrealized_return_pct'], 2)}%"
            if summary["unrealized_return_pct"] is not None
            else "浮动收益率: MISSING"
        ),
        f"基准日后已实现盈亏: {_quantized(summary['realized_pnl_since_baseline'], 3, grouping=True)} CNY",
    ]
    if summary["missing_prices"]:
        summary_lines.append("缺失行情: " + ", ".join(summary["missing_prices"]))
    return table + "\n" + "\n".join(summary_lines)


def _portfolio_csv(positions: list[dict[str, Any]]) -> str:
    fieldnames = [
        "ts_code",
        "name",
        "asset_type",
        "industry_name",
        "industry_source",
        "quantity",
        "average_cost",
        "remaining_cost",
        "close",
        "price_date",
        "pct_chg",
        "market_value",
        "unrealized_pnl",
        "return_pct",
        "realized_pnl_since_baseline",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in positions:
        writer.writerow(
            {
                "ts_code": row["ts_code"],
                "name": row["name"],
                "asset_type": row["asset_type"],
                "industry_name": row["industry_name"],
                "industry_source": row["industry_source"],
                "quantity": decimal_to_text(row["quantity"]),
                "average_cost": decimal_to_text(row["average_cost"]),
                "remaining_cost": decimal_to_text(row["remaining_cost"]),
                "close": decimal_to_text(row["close"]),
                "price_date": row["price_date"] or "",
                "pct_chg": decimal_to_text(row["pct_chg"]),
                "market_value": decimal_to_text(row["market_value"]),
                "unrealized_pnl": decimal_to_text(row["unrealized_pnl"]),
                "return_pct": decimal_to_text(row["return_pct"]),
                "realized_pnl_since_baseline": decimal_to_text(row["realized_pnl"]),
            }
        )
    return buffer.getvalue()


def command_show(args: argparse.Namespace, store: PortfolioStore) -> int:
    as_of = parse_date_value(args.as_of, field="报告截止日") if args.as_of else None
    positions, summary = store.position_report(args.account, as_of)
    if args.format == "json":
        text = json.dumps(_raw({"positions": positions, "summary": summary}), ensure_ascii=False, indent=2)
    elif args.format == "csv":
        text = _portfolio_csv(positions)
    else:
        text = _portfolio_table(positions, summary)
    _emit(text, args.output)
    return 0


def command_closed(args: argparse.Namespace, store: PortfolioStore) -> int:
    as_of = parse_date_value(args.as_of, field="报告截止日") if args.as_of else None
    cycles, summary = store.closed_position_report(args.account, as_of)
    if args.format == "json":
        _emit(
            json.dumps(
                _raw({"closed_positions": cycles, "summary": summary}),
                ensure_ascii=False,
                indent=2,
            ),
            args.output,
        )
        return 0

    headers = [
        "证券",
        "代码",
        "周期",
        "开始日",
        "清仓日",
        "清仓数量",
        "结转成本",
        "净卖出额",
        "清仓收益",
        "收益率",
    ]
    rows = [
        [
            row["name"],
            row["ts_code"],
            str(row["cycle_number"]),
            row["opened_on"].isoformat(),
            row["closed_on"].isoformat(),
            _quantized(row["sold_quantity"], 0, grouping=True),
            _quantized(row["cost_basis"], 3, grouping=True),
            _quantized(row["net_sale_proceeds"], 3, grouping=True),
            _quantized(row["realized_pnl"], 3, grouping=True),
            (
                f"{_quantized(row['return_pct'], 2)}%"
                if row["return_pct"] is not None
                else "MISSING"
            ),
        ]
        for row in cycles
    ]
    table = render_table(headers, rows, right_columns={2, 5, 6, 7, 8, 9})
    summary_lines = [
        "",
        f"完整清仓周期: {summary['cycle_count']}",
        f"涉及证券: {summary['security_count']}",
        f"累计清仓收益: {_quantized(summary['total_realized_pnl'], 3, grouping=True)} CNY",
        (
            f"累计清仓收益率: {_quantized(summary['return_pct'], 2)}%"
            if summary["return_pct"] is not None
            else "累计清仓收益率: MISSING"
        ),
        f"盈利 / 亏损: {summary['gain_count']} / {summary['loss_count']}",
        summary["calculation_note"],
    ]
    _emit(table + "\n" + "\n".join(summary_lines), args.output)
    return 0


def command_ledger(args: argparse.Namespace, store: PortfolioStore) -> int:
    rows = store.recent_ledger(args.account, args.limit)
    if args.format == "json":
        _emit(json.dumps(rows, ensure_ascii=False, indent=2), args.output)
        return 0
    headers = ["日期", "时间", "类型", "代码", "数量", "价格", "成交额", "费用", "现金额", "外部编号"]
    table_rows = [
        [
            row["event_date"],
            row["event_time"],
            row["event_type"],
            row["ts_code"],
            row["quantity"],
            row["price"],
            row["gross_amount"],
            row["fees"],
            row["cash_amount"],
            row["external_id"],
        ]
        for row in rows
    ]
    _emit(render_table(headers, table_rows, right_columns={4, 5, 6, 7, 8}), args.output)
    return 0


def command_reconciliations(args: argparse.Namespace, store: PortfolioStore) -> int:
    rows = store.recent_reconciliations(args.account, args.limit)
    if args.format == "json":
        _emit(json.dumps(rows, ensure_ascii=False, indent=2), args.output)
        return 0
    headers = [
        "日期",
        "时间",
        "类型",
        "代码",
        "数量",
        "价格",
        "成交额",
        "费用",
        "处理方式",
        "期初日",
    ]
    table_rows = [
        [
            row["event_date"],
            row["event_time"],
            row["event_type"],
            row["ts_code"],
            row["quantity"],
            row["price"],
            row["gross_amount"],
            row["fees"],
            row["disposition"],
            row["baseline_date"],
        ]
        for row in rows
    ]
    _emit(render_table(headers, table_rows, right_columns={4, 5, 6, 7}), args.output)
    return 0


def command_transfers(args: argparse.Namespace, store: PortfolioStore) -> int:
    rows = store.recent_internal_transfers(args.account, args.limit)
    if args.format == "json":
        _emit(json.dumps(rows, ensure_ascii=False, indent=2), args.output)
        return 0
    headers = [
        "转出日",
        "转入日",
        "代码",
        "数量",
        "转出券商",
        "转入券商",
        "参考价",
        "状态",
    ]
    table_rows = [
        [
            row["transfer_out_date"],
            row["transfer_in_date"],
            row["ts_code"],
            row["quantity"],
            row["from_broker"],
            row["to_broker"],
            row["reference_price"],
            row["status"],
        ]
        for row in rows
    ]
    _emit(render_table(headers, table_rows, right_columns={3, 6}), args.output)
    return 0


def command_web(args: argparse.Namespace, store: PortfolioStore) -> int:
    serve_dashboard(
        store,
        account_id=args.account,
        env_file=args.env_file,
        host=args.host,
        port=args.port,
        open_browser=not args.no_open,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="portfolio-tracker",
        description="本地持仓台账、交割单成本重算与 Tushare 收盘价更新。",
    )
    parser.add_argument("--db", default="data/db/portfolio.sqlite3", help="本地 SQLite 路径")
    parser.add_argument("--account", default="default", help="账户 ID")
    parser.add_argument("--account-name", default="默认账户", help="首次创建账户时使用的名称")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="初始化本地持仓数据库")
    init_parser.set_defaults(handler=command_init)

    opening_parser = subparsers.add_parser("import-opening", help="导入期初持仓快照")
    opening_parser.add_argument("--input", required=True, help="CSV/XLSX 期初持仓文件")
    opening_parser.add_argument("--sheet", help="Excel sheet 名或从 0 开始的序号")
    opening_parser.set_defaults(handler=command_import_opening)

    statement_parser = subparsers.add_parser("import-statement", help="预览或导入券商交割单")
    statement_parser.add_argument("--input", required=True, help="CSV/XLSX 交割单")
    statement_parser.add_argument("--sheet", help="Excel sheet 名或从 0 开始的序号")
    statement_parser.add_argument("--broker", default="generic", help="券商/导出来源标签")
    statement_mode = statement_parser.add_mutually_exclusive_group()
    statement_mode.add_argument(
        "--included-in-opening",
        action="store_true",
        help="登记基准日及以前、已包含在期初快照中的交割明细；不重复改变持仓",
    )
    statement_mode.add_argument(
        "--historical-closed",
        action="store_true",
        help="导入基准日前从零建仓且最终归零的完整已清仓流水",
    )
    statement_parser.add_argument("--apply", action="store_true", help="确认预览后实际写入")
    statement_parser.set_defaults(handler=command_import_statement)

    refresh_parser = subparsers.add_parser("refresh-prices", help="抓取最新可得收盘价")
    refresh_parser.add_argument("--env-file", default=".env.local", help="Tushare 本地配置")
    refresh_parser.add_argument("--as-of", help="只取该日或此前的最新收盘价")
    refresh_parser.add_argument("--lookback-days", type=int, default=60)
    refresh_parser.add_argument("--allow-partial", action="store_true", help="允许部分证券缺失行情")
    refresh_parser.set_defaults(handler=command_refresh_prices)

    kline_parser = subparsers.add_parser(
        "refresh-kline", help="显式更新某一持仓周期的前复权日 K 线"
    )
    kline_parser.add_argument("--code", required=True, help="证券 Tushare 代码")
    kline_parser.add_argument(
        "--range", choices=("3m", "1y", "cycle"), default="3m", help="展示区间"
    )
    kline_parser.add_argument("--cycle-id", help="已清仓周期 ID；当前周期可省略")
    kline_parser.add_argument("--as-of", help="行情与台账截止日，默认今天")
    kline_parser.add_argument("--env-file", default=".env.local", help="Tushare 本地配置")
    kline_parser.set_defaults(handler=command_refresh_kline)

    intraday_parser = subparsers.add_parser(
        "refresh-intraday", help="显式更新某一持仓周期的单日分钟行情"
    )
    intraday_parser.add_argument("--code", required=True, help="证券 Tushare 代码")
    intraday_parser.add_argument("--date", required=True, help="交易日 YYYY-MM-DD")
    intraday_parser.add_argument("--cycle-id", help="已清仓周期 ID；当前周期可省略")
    intraday_parser.add_argument("--as-of", help="台账截止日，默认今天")
    intraday_parser.add_argument(
        "--env-file", default=".env.local", help="Tushare 本地配置"
    )
    intraday_parser.set_defaults(handler=command_refresh_intraday)

    industry_parser = subparsers.add_parser(
        "refresh-industries", help="更新股票与主题 ETF 的行业分类"
    )
    industry_parser.add_argument("--env-file", default=".env.local", help="Tushare 本地配置")
    industry_parser.set_defaults(handler=command_refresh_industries)

    set_cash_parser = subparsers.add_parser("set-cash", help="记录指定日期的账户现金余额")
    set_cash_parser.add_argument("--amount", type=Decimal, required=True, help="现金余额（CNY）")
    set_cash_parser.add_argument("--as-of", help="余额日期，默认今天")
    set_cash_parser.add_argument("--note", default="", help="可选来源说明")
    set_cash_parser.set_defaults(handler=command_set_cash)

    cash_parser = subparsers.add_parser("cash", help="查看现金余额快照历史")
    cash_parser.add_argument("--limit", type=int, default=100)
    cash_parser.add_argument("--format", choices=("table", "json"), default="table")
    cash_parser.add_argument("--output", help="可选输出文件")
    cash_parser.set_defaults(handler=command_cash)

    show_parser = subparsers.add_parser("show", help="查看当前或历史时点持仓盈亏")
    show_parser.add_argument("--as-of", help="按历史日期重放台账与行情")
    show_parser.add_argument("--format", choices=("table", "json", "csv"), default="table")
    show_parser.add_argument("--output", help="可选输出文件")
    show_parser.set_defaults(handler=command_show)

    closed_parser = subparsers.add_parser("closed", help="查看完整清仓周期与已实现收益")
    closed_parser.add_argument("--as-of", help="按历史日期重放清仓周期")
    closed_parser.add_argument("--format", choices=("table", "json"), default="table")
    closed_parser.add_argument("--output", help="可选输出文件")
    closed_parser.set_defaults(handler=command_closed)

    ledger_parser = subparsers.add_parser("ledger", help="查看最近成交台账")
    ledger_parser.add_argument("--limit", type=int, default=100)
    ledger_parser.add_argument("--format", choices=("table", "json"), default="table")
    ledger_parser.add_argument("--output", help="可选输出文件")
    ledger_parser.set_defaults(handler=command_ledger)

    reconciliation_parser = subparsers.add_parser(
        "reconciliations", help="查看已包含在期初快照中的交割核对明细"
    )
    reconciliation_parser.add_argument("--limit", type=int, default=100)
    reconciliation_parser.add_argument("--format", choices=("table", "json"), default="table")
    reconciliation_parser.add_argument("--output", help="可选输出文件")
    reconciliation_parser.set_defaults(handler=command_reconciliations)

    transfer_parser = subparsers.add_parser(
        "transfers", help="查看不影响组合成本与盈亏的内部托管迁移"
    )
    transfer_parser.add_argument("--limit", type=int, default=100)
    transfer_parser.add_argument("--format", choices=("table", "json"), default="table")
    transfer_parser.add_argument("--output", help="可选输出文件")
    transfer_parser.set_defaults(handler=command_transfers)

    web_parser = subparsers.add_parser("web", help="启动本地持仓可视化页面")
    web_parser.add_argument(
        "--host",
        choices=("127.0.0.1", "localhost", "::1"),
        default="127.0.0.1",
        help="只允许本机回环地址",
    )
    web_parser.add_argument("--port", type=int, default=8765, help="本地服务端口")
    web_parser.add_argument("--env-file", default=".env.local", help="Tushare 本地配置")
    web_parser.add_argument("--no-open", action="store_true", help="启动后不自动打开浏览器")
    web_parser.set_defaults(handler=command_web)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = PortfolioStore(args.db)
    try:
        store.initialize(args.account, args.account_name)
        return int(args.handler(args, store))
    except (
        ValueError,
        RuntimeError,
        KlineNotFoundError,
        KlineFetchError,
        IntradayFetchError,
        PriceFetchError,
        IndustryFetchError,
        OSError,
    ) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
