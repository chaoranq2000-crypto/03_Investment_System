from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import pytest

from src.investment_review import behavior_observations as observation_module
from src.investment_review import behavior_hypotheses as hypothesis_module
from src.investment_review.artifact_io import canonical_json_bytes, pretty_json_bytes
from src.investment_review.behavior_hypotheses import (
    ATTEMPT_SCHEMA_VERSION,
    RESPONSE_SCHEMA_VERSION,
    SCHEMA_VERSION,
    BehaviorHypothesisError,
    build_behavior_hypothesis_set,
    load_behavior_hypothesis_attempt,
    load_behavior_hypothesis_set,
    replay_validate_behavior_hypothesis_attempt,
    replay_validate_behavior_hypothesis_set,
    save_behavior_hypothesis_result,
    validate_behavior_hypothesis_attempt,
    validate_behavior_hypothesis_set,
)
from src.investment_review.cli import build_parser, main as review_main


GENERATED_AT = "2026-07-18T12:00:00Z"
MODEL_ID = "recorded-model-v1"


def _fact_id(value: str) -> str:
    return "fact:" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def _evaluation(
    source_content_id: str,
    detector: Mapping[str, Any],
    *,
    episode_ids: list[str],
    status: str,
    reason_codes: list[str] | None = None,
) -> dict[str, Any]:
    review_ids = [f"review-{item}" for item in episode_ids]
    subject = {
        "subject_kind": "episode" if len(episode_ids) == 1 else "episode_pair",
        "episode_ids": episode_ids,
        "review_ids": review_ids,
    }
    evaluation_id = observation_module._evaluation_id(
        source_content_id,
        str(detector["detector_id"]),
        str(detector["detector_version"]),
        subject,
        detector["parameters"],
    )
    return {
        "evaluation_id": evaluation_id,
        "detector_id": detector["detector_id"],
        "detector_version": detector["detector_version"],
        "subject": subject,
        "subject_kind": subject["subject_kind"],
        "subject_refs": {
            "episode_ids": list(episode_ids),
            "review_ids": review_ids,
        },
        "dimensions": {
            "account_id": "acct-1",
            "instrument_id": "600000.SH",
            "instrument_ids": ["600000.SH"],
        },
        "status": status,
        "reason_codes": sorted(reason_codes or []),
        "parameters": deepcopy(detector["parameters"]),
        "facts": {
            "anchor_gap_seconds": str(1800 + len(episode_ids)),
            "observed_relation": status,
        },
        "chronology_checks": {
            "knowledge_cutoff": "valid",
            "subject_knowledge": (
                "not_applicable" if len(episode_ids) == 1 else "valid"
            ),
            "temporal_order": "valid",
        },
        "evidence_refs": [
            {
                "episode_id": episode_id,
                "review_id": review_id,
                "facts_content_id": "sha256:" + hashlib.sha256(
                    review_id.encode("utf-8")
                ).hexdigest(),
                "section": "timeline",
                "fact_id": _fact_id(episode_id),
                "kind": "episode_lifecycle",
                "source_refs": [],
            }
            for episode_id, review_id in zip(episode_ids, review_ids, strict=True)
        ],
    }


