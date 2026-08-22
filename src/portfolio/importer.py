from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from .models import (
    ClosePrice,
    ImportIssue,
    Instrument,
    LedgerEntry,
    OpeningParseResult,
    StatementParseResult,
    ZERO,
    decimal_to_text,
)


@dataclass(frozen=True)
class TabularData:
    source_name: str
    source_sha256: str
    rows: list[list[str]]


STATEMENT_ALIASES: dict[str, tuple[str, ...]] = {
    "event_date": ("event_date", "成交日期", "发生日期", "交易日期", "委托日期", "日期"),
    "event_time": ("event_time", "成交时间", "发生时间", "交易时间", "时间"),
    "ts_code": ("ts_code", "证券代码", "股票代码", "基金代码", "代码"),
    "name": ("name", "证券名称", "股票名称", "证券简称", "基金名称", "名称"),
    "event_type": (
        "event_type",
        "买卖标志",
        "买卖方向",
        "交易方向",
        "业务名称",
        "业务类型",
        "发生业务",
        "操作",
        "摘要",
    ),
    "quantity": ("quantity", "成交数量", "成交股数", "发生数量", "证券数量", "数量"),
    "price": ("price", "成交价格", "成交均价", "成交价", "价格"),
    "gross_amount": ("gross_amount", "成交金额", "成交额"),
    "net_amount": (
        "net_amount",
        "发生金额",
        "清算金额",
        "资金发生数",
        "资金变动",
        "净发生金额",
        "实际发生金额",
    ),
    "total_fee": ("total_fee", "手续费", "费用合计", "交易费用", "手续费合计"),
    "commission": ("commission", "佣金", "券商佣金"),
    "stamp_tax": ("stamp_tax", "印花税"),
    "transfer_fee": ("transfer_fee", "过户费"),
    "regulatory_fee": ("regulatory_fee", "规费", "经手费", "证管费"),
    "other_fee": ("other_fee", "其他费", "结算费", "附加费", "其他费用"),
    "external_id": (
        "external_id",
        "成交编号",
        "合同编号",
        "流水号",
        "申报合同号",
        "成交序号",
    ),
}

OPENING_ALIASES: dict[str, tuple[str, ...]] = {
    "as_of_date": ("as_of_date", "基准日", "截止日期", "快照日期", "日期"),
    "price_date": ("price_date", "行情日期", "收盘日期"),
    "ts_code": ("ts_code", "证券代码", "股票代码", "基金代码", "代码"),
    "name": ("name", "证券名称", "股票名称", "证券简称", "基金名称", "名称"),
    "asset_type": ("asset_type", "资产类型", "证券类型"),
    "quantity": ("quantity", "持仓数量", "证券数量", "数量"),
    "cost_price": ("cost_price", "成本价", "平均成本"),
    "total_cost": ("total_cost", "成本金额", "持仓成本", "总成本"),
    "last_close": ("last_close", "close", "最新价", "收盘价", "市价"),
    "pct_chg": ("pct_chg", "涨跌幅", "当日涨跌幅"),
    "market_value": ("market_value", "市值", "最新市值"),
    "unrealized_pnl": ("unrealized_pnl", "浮动盈亏", "持仓盈亏", "盈亏"),
    "note": ("note", "备注", "说明"),
}

FEE_COMPONENTS = ("commission", "stamp_tax", "transfer_fee", "regulatory_fee", "other_fee")
FEE_RULE_VERSION = "historical_fee_rule_v1"
CONVERTIBLE_BOND_FEE_RULE_VERSION = "online_convertible_bond_fee_rule_v1"
PRIMARY_BOND_SUBSCRIPTION_FEE_RULE_VERSION = (
    "online_primary_bond_subscription_fee_exempt_v1"
)
FEE_MONEY_QUANTUM = Decimal("0.01")
ETF_FEE_RATE = Decimal("0.0001")
ETF_MINIMUM_FEE = Decimal("0.10")
EQUITY_COMMISSION_RATE = Decimal("0.0001158")
EQUITY_MINIMUM_COMMISSION = Decimal("5.00")
EQUITY_TRANSFER_FEE_RATE = Decimal("0.00001")
EQUITY_SELL_STAMP_TAX_RATE = Decimal("0.0005")
CONVERTIBLE_BOND_CODE_PREFIXES = ("110", "111", "113", "118", "123", "127", "128")
# SSE and SZSE both charge 0.004% bilaterally.
CONVERTIBLE_BOND_EXCHANGE_FEE_RATE = Decimal("0.00004")


