from __future__ import annotations

import argparse
import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


DEFAULT_WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
PEER_FIELD_MAP = {
    "total_revenue": ("income", "total_revenue"),
    "net_profit_attributable": ("income", "n_income_attr_p"),
    "gross_margin": ("indicator", "grossprofit_margin"),
    "net_profit_margin": ("indicator", "netprofit_margin"),
    "roe_diluted": ("indicator", "roe_dt"),
    "debt_to_assets": ("indicator", "debt_to_assets"),
    "net_operating_cash_flow": ("cashflow", "n_cashflow_act"),
    "accounts_receivable": ("balance", "accounts_receiv"),
    "inventories": ("balance", "inventories"),
}


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"YAML must be a mapping: {path}")
    return payload


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _decimal_equal(left: object, right: object) -> bool:
    try:
        return Decimal(str(left)) == Decimal(str(right))
    except (InvalidOperation, ValueError):
        return False


def validate_bundle8b(repo_root: Path, workflow_id: str = DEFAULT_WORKFLOW_ID) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    run = repo_root / "reports/workflow_runs" / workflow_id
    errors: list[str] = []
    checks: dict[str, Any] = {}

    log = _load_yaml(run / "live_acquisition_run_log.yaml")
    delta = _read_csv(run / "R5_bundle8b_evidence_manifest_delta.csv")
    manifest = _read_csv(repo_root / "data/manifests/evidence_manifest.csv")
    manifest_by_id = {row["evidence_id"]: row for row in manifest}
    delta_ids = [row["evidence_id"] for row in delta]
    expected_delta = int(log["summary"]["evidence_manifest_rows_created"])
    if len(delta) != expected_delta:
        errors.append(f"delta rows {len(delta)} != expected {expected_delta}")
    if len(set(delta_ids)) != len(delta_ids):
        errors.append("delta evidence ids are not unique")
    missing_global = sorted(set(delta_ids) - set(manifest_by_id))
    if missing_global:
        errors.append(f"delta ids missing from global manifest: {missing_global}")
    missing_paths: list[str] = []
    for row in delta:
        for field in ("raw_file_path", "processed_text_path", "processed_table_path", "page_map_path"):
            value = row.get(field, "")
            if value and not (repo_root / value).exists():
                missing_paths.append(f"{row['evidence_id']}:{field}:{value}")
    if missing_paths:
        errors.append(f"missing evidence paths: {missing_paths}")
    checks["evidence_delta"] = {
        "rows": len(delta),
        "unique_ids": len(set(delta_ids)),
        "missing_global_ids": len(missing_global),
        "missing_paths": len(missing_paths),
    }

    health = _load_yaml(repo_root / "data/manifests/source_health_ledger.yaml")
    expected_health = {
        "tushare": "healthy",
        "baostock": "healthy",
        "cninfo": "healthy",
        "eastmoney_push2": "degraded",
        "tencent_finance": "healthy",
        "szse": "healthy",
    }
    observed_health = {
        source: health.get("sources", {}).get(source, {}).get("state")
        for source in expected_health
    }
    if observed_health != expected_health:
        errors.append(f"source health mismatch: {observed_health}")
    checks["source_health"] = observed_health

    peer_pack = _load_yaml(run / "peer_operating_evidence_pack.yaml")
    peer_metric_checks = 0
    for company in peer_pack.get("companies", []):
        if not isinstance(company, Mapping):
            errors.append("peer company entry is not a mapping")
            continue
        source_ids = company.get("source_evidence_ids", {})
        metrics = company.get("metrics", {})
        for metric_name, (source_key, source_field) in PEER_FIELD_MAP.items():
            evidence_id_value = str(source_ids.get(source_key, ""))
            manifest_row = manifest_by_id.get(evidence_id_value)
            if not manifest_row:
                errors.append(f"missing manifest row for peer source {evidence_id_value}")
                continue
            table_path = repo_root / manifest_row["processed_table_path"]
            rows = _read_csv(table_path)
            source_row = next((row for row in rows if row.get("end_date") == "20251231"), None)
            if source_row is None:
                errors.append(f"2025 row missing in {table_path}")
                continue
            metric_payload = metrics.get(metric_name, {})
            observed = metric_payload.get("value") if isinstance(metric_payload, Mapping) else None
            if not _decimal_equal(observed, source_row.get(source_field)):
                errors.append(
                    f"peer metric mismatch {company.get('stock_code')} {metric_name}: "
                    f"{observed} != {source_row.get(source_field)}"
                )
            if not isinstance(metric_payload, Mapping) or not metric_payload.get("unit"):
                errors.append(f"peer metric unit missing {company.get('stock_code')} {metric_name}")
            peer_metric_checks += 1
    checks["peer_metrics"] = {
        "companies": len(peer_pack.get("companies", [])),
        "metrics_checked": peer_metric_checks,
    }

    gaps = _load_yaml(run / "liquid_cooling_disclosure_gap_register.yaml")
    gap_by_id = {row["gap_id"]: row for row in gaps.get("gap_register", [])}
    revenue_gap = gap_by_id.get("LC-DISC-REV-2024", {})
    if revenue_gap.get("classification") != "B_approximate_or_computable_proxy":
        errors.append("2024 liquid-cooling revenue must remain category B")
    if not _decimal_equal(revenue_gap.get("value"), "300000000"):
        errors.append("2024 liquid-cooling approximate revenue is not 300000000 CNY")
    if revenue_gap.get("claim_type") != "management_comment":
        errors.append("2024 liquid-cooling approximate revenue is not management_comment")
    evidence_path = repo_root / str(revenue_gap.get("source_path", ""))
    source_text = evidence_path.read_text(encoding="utf-8") if evidence_path.exists() else ""
    if "液冷技术相关营业收入" not in source_text or "约 3" not in source_text:
        errors.append("2024 liquid-cooling source text does not contain the cited approximate disclosure")
    required_missing = {"LC-DISC-REV-2025", "LC-DISC-GM", "LC-DISC-ORDERS", "LC-DISC-CUSTOMERS", "LC-DISC-CASH-COLLECTION"}
    for gap_id in required_missing:
        if gap_by_id.get(gap_id, {}).get("status") != "MISSING_DISCLOSURE":
            errors.append(f"{gap_id} must remain MISSING_DISCLOSURE")
    checks["liquid_cooling_boundary"] = {
        "2024_revenue_classification": revenue_gap.get("classification"),
        "visible_missing_items": len(required_missing),
    }

    event_pack = _load_yaml(run / "market_event_pack.yaml")
    events = event_pack.get("future_event_calendar", [])
    event = events[0] if events else {}
    event_evidence = manifest_by_id.get(str(event.get("source_evidence_id", "")), {})
    event_path = repo_root / str(event_evidence.get("processed_table_path", ""))
    event_rows = _read_csv(event_path) if event_path.exists() else []
    event_source_row = next((row for row in event_rows if row.get("end_date") == "20260630"), {})
    if event.get("planned_date", "").replace("-", "") != event_source_row.get("pre_date"):
        errors.append("future event planned date does not match Tushare disclosure_date snapshot")
    for field in ("technical_snapshot_path", "valuation_snapshot_path"):
        path_value = event_pack.get("market_state", {}).get(field, "")
        if not path_value or not (repo_root / path_value).exists():
            errors.append(f"market event pack path missing: {field}={path_value}")
    checks["market_event"] = {
        "planned_date": event.get("planned_date"),
        "source_pre_date": event_source_row.get("pre_date"),
        "actual_date": event.get("actual_date"),
    }

    return {
        "artifact_type": "R5_bundle8b_close_input_validation",
        "schema_version": "v0.1",
        "workflow_id": workflow_id,
        "decision": "pass" if not errors else "fail",
        "checks": checks,
        "errors": errors,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Bundle 8B close inputs against evidence.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--workflow-id", default=DEFAULT_WORKFLOW_ID)
    parser.add_argument("--output", default="")
    args = parser.parse_args(argv)
    payload = validate_bundle8b(Path(args.repo_root), args.workflow_id)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
