from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Mapping

import yaml


WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
CLOSE_DATE = "2026-07-13"


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"YAML must be a mapping: {path}")
    return payload


def write_yaml(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(yaml.safe_dump(dict(payload), allow_unicode=True, sort_keys=False), encoding="utf-8")
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


def update_workflow_state(run: Path, regression: Mapping[str, Any]) -> dict[str, int]:
    path = run / "workflow_state.yaml"
    state = load_yaml(path)
    state.update(
        {
            "status": "needs_fix",
            "updated_at": CLOSE_DATE,
            "current_stage": "R5_bundle9_closed",
            "next_stage": "R5_bundle10_dynamic_writer_regression",
            "active_skill": "research-orchestrator",
            "required_next_skill": "stock-deep-dive",
        }
    )
    completed = state.setdefault("completed_stages", [])
    for stage in (
        "R5_bundle9_bottom_up_forecast_model",
        "R5_bundle9_company_valuation",
        "R5_bundle9_forecast_valuation_close",
    ):
        append_unique(completed, stage)

    state["forecast_snapshot"] = {
        "status": "ready_with_disclosure_todos",
        "model_path": f"reports/workflow_runs/{WORKFLOW_ID}/segment_forecast_model.yaml",
        "assumption_registry_path": f"reports/workflow_runs/{WORKFLOW_ID}/R5_bundle9_forecast_assumption_registry.yaml",
        "scenario_count": 3,
        "forecast_periods": ["2026E", "2027E", "2028E"],
        "assumption_count": 42,
        "profit_bridge_max_abs_difference": 0.0,
        "sample_quality_allowed": False,
    }
    state["valuation_snapshot_bundle9"] = {
        "status": "partial_with_todos",
        "valuation_as_of_date": "2026-07-10",
        "pack_path": f"reports/workflow_runs/{WORKFLOW_ID}/R5_bundle9_valuation_pack.yaml",
        "reverse_valuation_path": f"reports/workflow_runs/{WORKFLOW_ID}/reverse_valuation.yaml",
        "scenario_valuation_path": f"reports/workflow_runs/{WORKFLOW_ID}/scenario_valuation.yaml",
        "peer_set_quality": "LOW_CONFIDENCE_PEER_SET",
        "sample_quality_allowed": False,
    }

    state_artifacts = state.setdefault("artifacts", [])
    existing_paths = {str(row.get("path")) for row in state_artifacts if isinstance(row, Mapping)}
    core_artifacts = [
        ("R5_bundle9_forecast_assumption_registry", "R5_bundle9_forecast_assumption_registry.yaml", "stock-deep-dive", "T6"),
        ("segment_forecast_model", "segment_forecast_model.yaml", "stock-deep-dive", "T6"),
        ("forecast_bridge", "forecast_bridge.yaml", "stock-deep-dive", "T6"),
        ("R5_bundle9_valuation_pack", "R5_bundle9_valuation_pack.yaml", "company-valuation", "RP6"),
        ("reverse_valuation", "reverse_valuation.yaml", "company-valuation", "RP6"),
        ("scenario_valuation", "scenario_valuation.yaml", "company-valuation", "RP6"),
        ("bundle9_quality_report", "bundle9_quality_report.md", "quality-review", "T9"),
        ("bundle9_close_readout", "bundle9_close_readout.md", "research-orchestrator", "T11"),
    ]
    for artifact_type, name, skill, stage in core_artifacts:
        rel = f"reports/workflow_runs/{WORKFLOW_ID}/{name}"
        if rel in existing_paths:
            continue
        state_artifacts.append(
            {
                "artifact_type": artifact_type,
                "path": rel,
                "created_by_skill": skill,
                "stage": stage,
                "status": "current",
                "required": True,
            }
        )
        existing_paths.add(rel)

    resolved = {
        "R5Q-B7-EDEA2DF6": ("resolved_bundle9_bottom_up_forecast", "Bundle 9 uses three audited broad business lines and explicit drivers."),
        "R5Q-B7-FC4A9CE0": ("resolved_bundle9_explicit_profit_bridge", "Tax, finance, other operating drag, minority profit and cash flow are separately modeled."),
        "R5Q-B7-5F606C21": ("resolved_bundle9_reverse_scenario_valuation", "Reverse valuation and bear/base/bull market-cap ranges are now present."),
    }
    for todo in state.setdefault("open_todos", []):
        if not isinstance(todo, dict):
            continue
        issue_id = str(todo.get("issue_id", ""))
        if issue_id in resolved:
            todo["status"], todo["notes"] = resolved[issue_id]
            todo["resolved_at"] = CLOSE_DATE
        if issue_id in {"R5Q-B7-47122D56", "R5B8B-QR-PEER-001"}:
            todo["status"] = "accepted_todo_low_confidence_peer_set"
            todo["notes"] = "Four same-date peers exist, but forward multiples, official numeric reconciliation and liquid-cooling purity remain insufficient."

    gate_ids = {
        str(row.get("gate_id"))
        for row in state.setdefault("quality_gates", [])
        if isinstance(row, Mapping)
    }
    if "R5_BUNDLE9_CLOSE" not in gate_ids:
        state["quality_gates"].append(
            {
                "gate_id": "R5_BUNDLE9_CLOSE",
                "status": "accepted_with_todos",
                "checked_by": "quality-review",
                "notes": (
                    "42 traced assumptions; three scenarios; zero profit-bridge difference; "
                    "scenario and reverse valuation accepted; peer and intrinsic-method gaps visible; "
                    f"full regression {regression['full_repository']['summary']}."
                ),
                "current_scope": "bundle9_local_close",
            }
        )
    state["bundle9_close"] = {
        "decision": "accepted_with_todos",
        "bundle_closed": True,
        "closed_at": CLOSE_DATE,
        "reader_regenerated": False,
        "reader_score": 59,
        "reader_decision": "rejected",
        "sample_quality_allowed": False,
        "p2_allowed": False,
        "remote_ci": "TODO_AFTER_EXPLICIT_PUBLISH",
        "next_bundle": "R5_bundle10_dynamic_writer_regression",
    }
    backflow = state.setdefault("quality_backflow", {})
    backflow["bundle9_forecast_valuation_completed"] = True
    backflow["current_first_route"] = "stock-deep-dive"
    backflow["current_first_stage"] = "T7_technical_sentiment_event_pack"
    backflow["sample_quality_report_allowed"] = False
    backflow["p2_allowed"] = False
    write_yaml(path, state)
    return {"completed_stages": len(completed), "state_artifacts": len(state_artifacts)}


def update_open_todos(run: Path) -> dict[str, int]:
    path = run / "open_todos.csv"
    fields, rows = read_csv(path)
    by_id = {row["issue_id"]: row for row in rows}
    resolved = {
        "R5Q-B7-EDEA2DF6": ("resolved_bundle9_bottom_up_forecast", "Bundle 9 now uses audited broad business-line drivers."),
        "R5Q-B7-FC4A9CE0": ("resolved_bundle9_explicit_profit_bridge", "Expenses, tax, minority profit and cash flow are separately bridged."),
        "R5Q-B7-5F606C21": ("resolved_bundle9_reverse_scenario_valuation", "Reverse valuation and scenario market-cap ranges are present."),
    }
    for issue_id, (status, note) in resolved.items():
        if issue_id in by_id:
            by_id[issue_id]["status"] = status
            by_id[issue_id]["resolved_at"] = CLOSE_DATE
            by_id[issue_id]["notes"] = note
    for issue_id in ("R5Q-B7-47122D56", "R5B8B-QR-PEER-001"):
        if issue_id in by_id:
            by_id[issue_id]["status"] = "accepted_todo"
            by_id[issue_id]["notes"] = (
                "Four same-date peers exist, but forward multiples, official numeric reconciliation "
                "and liquid-cooling purity remain insufficient."
            )

    _, quality_rows = read_csv(run / "R5_bundle9_quality_issues.csv")
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
            "created_at": CLOSE_DATE,
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
        ("bundle9_forecast_assumption_registry", "R5_bundle9_forecast_assumption_registry.yaml", "stock-deep-dive", "T6", "42 reviewed forecast assumptions"),
        ("bundle9_segment_forecast_model", "segment_forecast_model.yaml", "stock-deep-dive", "T6", "three business lines and three scenarios"),
        ("bundle9_forecast_bridge", "forecast_bridge.yaml", "stock-deep-dive", "T6", "profit and cash-flow bridge"),
        ("bundle9_forecast_sensitivity", "forecast_sensitivity.csv", "stock-deep-dive", "T6", "12 forecast sensitivity rows"),
        ("bundle9_forecast_readout", "R5_bundle9_forecast_build_readout.yaml", "stock-deep-dive", "T6", "forecast build summary"),
        ("bundle9_market_snapshot", "market_snapshot.csv", "stock-deep-dive", "RP6", "reviewed dated market row"),
        ("bundle9_peer_market_snapshot", "peer_market_snapshot.csv", "stock-deep-dive", "RP6", "four low-confidence peer rows"),
        ("bundle9_valuation_readiness", "valuation_input_readiness.yaml", "stock-deep-dive", "RP6", "normalized valuation input status"),
        ("bundle9_valuation_request", "valuation_request.yaml", "stock-deep-dive", "RP6", "company-valuation handoff request"),
        ("bundle9_peer_reconciliation", "R5_bundle9_peer_reconciliation.yaml", "company-valuation", "RP6", "peer source and comparability review"),
        ("bundle9_valuation_input_registry", "R5_bundle9_valuation_input_registry.yaml", "company-valuation", "RP6", "controlled valuation method eligibility"),
        ("bundle9_valuation_pack", "R5_bundle9_valuation_pack.yaml", "company-valuation", "RP6", "partial valuation pack"),
        ("bundle9_reverse_valuation", "reverse_valuation.yaml", "company-valuation", "RP6", "five reverse profit thresholds"),
        ("bundle9_scenario_valuation", "scenario_valuation.yaml", "company-valuation", "RP6", "three scenario market-cap ranges"),
        ("bundle9_analyst_comparison", "analyst_forecast_comparison.csv", "company-valuation", "RP6", "three analyst-view comparison rows"),
        ("bundle9_valuation_build_readout", "R5_bundle9_valuation_build_readout.yaml", "company-valuation", "RP6", "valuation build summary"),
        ("bundle9_valuation_model", "valuation/valuation_model.yaml", "company-valuation", "RP6", "structured valuation model"),
        ("bundle9_valuation_snapshot", "valuation/valuation_snapshot.yaml", "company-valuation", "RP6", "dated valuation snapshot"),
        ("bundle9_peer_comparison", "valuation/peer_comparison.csv", "company-valuation", "RP6", "four peer comparison rows"),
        ("bundle9_valuation_sensitivity", "valuation/sensitivity_table.csv", "company-valuation", "RP6", "forecast and multiple sensitivity"),
        ("bundle9_valuation_section", "valuation/valuation_section_draft.md", "company-valuation", "RP6", "Chinese valuation section draft"),
        ("bundle9_valuation_gaps", "valuation/valuation_gap_requests.yaml", "company-valuation", "RP6", "five visible valuation gaps"),
        ("bundle9_valuation_quality_handoff", "valuation/valuation_quality_handoff.yaml", "company-valuation", "T9", "QR-VAL handoff"),
        ("bundle9_company_valuation_output", "valuation/valuation_output.yaml", "company-valuation", "RP6", "R5 mini-validator output"),
        ("bundle9_r5_valuation_handoff", "valuation/R5_valuation_handoff.yaml", "company-valuation", "RP6", "R5 valuation handoff"),
        ("bundle9_close_validation", "R5_bundle9_close_input_validation.json", "quality-review", "T9", "deterministic close pass"),
        ("bundle9_quality_issues", "R5_bundle9_quality_issues.csv", "quality-review", "T9", "accepted with TODOs"),
        ("bundle9_quality_report", "bundle9_quality_report.md", "quality-review", "T9", "local close authorized"),
        ("bundle9_regression_summary", "R5_bundle9_regression_summary.yaml", "quality-review", "T9", "local regression evidence"),
        ("bundle9_handoff_quality", "handoffs/20_to_quality-review_bundle9_gate.md", "stock-deep-dive", "T9", "quality dispatch"),
        ("bundle9_handoff_close", "handoffs/21_to_research-orchestrator_bundle9_close.md", "quality-review", "T10", "close dispatch"),
        ("bundle9_close_readout", "bundle9_close_readout.md", "research-orchestrator", "T11", "Bundle 9 locally closed"),
    ]


