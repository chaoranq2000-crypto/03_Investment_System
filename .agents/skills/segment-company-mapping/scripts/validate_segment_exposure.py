#!/usr/bin/env python3
"""Validate a segment_exposure YAML handoff for B4-lite mapping."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required: pip install pyyaml") from exc

EXPOSURE_TYPES = {
    "revenue",
    "product",
    "technology",
    "customer",
    "project",
    "capacity",
    "order",
    "narrative",
    "excluded",
    "todo_insufficient_evidence",
}
BACKFLOW_DECISIONS = {
    "update_exposure",
    "create_segment_candidate",
    "update_company_universe",
    "update_segment_taxonomy",
    "update_scorecard",
    "no_backflow_needed",
    "blocked",
}
MISSING_TOKENS = {"MISSING_DISCLOSURE", "MISSING", "TODO_SOURCE_REQUIRED", "LOW_CONFIDENCE_CLUE_ONLY"}


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError("root YAML object must be a mapping")
    return data


def _is_present(value: Any) -> bool:
    return value not in (None, "", [])


def _identity_value(data: dict[str, Any], key: str) -> Any:
    if _is_present(data.get(key)):
        return data.get(key)
    identity = data.get("company_identity")
    if isinstance(identity, dict):
        return identity.get(key)
    return None


def _is_missing_token(value: Any) -> bool:
    if isinstance(value, str):
        return any(token in value for token in MISSING_TOKENS)
    if isinstance(value, dict):
        if _is_present(value.get("value")):
            return True
        return any(token in str(value.get("missing_reason") or "") for token in MISSING_TOKENS)
    return False


def _is_pct_value_valid(value: Any) -> bool:
    if isinstance(value, (int, float)):
        return True
    return _is_missing_token(value)


def _has_support(exposure: dict[str, Any]) -> bool:
    for key in ("evidence_ids", "claim_ids", "metric_ids"):
        if _is_present(exposure.get(key)):
            return True
    if _is_present(exposure.get("missing_reason")):
        return True
    return _is_present(exposure.get("TODO")) or _is_present(exposure.get("todo"))


def _as_score(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def validate_segment_exposure(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    for key in ("stock_code", "company_id", "company_name"):
        if not _is_present(_identity_value(data, key)):
            errors.append(f"missing identity field: {key}")

    exposures = data.get("exposures")
    if not isinstance(exposures, list):
        return [*errors, "exposures must be a list"]

    for idx, exposure in enumerate(exposures):
        if not isinstance(exposure, dict):
            errors.append(f"exposures[{idx}] must be a mapping")
            continue

        exposure_type = exposure.get("exposure_type")
        if exposure_type not in EXPOSURE_TYPES:
            errors.append(f"exposures[{idx}].exposure_type is invalid: {exposure_type}")

        score = _as_score(exposure.get("exposure_score"))
        if score is None or score < 0 or score > 5:
            errors.append(f"exposures[{idx}].exposure_score must be between 0 and 5")

        if exposure_type == "narrative" and score is not None and score > 1:
            errors.append(f"exposures[{idx}]: narrative exposure cannot score above 1")

        if exposure_type == "technology" and score is not None and score > 2:
            support_types = set(exposure.get("supporting_exposure_types") or [])
            if not support_types.intersection({"product", "project", "customer"}):
                errors.append("exposures[{idx}]: technology exposure above 2 requires product/project/customer support".format(idx=idx))

        for pct_field in ("revenue_pct", "profit_pct"):
            if not _is_pct_value_valid(exposure.get(pct_field)):
                errors.append(f"exposures[{idx}].{pct_field} must be a number or explicit MISSING/TODO token")

        if not _has_support(exposure):
            errors.append(f"exposures[{idx}] requires evidence_ids, claim_ids, metric_ids, missing_reason, or TODO")

        decision = exposure.get("backflow_decision")
        if decision not in BACKFLOW_DECISIONS:
            errors.append(f"exposures[{idx}].backflow_decision is invalid: {decision}")

    return errors


def derive_outcome(data: dict[str, Any], errors: list[str]) -> str:
    if errors:
        if any("missing identity" in error or "exposures must be a list" in error for error in errors):
            return "blocked"
        return "needs_fix"
    if "TODO" in str(data) or "MISSING" in str(data):
        return "accepted_with_todos"
    return "accepted"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a B4-lite segment_exposure YAML file.")
    parser.add_argument("--input", required=True, type=Path, help="segment_exposure YAML path")
    args = parser.parse_args(argv)
    try:
        data = load_yaml(args.input)
        errors = validate_segment_exposure(data)
    except Exception as exc:  # noqa: BLE001
        print(f"outcome: blocked")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    outcome = derive_outcome(data, errors)
    print(f"outcome: {outcome}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {args.input}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
