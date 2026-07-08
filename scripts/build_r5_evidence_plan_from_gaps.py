#!/usr/bin/env python3
"""Build a plan-only R5 evidence plan from source-gap artifacts."""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml


FAMILY_ORDER = [
    "official_filings",
    "structured_financial_metrics",
    "market_snapshot",
    "peer_snapshot",
    "industry_context_clues",
    "news_event_clues",
    "investor_relations",
]


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data


def _clean_cell(value: str) -> str:
    return value.strip().strip("`").strip()


def parse_gap_report(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|") or "---" in line:
            continue
        cells = [_clean_cell(cell) for cell in line.strip().strip("|").split("|")]
        if cells and cells[0] == "gap_id":
            headers = cells
            continue
        if len(cells) < 6:
            continue
        rows.append(dict(zip(headers, cells)))
    return rows


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return cleaned or "gap"


def classify_families(row: dict[str, str]) -> set[str]:
    text = " ".join(row.values())
    families: set[str] = set()
    if "MISSING_DISCLOSURE" in text or "business" in text:
        families.update({"official_filings", "structured_financial_metrics"})
    if "TODO_MODEL_INPUT" in text or "forecast" in text:
        families.add("structured_financial_metrics")
    if "TODO_MARKET_DATA" in text or "market" in text or "technical" in text:
        families.add("market_snapshot")
    if "TODO_PEER_DATA" in text or "peer" in text:
        families.add("peer_snapshot")
    if "industry" in text:
        families.add("industry_context_clues")
    if "TODO_SOURCE_REQUIRED" in text or "sentiment" in text or "event" in text:
        families.update({"news_event_clues", "investor_relations"})
    if "LOW_CONFIDENCE_CLUE_ONLY" in text or "exposure" in text:
        families.add("official_filings")
    return families or {"official_filings"}


def _request(
    *,
    request_id: str,
    evidence_need: str,
    source_type: str,
    source_rank: str,
    as_of_date: str,
    allowed_usage: list[str],
    required_for_pack: list[str],
    missing_reason: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "evidence_need": evidence_need,
        "source_type": source_type,
        "source_rank": source_rank,
        "as_of_date": as_of_date,
        "freshness_policy": "explicit_as_of_date_or_visible_gap",
        "allowed_usage": allowed_usage,
        "required_for_pack": required_for_pack,
        "status": "planned",
        "evidence_id": None,
        "missing_reason": missing_reason,
        "next_action": next_action,
    }


def build_requests(gaps: list[dict[str, str]], as_of_date: str) -> dict[str, list[dict[str, Any]]]:
    requests: dict[str, list[dict[str, Any]]] = {family: [] for family in FAMILY_ORDER}
    seen: set[tuple[str, str]] = set()
    for row in gaps:
        gap_id = row.get("gap_id", "gap")
        missing = row.get("missing_data", "")
        next_action = row.get("next_action", "")
        for family in classify_families(row):
            key = (family, gap_id)
            if key in seen:
                continue
            seen.add(key)
            request_id = f"r5_{_slug(family)}_{_slug(gap_id)}"
            if family == "official_filings":
                request = _request(
                    request_id=request_id,
                    evidence_need=f"annual report / official disclosure for {missing}",
                    source_type="annual_report",
                    source_rank="A",
                    as_of_date=as_of_date,
                    allowed_usage=["fact_support", "business_exposure_after_review", "financial_metrics"],
                    required_for_pack=["business_breakdown_pack", "segment_exposure_pack"],
                    missing_reason="MISSING_DISCLOSURE",
                    next_action=next_action or "register official disclosure or keep visible source gap",
                )
            elif family == "structured_financial_metrics":
                request = _request(
                    request_id=request_id,
                    evidence_need=f"reviewed structured metrics for {missing}",
                    source_type="structured_financial_data",
                    source_rank="B",
                    as_of_date=as_of_date,
                    allowed_usage=["metric_candidate", "forecast_input_after_review"],
                    required_for_pack=["financial_history_pack", "forecast_model_pack"],
                    missing_reason="TODO_MODEL_INPUT",
                    next_action=next_action or "register reviewed metrics or keep TODO_MODEL_INPUT",
                )
            elif family == "market_snapshot":
                request = _request(
                    request_id=request_id,
                    evidence_need=f"dated market snapshot for {missing}",
                    source_type="market_data_snapshot",
                    source_rank="B",
                    as_of_date=as_of_date,
                    allowed_usage=["valuation_context", "technical_context"],
                    required_for_pack=["valuation_pack", "technical_market_pack"],
                    missing_reason="TODO_MARKET_DATA",
                    next_action=next_action or "register market snapshot or keep TODO_MARKET_DATA",
                )
            elif family == "peer_snapshot":
                request = _request(
                    request_id=request_id,
                    evidence_need=f"reviewed peer snapshot for {missing}",
                    source_type="peer_snapshot",
                    source_rank="B",
                    as_of_date=as_of_date,
                    allowed_usage=["peer_context", "valuation_context"],
                    required_for_pack=["peer_comparison_pack", "valuation_pack"],
                    missing_reason="TODO_PEER_DATA",
                    next_action=next_action or "register peer snapshot or keep TODO_PEER_DATA",
                )
            elif family == "industry_context_clues":
                request = _request(
                    request_id=request_id,
                    evidence_need=f"industry context source for {missing}",
                    source_type="industry_context",
                    source_rank="C",
                    as_of_date=as_of_date,
                    allowed_usage=["context_only", "TODO_generation"],
                    required_for_pack=["industry_context_pack"],
                    missing_reason="TODO_SOURCE_REQUIRED",
                    next_action=next_action or "register industry context source",
                )
            elif family == "news_event_clues":
                request = _request(
                    request_id=request_id,
                    evidence_need=f"dated news/event source for {missing}",
                    source_type="news_or_event_source",
                    source_rank="D",
                    as_of_date=as_of_date,
                    allowed_usage=["clue_only", "TODO_generation"],
                    required_for_pack=["sentiment_event_pack"],
                    missing_reason="TODO_SOURCE_REQUIRED",
                    next_action=next_action or "verify with official disclosure before material use",
                )
            else:
                request = _request(
                    request_id=request_id,
                    evidence_need=f"investor relations or company context for {missing}",
                    source_type="investor_relations",
                    source_rank="C",
                    as_of_date=as_of_date,
                    allowed_usage=["management_comment", "company_context"],
                    required_for_pack=["business_breakdown_pack", "sentiment_event_pack"],
                    missing_reason="TODO_SOURCE_REQUIRED",
                    next_action=next_action or "tag as management_comment and do not promote to fact",
                )
            requests[family].append(request)

    for family in FAMILY_ORDER:
        if not requests[family]:
            requests[family].append(
                _request(
                    request_id=f"r5_{family}_placeholder",
                    evidence_need=f"{family} placeholder from R5 gap bridge",
                    source_type=family,
                    source_rank="B" if family in {"market_snapshot", "peer_snapshot", "structured_financial_metrics"} else "C",
                    as_of_date=as_of_date,
                    allowed_usage=["context_only"] if family.endswith("clues") else ["TODO_generation"],
                    required_for_pack=["evidence_snapshot_pack"],
                    missing_reason="TODO_SOURCE_REQUIRED",
                    next_action="keep visible source gap until a concrete request is registered",
                )
            )
    return requests


def build_plan(pack: dict[str, Any], gaps: list[dict[str, str]], source_gap_report: str) -> dict[str, Any]:
    stock = pack.get("stock") if isinstance(pack.get("stock"), dict) else {}
    workflow_id = str(pack.get("workflow_id") or (pack.get("metadata") or {}).get("workflow_id") or "")
    stock_code = str(stock.get("stock_code") or pack.get("stock_code") or "")
    as_of_date = str(pack.get("as_of_date") or "TODO_SOURCE_REQUIRED")
    requests = build_requests(gaps, as_of_date)

    top_level = {
        "official_filings_needed": [item["evidence_need"] for item in requests["official_filings"]],
        "structured_financial_data_needed": [item["evidence_need"] for item in requests["structured_financial_metrics"]],
        "market_snapshot_needed": [item["evidence_need"] for item in requests["market_snapshot"]],
        "peer_snapshot_needed": [item["evidence_need"] for item in requests["peer_snapshot"]],
        "industry_data_needed": [item["evidence_need"] for item in requests["industry_context_clues"]],
        "analyst_consensus_needed": [],
        "news_and_event_sources_needed": [item["evidence_need"] for item in requests["news_event_clues"]],
    }

    return {
        "schema_version": "r5_evidence_plan_bridge_v0.1",
        "artifact_type": "R5_stock_evidence_snapshot_plan",
        "stock_code": stock_code,
        "workflow_id": workflow_id,
        **top_level,
        "priority": "high",
        "blocking_for_r5": True,
        "metadata": {
            "workflow_id": workflow_id,
            "stock_code": stock_code,
            "company_name": stock.get("company_name"),
            "as_of_date": as_of_date,
            "source_gap_report": source_gap_report,
        },
        "implementation_boundary": {
            "no_live_api": True,
            "no_downloader_added": True,
            "plan_only": True,
        },
        "source_gap_policy": {
            "missing_tokens": [
                "MISSING_DISCLOSURE",
                "TODO_SOURCE_REQUIRED",
                "TODO_MODEL_INPUT",
                "TODO_MARKET_DATA",
                "TODO_PEER_DATA",
            ],
            "preserve_missing_data": True,
        },
        "evidence_requests": requests,
        "handoff_to_stock_deep_dive": {
            "evidence_manifest_path": "data/manifests/evidence_manifest.csv",
            "claim_candidates_path": "data/manifests/claims_draft.csv",
            "metric_candidates_path": "data/manifests/metrics_draft.csv",
            "source_gap_register_path": source_gap_report,
            "evidence_counts": {
                "official_filings": "TODO",
                "structured_financial_metrics": "TODO",
                "market_snapshot": "TODO",
                "peer_snapshot": "TODO",
                "context_clues": "TODO",
            },
            "official_filing_requests": [item["request_id"] for item in requests["official_filings"]],
            "structured_metric_requests": [item["request_id"] for item in requests["structured_financial_metrics"]],
            "market_snapshot_requests": [item["request_id"] for item in requests["market_snapshot"]],
            "peer_snapshot_requests": [item["request_id"] for item in requests["peer_snapshot"]],
            "context_clue_requests": [
                item["request_id"]
                for family in ("industry_context_clues", "news_event_clues", "investor_relations")
                for item in requests[family]
            ],
            "missing_inputs": [
                "MISSING_DISCLOSURE",
                "TODO_SOURCE_REQUIRED",
                "TODO_MODEL_INPUT",
                "TODO_MARKET_DATA",
                "TODO_PEER_DATA",
            ],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build R5 evidence plan from source gaps.")
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--source-gap-report", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    pack = load_yaml(args.pack)
    gaps = parse_gap_report(args.source_gap_report)
    plan = build_plan(pack, gaps, str(args.source_gap_report).replace("\\", "/"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(yaml.safe_dump(plan, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"wrote {args.out}")
    print(f"gap_rows={len(gaps)} request_families={len(FAMILY_ORDER)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
