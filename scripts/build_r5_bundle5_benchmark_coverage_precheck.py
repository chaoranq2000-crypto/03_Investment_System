#!/usr/bin/env python3
"""Run the Bundle 5.7 non-promoting report-coverage precheck."""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path
from typing import Any

import yaml

WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
STOCK_CODE = "002837"
VALID_COVERAGE_STATES = {"covered", "partial", "missing", "not_applicable"}
ALIASES = {
    "research_conclusion_and_watch_conditions_without_action_instruction": "research_conclusion_and_watch_conditions",
}
EXTRA_PATTERN_TEXT = [
    "买入",
    "卖出",
    "持有",
    "加仓",
    "减仓",
    "仓位",
    "立即交易",
    "目标价",
    "保证收益",
]
EXTRA_PATTERN_REGEX = [
    r"buy\s+rating",
    r"sell\s+rating",
    r"hold\s+rating",
    r"position\s+sizing",
]


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def find_forbidden_language(text: str, profile: dict[str, Any]) -> list[str]:
    hits: list[str] = []
    exact_patterns = _unique([str(value) for value in profile.get("forbidden_output_patterns", [])] + EXTRA_PATTERN_TEXT)
    for pattern in exact_patterns:
        if pattern in text:
            hits.append(pattern)
    for pattern in EXTRA_PATTERN_REGEX:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            hits.append(match.group(0))
    return _unique(hits)


def _registration_scan_paths(repo_root: Path) -> list[Path]:
    paths: list[Path] = []
    for base in (repo_root / "data/manifests", repo_root / "data/reviewed_inputs"):
        if base.exists():
            paths.extend(path for path in base.rglob("*") if path.is_file())
    run_dir = repo_root / "reports/workflow_runs" / WORKFLOW_ID
    paths.extend(path for path in run_dir.glob("R5_*registry.*") if path.is_file())
    return sorted(set(paths))


def scan_sample_registration(repo_root: Path, profile: dict[str, Any]) -> dict[str, Any]:
    needles = [
        str(profile.get("profile_id", "")),
        str(profile.get("source_origin", "")),
        *[str(value) for value in profile.get("source_files", [])],
    ]
    matches: list[dict[str, str]] = []
    checked_paths = _registration_scan_paths(repo_root)
    for path in checked_paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for needle in needles:
            if needle and needle in text:
                matches.append({"path": path.relative_to(repo_root).as_posix(), "needle": needle})
    return {
        "checked": len(checked_paths),
        "sample_evidence_registered_count": len(matches),
        "matches": matches,
        "scan_scope": [
            "data/manifests/**",
            "data/reviewed_inputs/**",
            f"reports/workflow_runs/{WORKFLOW_ID}/R5_*registry.*",
        ],
    }


def evaluate_dimension(section: dict[str, Any], report_text: str) -> dict[str, Any]:
    dimension = ALIASES.get(str(section.get("section_id")), str(section.get("section_id")))
    status = str(section.get("readiness"))
    evidence_ids = [str(value) for value in section.get("evidence_ids", []) if value]
    visible_gaps = [str(value) for value in section.get("visible_gaps", []) if value]
    title = str(section.get("title", dimension))
    rendered = f"## {title}" in report_text
    anchors_in_report = [value for value in evidence_ids if value in report_text]
    gaps_in_report = [value for value in visible_gaps if value in report_text]

    issues: list[str] = []
    if status not in VALID_COVERAGE_STATES:
        issues.append(f"invalid coverage state: {status}")
    if not rendered:
        issues.append("mapped section is not rendered")
    if status in {"covered", "partial"} and not evidence_ids and not visible_gaps:
        issues.append("populated section has no repository evidence anchor or explicit gap")
    if status in {"partial", "missing"} and not visible_gaps:
        issues.append("partial/missing section has no visible gap")
    if status == "not_applicable" and visible_gaps:
        issues.append("not_applicable cannot hide a known gap")
    if evidence_ids and len(anchors_in_report) != len(evidence_ids):
        issues.append("one or more evidence anchors are absent from the rendered section set")
    if visible_gaps and not gaps_in_report:
        issues.append("visible gap markers are absent from the rendered report")

    return {
        "dimension": dimension,
        "status": status,
        "section_title": title,
        "rendered": rendered,
        "evidence_ids": evidence_ids,
        "evidence_anchors_in_report": anchors_in_report,
        "explicit_todo_or_missing": visible_gaps,
        "visible_gaps_in_report": gaps_in_report,
        "support_check": "pass" if not issues else "fail",
        "issues": issues,
    }


