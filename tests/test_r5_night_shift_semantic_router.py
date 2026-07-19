from __future__ import annotations

from src.maintenance.night_shift.contracts import route_pointer_contract


def test_missing_generation_id_routes_upstream_not_to_legacy_field() -> None:
    route = route_pointer_contract(
        missing_pointer="/generation_id",
        observed_fields=["/artifact_type", "/case_id", "/schema_version"],
    )
    assert route["route"] == "upstream_generation_contract"
    assert route["candidate_pointer"] is None
    assert route["resolution_claim_allowed"] is False


def test_missing_quality_boolean_is_not_equivalent_to_decision_pass() -> None:
    route = route_pointer_contract(
        missing_pointer="/candidate_ready_for_exact_hash_review",
        observed_fields=["/decision", "/gate_issues", "/metrics"],
    )
    assert route["route"] == "upstream_quality_contract"
    assert route["candidate_pointer"] is None
