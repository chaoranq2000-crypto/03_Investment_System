from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
KERNEL = ROOT / "docs" / "workflows" / "RESEARCH_WORKFLOW.md"
ORCHESTRATION = ROOT / "docs" / "workflows" / "WORKFLOW_ORCHESTRATION_SPEC.md"
OWNERSHIP = ROOT / "docs" / "meta" / "DOC_OWNERSHIP_MATRIX.md"
QUALITY_POLICY = ROOT / "docs" / "policies" / "QUALITY_GUARDRAILS.md"
ORCHESTRATOR_SKILL = ROOT / ".agents" / "skills" / "research-orchestrator" / "SKILL.md"
QUALITY_SKILL = ROOT / ".agents" / "skills" / "quality-review" / "SKILL.md"
ISSUE_SCHEMA = (
    ROOT
    / ".agents"
    / "skills"
    / "quality-review"
    / "references"
    / "issue_schema.md"
)
STATE_TEMPLATE = (
    ROOT
    / ".agents"
    / "skills"
    / "research-orchestrator"
    / "assets"
    / "workflow_state_template.yaml"
)
STATE_SCHEMA_DOC = (
    ROOT
    / ".agents"
    / "skills"
    / "research-orchestrator"
    / "references"
    / "workflow_state_schema.md"
)

CROSS_LAYER_OR_DERIVED_FIELDS = {
    "automated_report_quality_passed",
    "system_v1_complete",
    "p2_ready",
    "release_ready",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ordinary_template_excludes_cross_layer_and_derived_fields() -> None:
    state = yaml.safe_load(read(STATE_TEMPLATE))
    assert state["sample_quality_ready"] is False
    assert "decision" not in state["final_report_review"]
    for field in CROSS_LAYER_OR_DERIVED_FIELDS:
        assert field not in state


def test_kernel_separates_run_state_from_project_release_and_p2_evidence() -> None:
    kernel = read(KERNEL)
    assert "普通研究 run 只维护" in kernel
    assert "自动报告质量" in kernel and "派生" in kernel
    assert "普通细分、个股" in kernel and "不保存其全局副本" in kernel
    assert "不是普通研究 run 的完成字段" in kernel
    assert "旧字段也不是新 run 的写入合同" in kernel


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
    issue_schema = read(ISSUE_SCHEMA)
    quality_skill = read(QUALITY_SKILL)
    assert "G0–G10" in kernel
    assert "mapped_global_gate_ids" in issue_schema
    assert "local_check_id" in issue_schema
    assert "local_check_id" in quality_skill
    assert "只有 canonical gate id" in orchestration
    assert "不得产生第二套 global gate" in ownership


def test_runtime_projects_owner_facts_without_copying_a_second_contract() -> None:
    orchestration = read(ORCHESTRATION)
    ownership = read(OWNERSHIP)
    assert "只投影 owner 已经形成的事实" in orchestration
    assert "不得再手写同义结论" in orchestration
    assert "只链接各自证据 owner" in orchestration
    assert "ordinary run outcome and sample-quality meaning" in ownership
    assert "project integration and release evidence" in ownership
    assert "P2 readiness" in ownership


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


def test_local_and_legacy_checks_require_explicit_capability_handoffs() -> None:
    kernel = read(KERNEL)
    orchestration = read(ORCHESTRATION)
    assert "显式 capability-local evaluator" in kernel
    assert "退出普通 orchestrator 的默认 routing" in kernel
    assert "evaluator 不直接写 `workflow_state.status`" in kernel
    assert "canonical state" in kernel
    assert "Explicit capability-local evaluator dispatch" in orchestration
    assert "Only when a handoff explicitly names" in orchestration
    assert "never" in orchestration and "canonical" in orchestration


def test_kernel_owns_the_only_active_final_report_human_review_boundary() -> None:
    kernel = read(KERNEL)
    orchestration = read(ORCHESTRATION)
    policy = read(QUALITY_POLICY)
    orchestrator_skill = read(ORCHESTRATOR_SKILL)
    quality_skill = read(QUALITY_SKILL)
    ownership = read(OWNERSHIP)
    core_consumers = "\n".join(
        (kernel, orchestration, policy, orchestrator_skill, quality_skill)
    )
    assert "automated_report_quality_passed: false" not in core_consumers
    assert "decision: not_requested" not in core_consumers
    assert "workflow_state_schema.md" in kernel
    assert "workflow_state_schema.md" in orchestration
    assert "workflow_state_schema.md" in policy
    assert "workflow_state_schema.md" in orchestrator_skill
    assert "workflow_state_schema.md" in quality_skill
    assert "机器验证与唯一最终报告人工审核" in kernel
    assert "只有最终报告的 SHA-256 绑定人工审核" in kernel
    assert "不得转化为并行人审" in kernel
    assert "不得迁移旧 reviewer 身份" in orchestration
    assert "final-report review fields and transitions" in ownership


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