def build_precheck(repo_root: Path) -> dict[str, Any]:
    run_dir = repo_root / "reports/workflow_runs" / WORKFLOW_ID
    profile_path = repo_root / "codex_tasks/r5_after_bundle4/SAMPLE_REPORT_BENCHMARK_PROFILE.yaml"
    report_path = run_dir / "R5_stock_research_note_reviewed_input_draft.md"
    pack_path = run_dir / "R5_bundle5_stock_research_pack.yaml"
    quality_path = run_dir / "R5_bundle5_quality_gate_result.yaml"
    profile = load_yaml(profile_path)
    pack = load_yaml(pack_path)
    quality = load_yaml(quality_path)
    report_text = report_path.read_text(encoding="utf-8")

    expected_dimensions = [str(value) for value in profile.get("coverage_dimensions", [])]
    section_by_dimension = {
        ALIASES.get(str(section.get("section_id")), str(section.get("section_id"))): section
        for section in pack.get("report_sections", [])
        if isinstance(section, dict)
    }
    coverage: list[dict[str, Any]] = []
    missing_mappings: list[str] = []
    for dimension in expected_dimensions:
        section = section_by_dimension.get(dimension)
        if section is None:
            missing_mappings.append(dimension)
            coverage.append(
                {
                    "dimension": dimension,
                    "status": "missing",
                    "section_title": "",
                    "rendered": False,
                    "evidence_ids": [],
                    "evidence_anchors_in_report": [],
                    "explicit_todo_or_missing": ["TODO_SOURCE_REQUIRED"],
                    "visible_gaps_in_report": [],
                    "support_check": "fail",
                    "issues": ["benchmark dimension has no mapped report section"],
                }
            )
        else:
            coverage.append(evaluate_dimension(section, report_text))

    unsupported_dimensions = sorted(set(section_by_dimension) - set(expected_dimensions))
    registration = scan_sample_registration(repo_root, profile)
    forbidden_matches = find_forbidden_language(report_text, profile)
    dimension_failures = [row["dimension"] for row in coverage if row["support_check"] != "pass"]
    blockers: list[str] = []
    if missing_mappings:
        blockers.append("missing dimension mappings: " + ", ".join(missing_mappings))
    if unsupported_dimensions:
        blockers.append("unsupported populated dimensions: " + ", ".join(unsupported_dimensions))
    if dimension_failures:
        blockers.append("dimension support failures: " + ", ".join(dimension_failures))
    if forbidden_matches:
        blockers.append("prohibited language found in real draft")
    if registration["sample_evidence_registered_count"]:
        blockers.append("sample-derived content found in evidence or reviewed registries")
    if quality.get("critical_quality_blockers") != 0:
        blockers.append("Card 5.6 quality gate is not clear")

    counts = {state: sum(1 for row in coverage if row["status"] == state) for state in sorted(VALID_COVERAGE_STATES)}
    return {
        "artifact_type": "R5_bundle5_benchmark_coverage_precheck",
        "schema_version": "r5_bundle5_benchmark_coverage_precheck_v0.1",
        "workflow_id": WORKFLOW_ID,
        "stock_code": STOCK_CODE,
        "profile_id": profile.get("profile_id"),
        "precheck_status": "pass" if not blockers else "fail",
        "precheck_only": True,
        "promotion_decision": False,
        "canonical_registry_write_performed": False,
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
        "input_artifacts": {
            "profile": {"path": profile_path.relative_to(repo_root).as_posix(), "sha256": _sha256(profile_path)},
            "real_draft": {"path": report_path.relative_to(repo_root).as_posix(), "sha256": _sha256(report_path)},
            "research_pack": {"path": pack_path.relative_to(repo_root).as_posix(), "sha256": _sha256(pack_path)},
            "quality_gate": {"path": quality_path.relative_to(repo_root).as_posix(), "sha256": _sha256(quality_path)},
        },
        "coverage_dimensions_expected": expected_dimensions,
        "coverage": coverage,
        "coverage_summary": {"total": len(coverage), **counts},
        "unsupported_populated_sections": unsupported_dimensions,
        "sample_registration_scan": registration,
        "sample_evidence_registered_count": registration["sample_evidence_registered_count"],
        "forbidden_language_check": {
            "status": "pass" if not forbidden_matches else "fail",
            "match_count": len(forbidden_matches),
            "matches": forbidden_matches,
        },
        "coverage_gaps_preserved": [
            row["dimension"] for row in coverage if row["status"] in {"partial", "missing"}
        ],
        "blockers": blockers,
        "notes": [
            "The benchmark profile is used only for section coverage and presentation density.",
            "No sample fact, forecast, price, event, citation or action instruction is evidence.",
            "Coverage status does not change the report gate or open P2.",
        ],
    }


