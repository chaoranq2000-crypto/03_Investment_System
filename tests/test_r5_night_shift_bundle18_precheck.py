from __future__ import annotations

from pathlib import Path

from src.maintenance.night_shift.strategic import (
    build_bundle18_precheck,
    build_golden_case_inventory,
)


def test_bundle18_precheck_never_auto_triggers_or_synthesizes_review() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    precheck = build_bundle18_precheck(repo_root, build_golden_case_inventory(repo_root))
    assert precheck["overall_status"] == "not_ready"
    assert precheck["auto_trigger"] is False
    assert precheck["auto_accept"] is False
    assert precheck["ready_case_count"] == 0
    assert all(case["status"] == "not_ready" for case in precheck["cases"])
    assert all(case["checks"]["human_review_pending"] for case in precheck["cases"])
