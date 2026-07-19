from __future__ import annotations

from pathlib import Path

from src.maintenance.night_shift.backflow import (
    build_analysis_workbooks,
    build_evidence_requests,
    load_occurrences,
)


def test_evidence_and_analysis_packets_preserve_human_authority() -> None:
    occurrences = load_occurrences(Path(__file__).resolve().parents[1])
    evidence = build_evidence_requests(occurrences)
    analysis = build_analysis_workbooks(occurrences)
    assert evidence["request_count"] == 8
    assert all(item["auto_accept_allowed"] is False for item in evidence["requests"])
    assert all(item["evidence_acceptance"] is None for item in evidence["requests"])
    assert analysis["worksheet_count"] == 24
    assert all(item["analyst_conclusion"] is None for item in analysis["worksheets"])
    assert all(item["auto_judgment_allowed"] is False for item in analysis["worksheets"])
