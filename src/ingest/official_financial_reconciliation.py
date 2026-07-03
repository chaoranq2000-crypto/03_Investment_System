from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Sequence

import yaml


DATA_LAYER_RUN = Path("reports/workflow_runs/wf_20260703_data_layer_002837_invic")
STOCK_RUN = Path("reports/workflow_runs/wf_20260703_stock_first_002837_invic")
OFFICIAL_EVIDENCE_ID = "ev_annual_report_002837_20260421_ce7f64"

FIELDNAMES = [
    "metric_name",
    "original_metric_name",
    "normalized_metric_name",
    "period",
    "structured_value",
    "official_value",
    "unit",
    "source_structured_evidence_id",
    "official_evidence_id",
    "official_page_or_table_locator",
    "difference",
    "tolerance",
    "reconciliation_status",
    "notes",
]

OUTPUT_POSIX = "reports/workflow_runs/wf_20260703_data_layer_002837_invic/official_financial_reconciliation.csv"
READOUT_POSIX = (
    "reports/workflow_runs/wf_20260703_data_layer_002837_invic/"
    "official_financial_reconciliation_readout.md"
)


@dataclass(frozen=True)
class OfficialMetric:
    normalized_metric_name: str
    official_value: str
    unit: str
    locator: str
    notes: str


OFFICIAL_METRICS: dict[str, OfficialMetric] = {
    "total_revenue": OfficialMetric(
        "total_revenue",
        "6067759091.55",
        "CNY",
        "page:4; table:主要会计数据和财务指标",
        "2025 annual-report summary line item.",
    ),
    "n_income_attr_p": OfficialMetric(
        "n_income_attr_p",
        "521914773.00",
        "CNY",
        "page:4; table:主要会计数据和财务指标",
        "2025 annual-report summary line item.",
    ),
    "basic_eps": OfficialMetric(
        "basic_eps",
        "0.54",
        "CNY",
        "page:4; table:主要会计数据和财务指标",
        "2025 annual-report summary line item.",
    ),
    "operating_cash_flow": OfficialMetric(
        "operating_cash_flow",
        "157273222.36",
        "CNY",
        "page:4; table:主要会计数据和财务指标",
        "2025 annual-report summary line item.",
    ),
    "total_assets": OfficialMetric(
        "total_assets",
        "7747255663.66",
        "CNY",
        "page:3; table:主要会计数据和财务指标",
        "2025 year-end annual-report summary line item.",
    ),
    "roe": OfficialMetric(
        "roe",
        "16.58",
        "%",
        "page:4; table:主要会计数据和财务指标",
        "Annual-report weighted average ROE; unit is percent.",
    ),
}

OFFICIAL_MISSING_METRICS = {
    "gross_margin": "No direct company-level gross margin was parsed from the current annual-report summary.",
    "net_margin": "Net margin is not directly disclosed in the parsed annual-report summary.",
    "total_liabilities": "Total liabilities were not parsed from the current annual-report summary.",
    "debt_to_asset": "Debt-to-asset ratio is not directly disclosed in the parsed annual-report summary.",
}

METRIC_ALIASES = {
    "revenue": "total_revenue",
    "n_cashflow_act": "operating_cash_flow",
    "net_cash_flows_oper_act": "operating_cash_flow",
    "debt_to_assets": "debt_to_asset",
}

TARGET_METRICS = [
    "total_revenue",
    "n_income_attr_p",
    "gross_margin",
    "net_margin",
    "basic_eps",
    "operating_cash_flow",
    "total_assets",
    "total_liabilities",
    "roe",
    "debt_to_asset",
]


def _decimal(value: str) -> Decimal | None:
    text = str(value or "").replace(",", "").replace("%", "").strip()
    if not text or text.startswith("MISSING") or text.startswith("TODO"):
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _normalize_metric(metric_name: str) -> str:
    value = metric_name.strip()
    return METRIC_ALIASES.get(value, value)


def _load_structured_rows(financial_metric_pack: Path) -> dict[tuple[str, str], dict[str, str]]:
    rows: dict[tuple[str, str], dict[str, str]] = {}
    with financial_metric_pack.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            normalized = _normalize_metric(row.get("metric_name", ""))
            period = row.get("period", "")
            rows.setdefault((normalized, period), row)
    return rows


def _status(structured_value: str, official_value: str, tolerance: str) -> tuple[str, str]:
    if str(official_value).strip() == "official_missing":
        return "official_missing", ""
    if str(structured_value).strip() in {"", "structured_missing"}:
        return "structured_missing", ""
    structured = _decimal(structured_value)
    official = _decimal(official_value)
    if structured is None and official is None:
        return "needs_manual_review", ""
    if structured is None:
        return "structured_missing", ""
    if official is None:
        return "official_missing", ""
    difference = official - structured
    if abs(difference) <= Decimal(tolerance):
        if difference == 0:
            return "matched", "0"
        return "matched_with_rounding", str(difference)
    return "mismatch", str(difference)


