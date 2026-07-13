from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping
from typing import Sequence

from structured_api_pull import main as structured_main
from structured_api_pull import output_path, write_readout


SUPPORTED_APIS = {
    "stock_basic",
    "daily_basic",
    "daily",
    "pro_bar",
    "income",
    "balancesheet",
    "cashflow",
    "fina_indicator",
    "fina_mainbz",
    "disclosure_date",
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tushare evidence-ingest adapter wrapper.")
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
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--publish-date", default="")
    parser.add_argument("--start-date", default="")
    parser.add_argument("--end-date", default="")
    parser.add_argument("--fields", default="")
    parser.add_argument("--unit", default="")
    parser.add_argument("--token-env", default="TUSHARE_TOKEN")
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
        "tushare",
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
        "Tushare terms; token stored in environment only",
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


def _tushare_ts_code(stock_code: str) -> str:
    if "." in stock_code:
        return stock_code
    if stock_code.startswith(("00", "30")):
        return f"{stock_code}.SZ"
    if stock_code.startswith(("60", "68")):
        return f"{stock_code}.SH"
    if stock_code.startswith(("43", "83", "87", "88", "92")):
        return f"{stock_code}.BJ"
    return stock_code


def _clean_value(value: Any) -> str:
    if value is None:
        return ""
    try:
        if value != value:
            return ""
    except TypeError:
        pass
    return str(value)


def _records_from_result(result: Any) -> list[dict[str, str]]:
    if hasattr(result, "to_dict"):
        records = result.to_dict(orient="records")
    elif isinstance(result, list):
        records = result
    elif isinstance(result, Mapping):
        records = result.get("rows", [])
    else:
        records = []
    return [{str(key): _clean_value(value) for key, value in row.items()} for row in records]


def _live_params(args: argparse.Namespace) -> dict[str, str]:
    params: dict[str, str] = {}
    if args.api_name != "stock_basic":
        params["ts_code"] = _tushare_ts_code(args.stock_code)
    if args.api_name == "disclosure_date":
        # Tushare defines end_date here as the financial-report period, not a
        # date-range upper bound.  start_date is not a supported parameter.
        if args.end_date:
            params["end_date"] = args.end_date
        if args.fields:
            params["fields"] = args.fields
        return params
    for key in ["start_date", "end_date", "fields"]:
        value = getattr(args, key)
        if value:
            params[key] = value
    return params


def _fetch_tushare_live_rows(args: argparse.Namespace) -> list[dict[str, str]]:
    import tushare as ts  # type: ignore[import-not-found]

    ts.set_token(os.environ[args.token_env])
    pro = ts.pro_api()
    api_url = (
        os.environ.get("TUSHARE_HTTP_URL")
        or os.environ.get("TUSHARE_API_URL")
        or ""
    ).strip()
    if api_url:
        pro._DataApi__http_url = api_url
    params = _live_params(args)
    if args.api_name == "pro_bar":
        result = ts.pro_bar(api=pro, **params)
    else:
        result = getattr(pro, args.api_name)(**params)
    return _records_from_result(result)


def _run_structured_rows(args: argparse.Namespace, rows: list[dict[str, str]]) -> int:
    with tempfile.TemporaryDirectory(prefix="tushare_live_") as temp_dir:
        live_json = Path(temp_dir) / f"{args.api_name}_{args.stock_code}.json"
        live_json.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        command = _structured_args(args, dry_run=False)
        command.extend(["--input-json", str(live_json)])
        result = structured_main(command)
    if args.readout_output:
        payload = {
            "source_name": "tushare",
            "api_name": args.api_name,
            "mode": "live",
            "adapter_status": "live_completed",
            "result": "SUCCESS",
            "rows": len(rows),
            "token_env": args.token_env,
            "notes": "live Tushare response was routed through structured_api_pull; token value was not stored",
        }
        write_readout(output_path(Path(args.repo_root).resolve(), args.readout_output, Path("readout.json")), payload)
    return result


def blocked_payload(args: argparse.Namespace, reason: str) -> dict[str, object]:
    return {
        "source_name": "tushare",
        "api_name": args.api_name,
        "mode": args.mode or "auto",
        "allow_network": bool(args.allow_network),
        "adapter_status": "blocked",
        "result": "BLOCKED",
        "token_env": args.token_env,
        "permission_note": reason,
        "notes": "No API token value was stored. Use fixture or dry-run until live permission is ready.",
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.api_name not in SUPPORTED_APIS:
        raise SystemExit(f"Unsupported Tushare API for first batch: {args.api_name}")

    has_fixture = bool(args.fixture_csv or args.fixture_json)
    mode = args.mode or ("fixture" if has_fixture else "dry-run" if args.dry_run else "live")
    args.mode = mode

    if mode == "fixture":
        if not has_fixture:
            raise SystemExit("Tushare fixture mode requires --fixture-csv or --fixture-json")
        return structured_main(_structured_args(args, dry_run=False))

    if mode == "dry-run" or args.dry_run:
        return structured_main(_structured_args(args, dry_run=True))

    if mode != "live":
        raise SystemExit(f"Unsupported Tushare mode: {mode}")

    if not args.allow_network:
        payload = blocked_payload(args, "live Tushare mode requires explicit --allow-network")
        if args.readout_output:
            write_readout(output_path(Path(args.repo_root).resolve(), args.readout_output, Path("readout.json")), payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    if not os.environ.get(args.token_env):
        payload = blocked_payload(args, f"missing {args.token_env}")
        if args.readout_output:
            write_readout(output_path(Path(args.repo_root).resolve(), args.readout_output, Path("readout.json")), payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    try:
        rows = _fetch_tushare_live_rows(args)
    except Exception as exc:
        payload = blocked_payload(args, f"live Tushare call failed before artifact write: {type(exc).__name__}: {exc}")
        if args.readout_output:
            write_readout(output_path(Path(args.repo_root).resolve(), args.readout_output, Path("readout.json")), payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0
    if not rows:
        payload = blocked_payload(args, "live Tushare call returned zero rows")
        if args.readout_output:
            write_readout(output_path(Path(args.repo_root).resolve(), args.readout_output, Path("readout.json")), payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0
    return _run_structured_rows(args, rows)


if __name__ == "__main__":
    raise SystemExit(main())
