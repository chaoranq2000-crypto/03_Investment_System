#!/usr/bin/env python3
"""Validate an R5 valuation pack."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

STATUSES = {"TODO", "partial", "ready", "blocked"}
MARKET_FIELDS = {
    "current_price",
    "market_cap",
    "share_count",
    "net_cash_or_net_debt",
    "enterprise_value",
    "pe_ttm",
    "forward_pe",
    "pb",
    "ps",
    "ev_ebitda",
}
FORBIDDEN = re.compile(
    r"买入|卖出|持有|仓位|目标价|保证收益|buy\s+rating|sell\s+rating|hold\s+rating|position\s+sizing|target\s+price\s+instruction",
    re.IGNORECASE,
)


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("root YAML object must be a mapping")
    return data


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_text(item) for item in value)
    return "" if value is None else str(value)


def _metric_value(obj: Any) -> Any:
    return obj.get("value") if isinstance(obj, dict) else obj


def _has_anchor(obj: Any, parent: dict[str, Any] | None = None) -> bool:
    if isinstance(obj, dict) and (obj.get("evidence_id") or obj.get("metric_id")):
        return True
    return bool(parent and (parent.get("evidence_id") or parent.get("metric_id")))


def _missing_reason(obj: Any, parent: dict[str, Any] | None = None) -> str | None:
    if isinstance(obj, dict) and obj.get("missing_reason"):
        return str(obj.get("missing_reason"))
    if parent and parent.get("missing_reason"):
        return str(parent.get("missing_reason"))
    return None


def validate_market_snapshot(market: Any, *, ready: bool) -> list[str]:
    if not isinstance(market, dict):
        return ["market_snapshot must be a mapping"]
    errors: list[str] = []
    if "as_of_date" not in market:
        errors.append("market_snapshot.as_of_date is required")
    for field in sorted(MARKET_FIELDS):
        if field not in market:
            errors.append(f"market_snapshot.{field} is required")
            continue
        obj = market[field]
        value = _metric_value(obj)
        if value is None:
            reason = _missing_reason(obj, market)
            if not reason:
                errors.append(f"market_snapshot.{field} requires missing_reason when value is null")
            if ready:
                errors.append(f"market_snapshot.{field} cannot be null when status is ready")
        elif not _has_anchor(obj, market):
            errors.append(f"market_snapshot.{field} requires evidence_id or metric_id when non-null")
    return errors


def validate_peer_context(peer: Any, *, ready: bool) -> list[str]:
    if not isinstance(peer, dict):
        return ["peer_valuation_context must be a mapping"]
    errors: list[str] = []
    rows = peer.get("rows")
    if rows is None and "peer_multiples" in peer:
        rows = peer.get("peer_multiples")
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        errors.append("peer_valuation_context.rows must be a list")
        return errors
    if ready and not rows:
        errors.append("status ready requires at least one peer valuation context row")
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"peer_valuation_context.rows[{idx}] must be a mapping")
            continue
        value = row.get("multiple_value", row.get("value"))
        if value is not None and not _has_anchor(row):
            errors.append(f"peer_valuation_context.rows[{idx}] requires evidence_id or metric_id when non-null")
    return errors


def validate_methods(methods: Any, *, ready: bool) -> list[str]:
    if not isinstance(methods, list):
        return ["valuation_methods must be a list"]
    errors: list[str] = []
    ready_supported = False
    for idx, method in enumerate(methods):
        if not isinstance(method, dict):
            errors.append(f"valuation_methods[{idx}] must be a mapping")
            continue
        if method.get("status") == "ready" and method.get("supported_output") is not None:
            ready_supported = True
            if method.get("method_type") == "forecast_dependent" and not (
                method.get("forecast_assumption_ids") or method.get("forecast_metric_ids")
            ):
                errors.append(f"valuation_methods[{idx}] forecast-dependent ready method requires forecast assumptions or metrics")
    if ready and not ready_supported:
        errors.append("status ready requires at least one valuation method with supported output")
    return errors


def validate_valuation_pack(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("artifact_type") != "R5_valuation_pack":
        errors.append("artifact_type must be R5_valuation_pack")
    if data.get("status") not in STATUSES:
        errors.append("status must be one of TODO, partial, ready, blocked")
    if FORBIDDEN.search(_text(data)):
        errors.append("forbidden valuation advice phrase found")

    ready = data.get("status") == "ready"
    errors.extend(validate_market_snapshot(data.get("market_snapshot"), ready=ready))
    peer = data.get("peer_valuation_context", data.get("peer_context"))
    errors.extend(validate_peer_context(peer, ready=ready))
    errors.extend(validate_methods(data.get("valuation_methods", []), ready=ready))

    if ready:
        market = data.get("market_snapshot")
        if not isinstance(market, dict) or not market.get("as_of_date"):
            errors.append("status ready requires dated market_snapshot.as_of_date")
    if data.get("sample_quality_allowed") is True and data.get("status") != "ready":
        errors.append("sample_quality_allowed requires status ready")
    return errors


def derive_outcome(errors: list[str], data: dict[str, Any]) -> str:
    if errors:
        return "needs_fix"
    if "TODO_MARKET_DATA" in _text(data) or "TODO_PEER_DATA" in _text(data) or "missing_reason" in _text(data):
        return "accepted_with_todos"
    return "accepted"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate R5 valuation pack YAML.")
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--input", dest="input_path", type=Path)
    args = parser.parse_args(argv)
    path = args.input_path or args.path
    if path is None:
        parser.error("an input path is required")
    try:
        data = load_yaml(path)
        errors = validate_valuation_pack(data)
    except Exception as exc:  # noqa: BLE001
        print("outcome: blocked")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    outcome = derive_outcome(errors, data)
    print(f"outcome: {outcome}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
