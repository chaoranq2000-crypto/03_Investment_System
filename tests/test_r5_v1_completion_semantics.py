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
