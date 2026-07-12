#!/usr/bin/env python3
"""Build Bundle 5.2 reviewed disclosure records and candidate core subpacks."""
from __future__ import annotations

import argparse
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
STOCK_CODE = "002837"
ANNUAL_EVIDENCE_ID = "ev_annual_report_002837_20260421_2cbfc5"
INTERIM_EVIDENCE_ID = "ev_interim_report_002837_20250819_47054e"
Q1_EVIDENCE_ID = "ev_quarterly_report_002837_20260421_2f00c7"

EXPECTED_SOURCES = {
    ANNUAL_EVIDENCE_ID: {
        "path": "data/raw/annual_reports/cninfo_2025_annual_report_full_002837_2026-04-21.pdf",
        "sha256": "2cbfc5dc8a60b01212b68d930fb06d0a25bd74563cd1942bd87161246c3a1472",
        "pages": 196,
    },
    INTERIM_EVIDENCE_ID: {
        "path": "data/raw/announcements/cninfo_2025_interim_report_full_002837_2025-08-19.pdf",
        "sha256": "47054e736c74130385e4cab67f04708599c4bae0df5599b4446614039b3f0ffb",
        "pages": 162,
    },
    Q1_EVIDENCE_ID: {
        "path": "data/raw/announcements/szse_2026_q1_report_002837_2026-04-21.pdf",
        "sha256": "2f00c78f33e04ee476f633e57ca74de635f090a91e7c238b2251e5f1b19abd5c",
        "pages": 11,
    },
}

