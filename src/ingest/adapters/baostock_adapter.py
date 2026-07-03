from __future__ import annotations

import argparse
import importlib.util
import json
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
    parser.add_argument("--dry-run", action="store_true")
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
    return importlib.util.find_spec("baostock") is not None


def blocked_payload(args: argparse.Namespace, reason: str) -> dict[str, object]:
    return {
        "source_name": "baostock",
        "api_name": args.api_name,
        "adapter_status": "blocked",
        "result": "BLOCKED",
        "permission_note": reason,
        "notes": "Use fixture mode when Baostock package or network session is unavailable.",
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.api_name not in SUPPORTED_APIS:
        raise SystemExit(f"Unsupported Baostock API for first batch: {args.api_name}")

    has_fixture = bool(args.fixture_csv or args.fixture_json)
    if has_fixture:
        return structured_main(_structured_args(args, dry_run=False))

    if args.dry_run and package_available():
        return structured_main(_structured_args(args, dry_run=True))

    reason = "baostock package unavailable" if not package_available() else "live Baostock call deferred"
    payload = blocked_payload(args, reason)
    if args.readout_output:
        write_readout(output_path(Path(args.repo_root).resolve(), args.readout_output, Path("readout.json")), payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
