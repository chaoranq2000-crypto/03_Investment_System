#!/usr/bin/env python3
"""Evaluate R5 readiness without entering P2 or sample-quality reporting."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml


DEFAULT_RULES = Path("config/r5_readiness_gate_rules.yaml")
FORBIDDEN = re.compile(r"买入|卖出|持有|仓位|目标价|保证收益|buy rating|sell rating|hold rating|position sizing", re.IGNORECASE)


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _exists(repo_root: Path, rel_path: str) -> bool:
    return (repo_root / rel_path).exists()


def _text(repo_root: Path, rel_path: str) -> str:
    path = repo_root / rel_path
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def collect_inputs(repo_root: Path, rules: dict[str, Any]) -> dict[str, Any]:
    paths = rules["default_paths"]
    inputs: dict[str, Any] = {"paths": paths}

    smoke_path = repo_root / paths["smoke_result"]
    inputs["smoke_result"] = load_json(smoke_path) if smoke_path.exists() else {"status": "missing", "results": []}

    inventory_path = repo_root / paths["inventory_status"]
    inputs["inventory_status"] = load_yaml(inventory_path) if inventory_path.exists() else {"accepted": False, "inventory_status": "missing"}

    format_path = repo_root / paths["format_guard"]
    inputs["format_guard"] = load_json(format_path) if format_path.exists() else {"status": "missing"}

    pack_path = repo_root / paths["source_gapped_pack"]
    inputs["source_gapped_pack"] = load_yaml(pack_path) if pack_path.exists() else {}

    evidence_path = repo_root / paths["evidence_plan"]
    inputs["evidence_plan"] = load_yaml(evidence_path) if evidence_path.exists() else {}

    handoff_path = repo_root / paths["valuation_handoff_example"]
    inputs["valuation_handoff_example"] = load_yaml(handoff_path) if handoff_path.exists() else {}

    combined_text = "\n".join(
        _text(repo_root, paths[key])
        for key in ["source_gapped_pack", "source_gap_report", "evidence_plan", "valuation_handoff_example"]
        if _exists(repo_root, paths[key])
    )
    inputs["no_advice_passed"] = FORBIDDEN.search(combined_text) is None
    inputs["source_gap_report_exists"] = _exists(repo_root, paths["source_gap_report"])
    return inputs


def _pack_has_visible_gaps(pack: dict[str, Any]) -> bool:
    gaps = pack.get("source_gap_register")
    return isinstance(gaps, list) and len(gaps) > 0 and (pack.get("quality_status") or {}).get("source_gap_visible") is True


def decide_readiness(inputs: dict[str, Any]) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    non_blockers: list[dict[str, str]] = []

    smoke = inputs["smoke_result"]
    if smoke.get("status") != "pass":
        failed = [item.get("name", "unknown") for item in smoke.get("results", []) if item.get("exit_code") != 0]
        blockers.append(
            {
                "id": "patch_13_20_strict_smoke",
                "severity": "high",
                "reason": "Patch 13-20 strict smoke is not all green.",
                "detail": ", ".join(failed) or str(smoke.get("status")),
            }
        )

    inventory = inputs["inventory_status"]
    if inventory.get("accepted") is not True:
        blockers.append(
            {
                "id": "patch_inventory",
                "severity": "high",
                "reason": "Patch 1-12 inventory is not validated_complete.",
                "detail": str(inventory.get("inventory_status")),
            }
        )

    if not inputs.get("no_advice_passed"):
        blockers.append(
            {
                "id": "no_advice_gate",
                "severity": "high",
                "reason": "No-advice scan found forbidden trading-action language.",
                "detail": "forbidden phrase matched",
            }
        )

    pack = inputs["source_gapped_pack"]
    if not pack:
        blockers.append({"id": "source_gapped_pack", "severity": "high", "reason": "R5 source-gapped pack is missing.", "detail": ""})
    elif not _pack_has_visible_gaps(pack):
        blockers.append({"id": "source_gap_visibility", "severity": "high", "reason": "Source gaps are not visibly registered.", "detail": ""})

    evidence_plan = inputs["evidence_plan"]
    if evidence_plan.get("artifact_type") != "R5_stock_evidence_snapshot_plan":
        blockers.append({"id": "evidence_plan", "severity": "high", "reason": "R5 evidence plan is missing or invalid.", "detail": ""})

    handoff = inputs["valuation_handoff_example"]
    if handoff.get("artifact_type") != "R5_valuation_handoff":
        blockers.append({"id": "valuation_handoff_interlock", "severity": "high", "reason": "R5 valuation handoff interlock example is missing or invalid.", "detail": ""})

    if pack:
        forecast_status = (pack.get("forecast_model_pack") or {}).get("status")
        valuation_status = (pack.get("valuation_pack") or {}).get("status")
        if forecast_status != "ready":
            non_blockers.append({"id": "forecast_todo", "severity": "todo", "reason": "Forecast remains TODO_MODEL_INPUT for sample-quality.", "detail": str(forecast_status)})
        if valuation_status != "ready":
            non_blockers.append({"id": "valuation_todo", "severity": "todo", "reason": "Valuation remains TODO_MARKET_DATA / TODO_PEER_DATA for sample-quality.", "detail": str(valuation_status)})

    if blockers:
        decision = "R5_BLOCKED"
        can_enter = False
    elif non_blockers:
        decision = "R5_CONTRACTS_EXECUTABLE_WITH_TODOS_ONLY"
        can_enter = False
    else:
        decision = "R5_READY_FOR_SOURCE_GAPPED_REAL_SAMPLE_PILOT"
        can_enter = True

    return {
        "decision": decision,
        "can_enter_source_gapped_real_sample_pilot": can_enter,
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
        "blockers": blockers,
        "non_blockers": non_blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate R5 readiness gates.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    rules = load_yaml(args.rules)
    inputs = collect_inputs(repo_root, rules)
    result = decide_readiness(inputs)
    result["input_summary"] = {
        "smoke_status": inputs["smoke_result"].get("status"),
        "inventory_status": inputs["inventory_status"].get("inventory_status"),
        "format_guard_status": inputs["format_guard"].get("status"),
        "source_gap_report_exists": inputs.get("source_gap_report_exists"),
        "no_advice_passed": inputs.get("no_advice_passed"),
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "r5_readiness_decision={decision} can_enter_source_gapped_real_sample_pilot={can_enter} "
        "sample_quality_report_allowed={sample} p2_allowed={p2} blockers={blockers}".format(
            decision=result["decision"],
            can_enter=str(result["can_enter_source_gapped_real_sample_pilot"]).lower(),
            sample=str(result["sample_quality_report_allowed"]).lower(),
            p2=str(result["p2_allowed"]).lower(),
            blockers=len(result["blockers"]),
        )
    )
    return 0 if result["decision"] != "R5_BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