PRODUCT_ROWS = [
    ("room_cooling", "机房温控节能产品", 3_448_477_492.62, 56.83, 2_470_650_226.09, 28.36),
    ("cabinet_cooling", "机柜温控节能产品", 1_977_423_139.19, 32.59, 1_438_783_613.25, 27.24),
    ("bus_air_conditioning", "客车空调", 90_266_641.17, 1.49, None, None),
    ("rail_air_conditioning_service", "轨道交通列车空调及服务", 44_912_639.85, 0.74, None, None),
    ("other", "其他", 506_679_178.72, 8.35, None, None),
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sources(repo_root: Path) -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    for evidence_id, expected in EXPECTED_SOURCES.items():
        path = repo_root / expected["path"]
        if not path.is_file():
            raise FileNotFoundError(f"missing official evidence: {path}")
        actual_hash = _sha256(path)
        if actual_hash != expected["sha256"]:
            raise ValueError(f"official evidence hash mismatch for {evidence_id}: {actual_hash}")
        verified.append(
            {
                "evidence_id": evidence_id,
                "source_path": expected["path"],
                "sha256": actual_hash,
                "page_count": expected["pages"],
            }
        )
    return verified


def build_business_records(reviewed_at: str) -> list[dict[str, Any]]:
    common = {
        "workflow_id": WORKFLOW_ID,
        "stock_code": STOCK_CODE,
        "input_type": "business_disclosure",
        "as_of_date": "2025-12-31",
        "publication_date": "2026-04-21",
        "source_evidence_id": ANNUAL_EVIDENCE_ID,
        "source_rank": "A",
        "review_status": "accepted",
        "reviewer": "codex",
        "reviewed_at": reviewed_at,
        "capture_method": "codex_local_evidence_review_user_authorized",
        "no_live_api": True,
        "source_path": EXPECTED_SOURCES[ANNUAL_EVIDENCE_ID]["path"],
        "reporting_period": "2025A",
        "statement_scope": "consolidated",
        "accounting_scope_change": "none_reported_for_comparative_table",
        "sample_quality_allowed": False,
    }
    records: list[dict[str, Any]] = []
    for slug, reported_name, revenue, revenue_pct, cost, gross_margin in PRODUCT_ROWS:
        records.append(
            {
                **common,
                "input_id": f"r5_b5_business_2025_{slug}_revenue",
                "disclosure_id": f"annual_2025_{slug}_revenue",
                "disclosure_type": "reported_product_revenue",
                "business_line": reported_name,
                "disclosed_value": revenue,
                "unit": "CNY",
                "currency": "CNY",
                "claim_type": "fact",
                "page_or_table_locator": "PDF page 15; 第三节四、2（1）营业收入构成",
                "calculation_method": "direct_reported_value",
                "reported_revenue_pct": revenue_pct,
                "limitations": [
                    "发行人宽口径产品分类，不代表液冷单独口径。",
                    "只用于已披露产品线收入与公司总收入的对账。",
                ],
            }
        )
        if cost is not None and gross_margin is not None:
            records.append(
                {
                    **common,
                    "input_id": f"r5_b5_business_2025_{slug}_gross_margin",
                    "disclosure_id": f"annual_2025_{slug}_gross_margin",
                    "disclosure_type": "reported_product_gross_margin",
                    "business_line": reported_name,
                    "disclosed_value": gross_margin,
                    "unit": "pct",
                    "currency": None,
                    "claim_type": "fact",
                    "page_or_table_locator": "PDF page 16; 第三节四、2（2）占比超过10%的产品",
                    "calculation_method": "direct_reported_value",
                    "reported_cost": cost,
                    "cost_unit": "CNY",
                    "limitations": [
                        "发行人宽口径产品分类，不代表液冷单独口径。",
                        "毛利率仅适用于该披露产品大类。",
                    ],
                }
            )
    records.extend(
        [
            {
                **common,
                "input_id": "r5_b5_business_2025_company_revenue",
                "disclosure_id": "annual_2025_company_revenue",
                "disclosure_type": "reported_company_revenue",
                "business_line": "公司合计",
                "disclosed_value": 6_067_759_091.55,
                "unit": "CNY",
                "currency": "CNY",
                "claim_type": "fact",
                "page_or_table_locator": "PDF page 15; 第三节四、2（1）营业收入构成",
                "calculation_method": "direct_reported_value",
                "limitations": ["合并口径公司总收入。"],
            },
            {
                **common,
                "input_id": "r5_b5_business_2025_company_gross_margin",
                "disclosure_id": "annual_2025_company_gross_margin",
                "disclosure_type": "reported_company_gross_margin",
                "business_line": "公司合计",
                "disclosed_value": 27.86,
                "unit": "pct",
                "currency": None,
                "claim_type": "fact",
                "page_or_table_locator": "PDF page 16; 第三节四、2（2）精密温控节能设备",
                "calculation_method": "direct_reported_value",
                "limitations": ["合并口径综合毛利率，不代表任一细分技术路线。"],
            },
        ]
    )
    return records


def _metric(
    name: str,
    period: str,
    value: float,
    unit: str,
    evidence_id: str,
    *,
    method: str = "direct_reported_value",
    currency: str | None = "CNY",
    locator: str,
    claim_type: str = "fact",
) -> dict[str, Any]:
    return {
        "metric_name": name,
        "period": period,
        "value": value,
        "unit": unit,
        "currency": currency,
        "evidence_id": evidence_id,
        "metric_id": None,
        "calculation_method": method,
        "page_or_table_locator": locator,
        "claim_type": claim_type,
    }


def build_financial_history_pack() -> dict[str, Any]:
    annual_locator = "PDF page 7; 第二节六、主要会计数据和财务指标"
    q1_locator = "PDF page 2; 一、主要财务数据"
    annual_values = {
        "2023A": {
            "revenue": 3_528_859_077.13,
            "net_profit_attributable": 344_006_335.07,
            "net_profit_ex_items": 316_268_801.76,
            "operating_cashflow": 453_072_040.34,
            "total_assets": 5_091_055_172.06,
            "equity_attributable": 2_486_071_338.29,
            "basic_eps": 0.47,
            "weighted_roe": 15.03,
        },
        "2024A": {
            "revenue": 4_588_819_487.27,
            "net_profit_attributable": 452_664_369.42,
            "net_profit_ex_items": 429_719_858.69,
            "operating_cashflow": 199_835_014.95,
            "total_assets": 6_014_413_898.70,
            "equity_attributable": 2_915_892_117.15,
            "basic_eps": 0.47,
            "weighted_roe": 16.88,
        },
        "2025A": {
            "revenue": 6_067_759_091.55,
            "net_profit_attributable": 521_914_773.00,
            "net_profit_ex_items": 503_698_695.52,
            "operating_cashflow": 157_273_222.36,
            "total_assets": 7_747_255_663.66,
            "equity_attributable": 3_445_641_008.79,
            "basic_eps": 0.54,
            "weighted_roe": 16.58,
        },
    }
    q1_values = {
        "revenue": 1_175_329_313.61,
        "net_profit_attributable": 8_657_602.27,
        "net_profit_ex_items": 5_392_856.48,
        "operating_cashflow": -386_363_968.71,
        "total_assets": 7_761_763_222.65,
        "equity_attributable": 3_461_780_265.25,
        "basic_eps": 0.01,
        "weighted_roe": 0.25,
    }
    income_statement: list[dict[str, Any]] = []
    balance_sheet: list[dict[str, Any]] = []
    cashflow_statement: list[dict[str, Any]] = []
    key_metrics: list[dict[str, Any]] = []
    for period, values in annual_values.items():
        for name in ("revenue", "net_profit_attributable", "net_profit_ex_items"):
            income_statement.append(_metric(name, period, values[name], "CNY", ANNUAL_EVIDENCE_ID, locator=annual_locator))
        for name in ("total_assets", "equity_attributable"):
            balance_sheet.append(_metric(name, period, values[name], "CNY", ANNUAL_EVIDENCE_ID, locator=annual_locator))
        cashflow_statement.append(
            _metric("operating_cashflow", period, values["operating_cashflow"], "CNY", ANNUAL_EVIDENCE_ID, locator=annual_locator)
        )
        key_metrics.extend(
            [
                _metric("basic_eps", period, values["basic_eps"], "CNY_per_share", ANNUAL_EVIDENCE_ID, currency="CNY", locator=annual_locator),
                _metric("weighted_roe", period, values["weighted_roe"], "pct", ANNUAL_EVIDENCE_ID, currency=None, locator=annual_locator),
            ]
        )
    for name in ("revenue", "net_profit_attributable", "net_profit_ex_items"):
        income_statement.append(_metric(name, "2026Q1", q1_values[name], "CNY", Q1_EVIDENCE_ID, locator=q1_locator))
    for name in ("total_assets", "equity_attributable"):
        balance_sheet.append(_metric(name, "2026Q1", q1_values[name], "CNY", Q1_EVIDENCE_ID, locator=q1_locator))
    cashflow_statement.append(
        _metric("operating_cashflow", "2026Q1", q1_values["operating_cashflow"], "CNY", Q1_EVIDENCE_ID, locator=q1_locator)
    )
    key_metrics.extend(
        [
            _metric("basic_eps", "2026Q1", q1_values["basic_eps"], "CNY_per_share", Q1_EVIDENCE_ID, locator=q1_locator),
            _metric("weighted_roe", "2026Q1", q1_values["weighted_roe"], "pct", Q1_EVIDENCE_ID, currency=None, locator=q1_locator),
            _metric("gross_margin", "2025A", 27.86, "pct", ANNUAL_EVIDENCE_ID, currency=None, locator="PDF page 16; 第三节四、2（2）",),
            _metric(
                "gross_margin",
                "2026Q1",
                24.2935,
                "pct",
                Q1_EVIDENCE_ID,
                method="(revenue - operating_cost) / revenue * 100; revenue=1175329313.61; operating_cost=889801134.41",
                currency=None,
                locator="PDF page 9; 合并利润表",
                claim_type="inference",
            ),
        ]
    )
    return {
        "artifact_type": "R5_financial_history_pack",
        "schema_version": "r5_financial_history_pack_v0.1",
        "status": "ready",
        "as_of_date": "2026-04-21",
        "currency": "CNY",
        "periods": ["2023A", "2024A", "2025A", "2026Q1"],
        "income_statement": income_statement,
        "balance_sheet": balance_sheet,
        "cashflow_statement": cashflow_statement,
        "key_metrics": key_metrics,
        "financial_quality": {
            "revenue_quality": "2023-2025 audited annual figures; 2026Q1 unaudited quarterly figure",
            "profit_quality": "2026Q1 attributable profit fell 81.97% year on year while revenue grew 26.03%; do not extrapolate without explicit assumptions",
        },
        "adjusted_profit_bridge": {
            "status": "reviewed",
            "period": "2025A",
            "rows": [
                {"item": "net_profit_attributable", "value": 521_914_773.00, "unit": "CNY", "evidence_id": ANNUAL_EVIDENCE_ID},
                {"item": "net_profit_ex_items", "value": 503_698_695.52, "unit": "CNY", "evidence_id": ANNUAL_EVIDENCE_ID},
                {"item": "non_recurring_gap", "value": 18_216_077.48, "unit": "CNY", "evidence_id": ANNUAL_EVIDENCE_ID, "calculation_method": "attributable_profit_minus_ex_items_profit", "claim_type": "inference"},
            ],
        },
        "cashflow_quality": {
            "status": "reviewed",
            "notes": [
                "2025 operating cashflow was below 2024 and 2023 reported levels.",
                "2026Q1 operating cashflow was negative; a single quarter does not establish a full-year pattern.",
            ],
        },
        "working_capital_flags": {
            "status": "reviewed_limited",
            "flags": ["2026Q1 operating cashflow requires later working-capital note analysis"],
        },
        "roe_roic_commentary": {
            "status": "reviewed",
            "commentary": "Annual report supplies weighted ROE; ROIC is not calculated in this card because a reviewed invested-capital bridge is outside the disclosed summary table.",
        },
        "evidence_ids": [ANNUAL_EVIDENCE_ID, INTERIM_EVIDENCE_ID, Q1_EVIDENCE_ID],
        "missing_items": [],
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }


def _business_metric(
    value: float | None,
    unit: str,
    *,
    method: str = "direct_reported_value",
) -> dict[str, Any]:
    if value is None:
        return {"value": None, "unit": unit, "evidence_id": None, "metric_id": None, "missing_reason": "MISSING_DISCLOSURE"}
    return {
        "value": value,
        "unit": unit,
        "evidence_id": ANNUAL_EVIDENCE_ID,
        "metric_id": None,
        "calculation_method": method,
    }


def build_business_breakdown_pack() -> dict[str, Any]:
    total_gross_profit = 1_690_633_310.57
    business_lines: list[dict[str, Any]] = []
    for slug, reported_name, revenue, revenue_pct, cost, gross_margin in PRODUCT_ROWS:
        gross_profit = None if cost is None else round(revenue - cost, 2)
        gross_profit_pct = None if gross_profit is None else round(gross_profit / total_gross_profit * 100, 2)
        missing = [] if gross_profit is not None else ["该低占比产品未在年报10%以上产品表中单列营业成本和毛利率。"]
        business_lines.append(
            {
                "business_name": slug,
                "reported_name": reported_name,
                "role": "reported_broad_product_line",
                "revenue": _business_metric(revenue, "CNY"),
                "revenue_pct": _business_metric(revenue_pct, "pct"),
                "gross_margin": _business_metric(gross_margin, "pct"),
                "gross_profit": _business_metric(
                    gross_profit,
                    "CNY",
                    method="reported_revenue_minus_reported_cost",
                ),
                "gross_profit_pct": _business_metric(
                    gross_profit_pct,
                    "pct",
                    method="derived_line_gross_profit_divided_by_reported_company_gross_profit",
                ),
                "products": [reported_name],
                "customers": [],
                "capacity": [],
                "orders": [],
                "pricing_driver": "not_assessed_in_card_5_2",
                "cost_driver": "reported cost available only for product lines above the disclosure threshold" if cost is not None else "not_separately_disclosed",
                "linked_segments": [],
                "confidence": "high" if cost is not None else "medium",
                "evidence_ids": [ANNUAL_EVIDENCE_ID],
                "missing_items": missing,
                "page_or_table_locator": "PDF pages 15-16; 第三节四、2",
                "claim_type": "fact_with_arithmetic_derivations" if cost is not None else "fact_with_visible_gaps",
            }
        )
    business_lines.append(
        {
            "business_name": "liquid_cooling_specific",
            "reported_name": "液冷单独口径",
            "role": "product_line_clue_only",
            "revenue": _business_metric(None, "CNY"),
            "revenue_pct": _business_metric(None, "pct"),
            "gross_margin": _business_metric(None, "pct"),
            "gross_profit": _business_metric(None, "CNY"),
            "gross_profit_pct": _business_metric(None, "pct"),
            "products": ["Coolinside cold plates", "CDU", "manifold", "quick connectors"],
            "customers": [],
            "capacity": [],
            "orders": [],
            "pricing_driver": "TODO_SOURCE_REQUIRED",
            "cost_driver": "TODO_SOURCE_REQUIRED",
            "linked_segments": ["ai_server_liquid_cooling"],
            "confidence": "medium",
            "evidence_ids": [ANNUAL_EVIDENCE_ID],
            "missing_items": [
                "液冷收入占比未单列披露。",
                "液冷毛利率未单列披露。",
                "液冷利润贡献未单列披露。",
            ],
            "page_or_table_locator": "PDF pages 9-10 product narrative; financial tables use broader room/cabinet categories",
            "claim_type": "product_clue_and_unknown_metrics",
        }
    )
    product_revenue_sum = round(sum(row[2] for row in PRODUCT_ROWS), 2)
    return {
        "artifact_type": "R5_business_breakdown_pack",
        "schema_version": "r5_business_breakdown_pack_v0.1",
        "status": "partial",
        "as_of_date": "2026-04-21",
        "stock_code": STOCK_CODE,
        "business_lines": business_lines,
        "profit_pool_summary": {
            "status": "partial",
            "company_revenue": 6_067_759_091.55,
            "company_operating_cost": 4_377_125_780.98,
            "company_gross_profit": total_gross_profit,
            "unit": "CNY",
            "evidence_id": ANNUAL_EVIDENCE_ID,
            "product_revenue_sum": product_revenue_sum,
            "reconciliation_residual": round(6_067_759_091.55 - product_revenue_sum, 2),
            "calculation_method": "sum_reported_product_revenue_and_compare_with_reported_company_revenue",
            "limitation": "Only the two product lines above the disclosure threshold have separate cost and margin rows.",
        },
        "structural_contradictions": [
            "The issuer discloses liquid-cooling products but reports revenue and margin in broader room/cabinet cooling categories.",
            "Broad product-line totals therefore cannot be relabeled as liquid-cooling-specific financials.",
        ],
        "linked_segments": ["ai_server_liquid_cooling"],
        "missing_items": [
            {"item": "liquid_cooling_revenue_share", "reason": "MISSING_DISCLOSURE"},
            {"item": "liquid_cooling_gross_margin", "reason": "MISSING_DISCLOSURE"},
            {"item": "liquid_cooling_profit_contribution", "reason": "MISSING_DISCLOSURE"},
        ],
        "source_gap_register": [
            {"gap_id": "R5_002837_GAP_BUSINESS_001", "token": "MISSING_DISCLOSURE", "owner": "evidence-ingest", "next_action": "retain visible gap until an official split is published"}
        ],
        "evidence_ids": [ANNUAL_EVIDENCE_ID, INTERIM_EVIDENCE_ID],
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }


def build_partial_core_preflight() -> dict[str, Any]:
    return {
        "artifact_type": "R5_bundle5_core_preflight_after_disclosure",
        "schema_version": "r5_bundle5_core_preflight_after_disclosure_v0.1",
        "workflow_id": WORKFLOW_ID,
        "status": "pass_for_card_5_2_partial_core",
        "financial_history_status": "accepted",
        "business_breakdown_status": "accepted_with_todos",
        "forecast_model_status": "not_run_until_card_5_4",
        "valuation_status": "not_run_until_card_5_4",
        "blocking_for_card_5_2": [],
        "blocking_for_card_5_5": [
            "reviewed market snapshot not yet onboarded",
            "reviewed peer snapshot not yet onboarded",
            "forecast and valuation inputs not yet reviewed",
        ],
        "known_todos": ["MISSING_DISCLOSURE", "TODO_SOURCE_REQUIRED"],
        "canonical_registry_write_allowed": False,
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
        "interpretation": "Financial and broad business candidate packs validate at the level allowed by Card 5.2; full core preflight waits for Cards 5.3-5.4.",
    }


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def write_readout(path: Path, reviewed_at: str, record_count: int) -> None:
    text = f"""# R5 Bundle 5.2 — Official Disclosure and Financial History Readout

status: accepted_with_visible_disclosure_gaps

## result

- workflow_id: `{WORKFLOW_ID}`
- stock_code: `{STOCK_CODE}`
- reviewer: `codex`
- reviewed_at: `{reviewed_at}`
- accepted_business_disclosure_records: `{record_count}`
- financial_history_candidate: `accepted`
- business_breakdown_candidate: `accepted_with_todos`
- canonical_registry_changed: `false`
- sample_quality_report_allowed: `false`
- p2_allowed: `false`

Three immutable source-rank A filings were verified by physical path and SHA256. The 2025 annual report supports 2023-2025 company financial history and broad product-line revenue/margin tables; the 2026 Q1 report supplies the latest company totals. Reported facts and arithmetic derivations are labeled separately.

## reconciliation

- 2025 reported company revenue: `6,067,759,091.55 CNY`.
- Sum of the five reported product revenue rows: `6,067,759,091.55 CNY`.
- Reconciliation residual: `0.00 CNY`.
- Room-cooling and cabinet-cooling gross profit are arithmetic derivations from reported revenue minus reported cost.

## disclosure_boundary

The issuer's financial tables use broad room-cooling and cabinet-cooling categories. They do not separately disclose liquid-cooling revenue share, gross margin, or profit contribution. Those three fields remain visible as `MISSING_DISCLOSURE`; no broad category was relabeled as liquid cooling.

## outputs

- `data/reviewed_inputs/{WORKFLOW_ID}/business_disclosure/official_2025_annual_report.yaml`
- `reports/workflow_runs/{WORKFLOW_ID}/R5_bundle5_financial_history_candidate.yaml`
- `reports/workflow_runs/{WORKFLOW_ID}/R5_bundle5_business_breakdown_candidate.yaml`
- `reports/workflow_runs/{WORKFLOW_ID}/R5_bundle5_core_preflight_after_disclosure.yaml`
- `reports/workflow_runs/{WORKFLOW_ID}/R5_bundle5_business_disclosure_validation.json`

## next_card

Proceed to Card 5.3 for dated market and peer inputs. Canonical registries remain read-only.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_outputs(repo_root: Path, workflow_id: str, reviewed_at: str) -> dict[str, Any]:
    if workflow_id != WORKFLOW_ID:
        raise ValueError(f"this Bundle 5.2 builder is scoped to {WORKFLOW_ID}")
    datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
    verified = verify_sources(repo_root)
    records = build_business_records(reviewed_at)
    run_dir = repo_root / "reports/workflow_runs" / workflow_id
    dropzone_path = repo_root / "data/reviewed_inputs" / workflow_id / "business_disclosure" / "official_2025_annual_report.yaml"
    write_yaml(dropzone_path, {"records": records})
    write_yaml(run_dir / "R5_bundle5_financial_history_candidate.yaml", build_financial_history_pack())
    write_yaml(run_dir / "R5_bundle5_business_breakdown_candidate.yaml", build_business_breakdown_pack())
    write_yaml(run_dir / "R5_bundle5_core_preflight_after_disclosure.yaml", build_partial_core_preflight())
    write_readout(repo_root / "reports/p1_6/R5_BUNDLE_5_2_OFFICIAL_DISCLOSURE_FINANCIAL_READOUT.md", reviewed_at, len(records))
    return {"verified_sources": verified, "record_count": len(records), "dropzone_path": dropzone_path.as_posix()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build R5 Bundle 5.2 official-disclosure onboarding outputs.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--workflow-id", default=WORKFLOW_ID)
    parser.add_argument("--reviewed-at", required=True)
    args = parser.parse_args(argv)
    result = build_outputs(args.repo_root.resolve(), args.workflow_id, args.reviewed_at)
    print(
        "r5_bundle5_card_5_2 status=generated "
        f"verified_sources={len(result['verified_sources'])} accepted_records={result['record_count']} "
        "promotion_allowed=false sample_quality=false p2=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
