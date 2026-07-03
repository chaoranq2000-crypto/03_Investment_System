from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from typing import Sequence

from structured_api_pull import main as structured_main
from structured_api_pull import output_path, write_readout


SUPPORTED_APIS = {
    "query_stock_basic",
    "query_history_k_data_plus",
    "query_profit_data",
    "query_balance_data",
    "query_cash_flow_data",
    "query_dupont_data",
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Baostock evidence-ingest adapter wrapper.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--api-name", required=True)
    parser.add_argument("--stock-code", required=True)
    parser.add_argument("--company-id", default="")
    parser.add_argument("--company-name", default="")
    parser.add_argument("--fixture-csv", default="")
    parser.add_argument("--fixture-json", default="")
    parser.add_argument("--mode", choices=["fixture", "dry-run", "live"], default="")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--frequency", default="d")
    parser.add_argument("--adjustflag", default="3")
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--publish-date", default="")
    parser.add_argument("--start-date", default="")
    parser.add_argument("--end-date", default="")
    parser.add_argument("--fields", default="")
    parser.add_argument("--unit", default="")
    parser.add_argument("--manifest-path", default="")
    parser.add_argument("--metrics-path", default="")
    parser.add_argument("--ingest-runs-path", default="")
    parser.add_argument("--log-dir", default="")
    parser.add_argument("--raw-dir", default="")
    parser.add_argument("--normalized-dir", default="")
    parser.add_argument("--readout-output", default="")
    return parser.parse_args(argv)


def _structured_args(args: argparse.Namespace, *, dry_run: bool) -> list[str]:
    command = [
        "--repo-root",
        args.repo_root,
        "--source-name",
        "baostock",
        "--api-name",
        args.api_name,
        "--stock-code",
        args.stock_code,
        "--company-id",
        args.company_id,
        "--company-name",
        args.company_name,
        "--as-of-date",
        args.as_of_date,
        "--publish-date",
        args.publish_date,
        "--start-date",
        args.start_date,
        "--end-date",
        args.end_date,
        "--fields",
        args.fields,
        "--unit",
        args.unit,
        "--license-note",
        "Baostock terms; login-query-logout required for live calls",
    ]
    if dry_run:
        command.append("--dry-run")
    if args.fixture_csv:
        command.extend(["--input-csv", args.fixture_csv])
    if args.fixture_json:
        command.extend(["--input-json", args.fixture_json])
    for option in [
        "manifest_path",
        "metrics_path",
        "ingest_runs_path",
        "log_dir",
        "raw_dir",
        "normalized_dir",
        "readout_output",
    ]:
        value = getattr(args, option)
        if value:
            command.extend([f"--{option.replace('_', '-')}", value])
    return command


def package_available() -> bool:
    if "baostock" in sys.modules:
        return True
    return importlib.util.find_spec("baostock") is not None


def _baostock_code(stock_code: str) -> str:
    if stock_code.startswith(("sh.", "sz.", "bj.")):
        return stock_code
    if stock_code.startswith(("60", "68")):
        return f"sh.{stock_code}"
    if stock_code.startswith(("43", "83", "87", "88", "92")):
        return f"bj.{stock_code}"
    return f"sz.{stock_code}"


def _year_quarter(args: argparse.Namespace) -> tuple[str, str]:
    date_value = args.end_date or args.as_of_date or args.start_date
    year = date_value[:4] if len(date_value) >= 4 else ""
    month = date_value[5:7] if "-" in date_value and len(date_value) >= 7 else date_value[4:6]
    try:
        quarter = str((int(month) - 1) // 3 + 1)
    except ValueError:
        quarter = ""
    return year, quarter


def _rows_from_result(result: object) -> list[dict[str, str]]:
    error_code = str(getattr(result, "error_code", "0"))
    if error_code not in {"0", ""}:
        message = getattr(result, "error_msg", "")
        raise RuntimeError(f"baostock query failed: {error_code} {message}")
    fields = list(getattr(result, "fields", []) or [])
    rows: list[dict[str, str]] = []
    while result.next():  # type: ignore[attr-defined]
        values = list(result.get_row_data())  # type: ignore[attr-defined]
        rows.append({field: value for field, value in zip(fields, values)})
    return rows


def _fetch_baostock_live_rows(args: argparse.Namespace) -> list[dict[str, str]]:
    import baostock as bs  # type: ignore[import-not-found]

    login_result = bs.login()
    if str(getattr(login_result, "error_code", "0")) not in {"0", ""}:
        message = getattr(login_result, "error_msg", "")
        raise RuntimeError(f"baostock login failed: {getattr(login_result, 'error_code', '')} {message}")
    try:
        code = _baostock_code(args.stock_code)
        if args.api_name == "query_history_k_data_plus":
            fields = args.fields or "date,code,open,high,low,close,volume,amount,adjustflag"
            result = bs.query_history_k_data_plus(
                code,
                fields,
                start_date=args.start_date,
                end_date=args.end_date or args.as_of_date,
                frequency=args.frequency,
                adjustflag=args.adjustflag,
            )
        else:
            year, quarter = _year_quarter(args)
            result = getattr(bs, args.api_name)(code=code, year=year, quarter=quarter)
        return _rows_from_result(result)
    finally:
        bs.logout()


def _run_structured_rows(args: argparse.Namespace, rows: list[dict[str, str]]) -> int:
    with tempfile.TemporaryDirectory(prefix="baostock_live_") as temp_dir:
        live_json = Path(temp_dir) / f"{args.api_name}_{args.stock_code}.json"
        live_json.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        command = _structured_args(args, dry_run=False)
        command.extend(["--input-json", str(live_json)])
        result = structured_main(command)
    if args.readout_output:
        payload = {
            "source_name": "baostock",
            "api_name": args.api_name,
            "mode": "live",
            "adapter_status": "live_completed",
            "result": "SUCCESS",
            "rows": len(rows),
            "frequency": args.frequency,
            "adjustflag": args.adjustflag,
            "notes": "live Baostock response used login-query-logout and was routed through structured_api_pull",
        }
        write_readout(output_path(Path(args.repo_root).resolve(), args.readout_output, Path("readout.json")), payload)
    return result


def blocked_payload(args: argparse.Namespace, reason: str) -> dict[str, object]:
    return {
        "source_name": "baostock",
        "api_name": args.api_name,
        "mode": args.mode or "auto",
        "allow_network": bool(args.allow_network),
        "adapter_status": "blocked",
        "result": "BLOCKED",
        "permission_note": reason,
        "notes": "Use fixture mode when Baostock package or network session is unavailable. Live mode must login-query-logout in a manual smoke pass.",
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.api_name not in SUPPORTED_APIS:
        raise SystemExit(f"Unsupported Baostock API for first batch: {args.api_name}")

    has_fixture = bool(args.fixture_csv or args.fixture_json)
    mode = args.mode or ("fixture" if has_fixture else "dry-run" if args.dry_run else "live")
    args.mode = mode

    if mode == "fixture":
        if not has_fixture:
            raise SystemExit("Baostock fixture mode requires --fixture-csv or --fixture-json")
        return structured_main(_structured_args(args, dry_run=False))

    if mode == "dry-run" or args.dry_run:
        if package_available():
            return structured_main(_structured_args(args, dry_run=True))
        reason = "baostock package unavailable"
        payload = blocked_payload(args, reason)
        if args.readout_output:
            write_readout(output_path(Path(args.repo_root).resolve(), args.readout_output, Path("readout.json")), payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    if mode != "live":
        raise SystemExit(f"Unsupported Baostock mode: {mode}")

    if not args.allow_network:
        reason = "live Baostock mode requires explicit --allow-network"
        payload = blocked_payload(args, reason)
        if args.readout_output:
            write_readout(output_path(Path(args.repo_root).resolve(), args.readout_output, Path("readout.json")), payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0
    if not package_available():
        reason = "baostock package unavailable"
        payload = blocked_payload(args, reason)
        if args.readout_output:
            write_readout(output_path(Path(args.repo_root).resolve(), args.readout_output, Path("readout.json")), payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0
    try:
        rows = _fetch_baostock_live_rows(args)
    except Exception as exc:
        payload = blocked_payload(args, f"live Baostock call failed before artifact write: {type(exc).__name__}: {exc}")
        if args.readout_output:
            write_readout(output_path(Path(args.repo_root).resolve(), args.readout_output, Path("readout.json")), payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0
    if not rows:
        payload = blocked_payload(args, "live Baostock call returned zero rows")
        if args.readout_output:
            write_readout(output_path(Path(args.repo_root).resolve(), args.readout_output, Path("readout.json")), payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0
    return _run_structured_rows(args, rows)


if __name__ == "__main__":
    raise SystemExit(main())
