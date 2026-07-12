from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any


DEFAULT_TUSHARE_API_URL = "https://fast.xiaodefa.cn"


def _load_tushare() -> Any:
    try:
        return importlib.import_module("tushare")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The optional 'tushare' package is required only for live Tushare access; "
            "install it before calling get_tushare_pro()."
        ) from exc


def load_env_file(path: str | Path = ".env.local") -> dict[str, str]:
    env_path = Path(path)
    values: dict[str, str] = {}
    if not env_path.exists():
        return values

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def tushare_config_summary(path: str | Path = ".env.local") -> dict[str, Any]:
    values = {**load_env_file(path), **os.environ}
    token = values.get("TUSHARE_TOKEN", "").strip()
    api_url = (
        values.get("TUSHARE_HTTP_URL") or values.get("TUSHARE_API_URL") or DEFAULT_TUSHARE_API_URL
    ).strip()
    return {
        "token_present": bool(token),
        "token_length": len(token),
        "token_alnum": token.isalnum() if token else False,
        "api_url": api_url,
        "disable_proxy": values.get("TUSHARE_DISABLE_PROXY", "false").strip().lower()
        in {"1", "true", "yes", "y", "on"},
        "uses_proxy_url": api_url != "https://api.tushare.pro",
    }


def get_tushare_pro(path: str | Path = ".env.local", api_url: str | None = None) -> Any:
    values = {**load_env_file(path), **os.environ}
    token = values.get("TUSHARE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TUSHARE_TOKEN is missing")
    if len(token) != 56:
        raise RuntimeError(f"TUSHARE_TOKEN length should be 56, got {len(token)}")

    endpoint = (
        api_url
        or values.get("TUSHARE_HTTP_URL")
        or values.get("TUSHARE_API_URL")
        or DEFAULT_TUSHARE_API_URL
    ).strip()

    # The local guide requires setting the token through the SDK and then
    # overriding the private HTTP endpoint so requests go through the proxy.
    ts = _load_tushare()
    ts.set_token(token)
    pro = ts.pro_api()
    pro._DataApi__http_url = endpoint
    return pro
