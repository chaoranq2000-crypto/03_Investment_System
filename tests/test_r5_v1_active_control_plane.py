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