def build_reconciliation_rows(financial_metric_pack: Path, period: str = "20251231") -> list[dict[str, str]]:
    structured_rows = _load_structured_rows(financial_metric_pack)
    output: list[dict[str, str]] = []
    for metric in TARGET_METRICS:
        structured = structured_rows.get((metric, period), {})
        original_metric = structured.get("metric_name", metric)
        structured_value = structured.get("value", "")
        structured_evidence_id = structured.get("source_evidence_id", "")
        if metric in OFFICIAL_METRICS:
            official = OFFICIAL_METRICS[metric]
            official_value = official.official_value
            official_id = OFFICIAL_EVIDENCE_ID
            locator = official.locator
            unit = structured.get("unit") or official.unit
            notes = official.notes
        else:
            official_value = "official_missing"
            official_id = "official_missing"
            locator = "official_missing"
            unit = structured.get("unit", "")
            notes = OFFICIAL_MISSING_METRICS[metric]
        tolerance = "0.01" if unit in {"CNY", "%"} else "0.0001"
        status, difference = _status(structured_value, official_value, tolerance)
        output.append(
            {
                "metric_name": metric,
                "original_metric_name": original_metric,
                "normalized_metric_name": metric,
                "period": period,
                "structured_value": structured_value or "structured_missing",
                "official_value": official_value,
                "unit": unit,
                "source_structured_evidence_id": structured_evidence_id or "structured_missing",
                "official_evidence_id": official_id,
                "official_page_or_table_locator": locator,
                "difference": difference,
                "tolerance": tolerance,
                "reconciliation_status": status,
                "notes": notes
                + " Structured data remains metric-only and is not promoted to reported fact by this file.",
            }
        )
    return output