def update_artifact_manifest(repo_root: Path, run: Path) -> dict[str, int]:
    path = run / "artifact_manifest.csv"
    fields, rows = read_csv(path)
    existing_paths = {row["path"] for row in rows}
    numbers = [
        int(row["artifact_id"].split("_")[-1])
        for row in rows
        if row.get("artifact_id", "").startswith("art_")
    ]
    next_number = max(numbers, default=0) + 1
    added = 0
    for artifact_type, name, skill, stage, notes in artifact_specs():
        rel = f"reports/workflow_runs/{WORKFLOW_ID}/{name}"
        if rel in existing_paths:
            continue
        if not (repo_root / rel).exists():
            raise FileNotFoundError(f"required Bundle 9 close artifact missing: {rel}")
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
        existing_paths.add(rel)
        next_number += 1
        added += 1
    write_csv(path, fields, rows)
    return {"rows": len(rows), "added": added}


def render_close_readout(run: Path, regression: Mapping[str, Any]) -> None:
    summary = regression["full_repository"]["summary"]
    text = f"""# R5 Bundle 9 Local Close Readout

- workflow_id: `{WORKFLOW_ID}`
- close_date: `{CLOSE_DATE}`
- decision: `accepted_with_todos`
- bundle_closed: `true`
- reader_regenerated: `false`
- reader_state: `59/82, research_draft, rejected`
- sample_quality_allowed: `false`
- repository_publish: `not_authorized_not_performed`
- remote_ci: `TODO_AFTER_EXPLICIT_PUBLISH`

## Outcome

Bundle 9 已在本地完成自下而上预测、显式利润与现金流桥、三情景、敏感性、分析师差异、静态/动态估值、四家同业上下文、反向估值和情景市值区间。Canonical workflow 继续保持 `needs_fix`，下一路由切换到 Bundle 10 的动态 Writer、跨行业回归与人工审查；这不是 Reader 或样例质量许可。

## Close Evidence

| item | result |
|---|---|
| forecast assumptions | 42 rows; all carry evidence and metric anchors |
| forecast model | three business lines; three scenarios; 2026E-2028E |
| profit bridge | nine scenario-years; maximum reconciliation difference 0 |
| forecast sensitivity | 12 rows across revenue, margin, opex and working capital |
| market inputs | one reviewed subject row and four same-date peer rows |
| dynamic valuation | base PE 193.6x / 137.2x / 105.7x for 2026E-2028E |
| scenario valuation | three 2027E market-cap ranges with explicit multiple assumptions |
| reverse valuation | five PE stress points reconciled to current market cap |
| analyst context | two-broker midpoint comparison; three analyst_view rows |
| quality decision | accepted_with_todos; no active critical/high issue |
| full regression | {summary} |

## Preserved Gaps

1. 液冷独立收入、毛利率与利润贡献仍为 `MISSING_DISCLOSURE`。
2. 同业远期倍数与全部官方年报逐项数值对账尚未完成，peer set 保持低置信。
3. 企业价值、净负债、折现率和终值增速缺失，DCF 保持跳过。
4. 液冷独立经济性与未分配成本缺失，SOTP 保持跳过。
5. Reader、动态 Writer、两个跨行业样本、人工审查与最终样例质量门仍属 Bundle 10。

## Next Route

`research-orchestrator -> stock-deep-dive -> quality-review`，进入 Bundle 10；动态 Writer 必须消费结构化 pack，不得自由新增公司事实或估值数字。

## Research Boundary

本 readout 记录研究模型与工作流状态，不形成交易动作或收益承诺。
"""
    (run / "bundle9_close_readout.md").write_text(text, encoding="utf-8")


