from __future__ import annotations

import hashlib
import importlib.util
import sys
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Mapping

import pytest

from src.investment_review.artifact_io import canonical_json_bytes
from src.investment_review.episode_interpretation import (
    UnavailableInterpretationProvider,
    build_model_assisted_episode_review,
    validate_interpretation_attempt,
)
from src.investment_review.episode_review import (
    build_facts_only_episode_review,
    render_episode_review_markdown,
    replay_validate_episode_review,
    validate_episode_review,
)
from src.investment_review.episode_revision import (
    apply_human_review,
    diff_episode_reviews,
    query_episode_review_revision,
    validate_revision_chain,
)
from src.investment_review.review_input_bundle import (
    replay_validate_review_input_bundle,
    validate_review_input_bundle,
)


def _load_p2f3_helpers() -> ModuleType:
    module_name = "_investment_review_p2f3_e2e_fixture_helpers"
    existing = sys.modules.get(module_name)
    if isinstance(existing, ModuleType):
        return existing
    source_path = Path(__file__).with_name(
        "test_investment_review_episode_interpretation.py"
    )
    spec = importlib.util.spec_from_file_location(module_name, source_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


P2F3 = _load_p2f3_helpers()
P2F1 = P2F3.P2F1


@pytest.fixture(scope="module")
def complete_chain(tmp_path_factory: pytest.TempPathFactory):
    return P2F1._fixture_chain(tmp_path_factory.mktemp("p2f5-complete"))


def _db_sha256(chain: Any) -> str:
    return hashlib.sha256(chain.portfolio_db.read_bytes()).hexdigest()


def _warning_codes(artifact: Mapping[str, Any]) -> set[str]:
    return {
        str(item.get("code"))
        for item in artifact.get("warnings", [])
        if isinstance(item, Mapping)
    }


def _all_facts(artifact: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        fact
        for section in artifact["fact_sections"].values()
        for fact in section["facts"]
    ]


def _source_replay(
    bundle: Mapping[str, Any],
    chain: Any,
    *,
    decisions: Iterable[Mapping[str, Any]] | None = None,
    supplemental: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    return replay_validate_review_input_bundle(
        bundle,
        episode_collection=chain.collection,
        episode_portfolio_context=chain.portfolio_context,
        portfolio_db=chain.portfolio_db,
        decision_sources=chain.decisions if decisions is None else decisions,
        supplemental_sources=chain.supplemental if supplemental is None else supplemental,
    )


def _human_request(
    action: str,
    target_id: str,
    *,
    reviewed_at: str,
    reason: str,
    corrections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "p2f.human_review_request.v1",
        "action": action,
        "reviewed_at": reviewed_at,
        "actor_ref": "reviewer:p2f5-e2e",
        "reason": reason,
        "target_ids": [target_id],
        "corrections": corrections or [],
    }


def _main_id(artifact: Mapping[str, Any]) -> str:
    return artifact["interpretation_sections"]["main_tensions"][0]["finding_id"]


def _build_complete(chain: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    bundle = P2F1._build_bundle(chain)
    assert _source_replay(bundle, chain)["source_verification"]["status"] == "verified"
    facts = build_facts_only_episode_review(bundle)
    assert replay_validate_episode_review(
        facts, input_bundle=bundle
    )["source_verification"]["status"] == "verified"
    result = P2F3._build(facts)
    assert result.used_fallback is False
    return bundle, facts, result.artifact


def _all_keys(value: object) -> set[str]:
    result: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            result.add(str(key))
            result.update(_all_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            result.update(_all_keys(nested))
    return result


def test_f5_01_complete_episode_runs_full_review_and_render_pipeline(
    complete_chain: Any,
) -> None:
    database_before = _db_sha256(complete_chain)
    bundle, facts, model = _build_complete(complete_chain)
    rev2 = apply_human_review(
        model,
        _human_request(
            "accept",
            _main_id(model),
            reviewed_at="2026-07-01T09:00:00Z",
            reason="The frozen fact references were reviewed.",
        ),
    )
    assert validate_revision_chain([model, rev2])["validation_status"] == "accepted"
    assert replay_validate_episode_review(
        rev2, input_bundle=bundle
    )["source_verification"]["status"] == "verified"
    markdown = render_episode_review_markdown(rev2)
    assert facts["content_id"] != model["content_id"] != rev2["content_id"]
    assert "# 第一部分：事实层" in markdown
    assert "# 第二部分：解释层" in markdown
    assert "不是交易建议" in markdown
    assert _db_sha256(complete_chain) == database_before


def test_f5_02_missing_decision_and_market_degrade_without_invention(
    tmp_path: Path,
) -> None:
    chain = P2F1._fixture_chain(
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
    bundle = P2F1._build_bundle(chain)
    replay = _source_replay(bundle, chain)
    assert replay["validation_status"] != "blocked"
    facts = build_facts_only_episode_review(bundle)
    assert facts["fact_sections"]["market_context"]["status"] == "missing"
    assert facts["fact_sections"]["market_context"]["facts"] == []
    assert facts["fact_sections"]["execution_consistency"]["status"] == "unlinked"
    assert facts["fact_sections"]["execution_consistency"]["facts"] == []
    rendered = render_episode_review_markdown(facts)
    assert "MARKET" in rendered
    assert not any(
        fact["kind"] in {"market_record", "recorded_decision"}
        for fact in _all_facts(facts)
    )
    assert "unknown value: 0" not in rendered.casefold()


def test_f5_03_open_episode_never_forges_exit_or_final_outcome(
    tmp_path: Path,
) -> None:
    chain = P2F1._fixture_chain(
        tmp_path,
        events=[P2F1._event("buy-1")],
        snapshots=P2F1._default_snapshots()[:2],
        decisions=[],
        supplemental=[],
    )
    bundle = P2F1._build_bundle(chain)
    assert _source_replay(bundle, chain)["validation_status"] != "blocked"
    facts = build_facts_only_episode_review(bundle)
    lifecycle = next(fact for fact in _all_facts(facts) if fact["kind"] == "episode_lifecycle")
    assert lifecycle["data"]["status"] == "open"
    assert lifecycle["data"]["closed_at"] is None
    assert lifecycle["data"]["closing_event_id"] is None
    assert facts["fact_sections"]["outcome_context"]["facts"] == []
    timeline = " ".join(
        fact["statement"].casefold()
        for fact in facts["fact_sections"]["timeline"]["facts"]
    )
    assert "sell" not in timeline
    assert "closed" not in timeline


def test_f5_04_cutoff_withholds_future_decision_and_market_sources(
    complete_chain: Any,
) -> None:
    future_decision = deepcopy(complete_chain.decisions[0])
    future_decision["knowledge_at"] = (
        P2F1.CUTOFF + timedelta(seconds=1)
    ).isoformat()
    future_market = P2F1._optional_source(
        "market-future",
        "market_context",
        effective_at=P2F1.CUTOFF + timedelta(seconds=1),
        knowledge_at=P2F1.CUTOFF + timedelta(seconds=2),
    )
    decisions = [future_decision]
    supplemental = [future_market]
    bundle = P2F1._build_bundle(
        complete_chain, decisions=decisions, supplemental=supplemental
    )
    assert validate_review_input_bundle(bundle)["validation_status"] != "blocked"
    assert _source_replay(
        bundle,
        complete_chain,
        decisions=decisions,
        supplemental=supplemental,
    )["source_verification"]["status"] == "verified"
    assert bundle["frozen_sources"]["linked_decisions"] == []
    assert bundle["frozen_sources"]["supplemental_sources"] == []
    assert {
        "DECISION_WITHHELD_BY_CUTOFF",
        "MARKET_CONTEXT_WITHHELD_BY_CUTOFF",
    }.issubset(_warning_codes(bundle))
    facts = build_facts_only_episode_review(bundle)
    assert not any(
        fact["kind"] in {"recorded_decision", "market_record"}
        for fact in _all_facts(facts)
    )
    assert replay_validate_episode_review(
        facts, input_bundle=bundle
    )["source_verification"]["status"] == "verified"


def test_f5_05_model_unavailable_returns_byte_exact_facts(
    complete_chain: Any,
) -> None:
    bundle = P2F1._build_bundle(complete_chain)
    facts = build_facts_only_episode_review(bundle)
    result = build_model_assisted_episode_review(
        facts,
        provider=UnavailableInterpretationProvider("unavailable-e2e-provider"),
        attempted_at="2026-07-01T08:00:00Z",
        parameters={"temperature": "0"},
    )
    assert result.used_fallback is True
    assert canonical_json_bytes(result.artifact) == canonical_json_bytes(facts)
    assert result.attempt["status"] == "fallback_facts_only"
    assert result.attempt["result_review_content_id"] == facts["content_id"]
    assert validate_interpretation_attempt(result.attempt)["validation_status"] == "accepted"


def test_f5_06_unsafe_model_output_falls_back_without_polluting_facts(
    complete_chain: Any,
) -> None:
    _, facts, _ = _build_complete(complete_chain)
    payload = P2F3._response_payload(facts)
    payload["interpretation_sections"]["main_tensions"][0]["statement"] = (
        "The user should buy this security immediately."
    )
    result = P2F3._build(facts, payload)
    assert result.used_fallback is True
    assert canonical_json_bytes(result.artifact) == canonical_json_bytes(facts)
    assert "POLICY_DIRECT_ADVICE" in result.attempt["failure_codes"]
    assert "should buy" not in render_episode_review_markdown(result.artifact).casefold()


def test_f5_07_human_correction_chain_is_auditable_and_replayable(
    complete_chain: Any,
) -> None:
    database_before = _db_sha256(complete_chain)
    bundle, _, model = _build_complete(complete_chain)
    rev2 = apply_human_review(
        model,
        _human_request(
            "accept",
            _main_id(model),
            reviewed_at="2026-07-01T09:00:00Z",
            reason="Initial interpretation accepted after source review.",
        ),
    )
    accepted_id = rev2["governance"]["human_reviews"][-1]["result_target_ids"][0]
    accepted_item = next(
        item
        for item in rev2["interpretation_sections"]["main_tensions"]
        if item["finding_id"] == accepted_id
    )
    replacement = next(
        fact["fact_id"]
        for fact in _all_facts(rev2)
        if fact["fact_id"] not in accepted_item["fact_refs"]
    )
    rev3 = apply_human_review(
        rev2,
        _human_request(
            "correct",
            accepted_id,
            reviewed_at="2026-07-01T10:00:00Z",
            reason="Replace support with the fact selected during human review.",
            corrections=[
                {
                    "operation": "replace_fact_refs",
                    "target_id": accepted_id,
                    "fact_refs": [replacement],
                }
            ],
        ),
    )
    chain = [model, rev2, rev3]
    assert validate_revision_chain(chain)["validation_status"] == "accepted"
    assert replay_validate_episode_review(
        rev3, input_bundle=bundle
    )["source_verification"]["status"] == "verified"
    difference = diff_episode_reviews(rev2, rev3)
    assert difference["facts_unchanged"] is True
    assert difference["declared_target_ids"] == [accepted_id]
    assert canonical_json_bytes(
        query_episode_review_revision(chain, revision_no=1)
    ) == canonical_json_bytes(model)
    assert len(rev3["governance"]["human_reviews"]) == 2
    assert _db_sha256(complete_chain) == database_before


def test_f5_08_reordered_inputs_produce_identical_complete_artifacts(
    complete_chain: Any,
) -> None:
    database_before = _db_sha256(complete_chain)
    bundle_a = P2F1._build_bundle(complete_chain)
    bundle_b = P2F1._build_bundle(
        complete_chain,
        decisions=list(reversed(complete_chain.decisions)),
        supplemental=list(reversed(complete_chain.supplemental)),
    )
    assert canonical_json_bytes(bundle_a) == canonical_json_bytes(bundle_b)
    facts_a = build_facts_only_episode_review(bundle_a)
    facts_b = build_facts_only_episode_review(bundle_b)
    assert canonical_json_bytes(facts_a) == canonical_json_bytes(facts_b)
    model_a = P2F3._build(facts_a).artifact
    model_b = P2F3._build(facts_b).artifact
    assert canonical_json_bytes(model_a) == canonical_json_bytes(model_b)
    request = _human_request(
        "accept",
        _main_id(model_a),
        reviewed_at="2026-07-01T09:00:00Z",
        reason="Deterministic human review fixture.",
    )
    rev_a = apply_human_review(model_a, request)
    rev_b = apply_human_review(model_b, request)
    assert canonical_json_bytes(rev_a) == canonical_json_bytes(rev_b)
    assert render_episode_review_markdown(rev_a) == render_episode_review_markdown(rev_b)
    assert _db_sha256(complete_chain) == database_before


def test_f5_09_successful_release_artifact_has_no_advice_or_score_fields(
    complete_chain: Any,
) -> None:
    _, _, model = _build_complete(complete_chain)
    revised = apply_human_review(
        model,
        _human_request(
            "accept",
            _main_id(model),
            reviewed_at="2026-07-01T09:00:00Z",
            reason="Safety fields and evidence links checked.",
        ),
    )
    assert validate_episode_review(revised)["validation_status"] == "accepted"
    assert revised["governance"]["no_advice"] is True
    assert revised["governance"]["no_mechanical_score"] is True
    assert _all_keys(revised).isdisjoint(
        {
            "buy_signal",
            "sell_signal",
            "position_size",
            "recommendation",
            "rating",
            "score",
        }
    )
    rendered = render_episode_review_markdown(revised).casefold()
    assert "不是交易建议" in rendered
    assert "should buy" not in rendered
    assert "should sell" not in rendered
