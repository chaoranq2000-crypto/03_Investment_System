#!/usr/bin/env python3
"""Validate Bundle 8 independent industry evidence handoff."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def _values(source: dict[str, Any], key: str) -> set[str]:
    value = source.get(key) or []
    if not isinstance(value, list):
        value = [value]
    return {str(item) for item in value if str(item)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pack")
    args = parser.parse_args()
    path = Path(args.pack)
    pack = _load(path)
    errors: list[str] = []
    if pack.get("artifact_type") != "R5_industry_evidence_pack":
        errors.append("artifact_type_mismatch")
    sources = pack.get("sources") or []
    if not isinstance(sources, list):
        errors.append("sources_not_list")
        sources = []

    demand: set[str] = set()
    supply: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            errors.append("source_not_mapping")
            continue
        if source.get("review_status") not in {"reviewed", "promoted", "accepted"}:
            errors.append(f"source_not_reviewed:{source.get('source_id', '')}")
        if source.get("independence") != "independent":
            errors.append(f"industry_source_not_independent:{source.get('source_id', '')}")
        underlying = str(source.get("underlying_source_id") or source.get("source_id") or "")
        classes = _values(source, "evidence_classes")
        if "industry_demand" in classes:
            demand.add(underlying)
        if "industry_supply_competition" in classes:
            supply.add(underlying)
    if len(demand) < 2:
        errors.append(f"industry_demand_underlying_below_minimum:{len(demand)}")
    if len(supply) < 2:
        errors.append(f"industry_supply_underlying_below_minimum:{len(supply)}")
    print(
        "industry_evidence_pack "
        f"decision={'pass' if not errors else 'fail'} demand={len(demand)} "
        f"supply={len(supply)} errors={len(errors)}"
    )
    if errors:
        for error in sorted(set(errors)):
            print(error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
