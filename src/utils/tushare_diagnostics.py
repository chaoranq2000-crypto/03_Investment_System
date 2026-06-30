"""Sanitized Tushare configuration and connectivity diagnostics."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV = ROOT / ".env.local"
DEFAULT_FIELDS = "ts_code,symbol,name,area,industry,list_date"
PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


def _load_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        data[key.strip()] = value.strip().strip("\"'")
    return data


def _parse_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _token_meta(token: str) -> dict[str, Any]:
    return {
        "present": bool(token),
        "length": len(token),
        "has_whitespace": any(ch.isspace() for ch in token),
        "looks_like_placeholder": token.lower() in {"", "your_token_here", "replace_me"},
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


def _proxy_meta() -> dict[str, Any]:
    return {
        key: {"present": key in os.environ, "length": len(os.environ.get(key, ""))}
        for key in PROXY_KEYS
    }


def _scrub(message: object, token: str) -> str:
    text = str(message)
    if token:
        text = text.replace(token, "<TOKEN>")
    return text[:1000]


def _probe_sdk(token: str, http_url: str, disable_proxy: bool) -> dict[str, Any]:
    old_proxy_env = {key: os.environ.get(key) for key in PROXY_KEYS}
    if disable_proxy:
        for key in PROXY_KEYS:
            os.environ.pop(key, None)
    try:
        import tushare as ts

        pro = ts.pro_api(token)
        if http_url:
            pro._DataApi__http_url = http_url

        result: dict[str, Any] = {
            "tushare_version": getattr(ts, "__version__", "unknown"),
            "http_url": getattr(pro, "_DataApi__http_url", None),
            "disable_proxy": disable_proxy,
        }
        try:
            df = pro.stock_basic(
                exchange="",
                list_status="L",
                fields=DEFAULT_FIELDS,
            )
            result["stock_basic"] = {"status": "ok", "rows": int(len(df))}
        except Exception as exc:  # noqa: BLE001 - diagnostic captures SDK failures.
            result["stock_basic"] = {
                "status": "error",
                "error_type": type(exc).__name__,
                "message": _scrub(exc, token),
            }

        try:
            df = pro.anns_d(
                ts_code="000001.SZ",
                start_date="20260701",
                end_date="20260701",
                fields="ann_date,ts_code,name,title,url",
            )
            result["anns_d"] = {"status": "ok", "rows": int(len(df))}
        except Exception as exc:  # noqa: BLE001 - permission errors are expected diagnostics.
            result["anns_d"] = {
                "status": "error",
                "error_type": type(exc).__name__,
                "message": _scrub(exc, token),
            }
        return result
    except Exception as exc:  # noqa: BLE001 - keep diagnostics self-contained.
        return {"setup_error_type": type(exc).__name__, "message": _scrub(exc, token)}
    finally:
        for key, value in old_proxy_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--http-url", default=None)
    parser.add_argument("--disable-proxy", action="store_true")
    args = parser.parse_args()

    env = _load_env(args.env_file)
    token = env.get("TUSHARE_TOKEN", "")
    http_url = args.http_url
    if http_url is None:
        http_url = env.get("TUSHARE_HTTP_URL") or env.get("TUSHARE_API_URL", "")
    disable_proxy = args.disable_proxy or _parse_bool(env.get("TUSHARE_DISABLE_PROXY"))

    output = {
        "env_file": str(args.env_file),
        "token": _token_meta(token),
        "token_dates": _token_date_meta(env),
        "configured_http_url": http_url or None,
        "proxy_environment": _proxy_meta(),
        "sdk_probe": _probe_sdk(token, http_url, disable_proxy) if token else {"status": "skipped_no_token"},
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

    probe = output["sdk_probe"]
    stock_basic = probe.get("stock_basic", {}) if isinstance(probe, dict) else {}
    return 0 if stock_basic.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
