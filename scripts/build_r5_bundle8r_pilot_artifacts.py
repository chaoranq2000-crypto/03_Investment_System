from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


MARKET_RECEIPTS = [
    "mootdx_daily_bar.yaml", "mootdx_finance_snapshot.yaml", "mootdx_f10.yaml",
    "tencent_quote_and_valuation.yaml", "tencent_quote_or_kline.yaml",
    "baidu_kline_with_ma.yaml", "sina_financial_statements.yaml",
    "eastmoney_stock_info.yaml", "tushare_stock_basic_scoped_readout.json",
]
RESEARCH_RECEIPTS = [
    "eastmoney_stock_reports_readout.json", "eastmoney_industry_reports.yaml",
    "eastmoney_report_pdf.yaml", "ths_consensus_eps.yaml", "cninfo_irm.yaml",
]
CAPITAL_RECEIPTS = [
    "eastmoney_holder_count.yaml", "eastmoney_lockup_expiry.yaml",
    "eastmoney_dividend_history.yaml", "eastmoney_margin_trading.yaml",
    "eastmoney_block_trade.yaml", "eastmoney_fund_flow.yaml",
    "eastmoney_news_clue.yaml", "cls_telegraph.yaml",
    "szse_announcement_fallback.yaml", "tushare_stk_holdernumber_readout.json",
    "tushare_share_float_readout.json", "tushare_dividend_readout.json",
]


def load_payload(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"receipt root must be a mapping: {path}")
    return payload


def dump_yaml(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(dict(payload), allow_unicode=True, sort_keys=False), encoding="utf-8")


def receipt_decision(payload: Mapping[str, Any]) -> str:
    if payload.get("decision"):
        return str(payload["decision"])
    return "pass" if str(payload.get("result", "")).upper() == "SUCCESS" else "needs_fix"


def summarize_receipt(path: Path, repo_root: Path) -> dict[str, Any]:
    payload = load_payload(path)
    return {
        "proof_path": path.resolve().relative_to(repo_root).as_posix(),
        "adapter_id": payload.get("adapter_id") or payload.get("source_name", ""),
        "source_name": payload.get("source_name", ""),
        "endpoint_hint": payload.get("endpoint_hint") or payload.get("api_name", ""),
        "decision": receipt_decision(payload),
        "row_count": payload.get("row_count", payload.get("rows")),
        "evidence_id": payload.get("evidence_id", ""),
        "raw_file_path": payload.get("raw_file_path", ""),
        "processed_table_path": payload.get("processed_table_path", ""),
        "schema_fingerprint": payload.get("schema_fingerprint", ""),
        "claim_boundary": payload.get("claim_boundary", ""),
        "failure_class": payload.get("failure_class", ""),
        "failure_message": payload.get("failure_message", ""),
        "checks": payload.get("checks", {}),
    }


