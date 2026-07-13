from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.report.r5_reader_report_writer import (  # noqa: E402
    SECTION_HEADINGS,
    build_reader_report,
    build_traceability_appendix,
    load_yaml,
    validate_citations,
)


FORBIDDEN = {
    "raw_internal_id": re.compile(r"(?:ev_|claim_(?:id|cn)_|metric_(?:id|cn)_|assumption_id|r5_b[0-9]_)[A-Za-z0-9_]+", re.I),
    "internal_path": re.compile(r"(?:reports/workflow_runs|data/manifests|data/raw|data/processed|\.agents/skills)/[^\s`)>]+", re.I),
    "raw_gap_token": re.compile(r"\b(?:TODO|MISSING|LOW_CONFIDENCE|UNREVIEWED|UNVERIFIED)(?:_[A-Z0-9_]+)?\b", re.I),
    "direct_advice": re.compile(r"(?:买入|卖出|持有评级|建议仓位|加仓|减仓|目标价|保证收益)"),
}


def issue(severity: str, path: str, description: str) -> dict[str, str]:
    return {"severity": severity, "path": path, "description": description}


def validate_pack(data: Mapping[str, Any], repo_root: Path = ROOT) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if data.get("artifact_type") != "R5_reader_report_pack":
        issues.append(issue("high", "artifact_type", "artifact_type must be R5_reader_report_pack"))
    metadata = data.get("metadata")
    if not isinstance(metadata, Mapping):
        issues.append(issue("high", "metadata", "metadata must be a mapping"))
        metadata = {}
    for field in ("workflow_id", "company_id", "company_name", "stock_code", "cutoff_date", "human_review_status"):
        if not metadata.get(field):
            issues.append(issue("high", f"metadata.{field}", f"{field} is required"))
    if metadata.get("human_review_status") != "pending":
        issues.append(issue("high", "metadata.human_review_status", "automated writer pack must keep external review pending"))
    if metadata.get("sample_quality_report_allowed") is not False or metadata.get("p2_allowed") is not False:
        issues.append(issue("high", "metadata", "sample-quality and P2 permissions must remain false"))
    if data.get("no_advice_boundary") is not True:
        issues.append(issue("high", "no_advice_boundary", "no_advice_boundary must be true"))

    sections = data.get("sections")
    if not isinstance(sections, list):
        issues.append(issue("high", "sections", "sections must be a list"))
        sections = []
    section_ids = [str(row.get("section_id")) for row in sections if isinstance(row, Mapping)]
    if set(section_ids) != set(SECTION_HEADINGS) or len(section_ids) != len(set(section_ids)):
        issues.append(issue("high", "sections", "exactly ten unique canonical sections are required"))
    used_refs: set[str] = set()
    for index, row in enumerate(sections):
        if not isinstance(row, Mapping):
            issues.append(issue("high", f"sections[{index}]", "section must be a mapping"))
            continue
        if not row.get("judgment") or not row.get("judgment_refs"):
            issues.append(issue("high", f"sections[{index}]", "judgment and judgment_refs are required"))
        used_refs.update(str(ref) for ref in row.get("judgment_refs") or [])
        blocks = row.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            issues.append(issue("high", f"sections[{index}].blocks", "at least one content block is required"))
            continue
        for block_index, block in enumerate(blocks):
            if not isinstance(block, Mapping):
                issues.append(issue("high", f"sections[{index}].blocks[{block_index}]", "block must be a mapping"))
                continue
            used_refs.update(str(ref) for ref in block.get("refs") or [])
            for item in block.get("items") or []:
                if isinstance(item, Mapping):
                    used_refs.update(str(ref) for ref in item.get("refs") or [])

    records = data.get("traceability_records")
    if not isinstance(records, list) or not records:
        issues.append(issue("high", "traceability_records", "traceability records are required"))
        records = []
    record_refs = [str(row.get("display_reference_id")) for row in records if isinstance(row, Mapping)]
    if len(record_refs) != len(set(record_refs)):
        issues.append(issue("high", "traceability_records", "display reference IDs must be unique"))
    missing_refs = sorted(used_refs - set(record_refs))
    if missing_refs:
        issues.append(issue("high", "traceability_records", f"used references are missing: {missing_refs}"))
    required_record_fields = {
        "display_reference_id", "claim_type", "claim_summary", "period", "raw_evidence_ids",
        "source_category", "source_path", "method", "confidence", "limitation", "reviewer_state",
        "conflict_or_staleness_status",
    }
    for index, row in enumerate(records):
        if not isinstance(row, Mapping):
            issues.append(issue("high", f"traceability_records[{index}]", "record must be a mapping"))
            continue
        missing = sorted(field for field in required_record_fields if field not in row or row.get(field) in ("", []))
        if missing:
            issues.append(issue("high", f"traceability_records[{index}]", f"missing fields: {missing}"))
        source_path = str(row.get("source_path") or "")
        if source_path and not Path(source_path).is_absolute() and not (repo_root / source_path).exists():
            issues.append(issue("high", f"traceability_records[{index}].source_path", f"source path does not exist: {source_path}"))

    try:
        report = build_reader_report(data)
        appendix = build_traceability_appendix(data)
        unresolved = validate_citations(report, appendix)
        if unresolved:
            issues.append(issue("high", "citations", f"unresolved citations: {unresolved}"))
        for name, pattern in FORBIDDEN.items():
            match = pattern.search(report)
            if match:
                issues.append(issue("high", f"rendered_report.{name}", f"forbidden visible text: {match.group(0)}"))
    except Exception as exc:  # noqa: BLE001
        issues.append(issue("high", "render", f"pack render failed: {exc}"))
    return issues


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a pack-driven R5 reader report input.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        issues = validate_pack(load_yaml(args.path), args.repo_root.resolve())
    except Exception as exc:  # noqa: BLE001
        issues = [issue("high", str(args.path), f"failed to load pack: {exc}")]
    decision = "accepted" if not issues else "blocked"
    print(json.dumps({"decision": decision, "issues": issues}, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
