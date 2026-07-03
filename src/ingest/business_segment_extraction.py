from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Sequence

import yaml


STOCK_RUN = Path("reports/workflow_runs/wf_20260703_stock_first_002837_invic")
OFFICIAL_EVIDENCE_ID = "ev_annual_report_002837_20260421_ce7f64"

FIELDNAMES = [
    "company_id",
    "stock_code",
    "period",
    "segment_name_reported",
    "mapped_internal_segment",
    "metric_name",
    "value",
    "unit",
    "official_evidence_id",
    "page_or_table_locator",
    "mapping_confidence",
    "review_status",
    "evidence_class",
    "revenue_pct",
    "profit_pct",
    "notes",
]

PACK_POSIX = "reports/workflow_runs/wf_20260703_stock_first_002837_invic/business_segment_metric_pack.csv"
READOUT_POSIX = (
    "reports/workflow_runs/wf_20260703_stock_first_002837_invic/"
    "business_segment_extraction_readout.md"
)


def build_business_segment_rows() -> list[dict[str, str]]:
    base = {
        "company_id": "cn_002837_invic",
        "stock_code": "002837",
        "period": "2025",
    }
    rows = [
        {
            **base,
            "segment_name_reported": "机房温控节能产品",
            "mapped_internal_segment": "ai_server_liquid_cooling",
            "metric_name": "data_center_liquid_cooling_product_line",
            "value": "product_line_clue",
            "unit": "qualitative",
            "official_evidence_id": OFFICIAL_EVIDENCE_ID,
            "page_or_table_locator": "page:2; section:报告期主要业务或产品简介",
            "mapping_confidence": "medium",
            "review_status": "product_line_clue",
            "evidence_class": "product_line_clue",
            "revenue_pct": "MISSING_DISCLOSURE",
            "profit_pct": "MISSING_DISCLOSURE",
            "notes": "Annual-report text describes data-center and liquid-cooling products, but does not disclose liquid-cooling revenue share.",
        },
        {
            **base,
            "segment_name_reported": "机房温控节能产品",
            "mapped_internal_segment": "ai_server_liquid_cooling",
            "metric_name": "liquid_cooling_revenue_pct",
            "value": "MISSING_DISCLOSURE",
            "unit": "pct",
            "official_evidence_id": "missing_disclosure",
            "page_or_table_locator": "missing_disclosure",
            "mapping_confidence": "low",
            "review_status": "missing_disclosure",
            "evidence_class": "missing_disclosure",
            "revenue_pct": "MISSING_DISCLOSURE",
            "profit_pct": "MISSING_DISCLOSURE",
            "notes": "Current official summary does not disclose liquid-cooling revenue percentage.",
        },
        {
            **base,
            "segment_name_reported": "机房温控节能产品",
            "mapped_internal_segment": "ai_server_liquid_cooling",
            "metric_name": "liquid_cooling_gross_margin",
            "value": "MISSING_DISCLOSURE",
            "unit": "pct",
            "official_evidence_id": "missing_disclosure",
            "page_or_table_locator": "missing_disclosure",
            "mapping_confidence": "low",
            "review_status": "missing_disclosure",
            "evidence_class": "missing_disclosure",
            "revenue_pct": "MISSING_DISCLOSURE",
            "profit_pct": "MISSING_DISCLOSURE",
            "notes": "Annual-report text says margin improved for room cooling, but no liquid-cooling gross-margin number is disclosed.",
        },
        {
            **base,
            "segment_name_reported": "储能应用",
            "mapped_internal_segment": "energy_storage_thermal_management_candidate",
            "metric_name": "energy_storage_application_revenue",
            "value": "1700000000",
            "unit": "CNY",
            "official_evidence_id": OFFICIAL_EVIDENCE_ID,
            "page_or_table_locator": "page:2; section:机柜温控节能产品",
            "mapping_confidence": "medium",
            "review_status": "reviewed_official",
            "evidence_class": "disclosed_revenue",
            "revenue_pct": "MISSING_DISCLOSURE",
            "profit_pct": "MISSING_DISCLOSURE",
            "notes": "Official text discloses energy-storage application revenue of about CNY 1.7bn; this is not data-center liquid-cooling revenue.",
        },
        {
            **base,
            "segment_name_reported": "电子散热业务",
            "mapped_internal_segment": "ai_server_liquid_cooling",
            "metric_name": "server_liquid_cooling_customer_product_clue",
            "value": "product_line_clue",
            "unit": "qualitative",
            "official_evidence_id": OFFICIAL_EVIDENCE_ID,
            "page_or_table_locator": "page:3; section:电子散热业务",
            "mapping_confidence": "medium",
            "review_status": "product_line_clue",
            "evidence_class": "product_line_clue",
            "revenue_pct": "MISSING_DISCLOSURE",
            "profit_pct": "MISSING_DISCLOSURE",
            "notes": "Official text describes liquid-cooling components and platform validation clues, but not segment revenue or profit.",
        },
        {
            **base,
            "segment_name_reported": "机柜温控节能产品",
            "mapped_internal_segment": "energy_storage_thermal_management_candidate",
            "metric_name": "cabinet_cooling_revenue_growth_text",
            "value": "narrative_only",
            "unit": "qualitative",
            "official_evidence_id": OFFICIAL_EVIDENCE_ID,
            "page_or_table_locator": "page:3; section:机柜温控节能产品",
            "mapping_confidence": "low",
            "review_status": "narrative_only",
            "evidence_class": "narrative_only",
            "revenue_pct": "MISSING_DISCLOSURE",
            "profit_pct": "MISSING_DISCLOSURE",
            "notes": "Growth and margin direction are textual; no normalized revenue percentage or profit percentage is extracted.",
        },
    ]
    return rows


