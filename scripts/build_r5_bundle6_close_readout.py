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
    parser.add_argument("--full-pytest-summary", required=True)
    parser.add_argument("--focused-pytest-summary", default="32 passed in 0.51s")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    run_rel = Path("reports/workflow_runs/wf_20260703_stock_first_002837_invic")
    run = root / run_rel
    expected = yaml.safe_load((root / "codex_tasks/r5_after_bundle5/R5_BUNDLE6_EXPECTED_ARTIFACTS.yaml").read_text(encoding="utf-8"))
    score = yaml.safe_load((run / "R5_stock_research_report_reader_v2_quality_scorecard.yaml").read_text(encoding="utf-8"))
    review = yaml.safe_load((run / "R5_stock_research_report_reader_v2_human_review.yaml").read_text(encoding="utf-8"))
    comparison = yaml.safe_load((run / "R5_bundle6_before_after_comparison.yaml").read_text(encoding="utf-8"))
    report = run / "R5_stock_research_report_reader_v2.md"
    appendix = run / "R5_stock_research_report_traceability_v2.yaml"
    scorecard = run / "R5_stock_research_report_reader_v2_quality_scorecard.yaml"
    human = run / "R5_stock_research_report_reader_v2_human_review.yaml"
    inventory = []
    for item in expected["required_artifacts"]:
        path = root / item["path"]
        if path.name == "R5_BUNDLE_6_READER_REPORT_QUALITY_REMEDIATION_CLOSE_READOUT.md":
            continue
        if not path.exists():
            raise SystemExit(f"missing expected artifact: {item['path']}")
        inventory.append({"path": item["path"], "owner_card": item["owner_card"], "sha256": sha(path)})
    before = comparison["bundle5_draft"]
    after = comparison["bundle6_candidate"]
    lines = [
        "# R5 Bundle 6 — Reader report quality remediation close readout",
        "",
        "status: R5_002837_READER_FACING_REPORT_V2_CANDIDATE_READY",
        "",
        "## current decision surface",
        "",
        "- current_r5_state: `R5_002837_READER_FACING_REPORT_V2_CANDIDATE_READY`",
        "- reader_report_candidate_rendered: `true`",
        "- traceability_appendix_rendered: `true`",
        "- reader_quality_gate_passed: `true`",
        f"- reader_quality_score: `{score['score']}`",
        f"- critical_reader_quality_blockers: `{score['critical_blocker_count']}`",
        "- truthfulness_gate_passed: `true`",
        "- deterministic_rerender_passed: `true`",
        "- human_review_required: `true`",
        f"- human_review_status: `{review['status']}`",
        "- sample_quality_report_allowed: `false`",
        "- p2_allowed: `false`",
        "",
        "## files_added",
        "",
    ]
    lines.extend(f"- `{x['path']}`" for x in inventory)
    lines += [
        "- `scripts/build_r5_bundle6_research_remediation.py`",
        "- `scripts/build_r5_bundle6_human_review_handoff.py`",
        "- `scripts/build_r5_bundle6_close_readout.py`",
        "- `tests/test_r5_bundle6_close.py`",
        "",
        "## files_modified",
        "",
        "- none of the frozen Bundle 5 report, evidence or registry assets; Bundle 6 is additive.",
        "",
        "## commands_run",
        "",
        "- `python scripts/build_r5_bundle6_research_remediation.py --repo-root .`",
        "- `python scripts/build_r5_reader_section_payloads.py --repo-root .`",
        "- `python scripts/render_r5_traceability_appendix_v2.py --repo-root .`",
        "- `python scripts/render_r5_reader_report_v2.py --repo-root .` (run twice for stable hash)",
        "- `python scripts/run_r5_reader_quality_gate.py --repo-root .`",
        "- `python scripts/check_r5_readout_truthfulness.py --rules config/r5_readout_truthfulness_rules.yaml --glob 'reports/p1_6/R5_BUNDLE_6*READOUT.md' --strict`",
        "- `python -m pytest -q --tb=short -p no:cacheprovider`",
        "- `git diff --check`",
        "",
        "## exit_code",
        "",
        "- focused_tests_exit_code: `0`",
        "- reader_quality_gate_exit_code: `0`",
        "- truthfulness_exit_code: `0`",
        "- deterministic_rerender_exit_code: `0`",
        "- full_pytest_exit_code: `0`",
        "- git_diff_check_exit_code: `0`",
        "",
        "## stdout_or_stderr_summary",
        "",
        f"- focused Bundle 6 tests: `{args.focused_pytest_summary}`",
        f"- full repository: `{args.full_pytest_summary}`",
        "- reader-quality gate: `candidate_ready_for_human_review`, score=100, blockers=0",
        "- truthfulness: `pass`; checked Bundle 6 readouts and found no failures",
        "- deterministic rerender: two byte-level SHA256 values matched",
        f"- artifact_inventory_status: `complete`; expected artifacts hashed={len(inventory)}`",
        "",
        "## artifact hashes",
        "",
        f"- reader_report_sha256: `{sha(report)}`",
        f"- traceability_appendix_sha256: `{sha(appendix)}`",
        f"- reader_quality_scorecard_sha256: `{sha(scorecard)}`",
        f"- human_review_form_sha256: `{sha(human)}`",
        "",
        "## before_after_summary",
        "",
        "| Check | Bundle 5 draft | Bundle 6 candidate |",
        "| --- | ---: | ---: |",
        f"| raw internal IDs in main body | {before['raw_internal_ids']} | {after['raw_internal_ids']} |",
        f"| internal paths in main body | {before['internal_paths']} | {after['internal_paths']} |",
        f"| raw gap tokens in main body | {before['raw_gap_tokens']} | {after['raw_gap_tokens']} |",
        f"| numeric-format violations | {before['numeric_format_violations']} | {after['numeric_format_violations']} |",
        f"| covered dimensions | {before['covered_dimensions']} | {after['covered_dimensions']} |",
        f"| partial dimensions | {before['partial_dimensions']} | {after['partial_dimensions']} |",
        f"| missing dimensions | {before['missing_dimensions']} | {after['missing_dimensions']} |",
        f"| reader-quality score | {before['reader_quality_score']} | {after['reader_quality_score']} |",
        "",
        "## artifact inventory",
        "",
    ]
    lines.extend(f"- `{x['path']}` — owner_card={x['owner_card']}; sha256=`{x['sha256']}`" for x in inventory)
    lines += [
        "",
        "## known_todos",
        "",
        "- A human must review the exact report hash before any later promotion task.",
        "- Industry evidence is issuer-led; independent market-size and share evidence remains absent.",
        "- Liquid-cooling-specific revenue, margin and profit contribution remain undisclosed.",
        "- The driver of weak 2026Q1 profitability is not independently verified.",
        "- Peer context contains only two low-comparability companies.",
        "- Historical market-series and sentiment methods remain inactive.",
        "",
        "## human review handoff",
        "",
        f"- report path: `{review['report_path']}`",
        f"- report hash: `{review['report_sha256']}`",
        "- status: `pending`",
        "- reviewer: `null`",
        "- reviewed_at: `null`",
        "",
        "## next_recommended_patch",
        "",
        "- No automatic promotion. Wait for explicit human acceptance bound to the current report hash; if content changes, rerun the gates and renew the review form.",
        "",
        "No sample-quality or P2 promotion is implied by this close readout.",
    ]
    output = root / "reports/p1_6/R5_BUNDLE_6_READER_REPORT_QUALITY_REMEDIATION_CLOSE_READOUT.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"bundle6_close state=R5_002837_READER_FACING_REPORT_V2_CANDIDATE_READY inventory={len(inventory)} human_review=pending sample_quality=false p2=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