def append_run_log(run: Path, regression: Mapping[str, Any]) -> bool:
    path = run / "run_log.md"
    text = path.read_text(encoding="utf-8")
    marker = "## Bundle 9 local close"
    if marker in text:
        return False
    summary = regression["full_repository"]["summary"]
    addition = f"""

{marker}

| Step | Status | Notes |
|---|---|---|
| Forecast assumptions | done | 42 reviewed assumptions with evidence and metric anchors. |
| Bottom-up model | done | Three audited broad business lines; bear/base/bull; 2026E-2028E. |
| Profit and cash flow bridge | done | Expenses, tax, minority profit, working capital and capex separated; reconciliation difference 0. |
| Forecast sensitivity | done | 12 rows covering revenue growth, gross margin, opex and working capital. |
| Valuation inputs | accepted | One subject and four peer market rows; peer set remains low confidence. |
| Valuation methods | accepted_with_todos | Static, dynamic, scenario and reverse used; DCF and SOTP remain unsupported. |
| Quality gate | accepted_with_todos | No active critical/high issue; sample-quality permission remains false. |
| Regression | done_local | Full repository pytest: {summary}. |
| Canonical close | done_local | Bundle 9 closed; workflow remains needs_fix; Reader remains 59/82 rejected; next route is Bundle 10. |
| Publish boundary | preserved | No staging, commit, push or remote CI claim was performed. |
"""
    path.write_text(text.rstrip() + addition + "\n", encoding="utf-8")
    return True


