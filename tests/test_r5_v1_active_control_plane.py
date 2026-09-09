from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELIVERY_BASELINE = "a96c1b717bf15905d72fd142efd946fa01bce666"
PACKAGE_BASELINE = "312adc73821706b0b7ca6aa00e80ee608bd10b32"
HISTORICAL_SCOPE_AUDIT = (
    "reports/p1_6/r5_night_shift/r5_overnight_05_20260723/"
    "validation/scope_audit.json"
)
HISTORICAL_SCOPE_AUDIT_OID = "c50f932c7101a5d54f791dd6e6505a76103eda15"
HISTORICAL_SCOPE_AUDIT_BYTES = 3269
HISTORICAL_SCOPE_AUDIT_SHA256 = (
    "8670a74e180024894126479e73e7fa4ebe4ba284ae4bb80683831c16691ded57"
)
RETAINED_CONTROL_PATHS = (
    "config/r5_readout_canonical_index.yaml",
    "docs/meta/DOCS_REPORTS_RETENTION_DEPENDENCY_MANIFEST.yaml",
    "reports/quality/source_route_quality_report.yaml",
    "reports/workflow_runs/wf_20260725_stock_first_002837_v1_policy_refresh/workflow_state.yaml",
    "reports/workflow_runs/wf_20260725_stock_first_002837_v1_policy_refresh/"
    "validation/replay_receipt.yaml",
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def git_output(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(ROOT), *args], text=True, encoding="utf-8"
    ).strip()


def historical_scope_audit() -> dict[str, object]:
    object_name = f"{DELIVERY_BASELINE}:{HISTORICAL_SCOPE_AUDIT}"
    assert git_output("rev-parse", object_name) == HISTORICAL_SCOPE_AUDIT_OID
    assert (
        int(git_output("cat-file", "-s", object_name))
        == HISTORICAL_SCOPE_AUDIT_BYTES
    )
    payload = subprocess.check_output(
        ["git", "-C", str(ROOT), "cat-file", "blob", object_name]
    )
    assert len(payload) == HISTORICAL_SCOPE_AUDIT_BYTES
    assert hashlib.sha256(payload).hexdigest() == HISTORICAL_SCOPE_AUDIT_SHA256
    parsed = json.loads(payload)
    assert isinstance(parsed, dict)
    return parsed


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


def test_bundle_runtimes_are_explicit_local_evaluators_only() -> None:
    kernel = read("docs/workflows/RESEARCH_WORKFLOW.md")
    skill = read(".agents/skills/research-orchestrator/SKILL.md")
    bundle11_cli = read("scripts/run_r5_bundle11r_runtime.py")
    bundle12_cli = read("scripts/run_r5_bundle12r_operating_evidence_gate.py")
    bundle13_cli = read("scripts/run_r5_bundle13r_evidence_backflow.py")
    bundle_sources = "\n".join(
        read(path)
        for path in (
            "scripts/run_r5_bundle11r_runtime.py",
            "src/research/r5_bundle12r_operating_evidence.py",
            "src/research/r5_bundle13r_evidence_backflow.py",
        )
    )

    assert "退出普通 orchestrator 的默认 routing" in kernel
    assert "调用方明确请求某个 capability" in kernel
    assert "不直接写 `workflow_state.status`" in kernel
    assert "post-10R research-depth stage" not in skill
    assert "def run_runtime(" in bundle11_cli
    assert "result = run_runtime(" in bundle11_cli
    assert "from src.quality.semantic_research_gate import run_semantic_gate" in bundle11_cli
    assert 'parser.add_argument("--segment-plan", required=True)' in bundle11_cli
    assert 'parser.add_argument("--output", required=True)' in bundle11_cli
    assert 'parser.add_argument("--input", required=True' in bundle12_cli
    assert 'parser.add_argument("--output-dir", required=True' in bundle12_cli
    assert 'parser.add_argument("--bundle12r-context-dir", required=True)' in bundle13_cli
    assert 'parser.add_argument("--reviewed-backfill", required=True)' in bundle13_cli
    assert 'parser.add_argument("--output-dir", required=True)' in bundle13_cli
    assert "workflow_state.yaml" not in bundle_sources
    assert "validate_workflow_state" not in bundle_sources
    assert "workflow_state.yaml" not in bundle11_cli
    assert "workflow_state.yaml" not in bundle12_cli + bundle13_cli


def test_v1_history_is_git_recoverable_and_current_control_paths_are_present() -> None:
    assert (
        git_output("merge-base", "--is-ancestor", DELIVERY_BASELINE, PACKAGE_BASELINE)
        == ""
    )
    audit = historical_scope_audit()
    assert audit["passed"] is True
    assert audit["historical_changed_paths"] == []
    assert audit["out_of_scope_paths"] == []
    for relative in RETAINED_CONTROL_PATHS:
        path = ROOT / relative
        assert path.is_file()
        assert path.stat().st_size > 0
        if relative != "docs/meta/DOCS_REPORTS_RETENTION_DEPENDENCY_MANIFEST.yaml":
            assert git_output("ls-files", "--error-unmatch", relative) == relative


def test_legacy_night05_scope_is_frozen_at_delivery_snapshot() -> None:
    audit = historical_scope_audit()
    assert audit["mission_id"] == "r5_overnight_05_20260723"
    assert audit["baseline_commit"] == "d0fc0fb735f0f581619e330b3fa6f1ef1914a276"
    assert audit["git_diff_check"] == "passed"
    assert audit["historical_changed_paths"] == []
    assert audit["out_of_scope_paths"] == []
    assert audit["force_push_used"] is False
    assert audit["main_merged"] is False


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
    assert "活动人审只绑定一次最终报告的当前字节 SHA-256" in kernel
    assert "其他 exact-hash、generation lock" in kernel
    assert "rollback 只保护可变且非幂等的" in kernel
    assert "写入事务" in kernel
    assert "remote receipt 只证明 publication 边界" in kernel
    assert "活动人工审核只" in orchestration
    assert "绑定最终报告当前字节的 SHA-256" in orchestration
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
