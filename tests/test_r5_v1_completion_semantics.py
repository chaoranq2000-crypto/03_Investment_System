from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KERNEL = ROOT / "docs" / "workflows" / "RESEARCH_WORKFLOW.md"
ORCHESTRATION = ROOT / "docs" / "workflows" / "WORKFLOW_ORCHESTRATION_SPEC.md"
OWNERSHIP = ROOT / "docs" / "meta" / "DOC_OWNERSHIP_MATRIX.md"

TRUTHS = {
    "system_v1_complete",
    "sample_quality_ready",
    "p2_ready",
    "release_ready",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_kernel_owns_four_independent_v1_truths() -> None:
    kernel = read(KERNEL)
    for truth in TRUTHS:
        assert truth in kernel
    assert "四个互不替代的布尔事实" in kernel
    assert "system_v1_complete=true" in kernel
    assert "open `engineering_defect` 为零" in kernel
    assert "不得自动把后三项改为 true" in kernel


def test_external_truth_and_long_term_goal_do_not_move_engineering_completion() -> None:
    kernel = read(KERNEL)
    assert "发行人未披露数据" in kernel
    assert "review_intake_ready" in kernel
    assert "不能写入 canonical" in kernel
    assert "r5_bundle17r_bf2_four_case_activation" in kernel
    assert "保持 open" in kernel


def test_active_run_has_one_current_control_plane() -> None:
    kernel = read(KERNEL)
    orchestration = read(ORCHESTRATION)
    for asset in (
        "workflow_state.yaml",
        "open_todos.csv",
        "quality_gate_report.md",
        "workflow_readout.md",
    ):
        assert asset in kernel
        assert asset in orchestration
    assert "平行 current state" in orchestration
    assert "不能覆盖历史 run" in kernel


def test_local_checks_map_to_the_only_global_gate_set() -> None:
    kernel = read(KERNEL)
    orchestration = read(ORCHESTRATION)
    ownership = read(OWNERSHIP)
    assert "G0–G10" in kernel
    assert "mapped_global_gate_ids" in kernel
    assert "local_check_id" in kernel
    assert "只有 canonical gate id" in orchestration
    assert "不得产生第二套 global gate" in ownership


def test_runtime_consumes_but_does_not_redefine_completion_truths() -> None:
    orchestration = read(ORCHESTRATION)
    ownership = read(OWNERSHIP)
    assert "不在本文件或 runtime 中重定义" in orchestration
    for truth in TRUTHS:
        assert truth in orchestration
        assert truth in ownership


def test_kernel_owns_current_goal_issue_and_outcome_semantics() -> None:
    kernel = read(KERNEL)
    for field in (
        "impact_scope",
        "active_disposition",
        "affected_capabilities",
        "blocks_current_goal",
    ):
        assert field in kernel
    for outcome in (
        "accepted",
        "accepted_with_todos",
        "needs_fix",
        "blocked",
    ):
        assert f"| `{outcome}` |" in kernel
    assert "severity" in kernel
    assert "不能单独决定 `blocks_current_goal`" in kernel
    assert "发行人直接披露" in kernel
    assert "经审计的聚合口径" in kernel
    assert "有界估计 / 情景" in kernel
    assert "unknown 或省略依赖该字段的结论" in kernel


def test_bundle_and_r5_local_checks_are_explicit_capability_evaluators() -> None:
    kernel = read(KERNEL)
    orchestration = read(ORCHESTRATION)
    assert "Bundle11R–16R" in kernel
    assert "退出普通 orchestrator 的默认 routing" in kernel
    assert "不直接写 `workflow_state.status`" in kernel
    assert "不在普通 orchestration 的默认 dispatch 图中" in orchestration
    assert "不得消费 Bundle-local pass/fail 直接覆盖 canonical state" in orchestration


def test_kernel_owns_the_only_active_final_report_human_review_boundary() -> None:
    kernel = read(KERNEL)
    orchestration = read(ORCHESTRATION)
    ownership = read(OWNERSHIP)
    for field in (
        "final_report_review_semantics_version",
        "automated_report_quality_passed",
        "final_report_review_status",
        "final_report_review.report_sha256",
        "final_report_review.change_scope",
    ):
        assert field in kernel or field in orchestration
    assert "机器验证与唯一最终报告人工审核" in kernel
    assert "只有最终报告的 SHA-256 绑定人工审核" in kernel
    assert "不得转化为并行人审" in kernel
    assert "not_requested" in orchestration
    assert "pending" in orchestration
    assert "不得阻止自动 workflow close" in orchestration
    assert "final-report human-review semantics" in ownership


def test_final_review_pending_does_not_become_canonical_ready_for_review() -> None:
    schema = read(
        ROOT
        / ".agents"
        / "skills"
        / "research-orchestrator"
        / "references"
        / "workflow_state_schema.md"
    )
    assert "等待机器质量审查或自动 gate" in schema
    assert "最终报告审核 `pending` 只写入" in schema
