#!/usr/bin/env python3
"""Validate R5 market and peer input boundaries."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

FORBIDDEN_NUMERIC_FIELDS = {"current_price", "market_cap", "pe_ttm", "PE", "PB", "PS", "pb", "ps"}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data


def _has_reviewed_market_data(market: dict[str, Any]) -> bool:
    fields = market.get("market_fields")
    if not isinstance(fields, dict):
        return False
    return bool(market.get("as_of_date")) and all(fields.get(key) is not None for key in ["current_price", "market_cap"])


def _has_reviewed_peer_data(peer: dict[str, Any]) -> bool:
    return bool(peer.get("peer_selection_method")) and bool(peer.get("peer_set"))


def _unreviewed_numeric_fields(section: dict[str, Any], status: str) -> list[str]:
    fields = section.get("market_fields") or section.get("peer_metrics") or {}
    if not isinstance(fields, dict):
        return []
    if status not in {"TODO_MARKET_DATA", "TODO_PEER_DATA", "planned"}:
        return []
    return sorted(key for key in fields if key in FORBIDDEN_NUMERIC_FIELDS and fields.get(key) is not None)


def validate_inputs(market: dict[str, Any], peer: dict[str, Any], *, level: str = "source_gapped_research_draft") -> list[str]:
    errors: list[str] = []
    if market.get("artifact_type") != "R5_market_snapshot":
        errors.append("market.artifact_type must be R5_market_snapshot")
    if peer.get("artifact_type") != "R5_peer_snapshot":
        errors.append("peer.artifact_type must be R5_peer_snapshot")
    if market.get("no_live_api") is not True:
        errors.append("market.no_live_api must be true")
    if peer.get("no_live_api") is not True:
        errors.append("peer.no_live_api must be true")
    if not market.get("as_of_date") and market.get("missing_reason") != "TODO_MARKET_DATA":
        errors.append("market requires as_of_date or missing_reason TODO_MARKET_DATA")
    if not peer.get("peer_selection_method") and peer.get("missing_reason") != "TODO_PEER_DATA":
        errors.append("peer requires peer_selection_method or missing_reason TODO_PEER_DATA")

    for field in _unreviewed_numeric_fields(market, str(market.get("status", ""))):
        errors.append(f"market.{field} must stay null until reviewed")
    for field in _unreviewed_numeric_fields(peer, str(peer.get("status", ""))):
        errors.append(f"peer.{field} must stay null until reviewed")

    if level == "sample_quality_candidate":
        if not _has_reviewed_market_data(market):
            errors.append("sample_quality_candidate requires reviewed market snapshot")
        if not _has_reviewed_peer_data(peer):
            errors.append("sample_quality_candidate requires reviewed peer snapshot")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate R5 market and peer input stubs.")
    parser.add_argument("--market", required=True, type=Path)
    parser.add_argument("--peer", required=True, type=Path)
    parser.add_argument("--level", default="source_gapped_research_draft")
    args = parser.parse_args(argv)

    market = load_yaml(args.market)
    peer = load_yaml(args.peer)
    errors = validate_inputs(market, peer, level=args.level)
    payload = {
        "outcome": "accepted_with_todos" if not errors else "blocked",
        "level": args.level,
        "errors": errors,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