def close_bundle9(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    run = repo_root / "reports/workflow_runs" / WORKFLOW_ID
    validation = json.loads((run / "R5_bundle9_close_input_validation.json").read_text(encoding="utf-8"))
    if validation.get("decision") != "pass":
        raise ValueError("Bundle 9 deterministic validation is not pass")
    quality_text = (run / "bundle9_quality_report.md").read_text(encoding="utf-8")
    if "decision: `accepted_with_todos`" not in quality_text:
        raise ValueError("Bundle 9 quality decision is not accepted_with_todos")
    regression = load_yaml(run / "R5_bundle9_regression_summary.yaml")
    if regression.get("full_repository", {}).get("status") != "pass":
        raise ValueError("Bundle 9 full repository regression is not pass")
    render_close_readout(run, regression)
    state_result = update_workflow_state(run, regression)
    todo_result = update_open_todos(run)
    artifact_result = update_artifact_manifest(repo_root, run)
    log_appended = append_run_log(run, regression)
    return {
        "artifact_type": "R5_bundle9_close_result",
        "schema_version": "v0.1",
        "workflow_id": WORKFLOW_ID,
        "decision": "accepted_with_todos",
        "bundle_closed": True,
        "next_stage": "R5_bundle10_dynamic_writer_regression",
        "state": state_result,
        "open_todos": todo_result,
        "artifact_manifest": artifact_result,
        "run_log_appended": log_appended,
        "reader_regenerated": False,
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Close Bundle 9 locally after quality and regression checks.")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    result = close_bundle9(Path(args.repo_root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
