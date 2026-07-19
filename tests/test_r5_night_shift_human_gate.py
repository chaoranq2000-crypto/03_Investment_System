from __future__ import annotations

from pathlib import Path

from src.maintenance.night_shift.backflow import build_human_handoffs, load_occurrences


def test_human_gate_handoffs_leave_all_decision_fields_empty() -> None:
    handoffs = build_human_handoffs(load_occurrences(Path(__file__).resolve().parents[1]))
    assert handoffs["handoff_count"] == 3
    for item in handoffs["handoffs"]:
        assert item["reviewer"] is None
        assert item["reviewed_at"] is None
        assert item["decision"] is None
        assert item["decision_notes"] is None
        assert item["auto_accept_allowed"] is False
        assert len(item["candidate_sha256"] or "") == 64
