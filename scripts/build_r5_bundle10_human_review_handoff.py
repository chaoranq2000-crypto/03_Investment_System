from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, Mapping

import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_review_form(handoff: Mapping[str, Any]) -> str:
    lines = [
        "# R5 Reader v3 外部人工评审表",
        "",
        f"- workflow_id: `{handoff['workflow_id']}`",
        "- form_status: `pending_external_human_review`",
        "- boundary: 本表由自动化流程预填待审信息，不构成人工签署。",
        "",
        "## 哈希绑定输入",
        "",
        f"- Reader: `{handoff['report_path']}`",
        f"- Reader SHA256: `{handoff['reader_report_sha256']}`",
        f"- 追溯附录: `{handoff['appendix_path']}`",
        f"- 追溯附录 SHA256: `{handoff['traceability_appendix_sha256']}`",
        f"- 自动评分表: `{handoff['scorecard_path']}`",
        f"- 自动评分表 SHA256: `{handoff['quality_scorecard_sha256']}`",
        f"- 机器可读提交模板: `{handoff['submission_template_path']}`",
        "",
        "## 评审步骤",
        "",
        "1. 独立阅读 Reader，并按需核对追溯附录与自动评分表。",
        "2. 确认正在审阅的 Reader SHA256 与本表一致；如不一致，停止签署并重新生成评审包。",
        "3. 对 HR-1 至 HR-6 分别填写 `pass` 或 `needs_fix`，不得保留 `pending`。",
        "4. 填写真实评审人标识、评审时间、总体决定以及阻断/非阻断意见，并同步填写机器可读提交模板。",
        "5. 只有六项均为 `pass`、总体决定为 `pass`、无阻断意见且哈希一致，才可提交最终关闭。",
        "",
        "## 必填检查表",
        "",
        "| check_id | 检查问题 | 评审结果 | 评审意见 |",
        "|---|---|---|---|",
    ]
    for row in handoff["required_checklist"]:
        lines.append(f"| {row['check_id']} | {row['check']} | `pending` |  |")
    lines.extend(
        [
            "",
            "## 人工签署（全部必填）",
            "",
            "- external_reviewer: `<required>`",
            "- reviewed_at: `<required, ISO-8601>`",
            "- decision: `<required: pass / needs_fix / reject>`",
            f"- report_sha256_confirmed: `{handoff['reader_report_sha256']}`",
            "- blocking_comments: `<required; 无则填写 none>`",
            "- nonblocking_comments: `<required; 无则填写 none>`",
            "",
            "## 校验与关闭命令",
            "",
            "先复制提交模板为 `R5_stock_research_report_reader_v3_human_review_submission.yaml` 并由真实评审人填写，然后执行：",
            "",
            "```powershell",
            ".\\.conda\\investment-system\\python.exe scripts/validate_r5_bundle10_human_review_submission.py --repo-root . --submission reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_report_reader_v3_human_review_submission.yaml",
            ".\\.conda\\investment-system\\python.exe scripts/finalize_r5_bundle10_after_human_review.py --repo-root . --submission reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_report_reader_v3_human_review_submission.yaml --confirm-finalize",
            "```",
            "",
            "## 提交边界",
            "",
            "签署后应复制并填写 YAML 提交模板，不要把模板原件或 pending handoff 直接改成通过。随后运行人工提交校验、Reader 门、Bundle 10 关闭校验和全量回归。任何报告内容变化都会使本次评审失效。",
            "",
        ]
    )
    return "\n".join(lines)


def build_submission_template(handoff: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": "R5_reader_external_human_review_submission",
        "schema_version": "v0.1",
        "workflow_id": handoff["workflow_id"],
        "external_reviewer": None,
        "reviewer_type": "human",
        "reviewed_at": None,
        "decision": None,
        "report_sha256_confirmed": handoff["reader_report_sha256"],
        "traceability_appendix_sha256_confirmed": handoff["traceability_appendix_sha256"],
        "required_checklist": [
            {
                "check_id": row["check_id"],
                "status": "pending",
                "comment": None,
            }
            for row in handoff["required_checklist"]
        ],
        "blocking_comments": [],
        "nonblocking_comments": [],
        "attestation": {
            "external_human_review_confirmed": False,
            "report_read_in_full": False,
            "traceability_consulted_as_needed": False,
            "automated_agent_generated": None,
        },
        "instructions": "复制本模板为 submission.yaml 后由真实评审人填写；模板原件保持 pending。",
    }


