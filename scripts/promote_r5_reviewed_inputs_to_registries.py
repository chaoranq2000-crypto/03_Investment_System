#!/usr/bin/env python3
"""Materialize validated reviewed inputs into deterministic R5 registries."""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import r5_reviewed_input_registry_io as registry_io  # noqa: E402
import validate_r5_reviewed_input_dropzone as dropzone  # noqa: E402

REAL_WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
WORKFLOW_ID = REAL_WORKFLOW_ID
FIXTURE_WORKFLOW_ID = "wf_fixture_r5_bundle4"
CORE_FORECAST_DRIVERS = ["revenue_growth", "gross_margin", "opex", "net_profit", "eps"]
REGISTRY_FILENAMES = {
    "market_peer": "R5_market_peer_input_registry.yaml",
    "forecast_assumptions": "R5_forecast_assumption_registry.yaml",
    "valuation_inputs": "R5_valuation_input_registry.yaml",
    "evidence_ledger": "R5_evidence_request_review_ledger.yaml",
}
INPUT_TYPE_FLAGS = {
    "market_snapshot": "reviewed_market_inputs_available",
    "peer_snapshot": "reviewed_peer_inputs_available",
    "forecast_assumptions": "reviewed_forecast_assumptions_available",
    "business_disclosure": "reviewed_business_disclosure_available",
    "valuation_inputs": "reviewed_valuation_inputs_available",
}
TODO_BY_TYPE = {
    "market_snapshot": "TODO_MARKET_DATA",
    "peer_snapshot": "TODO_PEER_DATA",
    "forecast_assumptions": "TODO_MODEL_INPUT",
    "business_disclosure": "MISSING_DISCLOSURE",
    "valuation_inputs": "TODO_SOURCE_REQUIRED",
}
PACK_SECTION_BY_TYPE = {
    "market_snapshot": "valuation_pack",
    "peer_snapshot": "peer_comparison_pack",
    "forecast_assumptions": "forecast_model_pack",
    "business_disclosure": "business_breakdown_pack",
    "valuation_inputs": "valuation_pack",
}
MARKET_FIELD_MAP = {
    "close_price": ("current_price", "CNY_per_share"),
    "market_cap": ("market_cap", "CNY"),
    "pe_ttm": ("pe_ttm", "multiple"),
    "pb": ("pb", "multiple"),
    "ps": ("ps", "multiple"),
}
SCOPE_BY_DRIVER = {
    "revenue_growth": "company",
    "gross_margin": "margin",
    "opex": "opex",
    "net_profit": "company",
    "eps": "company",
}
UNIT_BY_DRIVER = {
    "revenue_growth": "pct",
    "gross_margin": "pct",
    "opex": "pct",
    "net_profit": "CNY",
    "eps": "CNY_per_share",
}


def load_yaml(path: Path) -> dict[str, Any]:
    """Compatibility wrapper retained for callers of the earlier promoter."""

    return registry_io.load_yaml(path)


def collect_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in dropzone.iter_input_files(root):
        records.extend(dropzone.read_dropzone_file(path))
    return [row for row in records if isinstance(row, dict)]


def _sorted_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(records, key=lambda row: (str(row.get("input_type", "")), str(row.get("input_id", ""))))


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip().lower() in dropzone.NULL_VALUES)


