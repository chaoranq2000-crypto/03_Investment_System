#!/usr/bin/env python3
"""Evaluate whether an R5 pack can be promoted beyond source-gapped draft."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

FORBIDDEN = re.compile(
    r"买入|卖出|持有|仓位|目标价|保证收益|buy\s+rating|sell\s+rating|hold\s+rating|position\s+sizing",
    re.IGNORECASE,
)


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_text(item) for item in value)
    return value if isinstance(value, str) else ""


def _issue(issue_id: str, severity: str, reason: str, detail: str = "") -> dict[str, str]:
    return {"id": issue_id, "severity": severity, "reason": reason, "detail": detail}


def _visible_gap_tokens(pack: dict[str, Any]) -> set[str]:
    register = pack.get("source_gap_register") or []
    return {token for token in ["TODO_MARKET_DATA", "TODO_PEER_DATA", "TODO_MODEL_INPUT", "MISSING_DISCLOSURE", "TODO_SOURCE_REQUIRED", "LOW_CONFIDENCE_CLUE_ONLY"] if token in _text(register)}


def evaluate_promotion(pack: dict[str, Any], dry_run: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    non_blocking_todos: list[dict[str, str]] = []
    text = _text(pack)

    if FORBIDDEN.search(text):
        blockers.append(_issue("no_advice_gate", "high", "Direct trading language found in R5 pack."))

    quality = pack.get("quality_status") if isinstance(pack.get("quality_status"), dict) else {}
    if quality.get("high_issue_count") not in (0, "0", None):
        blockers.append(_issue("high_quality_issues", "high", "Pack has high quality issues.", str(quality.get("high_issue_count"))))
    if quality.get("source_gap_visible") is not True:
        blockers.append(_issue("source_gap_visibility", "high", "Source gaps are not visibly registered."))

    visible_tokens = _visible_gap_tokens(pack)
    hidden_tokens = sorted(token for token in rules.get("blocking_todo_tokens", []) if token in text and token not in visible_tokens)
    if hidden_tokens:
        blockers.append(_issue("hidden_todo_check", "high", "TODO/MISSING tokens appear outside visible source gaps.", ", ".join(hidden_tokens)))

    remaining_todos = list(dry_run.get("remaining_todos") or [])
    for token in remaining_todos:
        non_blocking_todos.append(_issue(f"todo_{token.lower()}", "todo", "Reviewed input TODO remains visible.", str(token)))

    if blockers:
        level = "blocked"
    elif all(dry_run.get(flag) is True for flag in rules.get("required_for_sample_quality_candidate", [])) and not remaining_todos:
        level = "sample_quality_candidate"
    elif all(dry_run.get(flag) is True for flag in rules.get("required_for_reviewed_input_research_draft", [])):
        level = "reviewed_input_research_draft"
    else:
        level = "source_gapped_research_draft"

    return {
        "artifact_type": "R5_pack_promotion_gate_result",
        "promotion_level": level,
        "blockers": blockers,
        "non_blocking_todos": non_blocking_todos,
        "checks": {
            "evidence_completeness": bool((pack.get("evidence_snapshot_pack") or {}).get("evidence_ids")),
            "business_disclosure_gaps_visible": "MISSING_DISCLOSURE" in visible_tokens,
            "reviewed_market_snapshot": dry_run.get("reviewed_market_inputs_available") is True,
            "reviewed_peer_snapshot": dry_run.get("reviewed_peer_inputs_available") is True,
            "reviewed_forecast_assumptions": dry_run.get("reviewed_forecast_assumptions_available") is True,
            "valuation_input_eligibility": dry_run.get("reviewed_valuation_inputs_available") is True,
            "no_advice_gate": not FORBIDDEN.search(text),
            "hidden_todo_check": not hidden_tokens,
            "source_gap_visibility": quality.get("source_gap_visible") is True,
        },
        "sample_quality_candidate_allowed": level == "sample_quality_candidate",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate R5 pack promotion.")
    parser.add_argument("--rules", type=Path, default=Path("config/r5_pack_promotion_rules.yaml"))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--dry-run", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)

    rules = load_yaml(args.rules)
    paths = rules.get("default_paths", {})
    pack_path = args.pack or Path(paths["source_gapped_pack"])
    dry_run_path = args.dry_run or Path(paths["reviewed_input_dry_run"])
    result = evaluate_promotion(load_yaml(pack_path), load_yaml(dry_run_path), rules)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(payload + "\n", encoding="utf-8")
    print(
        "r5_pack_promotion_level={level} blockers={blockers} todos={todos}".format(
            level=result["promotion_level"],
            blockers=len(result["blockers"]),
            todos=len(result["non_blocking_todos"]),
        )
    )
    if args.json:
        print(payload)
    return 0 if result["promotion_level"] != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
