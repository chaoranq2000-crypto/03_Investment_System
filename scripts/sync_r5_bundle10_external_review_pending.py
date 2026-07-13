from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Mapping

import yaml


WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
SYNC_DATE = "2026-07-13"


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def write_yaml(path: Path, data: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(yaml.safe_dump(dict(data), allow_unicode=True, sort_keys=False), encoding="utf-8")
    temporary.replace(path)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def append_unique(items: list[Any], value: Any) -> None:
    if value not in items:
        items.append(value)


def render_readout(
    run: Path,
    scorecard: Mapping[str, Any],
    regression: Mapping[str, Any],
    cross: Mapping[str, Any],
    handoff: Mapping[str, Any],
) -> None:
    summary = regression["full_repository"]["summary"]
    text = f"""# R5 Bundle 10 Automated Completion Readout

- workflow_id: `{WORKFLOW_ID}`
- sync_date: `{SYNC_DATE}`
- automated_decision: `candidate_ready_for_human_review`
- reader_score: `{scorecard['score']}/{scorecard['threshold']}`
- truthfulness_status: `{scorecard['truthfulness_status']}`
- critical_blockers: `{scorecard['critical_blocker_count']}`
- external_human_review: `pending`
- bundle_closed: `false`
- sample_quality_allowed: `false`
- p2_allowed: `false`
- repository_publish: `not_authorized_not_performed`

## Outcome

Bundle 10 的自动化工作已全部完成：动态 Writer 不再硬编码公司身份，v3 Reader 从结构化 pack 生成；技术、情绪和未来事件链进入正文；工业设备与医疗服务两个跨行业合成样本验证了通用渲染，并通过病句、段落重复、章节判断复述和直接投资语言检查；读者质量门从零计分为 {scorecard['score']} 分，truthfulness 通过且无 blocker。

根据质量契约，自动化候选不能替代外部人工复核。当前 handoff 精确绑定报告 SHA256 `{handoff['reader_report_sha256']}`；reviewer、时间与签署结论仍为空。Canonical 状态因此停在 `R5_bundle10_external_human_review_pending`，而不是最终关闭。

## Automated Evidence

| item | result |
|---|---|
| reader pack | 10 sections; 14 traceability records; contract accepted |
| dynamic Writer | current company name/code/workflow hardcoding = 0 |
| technical pack | 250-day dated series; contract accepted_with_todos |
| sentiment/event pack | macro/industry/company layers and future event chain present |
| Reader v3 | citations resolved; visible machine leakage = 0 |
| reader quality gate | {scorecard['score']}/100; candidate ready; truthfulness pass; 0 blockers |
| forecast capabilities | bottom-up; three scenarios; explicit expense/tax/minority bridge; arithmetic pass |
| valuation capabilities | four reviewed peer inputs; dynamic, reverse and scenario context present |
| cross-industry regression | {cross['case_count']} cases / {cross['distinct_industries']} industries / no identity leakage / narrative quality pass |
| AI semantic precheck | pass_for_external_human_handoff; not external signoff |
| full regression | {summary} |

## Remaining External Gate

真实外部审查者需要：

1. 确认 handoff 中的 Reader SHA256 与正在审阅的文件一致。
2. 完成核心观点、类型区分、预测估值、风险反证、技术情绪事件和可读性六项清单。
3. 填写 reviewer、reviewed_at、decision 和评论。
4. 如报告内容发生任何变化，重新生成哈希并重新审查。

外部签署之前，样例质量与 P2 许可保持 false。

## Research Boundary

本 readout 记录自动化研究质量与外部复核边界，不形成交易动作、配置比例或收益承诺。
"""
    (run / "bundle10_internal_completion_readout.md").write_text(text, encoding="utf-8")


def update_state(
    run: Path,
    scorecard: Mapping[str, Any],
    regression: Mapping[str, Any],
    cross: Mapping[str, Any],
    handoff: Mapping[str, Any],
) -> dict[str, int]:
    path = run / "workflow_state.yaml"
    state = load_yaml(path)
    state.update(
        {
            "status": "needs_fix",
            "updated_at": SYNC_DATE,
            "current_stage": "R5_bundle10_external_human_review_pending",
            "next_stage": "R5_bundle10_external_human_review",
            "active_skill": "research-orchestrator",
            "required_next_skill": "quality-review",
            "external_action_required": "human_review",
        }
    )
    completed = state.setdefault("completed_stages", [])
    for stage in (
        "R5_bundle10_technical_sentiment_event_pack",
        "R5_bundle10_dynamic_writer",
        "R5_bundle10_cross_industry_writer_regression",
        "R5_bundle10_reader_quality_gate",
        "R5_bundle10_ai_semantic_precheck",
    ):
        append_unique(completed, stage)

    for artifact in state.setdefault("artifacts", []):
        if not isinstance(artifact, dict):
            continue
        if str(artifact.get("path", "")).endswith("R5_stock_research_report_reader_v2_quality_scorecard.yaml"):
            artifact["status"] = "superseded_by_bundle10_reader_v3"
    existing_paths = {
        str(row.get("path")) for row in state["artifacts"] if isinstance(row, Mapping)
    }
    core = [
        ("R5_reader_report_pack_v0_2", "R5_bundle10_reader_pack.yaml", "stock-deep-dive", "T8", "current"),
        ("R5_reader_report_v3", "R5_stock_research_report_reader_v3.md", "stock-deep-dive", "T8", "candidate_ready_for_external_human_review"),
        ("R5_reader_traceability_v3", "R5_stock_research_report_traceability_v3.yaml", "stock-deep-dive", "T8", "current"),
        ("R5_reader_quality_scorecard_v3", "R5_stock_research_report_reader_v3_quality_scorecard.yaml", "quality-review", "T9", "candidate_ready_for_human_review"),
        ("R5_reader_external_human_review_handoff", "R5_stock_research_report_reader_v3_human_review.yaml", "quality-review", "T10", "pending_external_human_review"),
        ("R5_reader_external_human_review_form", "R5_stock_research_report_reader_v3_human_review_form.md", "quality-review", "T10", "pending_external_human_review"),
        ("R5_reader_external_human_review_submission_template", "R5_stock_research_report_reader_v3_human_review_submission_template.yaml", "quality-review", "T10", "pending_external_human_review"),
        ("bundle10_quality_report", "bundle10_quality_report.md", "quality-review", "T9", "accepted_with_todos"),
        ("bundle10_internal_completion_readout", "bundle10_internal_completion_readout.md", "research-orchestrator", "T11", "current"),
    ]
    for artifact_type, name, skill, stage, status in core:
        rel = f"reports/workflow_runs/{WORKFLOW_ID}/{name}"
        if rel in existing_paths:
            continue
        state["artifacts"].append(
            {
                "artifact_type": artifact_type,
                "path": rel,
                "created_by_skill": skill,
                "stage": stage,
                "status": status,
                "required": True,
            }
        )
        existing_paths.add(rel)

    resolutions = {
        "R5Q-B7-A823A644": ("resolved_bundle10_reader_density", "Reader v3 exceeds the density floor and passed all ten section diagnostics."),
        "R5Q-B7-47122D56": ("resolved_bundle10_reviewed_peer_context", "Four dated peer inputs with selection reasons and limitations reached the Reader gate."),
        "R5Q-B7-E0B818E7": ("resolved_bundle10_sentiment_layers", "Macro, industry and company sentiment layers are represented with explicit uncertainty."),
        "R5Q-B7-9A50BA49": ("resolved_bundle10_future_event_chain", "Future date, impact path, verification metrics and counterevidence conditions are visible."),
    }
    for todo in state.setdefault("open_todos", []):
        if not isinstance(todo, dict):
            continue
        issue_id = str(todo.get("issue_id", ""))
        if issue_id in resolutions:
            todo["status"], todo["notes"] = resolutions[issue_id]
            todo["resolved_at"] = SYNC_DATE

    gates = state.setdefault("quality_gates", [])
    gate_payload = {
        "gate_id": "R5_BUNDLE10_AUTOMATED",
        "status": "candidate_ready_for_human_review",
        "checked_by": "quality-review",
        "notes": (
            f"Reader score {scorecard['score']}/{scorecard['threshold']}; truthfulness pass; "
            f"zero blockers; full regression {regression['full_repository']['summary']}; "
            "external human review remains pending."
        ),
        "current_scope": "bundle10_automated_completion_only",
    }
    existing_gate = next(
        (
            row
            for row in gates
            if isinstance(row, dict) and row.get("gate_id") == "R5_BUNDLE10_AUTOMATED"
        ),
        None,
    )
    if existing_gate is None:
        gates.append(gate_payload)
    else:
        existing_gate.update(gate_payload)
    state["reader_candidate_snapshot"] = {
        "report_path": f"reports/workflow_runs/{WORKFLOW_ID}/R5_stock_research_report_reader_v3.md",
        "traceability_path": f"reports/workflow_runs/{WORKFLOW_ID}/R5_stock_research_report_traceability_v3.yaml",
        "scorecard_path": f"reports/workflow_runs/{WORKFLOW_ID}/R5_stock_research_report_reader_v3_quality_scorecard.yaml",
        "human_review_handoff_path": f"reports/workflow_runs/{WORKFLOW_ID}/R5_stock_research_report_reader_v3_human_review.yaml",
        "report_sha256": handoff["reader_report_sha256"],
        "decision": scorecard["decision"],
        "quality_band": scorecard["quality_band"],
        "score": scorecard["score"],
        "threshold": scorecard["threshold"],
        "truthfulness_status": scorecard["truthfulness_status"],
        "critical_blocker_count": scorecard["critical_blocker_count"],
        "human_review_status": "pending_external",
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
    }
    state["bundle10_internal_completion"] = {
        "decision": "candidate_ready_for_human_review",
        "internal_execution_complete": True,
        "bundle_closed": False,
        "synced_at": SYNC_DATE,
        "external_human_review": "pending",
        "sample_quality_allowed": False,
        "p2_allowed": False,
        "remote_ci": "TODO_AFTER_EXPLICIT_PUBLISH",
        "next_gate": "R5_bundle10_external_human_review",
        "cross_industry_regression": {
            "fixture_boundary": cross["fixture_boundary"],
            "case_count": cross["case_count"],
            "distinct_industries": cross["distinct_industries"],
            "narrative_quality": cross["narrative_quality"]["status"],
        },
    }
    backflow = state.setdefault("quality_backflow", {})
    backflow["prior_source_scorecard"] = backflow.get("source_scorecard")
    backflow["source_scorecard"] = f"reports/workflow_runs/{WORKFLOW_ID}/R5_stock_research_report_reader_v3_quality_scorecard.yaml"
    backflow["decision"] = scorecard["decision"]
    backflow["quality_band"] = scorecard["quality_band"]
    backflow["score"] = scorecard["score"]
    backflow["critical_blocker_count"] = scorecard["critical_blocker_count"]
    backflow["fix_routes"] = []
    backflow["current_first_route"] = "external_human_review"
    backflow["current_first_stage"] = "R5_bundle10_external_human_review"
    backflow["sample_quality_report_allowed"] = False
    backflow["p2_allowed"] = False
    write_yaml(path, state)
    return {"completed_stages": len(completed), "state_artifacts": len(state["artifacts"])}


def update_open_todos(run: Path) -> dict[str, int]:
    path = run / "open_todos.csv"
    fields, rows = read_csv(path)
    by_id = {row["issue_id"]: row for row in rows}
    resolutions = {
        "R5Q-B7-A823A644": ("resolved_bundle10_reader_density", "Reader v3 passed the density and section-analysis gate."),
        "R5Q-B7-47122D56": ("resolved_bundle10_reviewed_peer_context", "Four dated peer inputs reached the Reader gate with visible comparability limits."),
        "R5Q-B7-E0B818E7": ("resolved_bundle10_sentiment_layers", "Macro, industry and company sentiment layers are present with uncertainty."),
        "R5Q-B7-9A50BA49": ("resolved_bundle10_future_event_chain", "Future date, impact path, verification metrics and counterevidence conditions are present."),
    }
    for issue_id, (status, note) in resolutions.items():
        if issue_id in by_id:
            by_id[issue_id]["status"] = status
            by_id[issue_id]["resolved_at"] = SYNC_DATE
            by_id[issue_id]["notes"] = note
    _, quality_rows = read_csv(run / "R5_bundle10_quality_issues.csv")
    added = 0
    for issue in quality_rows:
        if issue["status"] != "accepted_todo" or issue["issue_id"] in by_id:
            continue
        row = {
            "issue_id": issue["issue_id"],
            "severity": issue["severity"],
            "stage": issue["stage"],
            "target_artifact": issue["target_artifact"],
            "description": issue["description"],
            "fix_owner_skill": issue["fix_owner_skill"],
            "status": "accepted_todo",
            "created_at": SYNC_DATE,
            "resolved_at": "",
            "notes": issue["next_action"],
        }
        rows.append(row)
        by_id[row["issue_id"]] = row
        added += 1
    write_csv(path, fields, rows)
    return {"rows": len(rows), "added": added}


def artifact_specs() -> list[tuple[str, str, str, str, str]]:
    return [
        ("bundle10_technical_market_pack", "R5_bundle10_technical_market_pack.yaml", "stock-deep-dive", "T7", "250-day technical market context"),
        ("bundle10_sentiment_event_pack", "R5_bundle10_sentiment_event_pack.yaml", "stock-deep-dive", "T7", "three sentiment layers and future event chain"),
        ("bundle10_reader_gate_forecast", "R5_bundle10_reader_gate_forecast.yaml", "stock-deep-dive", "T8", "forecast gate adapter"),
        ("bundle10_reader_gate_valuation", "R5_bundle10_reader_gate_valuation.yaml", "company-valuation", "T8", "valuation gate adapter"),
        ("bundle10_reader_pack", "R5_bundle10_reader_pack.yaml", "stock-deep-dive", "T8", "pack-driven ten-section Reader input"),
        ("bundle10_reader_pack_readout", "R5_bundle10_reader_pack_build_readout.yaml", "stock-deep-dive", "T8", "Reader pack build summary"),
        ("bundle10_reader_v3", "R5_stock_research_report_reader_v3.md", "stock-deep-dive", "T8", "97-point Reader candidate"),
        ("bundle10_traceability_v3", "R5_stock_research_report_traceability_v3.yaml", "stock-deep-dive", "T8", "resolved display references with exact source paths"),
        ("bundle10_reader_scorecard_v3", "R5_stock_research_report_reader_v3_quality_scorecard.yaml", "quality-review", "T9", "candidate ready for human review"),
        ("bundle10_cross_industry_regression", "R5_bundle10_cross_industry_writer_regression.yaml", "quality-review", "T9", "two synthetic industries passed identity and narrative regression"),
        ("bundle10_fixture_industrial_reader", "bundle10_cross_industry_regression/industrial_equipment_reader.md", "quality-review", "T9", "synthetic Writer regression"),
        ("bundle10_fixture_industrial_trace", "bundle10_cross_industry_regression/industrial_equipment_traceability.yaml", "quality-review", "T9", "synthetic traceability"),
        ("bundle10_fixture_healthcare_reader", "bundle10_cross_industry_regression/healthcare_services_reader.md", "quality-review", "T9", "synthetic Writer regression"),
        ("bundle10_fixture_healthcare_trace", "bundle10_cross_industry_regression/healthcare_services_traceability.yaml", "quality-review", "T9", "synthetic traceability"),
        ("bundle10_human_review_handoff", "R5_stock_research_report_reader_v3_human_review.yaml", "quality-review", "T10", "hash-bound external review pending"),
        ("bundle10_human_review_form", "R5_stock_research_report_reader_v3_human_review_form.md", "quality-review", "T10", "hash-bound six-item external review form"),
        ("bundle10_human_review_submission_template", "R5_stock_research_report_reader_v3_human_review_submission_template.yaml", "quality-review", "T10", "fail-closed external review submission template"),
        ("bundle10_ai_semantic_precheck", "R5_bundle10_ai_assisted_semantic_precheck.yaml", "quality-review", "T9", "not external signoff"),
        ("bundle10_close_validation", "R5_bundle10_close_input_validation.json", "quality-review", "T9", "automated completion validation pass"),
        ("bundle10_quality_issues", "R5_bundle10_quality_issues.csv", "quality-review", "T9", "accepted with TODOs"),
        ("bundle10_quality_report", "bundle10_quality_report.md", "quality-review", "T9", "automated candidate quality report"),
        ("bundle10_regression_summary", "R5_bundle10_regression_summary.yaml", "quality-review", "T9", "632 passed 2 skipped"),
        ("bundle10_handoff_quality", "handoffs/22_to_quality-review_bundle10_reader_gate.md", "stock-deep-dive", "T9", "quality dispatch"),
        ("bundle10_handoff_external", "handoffs/23_to_research-orchestrator_bundle10_external_review_pending.md", "quality-review", "T10", "external review dispatch"),
        ("bundle10_internal_completion_readout", "bundle10_internal_completion_readout.md", "research-orchestrator", "T11", "automated completion and external boundary"),
    ]


def update_artifact_manifest(repo_root: Path, run: Path) -> dict[str, int]:
    path = run / "artifact_manifest.csv"
    fields, rows = read_csv(path)
    by_path = {row["path"]: row for row in rows}
    numbers = [
        int(row["artifact_id"].split("_")[-1])
        for row in rows
        if row.get("artifact_id", "").startswith("art_")
    ]
    next_number = max(numbers, default=0) + 1
    added = 0
    for artifact_type, name, skill, stage, notes in artifact_specs():
        rel = f"reports/workflow_runs/{WORKFLOW_ID}/{name}"
        if rel in by_path:
            by_path[rel]["notes"] = notes
            by_path[rel]["exists"] = "True"
            continue
        if not (repo_root / rel).exists():
            raise FileNotFoundError(f"required Bundle 10 artifact missing: {rel}")
        rows.append(
            {
                "artifact_id": f"art_{next_number:03d}",
                "artifact_type": artifact_type,
                "path": rel,
                "created_by_skill": skill,
                "stage": stage,
                "required": "True",
                "exists": "True",
                "status": "current",
                "notes": notes,
            }
        )
        by_path[rel] = rows[-1]
        next_number += 1
        added += 1
    write_csv(path, fields, rows)
    return {"rows": len(rows), "added": added}


def append_run_log(
    run: Path,
    scorecard: Mapping[str, Any],
    regression: Mapping[str, Any],
    cross: Mapping[str, Any],
) -> bool:
    path = run / "run_log.md"
    text = path.read_text(encoding="utf-8")
    marker = "## Bundle 10 automated completion"
    if marker in text:
        return False
    addition = f"""

{marker}

| Step | Status | Notes |
|---|---|---|
| Dynamic Writer | done | Pack-driven; current company identity hardcoding removed. |
| Technical / sentiment / event | done_with_todos | 250-day technical context, three sentiment layers and future event chain. |
| Reader v3 | done | Ten sections with resolved display references. |
| Reader quality gate | candidate_ready_for_human_review | Score {scorecard['score']}/{scorecard['threshold']}; truthfulness pass; zero blockers. |
| Cross-industry regression | pass | {cross['case_count']} synthetic cases across {cross['distinct_industries']} industries; no identity leakage; narrative-quality checks pass. |
| AI semantic precheck | pass_for_external_human_handoff | Explicitly not external signoff. |
| Full regression | done_local | {regression['full_repository']['summary']}. |
| Canonical state | external_human_review_pending | Bundle 10 automated work complete; bundle not finally closed. |
| Sample quality / P2 | false / false | Requires hash-bound external human review. |
| Publish boundary | preserved | No staging, commit, push or remote CI claim was performed. |
"""
    path.write_text(text.rstrip() + addition + "\n", encoding="utf-8")
    return True


def sync_bundle10(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    run = repo_root / "reports/workflow_runs" / WORKFLOW_ID
    validation = json.loads((run / "R5_bundle10_close_input_validation.json").read_text(encoding="utf-8"))
    if validation.get("decision") != "pass":
        raise ValueError("Bundle 10 deterministic validation is not pass")
    regression = load_yaml(run / "R5_bundle10_regression_summary.yaml")
    if regression.get("full_repository", {}).get("status") != "pass":
        raise ValueError("Bundle 10 full regression is not pass")
    cross = load_yaml(run / "R5_bundle10_cross_industry_writer_regression.yaml")
    narrative = cross.get("narrative_quality") or {}
    if (
        cross.get("decision") != "pass"
        or cross.get("fixture_boundary") != "synthetic_layout_and_schema_regression_only"
        or cross.get("case_count", 0) < 2
        or cross.get("distinct_industries", 0) < 2
        or narrative.get("status") != "pass"
        or narrative.get("total_duplicate_paragraph_count") != 0
        or narrative.get("total_judgment_restatement_count") != 0
        or narrative.get("malformed_pattern_hits")
        or narrative.get("prohibited_advice_hits")
    ):
        raise ValueError("cross-industry Writer regression is not narrative-quality ready")
    scorecard = load_yaml(run / "R5_stock_research_report_reader_v3_quality_scorecard.yaml")
    if scorecard.get("decision") != "candidate_ready_for_human_review":
        raise ValueError("Reader v3 is not ready for human review")
    handoff = load_yaml(run / "R5_stock_research_report_reader_v3_human_review.yaml")
    if handoff.get("status") != "pending_external_human_review":
        raise ValueError("external human-review boundary is not pending")
    render_readout(run, scorecard, regression, cross, handoff)
    state = update_state(run, scorecard, regression, cross, handoff)
    todos = update_open_todos(run)
    artifacts = update_artifact_manifest(repo_root, run)
    log_appended = append_run_log(run, scorecard, regression, cross)
    return {
        "artifact_type": "R5_bundle10_external_review_pending_sync",
        "schema_version": "v0.1",
        "workflow_id": WORKFLOW_ID,
        "automated_decision": scorecard["decision"],
        "reader_score": scorecard["score"],
        "truthfulness_status": scorecard["truthfulness_status"],
        "cross_industry_narrative_quality": narrative["status"],
        "external_human_review": "pending",
        "bundle_closed": False,
        "current_stage": "R5_bundle10_external_human_review_pending",
        "state": state,
        "open_todos": todos,
        "artifact_manifest": artifacts,
        "run_log_appended": log_appended,
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize Bundle 10 automated completion to external-review pending state.")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    result = sync_bundle10(Path(args.repo_root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
