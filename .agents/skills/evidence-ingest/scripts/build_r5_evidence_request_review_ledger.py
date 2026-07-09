#!/usr/bin/env python3
"""Build an initial R5 evidence request review ledger from a request queue."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def _reason(row: dict[str, Any]) -> str:
    return str(row.get("missing_reason") or row.get("status") or "TODO_SOURCE_REQUIRED")


def build_ledger(queue: dict[str, Any], source_queue_path: str) -> dict[str, Any]:
    requests = queue.get("requests") or []
    if not isinstance(requests, list):
        raise ValueError("queue.requests must be a list")
    items: list[dict[str, Any]] = []
    for row in requests:
        if not isinstance(row, dict):
            continue
        evidence_id = row.get("evidence_id")
        decision = "pending" if evidence_id in (None, "") else "accepted"
        items.append(
            {
                "request_id": row.get("request_id"),
                "source_gap_id": row.get("source_gap_id"),
                "pack_section": row.get("pack_section"),
                "review_decision": decision,
                "evidence_id": evidence_id,
                "source_rank": row.get("source_rank"),
                "reason": _reason(row),
                "next_action": row.get("next_action") or "manual source collection required before promotion",
            }
        )
    pending_count = sum(1 for item in items if item["review_decision"] == "pending")
    accepted_count = sum(1 for item in items if item["review_decision"] == "accepted")
    return {
        "schema_version": "r5_evidence_request_review_ledger_v0.1",
        "artifact_type": "R5_evidence_request_review_ledger",
        "workflow_id": queue.get("workflow_id"),
        "stock_code": queue.get("stock_code"),
        "source_queue_path": source_queue_path,
        "review_status": "accepted" if items and pending_count == 0 else "pending",
        "no_live_api": True,
        "items": items,
        "summary": {
            "request_count": len(items),
            "pending_count": pending_count,
            "accepted_count": accepted_count,
            "accepted_null_evidence_count": sum(1 for item in items if item["review_decision"] == "accepted" and not item.get("evidence_id")),
        },
        "promotion_rules": [
            "accepted requires evidence_id and source_rank",
            "pending cannot unblock source-gapped pilot",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an R5 evidence request review ledger.")
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    ledger = build_ledger(load_yaml(args.queue), str(args.queue).replace("\\", "/"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(yaml.safe_dump(ledger, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(
        "ledger_status={status} request_count={requests} pending_count={pending} accepted_count={accepted}".format(
            status=ledger["review_status"],
            requests=ledger["summary"]["request_count"],
            pending=ledger["summary"]["pending_count"],
            accepted=ledger["summary"]["accepted_count"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