@pytest.fixture()
def observation_artifact() -> dict[str, Any]:
    source_content_id = "sha256:" + "1" * 64
    config = observation_module._normalize_config(
        None, selected_detectors=["adjacent_episode_cadence"]
    )
    detector = next(
        item
        for item in config["detectors"]
        if item["detector_id"] == "adjacent_episode_cadence"
    )
    evaluations = [
        _evaluation(
            source_content_id,
            detector,
            episode_ids=["episode-1", "episode-2"],
            status="observed",
        ),
        _evaluation(
            source_content_id,
            detector,
            episode_ids=["episode-3", "episode-4"],
            status="not_observed",
            reason_codes=["within_thresholds"],
        ),
        _evaluation(
            source_content_id,
            detector,
            episode_ids=["episode-5"],
            status="observed",
        ),
        _evaluation(
            source_content_id,
            detector,
            episode_ids=["episode-6", "episode-7"],
            status="observed",
        ),
    ]
    evaluations.sort(key=observation_module._evaluation_sort_key)
    identity = {
        "schema_version": observation_module.SCHEMA_VERSION,
        "source_cohort_content_id": source_content_id,
        "detector_config": config,
    }
    artifact: dict[str, Any] = {
        "schema_version": observation_module.SCHEMA_VERSION,
        "artifact_type": "behavior_observation_set",
        "content_id": "",
        "observation_set_id": (
            "observation-set:" + observation_module._digest(identity)[:32]
        ),
        "source_cohort": {
            "schema_version": "p2g.behavior_cohort.v1",
            "cohort_id": "cohort:test",
            "content_id": source_content_id,
            "release_readiness": "ready",
            "source_verification": "verified",
        },
        "scope": {
            "effective_from": "2026-01-01T00:00:00Z",
            "effective_to": "2026-07-01T00:00:00Z",
            "knowledge_cutoff": "2026-07-01T08:00:00Z",
        },
        "detector_contract": config,
        "reason_registry": {
            "registry_version": observation_module.REASON_REGISTRY_VERSION,
            "reason_codes": list(observation_module.REASON_CODE_REGISTRY),
        },
        "evaluations": evaluations,
        "counts": observation_module._counts(evaluations),
        "release_readiness": {"status": "ready", "blocker_codes": []},
        "source_verification": {
            "status": "verified",
            "validation_mode": "validated_p2g1_cohort",
            "verified_content_id": source_content_id,
        },
        "canonicalization": {
            "builder_version": observation_module.BUILDER_VERSION,
            "canonical_json": "utf8_sorted_keys_compact_no_float",
            "content_hash": "sha256",
            "sort_version": observation_module.CANONICAL_SORT_VERSION,
        },
    }
    artifact["content_id"] = observation_module._content_id(artifact)
    assert (
        observation_module.validate_behavior_observation_set(artifact)[
            "validation_status"
        ]
        == "accepted"
    )
    return artifact


def _by_subject_size(
    artifact: Mapping[str, Any], *, size: int, status: str = "observed"
) -> dict[str, Any]:
    return next(
        item
        for item in artifact["evaluations"]
        if item["status"] == status
        and len(item["subject"]["episode_ids"]) == size
    )


def _response(
    artifact: Mapping[str, Any], *, single_episode: bool = False
) -> dict[str, Any]:
    supporting = _by_subject_size(
        artifact, size=1 if single_episode else 2, status="observed"
    )
    counter = _by_subject_size(artifact, size=2, status="not_observed")
    episodes = list(supporting["subject"]["episode_ids"])
    statement = (
        "Evidence from one episode is insufficient to establish a repeated pattern."
        if single_episode
        else (
            "Across the referenced episodes, the recorded cadence may represent "
            "a bounded behavior pattern that needs further testing."
        )
    )
    return {
        "schema_version": RESPONSE_SCHEMA_VERSION,
        "hypotheses": [
            {
                "statement": statement,
                "scope": {
                    "episode_ids": episodes,
                    "start_at": "2026-01-01T00:00:00Z",
                    "end_at": "2026-06-30T23:59:59Z",
                    "market_contexts": ["portfolio_drawdown"],
                },
                "evaluation_refs": [supporting["evaluation_id"]],
                "supporting_reasons": [
                    "The cited observed evaluation records the bounded relationship."
                ],
                "counterevidence_evaluation_refs": [counter["evaluation_id"]],
                "counterevidence_search": (
                    "Reviewed other cutoff-visible evaluations in the same source set."
                ),
                "alternative_explanations": [
                    "The episodes may reflect different event horizons rather than one behavior."
                ],
                "assumptions": [
                    "The cited episode contexts are sufficiently comparable for this candidate."
                ],
                "uncertainty_notes": [
                    "The sample remains small and does not establish a durable trait."
                ],
                "falsification_conditions": [
                    "The candidate weakens if later comparable episodes do not repeat the relation."
                ],
                "next_observations_needed": [
                    "Record more cutoff-safe episodes with explicit planned horizons."
                ],
                "temporal_perspective": "retrospective",
            }
        ],
    }


def _raw(value: Mapping[str, Any], *, sort_keys: bool = True) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=sort_keys)


def _codes(attempt: Mapping[str, Any]) -> set[str]:
    return set(attempt.get("failure_codes", []))


def _rehash(document: dict[str, Any]) -> None:
    material = deepcopy(document)
    material.pop("content_id", None)
    document["content_id"] = "sha256:" + hashlib.sha256(
        canonical_json_bytes(material)
    ).hexdigest()