def _dedupe(values: list[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for value in values:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _provenance(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "input_id": str(row.get("input_id")),
        "source_evidence_id": row.get("source_evidence_id"),
        "source_rank": row.get("source_rank"),
        "as_of_date": row.get("as_of_date"),
        "reviewer": row.get("reviewer"),
        "reviewed_at": row.get("reviewed_at"),
        "limitations": copy.deepcopy(row.get("limitations") or []),
    }


def _provenance_list(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_provenance(row) for row in _sorted_records(records)]


def _todo_field(value: str, unit: str | None, source_type: str) -> dict[str, Any]:
    field: dict[str, Any] = {
        "value": value,
        "evidence_id": None,
        "source_type": source_type,
        "missing_reason": value,
    }
    if unit:
        field["unit"] = unit
    return field


def _reviewed_field(
    *,
    value: Any,
    unit: str | None,
    source_type: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    ordered = _sorted_records(records)
    primary = ordered[0]
    field: dict[str, Any] = {
        "value": value,
        "evidence_id": primary.get("source_evidence_id"),
        "source_type": source_type,
        "input_id": primary.get("input_id"),
        "source_rank": primary.get("source_rank"),
        "as_of_date": primary.get("as_of_date"),
        "reviewer": primary.get("reviewer"),
        "reviewed_at": primary.get("reviewed_at"),
        "limitations": copy.deepcopy(primary.get("limitations") or []),
        "provenance": _provenance_list(ordered),
    }
    if unit:
        field["unit"] = unit
    return field


def _field_is_todo(field: Any) -> bool:
    if not isinstance(field, dict):
        return True
    value = field.get("value")
    todo_value = value is None or (
        isinstance(value, str) and value in {"TODO_MARKET_DATA", "TODO_PEER_DATA"}
    )
    return todo_value or not field.get("evidence_id")


def _market_status(payload: dict[str, Any], accepted_records: list[dict[str, Any]]) -> str:
    fields = []
    for block_name in ["market_inputs", "peer_inputs"]:
        block = payload.get(block_name)
        if isinstance(block, dict):
            fields.extend(block.values())
    if fields and all(not _field_is_todo(field) for field in fields):
        return "reviewed"
    return "explicitly_degraded_but_reviewed" if accepted_records else "pending"


def _build_market_peer_registry(
    workflow_id: str,
    stock_code: str,
    accepted_records: list[dict[str, Any]],
    conflicts: list[str],
) -> dict[str, Any]:
    market_records = [row for row in accepted_records if row.get("input_type") == "market_snapshot"]
    peer_records = [row for row in accepted_records if row.get("input_type") == "peer_snapshot"]
    market_inputs = {
        target: _todo_field("TODO_MARKET_DATA", unit, "market_snapshot")
        for _source, (target, unit) in MARKET_FIELD_MAP.items()
    }

    for source_field, (target_field, unit) in MARKET_FIELD_MAP.items():
        rows = [row for row in market_records if not _is_missing(row.get(source_field))]
        if not rows:
            continue
        values = _dedupe([row.get(source_field) for row in rows])
        if len(values) > 1:
            conflicts.append(f"market semantic conflict for {target_field}")
            continue
        market_inputs[target_field] = _reviewed_field(
            value=values[0],
            unit=unit,
            source_type="market_snapshot",
            records=rows,
        )

    peer_inputs: dict[str, Any] = {
        "peer_set": _todo_field("TODO_PEER_DATA", None, "peer_snapshot"),
        "peer_valuation_multiples": _todo_field("TODO_PEER_DATA", None, "peer_snapshot"),
    }
    if peer_records:
        ordered = _sorted_records(peer_records)
        peer_set = sorted({str(row.get("peer_stock_code")) for row in ordered if row.get("peer_stock_code")})
        multiples = [
            {
                "peer_set_id": row.get("peer_set_id"),
                "peer_stock_code": row.get("peer_stock_code"),
                "peer_company_name": row.get("peer_company_name"),
                "metric_name": row.get("peer_metric_name"),
                "metric_value": row.get("peer_metric_value"),
                "metric_unit": row.get("peer_metric_unit"),
                "input_id": row.get("input_id"),
                "evidence_id": row.get("source_evidence_id"),
            }
            for row in ordered
        ]
        peer_inputs["peer_set"] = _reviewed_field(
            value=peer_set,
            unit=None,
            source_type="peer_snapshot",
            records=ordered,
        )
        peer_inputs["peer_valuation_multiples"] = _reviewed_field(
            value=multiples,
            unit=None,
            source_type="peer_snapshot",
            records=ordered,
        )

    relevant = market_records + peer_records
    as_of_dates = sorted({str(row.get("as_of_date")) for row in relevant if row.get("as_of_date")})
    reviewers = sorted({str(row.get("reviewer")) for row in relevant if row.get("reviewer")})
    payload: dict[str, Any] = {
        "schema_version": "r5_market_peer_input_registry_v0.1",
        "artifact_type": "R5_market_peer_input_registry",
        "workflow_id": workflow_id,
        "stock_code": stock_code,
        "as_of_date": as_of_dates[-1] if as_of_dates else None,
        "review_status": "pending",
        "reviewer": ", ".join(reviewers) if reviewers else None,
        "no_live_api": True,
        "market_inputs": market_inputs,
        "peer_inputs": peer_inputs,
        "allowed_usage": ["reviewed_input_research_draft_only"],
        "blocking_rules": ["fixture inputs never open sample-quality or P2"],
        "promotion_provenance": _provenance_list(relevant),
    }
    payload["review_status"] = _market_status(payload, relevant)
    return payload


def _merge_market_peer(
    existing: dict[str, Any],
    candidate: dict[str, Any],
    workflow_id: str,
    stock_code: str,
    conflicts: list[str],
) -> dict[str, Any]:
    if not existing:
        return candidate
    if str(existing.get("workflow_id")) not in {"", workflow_id} or str(existing.get("stock_code")) not in {"", stock_code}:
        conflicts.append("market/peer registry identity conflict")
        return candidate
    merged = copy.deepcopy(candidate)
    for key, value in existing.items():
        if key not in {"market_inputs", "peer_inputs", "promotion_provenance"}:
            merged.setdefault(key, copy.deepcopy(value))
    for block_name in ["market_inputs", "peer_inputs"]:
        old_block = existing.get(block_name) if isinstance(existing.get(block_name), dict) else {}
        new_block = merged[block_name]
        for field_name, old_field in old_block.items():
            if field_name not in new_block:
                new_block[field_name] = copy.deepcopy(old_field)
                continue
            new_field = new_block[field_name]
            if old_field == new_field:
                continue
            if _field_is_todo(old_field) and not _field_is_todo(new_field):
                continue
            if not _field_is_todo(old_field) and _field_is_todo(new_field):
                new_block[field_name] = copy.deepcopy(old_field)
                continue
            old_input = old_field.get("input_id") if isinstance(old_field, dict) else None
            new_input = new_field.get("input_id") if isinstance(new_field, dict) else None
            old_evidence = old_field.get("evidence_id") if isinstance(old_field, dict) else None
            new_evidence = new_field.get("evidence_id") if isinstance(new_field, dict) else None
            if old_input == new_input and old_evidence == new_evidence:
                continue
            conflicts.append(f"market/peer existing record conflict for {block_name}.{field_name}")
    old_provenance = existing.get("promotion_provenance") or []
    merged["promotion_provenance"] = _merge_rows_by_key(
        list(old_provenance) + list(candidate.get("promotion_provenance") or []), "input_id"
    )
    merged["review_status"] = _market_status(merged, merged["promotion_provenance"])
    return merged


def _pending_forecast_assumption(driver: str) -> dict[str, Any]:
    return {
        "assumption_id": f"TODO_REVIEWED_{driver.upper()}",
        "driver": driver,
        "periods": ["2026E"],
        "value": "TODO_MODEL_INPUT",
        "unit": UNIT_BY_DRIVER[driver],
        "evidence_ids": [],
        "metric_ids": [],
        "missing_reason": "TODO_MODEL_INPUT",
        "allowed_usage": "degraded_forecast_only",
        "review_status": "pending",
        "scope": SCOPE_BY_DRIVER[driver],
        "scenario": "base",
        "metric_name": driver,
        "supporting_evidence_ids": [],
        "supporting_metric_ids": [],
        "rationale": "TODO_MODEL_INPUT",
        "limitations": ["TODO_MODEL_INPUT"],
    }


def _reviewed_forecast_assumption(row: dict[str, Any]) -> dict[str, Any]:
    source_evidence_id = row.get("source_evidence_id")
    evidence_ids = list(row.get("evidence_ids") or ([source_evidence_id] if source_evidence_id else []))
    metric_ids = list(row.get("metric_ids") or [])
    supporting_evidence_ids = list(row.get("supporting_evidence_ids") or evidence_ids)
    supporting_metric_ids = list(row.get("supporting_metric_ids") or metric_ids)
    return {
        "assumption_id": row.get("assumption_id") or row.get("input_id"),
        "driver": row.get("driver") or row.get("metric_name"),
        "periods": copy.deepcopy(row.get("periods") or ["2026E"]),
        "value": row.get("value"),
        "unit": row.get("unit"),
        "evidence_ids": evidence_ids,
        "metric_ids": metric_ids,
        "allowed_usage": "reviewed_input_research_draft",
        "review_status": "reviewed",
        "reviewer_note": row.get("reviewer_note") or "reviewed input promotion",
        "scope": row.get("scope") or SCOPE_BY_DRIVER.get(str(row.get("driver")), "company"),
        "scenario": row.get("scenario") or "base",
        "metric_name": row.get("metric_name") or row.get("driver"),
        "supporting_evidence_ids": supporting_evidence_ids,
        "supporting_metric_ids": supporting_metric_ids,
        "rationale": row.get("rationale") or "reviewed input promotion",
        "limitations": copy.deepcopy(row.get("limitations") or []),
        "input_id": row.get("input_id"),
        "source_rank": row.get("source_rank"),
        "as_of_date": row.get("as_of_date"),
        "reviewer": row.get("reviewer"),
        "reviewed_at": row.get("reviewed_at"),
        "provenance": _provenance(row),
    }


def _build_forecast_registry(
    workflow_id: str,
    stock_code: str,
    accepted_records: list[dict[str, Any]],
    conflicts: list[str],
) -> dict[str, Any]:
    records = [row for row in accepted_records if row.get("input_type") == "forecast_assumptions"]
    accepted_by_driver: dict[str, dict[str, Any]] = {}
    for row in _sorted_records(records):
        driver = str(row.get("driver") or row.get("metric_name") or "")
        if not driver:
            conflicts.append(f"forecast input {row.get('input_id')} has no driver")
            continue
        if driver in accepted_by_driver and accepted_by_driver[driver] != row:
            conflicts.append(f"forecast semantic conflict for driver {driver}")
            continue
        accepted_by_driver[driver] = row

    assumptions = []
    for driver in CORE_FORECAST_DRIVERS:
        row = accepted_by_driver.get(driver)
        assumptions.append(_reviewed_forecast_assumption(row) if row else _pending_forecast_assumption(driver))
    for driver in sorted(set(accepted_by_driver) - set(CORE_FORECAST_DRIVERS)):
        assumptions.append(_reviewed_forecast_assumption(accepted_by_driver[driver]))

    reviewed_drivers = {str(row.get("driver")) for row in assumptions if row.get("review_status") == "reviewed"}
    if set(CORE_FORECAST_DRIVERS) <= reviewed_drivers:
        review_status = "reviewed"
    elif reviewed_drivers:
        review_status = "explicitly_degraded_but_reviewed"
    else:
        review_status = "pending"
    as_of_dates = sorted({str(row.get("as_of_date")) for row in records if row.get("as_of_date")})
    reviewers = sorted({str(row.get("reviewer")) for row in records if row.get("reviewer")})
    return {
        "schema_version": "r5_forecast_assumption_registry_v0.1",
        "artifact_type": "R5_forecast_assumption_registry",
        "workflow_id": workflow_id,
        "stock_code": stock_code,
        "review_status": review_status,
        "as_of_date": as_of_dates[-1] if as_of_dates else None,
        "reviewer": ", ".join(reviewers) if reviewers else None,
        "no_live_api": True,
        "assumptions": assumptions,
        "blocking_rules": ["fixture assumptions never open sample-quality or P2"],
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
    }


def _merge_forecast(
    existing: dict[str, Any],
    candidate: dict[str, Any],
    workflow_id: str,
    stock_code: str,
    conflicts: list[str],
) -> dict[str, Any]:
    if not existing:
        return candidate
    if str(existing.get("workflow_id")) not in {"", workflow_id} or str(existing.get("stock_code")) not in {"", stock_code}:
        conflicts.append("forecast registry identity conflict")
        return candidate
    old_rows = [row for row in existing.get("assumptions") or [] if isinstance(row, dict)]
    new_rows = [row for row in candidate.get("assumptions") or [] if isinstance(row, dict)]
    old_by_driver = {str(row.get("driver")): row for row in old_rows if row.get("driver")}
    merged_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for new_row in new_rows:
        driver = str(new_row.get("driver"))
        seen.add(driver)
        old_row = old_by_driver.get(driver)
        if old_row is None or old_row == new_row:
            merged_rows.append(copy.deepcopy(new_row))
        elif old_row.get("review_status") != "reviewed" and new_row.get("review_status") == "reviewed":
            merged_rows.append(copy.deepcopy(new_row))
        elif old_row.get("review_status") == "reviewed" and new_row.get("review_status") != "reviewed":
            merged_rows.append(copy.deepcopy(old_row))
        elif old_row.get("input_id") == new_row.get("input_id") and old_row.get("evidence_ids") == new_row.get("evidence_ids"):
            merged_rows.append(copy.deepcopy(new_row))
        else:
            conflicts.append(f"forecast existing record conflict for driver {driver}")
            merged_rows.append(copy.deepcopy(old_row))
    for old_row in old_rows:
        driver = str(old_row.get("driver"))
        if driver not in seen:
            merged_rows.append(copy.deepcopy(old_row))
    merged = copy.deepcopy(candidate)
    stale_when_fully_reviewed = {"forecast_model_interlock"}
    for key, value in existing.items():
        if key != "assumptions" and not (
            candidate.get("review_status") == "reviewed" and key in stale_when_fully_reviewed
        ):
            merged.setdefault(key, copy.deepcopy(value))
    merged["assumptions"] = sorted(merged_rows, key=lambda row: (CORE_FORECAST_DRIVERS.index(str(row.get("driver"))) if str(row.get("driver")) in CORE_FORECAST_DRIVERS else 99, str(row.get("driver")), str(row.get("assumption_id"))))
    reviewed_drivers = {str(row.get("driver")) for row in merged_rows if row.get("review_status") == "reviewed"}
    merged["review_status"] = (
        "reviewed"
        if set(CORE_FORECAST_DRIVERS) <= reviewed_drivers
        else "explicitly_degraded_but_reviewed"
        if reviewed_drivers
        else "pending"
    )
    return merged


def _accepted_by_type(accepted_records: list[dict[str, Any]], input_type: str) -> list[dict[str, Any]]:
    return [row for row in accepted_records if row.get("input_type") == input_type]


def _block_reference(
    *,
    path: str,
    records: list[dict[str, Any]],
    ready_status: str = "reviewed",
    missing_status: str,
) -> dict[str, Any]:
    if not records:
        return {"path": path, "review_status": missing_status, "source_evidence_ids": [], "input_ids": []}
    return {
        "path": path,
        "review_status": ready_status,
        "source_evidence_ids": sorted({str(row.get("source_evidence_id")) for row in records}),
        "input_ids": sorted({str(row.get("input_id")) for row in records}),
        "provenance": _provenance_list(records),
    }


def _build_valuation_registry(
    workflow_id: str,
    stock_code: str,
    accepted_records: list[dict[str, Any]],
) -> dict[str, Any]:
    market = _accepted_by_type(accepted_records, "market_snapshot")
    peer = _accepted_by_type(accepted_records, "peer_snapshot")
    forecast = _accepted_by_type(accepted_records, "forecast_assumptions")
    business = _accepted_by_type(accepted_records, "business_disclosure")
    valuation = _accepted_by_type(accepted_records, "valuation_inputs")
    reviewed_drivers = {str(row.get("driver") or row.get("metric_name")) for row in forecast}
    forecast_ready = set(CORE_FORECAST_DRIVERS) <= reviewed_drivers
    requested_methods = {
        str(method)
        for row in valuation
        for method in (row.get("requested_methods") or [])
    }
    relative_ready = bool(valuation and market and peer)
    dcf_ready = bool(valuation and forecast_ready)
    sotp_ready = bool(valuation and business)
    method_rules = [
        ("relative_pe", relative_ready, ["reviewed_market_snapshot", "reviewed_peer_snapshot"]),
        ("dcf", dcf_ready, ["reviewed_forecast_assumptions"]),
        ("sotp", sotp_ready, ["reviewed_business_disclosure"]),
    ]
    methods = sorted(
        [
            {
                "method": name,
                "requested": name in requested_methods,
                "eligibility": "eligible" if name in requested_methods and ready else "blocked_for_sample_quality",
                "required_inputs": required,
            }
            for name, ready, required in method_rules
        ],
        key=lambda row: str(row["method"]),
    )
    limitations = [token for input_type, token in TODO_BY_TYPE.items() if not _accepted_by_type(accepted_records, input_type)]
    return {
        "artifact_type": "R5_valuation_input_registry",
        "schema_version": "r5_valuation_input_registry_v0.1",
        "workflow_id": workflow_id,
        "stock_code": stock_code,
        "no_live_api": True,
        "market_snapshot": _block_reference(
            path=REGISTRY_FILENAMES["market_peer"], records=market, missing_status="TODO_MARKET_DATA"
        ),
        "peer_snapshot": _block_reference(
            path=REGISTRY_FILENAMES["market_peer"], records=peer, missing_status="TODO_PEER_DATA"
        ),
        "forecast_model": {
            **_block_reference(
                path=REGISTRY_FILENAMES["forecast_assumptions"],
                records=forecast if forecast_ready else [],
                missing_status="TODO_MODEL_INPUT",
            ),
            "assumption_ids": sorted({str(row.get("assumption_id") or row.get("input_id")) for row in forecast}) if forecast_ready else [],
        },
        "business_line_split": {
            "review_status": "reviewed" if business else "MISSING_DISCLOSURE",
            "source_evidence_ids": sorted({str(row.get("source_evidence_id")) for row in business}),
            "input_ids": sorted({str(row.get("input_id")) for row in business}),
            "provenance": _provenance_list(business),
        },
        "valuation_input_refs": _provenance_list(valuation),
        "valuation_methods": methods,
        "limitations": limitations,
        "fixture_mode_caps": {"sample_quality_report_allowed": False, "p2_allowed": False},
    }


def _merge_valuation(
    existing: dict[str, Any],
    candidate: dict[str, Any],
    workflow_id: str,
    stock_code: str,
    conflicts: list[str],
) -> dict[str, Any]:
    if not existing:
        return candidate
    if str(existing.get("workflow_id")) not in {"", workflow_id} or str(existing.get("stock_code")) not in {"", stock_code}:
        conflicts.append("valuation registry identity conflict")
        return candidate
    merged = copy.deepcopy(candidate)
    known_blocks = {"market_snapshot", "peer_snapshot", "forecast_model", "business_line_split"}
    for key, value in existing.items():
        if key not in known_blocks | {"valuation_methods", "valuation_input_refs", "limitations"}:
            merged.setdefault(key, copy.deepcopy(value))
    for block_name in known_blocks:
        old = existing.get(block_name)
        new = merged.get(block_name)
        if not isinstance(old, dict) or not isinstance(new, dict) or old == new:
            continue
        old_ready = old.get("review_status") in {"reviewed", "ready", "explicitly_scoped"}
        new_ready = new.get("review_status") in {"reviewed", "ready", "explicitly_scoped"}
        if old_ready and not new_ready:
            merged[block_name] = copy.deepcopy(old)
        elif old_ready and new_ready and old.get("source_evidence_ids") != new.get("source_evidence_ids"):
            conflicts.append(f"valuation existing record conflict for {block_name}")
    old_methods = {str(row.get("method")): row for row in existing.get("valuation_methods") or [] if isinstance(row, dict)}
    new_methods = {str(row.get("method")): row for row in merged.get("valuation_methods") or [] if isinstance(row, dict)}
    for method, row in old_methods.items():
        new_methods.setdefault(method, copy.deepcopy(row))
    merged["valuation_methods"] = [new_methods[key] for key in sorted(new_methods)]
    merged["valuation_input_refs"] = _merge_rows_by_key(
        list(existing.get("valuation_input_refs") or []) + list(candidate.get("valuation_input_refs") or []),
        "input_id",
    )
    return merged


def _ledger_decision(status: str) -> str:
    return {
        "accepted": "accepted",
        "accepted_degraded": "needs_manual_collection",
        "pending": "pending",
        "rejected": "rejected",
    }.get(status, "pending")


def _build_evidence_ledger(workflow_id: str, stock_code: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    items = []
    for row in _sorted_records(records):
        input_id = str(row.get("input_id"))
        status = str(row.get("review_status"))
        input_type = str(row.get("input_type"))
        decision = _ledger_decision(status)
        if decision == "accepted":
            reason = "reviewed input accepted"
            next_action = "retain in the validated registry provenance chain"
        elif decision == "rejected":
            reason = "reviewed input rejected"
            next_action = "retain rejection without promoting a fact"
        else:
            limitations = row.get("limitations") or [TODO_BY_TYPE.get(input_type, "TODO_SOURCE_REQUIRED")]
            reason = "; ".join(str(item) for item in limitations)
            next_action = "keep the unresolved or degraded input visible"
        items.append(
            {
                "request_id": f"reviewed_input::{input_id}",
                "source_gap_id": f"R5_FIXTURE_{input_type.upper()}_INPUT",
                "pack_section": PACK_SECTION_BY_TYPE.get(input_type, "evidence_snapshot_pack"),
                "review_decision": decision,
                "evidence_id": row.get("source_evidence_id"),
                "source_rank": row.get("source_rank"),
                "reason": reason,
                "next_action": next_action,
                "input_id": input_id,
                "input_type": input_type,
                "input_review_status": status,
                "as_of_date": row.get("as_of_date"),
                "reviewer": row.get("reviewer"),
                "reviewed_at": row.get("reviewed_at"),
                "limitations": copy.deepcopy(row.get("limitations") or []),
                "no_live_api": True,
                "provenance": _provenance(row),
            }
        )
    return _finalize_ledger(
        {
            "schema_version": "r5_evidence_request_review_ledger_v0.1",
            "artifact_type": "R5_evidence_request_review_ledger",
            "workflow_id": workflow_id,
            "stock_code": stock_code,
            "source_queue_path": None,
            "review_status": "pending",
            "no_live_api": True,
            "items": items,
            "promotion_rules": [
                "accepted requires evidence_id and source_rank",
                "non-accepted decisions never become reviewed facts",
                "fixture rows never open sample-quality or P2",
            ],
        }
    )


def _merge_rows_by_key(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_key = str(row.get(key) or "")
        if row_key:
            merged[row_key] = copy.deepcopy(row)
    return [merged[row_key] for row_key in sorted(merged)]


def _finalize_ledger(payload: dict[str, Any]) -> dict[str, Any]:
    items = sorted(
        [row for row in payload.get("items") or [] if isinstance(row, dict)],
        key=lambda row: str(row.get("request_id", "")),
    )
    decisions = Counter(str(row.get("review_decision")) for row in items)
    payload["items"] = items
    payload["review_status"] = "reviewed" if items and decisions.get("accepted", 0) == len(items) else "pending"
    payload["summary"] = {
        "request_count": len(items),
        "pending_count": decisions.get("pending", 0),
        "accepted_count": decisions.get("accepted", 0),
        "rejected_count": decisions.get("rejected", 0),
        "needs_manual_collection_count": decisions.get("needs_manual_collection", 0),
        "accepted_null_evidence_count": sum(
            1 for row in items if row.get("review_decision") == "accepted" and not row.get("evidence_id")
        ),
    }
    return payload


def _merge_ledger(
    existing: dict[str, Any],
    candidate: dict[str, Any],
    workflow_id: str,
    stock_code: str,
    conflicts: list[str],
) -> dict[str, Any]:
    if not existing:
        return candidate
    if str(existing.get("workflow_id")) not in {"", workflow_id} or str(existing.get("stock_code")) not in {"", stock_code}:
        conflicts.append("evidence ledger identity conflict")
        return candidate
    old_items = {str(row.get("request_id")): row for row in existing.get("items") or [] if isinstance(row, dict)}
    new_items = {str(row.get("request_id")): row for row in candidate.get("items") or [] if isinstance(row, dict)}
    merged_items: dict[str, dict[str, Any]] = {key: copy.deepcopy(value) for key, value in old_items.items()}
    for request_id, row in new_items.items():
        old = merged_items.get(request_id)
        if old and old != row and old.get("input_id") != row.get("input_id"):
            conflicts.append(f"evidence ledger conflict for {request_id}")
            continue
        merged_items[request_id] = copy.deepcopy(row)
    merged = copy.deepcopy(candidate)
    for key, value in existing.items():
        if key not in {"items", "summary", "review_status"}:
            merged.setdefault(key, copy.deepcopy(value))
    merged["items"] = [merged_items[key] for key in sorted(merged_items)]
    return _finalize_ledger(merged)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise ImportError(f"cannot load validator: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _validate_candidate(name: str, payload: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    roundtrip = yaml.safe_load(registry_io.dump_yaml_bytes(payload).decode("utf-8"))
    validators: list[dict[str, Any]] = []
    if name == "market_peer":
        module = _load_module(
            "r5_bundle4_market_validator",
            repo_root / ".agents/skills/stock-deep-dive/scripts/validate_r5_market_peer_input_registry.py",
        )
        issues = module.validate_registry(roundtrip)
        validators.append({"name": "market_peer_registry", "decision": module.derive_decision(roundtrip, issues), "issues": issues})
    elif name == "forecast_assumptions":
        module = _load_module(
            "r5_bundle4_forecast_registry_validator",
            repo_root / ".agents/skills/stock-deep-dive/scripts/validate_r5_forecast_assumption_registry.py",
        )
        issues = module.validate_registry(roundtrip)
        validators.append({"name": "forecast_registry", "decision": module.derive_decision(roundtrip, issues), "issues": issues})
        if roundtrip.get("review_status") == "reviewed":
            downstream = _load_module(
                "r5_bundle4_forecast_downstream_validator",
                repo_root / ".agents/skills/stock-deep-dive/scripts/validate_r5_forecast_assumptions.py",
            )
            downstream_issues = downstream.validate_assumptions(roundtrip)
            validators.append(
                {
                    "name": "forecast_downstream",
                    "decision": downstream.derive_decision(roundtrip, downstream_issues),
                    "issues": downstream_issues,
                }
            )
    elif name == "valuation_inputs":
        module = _load_module(
            "r5_bundle4_valuation_validator",
            repo_root / ".agents/skills/stock-deep-dive/scripts/validate_r5_valuation_inputs.py",
        )
        issues = module.validate_valuation_inputs(roundtrip)
        validators.append({"name": "valuation_inputs", "decision": module.derive_decision(roundtrip, issues), "issues": issues})
    elif name == "evidence_ledger":
        module = _load_module(
            "r5_bundle4_ledger_validator",
            repo_root / ".agents/skills/evidence-ingest/scripts/validate_r5_evidence_request_review_ledger.py",
        )
        issues = module.validate_ledger(roundtrip)
        validators.append({"name": "evidence_ledger", "decision": module.derive_decision(roundtrip, issues), "issues": issues})
    else:  # pragma: no cover - internal programming error
        raise ValueError(f"unknown registry candidate: {name}")
    blocked = any(
        item["decision"] == "blocked"
        or any(issue.get("severity") == "high" for issue in item.get("issues", []))
        for item in validators
    )
    return {
        "decision": "blocked" if blocked else validators[-1]["decision"],
        "validators": validators,
        "issues": [issue for item in validators for issue in item.get("issues", [])],
    }


def _registry_paths(output_run_dir: Path) -> dict[str, Path]:
    return {key: output_run_dir / filename for key, filename in REGISTRY_FILENAMES.items()}


def _registry_input_ids(name: str, records: list[dict[str, Any]]) -> list[str]:
    if name == "market_peer":
        allowed = {"market_snapshot", "peer_snapshot"}
        selected = [row for row in records if row.get("review_status") == "accepted" and row.get("input_type") in allowed]
    elif name == "forecast_assumptions":
        selected = [row for row in records if row.get("review_status") == "accepted" and row.get("input_type") == "forecast_assumptions"]
    elif name == "valuation_inputs":
        selected = [row for row in records if row.get("review_status") == "accepted"]
    else:
        selected = records
    return sorted({str(row.get("input_id")) for row in selected if row.get("input_id")})


def _blocked_registry_results(
    output_run_dir: Path,
    records: list[dict[str, Any]],
    reason: str,
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for name, path in _registry_paths(output_run_dir).items():
        before_hash = registry_io.file_sha256(path)
        results[name] = {
            "target_path": str(path),
            "action": "blocked",
            "planned_action": "unchanged",
            "before_hash": before_hash,
            "after_hash": before_hash,
            "promoted_input_ids": _registry_input_ids(name, records),
            "validation": {"decision": "blocked", "issues": [{"severity": "high", "description": reason}]},
        }
    return results


def _promotion_level(flags: dict[str, bool], fixture_mode: bool) -> str:
    core_ready = all(
        flags[key]
        for key in [
            "reviewed_market_inputs_available",
            "reviewed_peer_inputs_available",
            "reviewed_forecast_assumptions_available",
            "reviewed_valuation_inputs_available",
        ]
    )
    if core_ready:
        return "reviewed_input_research_draft"
    return "source_gapped_research_draft"


def _result(
    *,
    workflow_id: str,
    stock_code: str | None,
    dropzone_root: Path,
    output_run_dir: Path,
    fixture_mode: bool,
    dry_run: bool,
    validation_status: str,
    validation_issues: list[dict[str, Any]],
    promotion_status: str,
    registry_results: dict[str, Any],
    records: list[dict[str, Any]],
    flags: dict[str, bool],
    registries_changed: bool,
) -> dict[str, Any]:
    accepted = [row for row in records if row.get("review_status") == "accepted"]
    degraded = [row for row in records if row.get("review_status") == "accepted_degraded"]
    allowed_level = _promotion_level(flags, fixture_mode)
    remaining_todos = [TODO_BY_TYPE[input_type] for input_type in TODO_BY_TYPE if not flags[INPUT_TYPE_FLAGS[input_type]]]
    return {
        "artifact_type": "R5_reviewed_input_registry_promotion_result",
        "schema_version": "r5_reviewed_input_registry_promotion_result_v0.2",
        "workflow_id": workflow_id,
        "stock_code": stock_code,
        "fixture_mode": fixture_mode,
        "dry_run": dry_run,
        "no_live_api": True,
        "dropzone_root": str(dropzone_root),
        "output_run_dir": str(output_run_dir),
        "validation_status": validation_status,
        "validation_issues": validation_issues,
        "promotion_status": promotion_status,
        "registries_changed": registries_changed,
        "allowed_report_level": allowed_level,
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
        "accepted_count": len(accepted),
        "accepted_degraded_count": len(degraded),
        "accepted_input_ids": sorted(str(row.get("input_id")) for row in accepted),
        "accepted_degraded_input_ids": sorted(str(row.get("input_id")) for row in degraded),
        "reviewed_flags_from_accepted_rows": flags,
        "remaining_todos": remaining_todos,
        "registry_paths": {key: str(path) for key, path in _registry_paths(output_run_dir).items()},
        "registry_results": registry_results,
        "notes": [
            "Only review_status=accepted rows become registry facts.",
            "All intake decisions remain traceable in the evidence review ledger.",
            "Registry promotion is capped at reviewed-input research-draft level; it never opens sample-quality or P2.",
        ],
    }


def promote_reviewed_inputs(
    *,
    repo_root: Path,
    workflow_id: str,
    dropzone_root: Path,
    output_run_dir: Path,
    fixture_mode: bool,
    dry_run: bool = False,
    stock_code: str | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    dropzone_root = dropzone_root.resolve()
    output_run_dir = output_run_dir.resolve()
    records = collect_records(dropzone_root)
    validation = dropzone.validate_root(dropzone_root)
    flags = {
        flag: any(row.get("review_status") == "accepted" and row.get("input_type") == input_type for row in records)
        for input_type, flag in INPUT_TYPE_FLAGS.items()
    }
    derived_workflows = list(validation.get("unique_workflow_ids") or [])
    derived_stocks = list(validation.get("unique_stock_codes") or [])
    derived_workflow = derived_workflows[0] if len(derived_workflows) == 1 else None
    derived_stock = derived_stocks[0] if len(derived_stocks) == 1 else None
    real_run_dir = (repo_root / "reports/workflow_runs" / REAL_WORKFLOW_ID).resolve()

    boundary_reason = None
    if fixture_mode and (workflow_id == REAL_WORKFLOW_ID or output_run_dir == real_run_dir):
        boundary_reason = "fixture mode rejects the real workflow ID and committed real run directory"
    elif validation["status"] != "pass":
        boundary_reason = "dropzone validation failed"
    elif derived_workflow and derived_workflow != workflow_id:
        boundary_reason = f"CLI workflow_id {workflow_id} does not match validated rows {derived_workflow}"
    elif stock_code is not None and derived_stock and str(stock_code) != str(derived_stock):
        boundary_reason = f"CLI stock_code {stock_code} does not match validated rows {derived_stock}"

    effective_stock = str(stock_code or derived_stock) if (stock_code or derived_stock) is not None else None
    if boundary_reason:
        status = "blocked_invalid_dropzone" if validation["status"] != "pass" else "blocked_identity_or_fixture_boundary"
        return _result(
            workflow_id=workflow_id,
            stock_code=effective_stock,
            dropzone_root=dropzone_root,
            output_run_dir=output_run_dir,
            fixture_mode=fixture_mode,
            dry_run=dry_run,
            validation_status="fail",
            validation_issues=list(validation.get("issues") or [])
            + [{"issue_id": "R5PROMOTE-BOUNDARY-001", "severity": "high", "description": boundary_reason}],
            promotion_status=status,
            registry_results=_blocked_registry_results(output_run_dir, records, boundary_reason),
            records=records,
            flags=flags,
            registries_changed=False,
        )

    accepted_records = [row for row in records if row.get("review_status") == "accepted"]
    if not accepted_records:
        registry_results = {}
        for name, path in _registry_paths(output_run_dir).items():
            before_hash = registry_io.file_sha256(path)
            registry_results[name] = {
                "target_path": str(path),
                "action": "unchanged",
                "planned_action": "unchanged",
                "before_hash": before_hash,
                "after_hash": before_hash,
                "promoted_input_ids": _registry_input_ids(name, records),
                "validation": {"decision": "not_run", "issues": []},
            }
        return _result(
            workflow_id=workflow_id,
            stock_code=effective_stock,
            dropzone_root=dropzone_root,
            output_run_dir=output_run_dir,
            fixture_mode=fixture_mode,
            dry_run=dry_run,
            validation_status="pass",
            validation_issues=[],
            promotion_status="no_accepted_inputs",
            registry_results=registry_results,
            records=records,
            flags=flags,
            registries_changed=False,
        )

    conflicts: list[str] = []
    paths = _registry_paths(output_run_dir)
    market_candidate = _build_market_peer_registry(workflow_id, effective_stock or "", accepted_records, conflicts)
    market_candidate = _merge_market_peer(
        registry_io.load_yaml(paths["market_peer"]), market_candidate, workflow_id, effective_stock or "", conflicts
    )
    forecast_candidate = _build_forecast_registry(workflow_id, effective_stock or "", accepted_records, conflicts)
    forecast_candidate = _merge_forecast(
        registry_io.load_yaml(paths["forecast_assumptions"]),
        forecast_candidate,
        workflow_id,
        effective_stock or "",
        conflicts,
    )
    valuation_candidate = _build_valuation_registry(workflow_id, effective_stock or "", accepted_records)
    valuation_candidate = _merge_valuation(
        registry_io.load_yaml(paths["valuation_inputs"]),
        valuation_candidate,
        workflow_id,
        effective_stock or "",
        conflicts,
    )
    ledger_candidate = _build_evidence_ledger(workflow_id, effective_stock or "", records)
    ledger_candidate = _merge_ledger(
        registry_io.load_yaml(paths["evidence_ledger"]),
        ledger_candidate,
        workflow_id,
        effective_stock or "",
        conflicts,
    )
    candidates = {
        "market_peer": market_candidate,
        "forecast_assumptions": forecast_candidate,
        "valuation_inputs": valuation_candidate,
        "evidence_ledger": ledger_candidate,
    }

    if conflicts:
        reason = "; ".join(sorted(set(conflicts)))
        return _result(
            workflow_id=workflow_id,
            stock_code=effective_stock,
            dropzone_root=dropzone_root,
            output_run_dir=output_run_dir,
            fixture_mode=fixture_mode,
            dry_run=dry_run,
            validation_status="fail",
            validation_issues=[{"issue_id": "R5PROMOTE-CONFLICT-001", "severity": "high", "description": reason}],
            promotion_status="blocked_registry_conflict",
            registry_results=_blocked_registry_results(output_run_dir, records, reason),
            records=records,
            flags=flags,
            registries_changed=False,
        )

    registry_results: dict[str, dict[str, Any]] = {}
    candidate_bytes: dict[Path, bytes] = {}
    any_blocked = False
    for name in REGISTRY_FILENAMES:
        path = paths[name]
        payload_bytes = registry_io.dump_yaml_bytes(candidates[name])
        validation_result = _validate_candidate(name, candidates[name], repo_root)
        before_hash = registry_io.file_sha256(path)
        planned = registry_io.planned_action(path, payload_bytes)
        candidate_hash = registry_io.sha256_bytes(payload_bytes)
        if validation_result["decision"] == "blocked":
            any_blocked = True
        candidate_bytes[path] = payload_bytes
        registry_results[name] = {
            "target_path": str(path),
            "action": "blocked" if validation_result["decision"] == "blocked" else "unchanged",
            "planned_action": planned,
            "before_hash": before_hash,
            "after_hash": candidate_hash,
            "promoted_input_ids": _registry_input_ids(name, records),
            "validation": validation_result,
        }

    if any_blocked:
        for item in registry_results.values():
            item["action"] = "blocked"
            item["after_hash"] = item["before_hash"]
        return _result(
            workflow_id=workflow_id,
            stock_code=effective_stock,
            dropzone_root=dropzone_root,
            output_run_dir=output_run_dir,
            fixture_mode=fixture_mode,
            dry_run=dry_run,
            validation_status="fail",
            validation_issues=[issue for item in registry_results.values() for issue in item["validation"].get("issues", [])],
            promotion_status="blocked_candidate_validation",
            registry_results=registry_results,
            records=records,
            flags=flags,
            registries_changed=False,
        )

    if dry_run:
        return _result(
            workflow_id=workflow_id,
            stock_code=effective_stock,
            dropzone_root=dropzone_root,
            output_run_dir=output_run_dir,
            fixture_mode=fixture_mode,
            dry_run=True,
            validation_status="pass",
            validation_issues=[],
            promotion_status="dry_run_ready",
            registry_results=registry_results,
            records=records,
            flags=flags,
            registries_changed=False,
        )

    output_run_dir.mkdir(parents=True, exist_ok=True)
    try:
        registry_io.commit_registry_bytes(candidate_bytes)
    except Exception as exc:  # noqa: BLE001
        reason = f"atomic registry commit failed and was rolled back: {exc}"
        blocked = _blocked_registry_results(output_run_dir, records, reason)
        return _result(
            workflow_id=workflow_id,
            stock_code=effective_stock,
            dropzone_root=dropzone_root,
            output_run_dir=output_run_dir,
            fixture_mode=fixture_mode,
            dry_run=False,
            validation_status="fail",
            validation_issues=[{"issue_id": "R5PROMOTE-COMMIT-001", "severity": "high", "description": reason}],
            promotion_status="blocked_atomic_commit",
            registry_results=blocked,
            records=records,
            flags=flags,
            registries_changed=False,
        )

    changed = False
    for name, item in registry_results.items():
        item["action"] = item["planned_action"]
        item["after_hash"] = registry_io.file_sha256(paths[name])
        changed = changed or item["action"] in {"created", "updated"}
    return _result(
        workflow_id=workflow_id,
        stock_code=effective_stock,
        dropzone_root=dropzone_root,
        output_run_dir=output_run_dir,
        fixture_mode=fixture_mode,
        dry_run=False,
        validation_status="pass",
        validation_issues=[],
        promotion_status="accepted_inputs_promoted" if changed else "accepted_inputs_unchanged",
        registry_results=registry_results,
        records=records,
        flags=flags,
        registries_changed=changed,
    )


def build_promotion_result(
    *,
    repo_root: Path,
    workflow_id: str,
    dropzone_root: Path | None = None,
) -> dict[str, Any]:
    """Backward-compatible wrapper used by Patch 53 tests and callers."""

    repo_root = repo_root.resolve()
    actual_dropzone_root = dropzone_root or repo_root / "data/reviewed_inputs" / workflow_id
    return promote_reviewed_inputs(
        repo_root=repo_root,
        workflow_id=workflow_id,
        stock_code=None,
        dropzone_root=actual_dropzone_root,
        output_run_dir=repo_root / "reports/workflow_runs" / workflow_id,
        fixture_mode=False,
        dry_run=False,
    )


def write_result(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        path.write_bytes(registry_io.dump_yaml_bytes(payload))


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    """Compatibility alias for earlier callers."""

    write_result(path, payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote accepted R5 reviewed inputs to physical registries.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--workflow-id", default=WORKFLOW_ID)
    parser.add_argument("--stock-code")
    parser.add_argument("--dropzone-root", type=Path)
    parser.add_argument("--output-run-dir", type=Path)
    parser.add_argument("--fixture-mode", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", type=Path, required=True, help="Promotion result path; JSON or YAML by suffix.")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    dropzone_root = (args.dropzone_root or repo_root / "data/reviewed_inputs" / args.workflow_id).resolve()
    output_run_dir = (
        args.output_run_dir or repo_root / "reports/workflow_runs" / args.workflow_id
    ).resolve()
    result = promote_reviewed_inputs(
        repo_root=repo_root,
        workflow_id=args.workflow_id,
        stock_code=args.stock_code,
        dropzone_root=dropzone_root,
        output_run_dir=output_run_dir,
        fixture_mode=args.fixture_mode,
        dry_run=args.dry_run,
    )
    write_result(args.json, result)
    print(
        "r5_reviewed_input_promotion_status={status} registries_changed={changed} "
        "allowed_report_level={level} accepted={accepted} accepted_degraded={degraded}".format(
            status=result["promotion_status"],
            changed=str(result["registries_changed"]).lower(),
            level=result["allowed_report_level"],
            accepted=result["accepted_count"],
            degraded=result["accepted_degraded_count"],
        )
    )
    return 0 if result["validation_status"] == "pass" and "blocked" not in result["promotion_status"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
