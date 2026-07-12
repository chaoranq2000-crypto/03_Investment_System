#!/usr/bin/env python3
"""Validate an R5_stock_research_pack YAML artifact."""
from __future__ import annotations

import argparse
import json
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
    "metadata",
    "pack_status",
    "quality_status",
    "source_gap_policy",
    "source_gap_register",
    *CORE_PACKS,
]

REQUIRED_PACKS = [*CORE_PACKS, "report_composition_pack"]
PACK_STATUS = {"sample_quality_candidate", "research_draft", "blocked", "needs_fix"}
MISSING_TOKENS = {
    "MISSING_DISCLOSURE",
    "TODO_SOURCE_REQUIRED",
    "TODO_MODEL_INPUT",
    "TODO_MARKET_DATA",
    "TODO_PEER_DATA",
    "LOW_CONFIDENCE_CLUE_ONLY",
}
FORECAST_YEARS = {"2026E", "2027E", "2028E"}
REQUIRED_FORECAST_METRICS = {"revenue", "gross_margin", "net_profit_attributable", "eps"}
TRACE_KEYS = {
    "source_evidence_id",
    "evidence_id",
    "evidence_ids",
    "metric_id",
    "claim_id",
    "assumption_id",
    "scenario_id",
    "source_path",
}
MISSING_KEYS = {"missing_reason", "missing_items", "source_gap", "source_gap_id"}
FORBIDDEN_ACTION_PHRASES = [
    "买入评级",
    "卖出评级",
    "持有评级",
    "建议买入",
    "建议卖出",
    "建议建仓",
    "仓位建议",
    "目标买点",
]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError("root YAML object must be a mapping")
    return data


def _issue(
    issue_id: str,
    severity: str,
    path: str,
    description: str,
    next_action: str,
) -> dict[str, str]:
    return {
        "issue_id": issue_id,
        "severity": severity,
        "path": path,
        "description": description,
        "next_action": next_action,
    }


def _has_any_key(obj: dict[str, Any], keys: set[str]) -> bool:
    return any(obj.get(key) not in (None, "", []) for key in keys)


def _check_metric_object(obj: dict[str, Any], path: str, issues: list[dict[str, str]]) -> None:
    if obj.get("value") is None:
        if not _has_any_key(obj, MISSING_KEYS):
            issues.append(
                _issue(
                    "R5P-METRIC-001",
                    "high",
                    path,
                    f"{path}: value is null but missing_reason/missing_items/source_gap is absent",
                    "Add an explicit missing reason or source gap row.",
                )
            )
        return
    if not _has_any_key(obj, TRACE_KEYS):
        issues.append(
            _issue(
                "R5P-METRIC-002",
                "high",
                path,
                f"{path}: non-null value requires evidence_id or metric_id",
                "Attach evidence_id, metric_id, claim_id, assumption_id, or source path.",
            )
        )


