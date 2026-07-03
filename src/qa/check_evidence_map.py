from __future__ import annotations

from pathlib import Path


def check_evidence_map(report_path: Path, evidence_map_path: Path | None = None) -> list[str]:
    report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    issues: list[str] = []
    if "Evidence Map" not in report_text and "附录 A" not in report_text:
        issues.append("report_missing_evidence_map_section")
    if evidence_map_path and (not evidence_map_path.exists() or evidence_map_path.stat().st_size == 0):
        issues.append("evidence_map_file_missing_or_empty")
    if "claim_id" not in report_text and "metric_id" not in report_text:
        issues.append("report_missing_claim_or_metric_ids")
    return issues
