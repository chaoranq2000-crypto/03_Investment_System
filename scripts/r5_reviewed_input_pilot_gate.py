#!/usr/bin/env python3
"""Close the after-Patch36 reviewed-input pilot gate."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import r5_pack_promotion_gate  # noqa: E402

FORBIDDEN = re.compile(
    r"买入|卖出|持有|仓位|目标价|保证收益|buy\s+rating|sell\s+rating|hold\s+rating|position\s+sizing",
    re.IGNORECASE,
)


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_text(item) for item in value)
    return value if isinstance(value, str) else ""


def _blocker(blocker_id: str, reason: str, detail: str = "") -> dict[str, str]:
    return {"id": blocker_id, "severity": "high", "reason": reason, "detail": detail}


def collect_inputs(repo_root: Path, rules: dict[str, Any]) -> dict[str, Any]:
    paths = rules["default_paths"]
    smoke = load_json(repo_root / paths["strict_smoke_result"])
    pack = load_yaml(repo_root / paths["source_gapped_pack"])
    dry_run = load_yaml(repo_root / paths["reviewed_input_dry_run_result"])
    scorecard = load_yaml(repo_root / paths["quality_scorecard_v2"])
    promotion_rules = load_yaml(repo_root / paths["promotion_rules"])
    promotion = r5_pack_promotion_gate.evaluate_promotion(pack, dry_run, promotion_rules)
    return {
        "strict_smoke_result": smoke,
        "source_gapped_pack": pack,
        "reviewed_input_dry_run_result": dry_run,
        "quality_scorecard_v2": scorecard,
        "pack_promotion_gate_result": promotion,
        "no_advice_gate_passed": FORBIDDEN.search(_text(pack)) is None,
    }


def evaluate_gate(inputs: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    non_blocking_todos: list[dict[str, str]] = []
    smoke = inputs["strict_smoke_result"]
    dry_run = inputs["reviewed_input_dry_run_result"]
    scorecard = inputs["quality_scorecard_v2"]
    promotion = inputs["pack_promotion_gate_result"]

    if smoke.get("status") != "pass" or int(smoke.get("failed", 1)) != 0:
        blockers.append(_blocker("strict_smoke", "Strict R5 smoke did not pass.", str(smoke.get("status"))))
    if promotion.get("promotion_level") == "blocked":
        blockers.extend(promotion.get("blockers") or [])
    if inputs.get("no_advice_gate_passed") is not True:
        blockers.append(_blocker("no_advice_gate", "No-advice gate failed."))

    required_flags = rules.get("required_for_reviewed_input_pilot", [])
    missing_reviewed_inputs = [flag for flag in required_flags if dry_run.get(flag) is not True]
    if missing_reviewed_inputs:
        blockers.append(_blocker("reviewed_input_requirements", "Reviewed-input pilot requires market, peer, forecast and valuation reviewed inputs.", ", ".join(missing_reviewed_inputs)))

    remaining_todos = list(dry_run.get("remaining_todos") or [])
    critical_todos = [token for token in remaining_todos if token in set(rules.get("critical_todo_tokens", []))]
    for token in remaining_todos:
        non_blocking_todos.append({"id": f"todo_{str(token).lower()}", "severity": "todo", "reason": "TODO remains visible after reviewed-input dry run.", "detail": str(token)})

    reviewed_input_pilot_allowed = not blockers
    fixed_boundaries = rules.get("fixed_boundaries") if isinstance(rules.get("fixed_boundaries"), dict) else {}
    sample_quality_allowed = (
        reviewed_input_pilot_allowed
        and promotion.get("promotion_level") == "sample_quality_candidate"
        and not critical_todos
        and not scorecard.get("sample_quality_blockers")
    )
    if fixed_boundaries.get("sample_quality_report_allowed") is False:
        sample_quality_allowed = False
    p2_allowed = sample_quality_allowed and bool(scorecard.get("p2_allowed", False))
    if fixed_boundaries.get("p2_allowed") is False:
        p2_allowed = False

    raw_promotion_level = promotion.get("promotion_level")
    effective_promotion_level = raw_promotion_level
    if fixed_boundaries.get("sample_quality_report_allowed") is False and raw_promotion_level == "sample_quality_candidate":
        effective_promotion_level = "reviewed_input_research_draft"

    if blockers:
        current_state = "R5_REVIEWED_INPUT_PILOT_BLOCKED_SOURCE_GAPPED"
    elif sample_quality_allowed:
        current_state = "R5_SAMPLE_QUALITY_CANDIDATE_ALLOWED"
    else:
        current_state = "R5_REVIEWED_INPUT_PILOT_ALLOWED"

    return {
        "artifact_type": "R5_reviewed_input_pilot_gate_result",
        "current_r5_state": current_state,
        "reviewed_input_pilot_allowed": reviewed_input_pilot_allowed,
        "sample_quality_report_allowed": sample_quality_allowed,
        "p2_allowed": p2_allowed,
        "blockers": blockers,
        "non_blocking_todos": non_blocking_todos,
        "input_summary": {
            "strict_smoke_status": smoke.get("status"),
            "raw_pack_promotion_level": raw_promotion_level,
            "pack_promotion_level": effective_promotion_level,
            "quality_allowed_report_level": scorecard.get("allowed_report_level"),
            "no_advice_gate_passed": inputs.get("no_advice_gate_passed"),
            "critical_todos": critical_todos,
            "fixed_boundaries": fixed_boundaries,
        },
        "next_candidate_tasks": list(rules.get("next_candidate_tasks") or [])[: int(rules.get("max_next_candidate_tasks", 3))],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the R5 reviewed-input pilot gate.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--rules", type=Path, default=Path("config/r5_reviewed_input_pilot_gate_rules.yaml"))
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    rules = load_yaml(args.rules)
    result = evaluate_gate(collect_inputs(repo_root, rules), rules)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "r5_reviewed_input_pilot_state={state} reviewed_input_pilot_allowed={pilot} sample_quality_allowed={sample} p2_allowed={p2} blockers={blockers}".format(
            state=result["current_r5_state"],
            pilot=str(result["reviewed_input_pilot_allowed"]).lower(),
            sample=str(result["sample_quality_report_allowed"]).lower(),
            p2=str(result["p2_allowed"]).lower(),
            blockers=len(result["blockers"]),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
