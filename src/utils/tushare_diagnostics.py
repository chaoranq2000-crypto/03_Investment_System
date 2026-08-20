"""Sanitized, read-only Tushare configuration and capability diagnostics."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from src.utils.tushare_client import (
    TUSHARE_TOKEN_ENV,
    get_tushare_pro,
    load_env_file,
    sanitize_provider_error,
    tushare_config_summary,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV = ROOT / ".env.local"
PROXY_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)
NO_PROXY_KEYS = ("NO_PROXY", "no_proxy")


def _effective_value(env: Mapping[str, str], key: str) -> str:
    return os.environ[key] if key in os.environ else env.get(key, "")


def probe_definitions(
    profile: str,
    *,
    today: date | None = None,
) -> tuple[dict[str, Any], ...]:
    end = today or date.today()
    start = end - timedelta(days=14)
    financial_start = end - timedelta(days=800)
    # Optional end-of-day and minute datasets should use a completed session;
    # the current trading day can legitimately be empty before publication.
    probe_day = end - timedelta(days=1)
    while probe_day.weekday() >= 5:
        probe_day -= timedelta(days=1)
    date_range = {
        "start_date": start.strftime("%Y%m%d"),
        "end_date": end.strftime("%Y%m%d"),
    }
    core: tuple[dict[str, Any], ...] = (
        {
            "api_name": "stock_basic",
            "required": True,
            "params": {
                "ts_code": "000001.SZ",
                "fields": "ts_code,symbol,name,industry,list_date",
            },
        },
        {
            "api_name": "daily",
            "required": True,
            "params": {
                "ts_code": "000001.SZ",
                **date_range,
                "fields": "ts_code,trade_date,open,high,low,close,vol,amount",
            },
        },
    )
    if profile == "core":
        return core
    if profile == "research":
        return (
            *core,
            {
                "api_name": "daily_basic",
                "required": True,
                "params": {
                    "ts_code": "000001.SZ",
                    **date_range,
                    "fields": "ts_code,trade_date,close,pe_ttm,pb,total_mv",
                },
            },
            {
                "api_name": "income",
                "required": True,
                "params": {
                    "ts_code": "000001.SZ",
                    "start_date": financial_start.strftime("%Y%m%d"),
                    "end_date": end.strftime("%Y%m%d"),
                    "fields": "ts_code,ann_date,end_date,total_revenue,n_income_attr_p",
                },
            },
        )
    if profile == "portfolio":
        return (
            *core,
            {
                "api_name": "adj_factor",
                "required": True,
                "params": {
                    "ts_code": "000001.SZ",
                    **date_range,
                    "fields": "ts_code,trade_date,adj_factor",
                },
            },
            {
                "api_name": "fund_daily",
                "required": True,
                "params": {
                    "ts_code": "510300.SH",
                    **date_range,
                    "fields": "ts_code,trade_date,open,high,low,close,vol,amount",
                },
            },
            {
                "api_name": "fund_adj",
                "required": True,
                "params": {
                    "ts_code": "510300.SH",
                    **date_range,
                    "fields": "ts_code,trade_date,adj_factor",
                },
            },
            {
                "api_name": "cb_daily",
                "required": False,
                "params": {
                    "trade_date": probe_day.strftime("%Y%m%d"),
                    "fields": "ts_code,trade_date,open,high,low,close,vol,amount",
                },
            },
            {
                "api_name": "stk_mins",
                "required": False,
                "params": {
                    "ts_code": "000001.SZ",
                    "freq": "1min",
                    "start_date": f"{probe_day.isoformat()} 09:00:00",
                    "end_date": f"{probe_day.isoformat()} 15:30:00",
                    "fields": "ts_code,trade_time,open,high,low,close,vol,amount",
                },
            },
            {
                "api_name": "etf_mins",
                "required": False,
                "params": {
                    "ts_code": "510300.SH",
                    "freq": "1min",
                    "start_date": f"{probe_day.isoformat()} 09:00:00",
                    "end_date": f"{probe_day.isoformat()} 15:30:00",
                    "fields": "ts_code,trade_time,open,high,low,close,vol,amount",
                },
            },
        )
    raise ValueError(f"unsupported diagnostic profile: {profile}")


def _token_meta(token: str) -> dict[str, Any]:
    return {
        "present": bool(token),
        "length": len(token),
        "has_whitespace": any(ch.isspace() for ch in token),
        "looks_like_placeholder": token.lower()
        in {"", "your_token_here", "replace_me", "fake-token"},
    }


def _token_date_meta(env: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in ("TUSHARE_TOKEN_START_AT", "TUSHARE_TOKEN_EXPIRES_AT"):
        value = env.get(key)
        if not value:
            result[key] = {"present": False}
            continue
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            now = datetime.now(parsed.tzinfo) if parsed.tzinfo else datetime.now()
            result[key] = {
                "present": True,
                "parse_ok": True,
                "iso": parsed.isoformat(),
                "days_delta": round((parsed - now).total_seconds() / 86400, 2),
            }
        except ValueError as exc:
            result[key] = {"present": True, "parse_ok": False, "error_type": type(exc).__name__}
    return result


def _no_proxy_matches(host: str, value: str) -> bool:
    normalized_host = host.lower().strip(".")
    for raw in value.split(","):
        entry = raw.strip()
        if not entry:
            continue
        if entry == "*":
            return True
        if "://" in entry:
            entry = urlsplit(entry).hostname or ""
        else:
            entry = entry.rsplit(":", 1)[0] if entry.count(":") == 1 else entry
        normalized_entry = entry.lower().lstrip(".").strip(".")
        if normalized_entry and (
            normalized_host == normalized_entry
            or normalized_host.endswith(f".{normalized_entry}")
        ):
            return True
    return False


def _proxy_meta(endpoint: str | None) -> dict[str, Any]:
    host = urlsplit(endpoint).hostname if endpoint else None
    no_proxy_values = [os.environ.get(key, "") for key in NO_PROXY_KEYS]
    return {
        "environment_proxy_present": any(os.environ.get(key) for key in PROXY_KEYS),
        "no_proxy_present": any(no_proxy_values),
        "endpoint_host_in_no_proxy": bool(
            host and any(_no_proxy_matches(host, value) for value in no_proxy_values)
        ),
        "values_redacted": True,
    }


def _sdk_version() -> str:
    try:
        return importlib.metadata.version("tushare")
    except importlib.metadata.PackageNotFoundError:
        return "not_installed"


def _probe_sdk(env_file: Path, *, profile: str) -> dict[str, Any]:
    env = load_env_file(env_file)
    token = _effective_value(env, TUSHARE_TOKEN_ENV)
    try:
        pro = get_tushare_pro(env_file)
    except Exception as exc:
        return {
            "status": "setup_error",
            "error_type": type(exc).__name__,
            "message": sanitize_provider_error(exc, secrets=(token,)),
        }

    probes: dict[str, Any] = {}
    for definition in probe_definitions(profile):
        api_name = str(definition["api_name"])
        required = bool(definition["required"])
        try:
            frame = getattr(pro, api_name)(**dict(definition["params"]))
            rows = int(len(frame))
            columns = [str(item) for item in getattr(frame, "columns", [])]
            expected_columns = [
                item.strip()
                for item in str(definition["params"].get("fields", "")).split(",")
                if item.strip()
            ]
            missing_columns = [item for item in expected_columns if item not in columns]
            status = "schema_mismatch" if missing_columns else "ok" if rows else "empty"
            probes[api_name] = {
                "status": status,
                "required": required,
                "rows": rows,
                "columns": columns,
                "missing_columns": missing_columns,
            }
        except Exception as exc:
            probes[api_name] = {
                "status": "error",
                "required": required,
                "error_type": type(exc).__name__,
                "message": sanitize_provider_error(exc, secrets=(token,)),
            }

    required_passed = all(
        item["status"] == "ok" for item in probes.values() if item["required"]
    )
    optional_failures = [
        name
        for name, item in probes.items()
        if not item["required"] and item["status"] != "ok"
    ]
    minute_names = ("stk_mins", "etf_mins")
    minute_capability = "not_probed"
    if profile == "portfolio":
        minute_capability = (
            "available"
            if all(probes[name]["status"] == "ok" for name in minute_names)
            else "unavailable_or_unverified"
        )
    return {
        "status": "ok" if required_passed else "required_probe_failed",
        "profile": profile,
        "tushare_version": _sdk_version(),
        "configured_endpoint": getattr(pro, "_DataApi__http_url", None),
        "probes": probes,
        "optional_failures": optional_failures,
        "minute_capability": minute_capability,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--profile", choices=("core", "research", "portfolio"), default="core")
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Run bounded read-only probes; otherwise diagnostics are configuration-only.",
    )
    args = parser.parse_args(argv)

    env = load_env_file(args.env_file)
    token = _effective_value(env, TUSHARE_TOKEN_ENV)
    summary = tushare_config_summary(args.env_file)
    config_valid = bool(
        summary["token_format_valid"]
        and summary["endpoint_status"] == "valid"
        and summary["proxy_setting_status"] == "valid"
    )

    output = {
        "env_file": str(args.env_file),
        "token": _token_meta(token),
        "token_dates": _token_date_meta(env),
        "configuration": summary,
        "proxy_environment": _proxy_meta(summary["endpoint"]),
        "network_policy": {
            "allow_network": bool(args.allow_network),
            "default": "configuration_only",
            "probe_kind": "bounded_read_only",
        },
        "sdk_probe": (
            _probe_sdk(args.env_file, profile=args.profile)
            if args.allow_network
            else {"status": "skipped_network_not_allowed", "profile": args.profile}
        ),
        "capability_boundary": {
            "profiles_are_live_checks_not_permission_guarantees": True,
            "portfolio_optional_endpoints": ["cb_daily", "stk_mins", "etf_mins"],
            "investment_review": "no_direct_tushare_dependency_in_main",
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

    if not config_valid:
        return 1
    if not args.allow_network:
        return 0
    return 0 if output["sdk_probe"].get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