def write_csv_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_readout(path: Path, rows: list[dict[str, str]]) -> None:
    counts: dict[str, int] = {}
    for row in rows:
        status = row["reconciliation_status"]
        counts[status] = counts.get(status, 0) + 1
    lines = [
        "# Official Disclosure Reconciliation Readout",
        "",
        "workflow_id: wf_20260703_data_layer_002837_invic",
        "stock_code: 002837",
        "company_id: cn_002837_invic",
        "status: partial_reconciliation_completed_with_review_todos",
        "",
        "## Scope",
        "",
        "This MVP reconciles company-level structured financial metrics against the registered 2025 annual-report summary. It does not promote structured data into reported facts and does not evaluate business-segment exposure.",
        "",
        "## Status Counts",
        "",
        "| reconciliation_status | count |",
        "|---|---:|",
    ]
    for status in [
        "matched",
        "matched_with_rounding",
        "mismatch",
        "official_missing",
        "structured_missing",
        "needs_manual_review",
    ]:
        lines.append(f"| {status} | {counts.get(status, 0)} |")
    lines.extend(
        [
            "",
            "## Required Core Metrics",
            "",
            "| metric | period | structured_value | official_value | status | evidence |",
            "|---|---|---:|---:|---|---|",
        ]
    )
    for row in rows:
        if row["normalized_metric_name"] in {"total_revenue", "n_income_attr_p", "basic_eps"}:
            lines.append(
                "| {metric} | {period} | {structured} | {official} | {status} | {evidence} |".format(
                    metric=row["normalized_metric_name"],
                    period=row["period"],
                    structured=row["structured_value"],
                    official=row["official_value"],
                    status=row["reconciliation_status"],
                    evidence=row["official_evidence_id"],
                )
            )
    lines.extend(
        [
            "",
            "## Boundary Decision",
            "",
            "- DLBR-001 is refined from unreconciled stub to partial reconciliation completed with mismatches and remaining official_missing fields.",
            "- Mismatch rows are visible and require quality-review before any promotion.",
            "- Company-level metrics still cannot prove liquid-cooling revenue share, orders, customer exposure or segment profitability.",
            "- Structured data is not promoted to reported fact; it remains metric-only until an explicit review step promotes a candidate.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _replace_gap_report(data_layer_run: Path) -> None:
    path = data_layer_run / "source_gap_report.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "| official_disclosure_reconciliation_stub.md | available_with_todo | Structured financial metrics still require official disclosure reconciliation |",
        "| official_financial_reconciliation.csv | available_with_review_todo | Partial official reconciliation completed; mismatch and official_missing rows require quality-review before promotion |",
    )
    text = text.replace(
        "| DL-GAP-002 | medium | TODO_DISCLOSURE_RECONCILIATION | structured financial metrics need official filing reconciliation before material company facts |",
        "| DL-GAP-002 | medium | PARTIAL_RECONCILIATION_COMPLETED_REVIEW_TODO | official_financial_reconciliation.csv exists; mismatches and remaining official_missing fields stay visible before any promotion |",
    )
    path.write_text(text, encoding="utf-8")


def _rewrite_open_todos(data_layer_run: Path) -> None:
    path = data_layer_run / "open_todos.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0].keys()) if rows else []
    for row in rows:
        if row.get("issue_id") == "DL-GAP-002":
            row["target_artifact"] = "official_financial_reconciliation.csv"
            row["description"] = (
                "partial official reconciliation completed; mismatch and official_missing rows require review before promotion"
            )
            row["status"] = "accepted_todo"
            row["notes"] = "Do not use structured financial metrics as reported facts until reviewed."
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _update_workflow_state(data_layer_run: Path) -> None:
    path = data_layer_run / "workflow_state.yaml"
    state = yaml.safe_load(path.read_text(encoding="utf-8"))
    state["updated_at"] = "2026-07-03"
    state["current_stage"] = "R4_official_disclosure_reconciliation"
    state["next_stage"] = "R4_business_segment_disclosure_extraction"
    state["required_next_skill"] = "stock-deep-dive"
    artifacts = state.get("artifacts", [])
    existing = {item.get("artifact_type") for item in artifacts if isinstance(item, dict)}
    if "official_financial_reconciliation" not in existing:
        artifacts.append(
            {
                "artifact_type": "official_financial_reconciliation",
                "path": OUTPUT_POSIX,
                "created_by_skill": "evidence-ingest",
                "stage": "R4_Next_2",
                "status": "current",
                "required": True,
            }
        )
    if "official_financial_reconciliation_readout" not in existing:
        artifacts.append(
            {
                "artifact_type": "official_financial_reconciliation_readout",
                "path": READOUT_POSIX,
                "created_by_skill": "evidence-ingest",
                "stage": "R4_Next_2",
                "status": "current",
                "required": True,
            }
        )
    for todo in state.get("open_todos", []):
        if isinstance(todo, dict) and todo.get("issue_id") == "DL-GAP-002":
            todo["target_artifact"] = "official_financial_reconciliation.csv"
            todo["status"] = "accepted_todo"
            todo["notes"] = (
                "Partial official reconciliation exists; mismatch and official_missing rows remain review TODOs."
            )
    path.write_text(
        yaml.safe_dump(state, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def _update_artifact_manifest(data_layer_run: Path) -> None:
    path = data_layer_run / "artifact_manifest.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0].keys()) if rows else []
    existing = {row.get("artifact_type") for row in rows}
    additions = [
        {
            "artifact_id": "art_016",
            "artifact_type": "official_financial_reconciliation",
            "path": "official_financial_reconciliation.csv",
            "created_by_skill": "evidence-ingest",
            "stage": "R4_Next_2",
            "required": "True",
            "exists": "True",
            "status": "current",
            "notes": "partial official reconciliation with visible mismatch/official_missing rows",
        },
        {
            "artifact_id": "art_017",
            "artifact_type": "official_financial_reconciliation_readout",
            "path": "official_financial_reconciliation_readout.md",
            "created_by_skill": "evidence-ingest",
            "stage": "R4_Next_2",
            "required": "True",
            "exists": "True",
            "status": "current",
            "notes": "R4 Next-2 readout",
        },
    ]
    rows.extend(row for row in additions if row["artifact_type"] not in existing)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_stage_readout(repo_root: Path, rows: list[dict[str, str]]) -> None:
    path = repo_root / "reports/p1_6/OFFICIAL_DISCLOSURE_RECONCILIATION_MVP_READOUT.md"
    mismatch = sum(1 for row in rows if row["reconciliation_status"] == "mismatch")
    official_missing = sum(1 for row in rows if row["reconciliation_status"] == "official_missing")
    structured_missing = sum(1 for row in rows if row["reconciliation_status"] == "structured_missing")
    lines = [
        "# OFFICIAL_DISCLOSURE_RECONCILIATION_MVP_READOUT",
        "",
        "date: 2026-07-03",
        "status: PASS_WITH_REVIEW_TODOS",
        "",
        "## Outputs",
        "",
        f"- `{OUTPUT_POSIX}`",
        f"- `{READOUT_POSIX}`",
        "",
        "## Result",
        "",
        f"- mismatch_rows: {mismatch}",
        f"- official_missing_rows: {official_missing}",
        f"- structured_missing_rows: {structured_missing}",
        "- DLBR-001 is no longer only a stub; it is now a partial reconciliation result with visible review TODOs.",
        "- No structured metric was promoted to reported fact.",
        "- No business exposure was inferred from company-level financial metrics.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_official_reconciliation(*, repo_root: Path) -> list[dict[str, str]]:
    data_layer_run = repo_root / DATA_LAYER_RUN
    rows = build_reconciliation_rows(data_layer_run / "financial_metric_pack.csv")
    output_path = data_layer_run / "official_financial_reconciliation.csv"
    readout_path = data_layer_run / "official_financial_reconciliation_readout.md"
    write_csv_rows(output_path, rows)
    write_readout(readout_path, rows)
    _replace_gap_report(data_layer_run)
    _rewrite_open_todos(data_layer_run)
    _update_workflow_state(data_layer_run)
    _update_artifact_manifest(data_layer_run)
    write_stage_readout(repo_root, rows)
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build official financial reconciliation for the R4 data-layer run.")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args(argv)
    rows = build_official_reconciliation(repo_root=Path(args.repo_root).resolve())
    print({"rows": len(rows), "output": OUTPUT_POSIX})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