def normalize_header(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    return re.sub(r"[\s_\-—:：/\\()（）\[\]【】.]+", "", text)


def _alias_lookup(aliases: dict[str, tuple[str, ...]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for canonical, candidates in aliases.items():
        for candidate in candidates:
            result[normalize_header(candidate)] = canonical
    return result


def _clean_cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "nat", "none"}:
        return ""
    excel_text = re.fullmatch(r'=\"(.*)\"', text, flags=re.DOTALL)
    if excel_text:
        return excel_text.group(1).replace('""', '"')
    return text


def read_tabular(path: str | Path, sheet: str | int | None = None) -> TabularData:
    source_path = Path(path)
    if not source_path.is_file():
        raise FileNotFoundError(f"输入文件不存在: {source_path}")
    raw = source_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    suffix = source_path.suffix.lower()

    is_ooxml = raw.startswith(b"PK\x03\x04")
    is_ole_workbook = raw.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    if suffix in {".xlsx", ".xls"} and (is_ooxml or is_ole_workbook):
        try:
            import pandas as pd
        except ModuleNotFoundError as exc:
            raise RuntimeError("读取 Excel 交割单需要 pandas/openpyxl") from exc
        try:
            frame = pd.read_excel(
                source_path,
                header=None,
                dtype=str,
                sheet_name=0 if sheet is None else sheet,
                keep_default_na=False,
            )
        except Exception as exc:
            raise RuntimeError(f"无法读取 Excel 交割单 {source_path.name}: {exc}") from exc
        rows = [[_clean_cell(value) for value in row] for row in frame.values.tolist()]
        return TabularData(source_path.name, digest, rows)

    decoded: str | None = None
    for encoding in ("utf-8-sig", "gb18030", "utf-16", "utf-8"):
        try:
            decoded = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if decoded is None:
        raise RuntimeError(f"无法识别文本编码: {source_path.name}")

    if suffix == ".tsv" or "\t" in decoded.partition("\n")[0]:
        delimiter = "\t"
    else:
        try:
            delimiter = csv.Sniffer().sniff(decoded[:8192], delimiters=",\t;|").delimiter
        except csv.Error:
            delimiter = ","
    rows = [[_clean_cell(value) for value in row] for row in csv.reader(io.StringIO(decoded), delimiter=delimiter)]
    return TabularData(source_path.name, digest, rows)


def _header_mapping(
    rows: list[list[str]],
    aliases: dict[str, tuple[str, ...]],
    *,
    required: set[str],
    one_of: set[str],
) -> tuple[int, dict[str, int]]:
    lookup = _alias_lookup(aliases)
    best: tuple[int, int, dict[str, int]] | None = None
    for row_index, row in enumerate(rows[:40]):
        mapping: dict[str, int] = {}
        for column_index, value in enumerate(row):
            canonical = lookup.get(normalize_header(value))
            if canonical and canonical not in mapping:
                mapping[canonical] = column_index
        score = len(mapping)
        if required.issubset(mapping) and (not one_of or one_of.intersection(mapping)):
            if best is None or score > best[0]:
                best = (score, row_index, mapping)
    if best is None:
        expected = ", ".join(sorted(required))
        raise ValueError(f"未识别到表头；至少需要字段: {expected}")
    return best[1], best[2]


def _value(row: list[str], mapping: dict[str, int], key: str) -> str:
    index = mapping.get(key)
    if index is None or index >= len(row):
        return ""
    return _clean_cell(row[index])


def parse_decimal(value: Any, *, required: bool = False, field: str = "数值") -> Decimal | None:
    text = unicodedata.normalize("NFKC", _clean_cell(value)).strip()
    if text in {"", "-", "--", "/", "N/A", "n/a"}:
        if required:
            raise ValueError(f"{field}为空")
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    text = (
        text.replace(",", "")
        .replace("，", "")
        .replace("￥", "")
        .replace("¥", "")
        .replace("元", "")
        .replace("股", "")
        .replace("份", "")
        .replace("%", "")
        .replace(" ", "")
    )
    try:
        result = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"{field}不是有效数字: {value!r}") from exc
    return -result if negative else result


def parse_date_value(value: Any, *, field: str = "日期") -> date:
    text = unicodedata.normalize("NFKC", _clean_cell(value)).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    if text.isdigit() and len(text) == 8:
        return datetime.strptime(text, "%Y%m%d").date()
    if text.isdigit() and 20000 <= int(text) <= 80000:
        return date(1899, 12, 30) + timedelta(days=int(text))
    cleaned = text.split(" ", 1)[0].split("T", 1)[0]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"{field}不是有效日期: {value!r}")