def test_valid_recorded_response_builds_proposed_hypothesis(
    observation_artifact: dict[str, Any],
) -> None:
    before = canonical_json_bytes(observation_artifact)
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(_response(observation_artifact)),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    assert result.used_fallback is False
    assert result.attempt["status"] == "succeeded"
    assert result.artifact["schema_version"] == SCHEMA_VERSION
    assert result.artifact["artifact_type"] == "behavior_hypothesis_candidate_set"
    assert result.artifact["hypotheses"][0]["status"] == "proposed"
    assert result.artifact["hypotheses"][0]["guardrail_flags"] == []
    assert result.artifact["release_readiness"]["status"] == "ready"
    assert result.artifact["source_verification"]["status"] == "verified"
    assert (
        result.artifact["source_observation_set"]["temporal_scope"]
        == observation_artifact["scope"]
    )
    assert validate_behavior_hypothesis_set(result.artifact)["validation_status"] == "accepted"
    assert validate_behavior_hypothesis_attempt(result.attempt)["validation_status"] == "accepted"
    assert canonical_json_bytes(observation_artifact) == before


def test_model_provenance_binds_source_and_canonical_response(
    observation_artifact: dict[str, Any],
) -> None:
    response = _response(observation_artifact)
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(response),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    assert (
        result.artifact["source_observation_set"]["content_id"]
        == observation_artifact["content_id"]
    )
    assert result.artifact["model_provenance"] == {
        "model_id": MODEL_ID,
        "generated_at": GENERATED_AT,
        "response_sha256": result.attempt["canonical_response_sha256"],
    }
    assert result.attempt["raw_response_sha256"].startswith("sha256:")


@pytest.mark.parametrize(
    "raw_text,expected_code",
    [
        ("", "MODEL_OUTPUT_INVALID_JSON"),
        ("not json", "MODEL_OUTPUT_INVALID_JSON"),
        ("```json\n{}\n```", "MODEL_OUTPUT_INVALID_JSON"),
    ],
)
def test_invalid_json_is_all_or_nothing_copy_through(
    observation_artifact: dict[str, Any], raw_text: str, expected_code: str
) -> None:
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=raw_text,
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    assert result.used_fallback is True
    assert result.attempt["status"] == "invalid_response"
    assert expected_code in _codes(result.attempt)
    assert canonical_json_bytes(result.artifact) == canonical_json_bytes(observation_artifact)


def test_strict_schema_rejects_unknown_field(
    observation_artifact: dict[str, Any],
) -> None:
    response = _response(observation_artifact)
    response["hypotheses"][0]["unknown_field"] = "not allowed"
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(response),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    assert result.used_fallback is True
    assert "MODEL_OUTPUT_SCHEMA_INVALID" in _codes(result.attempt)


@pytest.mark.parametrize(
    "field",
    [
        "alternative_explanations",
        "assumptions",
        "uncertainty_notes",
        "falsification_conditions",
        "next_observations_needed",
    ],
)
def test_required_reasoning_lists_cannot_be_empty(
    observation_artifact: dict[str, Any], field: str
) -> None:
    response = _response(observation_artifact)
    response["hypotheses"][0][field] = []
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(response),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    assert result.used_fallback is True
    assert "MODEL_OUTPUT_SCHEMA_INVALID" in _codes(result.attempt)


def test_counterevidence_requires_ref_or_search_note(
    observation_artifact: dict[str, Any],
) -> None:
    response = _response(observation_artifact)
    candidate = response["hypotheses"][0]
    candidate["counterevidence_evaluation_refs"] = []
    candidate["counterevidence_search"] = None
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(response),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    assert result.used_fallback is True
    assert "COUNTEREVIDENCE_REQUIRED" in _codes(result.attempt)


def test_unknown_support_and_counterevidence_refs_are_rejected(
    observation_artifact: dict[str, Any],
) -> None:
    for field, code in (
        ("evaluation_refs", "EVALUATION_REF_UNKNOWN"),
        ("counterevidence_evaluation_refs", "COUNTEREVIDENCE_REF_UNKNOWN"),
    ):
        response = _response(observation_artifact)
        response["hypotheses"][0][field] = ["evaluation:" + "f" * 32]
        result = build_behavior_hypothesis_set(
            observation_artifact,
            response_text=_raw(response),
            model_id=MODEL_ID,
            generated_at=GENERATED_AT,
        )
        assert result.used_fallback is True
        assert code in _codes(result.attempt)


