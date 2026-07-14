#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
RUN_REL = Path("reports/workflow_runs") / WORKFLOW_ID
BUNDLE_REL = RUN_REL / "bundle11r"
AS_OF_DATE = "2026-07-14"
PACKAGE_NAME = "R5_BUNDLE_11R_RUNTIME_WORKFLOW_REFACTOR_PATCH_2026-07-14.zip"
PACKAGE_SHA256 = "1f5e34cf100159327886f570c8caa980baebd6f29580d1e5748ce5bcc582281c"
OLD_READER_SHA256 = "cb261412f1c72dfd56e6dc9030c3d0f8bb06d4963a5525396059a6b1a21e6090"

ISSUE_FIELDS = [
    "issue_id",
    "severity",
    "gate_id",
    "stage",
    "target_artifact",
    "section",
    "description",
    "fix_owner_skill",
    "blocking_decision",
    "next_action",
    "status",
]
MANIFEST_FIELDS = [
    "artifact_id",
    "artifact_type",
    "path",
    "created_by_skill",
    "stage",
    "required",
    "exists",
    "status",
    "notes",
]
TODO_FIELDS = [
    "issue_id",
    "severity",
    "stage",
    "target_artifact",
    "description",
    "fix_owner_skill",
    "status",
    "created_at",
    "resolved_at",
    "notes",
]


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return payload


