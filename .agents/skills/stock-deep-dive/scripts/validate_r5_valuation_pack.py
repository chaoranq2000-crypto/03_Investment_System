#!/usr/bin/env python3
"""Validate an R5 valuation pack."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required: pip install pyyaml") from exc

MARKET_FIELDS = {"as_of_date", "current_price", "market_cap", "share_count"}
MULTIPLES = {"PE_TTM", "forward_PE", "PB", "PS"}
SCENARIO_FIELDS = {"method", "key_assumptions", "source_ids_or_missing_reason"}
FORBIDDEN = ["买入", "卖出", "持有", "仓位", "保证收益", "target price instruction"]


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("root YAML object must be a mapping")
    return data


def _is_missing_ok(obj: Any) -> bool:
    return isinstance(obj, dict) and bool(obj.get("missing_reason"))


def _walk_text(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(_walk_text(v) for v in value.values())
    if isinstance(value, list):
        return "\n".join(_walk_text(v) for v in value)
    return value if isinstance(value, str) else ""


def validate_valuation_pack(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("artifact_type") != "R5_valuation_pack":
        errors.append("artifact_type must be R5_valuation_pack")

    market = data.get("market_snapshot")
    if not isinstance(market, dict):
        errors.append("market_snapshot must be a mapping")
    else:
        for field in sorted(MARKET_FIELDS):
            if field not in market:
                errors.append(f"market_snapshot.{field} is required")
            elif market.get(field) is None and not market.get("missing_reason"):
                errors.append(f"market_snapshot.{field} requires missing_reason when value is null")

    multiples = data.get("multiples")
    if not isinstance(multiples, dict):
        errors.append("multiples must be a mapping")
    else:
        for key in sorted(MULTIPLES):
            value = multiples.get(key)
            if value is None:
                errors.append(f"multiples.{key} is required")
            elif isinstance(value, dict) and value.get("value") is None and not value.get("missing_reason"):
                errors.append(f"multiples.{key} requires missing_reason when value is null")

    peer = data.get("peer_context")
    if not isinstance(peer, dict):
        errors.append("peer_context must be a mapping")
    elif not (peer.get("peer_set") and peer.get("peer_multiples")) and not peer.get("missing_reason"):
        errors.append("peer_context requires peer_set and peer_multiples or missing_reason")

    scenarios = data.get("valuation_scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        errors.append("valuation_scenarios must be a non-empty list")
    else:
        for idx, row in enumerate(scenarios):
            if not isinstance(row, dict):
                errors.append(f"valuation_scenarios[{idx}] must be a mapping")
                continue
            missing = sorted(SCENARIO_FIELDS - set(row))
            if missing:
                errors.append(f"valuation_scenarios[{idx}] missing: {', '.join(missing)}")
            if not row.get("source_ids_or_missing_reason"):
                errors.append(f"valuation_scenarios[{idx}].source_ids_or_missing_reason is required")

    if data.get("sample_quality_allowed") is True:
        if not isinstance(market, dict) or any(market.get(field) is None for field in MARKET_FIELDS):
            errors.append("sample_quality_allowed requires complete market_snapshot")
        if isinstance(peer, dict) and peer.get("missing_reason"):
            errors.append("sample_quality_allowed requires peer context without missing_reason")

    text = _walk_text(data)
    for phrase in FORBIDDEN:
        if phrase in text:
            errors.append(f"forbidden valuation advice phrase: {phrase}")
    return errors


def derive_outcome(errors: list[str], data: dict[str, Any]) -> str:
    if errors:
        return "needs_fix"
    if "TODO" in str(data) or "missing_reason" in str(data):
        return "accepted_with_todos"
    return "accepted"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate R5 valuation pack YAML.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        data = load_yaml(args.path)
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
    print(f"OK: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
