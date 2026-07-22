from __future__ import annotations

import subprocess
from pathlib import Path

from src.maintenance.night_shift.night05 import DELIVERY_COMMIT, build_scope_audit


ROOT = Path(__file__).resolve().parents[1]
BASELINE = "a96c1b717bf15905d72fd142efd946fa01bce666"
PROTECTED_PATHS = (
    "data/raw",
    "reports/p1_6/r5_bundle17r",
    "reports/p1_6/r5_night_shift/r5_overnight_02_20260720",
    "reports/p1_6/r5_night_shift/r5_overnight_03_20260721",
    "reports/p1_6/r5_night_shift/r5_overnight_04_20260722",
    "reports/p1_6/r5_night_shift/r5_overnight_05_20260723",
    "reports/workflow_runs/wf_20260703_stock_first_002837_invic",
    "AGENTS.md",
    ".github",
    "pyproject.toml",
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def git_output(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(ROOT), *args], text=True, encoding="utf-8"
    ).strip()


def test_canonical_entrypoint_and_state_owner_are_explicit() -> None:
    kernel = read("docs/workflows/RESEARCH_WORKFLOW.md")
    skill = read(".agents/skills/research-orchestrator/SKILL.md")
    state_schema = read(
        ".agents/skills/research-orchestrator/references/workflow_state_schema.md"
    )
    validator = read(
        ".agents/skills/research-orchestrator/scripts/validate_workflow_state.py"
    )
    assert "唯一全局 workflow kernel" in kernel
    assert "本 skill 是执行入口，不是全局事实源" in skill
    assert "only field-level reference" in state_schema
    assert '"review_intake_ready"' not in validator


def test_local_and_historical_runtimes_do_not_replace_the_orchestrator() -> None:
    skill = read(".agents/skills/research-orchestrator/SKILL.md")
    bundle_cli = read("scripts/run_r5_bundle11r_runtime.py")
    night_cli = read("scripts/run_r5_night_shift.py")
    assert "post-10R research-depth stage" in skill
    assert "src.research.r5_bundle11r_runtime" in bundle_cli
    assert "night-shift mission dispatcher" in night_cli
    assert "return runtime_main(arguments)" in night_cli


def test_v1_protected_history_is_unchanged_from_the_night05_delivery() -> None:
    assert DELIVERY_COMMIT == BASELINE
    committed = git_output(
        "diff", "--name-only", f"{BASELINE}..HEAD", "--", *PROTECTED_PATHS
    )
    working = git_output(
        "diff", "--name-only", BASELINE, "--", *PROTECTED_PATHS
    )
    untracked_or_modified = git_output(
        "status", "--short", "--untracked-files=all", "--", *PROTECTED_PATHS
    )
    assert committed == ""
    assert working == ""
    assert untracked_or_modified == ""


def test_legacy_night05_scope_is_frozen_at_delivery_snapshot() -> None:
    audit = build_scope_audit(ROOT)
    assert audit["scope_head"] == BASELINE
    assert audit["scope_mode"] == "frozen_delivery_snapshot"
    assert audit["historical_changed_paths"] == []
    assert audit["out_of_scope_paths"] == []


def test_orchestration_contract_is_only_a_compatibility_pointer() -> None:
    compatibility = read(
        ".agents/skills/research-orchestrator/references/orchestration_contract.md"
    )
    assert "compatibility pointer" in compatibility
    assert "WORKFLOW_ORCHESTRATION_SPEC.md" in compatibility
    assert "state_schema_version: r5_v1" in compatibility
    assert "ready_for_limited_p2" not in compatibility
    assert "## Workflow run directory" not in compatibility
    assert "## Readout format" not in compatibility


def test_r5_and_data_layer_checks_have_explicit_global_gate_mappings() -> None:
    quality_skill = read(".agents/skills/quality-review/SKILL.md")
    r5_mapping = read(".agents/skills/quality-review/references/r5_quality_gate.md")
    data_layer = read("src/qa/data_layer_quality_review.py")
    for field in (
        "local_check_id",
        "mapped_global_gate_ids",
        "applicable_boundary",
        "failure_backflow",
    ):
        assert field in quality_skill or field in r5_mapping
    assert "| `R5-G10` | `G9` |" in r5_mapping
    assert "| `R5-G11` | `G7` |" in r5_mapping
    assert '"DLQ-1": ("G1",)' in data_layer
    assert '"gate_id": mapped_gate_ids[0]' in data_layer
    assert '"local_check_id": local_check_id' in data_layer


def test_high_cost_controls_are_bound_to_their_real_risk_boundaries() -> None:
    kernel = " ".join(read("docs/workflows/RESEARCH_WORKFLOW.md").split())
    orchestration = " ".join(
        read("docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md").split()
    )
    assert "exact-hash 只绑定已经冻结、即将交给人的 review 输入" in kernel
    assert "rollback 只保护可变且非幂等的" in kernel
    assert "写入事务" in kernel
    assert "remote receipt 只证明 publication 边界" in kernel
    assert "exact-hash 只用于" in orchestration
    assert "rollback 只用于可变、非幂等写入" in orchestration
    assert "remote receipt 只用于 publication" in orchestration


def test_bundle7_backflow_is_an_explicit_legacy_compatibility_tool() -> None:
    backflow = read("scripts/reconcile_r5_quality_backflow.py")
    assert "DEFAULT_RUN" not in backflow
    assert 'parser.add_argument("--workflow-run", required=True)' in backflow
    assert "--legacy-compatibility" in backflow
    assert "cannot update an active r5_v1 state" in backflow
    assert '"local_check_id": LOCAL_CHECK_ID' in backflow
    assert '"status": "historical_compatibility"' in backflow
