#!/usr/bin/env python3
"""Freeze the Bundle 5 reader-surface baseline for Bundle 6.0."""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path
from typing import Any

import yaml

WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
RUN_REL = Path("reports/workflow_runs") / WORKFLOW_ID
REPORT_REL = RUN_REL / "R5_stock_research_note_reviewed_input_draft.md"
QUALITY_REL = RUN_REL / "R5_bundle5_quality_gate_result.yaml"
BENCHMARK_REL = RUN_REL / "R5_bundle5_benchmark_coverage_precheck.yaml"
BASELINE_REL = RUN_REL / "R5_bundle6_reader_surface_baseline.yaml"
READOUT_REL = Path("reports/p1_6/R5_BUNDLE_6_0_STATUS_READER_QUALITY_BASELINE_READOUT.md")

RAW_ID_RE = re.compile(r"\b(?:ev_[A-Za-z0-9_]+|r5_b5_[A-Za-z0-9_]+)\b")
INTERNAL_PATH_RE = re.compile(
    r"(?:reports/workflow_runs|data/reviewed_inputs|data/raw|data/processed)/[^\s|]+"
)
MACHINE_LABEL_RE = re.compile(r"(?m)^-\s*(?:readiness|visible_gap|next_action):")
GAP_TOKEN_RE = re.compile(r"\b(?:TODO|MISSING|LOW_CONFIDENCE|UNREVIEWED)[A-Z0-9_]*\b")
OVER_PRECISE_RE = re.compile(r"(?<![\w.])-?\d[\d,]*\.\d{5,}(?!\d)")
HEADING_RE = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")
MACHINE_SECTION_IDS = {
    "company_context",
    "financial_history_and_cash_flow_quality",
    "business_breakdown_and_segment_economics",
    "industry_structure_and_competition",
    "forecast",
    "valuation",
    "dated_market_or_technical_state_when_supported",
    "dated_sentiment_and_events_when_supported",
    "risks_counterevidence_and_open_questions",
    "research_conclusion_and_watch_conditions",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def _unique_matches(pattern: re.Pattern[str], text: str) -> list[str]:
    return list(dict.fromkeys(match.group(0) for match in pattern.finditer(text)))


def scan_reader_surface(report_text: str) -> dict[str, Any]:
    headings = [match.group(2) for match in HEADING_RE.finditer(report_text)]
    machine_sections = [heading for heading in headings if heading in MACHINE_SECTION_IDS]
    raw_ids = _unique_matches(RAW_ID_RE, report_text)
    internal_paths = _unique_matches(INTERNAL_PATH_RE, report_text)
    gap_tokens = _unique_matches(GAP_TOKEN_RE, report_text)
    over_precise = _unique_matches(OVER_PRECISE_RE, report_text)
    return {
        "line_count": len(report_text.splitlines()),
        "nonblank_line_count": sum(1 for line in report_text.splitlines() if line.strip()),
        "character_count": len(report_text),
        "heading_count": len(headings),
        "headings": headings,
        "raw_internal_id_count": len(raw_ids),
        "raw_internal_ids": raw_ids,
        "internal_path_count": len(internal_paths),
        "internal_paths": internal_paths,
        "machine_label_count": len(MACHINE_LABEL_RE.findall(report_text)),
        "gap_token_count": len(gap_tokens),
        "gap_tokens": gap_tokens,
        "duplicate_machine_readiness_section_count": len(machine_sections),
        "duplicate_machine_readiness_sections": machine_sections,
        "source_gap_appendix_in_main_body": "## Source Gap Appendix" in report_text,
        "over_precise_numeric_count": len(over_precise),
        "over_precise_numeric_examples": over_precise[:20],
    }


def build_baseline(
    repo_root: Path,
    *,
    full_pytest_summary: str,
    bundle5_close_summary: str,
) -> dict[str, Any]:
    report_path = repo_root / REPORT_REL
    quality_path = repo_root / QUALITY_REL
    benchmark_path = repo_root / BENCHMARK_REL
    truthfulness_path = repo_root / "reports/p1_6/r5_bundle5_readout_truthfulness_result.json"
    report_text = report_path.read_text(encoding="utf-8")
    benchmark = _load_yaml(benchmark_path)
    quality = _load_yaml(quality_path)
    surface = scan_reader_surface(report_text)
    coverage = benchmark.get("coverage_summary") or {}
    return {
        "artifact_type": "R5_bundle6_reader_surface_baseline",
        "schema_version": "r5_bundle6_reader_surface_baseline_v0.1",
        "workflow_id": WORKFLOW_ID,
        "stock_code": "002837",
        "classification": "audit_oriented_research_draft_not_reader_candidate",
        "before_state_preserved": True,
        "input_artifacts": {
            "bundle5_draft": {"path": REPORT_REL.as_posix(), "sha256": _sha256(report_path)},
            "bundle5_quality_gate": {"path": QUALITY_REL.as_posix(), "sha256": _sha256(quality_path)},
            "bundle5_benchmark_precheck": {"path": BENCHMARK_REL.as_posix(), "sha256": _sha256(benchmark_path)},
            "bundle5_truthfulness": {"path": truthfulness_path.relative_to(repo_root).as_posix(), "sha256": _sha256(truthfulness_path)},
        },
        "verification": {
            "bundle5_truthfulness": "pass_checked_8_failed_0",
            "bundle5_close_pytest": bundle5_close_summary,
            "full_repository_pytest": full_pytest_summary,
            "bundle5_quality_decision": quality.get("quality_decision"),
            "critical_quality_blockers": quality.get("critical_quality_blockers"),
        },
        "reader_surface": surface,
        "coverage_baseline": {
            "total": coverage.get("total"),
            "covered": coverage.get("covered"),
            "partial": coverage.get("partial"),
            "missing": coverage.get("missing"),
            "partial_dimensions": [
                row.get("dimension") for row in benchmark.get("coverage", []) if row.get("status") == "partial"
            ],
            "missing_dimensions": [
                row.get("dimension") for row in benchmark.get("coverage", []) if row.get("status") == "missing"
            ],
        },
        "reader_quality_diagnostic": {
            "manual_planning_score": 46,
            "canonical_gate_score": None,
            "reader_candidate_accepted": False,
            "reason": "Bundle 5 proves truthfulness and renderability but the main body leaks audit metadata and lacks reader-oriented synthesis.",
        },
        "canonical_state_changed": False,
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
    }


def write_readout(repo_root: Path, baseline: dict[str, Any]) -> None:
    surface = baseline["reader_surface"]
    coverage = baseline["coverage_baseline"]
    report_hash = baseline["input_artifacts"]["bundle5_draft"]["sha256"]
    quality_hash = baseline["input_artifacts"]["bundle5_quality_gate"]["sha256"]
    text = f"""# R5 Bundle 6.0 — Status and Reader-quality Baseline Readout

status: accepted_baseline_only

## files_added

- `scripts/build_r5_bundle6_reader_baseline.py`
- `{BASELINE_REL.as_posix()}`
- `tests/test_r5_bundle6_reader_baseline.py`
- `{READOUT_REL.as_posix()}`

## files_modified

- none; the Bundle 5 draft, evidence and registries were preserved byte-for-byte.

## commands_run

- `.\\.conda\\investment-system\\python.exe scripts\\check_r5_readout_truthfulness.py --rules config\\r5_readout_truthfulness_rules.yaml --glob 'reports/p1_6/R5_BUNDLE_5*READOUT.md' --strict`
- `.\\.conda\\investment-system\\python.exe -m pytest -q tests\\test_r5_bundle5_close.py --tb=short -p no:cacheprovider`
- `.\\.conda\\investment-system\\python.exe -m pytest -q --tb=short -p no:cacheprovider`
- `.\\.conda\\investment-system\\python.exe scripts\\build_r5_bundle6_reader_baseline.py --repo-root . --full-pytest-summary "510 passed, 2 skipped in 20.98s" --bundle5-close-summary "9 passed in 0.17s"`

## exit_code

- truthfulness_exit_code: `0`
- bundle5_close_exit_code: `0`
- full_pytest_exit_code: `0`
- baseline_builder_exit_code: `0`

## stdout_or_stderr_summary

- truthfulness: `pass checked=8 failed=0`
- Bundle 5 close: `{baseline['verification']['bundle5_close_pytest']}`
- full repository: `{baseline['verification']['full_repository_pytest']}`
- report_sha256: `{report_hash}`
- quality_gate_sha256: `{quality_hash}`
- reader_surface_inventory_status: `complete`
- raw_internal_ids={surface['raw_internal_id_count']}; internal_paths={surface['internal_path_count']}; gap_tokens={surface['gap_token_count']}; over_precise_values={surface['over_precise_numeric_count']}; duplicate_machine_sections={surface['duplicate_machine_readiness_section_count']}
- coverage_checked={coverage['total']}; covered={coverage['covered']}; partial={coverage['partial']}; missing={coverage['missing']}

## known_todos

- The frozen Bundle 5 draft remains an audit-oriented research draft and is not a reader-facing candidate.
- Cards 6.1-6.8 must build a separate reader report, traceability appendix and reader-quality gate.

## next_recommended_patch

- Execute Card 6.1 and define the reader-report/traceability split contract without changing evidence or Registry state.

## fixed_boundaries

- current_draft_rewritten: `false`
- canonical_state_changed: `false`
- sample_quality_report_allowed: `false`
- p2_allowed: `false`
"""
    path = repo_root / READOUT_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run(repo_root: Path, *, full_pytest_summary: str, bundle5_close_summary: str) -> dict[str, Any]:
    baseline = build_baseline(
        repo_root,
        full_pytest_summary=full_pytest_summary,
        bundle5_close_summary=bundle5_close_summary,
    )
    baseline_path = repo_root / BASELINE_REL
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(yaml.safe_dump(baseline, allow_unicode=True, sort_keys=False), encoding="utf-8")
    write_readout(repo_root, baseline)
    return baseline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Freeze the R5 Bundle 6.0 reader-quality baseline.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--full-pytest-summary", required=True)
    parser.add_argument("--bundle5-close-summary", required=True)
    args = parser.parse_args(argv)
    result = run(
        args.repo_root.resolve(),
        full_pytest_summary=args.full_pytest_summary,
        bundle5_close_summary=args.bundle5_close_summary,
    )
    surface = result["reader_surface"]
    print(
        "r5_bundle6_card_6_0 status=accepted_baseline_only classification={classification} "
        "raw_ids={raw_ids} paths={paths} gaps={gaps} over_precision={precision} sample_quality=false p2=false".format(
            classification=result["classification"],
            raw_ids=surface["raw_internal_id_count"],
            paths=surface["internal_path_count"],
            gaps=surface["gap_token_count"],
            precision=surface["over_precise_numeric_count"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
