from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Mapping

import pytest

from src.investment_review.artifact_io import canonical_json_bytes
from src.investment_review.cli import main as review_main
from src.investment_review.episode_review import (
    EpisodeReviewError,
    build_facts_only_episode_review,
    load_episode_review,
    query_episode_review,
    render_episode_review_markdown,
    replay_validate_episode_review,
    save_episode_review,
    validate_episode_review,
)


FACT_SECTION_NAMES = (
    "timeline",
    "security_context",
    "portfolio_context",
    "market_context",
    "outcome_context",
    "execution_consistency",
)
INTERPRETATION_SECTION_NAMES = (
    "main_tensions",
    "hypotheses",
    "alternative_explanations",
    "counterfactual_options",
    "history_links",
)
TEMPORAL_ROLES = {
    "known_at_decision",
    "learned_during_episode",
    "known_after_episode",
    "not_applicable",
}


def _load_p2f1_fixture_helpers() -> ModuleType:
    """Reuse the production-chain fixture without making tests a Python package."""

    module_name = "_investment_review_p2f1_fixture_helpers"
    existing = sys.modules.get(module_name)
    if isinstance(existing, ModuleType):
        return existing
    source_path = Path(__file__).with_name(
        "test_investment_review_review_input_bundle.py"
    )
    spec = importlib.util.spec_from_file_location(module_name, source_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


P2F1 = _load_p2f1_fixture_helpers()


def _review_content_id(artifact: Mapping[str, Any]) -> str:
    material = deepcopy(dict(artifact))
    material.pop("content_id", None)
    return "sha256:" + hashlib.sha256(canonical_json_bytes(material)).hexdigest()


def _rehash(artifact: dict[str, Any]) -> dict[str, Any]:
    artifact["content_id"] = _review_content_id(artifact)
    return artifact


def _rehash_fact(fact: dict[str, Any]) -> dict[str, Any]:
    material = deepcopy(fact)
    material.pop("fact_id", None)
    fact["fact_id"] = "fact:" + hashlib.sha256(
        canonical_json_bytes(material)
    ).hexdigest()[:32]
    return fact


def _findings(validation: Mapping[str, Any]) -> set[str]:
    return {
        str(item.get("code"))
        for item in validation.get("findings", [])
        if isinstance(item, Mapping)
    }


def _facts(
    artifact: Mapping[str, Any], section: str | None = None
) -> list[dict[str, Any]]:
    sections = artifact.get("fact_sections") or {}
    names: Iterable[str] = (section,) if section is not None else FACT_SECTION_NAMES
    return [
        dict(fact)
        for name in names
        for fact in (sections.get(name) or {}).get("facts", [])
        if isinstance(fact, Mapping)
    ]


def _all_values(value: object) -> Iterable[object]:
    yield value
    if isinstance(value, Mapping):
        for nested in value.values():
            yield from _all_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _all_values(nested)


def _strings(value: object) -> Iterable[str]:
    for item in _all_values(value):
        if isinstance(item, str):
            yield item


def _with_payload(source: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(source))
    result["payload"] = deepcopy(dict(payload))
    result["content_id"] = P2F1._value_content_id(result["payload"])
    return result


def _plan_decision(
    source: Mapping[str, Any], *, quantity: str
) -> dict[str, Any]:
    return _with_payload(
        source,
        {
            "source_id": str(source["source_id"]),
            "statement": "structured execution plan",
            "execution_plan": {
                "event_id": "buy-1",
                "symbol": "600000.SH",
                "side": "BUY",
                "quantity": quantity,
            },
        },
    )


def _outcome_source(
    source: Mapping[str, Any], *, realized_pnl: str
) -> dict[str, Any]:
    return _with_payload(
        source,
        {
            "source_id": str(source["source_id"]),
            "statement": "realized episode outcome",
            "claim_type": "fact",
            "final": True,
            "realized_pnl": realized_pnl,
            "currency": "CNY",
        },
    )


def _assert_blocked(validation: Mapping[str, Any]) -> None:
    assert validation["validation_status"] == "blocked", validation
    assert _findings(validation), validation


@pytest.fixture
def chain(tmp_path: Path) -> Any:
    return P2F1._fixture_chain(tmp_path)


@pytest.fixture
def bundle(chain: Any) -> dict[str, Any]:
    return P2F1._build_bundle(chain)


@pytest.fixture
def review(bundle: dict[str, Any]) -> dict[str, Any]:
    return build_facts_only_episode_review(bundle)


def test_f2_01_complete_input_builds_exactly_six_valid_fact_sections(
    review: dict[str, Any],
) -> None:
    assert review["schema_version"] == "p2f.episode_review.v1"
    assert tuple(review["fact_sections"]) == FACT_SECTION_NAMES
    assert all(
        set(review["fact_sections"][name])
        == {
            "status",
            "reason",
            "source_ids",
            "warning_codes",
            "gap_codes",
            "facts",
        }
        for name in FACT_SECTION_NAMES
    )
    assert validate_episode_review(review)["validation_status"] != "blocked"
    fact_ids = [fact["fact_id"] for fact in _facts(review)]
    assert fact_ids
    assert len(fact_ids) == len(set(fact_ids))


def test_f2_01_facts_only_governance_and_empty_interpretations_are_exact(
    review: dict[str, Any],
) -> None:
    assert review["interpretation_sections"] == {
        name: [] for name in INTERPRETATION_SECTION_NAMES
    }
    assert review["revision"] == {
        "revision_no": 1,
        "status": "draft",
        "supersedes_content_id": None,
        "correction_reason": None,
    }
    assert review["governance"] == {
        "facts_interpretation_separated": True,
        "no_advice": True,
        "no_mechanical_score": True,
        "generation_mode": "facts_only",
        "model_generation": None,
        "human_reviews": [],
    }


def test_input_bundle_reference_is_an_exact_content_binding(
    bundle: dict[str, Any], review: dict[str, Any]
) -> None:
    assert review["input_bundle_ref"] == {
        "schema_version": bundle["schema_version"],
        "content_id": bundle["content_id"],
        "episode_id": bundle["episode_ref"]["episode_id"],
    }
    assert review["content_id"] == _review_content_id(review)


def test_f2_02_timeline_uses_canonical_episode_event_order(
    bundle: dict[str, Any], review: dict[str, Any]
) -> None:
    expected_event_ids = [
        item["event_id"]
        for item in bundle["frozen_sources"]["episode"]["event_refs"]
    ]
    timeline = [
        item
        for item in _facts(review, "timeline")
        if item["kind"] == "execution_event"
    ]
    assert len(timeline) == len(expected_event_ids)
    assert [item["source_refs"][0]["source_id"] for item in timeline] == (
        expected_event_ids
    )
    assert all(item["temporal_role"] == "learned_during_episode" for item in timeline)


def test_f2_03_same_second_events_remain_ambiguous_without_narrative_order(
    tmp_path: Path,
) -> None:
    ambiguous_chain = P2F1._fixture_chain(
        tmp_path,
        events=[
            P2F1._event("buy-1", sequence=None),
            P2F1._event("sell-1", at=P2F1.BASE, side="SELL", sequence=None),
        ],
        decisions=[],
        supplemental=[],
    )
    artifact = build_facts_only_episode_review(P2F1._build_bundle(ambiguous_chain))
    timeline = artifact["fact_sections"]["timeline"]
    assert timeline["status"] == "ambiguous"
    assert "AMBIGUOUS_EVENT_ORDER" in {
        *timeline["warning_codes"],
        *timeline["gap_codes"],
    }
    execution_facts = [
        fact for fact in timeline["facts"] if fact["kind"] == "execution_event"
    ]
    assert execution_facts
    assert all(
        "AMBIGUOUS_EVENT_ORDER" in fact["warning_codes"]
        for fact in execution_facts
    )
    statements = " ".join(fact["statement"].lower() for fact in timeline["facts"])
    assert not any(token in statements for token in ("first", "then", "先发生", "随后"))


def test_same_second_opening_decision_remains_explicitly_ambiguous(
    tmp_path: Path,
) -> None:
    decision_ref = P2F1._decision_ref(
        "decision-same-second",
        "buy-1",
        effective_at=P2F1.BASE - timedelta(minutes=20),
        knowledge_at=P2F1.BASE,
    )
    same_second_chain = P2F1._fixture_chain(
        tmp_path,
        events=[
            P2F1._event("buy-1", decision_refs=[decision_ref]),
            P2F1._event(
                "sell-1",
                at=P2F1.BASE + timedelta(hours=1),
                side="SELL",
                sequence=2,
            ),
        ],
        decisions=[
            P2F1._optional_source(
                "decision-same-second",
                "decision",
                effective_at=P2F1.BASE - timedelta(minutes=20),
                knowledge_at=P2F1.BASE,
                event_id="buy-1",
                relation="execution",
            )
        ],
        supplemental=[],
    )
    artifact = build_facts_only_episode_review(P2F1._build_bundle(same_second_chain))
    decision = next(
        fact for fact in _facts(artifact, "security_context")
        if fact["kind"] == "recorded_decision"
    )
    link = next(
        fact for fact in _facts(artifact, "execution_consistency")
        if fact["kind"] == "decision_execution_link"
    )
    warning = "SAME_SECOND_DECISION_AVAILABILITY_AMBIGUOUS"
    assert decision["availability"] == "ambiguous"
    assert decision["temporal_role"] == "learned_during_episode"
    assert warning in decision["warning_codes"]
    assert link["availability"] == "ambiguous"
    assert link["data"]["link_status"] == "ambiguous"
    assert warning in link["warning_codes"]
    assert warning in artifact["fact_sections"]["execution_consistency"]["gap_codes"]

    mutated = deepcopy(artifact)
    target = next(
        fact for fact in _facts_container(mutated)
        if fact["kind"] == "recorded_decision"
    )
    target["availability"] = "available"
    target["warning_codes"].remove(warning)
    _rehash_fact(target)
    _rehash(mutated)
    validation = validate_episode_review(mutated)
    _assert_blocked(validation)
    assert "SAME_SECOND_DECISION_AMBIGUITY_MISSING" in _findings(validation)


def test_f2_04_no_decision_is_an_explicit_execution_gap_not_an_inference(
    tmp_path: Path,
) -> None:
    no_decision_chain = P2F1._fixture_chain(
        tmp_path,
        events=[
            P2F1._event("buy-1"),
            P2F1._event(
                "sell-1",
                at=P2F1.BASE + timedelta(hours=1),
                side="SELL",
                sequence=2,
            ),
        ],
        decisions=[],
        supplemental=[],
    )
    artifact = build_facts_only_episode_review(P2F1._build_bundle(no_decision_chain))
    security = artifact["fact_sections"]["security_context"]
    execution = artifact["fact_sections"]["execution_consistency"]
    assert security["status"] == "available"
    assert execution["status"] == "unlinked"
    assert any(
        "DECISION" in code
        for code in [*execution["warning_codes"], *execution["gap_codes"]]
    )
    assert execution["facts"] == []


def test_f2_05_missing_market_context_has_no_invented_description(
    tmp_path: Path,
) -> None:
    no_market_chain = P2F1._fixture_chain(
        tmp_path,
        supplemental=[],
    )
    artifact = build_facts_only_episode_review(P2F1._build_bundle(no_market_chain))
    market = artifact["fact_sections"]["market_context"]
    assert market["status"] == "missing"
    assert market["facts"] == []
    assert any(
        "MARKET" in code
        for code in [*market["warning_codes"], *market["gap_codes"]]
    )


def test_f2_06_outcome_is_never_promoted_to_decision_time_fact(
    review: dict[str, Any],
) -> None:
    outcome = _facts(review, "outcome_context")
    assert outcome
    assert all(fact["temporal_role"] == "known_after_episode" for fact in outcome)
    assert all(fact["temporal_role"] != "known_at_decision" for fact in outcome)


def test_f2_07_self_rehashed_outcome_backfill_is_rejected_offline_and_replay(
    bundle: dict[str, Any], review: dict[str, Any]
) -> None:
    mutated = deepcopy(review)
    outcome = _facts(mutated, "outcome_context")
    assert outcome
    target_id = outcome[0]["fact_id"]
    target = next(
        item
        for item in mutated["fact_sections"]["outcome_context"]["facts"]
        if item["fact_id"] == target_id
    )
    target["temporal_role"] = "known_at_decision"
    _rehash_fact(target)
    _rehash(mutated)
    _assert_blocked(validate_episode_review(mutated))
    _assert_blocked(
        replay_validate_episode_review(mutated, input_bundle=bundle)
    )


def test_f2_08_every_fact_source_ref_closes_over_the_frozen_inventory(
    bundle: dict[str, Any], review: dict[str, Any]
) -> None:
    inventory = {
        item["source_id"]: item for item in bundle["source_inventory"]
    }
    for fact in _facts(review):
        assert fact["source_refs"], fact
        for source_ref in fact["source_refs"]:
            source = inventory[source_ref["source_id"]]
            assert set(source_ref) == {
                "source_id",
                "source_kind",
                "content_id",
                "locator",
                "frozen_pointer",
            }
            assert source_ref == {
                key: source[key]
                for key in (
                    "source_id",
                    "source_kind",
                    "content_id",
                    "locator",
                    "frozen_pointer",
                )
            }


def test_f2_08_missing_source_ref_is_rejected_after_self_rehash(
    review: dict[str, Any],
) -> None:
    mutated = deepcopy(review)
    target = next(item for item in _facts(mutated) if item["source_refs"])
    live_target = next(
        item
        for item in _facts_container(mutated)
        if item["fact_id"] == target["fact_id"]
    )
    live_target["source_refs"] = []
    _rehash_fact(live_target)
    _rehash(mutated)
    _assert_blocked(validate_episode_review(mutated))


def test_unknown_source_ref_is_rejected_after_self_rehash(
    bundle: dict[str, Any], review: dict[str, Any],
) -> None:
    mutated = deepcopy(review)
    target = next(item for item in _facts_container(mutated) if item["source_refs"])
    target["source_refs"][0]["source_id"] = "source-that-is-not-frozen"
    _rehash_fact(target)
    _rehash(mutated)
    _assert_blocked(
        replay_validate_episode_review(mutated, input_bundle=bundle)
    )


def _facts_container(artifact: Mapping[str, Any]) -> Iterable[dict[str, Any]]:
    for name in FACT_SECTION_NAMES:
        for fact in artifact["fact_sections"][name]["facts"]:
            yield fact


def test_f2_09_missing_sections_do_not_synthesize_zero_false_or_none_facts(
    tmp_path: Path,
) -> None:
    sparse_chain = P2F1._fixture_chain(
        tmp_path,
        decisions=[],
        supplemental=[],
    )
    artifact = build_facts_only_episode_review(P2F1._build_bundle(sparse_chain))
    for name in ("market_context", "outcome_context", "execution_consistency"):
        section = artifact["fact_sections"][name]
        assert section["status"] in {"missing", "unlinked"}
        assert section["facts"] == []
        assert section["gap_codes"]
    assert not any(isinstance(value, float) for value in _all_values(artifact))


def test_f2_10_structured_plan_match_is_factual_and_not_a_quality_judgment(
    chain: Any,
) -> None:
    decision = _plan_decision(chain.decisions[0], quantity="100")
    artifact = build_facts_only_episode_review(
        P2F1._build_bundle(chain, decisions=[decision])
    )
    facts = _facts(artifact, "execution_consistency")
    comparisons = [fact for fact in facts if fact["kind"] == "plan_execution_comparison"]
    assert comparisons
    quantity = [fact for fact in comparisons if fact["data"]["field"] == "planned_quantity"]
    assert quantity
    assert all(fact["data"]["result"] == "matches" for fact in quantity)
    assert all(fact["data"]["planned_value"] == "100" for fact in quantity)
    assert all(fact["data"]["actual_value"] == "100" for fact in quantity)
    assert all(len(fact["source_refs"]) >= 2 for fact in comparisons)
    assert not _contains_quality_judgment(facts)


def test_f2_11_structured_plan_deviation_records_difference_without_excuse(
    chain: Any,
) -> None:
    decision = _plan_decision(chain.decisions[0], quantity="200")
    artifact = build_facts_only_episode_review(
        P2F1._build_bundle(chain, decisions=[decision])
    )
    facts = _facts(artifact, "execution_consistency")
    comparisons = [fact for fact in facts if fact["kind"] == "plan_execution_comparison"]
    assert comparisons
    quantity = [fact for fact in comparisons if fact["data"]["field"] == "planned_quantity"]
    assert quantity
    assert all(fact["data"]["result"] == "deviates" for fact in quantity)
    assert all(fact["data"]["planned_value"] == "200" for fact in quantity)
    assert all(fact["data"]["actual_value"] == "100" for fact in quantity)
    assert not _contains_quality_judgment(facts)


def test_conflicting_structured_plan_fields_are_gapped_not_silently_chosen(
    chain: Any,
) -> None:
    source = chain.decisions[0]
    decision = _with_payload(
        source,
        {
            "source_id": str(source["source_id"]),
            "planned_quantity": "100",
            "execution_plan": {
                "event_id": "buy-1",
                "quantity": "200",
            },
        },
    )
    artifact = build_facts_only_episode_review(
        P2F1._build_bundle(chain, decisions=[decision])
    )
    section = artifact["fact_sections"]["execution_consistency"]
    assert "STRUCTURED_PLAN_CONTRADICTION" in section["gap_codes"]
    assert not any(
        fact["kind"] == "plan_execution_comparison"
        and fact["data"]["field"] == "planned_quantity"
        for fact in section["facts"]
    )


def _contains_quality_judgment(value: object) -> bool:
    material = " ".join(_strings(value)).lower()
    prohibited = (
        "good trade",
        "bad trade",
        "correct decision",
        "wrong decision",
        "decision was correct",
        "decision was wrong",
        "好交易",
        "坏交易",
        "决策正确",
        "决策错误",
    )
    return any(token in material for token in prohibited)


@pytest.mark.parametrize("realized_pnl", ["125.50", "-125.50"])
def test_f2_12_f2_13_profit_or_loss_never_labels_decision_quality(
    chain: Any, realized_pnl: str
) -> None:
    outcome = _outcome_source(chain.supplemental[1], realized_pnl=realized_pnl)
    artifact = build_facts_only_episode_review(
        P2F1._build_bundle(
            chain,
            supplemental=[chain.supplemental[0], outcome],
        )
    )
    facts = _facts(artifact, "outcome_context")
    assert any(fact["data"].get("realized_pnl") == realized_pnl for fact in facts)
    assert not _contains_quality_judgment(artifact)
    assert not any(
        key in {"score", "rating", "recommendation"}
        for key in _mapping_keys(artifact)
    )


def test_non_fact_outcome_cannot_publish_final_or_realized_pnl(chain: Any) -> None:
    source = chain.supplemental[1]
    estimate = _with_payload(
        source,
        {
            "source_id": str(source["source_id"]),
            "claim_type": "estimate",
            "final": True,
            "realized_pnl": "125.50",
            "currency": "CNY",
        },
    )
    artifact = build_facts_only_episode_review(
        P2F1._build_bundle(
            chain,
            supplemental=[chain.supplemental[0], estimate],
        )
    )
    fact = _facts(artifact, "outcome_context")[0]
    assert fact["data"]["source_claim_type"] == "estimate"
    assert fact["data"]["final"] is False
    assert "realized_pnl" not in fact["data"]
    assert "OUTCOME_CLAIM_NOT_FACT" in fact["warning_codes"]
    assert "FINAL_OUTCOME_UNVERIFIED" in artifact["fact_sections"][
        "outcome_context"
    ]["gap_codes"]


def test_self_consistent_invalid_fact_data_type_is_rejected(
    chain: Any,
) -> None:
    decision = _plan_decision(chain.decisions[0], quantity="100")
    artifact = build_facts_only_episode_review(
        P2F1._build_bundle(chain, decisions=[decision])
    )
    mutated = deepcopy(artifact)
    target = next(
        fact
        for fact in _facts_container(mutated)
        if fact["kind"] == "plan_execution_comparison"
    )
    target["data"]["planned_value"] = ["100"]
    _rehash_fact(target)
    _rehash(mutated)
    validation = validate_episode_review(mutated)
    _assert_blocked(validation)
    assert "FACT_DATA_TYPE_MISMATCH" in _findings(validation)


def test_final_outcome_requires_fact_source_and_post_close_times(
    review: dict[str, Any],
) -> None:
    mutated = deepcopy(review)
    target = next(
        fact
        for fact in _facts_container(mutated)
        if fact["kind"] == "outcome_record"
    )
    target["data"]["source_claim_type"] = "fact"
    target["data"]["final"] = True
    target["effective_at"] = "2026-07-01T02:00:00Z"
    target["knowledge_at"] = "2026-07-01T02:00:00Z"
    _rehash_fact(target)
    _rehash(mutated)
    validation = validate_episode_review(mutated)
    _assert_blocked(validation)
    assert "OUTCOME_FINALITY_INVALID" in _findings(validation)


def test_self_rehashed_opened_at_must_close_over_opening_event(
    review: dict[str, Any],
) -> None:
    mutated = deepcopy(review)
    lifecycle = next(
        fact
        for fact in _facts_container(mutated)
        if fact["kind"] == "episode_lifecycle"
    )
    lifecycle["data"]["opened_at"] = "2026-07-01T01:40:00Z"
    _rehash_fact(lifecycle)
    _rehash(mutated)

    validation = validate_episode_review(mutated)
    _assert_blocked(validation)
    assert "LIFECYCLE_EVENT_CLOSURE_MISMATCH" in _findings(validation)


def test_self_rehashed_closed_at_must_close_over_closing_event(
    review: dict[str, Any],
) -> None:
    mutated = deepcopy(review)
    lifecycle = next(
        fact
        for fact in _facts_container(mutated)
        if fact["kind"] == "episode_lifecycle"
    )
    lifecycle["data"]["closed_at"] = "2026-07-01T04:00:00Z"
    _rehash_fact(lifecycle)
    for fact in _facts_container(mutated):
        if fact["temporal_role"] == "known_after_episode":
            fact["temporal_role"] = "learned_during_episode"
            _rehash_fact(fact)
    _rehash(mutated)

    validation = validate_episode_review(mutated)
    _assert_blocked(validation)
    assert "LIFECYCLE_EVENT_CLOSURE_MISMATCH" in _findings(validation)


def _mapping_keys(value: object) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            yield str(key)
            yield from _mapping_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _mapping_keys(nested)


def test_f2_14_facts_only_markdown_preserves_every_fact_and_source_id(
    review: dict[str, Any],
) -> None:
    rendered = render_episode_review_markdown(review)
    assert review["review_id"] in rendered
    assert review["content_id"] in rendered
    for fact in _facts(review):
        assert fact["fact_id"] in rendered
        for source_ref in fact["source_refs"]:
            assert source_ref["source_id"] in rendered
    assert "facts_only" in rendered


def test_f2_15_repeated_build_is_byte_identical(bundle: dict[str, Any]) -> None:
    first = build_facts_only_episode_review(bundle)
    second = build_facts_only_episode_review(bundle)
    assert first == second
    assert first["content_id"] == second["content_id"]
    assert canonical_json_bytes(first) == canonical_json_bytes(second)


def test_f2_16_illegal_temporal_role_is_rejected_after_self_rehash(
    review: dict[str, Any],
) -> None:
    mutated = deepcopy(review)
    target = next(iter(_facts_container(mutated)))
    target["temporal_role"] = "known_in_the_future"
    _rehash_fact(target)
    _rehash(mutated)
    _assert_blocked(validate_episode_review(mutated))


def test_temporal_roles_and_fact_sorting_are_canonical(review: dict[str, Any]) -> None:
    for name in FACT_SECTION_NAMES:
        facts = review["fact_sections"][name]["facts"]
        assert all(fact["temporal_role"] in TEMPORAL_ROLES for fact in facts)
    assert validate_episode_review(review)["validation_status"] != "blocked"


def test_float_in_fact_is_rejected_even_with_matching_outer_hash(
    review: dict[str, Any],
) -> None:
    mutated = deepcopy(review)
    target = next(iter(_facts_container(mutated)))
    target["statement"] = 1.25
    _assert_blocked(validate_episode_review(mutated))


def test_open_episode_does_not_forge_exit_or_outcome(tmp_path: Path) -> None:
    open_chain = P2F1._fixture_chain(
        tmp_path,
        events=[P2F1._event("buy-1")],
        snapshots=P2F1._default_snapshots()[:2],
        decisions=[],
        supplemental=[],
    )
    artifact = build_facts_only_episode_review(P2F1._build_bundle(open_chain))
    outcome = artifact["fact_sections"]["outcome_context"]
    assert outcome["status"] == "missing"
    assert outcome["facts"] == []
    timeline_text = " ".join(
        fact["statement"].lower() for fact in _facts(artifact, "timeline")
    )
    assert "sell" not in timeline_text
    assert "closed" not in timeline_text


def test_open_episode_self_rehashed_final_outcome_is_rejected(tmp_path: Path) -> None:
    outcome = P2F1._optional_source(
        "outcome-open",
        "outcome",
        effective_at=P2F1.BASE + timedelta(minutes=10),
        knowledge_at=P2F1.BASE + timedelta(minutes=10),
        payload={
            "source_id": "outcome-open",
            "claim_type": "fact",
            "final": True,
            "realized_pnl": "1.00",
            "currency": "CNY",
        },
    )
    open_chain = P2F1._fixture_chain(
        tmp_path,
        events=[P2F1._event("buy-1")],
        snapshots=P2F1._default_snapshots()[:2],
        decisions=[],
        supplemental=[outcome],
    )
    artifact = build_facts_only_episode_review(P2F1._build_bundle(open_chain))
    target = next(
        fact
        for fact in _facts_container(artifact)
        if fact["kind"] == "outcome_record"
    )
    assert target["data"]["final"] is False
    mutated = deepcopy(artifact)
    target = next(
        fact
        for fact in _facts_container(mutated)
        if fact["kind"] == "outcome_record"
    )
    target["data"]["final"] = True
    _rehash_fact(target)
    _rehash(mutated)
    validation = validate_episode_review(mutated)
    _assert_blocked(validation)
    assert "OUTCOME_FINALITY_INVALID" in _findings(validation)


def test_save_load_query_and_render_round_trip(
    tmp_path: Path, review: dict[str, Any]
) -> None:
    output = tmp_path / "episode-review.json"
    assert save_episode_review(output, review) == output
    loaded = load_episode_review(output)
    assert loaded == review
    assert query_episode_review(loaded) == [review]
    assert query_episode_review(loaded, section="timeline") == [
        review["fact_sections"]["timeline"]
    ]
    fact = _facts(review)[0]
    assert query_episode_review(loaded, fact_id=fact["fact_id"]) == [fact]
    assert query_episode_review(loaded, content_id="sha256:" + "0" * 64) == []
    assert render_episode_review_markdown(loaded) == render_episode_review_markdown(review)


def test_query_rejects_an_invalid_artifact(review: dict[str, Any]) -> None:
    mutated = deepcopy(review)
    mutated["content_id"] = "sha256:" + "0" * 64
    with pytest.raises(EpisodeReviewError, match="invalid episode review"):
        query_episode_review(mutated)


@pytest.mark.parametrize("payload", [None, [], "not-an-object", 1, {"fact_sections": []}])
def test_validator_is_total_for_arbitrary_json(payload: object) -> None:
    validation = validate_episode_review(payload)  # type: ignore[arg-type]
    _assert_blocked(validation)


def test_extra_top_level_field_is_rejected_after_self_rehash(
    review: dict[str, Any],
) -> None:
    mutated = deepcopy(review)
    mutated["mechanical_score"] = 100
    _rehash(mutated)
    _assert_blocked(validate_episode_review(mutated))


def test_source_replay_accepts_exact_bundle_and_rejects_another_valid_bundle(
    chain: Any, review: dict[str, Any], bundle: dict[str, Any]
) -> None:
    accepted = replay_validate_episode_review(review, input_bundle=bundle)
    assert accepted["validation_status"] != "blocked"
    assert accepted["source_verification"]["status"] == "verified"

    changed_market = _with_payload(
        chain.supplemental[0],
        {
            "source_id": "market-1",
            "statement": "changed but independently valid market source",
            "decimal_value": "11.25",
        },
    )
    other_bundle = P2F1._build_bundle(
        chain,
        supplemental=[changed_market, chain.supplemental[1]],
    )
    assert other_bundle["content_id"] != bundle["content_id"]
    _assert_blocked(
        replay_validate_episode_review(review, input_bundle=other_bundle)
    )


def test_section_status_and_gap_codes_are_exactly_derived_from_input_bundle(
    bundle: dict[str, Any], review: dict[str, Any]
) -> None:
    for name in FACT_SECTION_NAMES:
        expected = bundle["section_availability"][name]
        section = review["fact_sections"][name]
        assert section["status"] == expected["status"]
        assert section["reason"] == expected["reason"]
        assert section["source_ids"] == expected["source_ids"]
        assert section["warning_codes"] == expected["warning_codes"]
        assert section["warning_codes"] == sorted(set(section["warning_codes"]))
        assert section["gap_codes"] == sorted(set(section["gap_codes"]))


def test_security_fact_is_traceable_to_episode_scope(
    bundle: dict[str, Any], review: dict[str, Any]
) -> None:
    facts = _facts(review, "security_context")
    assert facts
    assert any("600000.SH" in fact["statement"] for fact in facts)
    episode_id = bundle["episode_ref"]["episode_id"]
    assert any(
        source_ref["source_id"] == episode_id
        for fact in facts
        for source_ref in fact["source_refs"]
    )


def test_cli_build_show_validate_and_source_replay_round_trip(
    tmp_path: Path,
    bundle: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "review-input.json"
    P2F1.save_review_input_bundle(input_path, bundle)
    output = tmp_path / "episode-review.json"
    markdown = tmp_path / "episode-review.md"

    assert review_main(
        [
            "episode-review-build",
            "--input-bundle",
            str(input_path),
            "--facts-only",
            "--output",
            str(output),
            "--markdown-output",
            str(markdown),
        ]
    ) == 0
    built = json.loads(capsys.readouterr().out)
    assert built["content_id"].startswith("sha256:")
    assert built["fact_count"] > 0
    assert output.is_file() and markdown.is_file()

    assert review_main(["episode-review-validate", str(output)]) == 0
    assert "accepted" in capsys.readouterr().out
    assert review_main(
        [
            "episode-review-validate",
            str(output),
            "--source-replay",
            "--input-bundle",
            str(input_path),
        ]
    ) == 0
    assert "verified" in capsys.readouterr().out
    assert review_main(
        [
            "episode-review-show",
            str(output),
            "--section",
            "timeline",
        ]
    ) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown[0]["facts"]