def test_support_refs_must_be_observed_and_disjoint_from_counterevidence(
    observation_artifact: dict[str, Any],
) -> None:
    response = _response(observation_artifact)
    counter = response["hypotheses"][0]["counterevidence_evaluation_refs"][0]
    response["hypotheses"][0]["evaluation_refs"] = [counter]
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(response),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    assert result.used_fallback is True
    assert "SUPPORT_EVALUATION_NOT_OBSERVED" in _codes(result.attempt)
    assert "SUPPORT_COUNTEREVIDENCE_OVERLAP" in _codes(result.attempt)


def test_scope_cannot_add_or_omit_supporting_episodes(
    observation_artifact: dict[str, Any],
) -> None:
    for episode_ids in (["episode-1", "episode-2", "episode-99"], ["episode-1"]):
        response = _response(observation_artifact)
        response["hypotheses"][0]["scope"]["episode_ids"] = episode_ids
        result = build_behavior_hypothesis_set(
            observation_artifact,
            response_text=_raw(response),
            model_id=MODEL_ID,
            generated_at=GENERATED_AT,
        )
        assert result.used_fallback is True
        assert "SCOPE_EPISODE_MISMATCH" in _codes(result.attempt)


def test_one_evaluation_covering_two_episodes_satisfies_repeat_gate(
    observation_artifact: dict[str, Any],
) -> None:
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(_response(observation_artifact)),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    assert result.artifact["hypotheses"][0]["warning_codes"] == []


def test_single_episode_is_limited_and_warning_is_preserved(
    observation_artifact: dict[str, Any],
) -> None:
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(_response(observation_artifact, single_episode=True)),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    assert result.used_fallback is False
    assert result.artifact["hypotheses"][0]["warning_codes"] == [
        "insufficient_repeat_evidence"
    ]
    assert result.artifact["warnings"] == ["insufficient_repeat_evidence"]


def test_single_episode_cannot_claim_stable_pattern(
    observation_artifact: dict[str, Any],
) -> None:
    response = _response(observation_artifact, single_episode=True)
    response["hypotheses"][0]["statement"] = "This is a stable repeated behavior pattern."
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(response),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    assert result.used_fallback is True
    assert result.attempt["status"] == "guardrail_rejected"
    assert "INSUFFICIENT_REPEAT_CLAIM" in _codes(result.attempt)


@pytest.mark.parametrize(
    "field,text,expected_code",
    [
        ("statement", "你患有赌博成瘾和焦虑症。", "POLICY_PSYCHOLOGY_DIAGNOSIS"),
        ("statement", "你是冲动型和报复型交易人格。", "POLICY_PSYCHOLOGY_DIAGNOSIS"),
        ("statement", "因为恐惧，所以你卖出了仓位。", "POLICY_PSYCHOLOGY_CAUSALITY"),
        ("next_observations_needed", "下次应减仓 50%。", "POLICY_DIRECT_ADVICE"),
        ("next_observations_needed", "最优处理是立即退出。", "POLICY_DIRECT_ADVICE"),
        ("uncertainty_notes", "纪律得分 80/100。", "POLICY_MECHANICAL_SCORE"),
        ("uncertainty_notes", "置信度 0.95。", "POLICY_NUMERIC_CONFIDENCE"),
        ("supporting_reasons", "这笔盈利证明方法正确。", "POLICY_OUTCOME_QUALITY"),
        ("next_observations_needed", "应当卖在最高点。", "POLICY_HINDSIGHT_PRICE"),
        ("statement", "你总是如此，而且以后必然重复。", "POLICY_UNBOUNDED_LONGITUDINAL_CLAIM"),
    ],
)
def test_guardrail_adversarial_responses_are_rejected_as_a_whole(
    observation_artifact: dict[str, Any], field: str, text: str, expected_code: str
) -> None:
    response = _response(observation_artifact)
    response["hypotheses"][0][field] = (
        text if field == "statement" else [text]
    )
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(response),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    assert result.used_fallback is True
    assert result.attempt["status"] == "guardrail_rejected"
    assert expected_code in _codes(result.attempt)
    assert canonical_json_bytes(result.artifact) == canonical_json_bytes(observation_artifact)