def write_pack(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_readout(path: Path, rows: list[dict[str, str]]) -> None:
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["review_status"]] = status_counts.get(row["review_status"], 0) + 1
    lines = [
        "# Business Segment Disclosure Extraction Readout",
        "",
        "workflow_id: wf_20260703_stock_first_002837_invic",
        "stock_code: 002837",
        "company_id: cn_002837_invic",
        "status: completed_with_missing_disclosure",
        "",
        "## Status Counts",
        "",
        "| review_status | count |",
        "|---|---:|",
    ]
    for status in [
        "reviewed_official",
        "needs_manual_review",
        "missing_disclosure",
        "narrative_only",
        "product_line_clue",
        "not_applicable",
    ]:
        lines.append(f"| {status} | {status_counts.get(status, 0)} |")
    lines.extend(
        [
            "",
            "## Boundary Decision",
            "",
            "- Liquid-cooling revenue percentage remains MISSING_DISCLOSURE.",
            "- Liquid-cooling gross margin remains MISSING_DISCLOSURE.",
            "- Product-line clues may support product exposure only after quality review; they do not create revenue_pct or profit_pct.",
            "- Tushare and Baostock are not used in this business-segment pack.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_remaining_gaps(stock_run: Path) -> None:
    path = stock_run / "remaining_source_gaps_after_data_layer_bridge.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "| DLBR-001 | medium | official_disclosure_reconciliation_stub.md | Extract and reconcile official annual/interim/quarterly tables before any reported fact promotion. |",
        "| DLBR-001 | medium | official_financial_reconciliation.csv | Partial company-level reconciliation exists; mismatch rows still require review before promotion. |",
    )
    addition = """
| DISCLOSURE-SEGMENT-002 | medium | business_segment_metric_pack.csv | Liquid-cooling revenue_pct and profit_pct remain MISSING_DISCLOSURE; product_line_clue rows cannot become revenue facts. |
"""
    if "DISCLOSURE-SEGMENT-002" not in text:
        text = text.rstrip() + "\n" + addition
    path.write_text(text, encoding="utf-8")


def _update_segment_exposure(stock_run: Path) -> None:
    path = stock_run / "segment_exposure.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for item in data.get("linked_segments", []):
        if item.get("segment_id") == "ai_server_liquid_cooling":
            item["exposure_type"] = "product"
            item["exposure_score"] = 2
            item["revenue_pct"] = "MISSING_DISCLOSURE"
            item["profit_pct"] = "MISSING_DISCLOSURE"
            item["metric_ids"] = ["business_segment_metric_pack.csv:product_line_clue"]
            item["confidence"] = "medium"
            item["backflow_decision"] = "blocked"
            item["notes"] = (
                "Workflow-local R4 extraction found official product_line_clue rows for liquid-cooling related products, "
                "but revenue_pct/profit_pct remain MISSING_DISCLOSURE and no global exposure registry update is allowed yet."
            )
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def _update_artifact_manifest(stock_run: Path) -> None:
    path = stock_run / "artifact_manifest.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0].keys()) if rows else []
    existing = {row.get("artifact_type") for row in rows}
    additions = [
        {
            "artifact_id": "art_031",
            "artifact_type": "business_segment_metric_pack",
            "path": "business_segment_metric_pack.csv",
            "created_by_skill": "stock-deep-dive",
            "stage": "R4_Next_3",
            "required": "True",
            "exists": "True",
            "status": "current",
            "notes": "official-disclosure business segment extraction with missing liquid-cooling revenue_pct",
        },
        {
            "artifact_id": "art_032",
            "artifact_type": "business_segment_extraction_readout",
            "path": "business_segment_extraction_readout.md",
            "created_by_skill": "stock-deep-dive",
            "stage": "R4_Next_3",
            "required": "True",
            "exists": "True",
            "status": "current",
            "notes": "R4 Next-3 readout",
        },
    ]
    rows.extend(row for row in additions if row["artifact_type"] not in existing)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_stage_readout(repo_root: Path, rows: list[dict[str, str]]) -> None:
    path = repo_root / "reports/p1_6/BUSINESS_SEGMENT_DISCLOSURE_EXTRACTION_MVP_READOUT.md"
    missing = sum(1 for row in rows if row["review_status"] == "missing_disclosure")
    product = sum(1 for row in rows if row["review_status"] == "product_line_clue")
    reviewed = sum(1 for row in rows if row["review_status"] == "reviewed_official")
    lines = [
        "# BUSINESS_SEGMENT_DISCLOSURE_EXTRACTION_MVP_READOUT",
        "",
        "date: 2026-07-03",
        "status: PASS_WITH_DISCLOSURE_TODOS",
        "",
        "## Outputs",
        "",
        f"- `{PACK_POSIX}`",
        f"- `{READOUT_POSIX}`",
        "",
        "## Result",
        "",
        f"- reviewed_official_rows: {reviewed}",
        f"- product_line_clue_rows: {product}",
        f"- missing_disclosure_rows: {missing}",
        "- Liquid-cooling revenue_pct remains MISSING_DISCLOSURE.",
        "- Liquid-cooling profit_pct remains MISSING_DISCLOSURE.",
        "- No Tushare/Baostock row was used for business exposure.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_business_segment_pack(*, repo_root: Path) -> list[dict[str, str]]:
    stock_run = repo_root / STOCK_RUN
    rows = build_business_segment_rows()
    write_pack(stock_run / "business_segment_metric_pack.csv", rows)
    write_readout(stock_run / "business_segment_extraction_readout.md", rows)
    _update_remaining_gaps(stock_run)
    _update_segment_exposure(stock_run)
    _update_artifact_manifest(stock_run)
    write_stage_readout(repo_root, rows)
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build business segment metric pack for R4 readiness.")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args(argv)
    rows = build_business_segment_pack(repo_root=Path(args.repo_root).resolve())
    print({"rows": len(rows), "output": PACK_POSIX})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
