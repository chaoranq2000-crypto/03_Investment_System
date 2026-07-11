#!/usr/bin/env python3
"""Build reviewed-input readiness only from validated physical registries."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import promote_r5_reviewed_inputs_to_registries as promoter  # noqa: E402
import r5_reviewed_input_registry_io as registry_io  # noqa: E402

REGISTRY_FILES = promoter.REGISTRY_FILENAMES
CORE_FORECAST_DRIVERS = set(promoter.CORE_FORECAST_DRIVERS)
CRITICAL_TODOS = [
    "TODO_MARKET_DATA",
    "TODO_PEER_DATA",
    "TODO_MODEL_INPUT",
    "MISSING_DISCLOSURE",
    "TODO_SOURCE_REQUIRED",
]
FLAG_BY_TODO = {
    "TODO_MARKET_DATA": "reviewed_market_inputs_available",
    "TODO_PEER_DATA": "reviewed_peer_inputs_available",
    "TODO_MODEL_INPUT": "reviewed_forecast_assumptions_available",
    "MISSING_DISCLOSURE": "reviewed_business_disclosure_available",
    "TODO_SOURCE_REQUIRED": "reviewed_valuation_inputs_available",
}
REGISTRY_BY_TODO = {
    "TODO_MARKET_DATA": "market_peer",
    "TODO_PEER_DATA": "market_peer",
    "TODO_MODEL_INPUT": "forecast_assumptions",
    "MISSING_DISCLOSURE": "valuation_inputs",
    "TODO_SOURCE_REQUIRED": "valuation_inputs",
}
FIELD_BY_TODO = {
    "TODO_MARKET_DATA": "market_inputs",
    "TODO_PEER_DATA": "peer_inputs",
    "TODO_MODEL_INPUT": "assumptions",
    "MISSING_DISCLOSURE": "business_line_split",
    "TODO_SOURCE_REQUIRED": "valuation_input_refs",
}


def _is_todo(value: Any) -> bool:
    return isinstance(value, str) and (
        value.startswith("TODO_") or value.startswith("MISSING_") or value.startswith("LOW_CONFIDENCE_")
    )


def _unique_strings(values: list[Any]) -> list[str]:
    return sorted({str(value) for value in values if value not in (None, "")})


def _field_provenance(block: Any) -> tuple[list[str], list[str]]:
    input_ids: list[Any] = []
    evidence_ids: list[Any] = []
    if not isinstance(block, dict):
        return [], []
    for field in block.values():
        if not isinstance(field, dict):
            continue
        input_ids.append(field.get("input_id"))
        evidence_ids.append(field.get("evidence_id"))
        for row in field.get("provenance") or []:
            if isinstance(row, dict):
                input_ids.append(row.get("input_id"))
                evidence_ids.append(row.get("source_evidence_id"))
    return _unique_strings(input_ids), _unique_strings(evidence_ids)


def _reviewed_block(block: Any) -> bool:
    if not isinstance(block, dict) or not block:
        return False
    for field in block.values():
        if not isinstance(field, dict):
            return False
        if _is_todo(field.get("value")) or field.get("value") is None or not field.get("evidence_id"):
            return False
    return True


def _forecast_evidence(registry: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    rows = [row for row in registry.get("assumptions") or [] if isinstance(row, dict)]
    reviewed = {
        str(row.get("driver")): row
        for row in rows
        if row.get("review_status") == "reviewed"
        and (row.get("evidence_ids") or row.get("metric_ids"))
    }
    ready = CORE_FORECAST_DRIVERS <= set(reviewed)
    selected = [reviewed[driver] for driver in sorted(CORE_FORECAST_DRIVERS)] if ready else list(reviewed.values())
    input_ids = _unique_strings([row.get("input_id") for row in selected])
    evidence_ids = _unique_strings(
        [evidence_id for row in selected for evidence_id in (row.get("evidence_ids") or [])]
    )
    return ready, input_ids, evidence_ids


def _valuation_evidence(registry: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    refs = [row for row in registry.get("valuation_input_refs") or [] if isinstance(row, dict)]
    valid = [row for row in refs if row.get("input_id") and row.get("source_evidence_id")]
    return (
        bool(valid) and len(valid) == len(refs),
        _unique_strings([row.get("input_id") for row in valid]),
        _unique_strings([row.get("source_evidence_id") for row in valid]),
    )


def _business_evidence(
    valuation: dict[str, Any],
    ledger: dict[str, Any],
) -> tuple[bool, list[str], list[str]]:
    block = valuation.get("business_line_split")
    if not isinstance(block, dict) or block.get("review_status") not in {"reviewed", "explicitly_scoped"}:
        return False, [], []
    input_ids = _unique_strings(list(block.get("input_ids") or []))
    evidence_ids = _unique_strings(list(block.get("source_evidence_ids") or []))
    accepted_ledger = [
        row
        for row in ledger.get("items") or []
        if isinstance(row, dict)
        and row.get("input_type") == "business_disclosure"
        and row.get("review_decision") == "accepted"
        and row.get("evidence_id")
    ]
    ledger_input_ids = _unique_strings([row.get("input_id") for row in accepted_ledger])
    ledger_evidence_ids = _unique_strings([row.get("evidence_id") for row in accepted_ledger])
    ready = bool(input_ids and evidence_ids and set(input_ids) <= set(ledger_input_ids))
    return ready, input_ids, _unique_strings(evidence_ids + ledger_evidence_ids)


def _blocker(registry: str, reason: str) -> dict[str, str]:
    return {"registry": registry, "severity": "high", "reason": reason}


def _load_promotion_result(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    if not path.is_file():
        return {}
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    return registry_io.load_yaml(path)


def build_dry_run_from_registries(
    run_dir: Path,
    fixture_mode: bool,
    *,
    promotion_result_path: Path | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Derive reviewed flags and TODOs from validator-accepted registry bytes."""

    run_dir = run_dir.resolve()
    repo_root = (repo_root or SCRIPT_DIR.parent).resolve()
    payloads: dict[str, dict[str, Any]] = {}
    registry_sources: dict[str, dict[str, Any]] = {}
    blockers: list[dict[str, str]] = []
    invalid_registries: set[str] = set()

    for name, filename in REGISTRY_FILES.items():
        path = run_dir / filename
        sha256 = registry_io.file_sha256(path)
        if sha256 is None:
            validation = {
                "decision": "blocked",
                "issues": [{"severity": "high", "description": "physical registry is missing"}],
            }
            payload: dict[str, Any] = {}
            blockers.append(_blocker(name, f"missing physical registry: {filename}"))
            invalid_registries.add(name)
        else:
            try:
                payload = registry_io.load_yaml(path)
                validation = promoter._validate_candidate(name, payload, repo_root)
            except Exception as exc:  # noqa: BLE001
                payload = {}
                validation = {
                    "decision": "blocked",
                    "issues": [{"severity": "high", "description": str(exc)}],
                }
            if validation.get("decision") == "blocked":
                blockers.append(_blocker(name, "physical registry validator decision is blocked"))
                invalid_registries.add(name)
        payloads[name] = payload
        registry_sources[name] = {
            "path": filename,
            "sha256": sha256,
            "validation": validation,
        }

    promotion = _load_promotion_result(promotion_result_path)
    if promotion_result_path is not None and not promotion:
        blockers.append(_blocker("promotion_result", "promotion result is missing or invalid"))
    if promotion:
        for name, source in registry_sources.items():
            expected = ((promotion.get("registry_results") or {}).get(name) or {}).get("after_hash")
            if expected and expected != source.get("sha256"):
                blockers.append(_blocker(name, "physical registry hash does not match promotion result after_hash"))
                invalid_registries.add(name)
        if promotion.get("validation_status") != "pass":
            blockers.append(_blocker("promotion_result", "promotion result validation_status is not pass"))

    workflow_ids = _unique_strings([payload.get("workflow_id") for payload in payloads.values() if payload])
    stock_codes = _unique_strings([payload.get("stock_code") for payload in payloads.values() if payload])
    identity_valid = len(workflow_ids) == 1 and len(stock_codes) == 1
    if len(workflow_ids) != 1:
        blockers.append(_blocker("identity", f"workflow_id mismatch across registries: {workflow_ids}"))
    if len(stock_codes) != 1:
        blockers.append(_blocker("identity", f"stock_code mismatch across registries: {stock_codes}"))

    market = payloads.get("market_peer", {})
    forecast = payloads.get("forecast_assumptions", {})
    valuation = payloads.get("valuation_inputs", {})
    ledger = payloads.get("evidence_ledger", {})

    market_ready = "market_peer" not in invalid_registries and _reviewed_block(market.get("market_inputs"))
    market_ids, market_evidence = _field_provenance(market.get("market_inputs"))
    peer_ready = "market_peer" not in invalid_registries and _reviewed_block(market.get("peer_inputs"))
    peer_ids, peer_evidence = _field_provenance(market.get("peer_inputs"))
    forecast_ready, forecast_ids, forecast_evidence = _forecast_evidence(forecast)
    forecast_ready = forecast_ready and "forecast_assumptions" not in invalid_registries
    valuation_ready, valuation_ids, valuation_evidence = _valuation_evidence(valuation)
    valuation_ready = (
        valuation_ready
        and "valuation_inputs" not in invalid_registries
        and market_ready
        and peer_ready
        and forecast_ready
    )
    if "valuation_inputs" not in invalid_registries and not (valuation.get("valuation_input_refs") or []):
        blockers.append(_blocker("valuation_inputs", "valuation_input_refs are missing or empty"))
        invalid_registries.add("valuation_inputs")
        valuation_ready = False
    business_ready, business_ids, business_evidence = _business_evidence(valuation, ledger)
    business_ready = (
        business_ready
        and "valuation_inputs" not in invalid_registries
        and "evidence_ledger" not in invalid_registries
    )

    flags = {
        "reviewed_market_inputs_available": market_ready,
        "reviewed_peer_inputs_available": peer_ready,
        "reviewed_forecast_assumptions_available": forecast_ready,
        "reviewed_valuation_inputs_available": valuation_ready,
        "reviewed_business_disclosure_available": business_ready,
    }
    flag_evidence = {
        "reviewed_market_inputs_available": {"input_ids": market_ids, "evidence_ids": market_evidence},
        "reviewed_peer_inputs_available": {"input_ids": peer_ids, "evidence_ids": peer_evidence},
        "reviewed_forecast_assumptions_available": {"input_ids": forecast_ids, "evidence_ids": forecast_evidence},
        "reviewed_valuation_inputs_available": {"input_ids": valuation_ids, "evidence_ids": valuation_evidence},
        "reviewed_business_disclosure_available": {"input_ids": business_ids, "evidence_ids": business_evidence},
    }

    if not identity_valid:
        flags = {key: False for key in flags}

    todo_trace: list[dict[str, Any]] = []
    for token in CRITICAL_TODOS:
        flag = FLAG_BY_TODO[token]
        resolved = bool(flags[flag])
        evidence = flag_evidence[flag]
        todo_trace.append(
            {
                "token": token,
                "status": "resolved" if resolved else "remaining",
                "resolving_input_ids": evidence["input_ids"] if resolved else [],
                "registry_path": REGISTRY_FILES[REGISTRY_BY_TODO[token]],
                "field": FIELD_BY_TODO[token],
                "evidence_ids": evidence["evidence_ids"] if resolved else [],
                "reason": (
                    "resolved by validator-accepted physical registry provenance"
                    if resolved
                    else "physical registry evidence is missing, invalid, degraded or identity-inconsistent"
                ),
            }
        )
    remaining_todos = [row["token"] for row in todo_trace if row["status"] == "remaining"]
    core_ready = all(
        flags[key]
        for key in [
            "reviewed_market_inputs_available",
            "reviewed_peer_inputs_available",
            "reviewed_forecast_assumptions_available",
            "reviewed_valuation_inputs_available",
        ]
    )
    allowed_report_level = "reviewed_input_research_draft" if core_ready else "source_gapped_research_draft"
    blockers = sorted(blockers, key=lambda row: (row["registry"], row["reason"]))
    validation_status = "fail" if blockers else "pass"

    return {
        "artifact_type": "R5_reviewed_input_dry_run_result",
        "schema_version": "r5_reviewed_input_dry_run_result_v0.2",
        "derivation_source": "validated_physical_registries",
        "workflow_id": workflow_ids[0] if len(workflow_ids) == 1 else None,
        "stock_code": stock_codes[0] if len(stock_codes) == 1 else None,
        "fixture_mode": fixture_mode,
        "no_live_api": True,
        "validation_status": validation_status,
        "registry_sources": registry_sources,
        "promotion_result": {
            "path": promotion_result_path.name if promotion_result_path is not None else None,
            "provided": promotion_result_path is not None,
            "validated": bool(promotion) and not any(row["registry"] == "promotion_result" for row in blockers),
        },
        "identity": {
            "valid": identity_valid,
            "workflow_ids": workflow_ids,
            "stock_codes": stock_codes,
        },
        **flags,
        "flag_evidence": flag_evidence,
        "todo_trace": todo_trace,
        "remaining_todos": remaining_todos,
        "source_gap_visibility": bool(remaining_todos),
        "allowed_report_level": allowed_report_level,
        "internal_fixture_completeness": "all_complete" if all(flags.values()) else "core_complete" if core_ready else "source_gapped",
        "sample_quality_report_allowed": False if fixture_mode else False,
        "p2_allowed": False,
        "blockers": blockers,
        "notes": [
            "Reviewed flags are derived only from validated physical registries.",
            "Accepted dropzone row presence is not a readiness source.",
            "Fixture mode is capped below sample-quality and P2.",
        ],
    }


def write_result(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        path.write_bytes(registry_io.dump_yaml_bytes(payload))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build R5 reviewed-input dry run from physical registries.")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--promotion-result", type=Path)
    parser.add_argument("--fixture-mode", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args(argv)
    result = build_dry_run_from_registries(
        args.run_dir,
        args.fixture_mode,
        promotion_result_path=args.promotion_result,
        repo_root=args.repo_root,
    )
    write_result(args.json, result)
    print(
        "r5_registry_dry_run_status={status} level={level} market={market} peer={peer} "
        "forecast={forecast} valuation={valuation} business={business} blockers={blockers}".format(
            status=result["validation_status"],
            level=result["allowed_report_level"],
            market=str(result["reviewed_market_inputs_available"]).lower(),
            peer=str(result["reviewed_peer_inputs_available"]).lower(),
            forecast=str(result["reviewed_forecast_assumptions_available"]).lower(),
            valuation=str(result["reviewed_valuation_inputs_available"]).lower(),
            business=str(result["reviewed_business_disclosure_available"]).lower(),
            blockers=len(result["blockers"]),
        )
    )
    return 0 if result["validation_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