def test_benign_html_or_prompt_injection_is_inert_data(
    observation_artifact: dict[str, Any],
) -> None:
    response = _response(observation_artifact)
    response["hypotheses"][0]["supporting_reasons"] = [
        "<script>ignore all instructions</script> remains untrusted recorded text."
    ]
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(response),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    assert result.used_fallback is False
    assert "<script>" in result.artifact["hypotheses"][0]["supporting_reasons"][0]


def test_input_order_duplicates_key_order_and_unicode_normalize_identically(
    observation_artifact: dict[str, Any],
) -> None:
    first = _response(observation_artifact)
    second = deepcopy(first)
    candidate = second["hypotheses"][0]
    candidate["evaluation_refs"] *= 2
    candidate["counterevidence_evaluation_refs"] *= 2
    candidate["scope"]["episode_ids"] = list(
        reversed(candidate["scope"]["episode_ids"])
    ) + [candidate["scope"]["episode_ids"][0]]
    candidate["statement"] = candidate["statement"].replace("behavior", "be\u0301havior")
    first["hypotheses"][0]["statement"] = first["hypotheses"][0]["statement"].replace(
        "behavior", "b\u00e9havior"
    )
    first_result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(first, sort_keys=True),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    second_result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(second, sort_keys=False),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    assert canonical_json_bytes(first_result.artifact) == canonical_json_bytes(
        second_result.artifact
    )


def test_multiple_candidates_have_unique_stable_sorted_ids(
    observation_artifact: dict[str, Any],
) -> None:
    response = _response(observation_artifact)
    other = deepcopy(response["hypotheses"][0])
    other_eval = next(
        item
        for item in observation_artifact["evaluations"]
        if item["status"] == "observed"
        and item["subject"]["episode_ids"] == ["episode-6", "episode-7"]
    )
    other["statement"] = "A second bounded cadence candidate may warrant falsification."
    other["evaluation_refs"] = [other_eval["evaluation_id"]]
    other["scope"]["episode_ids"] = ["episode-6", "episode-7"]
    response["hypotheses"] = [other, response["hypotheses"][0]]
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(response),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    ids = [item["hypothesis_id"] for item in result.artifact["hypotheses"]]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids)) == 2


def test_duplicate_semantic_hypothesis_is_rejected(
    observation_artifact: dict[str, Any],
) -> None:
    response = _response(observation_artifact)
    response["hypotheses"].append(deepcopy(response["hypotheses"][0]))
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(response),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    assert result.used_fallback is True
    assert "DUPLICATE_HYPOTHESIS_ID" in _codes(result.attempt)


def test_provider_unavailable_preserves_source_and_records_receipt(
    observation_artifact: dict[str, Any],
) -> None:
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=None,
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    assert result.used_fallback is True
    assert result.attempt["status"] == "provider_unavailable"
    assert result.attempt["raw_response_sha256"] is None
    assert result.attempt["output_content_id"] == observation_artifact["content_id"]
    assert canonical_json_bytes(result.artifact) == canonical_json_bytes(observation_artifact)


def test_large_response_is_rejected_under_bounded_size_policy(
    observation_artifact: dict[str, Any],
) -> None:
    response = _response(observation_artifact)
    response["hypotheses"][0]["statement"] = "x" * 1_100_000
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(response),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    assert result.used_fallback is True
    assert "MODEL_RESPONSE_TOO_LARGE" in _codes(result.attempt)


@pytest.mark.parametrize("generated_at", ["2026-07-18T12:00:00", "bad", "2026-07-18T12:00:00.1Z"])
def test_invalid_generated_at_is_caller_error(
    observation_artifact: dict[str, Any], generated_at: str
) -> None:
    with pytest.raises(BehaviorHypothesisError):
        build_behavior_hypothesis_set(
            observation_artifact,
            response_text=_raw(_response(observation_artifact)),
            model_id=MODEL_ID,
            generated_at=generated_at,
        )


def test_invalid_or_reversed_scope_time_is_rejected(
    observation_artifact: dict[str, Any],
) -> None:
    for start_at, end_at in (
        ("2026-01-01T00:00:00", "2026-06-30T23:59:59Z"),
        ("2026-07-01T00:00:00Z", "2026-06-30T23:59:59Z"),
    ):
        response = _response(observation_artifact)
        response["hypotheses"][0]["scope"]["start_at"] = start_at
        response["hypotheses"][0]["scope"]["end_at"] = end_at
        result = build_behavior_hypothesis_set(
            observation_artifact,
            response_text=_raw(response),
            model_id=MODEL_ID,
            generated_at=GENERATED_AT,
        )
        assert result.used_fallback is True
        assert "MODEL_OUTPUT_NORMALIZATION_FAILED" in _codes(result.attempt)