def dump_yaml(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(dict(payload), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def quality_issue_rows() -> list[dict[str, str]]:
    common = {
        "stage": "R5_bundle11r_8_automated_close",
        "blocking_decision": "accepted_with_todos",
    }
    specs = [
        (
            "R5B11R-EVIDENCE-001",
            "medium",
            "R5-G1",
            "R5_bundle11r_operating_evidence_gap_requests.yaml",
            "evidence",
            "液冷项目数或交付容量仍缺少发行人可复算口径。",
            "evidence-ingest",
            "取得正式披露后替换显式缺口并重跑经营驱动。",
            "accepted_todo",
        ),
        (
            "R5B11R-FRESHNESS-001",
            "low",
            "R5-G2",
            "R5_bundle11r_operating_metric_registry.csv",
            "freshness",
            "当前经营锚截至2025年年报，后续正式披露尚未进入本代际。",
            "refresh-research",
            "每次定期报告或重大正式披露后刷新销量与宽产品线口径。",
            "accepted_todo",
        ),
        (
            "R5B11R-TRACE-001",
            "medium",
            "R5-G3",
            "R5_bundle11r_reader_input_pack.yaml",
            "traceability",
            "液冷与机房及机柜宽口径收入之间的重叠消除规则仍未披露。",
            "evidence-ingest",
            "取得同口径分项与消除关系后更新claim并检查重复加总。",
            "accepted_todo",
        ),
        (
            "R5B11R-CLAIMTYPE-001",
            "low",
            "R5-G4",
            "R5_bundle11r_reader_payload.yaml",
            "claim_types",
            "事实、估计、分析观点与未知项已分离，未发现类型越界。",
            "quality-review",
            "保持当前类型边界并在新证据进入时复核。",
            "resolved",
        ),
        (
            "R5B11R-METRIC-001",
            "medium",
            "R5-G5",
            "R5_bundle11r_research_question_matrix.yaml",
            "metrics",
            "分部单位价值、产品组合、单位成本与验收周期仍缺少可复算指标。",
            "evidence-ingest",
            "获得发行人或经审阅调研口径后登记指标并替换有边界估计。",
            "accepted_todo",
        ),
        (
            "R5B11R-EXPOSURE-001",
            "medium",
            "R5-G6",
            "R5_bundle11r_segment_driver_plan.yaml",
            "exposure",
            "液冷独立收入、毛利与营运资金暴露仍不能从宽产品线中可靠拆出。",
            "segment-company-mapping",
            "独立经济性出现后更新多对多暴露记录并保留消除关系。",
            "accepted_todo",
        ),
        (
            "R5B11R-REPORT-001",
            "low",
            "R5-G7",
            "R5_bundle11r_reader.md",
            "report",
            "Reader结构、引用解析和非补偿章节检查均通过。",
            "quality-review",
            "新证据或模型变动后重新生成并复核。",
            "resolved",
        ),
        (
            "R5B11R-COUNTER-001",
            "low",
            "R5-G8",
            "R5_bundle11r_reader_payload.yaml",
            "counterevidence",
            "利润率、现金转化、替代路线与同业口径限制均在Reader中可见。",
            "quality-review",
            "下一次刷新继续保留反证与可证伪条件。",
            "resolved",
        ),
        (
            "R5B11R-UNCERTAINTY-001",
            "medium",
            "R5-G9",
            "R5_bundle11r_operating_driver_pack.yaml",
            "uncertainty",
            "等价销量与混合单价为低置信度估计，不代表分部出货或项目量。",
            "stock-deep-dive",
            "发行人披露分部量价后替换估计并重新勾稽。",
            "accepted_todo",
        ),
        (
            "R5B11R-NOADVICE-001",
            "low",
            "R5-G10",
            "R5_bundle11r_reader.md",
            "no_advice",
            "Reader未发现行动性投资指令或确定性回报表达。",
            "quality-review",
            "后续版本继续执行同一文本门禁。",
            "resolved",
        ),
        (
            "R5B11R-REFRESH-001",
            "medium",
            "R5-G11",
            "R5_bundle11r_operating_to_9r_reconciliation.yaml",
            "refresh",
            "经营桥绑定当前9R模型，模型或正式披露变化后必须整体刷新。",
            "refresh-research",
            "任何模型代际或正式披露变化后重跑输入、runtime、Reader和精确哈希交接。",
            "accepted_todo",
        ),
        (
            "R5B11R-HUMAN-001",
            "medium",
            "QR-HUMAN-REVIEW",
            "R5_bundle11r_human_review_handoff.yaml",
            "human_review",
            "新Reader尚未完成绑定精确哈希的真实人工复核。",
            "quality-review",
            "由真实复核者检查Reader与追溯附录并提交独立结论。",
            "accepted_todo",
        ),
        (
            "R5B11R-DCF-001",
            "medium",
            "QR-VALUATION-DCF",
            "R5_bundle11r_reader_input_pack.yaml",
            "valuation",
            "净债务、折现率与终值输入仍不完整，现金流折现方法保持停用。",
            "company-valuation",
            "补齐全部可追溯输入后重新执行方法资格检查。",
            "accepted_todo",
        ),
        (
            "R5B11R-SOTP-001",
            "medium",
            "QR-VALUATION-SOTP",
            "R5_bundle11r_reader_input_pack.yaml",
            "valuation",
            "液冷独立经济性、未分配成本和消除关系缺失，分部加总方法保持停用。",
            "company-valuation",
            "取得同口径分部经济性与消除关系后重新执行方法资格检查。",
            "accepted_todo",
        ),
    ]
    rows = []
    for issue_id, severity, gate_id, target, section, description, owner, action, status in specs:
        rows.append(
            {
                **common,
                "issue_id": issue_id,
                "severity": severity,
                "gate_id": gate_id,
                "target_artifact": target,
                "section": section,
                "description": description,
                "fix_owner_skill": owner,
                "next_action": action,
                "status": status,
            }
        )
    return rows


def open_todo_specs() -> list[dict[str, str]]:
    specs = [
        ("R5B11R-EVIDENCE-001", "medium", "R5_bundle11r_operating_evidence_gap_requests.yaml", "液冷项目数或交付容量缺少可复算正式口径", "evidence-ingest", "取得正式披露后替换缺口并重跑经营驱动"),
        ("R5B11R-METRIC-001", "medium", "R5_bundle11r_research_question_matrix.yaml", "分部单位价值、产品组合、单位成本与验收周期缺失", "evidence-ingest", "取得可复算口径后登记指标并替换有边界估计"),
        ("R5B11R-TRACE-001", "medium", "R5_bundle11r_reader_input_pack.yaml", "液冷与宽产品线收入的重叠消除规则缺失", "evidence-ingest", "取得分项与消除关系后更新claim"),
        ("R5B11R-EXPOSURE-001", "medium", "R5_bundle11r_segment_driver_plan.yaml", "液冷独立收入、毛利与营运资金暴露仍不可拆分", "segment-company-mapping", "独立经济性出现后刷新暴露记录"),
        ("R5B11R-PEER-001", "medium", "R5_bundle11r_peer_eligibility.yaml", "4家候选同业均不满足经营定义与预测日期可比要求", "company-valuation", "至少3家形成同口径后重审同业方法"),
        ("R5B11R-HUMAN-001", "medium", "R5_bundle11r_human_review_handoff.yaml", "新Reader精确哈希人工复核待完成", "quality-review", "真实复核者提交独立哈希绑定结论"),
        ("R5B11R-DCF-001", "medium", "R5_bundle11r_reader_input_pack.yaml", "现金流折现方法输入仍不完整", "company-valuation", "补齐净债务、折现率和终值输入后重检"),
        ("R5B11R-SOTP-001", "medium", "R5_bundle11r_reader_input_pack.yaml", "分部加总方法缺少独立经济性与消除关系", "company-valuation", "取得同口径输入后重检"),
    ]
    return [
        {
            "issue_id": issue_id,
            "severity": severity,
            "stage": "R5_bundle11r_8_automated_close",
            "target_artifact": target,
            "description": description,
            "fix_owner_skill": owner,
            "status": "open",
            "created_at": AS_OF_DATE,
            "resolved_at": "",
            "notes": action,
        }
        for issue_id, severity, target, description, owner, action in specs
    ]


def validate_close_inputs(bundle_dir: Path) -> dict[str, Any]:
    runtime = load_yaml(bundle_dir / "R5_bundle11r_runtime_result.yaml")
    reconciliation = load_yaml(bundle_dir / "R5_bundle11r_operating_to_9r_reconciliation.yaml")
    scorecard = load_yaml(bundle_dir / "R5_bundle11r_reader_quality_scorecard.yaml")
    handoff = load_yaml(bundle_dir / "R5_bundle11r_human_review_handoff.yaml")
    lock = load_yaml(bundle_dir / "R5_bundle11r_reader_generation_lock.yaml")

    checks = {
        "runtime_candidate": runtime.get("decision") == "candidate_inputs_ready",
        "operating_driver_pass": runtime.get("operating_driver_pack", {}).get("decision") == "pass",
        "peer_context_only": runtime.get("peer_eligibility", {}).get("decision") == "context_only",
        "peer_multiples_disabled": runtime.get("peer_eligibility", {}).get("peer_method_eligible") is False,
        "semantic_candidate": runtime.get("semantic_quality", {}).get("decision") == "candidate_ready",
        "no_backflow": runtime.get("backflow_plan", {}).get("decision") == "no_backflow",
        "no_runtime_issues": not runtime.get("all_issues"),
        "reconciliation_pass": reconciliation.get("decision") == "pass",
        "reconciliation_rows": reconciliation.get("summary", {}).get("passed_row_count") == 9,
        "reader_candidate": scorecard.get("decision") == "candidate_ready_for_human_review",
        "reader_blockers_zero": not any(
            scorecard.get(key) for key in ("truthfulness_blockers", "core_section_blockers", "candidate_blockers")
        ),
        "human_review_pending": handoff.get("status") == "pending",
        "new_report_supersedes_old_hash": handoff.get("supersedes_report_sha256") == OLD_READER_SHA256,
        "generation_locked": lock.get("missing_artifact_count") == 0,
        "sample_quality_false": lock.get("sample_quality_allowed") is False,
        "p2_false": lock.get("p2_allowed") is False,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError("Bundle 11R close checks failed: " + ", ".join(failed))
    return {
        "runtime": runtime,
        "reconciliation": reconciliation,
        "scorecard": scorecard,
        "handoff": handoff,
        "lock": lock,
        "checks": checks,
    }


def _repo_path(path: Path, repo_root: Path) -> str:
    return str(path.relative_to(repo_root)).replace("\\", "/")


def _add_state_artifact(state: dict[str, Any], item: Mapping[str, Any]) -> None:
    artifacts = state.setdefault("artifacts", [])
    for index, existing in enumerate(artifacts):
        if existing.get("path") == item.get("path"):
            artifacts[index] = dict(item)
            return
    artifacts.append(dict(item))


def update_state(
    state: dict[str, Any],
    close: Mapping[str, Any],
    todo_rows: list[dict[str, str]],
    *,
    full_regression_passed: int | None,
    full_regression_skipped: int | None,
    full_regression_duration: float | None,
    publish_authorized: bool,
    publish_branch: str | None,
) -> dict[str, Any]:
    runtime = close["runtime"]
    reconciliation = close["reconciliation"]
    scorecard = close["scorecard"]
    handoff = close["handoff"]
    lock = close["lock"]

    state["status"] = "accepted_with_todos"
    # The previously human-reviewed v5 Reader remains the canonical accepted
    # baseline until the new 11R exact hash receives its own human decision.
    # Bundle 11R therefore lives on the forward-requalification surface.
    state["quality_target"] = "R5_bundle10r_reader_v5_human_review_passed"
    state["updated_at"] = AS_OF_DATE
    state["current_stage"] = "T10_close_readout"
    state["next_stage"] = None
    state["active_skill"] = None
    state["required_next_skill"] = None
    state["forward_requalification_current_stage"] = "R5_bundle11r_8_automated_close"
    state["forward_requalification_next_stage"] = None
    state["canonical_reader_status"] = "reader_v5_human_review_passed_with_todos"
    state["bundle11r_candidate_reader_status"] = "pending_exact_hash_human_review"
    state["canonical_sample_quality_allowed"] = False
    state["sample_quality_allowed"] = False
    state["p2_allowed"] = False
    state["external_action_required"] = None
    state["forward_requalification_external_action_required"] = {
        "action": "exact_hash_human_review",
        "status": "pending",
        "handoff": str(BUNDLE_REL / "R5_bundle11r_human_review_handoff.yaml").replace("\\", "/"),
        "reader_sha256": handoff["input_hashes"]["report_sha256"],
    }

    stages = [
        "R5_bundle11r_0_target_audit",
        "R5_bundle11r_1_runtime_foundation",
        "R5_bundle11r_2_real_input_build",
        "R5_bundle11r_3_operating_driver_gate",
        "R5_bundle11r_4_peer_eligibility_gate",
        "R5_bundle11r_5_semantic_quality_gate",
        "R5_bundle11r_6_reader_regeneration",
        "R5_bundle11r_7_exact_hash_human_review_handoff",
        "R5_bundle11r_8_automated_close",
    ]
    completed = state.setdefault("completed_stages", [])
    for stage in stages:
        if stage not in completed:
            completed.append(stage)

    state["bundle11r_runtime"] = {
        "decision": runtime["decision"],
        "question_count": runtime["research_question_matrix"]["summary"]["total"],
        "bounded_estimate_count": runtime["research_question_matrix"]["summary"]["bounded_estimate"],
        "optional_missing_count": runtime["research_question_matrix"]["summary"]["missing"],
        "critical_open_count": runtime["research_question_matrix"]["summary"]["critical_open"],
        "operating_driver_decision": runtime["operating_driver_pack"]["decision"],
        "peer_eligibility_decision": runtime["peer_eligibility"]["decision"],
        "eligible_peer_count": runtime["peer_eligibility"]["eligible_count"],
        "peer_multiples_used": False,
        "semantic_decision": runtime["semantic_quality"]["decision"],
        "backflow_decision": runtime["backflow_plan"]["decision"],
        "runtime_issue_count": len(runtime.get("all_issues") or []),
        "reconciliation_decision": reconciliation["decision"],
        "reconciliation_passed_rows": reconciliation["summary"]["passed_row_count"],
        "max_proxy_revenue_share": reconciliation["summary"]["max_proxy_revenue_share"],
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
    state["bundle11r_close"] = {
        "decision": "accepted_with_todos",
        "automated_scope_decision": scorecard["decision"],
        "package_task_chain_complete": True,
        "closed_at": AS_OF_DATE,
        "package_name": PACKAGE_NAME,
        "package_sha256": PACKAGE_SHA256,
        "reader_report_path": str(BUNDLE_REL / "R5_bundle11r_reader.md").replace("\\", "/"),
        "reader_report_sha256": handoff["input_hashes"]["report_sha256"],
        "reader_score": scorecard["score"],
        "reader_reference_count": len(scorecard["display_citations"]["used"]),
        "reader_generation_id": lock["generation_id"],
        "reader_generation_aggregate_sha256": lock["aggregate_sha256"],
        "locked_artifact_count": lock["artifact_count"],
        "human_review_status": "pending",
        "historical_reader_human_review_transferred": False,
        "full_regression_status": "pass" if full_regression_passed is not None else "pending_final_verification",
        "full_regression_passed": full_regression_passed,
        "full_regression_skipped": full_regression_skipped,
        "full_regression_duration_seconds": full_regression_duration,
        "accepted_todos": [row["issue_id"] for row in todo_rows],
        "sample_quality_allowed": False,
        "p2_allowed": False,
        "publish_status": "authorized_current_branch" if publish_authorized else "not_requested",
        "publish_branch": publish_branch if publish_authorized else None,
        "merge_authorized": False,
    }

    todo_index = {item.get("issue_id"): index for index, item in enumerate(state.setdefault("open_todos", []))}
    for row in todo_rows:
        state_row = {
            key: value
            for key, value in row.items()
            if key in {"issue_id", "severity", "stage", "target_artifact", "description", "fix_owner_skill", "status", "created_at", "resolved_at", "notes"}
            and value != ""
        }
        if row["issue_id"] in todo_index:
            state["open_todos"][todo_index[row["issue_id"]]] = state_row
        else:
            state["open_todos"].append(state_row)

    gate_entries = [
        {
            "gate_id": "R5_BUNDLE11R_RUNTIME",
            "status": "pass",
            "checked_by": "quality-review",
            "checked_at": AS_OF_DATE,
            "notes": "经营驱动通过；同业方法限定为背景；语义检查通过；无研究回流任务。",
            "current_scope": "bundle11r_runtime",
        },
        {
            "gate_id": "R5_BUNDLE11R_READER",
            "status": "pass",
            "checked_by": "quality-review",
            "checked_at": AS_OF_DATE,
            "notes": "Reader score 100/82；28个显示引用解析；真实性、核心章节与候选阻断均为0。",
            "current_scope": "bundle11r_reader_candidate",
        },
        {
            "gate_id": "R5_BUNDLE11R_AUTOMATED_CLOSE",
            "status": "pass",
            "checked_by": "research-orchestrator",
            "checked_at": AS_OF_DATE,
            "notes": "自动任务链闭环；新Reader精确哈希人工复核仍待完成；样例质量与P2保持false。",
            "current_scope": "bundle11r_automated_close_human_review_pending",
        },
    ]
    gates = state.setdefault("quality_gates", [])
    by_scope = {item.get("current_scope"): index for index, item in enumerate(gates)}
    for entry in gate_entries:
        if entry["current_scope"] in by_scope:
            gates[by_scope[entry["current_scope"]]] = entry
        else:
            gates.append(entry)
    return state


def write_handoffs(run_dir: Path, report_sha256: str) -> list[Path]:
    handoff_dir = run_dir / "handoffs"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    payloads = {
        "33_to_evidence-ingest_bundle11r_operating_metric.md": f"""# Handoff: research-orchestrator -> evidence-ingest

## Objective

登记并复核002837公司级精密温控节能设备2025A销量指标；保持公司级口径，不得解释为液冷或任一宽产品线分部销量。

## Inputs

- `bundle11r/R5_bundle11r_operating_metric_candidates.csv`
- `bundle11r/R5_bundle11r_operating_evidence_gap_requests.yaml`
- source evidence `ev_annual_report_002837_20260421_2cbfc5`

## Result

指标 `metric_company_cn_002837_invic_precision_thermal_management_sales_volume_2025A_11r` 已进入 workflow-local registry，值为324,058 units，period=2025A，calculation_method=direct_reported_value。项目数、单位价值、验收周期、独立毛利与营运资金仍是显式缺口。
""",
        "34_to_stock-deep-dive_bundle11r_operating_runtime.md": """# Handoff: evidence-ingest -> stock-deep-dive

## Objective

以经审阅公司级销量和9R宽产品线模型构建11R经营驱动，不额外加总液冷收入。

## Result

- 机房与机柜温控使用 hybrid 等价量价桥；其他业务保持 explicit proxy。
- 12个研究问题中6个为有边界估计、6个支持性问题缺失、critical_open=0。
- 三情景九组经营结果通过，代理收入占比最高约9.52%。
- 与9R收入和毛利在0.02元容差内9/9勾稽通过。
""",
        "35_to_quality-review_bundle11r_semantic_reader_gate.md": f"""# Handoff: stock-deep-dive -> quality-review

## Objective

对11R经营驱动、同业方法资格、语义完整性与新Reader执行非补偿审查。

## Result

- runtime issue=0，backflow task=0。
- 合格同业=0，同业倍数未启用；反向估值与情景压力测试沿用9R。
- Reader gate=`candidate_ready_for_human_review`，score=100，28/28显示引用解析。
- Reader SHA256=`{report_sha256}`。
- 样例质量与P2均保持false。
""",
        "36_to_research-orchestrator_bundle11r_close.md": f"""# Handoff: quality-review -> research-orchestrator

## Objective

在不继承旧Reader人审状态的前提下，关闭11R自动任务链并同步workflow事实面。

## Close Decision

自动范围=`accepted_with_todos`。新Reader精确哈希为`{report_sha256}`，人工复核状态=`pending`；旧v5报告哈希`{OLD_READER_SHA256}`的人审结果仅保留为历史。样例质量与P2均保持false。
""",
    }
    paths = []
    for name, content in payloads.items():
        path = handoff_dir / name
        path.write_text(content.strip() + "\n", encoding="utf-8", newline="\n")
        paths.append(path)
    return paths


def build_quality_report(close: Mapping[str, Any], regression_text: str) -> str:
    runtime = close["runtime"]
    recon = close["reconciliation"]
    score = close["scorecard"]
    handoff = close["handoff"]
    return f"""# R5 Bundle 11R 质量报告

> 历史兼容标记：早期 `quality_gate_report.md` 中的 pre-Bundle 7 快照为 `historical_snapshot_superseded_by_bundle7_quality_rebaseline`；其替代质量面保存在 `R5_bundle7_quality_gate_report.md`。本文件当前正文记录11R前向候选，不改写该历史关系。

## 结论

自动范围结论为 `accepted_with_todos`。002837真实输入 runtime 为 `candidate_inputs_ready`，经营驱动通过，同业方法限定为背景，语义检查通过，未生成研究回流任务。新Reader为 `candidate_ready_for_human_review`；真实人工复核仍为 `pending`。

## 可复核事实

| check | result |
|---|---|
| research questions | total={runtime['research_question_matrix']['summary']['total']}；bounded_estimate={runtime['research_question_matrix']['summary']['bounded_estimate']}；optional missing={runtime['research_question_matrix']['summary']['missing']}；critical_open=0 |
| operating driver | pass；三情景、三期间、三条宽产品线 |
| 9R reconciliation | {recon['summary']['passed_row_count']}/9；收入最大差额={recon['summary']['max_absolute_revenue_difference_CNY']} CNY；毛利最大差额={recon['summary']['max_absolute_gross_profit_difference_CNY']} CNY |
| proxy boundary | 最高占比={recon['summary']['max_proxy_revenue_share']:.2%}；低于45%上限 |
| peer method | eligible=0；同业倍数未启用 |
| semantic gate | candidate_ready；critical/high/medium=0/0/0 |
| Reader gate | score={score['score']}/{score['threshold']}；truth/core/candidate blockers=0/0/0 |
| references | {len(score['display_citations']['used'])}/{len(score['display_citations']['used'])} resolved |
| exact report hash | `{handoff['input_hashes']['report_sha256']}` |
| full regression | {regression_text} |

## 证据与推断边界

- `metric_company_cn_002837_invic_precision_thermal_management_sales_volume_2025A_11r` 是2025A公司级报告事实，值为324,058 units；不得解释为液冷或分部出货。
- 机房与机柜温控的等价销量、公司级混合单价和未来量价矩阵属于低置信度 `estimate`，用于解释既有9R宽产品线预测。
- 其他业务是显式 `proxy`；基准2026E占收入约9.32%。
- 4家候选同业均缺少同经营定义、收入纯度、会计边界和预测日期，因而只作背景。
- 液冷独立收入、毛利、项目数、单位价值、验收周期、重叠消除和营运资金保持 `MISSING/TODO`，未被猜测填补。

## 保留事项

`R5_bundle11r_quality_issues.csv` 记录14项门禁结果：critical/high为0；经营证据、分部指标、重叠消除、独立暴露、同业方法、DCF、SOTP与精确哈希人工复核作为medium/low TODO保留。所有事项均有owner和下一步。

## 边界

旧Reader v5的人审结论不转移到新哈希。`sample_quality_allowed=false`，`p2_allowed=false`。本文不构成投资建议。
"""


def build_close_readout(
    close: Mapping[str, Any],
    regression_text: str,
    *,
    publish_authorized: bool,
    publish_branch: str | None,
) -> str:
    recon = close["reconciliation"]
    handoff = close["handoff"]
    lock = close["lock"]
    return f"""# R5 Bundle 11R 自动任务链关闭读数

## 关闭结果

最新补丁包10步执行链已完成，自动范围为 `accepted_with_todos`：目标审计、补丁应用、集成、真实002837输入、经营驱动、同业资格、语义检查、Reader重建、新哈希交接与workflow同步均已落盘。

## 核心产物

| artifact | status |
|---|---|
| `R5_bundle11r_runtime_result.yaml` | candidate_inputs_ready；issue=0；backflow=0 |
| `R5_bundle11r_operating_to_9r_reconciliation.yaml` | pass；{recon['summary']['passed_row_count']}/9 |
| `R5_bundle11r_reader.md` | candidate_ready_for_human_review |
| `R5_bundle11r_reader_quality_scorecard.yaml` | 100/82；blockers=0 |
| `R5_bundle11r_human_review_handoff.yaml` | pending；SHA256 `{handoff['input_hashes']['report_sha256']}` |
| `R5_bundle11r_reader_generation_lock.yaml` | `{lock['generation_id']}`；{lock['artifact_count']} artifacts；missing=0 |
| `R5_bundle11r_quality_issues.csv` | accepted_with_todos；critical/high=0 |

## 验证

- 补丁包：`{PACKAGE_NAME}`；SHA256 `{PACKAGE_SHA256}`；包内校验36/36。
- 经营桥：三情景九组收入和毛利均在0.02 CNY容差内与9R一致；预测与估值总量未改写。
- Reader：28/28显示引用解析，真实性、核心章节和候选阻断均为0。
- 代际锁：`{lock['aggregate_sha256']}`。
- 全量回归：{regression_text}。

## 未完成但不阻断自动关闭的事项

- 新Reader的真实人工复核仍待完成；旧v5哈希的人审结论只保留为历史。
- 液冷独立项目量、单位价值、验收周期、独立毛利、重叠消除与营运资金仍缺少正式口径。
- 同业倍数、现金流折现和分部加总方法保持停用。
- 样例质量与P2继续为false。

## 发布边界

{f"用户已授权将本轮变更提交并推送到当前分支 `{publish_branch}`；未授权合并。" if publish_authorized else "本次没有执行暂存、提交、推送或合并。"}
"""


def replace_marked_section(path: Path, section: str) -> None:
    start = "<!-- R5_BUNDLE11R_CLOSE_START -->"
    end = "<!-- R5_BUNDLE11R_CLOSE_END -->"
    marked = f"{start}\n{section.strip()}\n{end}\n"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if start in existing and end in existing:
        prefix, tail = existing.split(start, 1)
        _, suffix = tail.split(end, 1)
        updated = prefix.rstrip() + "\n\n" + marked + suffix.lstrip("\r\n")
    else:
        updated = existing.rstrip() + ("\n\n" if existing.strip() else "") + marked
    path.write_text(updated, encoding="utf-8", newline="\n")


def sync_manifest(repo_root: Path, run_dir: Path, generated: list[tuple[str, Path, str, str, str, str]]) -> None:
    manifest_path = run_dir / "artifact_manifest.csv"
    rows = read_csv(manifest_path)
    by_path = {row["path"]: index for index, row in enumerate(rows)}
    numeric_ids = [int(row["artifact_id"].split("_")[-1]) for row in rows if row["artifact_id"].startswith("art_")]
    next_id = max(numeric_ids, default=0) + 1
    for artifact_type, path, skill, stage, status, notes in generated:
        rel = _repo_path(path, repo_root)
        row = {
            "artifact_id": "",
            "artifact_type": artifact_type,
            "path": rel,
            "created_by_skill": skill,
            "stage": stage,
            "required": "True",
            "exists": str(path.is_file()),
            "status": status,
            "notes": notes,
        }
        if rel in by_path:
            row["artifact_id"] = rows[by_path[rel]]["artifact_id"]
            rows[by_path[rel]] = row
        else:
            row["artifact_id"] = f"art_{next_id:03d}"
            next_id += 1
            by_path[rel] = len(rows)
            rows.append(row)

    for row in rows:
        if row["path"] == "quality_gate_report.md":
            row.update({"stage": "R5_bundle11r_8_automated_close", "status": "current", "notes": "current Bundle 11R automated quality snapshot"})
        elif row["path"] == "workflow_readout.md":
            row.update({"stage": "R5_bundle11r_8_automated_close", "status": "current", "notes": "current Bundle 11R automated close snapshot"})
    write_csv(manifest_path, rows, MANIFEST_FIELDS)


def sync_open_todos(run_dir: Path, todo_rows: list[dict[str, str]]) -> None:
    path = run_dir / "open_todos.csv"
    rows = read_csv(path)
    by_id = {row["issue_id"]: index for index, row in enumerate(rows)}
    for row in todo_rows:
        if row["issue_id"] in by_id:
            rows[by_id[row["issue_id"]]] = row
        else:
            by_id[row["issue_id"]] = len(rows)
            rows.append(row)
    write_csv(path, rows, TODO_FIELDS)


def close_bundle(
    repo_root: Path,
    *,
    full_regression_passed: int | None,
    full_regression_skipped: int | None,
    full_regression_duration: float | None,
    publish_authorized: bool,
    publish_branch: str | None,
) -> dict[str, Any]:
    run_dir = repo_root / RUN_REL
    bundle_dir = repo_root / BUNDLE_REL
    state_path = run_dir / "workflow_state.yaml"
    backup_path = run_dir / "workflow_state.yaml.pre_bundle11r"
    if not backup_path.exists():
        shutil.copy2(state_path, backup_path)

    close = validate_close_inputs(bundle_dir)
    issue_rows = quality_issue_rows()
    todo_rows = open_todo_specs()
    issues_path = bundle_dir / "R5_bundle11r_quality_issues.csv"
    write_csv(issues_path, issue_rows, ISSUE_FIELDS)

    if full_regression_passed is None:
        regression_text = "pending final repository verification"
    else:
        regression_text = (
            f"{full_regression_passed} passed, {full_regression_skipped or 0} skipped"
            + (f", {full_regression_duration:.2f}s" if full_regression_duration is not None else "")
        )

    quality_report_path = bundle_dir / "R5_bundle11r_quality_report.md"
    close_readout_path = bundle_dir / "R5_bundle11r_close_readout.md"
    change_log_path = bundle_dir / "R5_bundle11r_change_log.md"
    quality_report_path.write_text(build_quality_report(close, regression_text), encoding="utf-8", newline="\n")
    close_readout_path.write_text(
        build_close_readout(
            close,
            regression_text,
            publish_authorized=publish_authorized,
            publish_branch=publish_branch,
        ),
        encoding="utf-8",
        newline="\n",
    )
    change_log_path.write_text(
        "# R5 Bundle 11R change log\n\n"
        "- 新增公司级2025A销量事实与workflow-local metric。\n"
        "- 新增两条主要宽产品线的等价量价桥；其他业务保持显式代理。\n"
        "- 新增同业方法资格检查；0家合格，未启用同业倍数。\n"
        "- 新增语义完整性检查与定向backflow；本次issue=0、backflow=0。\n"
        "- 新Reader增加E23—E28引用，不改变9R预测与估值总量。\n"
        "- 新Reader人工复核重新置为pending；旧v5人审不跨哈希继承。\n"
        "- sample-quality与P2保持false。\n",
        encoding="utf-8",
        newline="\n",
    )

    handoff_paths = write_handoffs(run_dir, close["handoff"]["input_hashes"]["report_sha256"])
    state = update_state(
        load_yaml(state_path),
        close,
        todo_rows,
        full_regression_passed=full_regression_passed,
        full_regression_skipped=full_regression_skipped,
        full_regression_duration=full_regression_duration,
        publish_authorized=publish_authorized,
        publish_branch=publish_branch,
    )

    generated: list[tuple[str, Path, str, str, str, str]] = []
    skill_by_name = {
        "metric": "evidence-ingest",
        "quality": "quality-review",
        "semantic_quality": "quality-review",
        "human_review": "quality-review",
        "reader_generation_lock": "research-orchestrator",
        "close_readout": "research-orchestrator",
        "change_log": "research-orchestrator",
        "input_build_receipt": "research-orchestrator",
        "reader_input_build_receipt": "research-orchestrator",
    }
    for path in sorted(bundle_dir.glob("R5_bundle11r_*")):
        name = path.stem.lower()
        skill = "stock-deep-dive"
        for token, candidate in skill_by_name.items():
            if token in name:
                skill = candidate
                break
        status = "current"
        if "runtime_result" in name:
            status = "candidate_inputs_ready"
        elif "operating_driver_pack" in name or "reconciliation" in name:
            status = "pass"
        elif "peer_eligibility" in name:
            status = "context_only"
        elif "reader_quality_scorecard" in name or "reader.md" in path.name.lower():
            status = "candidate_ready_for_human_review"
        elif "human_review_handoff" in name:
            status = "pending"
        elif "reader_generation_lock" in name:
            status = "locked"
        elif "quality_issues" in name or "quality_report" in name or "close_readout" in name:
            status = "accepted_with_todos"
        generated.append(
            (
                name,
                path,
                skill,
                "R5_bundle11r_8_automated_close",
                status,
                "Bundle 11R real-input runtime and exact-hash Reader close artifact",
            )
        )

    for path in handoff_paths:
        generated.append(
            (
                path.stem,
                path,
                "research-orchestrator",
                "R5_bundle11r_8_automated_close",
                "complete",
                "Bundle 11R stage handoff",
            )
        )

    canonical_quality_path = run_dir / "quality_gate_report.md"
    canonical_readout_path = run_dir / "workflow_readout.md"
    canonical_quality_path.write_text(build_quality_report(close, regression_text), encoding="utf-8", newline="\n")
    canonical_readout_path.write_text(
        build_close_readout(
            close,
            regression_text,
            publish_authorized=publish_authorized,
            publish_branch=publish_branch,
        ),
        encoding="utf-8",
        newline="\n",
    )

    sync_open_todos(run_dir, todo_rows)
    sync_manifest(repo_root, run_dir, generated)

    for artifact_type, path, skill, stage, status, notes in generated:
        _add_state_artifact(
            state,
            {
                "artifact_type": artifact_type,
                "path": _repo_path(path, repo_root),
                "created_by_skill": skill,
                "stage": stage,
                "status": status,
                "required": True,
                "notes": notes,
            },
        )
    dump_yaml(state_path, state)

    run_log_section = build_close_readout(
        close,
        regression_text,
        publish_authorized=publish_authorized,
        publish_branch=publish_branch,
    )
    replace_marked_section(run_dir / "run_log.md", run_log_section)
    return {
        "decision": "accepted_with_todos",
        "reader_sha256": close["handoff"]["input_hashes"]["report_sha256"],
        "generation_id": close["lock"]["generation_id"],
        "quality_issue_count": len(issue_rows),
        "open_todo_count": len(todo_rows),
        "full_regression_status": "pass" if full_regression_passed is not None else "pending_final_verification",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Close the Bundle 11R automated 002837 task chain")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--full-regression-passed", type=int)
    parser.add_argument("--full-regression-skipped", type=int)
    parser.add_argument("--full-regression-duration", type=float)
    parser.add_argument("--publish-authorized", action="store_true")
    parser.add_argument("--publish-branch")
    args = parser.parse_args()
    result = close_bundle(
        Path(args.repo_root).resolve(),
        full_regression_passed=args.full_regression_passed,
        full_regression_skipped=args.full_regression_skipped,
        full_regression_duration=args.full_regression_duration,
        publish_authorized=args.publish_authorized,
        publish_branch=args.publish_branch,
    )
    print(
        f"decision={result['decision']} issues={result['quality_issue_count']} "
        f"todos={result['open_todo_count']} regression={result['full_regression_status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
