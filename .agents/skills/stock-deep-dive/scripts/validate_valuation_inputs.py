from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml


MARKET_COLUMNS = [
    "stock_code",
    "company_id",
    "stock_name",
    "exchange",
    "as_of_date",
    "currency",
    "close_price",
    "market_cap",
    "free_float_market_cap",
    "shares_outstanding",
    "float_shares",
    "pe_ttm",
    "pe_lyr",
    "pe_forward_2026e",
    "pb_lf",
    "ps_ttm",
    "ev",
    "ev_ebitda_ttm",
    "dividend_yield",
    "turnover_rate",
    "pct_chg_20d",
    "pct_chg_60d",
    "source_name",
    "source_type",
    "source_path",
    "source_evidence_id",
    "source_metric_id",
    "reliability_rank",
    "capture_method",
    "snapshot_status",
    "limitations",
]

MARKET_NUMERIC_COLUMNS = [
    "close_price",
    "market_cap",
    "free_float_market_cap",
    "shares_outstanding",
    "float_shares",
    "pe_ttm",
    "pe_lyr",
    "pe_forward_2026e",
    "pb_lf",
    "ps_ttm",
    "ev",
    "ev_ebitda_ttm",
    "dividend_yield",
    "turnover_rate",
    "pct_chg_20d",
    "pct_chg_60d",
]

PEER_COLUMNS = [
    "subject_stock_code",
    "subject_company_id",
    "peer_company",
    "peer_stock_code",
    "exchange",
    "peer_selection_reason",
    "business_similarity",
    "segment_overlap",
    "as_of_date",
    "currency",
    "market_cap",
    "pe_ttm",
    "pe_forward_2026e",
    "pe_forward_2027e",
    "pb_lf",
    "ps_ttm",
    "ev_ebitda_ttm",
    "revenue_growth_2026e",
    "net_profit_growth_2026e",
    "roe",
    "gross_margin",
    "source_name",
    "source_type",
    "source_path",
    "source_evidence_id",
    "reliability_rank",
    "confidence",
    "limitations",
]

FINANCIAL_COLUMNS = [
    "metric_id",
    "company_id",
    "stock_code",
    "metric_name",
    "period",
    "value",
    "unit",
    "currency",
    "source_evidence_id",
    "source_path",
    "calculation_method",
    "claim_type",
    "confidence",
    "review_status",
    "limitations",
]

READY_STATUSES = {"ready", "reviewed", "accepted", "current"}
PARTIAL_STATUSES = {"partial", "reviewed_r3_candidate", "low_confidence_fixture"}
TODO_PREFIXES = ("TODO", "MISSING", "LOW_CONFIDENCE", "UNKNOWN", "NOT_ASSESSABLE")

ADVICE_PATTERNS = [
    ("CN_BUY", re.compile(r"建议\s*买入|推荐\s*买入|买入评级|应当\s*买入")),
    ("CN_SELL", re.compile(r"建议\s*卖出|推荐\s*卖出|卖出评级|应当\s*卖出")),
    ("CN_HOLD", re.compile(r"建议\s*持有|持有评级|应当\s*持有")),
    ("CN_POSITION", re.compile(r"建议\s*仓位|仓位\s*\d+%")),
    ("CN_STOP", re.compile(r"止损|止盈")),
    ("CN_TARGET", re.compile(r"目标价\s*(为|:|：)")),
    ("EN_BUY_RATING", re.compile(r"\bbuy rating\b", re.IGNORECASE)),
    ("EN_SELL_RATING", re.compile(r"\bsell rating\b", re.IGNORECASE)),
    ("EN_HOLD_RATING", re.compile(r"\bhold rating\b", re.IGNORECASE)),
    ("EN_PRICE_TARGET", re.compile(r"\bprice target\s*(is|:)", re.IGNORECASE)),
    ("EN_POSITION", re.compile(r"\bposition sizing recommendation\b", re.IGNORECASE)),
    ("EN_STOP", re.compile(r"\bstop-loss at\b|\btake-profit at\b", re.IGNORECASE)),
]