def build_handoff(run: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    report = run / "R5_stock_research_report_reader_v3.md"
    appendix = run / "R5_stock_research_report_traceability_v3.yaml"
    scorecard_path = run / "R5_stock_research_report_reader_v3_quality_scorecard.yaml"
    pack_path = run / "R5_bundle10_reader_pack.yaml"
    for path in (report, appendix, scorecard_path, pack_path):
        if not path.exists():
            raise FileNotFoundError(path)
    scorecard = load_yaml(scorecard_path)
    pack = load_yaml(pack_path)
    if scorecard.get("decision") != "candidate_ready_for_human_review":
        raise ValueError("reader quality gate has not produced a human-review candidate")
    if scorecard.get("truthfulness_status") != "pass" or scorecard.get("critical_blocker_count") != 0:
        raise ValueError("truthfulness or blocker gate is not clean")
    if scorecard.get("sample_quality_report_allowed") is not False or scorecard.get("p2_allowed") is not False:
        raise ValueError("automated gate must remain fail-closed for sample quality and P2")

    hashes = {
        "reader_report_sha256": sha256(report),
        "traceability_appendix_sha256": sha256(appendix),
        "quality_scorecard_sha256": sha256(scorecard_path),
        "reader_pack_sha256": sha256(pack_path),
    }
    handoff = {
        "artifact_type": "R5_reader_external_human_review_handoff",
        "schema_version": "v0.3",
        "workflow_id": pack["metadata"]["workflow_id"],
        "report_path": report.as_posix(),
        "appendix_path": appendix.as_posix(),
        "scorecard_path": scorecard_path.as_posix(),
        "review_form_path": (run / "R5_stock_research_report_reader_v3_human_review_form.md").as_posix(),
        "submission_template_path": (run / "R5_stock_research_report_reader_v3_human_review_submission_template.yaml").as_posix(),
        **hashes,
        "automated_gate": {
            "decision": scorecard["decision"],
            "score": scorecard["score"],
            "threshold": scorecard["threshold"],
            "truthfulness_status": scorecard["truthfulness_status"],
            "critical_blocker_count": scorecard["critical_blocker_count"],
        },
        "external_reviewer": None,
        "reviewed_at": None,
        "status": "pending_external_human_review",
        "blocking_comments": [],
        "nonblocking_comments": [],
        "required_checklist": [
            {"check_id": "HR-1", "check": "核心观点是否与证据和边界一致", "status": "pending"},
            {"check_id": "HR-2", "check": "事实估计推断管理层表述与分析师观点是否易于区分", "status": "pending"},
            {"check_id": "HR-3", "check": "预测与估值假设是否清楚且不过度精确", "status": "pending"},
            {"check_id": "HR-4", "check": "风险反证和观察条件是否足以推翻核心判断", "status": "pending"},
            {"check_id": "HR-5", "check": "技术情绪事件是否只作为市场上下文", "status": "pending"},
            {"check_id": "HR-6", "check": "正文是否清晰可读且无内部机器字段", "status": "pending"},
        ],
        "signoff_fields": {
            "decision": None,
            "reviewer_name": None,
            "reviewed_at": None,
            "report_sha256_confirmed": None,
            "blocking_comment_count": None,
        },
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
        "boundary": "External human identity and signoff cannot be generated by an automated agent.",
    }
    precheck = {
        "artifact_type": "R5_bundle10_ai_assisted_semantic_precheck",
        "schema_version": "v0.1",
        "workflow_id": pack["metadata"]["workflow_id"],
        **hashes,
        "reviewer_type": "ai_assisted_manual_semantic_precheck",
        "reviewer": "Codex",
        "status": "pass_for_external_human_handoff",
        "checks": {
            "identity_and_cutoff_visible": True,
            "ten_sections_present": scorecard["required_section_coverage"]["covered"] == 10,
            "citations_resolved": scorecard["unresolved_citation_count"] == 0,
            "machine_token_leakage_zero": scorecard["machine_token_leakage_count"] == 0,
            "numeric_format_violations_zero": scorecard["numeric_format_violation_count"] == 0,
            "forecast_bridge_reconciled": scorecard["forecast_capabilities"]["arithmetic_reconciles"] is True,
            "reverse_or_scenario_valuation_present": (
                scorecard["valuation_capabilities"]["reverse_valuation"] is True
                or scorecard["valuation_capabilities"]["scenario_value_ranges"] is True
            ),
            "technical_sentiment_event_chain_present": all(
                scorecard["market_event_capabilities"][key]
                for key in (
                    "technical", "sentiment", "future_dated_event", "event_impact_path",
                    "event_verification_metric", "event_counterevidence_condition",
                )
            ),
            "automated_truthfulness_pass": scorecard["truthfulness_status"] == "pass",
        },
        "external_human_review_status": "pending",
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
        "boundary": "This precheck is not external human signoff.",
    }
    return handoff, precheck


def main() -> int:
    parser = argparse.ArgumentParser(description="Build hash-bound Bundle 10 external human-review handoff.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--workflow-run", required=True)
    parser.add_argument(
        "--force-reopen-after-report-change",
        action="store_true",
        help="Explicitly invalidate an already-passed review and rebuild a pending handoff.",
    )
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    run = Path(args.workflow_run)
    if not run.is_absolute():
        run = root / run
    existing_handoff_path = run / "R5_stock_research_report_reader_v3_human_review.yaml"
    if existing_handoff_path.exists():
        existing_handoff = load_yaml(existing_handoff_path)
        if (
            existing_handoff.get("status") == "passed_external_human_review"
            and not args.force_reopen_after_report_change
        ):
            raise ValueError(
                "external human review already passed; use "
                "--force-reopen-after-report-change only when the reviewed report changed"
            )
    handoff, precheck = build_handoff(run)
    (run / "R5_stock_research_report_reader_v3_human_review.yaml").write_text(
        yaml.safe_dump(handoff, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    (run / "R5_bundle10_ai_assisted_semantic_precheck.yaml").write_text(
        yaml.safe_dump(precheck, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    (run / "R5_stock_research_report_reader_v3_human_review_form.md").write_text(
        render_review_form(handoff), encoding="utf-8"
    )
    (run / "R5_stock_research_report_reader_v3_human_review_submission_template.yaml").write_text(
        yaml.safe_dump(build_submission_template(handoff), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(
        "human_review_handoff "
        f"status={handoff['status']} report_sha256={handoff['reader_report_sha256']} "
        f"automated_score={handoff['automated_gate']['score']} external_signoff=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
