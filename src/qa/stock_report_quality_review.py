from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Sequence

import yaml

from check_evidence_map import check_evidence_map
from check_forecast_valuation import check_forecast_and_valuation
from check_no_unsupported_advice import find_unsupported_advice


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_yaml(path: Path) -> object:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def _issue(
    issue_id: str,
    severity: str,
    gate_id: str,
    subcheck_id: str,
    stage: str,
    target_artifact: str,
    description: str,
    owner: str,
) -> dict[str, str]:
    return {
        "issue_id": issue_id,
        "severity": severity,
        "gate_id": gate_id,
        "subcheck_id": subcheck_id,
        "stage": stage,
        "target_artifact": target_artifact,
        "description": description,
        "fix_owner_skill": owner,
        "status": "open",
    }


def review_stock_report(run_dir: Path) -> dict[str, object]:
    report_path = run_dir / "stock_report_sample_quality_draft.md"
    report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    pack = _load_yaml(run_dir / "stock_analysis_pack.yaml")
    claims = _read_csv(run_dir / "claims_registry.csv")
    metrics = _read_csv(run_dir / "metrics_registry.csv")
    issues: list[dict[str, str]] = []

    evidence_map_issues = check_evidence_map(report_path, run_dir / "report_evidence_map.md")
    for index, item in enumerate(evidence_map_issues, start=1):
        issues.append(_issue(f"SRQR-G1-{index}", "high", "G1", "SRQ1", "T9", str(report_path), item, "stock-deep-dive"))

    for index, claim in enumerate(claims, start=1):
        if not claim.get("evidence_id"):
            issues.append(_issue(f"SRQR-G2-{index}", "high", "G2", "SRQ2", "T9", "claims_registry.csv", "claim missing evidence_id", "quality-review"))
        if not claim.get("quote_or_excerpt"):
            issues.append(_issue(f"SRQR-G2Q-{index}", "high", "G2", "SRQ2", "T9", "claims_registry.csv", "claim missing quote_or_excerpt", "quality-review"))
        if not claim.get("page_no_or_section"):
            issues.append(_issue(f"SRQR-G2L-{index}", "high", "G2", "SRQ2", "T9", "claims_registry.csv", "claim missing locator", "quality-review"))
    if not claims:
        issues.append(_issue("SRQR-G2-EMPTY", "high", "G2", "SRQ2", "T9", "claims_registry.csv", "no reviewed claims", "quality-review"))

    for index, metric in enumerate(metrics, start=1):
        missing = [field for field in ("period", "value", "unit", "source_evidence_id") if not metric.get(field)]
        if missing:
            issues.append(_issue(f"SRQR-G3-{index}", "high", "G3", "SRQ3", "T9", "metrics_registry.csv", f"metric missing {','.join(missing)}", "quality-review"))

    business = pack.get("business_breakdown", {}) if isinstance(pack, dict) else {}
    for line in business.get("business_lines", []) if isinstance(business.get("business_lines"), list) else []:
        revenue = str(line.get("revenue", ""))
        if revenue not in {"MISSING_DISCLOSURE", "TODO_SOURCE_REQUIRED"} and not line.get("claim_ids"):
            issues.append(_issue("SRQR-G7-SRQ4-1", "high", "G7", "SRQ4", "T9", "business_breakdown.yaml", "business revenue lacks claim support", "stock-deep-dive"))

    for link in business.get("segment_links", []) if isinstance(business.get("segment_links"), list) else []:
        score = int(link.get("exposure_score", 0) or 0)
        if score >= 4 and not link.get("claim_ids"):
            issues.append(_issue("SRQR-G6-SRQ5-1", "high", "G6", "SRQ5", "T9", "segment_exposure_draft.yaml", "high exposure score lacks claim support", "segment-company-mapping"))

    for index, item in enumerate(
        check_forecast_and_valuation(
            run_dir / "forecast_model.yaml",
            run_dir / "valuation_model.yaml",
            run_dir / "peer_comparison.csv",
        ),
        start=1,
    ):
        issues.append(_issue(f"SRQR-G7-SRQ6-SRQ7-{index}", "high", "G7", "SRQ6/SRQ7", "T9", "forecast_or_valuation", item, "stock-deep-dive"))

    technical = pack.get("technical_sentiment_event", {}) if isinstance(pack, dict) else {}
    tech_snapshot = technical.get("technical_snapshot", {}) if isinstance(technical, dict) else {}
    if not tech_snapshot.get("as_of_date"):
        issues.append(_issue("SRQR-G7-SRQ8-1", "high", "G7", "SRQ8", "T9", "technical_snapshot.yaml", "technical section lacks data date", "stock-deep-dive"))

    for index, pattern in enumerate(find_unsupported_advice(report_text), start=1):
        issues.append(_issue(f"SRQR-G9-SRQ10-{index}", "high", "G9", "SRQ10", "T9", str(report_path), f"unsupported advice pattern: {pattern}", "stock-deep-dive"))

    if not (run_dir / "backflow_decision.yaml").exists():
        issues.append(_issue("SRQR-G8-SRQ11-1", "high", "G8", "SRQ11", "T10", "backflow_decision.yaml", "backflow decision missing", "maintenance"))

    high_count = sum(1 for issue in issues if issue["severity"] == "high")
    medium_count = sum(1 for issue in issues if issue["severity"] == "medium")
    status = "accepted_sample_quality" if high_count == 0 and medium_count == 0 else "needs_fix"

    issue_md = ["# Quality Issue List", "", "| issue_id | severity | gate_id | subcheck_id | target_artifact | description | status |", "|---|---|---|---|---|---|---|"]
    if issues:
        for issue in issues:
            issue_md.append(
                f"| {issue['issue_id']} | {issue['severity']} | {issue['gate_id']} | {issue['subcheck_id']} | {issue['target_artifact']} | {issue['description']} | {issue['status']} |"
            )
    else:
        issue_md.append("| none | none | all | all | stock_report_sample_quality_draft.md | no high or medium issues | closed |")
    (run_dir / "quality_issue_list.md").write_text("\n".join(issue_md) + "\n", encoding="utf-8")

    gate_rows = [
        ("G1 Evidence Completeness / SRQ1", "pass" if not any(i["subcheck_id"] == "SRQ1" for i in issues) else "fail"),
        ("G2 Claim Locator / SRQ2", "pass" if not any(i["subcheck_id"] == "SRQ2" for i in issues) else "fail"),
        ("G3 Metric Normalization / SRQ3", "pass" if not any(i["subcheck_id"] == "SRQ3" for i in issues) else "fail"),
        ("G7 Business Breakdown / SRQ4", "pass" if not any(i["subcheck_id"] == "SRQ4" for i in issues) else "fail"),
        ("G6 Segment Exposure / SRQ5", "pass" if not any(i["subcheck_id"] == "SRQ5" for i in issues) else "fail"),
        ("G7 Forecast Valuation / SRQ6-SRQ7", "pass" if not any(i["subcheck_id"] == "SRQ6/SRQ7" for i in issues) else "fail"),
        ("G7 Technical Sentiment Event / SRQ8", "pass" if not any(i["subcheck_id"] == "SRQ8" for i in issues) else "fail"),
        ("G9 No Unsupported Advice / SRQ10", "pass" if not any(i["subcheck_id"] == "SRQ10" for i in issues) else "fail"),
        ("G8 Backflow Maintenance / SRQ11", "pass" if not any(i["subcheck_id"] == "SRQ11" for i in issues) else "fail"),
    ]
    report_md = ["# Quality Gate Report", "", f"final_status: {status}", f"high_issues: {high_count}", f"medium_issues: {medium_count}", "", "| gate | status |", "|---|---|"]
    report_md.extend(f"| {gate} | {gate_status} |" for gate, gate_status in gate_rows)
    (run_dir / "quality_gate_report.md").write_text("\n".join(report_md) + "\n", encoding="utf-8")
    checklist = {
        "final_status": status,
        "high_issues": high_count,
        "medium_issues": medium_count,
        "gates": [{"gate": gate, "status": gate_status} for gate, gate_status in gate_rows],
    }
    (run_dir / "stock_report_acceptance_checklist.yaml").write_text(
        yaml.safe_dump(checklist, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return checklist


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run stock report quality gates v2.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)
    print(yaml.safe_dump(review_stock_report(Path(args.run_dir)), allow_unicode=True, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