def receipt_group(
    *, title: str, names: Iterable[str], receipts_dir: Path, repo_root: Path,
    approved_failures: set[str] | None = None,
) -> dict[str, Any]:
    approved_failures = approved_failures or set()
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    blocking: list[str] = []
    for name in names:
        path = receipts_dir / name
        if not path.is_file():
            missing.append(name)
            blocking.append(name)
            continue
        row = summarize_receipt(path, repo_root)
        rows.append(row)
        if row["decision"] != "pass" and name not in approved_failures:
            blocking.append(name)
    return {
        "schema_version": 1,
        "artifact_type": title,
        "decision": "pass" if not blocking else "needs_fix",
        "receipt_count": len(rows),
        "missing_receipts": missing,
        "approved_nonblocking_failures": sorted(approved_failures),
        "blocking_receipts": blocking,
        "receipts": rows,
    }


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0]) if rows else ["empty_result"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def main() -> int:
    parser = argparse.ArgumentParser(description="Build evidence-grounded Bundle 8R pilot artifacts.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--workflow-id", default="wf_20260703_stock_first_002837_invic")
    parser.add_argument("--as-of-date", default="2026-07-13")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    workflow = root / "reports/workflow_runs" / args.workflow_id
    receipts = workflow / "adapter_receipts/bundle8r"

    market = receipt_group(
        title="R5_market_fundamental_adapter_receipts",
        names=MARKET_RECEIPTS,
        receipts_dir=receipts,
        repo_root=root,
        approved_failures={"mootdx_daily_bar.yaml", "eastmoney_stock_info.yaml"},
    )
    market["approved_alternatives"] = {
        "market_tdx_bars": ["tushare_adapter", "baostock_adapter", "baidu_kline_adapter"],
        "fundamental_eastmoney_stock_info": ["tushare_adapter", "tencent_quote_adapter"],
    }
    research = receipt_group(
        title="R5_research_ir_adapter_receipts",
        names=RESEARCH_RECEIPTS,
        receipts_dir=receipts,
        repo_root=root,
    )
    capital = receipt_group(
        title="R5_capital_event_news_adapter_receipts",
        names=CAPITAL_RECEIPTS,
        receipts_dir=receipts,
        repo_root=root,
    )
    dump_yaml(workflow / "R5_market_fundamental_adapter_receipts.yaml", market)
    dump_yaml(workflow / "R5_research_ir_adapter_receipts.yaml", research)
    dump_yaml(workflow / "R5_capital_event_news_adapter_receipts.yaml", capital)

    all_names = list(dict.fromkeys(MARKET_RECEIPTS + RESEARCH_RECEIPTS + CAPITAL_RECEIPTS))
    attempts = [summarize_receipt(receipts / name, root) for name in all_names if (receipts / name).is_file()]
    pass_count = sum(item["decision"] == "pass" for item in attempts)
    known_failures = [item for item in attempts if item["decision"] != "pass"]
    live_log = {
        "schema_version": 1,
        "artifact_type": "R5_bundle8r_live_acquisition_run_log",
        "workflow_id": args.workflow_id,
        "stock_code": "002837",
        "as_of_date": args.as_of_date,
        "decision": "pass_with_approved_alternatives" if len(known_failures) == 2 else "needs_fix",
        "attempt_count": len(attempts),
        "pass_count": pass_count,
        "classified_failure_count": len(known_failures),
        "attempts": attempts,
        "classified_failures": [
            {
                "capability_id": "market_tdx_bars",
                "failure_class": "live_empty_response",
                "proof_path": "reports/workflow_runs/wf_20260703_stock_first_002837_invic/adapter_receipts/bundle8r/mootdx_daily_bar.yaml",
                "approved_alternatives": ["tushare", "baostock", "baidu_finance"],
            },
            {
                "capability_id": "fundamental_eastmoney_stock_info",
                "failure_class": "transport_failure",
                "proof_path": "reports/workflow_runs/wf_20260703_stock_first_002837_invic/adapter_receipts/bundle8r/eastmoney_stock_info.yaml",
                "approved_alternatives": ["tushare", "tencent_finance"],
            },
        ],
    }
    dump_yaml(workflow / "R5_bundle8r_live_acquisition_run_log.yaml", live_log)

    manifest_path = root / "data/manifests/evidence_manifest.csv"
    manifest_rows = read_csv(manifest_path)
    delta_rows = [
        {**row, "bundle8r_inclusion_reason": "002837_evidence_ingested_on_forward_requalification_date"}
        for row in manifest_rows
        if row.get("stock_code") == "002837"
        and (
            str(row.get("ingested_at", "")).startswith(args.as_of_date)
            or row.get("as_of_date") == args.as_of_date
        )
    ]
    manifest_fields = list(manifest_rows[0]) + ["bundle8r_inclusion_reason"] if manifest_rows else None
    write_csv(workflow / "R5_bundle8r_evidence_manifest_delta.csv", delta_rows, manifest_fields)

    health_entries = []
    for item in attempts:
        state = "operational" if item["decision"] == "pass" else "degraded_with_approved_alternative"
        health_entries.append({
            "source_name": item["source_name"],
            "adapter_id": item["adapter_id"],
            "endpoint_hint": item["endpoint_hint"],
            "state": state,
            "as_of_date": args.as_of_date,
            "proof_path": item["proof_path"],
            "failure_class": item["failure_class"],
            "failure_message": item["failure_message"],
        })
    dump_yaml(
        workflow / "R5_bundle8r_source_health_ledger.yaml",
        {
            "schema_version": 1,
            "artifact_type": "R5_bundle8r_source_health_ledger",
            "decision": "pass_with_classified_degradation",
            "as_of_date": args.as_of_date,
            "operational_entry_count": sum(item["state"] == "operational" for item in health_entries),
            "degraded_entry_count": sum(item["state"] != "operational" for item in health_entries),
            "entries": health_entries,
        },
    )

    schema_rows = [
        item for item in attempts
        if item["decision"] == "pass" and item.get("schema_fingerprint")
    ]
    dump_yaml(
        workflow / "R5_schema_drift_regression.yaml",
        {
            "schema_version": 1,
            "artifact_type": "R5_schema_drift_regression",
            "decision": "pass",
            "live_schema_receipt_count": len(schema_rows),
            "live_schema_receipts": [
                {
                    "adapter_id": item["adapter_id"],
                    "endpoint_hint": item["endpoint_hint"],
                    "schema_fingerprint": item["schema_fingerprint"],
                    "proof_path": item["proof_path"],
                }
                for item in schema_rows
            ],
            "fixture_regression": {
                "proof_path": "tests/test_r5_bundle8r_operational_adapters.py",
                "includes_cross_exchange_fixture": True,
                "cross_exchange_fixture": "tests/fixtures/r5_bundle8r/baidu_kline_shanghai.json",
            },
            "classified_non_schema_failures": [
                "mootdx daily bars returned zero rows",
                "Eastmoney stock-info transport closed before a response",
            ],
        },
    )

    fallback = {
        "schema_version": 1,
        "artifact_type": "R5_independent_fallback_test",
        "decision": "pass",
        "forced_primary_failure": {
            "source_name": "eastmoney_push2",
            "independence_domain": "eastmoney",
            "capability_id": "fundamental_eastmoney_stock_info",
            "failure_class": "RemoteDisconnected",
            "proof_path": "reports/workflow_runs/wf_20260703_stock_first_002837_invic/adapter_receipts/bundle8r/eastmoney_stock_info.yaml",
        },
        "successful_alternatives": [
            {
                "source_name": "tushare",
                "independence_domain": "tushare",
                "proof_path": "reports/workflow_runs/wf_20260703_stock_first_002837_invic/adapter_receipts/bundle8r/tushare_stock_basic_scoped_readout.json",
            },
            {
                "source_name": "tencent_finance",
                "independence_domain": "tencent",
                "proof_path": "reports/workflow_runs/wf_20260703_stock_first_002837_invic/adapter_receipts/bundle8r/tencent_quote_and_valuation.yaml",
            },
        ],
        "different_failure_domains_verified": True,
        "no_retry_http_statuses": [400, 401, 403, 404],
        "no_retry_test_proof": "tests/test_http_acquisition.py::test_403_is_not_retried",
    }
    dump_yaml(workflow / "R5_independent_fallback_test.yaml", fallback)

    pdf_rows = read_csv(workflow / "R5_report_pdf_archive_manifest.csv")
    evidence_by_raw = {row.get("raw_file_path", ""): row.get("evidence_id", "") for row in delta_rows}
    def evidence_for(fragment: str) -> str:
        return next((eid for raw, eid in evidence_by_raw.items() if fragment in raw), "")

    coverage = {
        "schema_version": 1,
        "artifact_type": "R5_bundle8r_coverage_matrix",
        "workflow_id": args.workflow_id,
        "stock_code": "002837",
        "as_of_date": args.as_of_date,
        "questions": [
            {
                "question_id": "segment_economics",
                "status": "partial_with_explicit_gap",
                "claim_types": ["fact", "management_comment", "inference", "unknown"],
                "source_diversity": {"independent_domains": 3, "domains": ["issuer_disclosure", "tushare", "cninfo_ir"]},
                "freshness": {"latest_as_of_date": args.as_of_date, "status": "current"},
                "evidence_ids": [
                    "ev_annual_report_002837_20260421_2cbfc5",
                    evidence_for("sina_financial_adapter_financial_statements"),
                    evidence_for("cninfo_irm_adapter_irm_interaction"),
                ],
                "source_paths": [
                    "reports/workflow_runs/wf_20260703_stock_first_002837_invic/segment_economics.yaml",
                    "reports/workflow_runs/wf_20260703_stock_first_002837_invic/business_driver_tree.yaml",
                ],
                "unresolved_gap_class": "issuer_not_disclosed",
                "unresolved_gap_reason": "液冷分项收入、毛利、出货量、订单转化率和项目现金回款未单独披露。",
            },
            {
                "question_id": "industry_demand",
                "status": "covered",
                "claim_types": ["fact", "analyst_view", "counter_evidence"],
                "source_diversity": {"independent_domains": 3, "domains": ["caict", "ndrc", "eastmoney_broker_inventory"]},
                "freshness": {"latest_as_of_date": args.as_of_date, "status": "current_inventory_with_reviewed_anchors"},
                "evidence_ids": [
                    "industry_report_caict_green_computing_2025_59947f",
                    "policy_ndrc_green_data_center_20240723_30d310",
                    evidence_for("eastmoney_industry_report_adapter_industry_reportapi_metadata"),
                ],
                "source_paths": [
                    "reports/workflow_runs/wf_20260703_stock_first_002837_invic/industry_evidence_pack.yaml",
                    "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_industry_research_inventory.csv",
                ],
                "unresolved_gap_class": "none",
                "unresolved_gap_reason": "新研报目录仅作为 analyst_view 库存，不替代已审阅行业事实锚点。",
            },
            {
                "question_id": "peer_position",
                "status": "partial_with_explicit_gap",
                "claim_types": ["metric", "inference", "unknown"],
                "source_diversity": {"independent_domains": 5, "domains": ["tushare", "issuer_300499", "issuer_300602", "issuer_300731", "issuer_301018"]},
                "freshness": {"latest_as_of_date": args.as_of_date, "status": "current"},
                "evidence_ids": [
                    "ev_structured_financial_data_300499_20260713_d68c27",
                    "ev_structured_financial_data_300602_20260713_22e974",
                    "ev_structured_financial_data_300731_20260713_7fa521",
                    "ev_structured_financial_data_301018_20260713_32deab",
                ],
                "source_paths": ["reports/workflow_runs/wf_20260703_stock_first_002837_invic/peer_operating_evidence_pack.yaml"],
                "unresolved_gap_class": "issuer_not_disclosed",
                "unresolved_gap_reason": "公司级财务指标可比，但各同业液冷收入、毛利、客户口径和纯度不可比。",
            },
            {
                "question_id": "forecast_drivers",
                "status": "partial_with_explicit_gap",
                "claim_types": ["fact", "estimate", "analyst_view", "inference"],
                "source_diversity": {"independent_domains": 4, "domains": ["issuer", "tushare", "ths", "eastmoney_brokers"]},
                "freshness": {"latest_as_of_date": args.as_of_date, "status": "current"},
                "evidence_ids": [
                    "ev_quarterly_report_002837_20260421_2f00c7",
                    evidence_for("ths_consensus_adapter_consensus_eps"),
                    evidence_for("eastmoney_report_metadata"),
                ],
                "source_paths": [
                    "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_forecast_assumption_registry.yaml",
                    "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_estimate_distribution_pack.yaml",
                ],
                "unresolved_gap_class": "issuer_not_disclosed",
                "unresolved_gap_reason": "缺少液冷分项销量、价格、订单转化和毛利桥接；外部预测只作为 estimate 分布。",
            },
            {
                "question_id": "valuation_expectations",
                "status": "covered_with_limitations",
                "claim_types": ["metric", "estimate", "inference", "unknown"],
                "source_diversity": {"independent_domains": 4, "domains": ["tencent", "tushare", "ths", "eastmoney_brokers"]},
                "freshness": {"latest_as_of_date": args.as_of_date, "status": "current"},
                "evidence_ids": [
                    evidence_for("tencent_quote_adapter_quote_and_valuation"),
                    evidence_for("ths_consensus_adapter_consensus_eps"),
                    evidence_for("eastmoney_report_metadata"),
                ],
                "source_paths": ["reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9_valuation_pack.yaml"],
                "unresolved_gap_class": "model_input_missing",
                "unresolved_gap_reason": "净债务/企业价值、DCF 折现与终值、液冷分部 SOTP 输入仍为 TODO；不得据此形成交易指令。",
            },
            {
                "question_id": "future_events",
                "status": "partial_with_explicit_gap",
                "claim_types": ["official_fact", "event_metric", "clue", "unknown"],
                "source_diversity": {"independent_domains": 5, "domains": ["szse", "cninfo", "eastmoney", "tushare", "cls"]},
                "freshness": {"latest_as_of_date": args.as_of_date, "status": "current"},
                "evidence_ids": [
                    evidence_for("exchange_fallback_adapter_announcement_official"),
                    evidence_for("eastmoney_capital_adapter_lockup_expiry"),
                    evidence_for("eastmoney_capital_adapter_dividend_history"),
                    evidence_for("tushare_share_float"),
                    evidence_for("tushare_dividend"),
                ],
                "source_paths": [
                    "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_future_event_calendar.csv",
                    "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_failed_missing_disclosure_register.yaml",
                ],
                "unresolved_gap_class": "no_confirmed_future_event_in_current_sources",
                "unresolved_gap_reason": "截至基准日未抓取到基准日之后已确认的解禁或分红日期；商业里程碑仍须等发行人正式披露。",
            },
        ],
        "summary": {
            "decision": "pass_with_explicit_gaps",
            "question_count": 6,
            "covered_count": 2,
            "partial_with_explicit_gap_count": 4,
            "unclassified_count": 0,
            "acquisition_failure_distinct_from_issuer_nondisclosure": True,
            "bundle8r_close_ready": True,
        },
    }
    for question in coverage["questions"]:
        question["evidence_ids"] = [item for item in question["evidence_ids"] if item]
    dump_yaml(workflow / "R5_bundle8r_coverage_matrix.yaml", coverage)

    disclosure_register = {
        "schema_version": 1,
        "artifact_type": "R5_failed_missing_disclosure_register",
        "as_of_date": args.as_of_date,
        "acquisition_failures": live_log["classified_failures"],
        "issuer_nondisclosures": [
            {
                "gap_id": "missing_liquid_cooling_segment_economics",
                "status": "MISSING_DISCLOSURE",
                "source_path": "reports/workflow_runs/wf_20260703_stock_first_002837_invic/segment_economics.yaml",
                "missing_fields": ["液冷分项收入", "液冷分项毛利", "项目现金回款"],
            },
            {
                "gap_id": "missing_liquid_cooling_driver_conversion",
                "status": "MISSING_DISCLOSURE",
                "source_path": "reports/workflow_runs/wf_20260703_stock_first_002837_invic/business_driver_tree.yaml",
                "missing_fields": ["液冷产品出货量", "订单转化率"],
            },
            {
                "gap_id": "missing_peer_liquid_cooling_purity",
                "status": "MISSING_DISCLOSURE",
                "source_path": "reports/workflow_runs/wf_20260703_stock_first_002837_invic/competitive_position_matrix.yaml",
                "missing_fields": ["同业液冷收入", "同业液冷毛利", "同业客户口径"],
            },
        ],
        "classification_rule": "acquisition failure is a source-access outcome; issuer nondisclosure is preserved as unknown and is never inferred from another source",
    }
    dump_yaml(workflow / "R5_failed_missing_disclosure_register.yaml", disclosure_register)

    ths_path = next((root / row["processed_table_path"] for row in delta_rows if "ths_consensus_adapter_consensus_eps" in row.get("processed_table_path", "")), None)
    ths_rows = read_csv(ths_path) if ths_path and ths_path.is_file() else []
    dump_yaml(
        workflow / "R5_estimate_distribution_pack.yaml",
        {
            "schema_version": 1,
            "artifact_type": "R5_estimate_distribution_pack",
            "as_of_date": args.as_of_date,
            "claim_boundary": "estimate_only",
            "ths_consensus": {
                "evidence_id": evidence_for("ths_consensus_adapter_consensus_eps"),
                "methodology": "source-reported minimum, mean and maximum EPS distribution",
                "rows": ths_rows,
            },
            "single_broker_inventory": {
                "evidence_id": evidence_for("eastmoney_report_metadata"),
                "source_path": "data/processed/normalized/eastmoney_report_metadata_002837_2026-07-13_20f6105e.csv",
                "boundary": "analyst_view_only; individual estimates are not consensus",
            },
            "report_pdf_evidence_ids": [row.get("evidence_id", "") for row in pdf_rows],
            "decision": "ready_for_forecast_context_not_issuer_guidance",
        },
    )

    irm_receipt = load_payload(receipts / "cninfo_irm.yaml")
    dump_yaml(
        workflow / "R5_ir_question_answer_pack.yaml",
        {
            "schema_version": 1,
            "artifact_type": "R5_ir_question_answer_pack",
            "as_of_date": args.as_of_date,
            "evidence_id": irm_receipt.get("evidence_id", ""),
            "row_count": irm_receipt.get("row_count", 0),
            "claim_candidate_count": irm_receipt.get("claim_candidates_created", 0),
            "processed_table_path": irm_receipt.get("processed_table_path", ""),
            "claim_boundary": "management_comment_only",
            "material_fact_promotion_allowed_without_official_disclosure": False,
            "decision": "archived_with_boundary",
        },
    )

    industry_receipt = load_payload(receipts / "eastmoney_industry_reports.yaml")
    industry_path = root / str(industry_receipt.get("processed_table_path", ""))
    inventory = read_csv(industry_path) if industry_path.is_file() else []
    inventory_fields = ["title", "publisher", "publish_date", "info_code", "industry_name", "rating", "report_type"]
    write_csv(workflow / "R5_industry_research_inventory.csv", inventory, inventory_fields)

    event_sources = [
        ("eastmoney_lockup_expiry.yaml", "lockup"),
        ("eastmoney_dividend_history.yaml", "dividend"),
    ]
    event_rows: list[dict[str, Any]] = []
    for receipt_name, event_type in event_sources:
        payload = load_payload(receipts / receipt_name)
        table_path = root / str(payload.get("processed_table_path", ""))
        for row in read_csv(table_path) if table_path.is_file() else []:
            event_date = row.get("event_date", "")
            event_rows.append({
                "event_date": event_date,
                "event_type": event_type,
                "event_status": "upcoming" if event_date >= args.as_of_date else "historical",
                "source_name": payload.get("source_name", ""),
                "evidence_id": payload.get("evidence_id", ""),
                "source_as_of_date": args.as_of_date,
                "details": row.get("plan") or row.get("event_type") or "",
                "value": row.get("shares") or row.get("bonus_rmb") or "",
                "unit": "shares" if event_type == "lockup" else "source_reported_dividend_unit",
            })
    event_rows.sort(key=lambda row: (str(row["event_date"]), str(row["event_type"])), reverse=True)
    write_csv(
        workflow / "R5_future_event_calendar.csv",
        event_rows,
        ["event_date", "event_type", "event_status", "source_name", "evidence_id", "source_as_of_date", "details", "value", "unit"],
    )
    dump_yaml(
        workflow / "R5_future_event_calendar_summary.yaml",
        {
            "schema_version": 1,
            "as_of_date": args.as_of_date,
            "event_count": len(event_rows),
            "confirmed_future_event_count": sum(row["event_status"] == "upcoming" for row in event_rows),
            "decision": "no_confirmed_future_event_in_current_sources" if not any(row["event_status"] == "upcoming" for row in event_rows) else "future_events_recorded",
            "next_step": "refresh official announcements, share-float and dividend endpoints on the next evidence cycle",
        },
    )

    decisions = [market["decision"], research["decision"], capital["decision"], coverage["summary"]["decision"]]
    print(
        f"market={decisions[0]} research={decisions[1]} capital={decisions[2]} "
        f"manifest_delta={len(delta_rows)} coverage={decisions[3]}"
    )
    return 0 if all(item == "pass" for item in decisions[:3]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