def _walk_text(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(_walk_text(v) for v in value.values())
    if isinstance(value, list):
        return "\n".join(_walk_text(v) for v in value)
    return value if isinstance(value, str) else ""


def _pack_status(data: dict[str, Any], pack_name: str) -> str | None:
    pack = data.get(pack_name)
    return pack.get("status") if isinstance(pack, dict) else None


def _source_gap_text(data: dict[str, Any]) -> str:
    return _walk_text(data.get("source_gap_register") or [])


def derive_decision(data: dict[str, Any], issues: list[dict[str, str]]) -> str:
    if any(issue["severity"] == "high" for issue in issues):
        if any(issue["path"] in {"company_identity_pack", "evidence_snapshot_pack"} for issue in issues):
            return "blocked"
        if any("no-advice" in issue["description"].lower() for issue in issues):
            return "blocked"
        return "needs_fix"
    quality = data.get("quality_status") if isinstance(data.get("quality_status"), dict) else {}
    if quality.get("high_issue_count") not in (None, 0, "0"):
        return "needs_fix"
    if issues:
        return "accepted_with_todos"
    if any(_pack_status(data, pack_name) in {"TODO", "partial", None} for pack_name in REQUIRED_PACKS):
        return "accepted_with_todos"
    if quality.get("medium_issue_count") not in (None, 0, "0"):
        return "accepted_with_todos"
    return "accepted"


def validate_pack_issues(data: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if data.get("artifact_type") != "R5_stock_research_pack":
        issues.append(
            _issue(
                "R5P-ROOT-001",
                "high",
                "artifact_type",
                "artifact_type must be R5_stock_research_pack",
                "Set artifact_type to R5_stock_research_pack.",
            )
        )

    for key in REQUIRED_TOP_LEVEL:
        if key not in data:
            severity = "high" if key in {"company_identity_pack", "evidence_snapshot_pack"} else "medium"
            issues.append(
                _issue(
                    "R5P-ROOT-002",
                    severity,
                    key,
                    f"missing top-level key: {key}",
                    "Add the required top-level object or an explicit blocked/TODO object.",
                )
            )

    pack_status = data.get("pack_status")
    if pack_status not in PACK_STATUS:
        issues.append(
            _issue(
                "R5P-STATUS-001",
                "high",
                "pack_status",
                "pack_status must be one of sample_quality_candidate, research_draft, blocked, needs_fix",
                "Set pack_status to the R5 validator enum.",
            )
        )

    tokens = set((data.get("source_gap_policy") or {}).get("missing_value_tokens") or [])
    for token in sorted(MISSING_TOKENS - tokens):
        issues.append(
            _issue(
                "R5P-GAP-001",
                "medium",
                "source_gap_policy.missing_value_tokens",
                f"source_gap_policy.missing_value_tokens missing: {token}",
                "Add the missing token to the visible source-gap policy.",
            )
        )

    gap_text = _source_gap_text(data)
    text_blob = _walk_text(data)
    active_text_blob = _walk_text({key: value for key, value in data.items() if key != "source_gap_policy"})
    for token in sorted(MISSING_TOKENS):
        if token in active_text_blob and token not in gap_text:
            issues.append(
                _issue(
                    "R5P-GAP-002",
                    "high",
                    "source_gap_register",
                    f"TODO/MISSING token is not visible in source_gap_register: {token}",
                    "Add a source_gap_register row for every material TODO/MISSING token.",
                )
            )

    quality = data.get("quality_status") if isinstance(data.get("quality_status"), dict) else {}
    level = quality.get("allowed_report_level")
    if quality.get("source_gap_visible") is not True:
        issues.append(
            _issue(
                "R5P-GATE-001",
                "high",
                "quality_status.source_gap_visible",
                "quality_status.source_gap_visible must be true",
                "Keep source gaps visible before any report composition.",
            )
        )
    is_sample_candidate = pack_status == "sample_quality_candidate" or level in {"sample_quality_ready", "R5_sample_quality_ready"}
    if is_sample_candidate:
        if quality.get("high_issue_count") not in (0, "0"):
            issues.append(
                _issue(
                    "R5P-GATE-002",
                    "high",
                    "quality_status.high_issue_count",
                    "sample_quality_ready requires high_issue_count == 0",
                    "Resolve high severity issues or downgrade the allowed report level.",
                )
            )
        if quality.get("no_advice_gate_passed") is not True:
            issues.append(
                _issue(
                    "R5P-GATE-003",
                    "high",
                    "quality_status.no_advice_gate_passed",
                    "sample_quality_ready requires no_advice_gate_passed == true",
                    "Run no-advice review or downgrade the allowed report level.",
                )
            )

    for pack_name in REQUIRED_PACKS:
        pack = data.get(pack_name)
        if not isinstance(pack, dict):
            issues.append(
                _issue(
                    "R5P-PACK-001",
                    "high" if pack_name in {"company_identity_pack", "evidence_snapshot_pack"} else "medium",
                    pack_name,
                    f"{pack_name} must be a mapping",
                    "Add a mapping with status and visible TODO/MISSING fields.",
                )
            )
        elif "status" not in pack:
            issues.append(
                _issue(
                    "R5P-PACK-002",
                    "medium",
                    f"{pack_name}.status",
                    f"{pack_name}.status is required",
                    "Set pack status to TODO, partial, ready, or blocked.",
                )
            )

    if is_sample_candidate:
        for pack_name in ["forecast_model_pack", "valuation_pack", "business_breakdown_pack"]:
            if _pack_status(data, pack_name) != "ready":
                issues.append(
                    _issue(
                        "R5P-GATE-004",
                        "high",
                        f"{pack_name}.status",
                        f"sample_quality_candidate requires {pack_name}.status == ready",
                        "Downgrade the pack or complete the reviewed subpack.",
                    )
                )

    if "business_breakdown_pack" not in data and pack_status not in {"research_draft", "needs_fix", "blocked"}:
        issues.append(
            _issue(
                "R5P-BIZ-000",
                "high",
                "business_breakdown_pack",
                "missing business_breakdown_pack allows only research_draft or lower",
                "Downgrade pack_status or add a visible business_breakdown_pack.",
            )
        )

    business_pack = data.get("business_breakdown_pack") or {}
    lines = business_pack.get("business_lines")
    if not isinstance(lines, list) or not lines:
        issues.append(
            _issue(
                "R5P-BIZ-001",
                "medium",
                "business_breakdown_pack.business_lines",
                "business_breakdown_pack.business_lines must be a non-empty list",
                "Add business-line rows or explicit source gaps.",
            )
        )
    else:
        for idx, line in enumerate(lines):
            if not isinstance(line, dict):
                issues.append(
                    _issue(
                        "R5P-BIZ-002",
                        "high",
                        f"business_lines[{idx}]",
                        f"business_lines[{idx}] must be a mapping",
                        "Use a mapping for each business line.",
                    )
                )
                continue
            for field in ["revenue", "revenue_pct", "gross_margin", "gross_profit", "gross_profit_pct"]:
                metric = line.get(field)
                path = f"business_lines[{idx}].{field}"
                if not isinstance(metric, dict):
                    issues.append(
                        _issue(
                            "R5P-BIZ-003",
                            "high",
                            path,
                            f"{path} must be a mapping",
                            "Represent the metric as value/unit/source or missing_reason.",
                        )
                    )
                else:
                    _check_metric_object(metric, path, issues)
            if not line.get("confidence"):
                issues.append(
                    _issue(
                        "R5P-BIZ-004",
                        "medium",
                        f"business_lines[{idx}].confidence",
                        f"business_lines[{idx}].confidence is required",
                        "Set confidence to high, medium, low, not_assessed, or blocked.",
                    )
                )

    exposures = (data.get("segment_exposure_pack") or {}).get("exposures") or []
    if not isinstance(exposures, list):
        issues.append(
            _issue(
                "R5P-EXP-001",
                "medium",
                "segment_exposure_pack.exposures",
                "segment_exposure_pack.exposures must be a list",
                "Use a list, even when there are no accepted exposures.",
            )
        )
    else:
        for idx, exposure in enumerate(exposures):
            if not isinstance(exposure, dict):
                issues.append(
                    _issue(
                        "R5P-EXP-002",
                        "high",
                        f"segment_exposure_pack.exposures[{idx}]",
                        f"segment_exposure_pack.exposures[{idx}] must be a mapping",
                        "Use a mapping for each exposure row.",
                    )
                )
                continue
            if exposure.get("exposure_score") is not None and not (
                exposure.get("evidence_ids") or exposure.get("source_evidence_id") or exposure.get("missing_reason")
            ):
                issues.append(
                    _issue(
                        "R5P-EXP-003",
                        "high",
                        f"segment_exposure_pack.exposures[{idx}].exposure_score",
                        "exposure_score requires evidence_ids or missing_reason",
                        "Attach evidence or keep the exposure as a visible source gap.",
                    )
                )
            if not exposure.get("confidence"):
                issues.append(
                    _issue(
                        "R5P-EXP-004",
                        "medium",
                        f"segment_exposure_pack.exposures[{idx}].confidence",
                        "segment exposure confidence is required",
                        "Set confidence to high, medium, low, not_assessed, or blocked.",
                    )
                )

    forecast = data.get("forecast_model_pack") or {}
    if not FORECAST_YEARS.issubset(set(forecast.get("forecast_years") or [])):
        issues.append(
            _issue(
                "R5P-FCST-001",
                "high",
                "forecast_model_pack.forecast_years",
                "forecast_model_pack.forecast_years must include 2026E, 2027E, and 2028E",
                "Add the three required forecast years, using TODO values if needed.",
            )
        )
    missing_metrics = sorted(REQUIRED_FORECAST_METRICS - set(forecast.get("required_metrics") or []))
    if missing_metrics:
        issues.append(
            _issue(
                "R5P-FCST-002",
                "medium",
                "forecast_model_pack.required_metrics",
                f"forecast_model_pack.required_metrics missing: {', '.join(missing_metrics)}",
                "Include the required metric names even when values remain TODO.",
            )
        )

    market = (data.get("valuation_pack") or {}).get("market_snapshot") or {}
    if market.get("current_price") is None and not market.get("missing_reason"):
        issues.append(
            _issue(
                "R5P-VAL-001",
                "high",
                "valuation_pack.market_snapshot.current_price",
                "valuation_pack.market_snapshot.current_price is null but missing_reason is absent",
                "Add TODO_MARKET_DATA or provide reviewed market snapshot data.",
            )
        )
    if is_sample_candidate and market.get("current_price") is None:
        issues.append(
            _issue(
                "R5P-VAL-002",
                "high",
                "valuation_pack.market_snapshot.current_price",
                "sample_quality_candidate requires valuation_pack.market_snapshot.current_price",
                "Downgrade the pack until a reviewed market snapshot is available.",
            )
        )

    tech = data.get("technical_market_pack") or {}
    if (tech.get("status") == "ready" or tech.get("trend_judgement")) and not tech.get("as_of_date"):
        issues.append(
            _issue(
                "R5P-MKT-001",
                "high",
                "technical_market_pack.as_of_date",
                "technical_market_pack requires as_of_date before market-state language",
                "Add as_of_date or remove/downgrade the market-state judgement.",
            )
        )

    sentiment = data.get("sentiment_event_pack") or {}
    has_strong_sentiment = bool(sentiment.get("strong_judgement") or sentiment.get("event_judgement"))
    if (sentiment.get("status") == "ready" or has_strong_sentiment) and not sentiment.get("as_of_date"):
        issues.append(
            _issue(
                "R5P-SENT-001",
                "high",
                "sentiment_event_pack.as_of_date",
                "sentiment_event_pack requires as_of_date before strong sentiment/event judgement",
                "Add as_of_date or keep the section as TODO_SOURCE_REQUIRED.",
            )
        )

    for phrase in FORBIDDEN_ACTION_PHRASES:
        if phrase in text_blob:
            issues.append(
                _issue(
                    "R5P-NOADV-001",
                    "high",
                    "no_advice_scan",
                    f"forbidden direct trading phrase found: {phrase}",
                    "Remove direct trading language and rerun quality review.",
                )
            )
    return issues


def validate_pack(data: dict[str, Any]) -> list[str]:
    """Backward-compatible string error API used by earlier R5 tests."""
    return [issue["description"] for issue in validate_pack_issues(data)]


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
        issues = validate_pack_issues(data)
    except Exception as exc:  # noqa: BLE001
        payload = {
            "decision": "blocked",
            "issues": [
                _issue("R5P-LOAD-001", "high", str(path), f"ERROR: {exc}", "Fix YAML parse/load failure.")
            ],
            "legacy_summary": "outcome: blocked",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2
    decision = derive_decision(data, issues)
    payload = {
        "decision": decision,
        "issues": issues,
        "legacy_summary": f"outcome: {decision}",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if decision in {"accepted", "accepted_with_todos"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
