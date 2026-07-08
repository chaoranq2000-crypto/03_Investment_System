#!/usr/bin/env python3
"""Build a local R5 evidence request queue from a source-gap evidence plan."""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml


OWNER_BY_SOURCE_TYPE = {
    "annual_report": "evidence-ingest",
    "announcement": "evidence-ingest",
    "structured_financial_data": "evidence-ingest",
    "market_data_snapshot": "evidence-ingest",
    "peer_snapshot": "evidence-ingest",
    "industry_context_clues": "evidence-ingest",
    "news_or_event_source": "evidence-ingest",
    "investor_relations": "evidence-ingest",
}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data


def _source_gap_id(request: dict[str, Any]) -> str:
    request_id = str(request.get("request_id", ""))
    match = re.search(r"(r5_\d{6}_gap_[a-z_]+?_\d{3})", request_id, flags=re.IGNORECASE)
    if match:
        return match.group(1).upper()
    need = str(request.get("evidence_need", "")).upper()
    if "MISSING_DISCLOSURE" in need:
        return "R5_002837_GAP_BUSINESS_001"
    if "TODO_MODEL_INPUT" in need:
        return "R5_002837_GAP_FORECAST_001"
    if "TODO_PEER_DATA" in need:
        return "R5_002837_GAP_VALUATION_001"
    if "TODO_MARKET_DATA" in need:
        return "R5_002837_GAP_MARKET_001"
    if "TODO_SOURCE_REQUIRED" in need:
        return "R5_002837_GAP_SENTIMENT_001"
    if "LOW_CONFIDENCE_CLUE_ONLY" in need:
        return "R5_002837_GAP_EXPOSURE_001"
    return "R5_002837_GAP_UNMAPPED_001"


def _pack_section(request: dict[str, Any]) -> str:
    required = request.get("required_for_pack")
    if isinstance(required, list) and required:
        return str(required[0])
    return "evidence_snapshot_pack"


def flatten_requests(plan: dict[str, Any]) -> list[dict[str, Any]]:
    nested = plan.get("evidence_requests")
    if not isinstance(nested, dict):
        raise ValueError("plan.evidence_requests must be a mapping")

    workflow_id = str(plan.get("workflow_id", "TODO_WORKFLOW_ID"))
    stock_code = str(plan.get("stock_code", "TODO_STOCK_CODE"))
    rows: list[dict[str, Any]] = []
    for family in sorted(nested):
        requests = nested[family]
        if not isinstance(requests, list):
            continue
        for request in requests:
            if not isinstance(request, dict):
                continue
            source_type = str(request.get("source_type", family))
            rows.append(
                {
                    "request_id": str(request.get("request_id")),
                    "workflow_id": workflow_id,
                    "stock_code": stock_code,
                    "source_gap_id": _source_gap_id(request),
                    "pack_section": _pack_section(request),
                    "evidence_need": request.get("evidence_need"),
                    "source_type": source_type,
                    "source_rank": request.get("source_rank", "C"),
                    "freshness_policy": request.get("freshness_policy", "explicit_as_of_date_or_visible_gap"),
                    "required_for_pack": request.get("required_for_pack", []),
                    "allowed_usage": request.get("allowed_usage", []),
                    "owner_skill": OWNER_BY_SOURCE_TYPE.get(source_type, "evidence-ingest"),
                    "status": "planned",
                    "evidence_id": None,
                    "missing_reason": request.get("missing_reason", "TODO_SOURCE_REQUIRED"),
                    "next_action": request.get("next_action", "register reviewed evidence or keep source gap visible"),
                    "no_live_api": True,
                }
            )
    return sorted(rows, key=lambda item: item["request_id"])


def build_queue(plan: dict[str, Any], source_plan_path: str) -> dict[str, Any]:
    requests = flatten_requests(plan)
    return {
        "schema_version": "r5_evidence_request_queue_v0.1",
        "artifact_type": "R5_evidence_request_queue",
        "workflow_id": plan.get("workflow_id"),
        "stock_code": plan.get("stock_code"),
        "source_plan_path": source_plan_path,
        "no_live_api": True,
        "status": "planned",
        "requests": requests,
        "summary": {
            "request_count": len(requests),
            "source_gap_count": len({item["source_gap_id"] for item in requests}),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an R5 evidence request queue without live API calls.")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    plan = load_yaml(args.plan)
    queue = build_queue(plan, str(args.plan))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(yaml.safe_dump(queue, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"r5_evidence_request_queue status=planned requests={len(queue['requests'])} no_live_api=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
