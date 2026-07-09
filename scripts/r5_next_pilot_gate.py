#!/usr/bin/env python3
"""Evaluate the R5 next pilot gate without entering sample-quality or P2."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def _status_ready(data: dict[str, Any] | None) -> bool:
    return bool(data) and data.get("review_status") in {"reviewed", "explicitly_degraded_but_reviewed"}


def _source_gaps_visible(readiness: dict[str, Any]) -> bool:
    summary = readiness.get("input_summary")
    if isinstance(summary, dict) and summary.get("source_gap_report_exists") is False:
        return False
    return True


def _no_advice_passed(readiness: dict[str, Any]) -> bool:
    summary = readiness.get("input_summary")
    if isinstance(summary, dict) and summary.get("no_advice_passed") is False:
        return False
    return True


def _ledger_ok(ledger: dict[str, Any] | None) -> bool:
    if not ledger:
        return False
    for row in ledger.get("items") or []:
        if not isinstance(row, dict):
            return False
        if row.get("review_decision") == "accepted" and not row.get("evidence_id"):
            return False
    return True


def _registry_summary(registries: dict[str, Any] | None) -> dict[str, Any]:
    registries = registries or {}
    market_peer = registries.get("market_peer_input_registry")
    forecast = registries.get("forecast_assumption_registry")
    ledger = registries.get("evidence_request_review_ledger")
    return {
        "market_peer_registry_ready": _status_ready(market_peer),
        "forecast_assumption_registry_ready": _status_ready(forecast),
        "evidence_request_review_ledger_ok": _ledger_ok(ledger),
        "market_peer_review_status": market_peer.get("review_status") if isinstance(market_peer, dict) else "missing",
        "forecast_review_status": forecast.get("review_status") if isinstance(forecast, dict) else "missing",
        "ledger_review_status": ledger.get("review_status") if isinstance(ledger, dict) else "missing",
        "ledger_pending_count": ((ledger.get("summary") or {}).get("pending_count") if isinstance(ledger, dict) else None),
    }


def _registry_blockers(summary: dict[str, Any]) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    if not summary["market_peer_registry_ready"]:
        blockers.append(
            {
                "id": "market_peer_registry_pending",
                "severity": "todo",
                "reason": "market/peer input registry is not reviewed or reviewed-degraded.",
                "detail": str(summary["market_peer_review_status"]),
            }
        )
    if not summary["forecast_assumption_registry_ready"]:
        blockers.append(
            {
                "id": "forecast_assumption_registry_pending",
                "severity": "todo",
                "reason": "forecast assumption registry is not reviewed or reviewed-degraded.",
                "detail": str(summary["forecast_review_status"]),
            }
        )
    if not summary["evidence_request_review_ledger_ok"]:
        blockers.append(
            {
                "id": "evidence_request_review_ledger_not_ready",
                "severity": "todo",
                "reason": "evidence request review ledger is missing or contains invalid accepted rows.",
                "detail": str(summary["ledger_review_status"]),
            }
        )
    return blockers


def evaluate_gate(
    readiness: dict[str, Any],
    rules: dict[str, Any],
    registries: dict[str, Any] | None = None,
) -> dict[str, Any]:
    decision = str(readiness.get("decision", "R5_BLOCKED"))
    registry_summary = _registry_summary(registries)
    registry_blockers = _registry_blockers(registry_summary) if registries is not None else []
    readiness_blockers = list(readiness.get("blockers") or [])
    legacy_allowed = decision == "R5_READY_FOR_SOURCE_GAPPED_REAL_SAMPLE_PILOT"
    source_gapped_allowed = legacy_allowed if registries is None else (
        not readiness_blockers
        and registry_summary["market_peer_registry_ready"]
        and registry_summary["forecast_assumption_registry_ready"]
        and registry_summary["evidence_request_review_ledger_ok"]
        and _source_gaps_visible(readiness)
        and _no_advice_passed(readiness)
    )
    candidate_tasks = list(rules.get("candidate_tasks") or [])[: int(rules.get("max_next_candidate_tasks", 3))]
    return {
        "status": "closed_with_todos" if decision == "R5_CONTRACTS_EXECUTABLE_WITH_TODOS_ONLY" else "closed",
        "current_r5_state": decision,
        "source_gapped_real_sample_pilot_allowed": source_gapped_allowed,
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
        "blockers": readiness_blockers,
        "non_blockers": readiness.get("non_blockers", []),
        "registry_blockers": registry_blockers,
        "registry_summary": registry_summary,
        "next_candidate_tasks": candidate_tasks,
        "boundary": {
            "no_live_api": True,
            "do_not_execute_next_tasks_in_this_patch": True,
        },
    }


def _load_registries(repo_root: Path, rules: dict[str, Any]) -> dict[str, Any]:
    paths = rules.get("default_paths") or {}
    loaded: dict[str, Any] = {}
    for key in ["market_peer_input_registry", "forecast_assumption_registry", "evidence_request_review_ledger"]:
        path_text = paths.get(key)
        if not path_text:
            continue
        path = repo_root / path_text
        loaded[key] = load_yaml(path) if path.exists() else {"review_status": "missing"}
    return loaded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate R5 next pilot gate from readiness and reviewed-input registries.")
    parser.add_argument("--readiness", required=True, type=Path)
    parser.add_argument("--rules", default=Path("config/r5_next_pilot_gate_rules.yaml"), type=Path)
    parser.add_argument("--json", required=True, type=Path)
    args = parser.parse_args(argv)

    rules = load_yaml(args.rules)
    result = evaluate_gate(load_json(args.readiness), rules, _load_registries(Path(".").resolve(), rules))
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "r5_next_pilot_gate state={state} source_gapped_allowed={source} sample_quality_allowed={sample} p2_allowed={p2}".format(
            state=result["current_r5_state"],
            source=str(result["source_gapped_real_sample_pilot_allowed"]).lower(),
            sample=str(result["sample_quality_report_allowed"]).lower(),
            p2=str(result["p2_allowed"]).lower(),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
