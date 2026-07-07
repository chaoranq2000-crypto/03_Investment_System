from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (REPO_ROOT / "templates" / name).read_text(encoding="utf-8")


def test_close_readout_template_has_required_sections():
    text = read("r5_workflow_close_readout.md")
    for needle in ["scope", "artifacts", "tests", "quality decision", "open issues", "source gaps", "next tasks", "rollback notes"]:
        assert needle in text


def test_source_gap_template_has_required_columns():
    text = read("r5_source_gap_report.md")
    for needle in ["gap_id", "section", "missing_metric_or_claim", "searched_sources", "current_status", "downgrade_effect", "next_action"]:
        assert needle in text


def test_open_questions_template_has_required_columns():
    text = read("r5_open_questions.md")
    for needle in ["question_id", "owner_skill", "blocking_stage", "evidence_needed", "fallback_decision"]:
        assert needle in text


def test_task_queue_template_has_required_columns():
    text = read("r5_task_queue.md")
    for needle in ["task_id", "patch_name", "allowed_files", "blocked_files", "tests", "acceptance", "status"]:
        assert needle in text


def test_templates_preserve_no_advice_and_source_gap_boundary():
    joined = "\n".join(read(name) for name in ["r5_workflow_close_readout.md", "r5_source_gap_report.md", "r5_open_questions.md", "r5_task_queue.md"])
    assert "Do not output trading advice" in joined
    assert "Do not hide TODO" in joined