def normalize_stock_code(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if text.isdigit() and len(text) < 6:
        return text.zfill(6)
    return text


def is_blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def is_todo_value(value: Any) -> bool:
    text = "" if value is None else str(value).strip().upper()
    return text == "" or text.startswith(TODO_PREFIXES) or text in {"TODO", "MISSING", "NOT_APPLICABLE", "N/A"}


def status_bucket(value: Any) -> str:
    text = "" if value is None else str(value).strip().lower()
    if not text:
        return "todo"
    if text in READY_STATUSES:
        return "ready"
    if text in PARTIAL_STATUSES:
        return "partial"
    if text.upper().startswith(TODO_PREFIXES):
        return "todo"
    if text in {"todo", "not_acquired", "not_assessable"}:
        return "todo"
    return "partial"


def parse_date(value: Any) -> date | None:
    if is_todo_value(value):
        return None
    text = str(value).strip()
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


class ValuationInputValidator:
    def __init__(self, workflow_run: Path, repo_root: Path | None = None) -> None:
        self.repo_root = (repo_root or Path.cwd()).resolve()
        self.workflow_run = workflow_run if workflow_run.is_absolute() else (self.repo_root / workflow_run)
        self.workflow_run = self.workflow_run.resolve()
        self.issues: list[dict[str, Any]] = []
        self.notes: list[str] = []
        self.identity: dict[str, str] = {}

    def add_issue(self, severity: str, code: str, message: str, path: Path | None = None) -> None:
        self.issues.append(
            {
                "severity": severity,
                "code": code,
                "message": message,
                "path": self.display_path(path) if path else "",
            }
        )

    def display_path(self, path: Path | None) -> str:
        if path is None:
            return ""
        try:
            return path.resolve().relative_to(self.repo_root).as_posix()
        except ValueError:
            return path.resolve().as_posix()

    def resolve_path(self, value: Any) -> Path:
        text = "" if value is None else str(value).strip()
        path = Path(text)
        if path.is_absolute():
            return path
        candidate = (self.repo_root / path).resolve()
        if candidate.exists() or text.startswith("reports/") or text.startswith(".agents/"):
            return candidate
        return (self.workflow_run / path).resolve()

    def load_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            self.add_issue("high", "FILE_MISSING", "Required YAML file is missing.", path)
            return {}
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:  # noqa: BLE001
            self.add_issue("high", "YAML_PARSE_ERROR", f"YAML parse failed: {exc}", path)
            return {}
        if not isinstance(data, dict):
            self.add_issue("high", "YAML_ROOT_TYPE", "YAML root must be a mapping.", path)
            return {}
        return data

    def read_csv(self, path: Path, required_columns: list[str]) -> list[dict[str, str]]:
        if not path.exists():
            self.add_issue("high", "FILE_MISSING", "Required CSV file is missing.", path)
            return []
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                fieldnames = reader.fieldnames or []
                missing = [column for column in required_columns if column not in fieldnames]
                if missing:
                    self.add_issue("high", "CSV_MISSING_COLUMNS", f"Missing columns: {', '.join(missing)}", path)
                rows = []
                for index, row in enumerate(reader, start=2):
                    if None in row:
                        self.add_issue("high", "CSV_EXTRA_FIELDS", f"Row {index} has extra fields.", path)
                    rows.append({key: "" if value is None else value for key, value in row.items() if key is not None})
                return rows
        except Exception as exc:  # noqa: BLE001
            self.add_issue("high", "CSV_PARSE_ERROR", f"CSV parse failed: {exc}", path)
            return []

    def validate(self) -> dict[str, Any]:
        if not self.workflow_run.exists():
            self.add_issue("high", "WORKFLOW_RUN_MISSING", "Workflow run directory is missing.", self.workflow_run)
            return self.result()

        request_path = self.workflow_run / "valuation_request.yaml"
        request_doc = self.load_yaml(request_path)
        request = request_doc.get("valuation_request", {}) if isinstance(request_doc, dict) else {}
        if not isinstance(request, dict):
            self.add_issue("high", "VALUATION_REQUEST_ROOT", "valuation_request root is missing.", request_path)
            request = {}

        pack_path = self.workflow_run / "stock_analysis_pack.yaml"
        pack_doc = self.load_yaml(pack_path)
        self.set_identity(request, pack_doc)

        input_paths = request.get("input_paths", {}) if isinstance(request.get("input_paths", {}), dict) else {}
        market_path = self.resolve_path(input_paths.get("market_snapshot", "market_snapshot.csv"))
        peer_path = self.resolve_path(input_paths.get("peer_market_snapshot", "peer_market_snapshot.csv"))
        financial_path = self.resolve_path(input_paths.get("financial_metric_pack", "financial_metric_pack.csv"))
        readiness_path = self.resolve_path(input_paths.get("valuation_input_readiness", "valuation_input_readiness.yaml"))

        self.validate_market_snapshot(market_path)
        self.validate_peer_market_snapshot(peer_path)
        self.validate_financial_metric_pack(financial_path)
        self.validate_readiness(readiness_path)
        self.validate_request(request, request_path)
        self.scan_no_advice([request_path, market_path, peer_path, financial_path, readiness_path])

        return self.result()

    def set_identity(self, request: dict[str, Any], pack_doc: dict[str, Any]) -> None:
        stock_code = request.get("stock_code")
        company_id = request.get("company_id")
        if isinstance(pack_doc, dict):
            stock_code = stock_code or pack_doc.get("stock_code")
            company_id = company_id or pack_doc.get("company_id")
        self.identity = {
            "stock_code": normalize_stock_code(stock_code),
            "company_id": "" if company_id is None else str(company_id).strip(),
        }
        if not self.identity["stock_code"]:
            self.add_issue("high", "IDENTITY_MISSING", "stock_code is missing from valuation_request and stock_analysis_pack.")
        if not self.identity["company_id"]:
            self.add_issue("high", "IDENTITY_MISSING", "company_id is missing from valuation_request and stock_analysis_pack.")

    def validate_request(self, request: dict[str, Any], path: Path) -> None:
        if request.get("no_advice_boundary") is not True:
            self.add_issue("high", "NO_ADVICE_BOUNDARY", "valuation_request.no_advice_boundary must be true.", path)
        as_of_date = parse_date(request.get("as_of_date"))
        if request.get("as_of_date") and as_of_date is None:
            self.add_issue("high", "DATE_PARSE_ERROR", "valuation_request.as_of_date must be YYYY-MM-DD.", path)
        self.check_not_future(as_of_date, path, "valuation_request.as_of_date")
        input_paths = request.get("input_paths", {})
        if not isinstance(input_paths, dict) or "valuation_input_readiness" not in input_paths:
            self.add_issue("medium", "READINESS_PATH_MISSING", "valuation_request should include input_paths.valuation_input_readiness.", path)

    def validate_market_snapshot(self, path: Path) -> None:
        rows = self.read_csv(path, MARKET_COLUMNS)
        if not rows:
            self.add_issue("medium", "CSV_EMPTY", "market_snapshot.csv has no rows; use a TODO row when data is unavailable.", path)
            return
        for index, row in enumerate(rows, start=2):
            self.check_identity(row.get("stock_code"), row.get("company_id"), path, index)
            self.check_not_future(parse_date(row.get("as_of_date")), path, f"row {index} as_of_date")
            bucket = status_bucket(row.get("snapshot_status"))
            has_numeric = any(not is_todo_value(row.get(column)) for column in MARKET_NUMERIC_COLUMNS)
            if has_numeric or bucket in {"ready", "partial"}:
                self.require_fields(row, ["source_name", "source_type", "source_path", "as_of_date", "currency", "limitations"], path, index)
            if bucket == "todo":
                self.notes.append("market_snapshot.csv keeps explicit market-data TODO rows.")

    def validate_peer_market_snapshot(self, path: Path) -> None:
        rows = self.read_csv(path, PEER_COLUMNS)
        if not rows:
            self.add_issue("medium", "CSV_EMPTY", "peer_market_snapshot.csv has no rows; use a TODO row when data is unavailable.", path)
            return
        for index, row in enumerate(rows, start=2):
            self.check_identity(row.get("subject_stock_code"), row.get("subject_company_id"), path, index)
            self.check_not_future(parse_date(row.get("as_of_date")), path, f"row {index} as_of_date")
            bucket = status_bucket(row.get("confidence"))
            if bucket in {"ready", "partial"} and not is_todo_value(row.get("peer_company")):
                self.require_fields(
                    row,
                    [
                        "peer_company",
                        "peer_stock_code",
                        "peer_selection_reason",
                        "business_similarity",
                        "segment_overlap",
                        "source_name",
                        "source_type",
                        "source_path",
                        "limitations",
                    ],
                    path,
                    index,
                )
            else:
                self.notes.append("peer_market_snapshot.csv keeps explicit peer-data TODO rows.")

    def validate_financial_metric_pack(self, path: Path) -> None:
        rows = self.read_csv(path, FINANCIAL_COLUMNS)
        if not rows:
            self.add_issue("medium", "CSV_EMPTY", "financial_metric_pack.csv has no rows.", path)
            return
        for index, row in enumerate(rows, start=2):
            self.check_identity(row.get("stock_code"), row.get("company_id"), path, index)
            bucket = status_bucket(row.get("review_status"))
            if bucket in {"ready", "partial"}:
                self.require_fields(
                    row,
                    [
                        "metric_id",
                        "metric_name",
                        "period",
                        "value",
                        "unit",
                        "currency",
                        "source_evidence_id",
                        "source_path",
                        "calculation_method",
                        "claim_type",
                        "confidence",
                        "review_status",
                        "limitations",
                    ],
                    path,
                    index,
                )

    def validate_readiness(self, path: Path) -> None:
        data = self.load_yaml(path)
        root = data.get("valuation_input_readiness") if isinstance(data, dict) else None
        if not isinstance(root, dict):
            self.add_issue("high", "READINESS_ROOT", "valuation_input_readiness root is missing.", path)
            return
        self.check_identity(root.get("stock_code"), root.get("company_id"), path, 1)
        if root.get("no_advice_boundary") is not True:
            self.add_issue("high", "NO_ADVICE_BOUNDARY", "valuation_input_readiness.no_advice_boundary must be true.", path)
        self.check_not_future(parse_date(root.get("as_of_date")), path, "valuation_input_readiness.as_of_date")
        for key in ["input_paths", "statuses", "open_gaps"]:
            if key not in root:
                self.add_issue("high", "READINESS_FIELD_MISSING", f"valuation_input_readiness.{key} is required.", path)
        statuses = root.get("statuses", {})
        if not isinstance(statuses, dict):
            self.add_issue("high", "READINESS_STATUSES", "valuation_input_readiness.statuses must be a mapping.", path)
            return
        for name in ["market_snapshot", "peer_market_snapshot", "financial_metric_pack", "forecast_model"]:
            entry = statuses.get(name)
            if not isinstance(entry, dict):
                self.add_issue("high", "READINESS_STATUS_MISSING", f"statuses.{name} is required.", path)
                continue
            bucket = status_bucket(entry.get("status"))
            sources = entry.get("source_paths") or entry.get("source_metric_ids") or []
            gaps = entry.get("open_gaps") or []
            if bucket in {"ready", "partial"} and not sources:
                self.add_issue("high", "READY_WITHOUT_SOURCE", f"statuses.{name} is {entry.get('status')} but has no source paths or metric ids.", path)
            if bucket == "todo" and not gaps:
                self.add_issue("medium", "TODO_WITHOUT_GAP", f"statuses.{name} is TODO-like but has no open_gaps.", path)
            if entry.get("limitations") is None:
                self.add_issue("medium", "LIMITATIONS_MISSING", f"statuses.{name}.limitations should be present.", path)

    def check_identity(self, stock_code: Any, company_id: Any, path: Path, row_index: int) -> None:
        expected_stock = self.identity.get("stock_code")
        expected_company = self.identity.get("company_id")
        actual_stock = normalize_stock_code(stock_code)
        actual_company = "" if company_id is None else str(company_id).strip()
        if expected_stock and actual_stock and actual_stock != expected_stock:
            self.add_issue("high", "IDENTITY_MISMATCH", f"Row {row_index} stock_code {actual_stock} != {expected_stock}.", path)
        if expected_company and actual_company and actual_company != expected_company:
            self.add_issue("high", "IDENTITY_MISMATCH", f"Row {row_index} company_id {actual_company} != {expected_company}.", path)

    def require_fields(self, row: dict[str, Any], fields: list[str], path: Path, row_index: int) -> None:
        missing = [field for field in fields if is_blank(row.get(field))]
        if missing:
            self.add_issue("high", "READY_SOURCE_FIELDS_MISSING", f"Row {row_index} missing fields: {', '.join(missing)}", path)

    def check_not_future(self, parsed: date | None, path: Path, label: str) -> None:
        if parsed is not None and parsed > date.today():
            self.add_issue("high", "FUTURE_DATE", f"{label} is in the future: {parsed.isoformat()}.", path)

    def scan_no_advice(self, paths: list[Path]) -> None:
        for path in paths:
            if not path.exists() or path.is_dir():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = path.read_text(encoding="utf-8-sig")
            for code, pattern in ADVICE_PATTERNS:
                if pattern.search(text):
                    self.add_issue("high", "NO_ADVICE_VIOLATION", f"Prohibited advice pattern detected: {code}.", path)

    def result(self) -> dict[str, Any]:
        high_count = sum(1 for issue in self.issues if issue["severity"] == "high")
        medium_count = sum(1 for issue in self.issues if issue["severity"] == "medium")
        if high_count:
            status = "needs_fix"
        elif medium_count or self.notes:
            status = "accepted_with_todos"
        else:
            status = "accepted"
        return {
            "status": status,
            "workflow_run": self.display_path(self.workflow_run),
            "issue_counts": {
                "high": high_count,
                "medium": medium_count,
                "low": sum(1 for issue in self.issues if issue["severity"] == "low"),
            },
            "issues": self.issues,
            "notes": sorted(set(self.notes)),
        }


def write_outputs(workflow_run: Path, result: dict[str, Any]) -> None:
    json_path = workflow_run / "valuation_input_validation.json"
    md_path = workflow_run / "valuation_input_validation.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Valuation Input Validation",
        "",
        f"status: {result['status']}",
        "",
        "## Issue Counts",
        "",
        "| severity | count |",
        "|---|---:|",
    ]
    for severity, count in result["issue_counts"].items():
        lines.append(f"| {severity} | {count} |")
    lines.extend(["", "## Issues", ""])
    if result["issues"]:
        lines.extend(["| severity | code | path | message |", "|---|---|---|---|"])
        for issue in result["issues"]:
            message = str(issue["message"]).replace("|", "\\|")
            lines.append(f"| {issue['severity']} | {issue['code']} | `{issue['path']}` | {message} |")
    else:
        lines.append("No blocking issues found.")
    lines.extend(["", "## Notes", ""])
    if result["notes"]:
        for note in result["notes"]:
            lines.append(f"- {note}")
    else:
        lines.append("- No TODO notes.")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate stock-deep-dive valuation input handoff files.")
    parser.add_argument("--workflow-run", required=True, help="Path to reports/workflow_runs/<workflow_id>.")
    args = parser.parse_args(argv)

    workflow_run = Path(args.workflow_run)
    validator = ValuationInputValidator(workflow_run)
    result = validator.validate()
    resolved_run = validator.workflow_run
    if resolved_run.exists():
        write_outputs(resolved_run, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["status"] == "needs_fix" else 0


if __name__ == "__main__":
    sys.exit(main())