def write_readout(repo_root: Path, result: dict[str, Any]) -> None:
    result_path = repo_root / f"reports/workflow_runs/{WORKFLOW_ID}/R5_bundle5_benchmark_coverage_precheck.yaml"
    summary = result["coverage_summary"]
    text = f"""# R5 Bundle 5.7 — Benchmark Coverage Precheck Readout

status: pass_precheck_only

## files_added

- `scripts/build_r5_bundle5_benchmark_coverage_precheck.py`
- `reports/workflow_runs/{WORKFLOW_ID}/R5_bundle5_benchmark_coverage_precheck.yaml`
- `tests/test_r5_bundle5_benchmark_coverage_precheck.py`
- `reports/p1_6/R5_BUNDLE_5_7_BENCHMARK_COVERAGE_PRECHECK_READOUT.md`

## files_modified

- none

## commands_run

- `.\\.conda\\investment-system\\python.exe scripts\\build_r5_bundle5_benchmark_coverage_precheck.py --repo-root .`

## exit_code

- builder_exit_code: `0`

## stdout_or_stderr_summary

- `r5_bundle5_card_5_7 status=pass dimensions={summary['total']} forbidden=0 sample_evidence=0 promotion=false sample_quality=false p2=false`
- result_sha256: `{_sha256(result_path)}`
- coverage_checked={summary['total']}
- evidence_registration_paths_checked={result['sample_registration_scan']['checked']}
- inventory_status: `benchmark_precheck_complete`

## known_todos

- Coverage remains partial for business economics, valuation comparability, dated market state and research conclusion.
- Industry/competition and dated sentiment/events remain missing with explicit source gaps.

## next_recommended_patch

- Execute R5 Bundle 5.8 close validation and truthfulness checks without changing research registries.

## boundaries

- precheck_only: `true`
- promotion_decision: `false`
- canonical_registry_write_performed: `false`
- sample_quality_report_allowed: `false`
- p2_allowed: `false`
"""
    path = repo_root / "reports/p1_6/R5_BUNDLE_5_7_BENCHMARK_COVERAGE_PRECHECK_READOUT.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run(repo_root: Path) -> dict[str, Any]:
    result = build_precheck(repo_root)
    result_path = repo_root / f"reports/workflow_runs/{WORKFLOW_ID}/R5_bundle5_benchmark_coverage_precheck.yaml"
    _write_yaml(result_path, result)
    if result["blockers"]:
        raise RuntimeError("Bundle 5.7 precheck failed: " + "; ".join(result["blockers"]))
    write_readout(repo_root, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Bundle 5.7 benchmark coverage precheck.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    result = run(args.repo_root.resolve())
    summary = result["coverage_summary"]
    print(
        "r5_bundle5_card_5_7 status={status} dimensions={dimensions} forbidden={forbidden} "
        "sample_evidence={sample} promotion=false sample_quality=false p2=false".format(
            status=result["precheck_status"],
            dimensions=summary["total"],
            forbidden=result["forbidden_language_check"]["match_count"],
            sample=result["sample_evidence_registered_count"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