def parse_time_value(value: Any) -> str:
    text = unicodedata.normalize("NFKC", _clean_cell(value)).strip()
    if not text:
        return ""
    if " " in text:
        text = text.rsplit(" ", 1)[-1]
    if re.fullmatch(r"\d{1,6}(?:\.0)?", text):
        digits = text.split(".", 1)[0].zfill(6)
        text = f"{digits[:2]}:{digits[2:4]}:{digits[4:6]}"
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.strftime("%H:%M:%S")
        except ValueError:
            continue
    raise ValueError(f"成交时间不是有效时间: {value!r}")


def normalize_ts_code(value: Any) -> str:
    text = unicodedata.normalize("NFKC", _clean_cell(value)).upper().strip().lstrip("'")
    text = text.replace(" ", "")
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    match = re.fullmatch(r"(SH|SZ|BJ)[.-]?(\d{6})", text)
    if match:
        return f"{match.group(2)}.{match.group(1)}"
    match = re.fullmatch(r"(\d{6})[.-]?(SH|SZ|BJ)", text)
    if match:
        return f"{match.group(1)}.{match.group(2)}"
    if not re.fullmatch(r"\d{6}", text):
        raise ValueError(f"证券代码格式无法识别: {value!r}")
    if text.startswith(("4", "8", "920")):
        exchange = "BJ"
    elif text.startswith(("5", "6", "9")):
        exchange = "SH"
    elif text.startswith(("0", "1", "2", "3")):
        exchange = "SZ"
    else:
        raise ValueError(f"无法根据证券代码判断交易所: {value!r}")
    return f"{text}.{exchange}"


def infer_asset_type(ts_code: str, raw_type: str = "") -> str:
    normalized_type = normalize_header(raw_type)
    if any(token in normalized_type for token in ("etf", "基金", "lof")):
        return "etf"
    if any(token in normalized_type for token in ("股票", "ashare", "equity")):
        return "equity"
    code = ts_code.split(".", 1)[0]
    if code.startswith(("15", "16", "18", "50", "51", "52", "55", "56", "58")):
        return "etf"
    if code.startswith(("110", "111", "113", "118", "123", "127", "128")):
        return "unknown"
    return "equity"