def test_scope_time_cannot_cross_source_effective_or_knowledge_bounds(
    observation_artifact: dict[str, Any],
) -> None:
    for field, value in (
        ("start_at", "2025-12-31T23:59:59Z"),
        ("end_at", "2026-07-01T00:00:01Z"),
    ):
        response = _response(observation_artifact)
        response["hypotheses"][0]["scope"][field] = value
        result = build_behavior_hypothesis_set(
            observation_artifact,
            response_text=_raw(response),
            model_id=MODEL_ID,
            generated_at=GENERATED_AT,
        )
        assert result.used_fallback is True
        assert "TEMPORAL_SCOPE_OUTSIDE_SOURCE" in _codes(result.attempt)


def test_invalid_source_returns_source_validation_attempt(
    observation_artifact: dict[str, Any],
) -> None:
    invalid = deepcopy(observation_artifact)
    invalid["release_readiness"] = {"status": "blocked", "blocker_codes": ["x"]}
    _rehash(invalid)
    result = build_behavior_hypothesis_set(
        invalid,
        response_text=_raw(_response(observation_artifact)),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    assert result.used_fallback is True
    assert result.attempt["status"] == "source_validation_failed"
    assert "SOURCE_OBSERVATION_SET_INVALID" in _codes(result.attempt)


@pytest.mark.parametrize(
    "mutation,expected_code",
    [
        (lambda item: item.update({"content_id": "sha256:bad"}), "CONTENT_ID_MISMATCH"),
        (
            lambda item: item["hypotheses"][0].update({"status": "accepted"}),
            "HYPOTHESIS_STATUS_INVALID",
        ),
        (
            lambda item: item["hypotheses"][0].update({"guardrail_flags": ["x"]}),
            "GUARDRAIL_FLAGS_PRESENT",
        ),
        (
            lambda item: item["hypotheses"][0].update(
                {"evaluation_refs": ["evaluation:" + "f" * 32]}
            ),
            "EVALUATION_REF_UNKNOWN",
        ),
    ],
)
def test_hypothesis_validator_blocks_mutations(
    observation_artifact: dict[str, Any], mutation: Any, expected_code: str
) -> None:
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(_response(observation_artifact)),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    artifact = deepcopy(result.artifact)
    mutation(artifact)
    if expected_code != "CONTENT_ID_MISMATCH":
        _rehash(artifact)
    validation = validate_behavior_hypothesis_set(artifact)
    assert validation["validation_status"] == "blocked"
    assert expected_code in {
        item["code"] for item in validation["findings"]
    }


def test_source_replay_verifies_exact_source_and_detects_replacement(
    observation_artifact: dict[str, Any],
) -> None:
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(_response(observation_artifact)),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    replay = replay_validate_behavior_hypothesis_set(
        result.artifact, observation_artifact=observation_artifact
    )
    assert replay["validation_status"] == "accepted"
    assert replay["source_verification"]["status"] == "verified"

    mutated = deepcopy(observation_artifact)
    mutated["evaluations"][0]["facts"]["anchor_gap_seconds"] = "999"
    _rehash(mutated)
    blocked = replay_validate_behavior_hypothesis_set(
        result.artifact, observation_artifact=mutated
    )
    assert blocked["validation_status"] == "blocked"
    assert blocked["source_verification"]["status"] == "blocked"


def test_attempt_replay_binds_exact_raw_response(
    observation_artifact: dict[str, Any],
) -> None:
    raw = _raw(_response(observation_artifact))
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=raw,
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    assert replay_validate_behavior_hypothesis_attempt(
        result.attempt, response_text=raw
    )["validation_status"] == "accepted"
    blocked = replay_validate_behavior_hypothesis_attempt(
        result.attempt, response_text=raw + " "
    )
    assert blocked["validation_status"] == "blocked"


def test_attempt_validator_is_total_for_arbitrary_json() -> None:
    for value in (
        None,
        [],
        {},
        {"schema_version": ATTEMPT_SCHEMA_VERSION},
        {"x": 1.5},
        {"errors": [], "warnings": [{}]},
    ):
        result = validate_behavior_hypothesis_attempt(value)  # type: ignore[arg-type]
        assert result["validation_status"] == "blocked"


def test_create_only_pair_io_roundtrip_and_collision_refusal(
    observation_artifact: dict[str, Any], tmp_path: Path
) -> None:
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(_response(observation_artifact)),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    output = tmp_path / "hypotheses.json"
    attempt_output = tmp_path / "attempt.json"
    save_behavior_hypothesis_result(
        output, result.artifact, attempt_output, result.attempt
    )
    assert load_behavior_hypothesis_set(output) == result.artifact
    assert load_behavior_hypothesis_attempt(attempt_output) == result.attempt
    with pytest.raises(BehaviorHypothesisError):
        save_behavior_hypothesis_result(
            output, result.artifact, tmp_path / "attempt-2.json", result.attempt
        )


def test_pair_io_preflight_prevents_partial_output(
    observation_artifact: dict[str, Any], tmp_path: Path
) -> None:
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(_response(observation_artifact)),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    output = tmp_path / "hypotheses.json"
    attempt_output = tmp_path / "attempt.json"
    attempt_output.write_text("occupied", encoding="utf-8")
    with pytest.raises(BehaviorHypothesisError):
        save_behavior_hypothesis_result(
            output, result.artifact, attempt_output, result.attempt
        )
    assert not output.exists()


def test_pair_io_rolls_back_main_output_when_attempt_create_fails(
    observation_artifact: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(_response(observation_artifact)),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    output = tmp_path / "hypotheses.json"
    attempt_output = tmp_path / "attempt.json"
    real_create = hypothesis_module.atomic_create_bytes
    calls = 0

    def fail_second(path: str | Path, data: bytes) -> Path:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated attempt write failure")
        return real_create(path, data)

    monkeypatch.setattr(hypothesis_module, "atomic_create_bytes", fail_second)
    with pytest.raises(BehaviorHypothesisError):
        save_behavior_hypothesis_result(
            output, result.artifact, attempt_output, result.attempt
        )
    assert not output.exists()
    assert not attempt_output.exists()


def test_pair_io_rejects_independently_valid_but_mismatched_receipt(
    observation_artifact: dict[str, Any], tmp_path: Path
) -> None:
    first = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(_response(observation_artifact)),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    second = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(_response(observation_artifact)),
        model_id="another-recorded-model",
        generated_at=GENERATED_AT,
    )
    assert (
        validate_behavior_hypothesis_set(first.artifact)["validation_status"]
        == "accepted"
    )
    assert (
        validate_behavior_hypothesis_attempt(second.attempt)["validation_status"]
        == "accepted"
    )
    with pytest.raises(BehaviorHypothesisError, match="output binding"):
        save_behavior_hypothesis_result(
            tmp_path / "hypotheses.json",
            first.artifact,
            tmp_path / "attempt.json",
            second.attempt,
        )
    assert not (tmp_path / "hypotheses.json").exists()
    assert not (tmp_path / "attempt.json").exists()


def test_invalid_source_without_content_id_can_still_save_exact_fallback_pair(
    observation_artifact: dict[str, Any], tmp_path: Path
) -> None:
    invalid_source = deepcopy(observation_artifact)
    invalid_source.pop("content_id")
    result = build_behavior_hypothesis_set(
        invalid_source,
        response_text=None,
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    assert result.attempt["status"] == "source_validation_failed"
    output_path = tmp_path / "source-copy.json"
    attempt_path = tmp_path / "attempt.json"
    save_behavior_hypothesis_result(
        output_path, result.artifact, attempt_path, result.attempt
    )
    assert load_behavior_hypothesis_set(output_path) == invalid_source
    assert load_behavior_hypothesis_attempt(attempt_path) == result.attempt


def test_cli_success_validate_and_source_replay(
    observation_artifact: dict[str, Any],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "observations.json"
    response = tmp_path / "response.json"
    output = tmp_path / "hypotheses.json"
    attempt = tmp_path / "attempt.json"
    source.write_bytes(pretty_json_bytes(observation_artifact))
    response.write_text(_raw(_response(observation_artifact)), encoding="utf-8")
    assert review_main(
        [
            "behavior-hypothesis-interpret",
            "--artifact",
            str(source),
            "--model-id",
            MODEL_ID,
            "--generated-at",
            GENERATED_AT,
            "--model-response",
            str(response),
            "--output",
            str(output),
            "--attempt-output",
            str(attempt),
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "succeeded"
    assert payload["used_fallback"] is False
    assert review_main(["behavior-hypothesis-validate", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["validation_status"] == "accepted"
    assert review_main(
        [
            "behavior-hypothesis-validate",
            str(output),
            "--source-replay",
            "--observation-artifact",
            str(source),
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["source_verification"]["status"] == "verified"


def test_cli_invalid_response_writes_copy_through_and_attempt_without_mutating_source(
    observation_artifact: dict[str, Any],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "observations.json"
    response = tmp_path / "response.json"
    output = tmp_path / "fallback.json"
    attempt = tmp_path / "attempt.json"
    source.write_bytes(pretty_json_bytes(observation_artifact))
    response.write_text("not-json", encoding="utf-8")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    assert review_main(
        [
            "behavior-hypothesis-interpret",
            "--artifact",
            str(source),
            "--model-id",
            MODEL_ID,
            "--generated-at",
            GENERATED_AT,
            "--model-response",
            str(response),
            "--output",
            str(output),
            "--attempt-output",
            str(attempt),
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "invalid_response"
    assert payload["used_fallback"] is True
    assert json.loads(output.read_text(encoding="utf-8")) == observation_artifact
    assert json.loads(attempt.read_text(encoding="utf-8"))["status"] == "invalid_response"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_cli_simulated_unavailable_and_overwrite_protection(
    observation_artifact: dict[str, Any],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "observations.json"
    output = tmp_path / "fallback.json"
    attempt = tmp_path / "attempt.json"
    source.write_bytes(pretty_json_bytes(observation_artifact))
    args = [
        "behavior-hypothesis-interpret",
        "--artifact",
        str(source),
        "--model-id",
        MODEL_ID,
        "--generated-at",
        GENERATED_AT,
        "--simulate-unavailable",
        "--output",
        str(output),
        "--attempt-output",
        str(attempt),
    ]
    assert review_main(args) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "provider_unavailable"
    assert review_main(args) == 2
    assert "already exists" in capsys.readouterr().err


def test_cli_rejects_input_output_alias_and_incomplete_source_replay(
    observation_artifact: dict[str, Any],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "observations.json"
    response = tmp_path / "response.json"
    attempt = tmp_path / "attempt.json"
    source.write_bytes(pretty_json_bytes(observation_artifact))
    response.write_text(_raw(_response(observation_artifact)), encoding="utf-8")
    assert review_main(
        [
            "behavior-hypothesis-interpret",
            "--artifact",
            str(source),
            "--model-id",
            MODEL_ID,
            "--generated-at",
            GENERATED_AT,
            "--model-response",
            str(response),
            "--output",
            str(source),
            "--attempt-output",
            str(attempt),
        ]
    ) == 2
    assert "distinct" in capsys.readouterr().err
    assert not attempt.exists()
    assert review_main(
        ["behavior-hypothesis-validate", str(source), "--source-replay"]
    ) == 2
    assert "requires --observation-artifact" in capsys.readouterr().err


def test_cli_help_preserves_p2g3_and_exposes_explicit_p2g4_audit_commands() -> None:
    parser = build_parser()
    subparsers = next(
        action for action in parser._actions if action.dest == "command"
    )
    choices = set(subparsers.choices)
    assert {
        "behavior-hypothesis-interpret",
        "behavior-hypothesis-review",
        "behavior-hypothesis-render",
        "behavior-hypothesis-diff",
        "behavior-hypothesis-revision-list",
        "behavior-hypothesis-validate",
    }.issubset(choices)
    assert not any("hypothesis-correct" in item for item in choices)


def test_artifact_contains_no_machine_path_or_binary_float(
    observation_artifact: dict[str, Any],
) -> None:
    result = build_behavior_hypothesis_set(
        observation_artifact,
        response_text=_raw(_response(observation_artifact)),
        model_id=MODEL_ID,
        generated_at=GENERATED_AT,
    )
    rendered = canonical_json_bytes(result.artifact).decode("utf-8")
    assert str(Path.cwd()) not in rendered
    assert not any(
        isinstance(value, float)
        for hypothesis in result.artifact["hypotheses"]
        for value in hypothesis.values()
    )
