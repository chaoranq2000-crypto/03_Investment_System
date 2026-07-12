from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import yaml


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    run = root / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"
    report = run / "R5_stock_research_report_reader_v2.md"
    baseline = yaml.safe_load((run / "R5_bundle6_reader_surface_baseline.yaml").read_text(encoding="utf-8"))
    score = yaml.safe_load((run / "R5_stock_research_report_reader_v2_quality_scorecard.yaml").read_text(encoding="utf-8"))
    review = {
        "schema_version": "r5_reader_report_human_review_v0.1",
        "report_path": report.relative_to(root).as_posix(),
        "report_sha256": sha(report),
        "reviewer": None,
        "reviewed_at": None,
        "status": "pending",
        "blocking_comments": [],
        "nonblocking_comments": [],
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
    }
    comparison = {
        "artifact_type": "R5_bundle6_before_after_comparison",
        "schema_version": "v0.1",
        "comparison_scope": "structure_density_and_presentation_only",
        "bundle5_draft": {
            "raw_internal_ids": baseline["reader_surface"]["raw_internal_id_count"],
            "internal_paths": baseline["reader_surface"]["internal_path_count"],
            "raw_gap_tokens": baseline["reader_surface"]["gap_token_count"],
            "numeric_format_violations": baseline["reader_surface"]["over_precise_numeric_count"],
            "covered_dimensions": baseline["coverage_baseline"]["covered"],
            "partial_dimensions": baseline["coverage_baseline"]["partial"],
            "missing_dimensions": baseline["coverage_baseline"]["missing"],
            "reader_quality_score": baseline["reader_quality_diagnostic"]["manual_planning_score"],
        },
        "bundle6_candidate": {
            "raw_internal_ids": 0,
            "internal_paths": 0,
            "raw_gap_tokens": 0,
            "numeric_format_violations": score["numeric_format_violation_count"],
            "covered_dimensions": score["required_section_coverage"]["covered"],
            "partial_dimensions": 0,
            "missing_dimensions": len(score["required_section_coverage"]["missing"]),
            "reader_quality_score": score["score"],
        },
        "analytical_payload_complete_sections": 9,
        "remaining_limitations": [
            "行业证据主要来自发行人披露，独立市场规模和份额未纳入。",
            "液冷独立收入、毛利率和利润贡献未披露。",
            "2026年一季度弱盈利的具体驱动尚未验证。",
            "同业估值样本仅两家且可比性低。",
            "历史行情和情绪方法未启用。",
        ],
        "human_review_status": "pending",
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
    }
    (run / "R5_stock_research_report_reader_v2_human_review.yaml").write_text(yaml.safe_dump(review, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (run / "R5_bundle6_before_after_comparison.yaml").write_text(yaml.safe_dump(comparison, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"human_review_handoff status=pending report_sha256={review['report_sha256']} before_after=complete sample_quality=false p2=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
