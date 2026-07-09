#!/usr/bin/env python3
"""Run the R5 core asset subpack preflight gate."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import validate_r5_business_breakdown_pack as business_validator  # noqa: E402
import validate_r5_financial_history_pack as financial_validator  # noqa: E402
import validate_r5_forecast_model_pack as forecast_validator  # noqa: E402
import validate_r5_valuation_pack as valuation_validator  # noqa: E402

REPO_ROOT = SCRIPT_DIR.parents[3]
DEFAULTS = {
    "financial": REPO_ROOT / ".agents/skills/stock-deep-dive/assets/r5_financial_history_pack.example.yaml",
    "business": REPO_ROOT / ".agents/skills/stock-deep-dive/assets/r5_business_breakdown_pack.example.yaml",
    "forecast": REPO_ROOT / ".agents/skills/stock-deep-dive/assets/r5_forecast_model_pack.example.yaml",
    "valuation": REPO_ROOT / ".agents/skills/stock-deep-dive/assets/r5_valuation_pack.example.yaml",
}


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_text(item) for item in value)
    return "" if value is None else str(value)


def _known_todos(*payloads: dict[str, Any]) -> list[str]:
    tokens = [
        "TODO_MODEL_INPUT",
        "TODO_MARKET_DATA",
        "TODO_PEER_DATA",
        "TODO_SOURCE_REQUIRED",
        "MISSING_DISCLOSURE",
        "LOW_CONFIDENCE_CLUE_ONLY",
    ]
    text = "\n".join(_text(payload) for payload in payloads)
    return [token for token in tokens if token in text]


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("root YAML object must be a mapping")
    return data


def validate_one(
    *,
    label: str,
    path: Path,
    validate: Callable[[dict[str, Any]], list[str]],
    outcome: Callable[[list[str], dict[str, Any]], str],
) -> dict[str, Any]:
    try:
        data = load_yaml(path)
        errors = validate(data)
        derived = outcome(errors, data)
    except Exception as exc:  # noqa: BLE001
        return {
            "label": label,
            "path": str(path),
            "validator_status": "blocked",
            "errors": [f"ERROR: {exc}"],
            "data": {},
        }
    return {
        "label": label,
        "path": str(path),
        "validator_status": derived,
        "errors": errors,
        "data": data,
    }


def run_preflight(paths: dict[str, Path]) -> dict[str, Any]:
    checks = {
        "financial_history": validate_one(
            label="financial_history",
            path=paths["financial"],
            validate=financial_validator.validate_financial_history_pack,
            outcome=financial_validator.derive_outcome,
        ),
        "business_breakdown": validate_one(
            label="business_breakdown",
            path=paths["business"],
            validate=business_validator.validate_business_breakdown_pack,
            outcome=business_validator.derive_outcome,
        ),
        "forecast_model": validate_one(
            label="forecast_model",
            path=paths["forecast"],
            validate=forecast_validator.validate_forecast_model_pack,
            outcome=forecast_validator.derive_outcome,
        ),
        "valuation": validate_one(
            label="valuation",
            path=paths["valuation"],
            validate=valuation_validator.validate_valuation_pack,
            outcome=valuation_validator.derive_outcome,
        ),
    }
    blockers = [
        {"subpack": name, "errors": check["errors"]}
        for name, check in checks.items()
        if check["errors"] or check["validator_status"] in {"needs_fix", "blocked"}
    ]
    statuses = {name: check["validator_status"] for name, check in checks.items()}
    known_todos = _known_todos(*(check["data"] for check in checks.values()))
    all_accepted_with_todos = all(status == "accepted_with_todos" for status in statuses.values())
    all_ready = all(status == "accepted" for status in statuses.values())

    if blockers:
        core_state = "needs_fix"
    elif all_accepted_with_todos:
        core_state = "R5_CORE_ASSET_SCHEMAS_EXECUTABLE_WITH_TODOS"
    elif all_ready:
        core_state = "ready"
    else:
        core_state = "partial"

    sample_allowed = (
        not blockers
        and statuses["business_breakdown"] == "accepted"
        and statuses["forecast_model"] == "accepted"
        and statuses["valuation"] == "accepted"
    )
    return {
        "artifact_type": "R5_core_asset_preflight_result",
        "schema_version": "r5_core_asset_preflight_result_v0.1",
        "core_asset_state": core_state,
        "financial_history_status": statuses["financial_history"],
        "business_breakdown_status": statuses["business_breakdown"],
        "forecast_model_status": statuses["forecast_model"],
        "valuation_status": statuses["valuation"],
        "sample_quality_report_allowed": sample_allowed,
        "p2_allowed": False,
        "blockers": blockers,
        "non_blocking_todos": [
            {"token": token, "reason": "visible core subpack TODO or missing marker"}
            for token in known_todos
        ],
        "known_todos": known_todos,
        "next_candidate_tasks": [
            "supply accepted reviewed financial history inputs",
            "supply accepted reviewed business disclosure",
            "supply accepted reviewed forecast and valuation inputs",
        ],
        "checks": {name: {key: value for key, value in check.items() if key != "data"} for name, check in checks.items()},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run R5 core asset preflight.")
    parser.add_argument("--financial", type=Path, default=DEFAULTS["financial"])
    parser.add_argument("--business", type=Path, default=DEFAULTS["business"])
    parser.add_argument("--forecast", type=Path, default=DEFAULTS["forecast"])
    parser.add_argument("--valuation", type=Path, default=DEFAULTS["valuation"])
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args(argv)

    result = run_preflight(
        {
            "financial": args.financial,
            "business": args.business,
            "forecast": args.forecast,
            "valuation": args.valuation,
        }
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "r5_core_asset_state={state} financial={financial} business={business} forecast={forecast} valuation={valuation} sample_quality_allowed={sample} p2_allowed={p2} blockers={blockers}".format(
            state=result["core_asset_state"],
            financial=result["financial_history_status"],
            business=result["business_breakdown_status"],
            forecast=result["forecast_model_status"],
            valuation=result["valuation_status"],
            sample=str(result["sample_quality_report_allowed"]).lower(),
            p2=str(result["p2_allowed"]).lower(),
            blockers=len(result["blockers"]),
        )
    )
    return 0 if not result["blockers"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