def _round_fee(value: Decimal) -> Decimal:
    return value.quantize(FEE_MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _is_convertible_bond(ts_code: str | None) -> bool:
    code = str(ts_code or "").split(".", 1)[0]
    return code.startswith(CONVERTIBLE_BOND_CODE_PREFIXES)


def _is_primary_bond_subscription(raw_event: str) -> bool:
    return "新债入账" in normalize_header(raw_event)


def formal_fee_rule_version(*, asset_type: str, ts_code: str | None = None) -> str:
    if str(asset_type).strip().lower() in {"equity", "etf"}:
        return FEE_RULE_VERSION
    if _is_convertible_bond(ts_code):
        return CONVERTIBLE_BOND_FEE_RULE_VERSION
    raise ValueError(
        f"证券 {ts_code or '<unknown>'} 没有可应用的正式手续费规则"
    )


def calculate_historical_trade_fee(
    gross_amount: Decimal,
    *,
    asset_type: str,
    event_type: str,
    ts_code: str | None = None,
) -> Decimal:
    """Apply the user-confirmed formal fee rule for a supported security."""

    normalized_asset_type = str(asset_type).strip().lower()
    normalized_event_type = str(event_type).strip().upper()
    if gross_amount <= ZERO:
        raise ValueError("历史手续费规则要求成交金额为正")
    if normalized_event_type not in {"BUY", "SELL"}:
        raise ValueError(f"历史手续费规则不支持业务类型: {event_type}")
    if normalized_asset_type == "etf":
        return _round_fee(max(ETF_MINIMUM_FEE, gross_amount * ETF_FEE_RATE))
    if normalized_asset_type == "equity":
        commission = _round_fee(
            max(EQUITY_MINIMUM_COMMISSION, gross_amount * EQUITY_COMMISSION_RATE)
        )
        transfer_fee = _round_fee(gross_amount * EQUITY_TRANSFER_FEE_RATE)
        stamp_tax = (
            _round_fee(gross_amount * EQUITY_SELL_STAMP_TAX_RATE)
            if normalized_event_type == "SELL"
            else ZERO
        )
        return commission + transfer_fee + stamp_tax
    if _is_convertible_bond(ts_code):
        return _round_fee(gross_amount * CONVERTIBLE_BOND_EXCHANGE_FEE_RATE)
    raise ValueError(
        f"证券 {ts_code or '<unknown>'} 没有可应用的正式手续费规则"
    )


def _classify_event(value: str) -> str | None:
    normalized = normalize_header(value)
    if not normalized:
        return None
    if any(token in normalized for token in ("融资", "融券", "买券还券", "卖券还款", "担保品")):
        return "UNSUPPORTED_CREDIT"
    if any(token in normalized for token in ("红股", "送股", "转增", "证券转入", "证券转出")):
        return "UNSUPPORTED_CORPORATE_ACTION"
    if (
        normalized in {"b", "buy"}
        or "买入" in normalized
        or "配股缴款" in normalized
        or any(token in normalized for token in ("新股入账", "新债入账"))
    ):
        return "BUY"
    if normalized in {"s", "sell"} or "卖出" in normalized:
        return "SELL"
    if any(
        token in normalized
        for token in ("红利入账", "红利入帐", "股息入账", "股息入帐", "现金红利", "红利派发")
    ):
        return "DIVIDEND"
    if any(token in normalized for token in ("红利差异税", "股息红利差异扣税", "红利税")):
        return "CASH_FEE"
    return None


def _dedupe_key(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_statement(
    path: str | Path,
    *,
    account_id: str,
    broker: str = "generic",
    sheet: str | int | None = None,
) -> StatementParseResult:
    table = read_tabular(path, sheet)
    result = StatementParseResult(table.source_name, table.source_sha256)
    header_index, mapping = _header_mapping(
        table.rows,
        STATEMENT_ALIASES,
        required={"event_date", "ts_code", "event_type"},
        one_of={"quantity", "gross_amount", "net_amount"},
    )

    for row_index, row in enumerate(table.rows[header_index + 1 :], start=header_index + 2):
        if not any(_clean_cell(value) for value in row):
            continue
        result.total_rows += 1
        raw_event = _value(row, mapping, "event_type")
        event_type = _classify_event(raw_event)
        raw_code = _value(row, mapping, "ts_code")
        raw_quantity = _value(row, mapping, "quantity")
        raw_amount = _value(row, mapping, "gross_amount") or _value(row, mapping, "net_amount")

        if event_type in {"UNSUPPORTED_CREDIT", "UNSUPPORTED_CORPORATE_ACTION"}:
            result.issues.append(
                ImportIssue(
                    row_index,
                    "error",
                    "暂不支持信用交易、红股/转增或证券转入转出；需先明确数量与成本口径",
                    raw_event,
                    raw_code,
                )
            )
            continue
        if event_type is None:
            if raw_code and (raw_quantity or raw_amount):
                result.issues.append(
                    ImportIssue(row_index, "error", "无法识别业务类型", raw_event, raw_code)
                )
            else:
                result.skipped_rows += 1
            continue

        try:
            event_date = parse_date_value(_value(row, mapping, "event_date"), field="成交日期")
            event_time = parse_time_value(_value(row, mapping, "event_time"))
            ts_code = normalize_ts_code(raw_code)
            name = _value(row, mapping, "name").strip() or ts_code
            asset_type = infer_asset_type(ts_code)
            external_id = _value(row, mapping, "external_id").strip()
            note_parts = [f"broker={broker}", f"raw_event={raw_event}"]

            if event_type in {"DIVIDEND", "CASH_FEE"}:
                amount = parse_decimal(
                    _value(row, mapping, "net_amount") or _value(row, mapping, "gross_amount"),
                    required=True,
                    field="现金发生额",
                )
                assert amount is not None
                cash_amount = abs(amount)
                quantity = price = gross = fees = ZERO
            else:
                quantity_value = parse_decimal(raw_quantity, required=True, field="成交数量")
                price_value = parse_decimal(_value(row, mapping, "price"), field="成交价格")
                gross_value = parse_decimal(
                    _value(row, mapping, "gross_amount"), field="成交金额"
                )
                assert quantity_value is not None
                quantity = abs(quantity_value)
                if quantity == ZERO:
                    raise ValueError("成交数量不能为 0")
                if gross_value is None and price_value is None:
                    raise ValueError("成交价格和成交金额不能同时为空")
                gross = abs(gross_value) if gross_value is not None else quantity * abs(price_value)
                price = abs(price_value) if price_value is not None else gross / quantity
                if gross <= ZERO or price <= ZERO:
                    raise ValueError("成交价格和成交金额必须为正")

                total_fee = parse_decimal(_value(row, mapping, "total_fee"), field="手续费")
                if total_fee is not None:
                    fees = abs(total_fee)
                    note_parts.append("fee_source=broker_actual")
                else:
                    components = [
                        parse_decimal(_value(row, mapping, key), field=key) for key in FEE_COMPONENTS
                    ]
                    explicit_components = [item for item in components if item is not None]
                    fees = sum((abs(item) for item in explicit_components), ZERO)
                    if explicit_components:
                        note_parts.append("fee_source=broker_actual")
                    else:
                        net_amount = parse_decimal(
                            _value(row, mapping, "net_amount"), field="资金发生额"
                        )
                        if net_amount is not None:
                            inferred = (
                                abs(net_amount) - gross
                                if event_type == "BUY"
                                else gross - abs(net_amount)
                            )
                            if inferred >= ZERO:
                                fees = inferred
                                note_parts.append("fees_inferred_from_net_amount=true")
                                note_parts.append("fee_source=broker_actual")
                        elif _is_primary_bond_subscription(raw_event):
                            fees = ZERO
                            note_parts.append(
                                "fee_rule="
                                + PRIMARY_BOND_SUBSCRIPTION_FEE_RULE_VERSION
                            )
                            note_parts.append("fee_source=formal_exemption")
                        else:
                            fees = calculate_historical_trade_fee(
                                gross,
                                asset_type=asset_type,
                                event_type=event_type,
                                ts_code=ts_code,
                            )
                            note_parts.append(
                                "fee_rule="
                                + formal_fee_rule_version(
                                    asset_type=asset_type,
                                    ts_code=ts_code,
                                )
                            )
                            note_parts.append("fee_source=rule_derived")
                net_amount_for_audit = parse_decimal(
                    _value(row, mapping, "net_amount"), field="资金发生额"
                )
                if gross_value is None and net_amount_for_audit is not None:
                    inferred_gross = (
                        abs(net_amount_for_audit) - fees
                        if event_type == "BUY"
                        else abs(net_amount_for_audit) + fees
                    )
                    if inferred_gross <= ZERO:
                        raise ValueError("资金发生额与手续费无法还原正的成交金额")
                    gross = inferred_gross
                    note_parts.append("gross_inferred_from_net_amount=true")
                cash_amount = ZERO

            payload = {
                "account_id": account_id,
                "event_date": event_date.isoformat(),
                "event_time": event_time,
                "event_type": event_type,
                "ts_code": ts_code,
                "quantity": decimal_to_text(quantity),
                "price": decimal_to_text(price),
                "gross_amount": decimal_to_text(gross),
                "fees": decimal_to_text(fees),
                "cash_amount": decimal_to_text(cash_amount),
                "external_id": external_id,
            }
            entry = LedgerEntry(
                account_id=account_id,
                event_date=event_date,
                event_time=event_time,
                event_type=event_type,
                ts_code=ts_code,
                quantity=quantity,
                price=price,
                gross_amount=gross,
                fees=fees,
                cash_amount=cash_amount,
                external_id=external_id,
                dedupe_key=_dedupe_key(payload),
                source_row=row_index,
                note="; ".join(note_parts),
            )
            result.entries.append(entry)
            result.instruments[ts_code] = Instrument(
                ts_code=ts_code,
                name=name,
                asset_type=asset_type,
            )
        except ValueError as exc:
            result.issues.append(
                ImportIssue(row_index, "error", str(exc), raw_event, raw_code)
            )

    return result


def parse_opening_snapshot(
    path: str | Path,
    *,
    account_id: str,
    sheet: str | int | None = None,
) -> OpeningParseResult:
    table = read_tabular(path, sheet)
    result = OpeningParseResult(table.source_name, table.source_sha256)
    header_index, mapping = _header_mapping(
        table.rows,
        OPENING_ALIASES,
        required={"as_of_date", "ts_code", "quantity"},
        one_of={"cost_price", "total_cost", "market_value"},
    )

    for row_index, row in enumerate(table.rows[header_index + 1 :], start=header_index + 2):
        if not any(_clean_cell(value) for value in row):
            continue
        result.total_rows += 1
        raw_code = _value(row, mapping, "ts_code")
        try:
            as_of_date = parse_date_value(_value(row, mapping, "as_of_date"), field="基准日")
            price_date_text = _value(row, mapping, "price_date")
            price_date = (
                parse_date_value(price_date_text, field="行情日期")
                if price_date_text
                else as_of_date
            )
            if price_date > as_of_date:
                raise ValueError("行情日期不能晚于期初基准日")
            ts_code = normalize_ts_code(raw_code)
            name = _value(row, mapping, "name").strip() or ts_code
            quantity_value = parse_decimal(
                _value(row, mapping, "quantity"), required=True, field="持仓数量"
            )
            assert quantity_value is not None
            quantity = abs(quantity_value)
            if quantity == ZERO:
                raise ValueError("持仓数量不能为 0")

            cost_price = parse_decimal(_value(row, mapping, "cost_price"), field="成本价")
            total_cost = parse_decimal(_value(row, mapping, "total_cost"), field="成本金额")
            market_value = parse_decimal(_value(row, mapping, "market_value"), field="市值")
            unrealized = parse_decimal(
                _value(row, mapping, "unrealized_pnl"), field="浮动盈亏"
            )
            close = parse_decimal(_value(row, mapping, "last_close"), field="收盘价")
            pct_chg = parse_decimal(_value(row, mapping, "pct_chg"), field="涨跌幅")

            if total_cost is None and market_value is not None and unrealized is not None:
                total_cost = market_value - unrealized
            if total_cost is None and cost_price is not None:
                total_cost = cost_price * quantity
            if total_cost is None:
                raise ValueError("需要 total_cost，或 market_value + unrealized_pnl，或 cost_price")
            if total_cost < ZERO:
                raise ValueError("持仓成本不能为负")
            if close is None and market_value is not None:
                close = market_value / quantity
            if close is not None and close <= ZERO:
                raise ValueError("收盘价必须为正")
            if close is not None and market_value is not None:
                if abs(close * quantity - market_value) > Decimal("0.05"):
                    raise ValueError("市值与收盘价 × 数量不一致")
            if market_value is not None and unrealized is not None:
                if abs((market_value - total_cost) - unrealized) > Decimal("0.05"):
                    raise ValueError("市值、成本金额与浮动盈亏不一致")

            asset_type = infer_asset_type(ts_code, _value(row, mapping, "asset_type"))
            note = _value(row, mapping, "note") or "manual_opening_snapshot"
            payload = {
                "account_id": account_id,
                "event_date": as_of_date.isoformat(),
                "event_type": "OPENING",
                "ts_code": ts_code,
                "quantity": decimal_to_text(quantity),
                "total_cost": decimal_to_text(total_cost),
            }
            result.entries.append(
                LedgerEntry(
                    account_id=account_id,
                    event_date=as_of_date,
                    event_type="OPENING",
                    ts_code=ts_code,
                    quantity=quantity,
                    total_cost=total_cost,
                    dedupe_key=_dedupe_key(payload),
                    source_row=row_index,
                    note=note,
                )
            )
            result.instruments[ts_code] = Instrument(ts_code, name, asset_type)
            if close is not None:
                result.prices.append(
                    ClosePrice(
                        ts_code=ts_code,
                        trade_date=price_date,
                        close=close,
                        pct_chg=pct_chg,
                        source="opening_snapshot",
                    )
                )
        except ValueError as exc:
            result.issues.append(ImportIssue(row_index, "error", str(exc), ts_code=raw_code))

    return result
