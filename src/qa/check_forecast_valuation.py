from __future__ import annotations

from pathlib import Path

import yaml


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def check_forecast_and_valuation(forecast_path: Path, valuation_path: Path, peer_csv: Path) -> list[str]:
    issues: list[str] = []
    forecast = _load(forecast_path)
    valuation = _load(valuation_path)
    if not forecast.get("key_assumptions"):
        issues.append("forecast_missing_assumptions")
    if not forecast.get("sensitivity"):
        issues.append("forecast_missing_sensitivity")
    if not valuation.get("as_of_date"):
        issues.append("valuation_missing_as_of_date")
    if not peer_csv.exists() or peer_csv.stat().st_size == 0:
        issues.append("peer_table_missing")
    return issues
