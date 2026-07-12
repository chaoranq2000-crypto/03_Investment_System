from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_r5_bundle8_research_depth_plan.py"
SPEC = importlib.util.spec_from_file_location("bundle8_plan", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def issue(code: str, issue_id: str) -> dict:
    return {
        "issue_id": issue_id,
        "code": code,
        "description": code,
        "fix_owner_skill": "test",
        "stage": "test",
        "target_artifact": "test.yaml",
    }


def complete_backflow() -> dict:
    codes = list(MODULE.BUNDLE8_CODES) + list(MODULE.DEFERRED_BUNDLES)
    return {
        "workflow_id": "wf_test",
        "source_decision": "rejected",
        "quality_band": "research_draft",
        "score": 59,
        "threshold": 82,
        "target_state": {
            "status": "needs_fix",
            "required_next_skill": "evidence-ingest",
        },
        "generated_issues": [
            issue(code, f"ISSUE-{index:02d}") for index, code in enumerate(codes, start=1)
        ],
    }


def test_plan_maps_bundle8_and_defers_later_work() -> None:
    plan = MODULE.build_plan(
        complete_backflow(),
        as_of_date="2026-07-12",
        source_path="backflow.yaml",
    )
    assert plan["plan_decision"] == "bundle8_plan_ready"
    assert len(plan["accepted_bundle8_issues"]) == 4
    assert len(plan["deferred_issues"]) == 8
    assert plan["execution_order"][0] == "B8-M3-EVIDENCE-COVERAGE"
    assert plan["execution_order"][-1] == "B8-INTEGRATION-GATE"
    assert plan["state_policy"]["mutate_workflow_state_on_plan"] is False
    assert plan["state_policy"]["reader_regeneration_allowed"] is False


def test_missing_required_bundle8_issue_blocks_plan() -> None:
    backflow = complete_backflow()
    backflow["generated_issues"] = [
        row
        for row in backflow["generated_issues"]
        if row["code"] != "independent_industry_evidence_missing"
    ]
    plan = MODULE.build_plan(
        backflow,
        as_of_date="2026-07-12",
        source_path="backflow.yaml",
    )
    assert plan["plan_decision"] == "bundle8_plan_blocked"
    assert "independent_industry_evidence_missing" in plan["missing_required_codes"]


def test_unknown_backflow_code_is_not_silently_ignored() -> None:
    backflow = complete_backflow()
    backflow["generated_issues"].append(issue("unknown_new_gap", "ISSUE-X"))
    plan = MODULE.build_plan(
        backflow,
        as_of_date="2026-07-12",
        source_path="backflow.yaml",
    )
    assert plan["plan_decision"] == "bundle8_plan_blocked"
    assert plan["unmapped_issues"][0]["code"] == "unknown_new_gap"


def test_wrong_entry_state_blocks_plan() -> None:
    backflow = complete_backflow()
    backflow["target_state"]["status"] = "accepted_sample_quality"
    plan = MODULE.build_plan(
        backflow,
        as_of_date="2026-07-12",
        source_path="backflow.yaml",
    )
    assert plan["entry_state"]["entry_gate_passed"] is False
    assert plan["plan_decision"] == "bundle8_plan_blocked"
