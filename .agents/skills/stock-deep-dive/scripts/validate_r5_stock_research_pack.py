#!/usr/bin/env python3
"""Validate an R5_stock_research_pack YAML artifact for R5-MVP."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required: pip install pyyaml") from exc

CORE_PACKS = [
    "company_identity_pack",
    "evidence_snapshot_pack",
    "financial_history_pack",
    "business_breakdown_pack",
    "segment_exposure_pack",
    "industry_context_pack",
    "peer_comparison_pack",
    "forecast_model_pack",
    "valuation_pack",
    "technical_market_pack",
    "sentiment_event_pack",
    "risk_counterevidence_pack",
]
REQUIRED_TOP_LEVEL = [
    "schema_version",
    "artifact_type",
    "status",
    "stock",
    "quality_status",
    "source_gap_policy",
    *CORE_PACKS,
    "report_composition_pack",
]
REQUIRED_PACKS = [*CORE_PACKS, "report_composition_pack"]
MISSING_TOKENS = {"MISSING_DISCLOSURE", "TODO_SOURCE_REQUIRED", "TODO_MODEL_INPUT"}
FORECAST_YEARS = {"2026E", "2027E", "2028E"}
REQUIRED_FORECAST_METRICS = {"revenue", "gross_margin", "gross_profit", "net_profit_attributable", "eps"}
FORBIDDEN_ACTION_PHRASES = ["买入评级", "卖出评级", "持有评级", "建议买入", "建议卖出", "建议建仓", "仓位建议", "目标买点"]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError("root YAML object must be a mapping")
    return data


def _has_missing_explanation(value: Any) -> bool:
    return isinstance(value, dict) and any(k in value for k in ("missing_reason", "missing_items", "source_gap"))


def _check_metric_object(obj: dict[str, Any], path: str, errors: list[str]) -> None:
    if obj.get("value") is None and not _has_missing_explanation(obj):
        errors.append(f"{path}: value is null but missing_reason/missing_items/source_gap is absent")
    if obj.get("value") is not None and not (obj.get("evidence_id") or obj.get("metric_id")):
        errors.append(f"{path}: non-null value requires evidence_id or metric_id")


def _walk_text(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(_walk_text(v) for v in value.values())
    if isinstance(value, list):
        return "\n".join(_walk_text(v) for v in value)
    return value if isinstance(value, str) else ""


def _pack_status(data: dict[str, Any], pack_name: str) -> str | None:
    pack = data.get(pack_name)
    return pack.get("status") if isinstance(pack, dict) else None


def derive_outcome(data: dict[str, Any], errors: list[str]) -> str:
    if errors:
        return "blocked" if any("artifact_type" in error or "missing top-level" in error for error in errors) else "needs_fix"
    quality = data.get("quality_status") or {}
    if quality.get("high_issue_count") not in (None, 0, "0"):
        return "needs_fix"
    if any(_pack_status(data, pack_name) in {"TODO", "partial"} for pack_name in REQUIRED_PACKS):
        return "accepted_with_todos"
    if quality.get("medium_issue_count") not in (None, 0, "0"):
        return "accepted_with_todos"
    return "accepted"


def validate_pack(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_TOP_LEVEL:
        if key not in data:
            errors.append(f"missing top-level key: {key}")
    if data.get("artifact_type") != "R5_stock_research_pack":
        errors.append("artifact_type must be R5_stock_research_pack")

    tokens = set((data.get("source_gap_policy") or {}).get("missing_value_tokens") or [])
    missing_tokens = sorted(MISSING_TOKENS - tokens)
    if missing_tokens:
        errors.append(f"source_gap_policy.missing_value_tokens missing: {', '.join(missing_tokens)}")

    quality = data.get("quality_status") or {}
    level = quality.get("allowed_report_level")
    if quality.get("source_gap_visible") is not True:
        errors.append("quality_status.source_gap_visible must be true")
    if level == "sample_quality_ready":
        if quality.get("high_issue_count") not in (0, "0"):
            errors.append("sample_quality_ready requires high_issue_count == 0")
        if quality.get("no_advice_gate_passed") is not True:
            errors.append("sample_quality_ready requires no_advice_gate_passed == true")

    for pack_name in REQUIRED_PACKS:
        pack = data.get(pack_name)
        if not isinstance(pack, dict):
            errors.append(f"{pack_name} must be a mapping")
        elif "status" not in pack:
            errors.append(f"{pack_name}.status is required")

    if level == "sample_quality_ready":
        for pack_name in ["forecast_model_pack", "valuation_pack", "business_breakdown_pack"]:
            if _pack_status(data, pack_name) != "ready":
                errors.append(f"sample_quality_ready requires {pack_name}.status == ready")

    business_pack = data.get("business_breakdown_pack") or {}
    lines = business_pack.get("business_lines")
    if not isinstance(lines, list) or not lines:
        errors.append("business_breakdown_pack.business_lines must be a non-empty list")
    else:
        for idx, line in enumerate(lines):
            if not isinstance(line, dict):
                errors.append(f"business_lines[{idx}] must be a mapping")
                continue
            for field in ["revenue", "revenue_pct", "gross_margin", "gross_profit", "gross_profit_pct"]:
                metric = line.get(field)
                if not isinstance(metric, dict):
                    errors.append(f"business_lines[{idx}].{field} must be a mapping")
                else:
                    _check_metric_object(metric, f"business_lines[{idx}].{field}", errors)
            if not line.get("confidence"):
                errors.append(f"business_lines[{idx}].confidence is required")

    exposures = (data.get("segment_exposure_pack") or {}).get("exposures") or []
    if not isinstance(exposures, list):
        errors.append("segment_exposure_pack.exposures must be a list")
    else:
        for idx, exposure in enumerate(exposures):
            if not isinstance(exposure, dict):
                errors.append(f"segment_exposure_pack.exposures[{idx}] must be a mapping")
                continue
            if exposure.get("exposure_score") is not None and not (exposure.get("evidence_ids") or exposure.get("missing_reason")):
                errors.append(f"segment_exposure_pack.exposures[{idx}]: exposure_score requires evidence_ids or missing_reason")
            if not exposure.get("confidence"):
                errors.append(f"segment_exposure_pack.exposures[{idx}].confidence is required")

    forecast = data.get("forecast_model_pack") or {}
    if not FORECAST_YEARS.issubset(set(forecast.get("forecast_years") or [])):
        errors.append("forecast_model_pack.forecast_years must include 2026E, 2027E, and 2028E")
    missing_metrics = sorted(REQUIRED_FORECAST_METRICS - set(forecast.get("required_metrics") or []))
    if missing_metrics:
        errors.append(f"forecast_model_pack.required_metrics missing: {', '.join(missing_metrics)}")

    market = (data.get("valuation_pack") or {}).get("market_snapshot") or {}
    if market.get("current_price") is None and not market.get("missing_reason"):
        errors.append("valuation_pack.market_snapshot.current_price is null but missing_reason is absent")
    if level == "sample_quality_ready" and market.get("current_price") is None:
        errors.append("sample_quality_ready requires valuation_pack.market_snapshot.current_price")

    tech = data.get("technical_market_pack") or {}
    if tech.get("status") == "ready" and not tech.get("as_of_date"):
        errors.append("technical_market_pack.status=ready requires as_of_date")

    text_blob = _walk_text(data)
    for phrase in FORBIDDEN_ACTION_PHRASES:
        if phrase in text_blob:
            errors.append(f"forbidden direct trading phrase found: {phrase}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an R5_stock_research_pack YAML file.")
    parser.add_argument("path", nargs="?", type=Path, help="Pack path. Retained for backward compatibility.")
    parser.add_argument("--pack", dest="pack_path", type=Path, help="Pack path.")
    args = parser.parse_args(argv)
    path = args.pack_path or args.path
    if path is None:
        parser.error("provide a pack path or --pack")
    try:
        data = load_yaml(path)
        errors = validate_pack(data)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    outcome = derive_outcome(data, errors)
    print(f"outcome: {outcome}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
