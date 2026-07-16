from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping

import pytest

from src.investment_review.artifact_io import canonical_json_bytes
from src.investment_review.cli import main as review_main
from src.investment_review.episode_interpretation import (
    RecordedResponseProvider,
    UnavailableInterpretationProvider,
    build_interpretation_prompt,
    build_model_assisted_episode_review,
    facts_only_projection,
    replay_validate_interpretation_attempt,
    validate_interpretation_attempt,
)
from src.investment_review.episode_review import (
    build_facts_only_episode_review,
    load_episode_review,
    replay_validate_episode_review,
    save_episode_review,
    validate_episode_review,
)


ATTEMPTED_AT = "2026-07-01T08:00:00Z"


def _load_p2f1_fixture_helpers() -> ModuleType:
    module_name = "_investment_review_p2f1_interpretation_fixture_helpers"
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


@pytest.fixture(scope="module")
def context(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    chain = P2F1._fixture_chain(tmp_path_factory.mktemp("p2f3"))
    bundle = P2F1._build_bundle(chain)
    facts = build_facts_only_episode_review(bundle)
    return {"chain": chain, "bundle": bundle, "facts": facts}


def _all_facts(artifact: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(fact)
        for section in artifact["fact_sections"].values()
        for fact in section["facts"]
    ]


def _fact(artifact: Mapping[str, Any], *, kind: str) -> dict[str, Any]:
    return next(fact for fact in _all_facts(artifact) if fact["kind"] == kind)


def _response_payload(facts: Mapping[str, Any]) -> dict[str, Any]:
    decision_id = _fact(facts, kind="recorded_decision")["fact_id"]
    event_id = next(
        fact["fact_id"]
        for fact in _all_facts(facts)
        if fact["kind"] == "execution_event" and fact["data"]["side"] == "SELL"
    )
    return {
        "schema_version": "p2f.interpretation_output.v1",
        "interpretation_sections": {
            "main_tensions": [
                {
                    "kind": "main_tension",
                    "perspective": "retrospective",
                    "statement": (
                        "The recorded decision fields and observed execution may "
                        "reflect different time horizons."
                    ),
                    "confidence": "medium",
                    "fact_refs": [event_id, decision_id],
                    "counterevidence_status": "missing",
                    "counterevidence_fact_refs": [],
                    "assumptions": [
                        "The recorded decision fields remained applicable until execution."
                    ],
                    "uncertainty": (
                        "Counterevidence is missing because no linked invalidation "
                        "record was supplied."
                    ),
                }
            ],
            "hypotheses": [],
            "alternative_explanations": [
                {
                    "kind": "alternative_explanation",
                    "perspective": "retrospective",
                    "statement": (
                        "A portfolio constraint or information change not represented "
                        "by linked facts could also explain the timing."
                    ),
                    "confidence": "low",
                    "fact_refs": [event_id],
                    "counterevidence_status": "missing",
                    "counterevidence_fact_refs": [],
                    "assumptions": [
                        "Relevant context may exist outside the frozen source set."
                    ],
                    "uncertainty": (
                        "No direct source records whether an unlinked context change occurred."
                    ),
                }
            ],
            "counterfactual_options": [
                {
                    "description": (
                        "At the recorded closing event, compare a partial reduction "
                        "with the observed full close as a retrospective option."
                    ),
                    "fact_refs": [event_id],
                    "temporal_scope": "episode_time",
                    "feasibility": "possibly_feasible",
                    "tradeoffs": [
                        "It would retain some exposure while leaving some concentration."
                    ],
                    "not_advice": True,
                }
            ],
            "history_links": [],
        },
    }


def _raw_response(facts: Mapping[str, Any], payload: Mapping[str, Any] | None = None) -> str:
    return json.dumps(
        payload if payload is not None else _response_payload(facts),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _build(
    facts: Mapping[str, Any],
    payload: Mapping[str, Any] | None = None,
    *,
    model_id: str = "recorded-model-v1",
    parameters: Mapping[str, Any] | None = None,
):
    return build_model_assisted_episode_review(
        facts,
        provider=RecordedResponseProvider(model_id, _raw_response(facts, payload)),
        attempted_at=ATTEMPTED_AT,
        parameters=parameters or {"temperature": "0"},
    )


def _finding_codes(validation: Mapping[str, Any]) -> set[str]:
    return {
        str(item.get("code"))
        for item in validation.get("findings", [])
        if isinstance(item, Mapping)
    }


def _rehash(artifact: dict[str, Any]) -> None:
    material = deepcopy(artifact)
    material.pop("content_id", None)
    artifact["content_id"] = "sha256:" + hashlib.sha256(
        canonical_json_bytes(material)
    ).hexdigest()


def test_f3_01_f3_06_success_has_grounded_bounded_sections(
    context: dict[str, Any],
) -> None:
    result = _build(context["facts"])
    assert result.used_fallback is False
    assert result.attempt["status"] == "succeeded"
    assert validate_interpretation_attempt(result.attempt)["validation_status"] == "accepted"
    assert validate_episode_review(result.artifact)["validation_status"] == "accepted"
    governance = result.artifact["governance"]
    assert governance["generation_mode"] == "model_assisted"
    assert governance["model_generation"]["input_content_id"] == context["facts"][
        "content_id"
    ]
    tension = result.artifact["interpretation_sections"]["main_tensions"][0]
    assert tension["finding_id"].startswith("finding:")
    assert tension["fact_refs"]
    assert tension["assumptions"]
    assert tension["uncertainty"]
    assert result.artifact["interpretation_sections"]["alternative_explanations"]


def test_f3_01_missing_fact_ref_falls_back(context: dict[str, Any]) -> None:
    payload = _response_payload(context["facts"])
    payload["interpretation_sections"]["main_tensions"][0]["fact_refs"] = []
    result = _build(context["facts"], payload)
    assert result.used_fallback is True
    assert result.artifact == context["facts"]
    assert "MODEL_OUTPUT_SCHEMA_INVALID" in result.attempt["failure_codes"]


def test_f3_02_unknown_fact_ref_falls_back(context: dict[str, Any]) -> None:
    payload = _response_payload(context["facts"])
    payload["interpretation_sections"]["main_tensions"][0]["fact_refs"] = [
        "fact:" + "f" * 32
    ]
    result = _build(context["facts"], payload)
    assert result.used_fallback is True
    assert "INTERPRETATION_FACT_REF_UNKNOWN" in result.attempt["failure_codes"]


@pytest.mark.parametrize(
    ("statement", "expected_code"),
    [
        ("The exit proves fear and loss aversion.", "POLICY_PSYCHOLOGY_DIAGNOSIS"),
        ("The execution was undisciplined.", "POLICY_PSYCHOLOGY_DIAGNOSIS"),
        ("现在应该买入并继续持有。", "POLICY_DIRECT_ADVICE"),
        ("Buy the security now.", "POLICY_DIRECT_ADVICE"),
        ("Set the position size to 20%.", "POLICY_DIRECT_ADVICE"),
        ("The mechanical score is 85/100.", "POLICY_MECHANICAL_SCORE"),
        ("The profit proves this was a correct decision.", "POLICY_OUTCOME_QUALITY"),
    ],
)
def test_f3_03_f3_04_f3_05_policy_gate_rejects_unsafe_text(
    context: dict[str, Any], statement: str, expected_code: str
) -> None:
    payload = _response_payload(context["facts"])
    payload["interpretation_sections"]["main_tensions"][0]["statement"] = statement
    result = _build(context["facts"], payload)
    assert result.used_fallback is True
    assert expected_code in result.attempt["failure_codes"]


def test_f3_07_tension_without_alternative_is_not_releasable(
    context: dict[str, Any],
) -> None:
    payload = _response_payload(context["facts"])
    payload["interpretation_sections"]["alternative_explanations"] = []
    result = _build(context["facts"], payload)
    assert result.used_fallback is True
    assert "ALTERNATIVE_EXPLANATION_REQUIRED" in result.attempt["failure_codes"]


def test_f3_08_available_counterevidence_requires_fact_refs(
    context: dict[str, Any],
) -> None:
    payload = _response_payload(context["facts"])
    tension = payload["interpretation_sections"]["main_tensions"][0]
    tension["counterevidence_status"] = "available"
    tension["counterevidence_fact_refs"] = []
    result = _build(context["facts"], payload)
    assert result.used_fallback is True
    assert "COUNTEREVIDENCE_REF_REQUIRED" in result.attempt["failure_codes"]


def test_high_confidence_explains_missing_counterevidence(
    context: dict[str, Any],
) -> None:
    payload = _response_payload(context["facts"])
    tension = payload["interpretation_sections"]["main_tensions"][0]
    tension["confidence"] = "high"
    tension["uncertainty"] = "The interpretation remains uncertain."
    result = _build(context["facts"], payload)
    assert result.used_fallback is True
    assert (
        "COUNTEREVIDENCE_MISSING_EXPLANATION_REQUIRED"
        in result.attempt["failure_codes"]
    )


def test_f3_09_provider_unavailable_preserves_exact_facts(
    context: dict[str, Any],
) -> None:
    facts = context["facts"]
    before = canonical_json_bytes(facts)
    result = build_model_assisted_episode_review(
        facts,
        provider=UnavailableInterpretationProvider("offline-model"),
        attempted_at=ATTEMPTED_AT,
        parameters={"temperature": "0"},
    )
    assert result.used_fallback is True
    assert canonical_json_bytes(result.artifact) == before
    assert result.attempt["error_code"] == "MODEL_PROVIDER_UNAVAILABLE"
    assert result.attempt["provenance"]["output_hash"] is None
    assert validate_interpretation_attempt(result.attempt)["validation_status"] == "accepted"


def test_f3_10_invalid_json_preserves_exact_facts(context: dict[str, Any]) -> None:
    facts = context["facts"]
    result = build_model_assisted_episode_review(
        facts,
        provider=RecordedResponseProvider("recorded-model", "{not-json"),
        attempted_at=ATTEMPTED_AT,
    )
    assert result.used_fallback is True
    assert canonical_json_bytes(result.artifact) == canonical_json_bytes(facts)
    assert "MODEL_OUTPUT_INVALID_JSON" in result.attempt["failure_codes"]


def test_f3_11_model_and_parameters_change_provenance_and_content(
    context: dict[str, Any],
) -> None:
    first = _build(
        context["facts"], model_id="model-a", parameters={"temperature": "0"}
    )
    second = _build(
        context["facts"], model_id="model-b", parameters={"temperature": "0.1"}
    )
    first_meta = first.artifact["governance"]["model_generation"]
    second_meta = second.artifact["governance"]["model_generation"]
    assert first_meta["prompt_hash"] == second_meta["prompt_hash"]
    assert first_meta["output_hash"] == second_meta["output_hash"]
    assert first_meta["model_id"] != second_meta["model_id"]
    assert first.artifact["content_id"] != second.artifact["content_id"]


def test_f3_12_same_raw_response_is_reproducible(context: dict[str, Any]) -> None:
    first = _build(context["facts"])
    second = _build(context["facts"])
    assert first.artifact == second.artifact
    assert first.attempt == second.attempt
    raw = _raw_response(context["facts"])
    replay = replay_validate_interpretation_attempt(first.attempt, raw_output=raw)
    assert replay["validation_status"] == "accepted"
    assert replay["output_verification"]["status"] == "verified"


def test_f3_13_outcome_cannot_enter_decision_time_interpretation(
    context: dict[str, Any],
) -> None:
    payload = _response_payload(context["facts"])
    outcome_id = _fact(context["facts"], kind="outcome_record")["fact_id"]
    tension = payload["interpretation_sections"]["main_tensions"][0]
    tension["perspective"] = "decision_time"
    tension["fact_refs"] = [outcome_id]
    result = _build(context["facts"], payload)
    assert result.used_fallback is True
    assert "INTERPRETATION_TEMPORAL_LEAKAGE" in result.attempt["failure_codes"]


def test_f3_14_counterfactual_cannot_use_post_episode_outcome(
    context: dict[str, Any],
) -> None:
    payload = _response_payload(context["facts"])
    outcome_id = _fact(context["facts"], kind="outcome_record")["fact_id"]
    option = payload["interpretation_sections"]["counterfactual_options"][0]
    option["fact_refs"] = [outcome_id]
    result = _build(context["facts"], payload)
    assert result.used_fallback is True
    assert "COUNTERFACTUAL_TEMPORAL_LEAKAGE" in result.attempt["failure_codes"]


def test_f3_14_hindsight_best_price_is_rejected(context: dict[str, Any]) -> None:
    payload = _response_payload(context["facts"])
    payload["interpretation_sections"]["counterfactual_options"][0][
        "description"
    ] = "Sell at the highest price later observed."
    result = _build(context["facts"], payload)
    assert result.used_fallback is True
    assert "POLICY_HINDSIGHT_PRICE" in result.attempt["failure_codes"]


def test_prompt_uses_facts_not_raw_decision_payload(context: dict[str, Any]) -> None:
    chain = context["chain"]
    decision = deepcopy(chain.decisions[0])
    secret = "RAW_PRIVATE_DECISION_TEXT_MUST_NOT_ENTER_PROMPT"
    decision["payload"] = {
        "source_id": decision["source_id"],
        "statement": secret,
    }
    decision["content_id"] = P2F1._value_content_id(decision["payload"])
    bundle = P2F1._build_bundle(chain, decisions=[decision])
    facts = build_facts_only_episode_review(bundle)
    prompt = build_interpretation_prompt(facts)
    assert secret not in prompt
    assert facts["content_id"] in prompt
    assert all(fact["fact_id"] in prompt for fact in _all_facts(facts))


def test_success_does_not_mutate_fact_sections_or_source_binding(
    context: dict[str, Any],
) -> None:
    facts = context["facts"]
    result = _build(facts)
    assert result.artifact["fact_sections"] == facts["fact_sections"]
    assert result.artifact["input_bundle_ref"] == facts["input_bundle_ref"]
    assert result.artifact["warnings"] == facts["warnings"]
    assert facts_only_projection(result.artifact) == facts


def test_model_assisted_source_replay_verifies_only_immutable_facts(
    context: dict[str, Any],
) -> None:
    result = _build(context["facts"])
    replay = replay_validate_episode_review(
        result.artifact, input_bundle=context["bundle"]
    )
    assert replay["validation_status"] == "accepted"
    assert replay["source_verification"]["status"] == "verified"
    assert replay["source_verification"]["generation_mode"] == "model_assisted"
    assert replay["source_verification"]["interpretation_replay"] == "not_replayed"


def test_forged_interpretation_content_id_is_rejected(context: dict[str, Any]) -> None:
    result = _build(context["facts"])
    mutated = deepcopy(result.artifact)
    mutated["governance"]["model_generation"]["interpretation_content_id"] = (
        "sha256:" + "0" * 64
    )
    _rehash(mutated)
    validation = validate_episode_review(mutated)
    assert validation["validation_status"] == "blocked"
    assert "INTERPRETATION_CONTENT_ID_MISMATCH" in _finding_codes(validation)


def test_history_links_are_rejected_without_typed_history_input(
    context: dict[str, Any],
) -> None:
    payload = _response_payload(context["facts"])
    payload["interpretation_sections"]["history_links"] = [
        {"link_id": "untyped-history"}
    ]
    result = _build(context["facts"], payload)
    assert result.used_fallback is True
    assert "MODEL_OUTPUT_SCHEMA_INVALID" in result.attempt["failure_codes"]


def test_human_authored_mode_is_not_enabled_before_p2f4(
    context: dict[str, Any],
) -> None:
    result = _build(context["facts"])
    mutated = deepcopy(result.artifact)
    mutated["governance"]["generation_mode"] = "human_authored"
    mutated["governance"]["model_generation"] = None
    _rehash(mutated)
    validation = validate_episode_review(mutated)
    assert validation["validation_status"] == "blocked"
    assert "GENERATION_MODE_NOT_ENABLED" in _finding_codes(validation)


def test_attempt_replay_rejects_different_raw_text(context: dict[str, Any]) -> None:
    result = _build(context["facts"])
    replay = replay_validate_interpretation_attempt(
        result.attempt, raw_output=_raw_response(context["facts"]) + " "
    )
    assert replay["validation_status"] == "blocked"
    assert "MODEL_OUTPUT_HASH_MISMATCH" in _finding_codes(replay)


@pytest.mark.parametrize("payload", [None, [], "invalid", 1])
def test_attempt_validator_is_total_for_arbitrary_json(payload: object) -> None:
    validation = validate_interpretation_attempt(payload)  # type: ignore[arg-type]
    assert validation["validation_status"] == "blocked"


def test_attempt_validator_rejects_binary_float_without_raising(
    context: dict[str, Any],
) -> None:
    result = _build(context["facts"])
    mutated = deepcopy(result.attempt)
    mutated["provenance"]["parameters"] = {"temperature": 0.1}
    validation = validate_interpretation_attempt(mutated)
    assert validation["validation_status"] == "blocked"
    assert "ATTEMPT_PROVENANCE_INVALID" in _finding_codes(validation)


def test_cli_model_assisted_and_fallback_are_explicit(
    context: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    facts_path = tmp_path / "facts.json"
    response_path = tmp_path / "response.json"
    model_path = tmp_path / "model-review.json"
    success_attempt_path = tmp_path / "model-attempt.json"
    save_episode_review(facts_path, context["facts"])
    response_path.write_text(_raw_response(context["facts"]), encoding="utf-8")

    assert review_main(
        [
            "episode-review-interpret",
            "--artifact",
            str(facts_path),
            "--model-id",
            "recorded-model-v1",
            "--generated-at",
            ATTEMPTED_AT,
            "--model-response",
            str(response_path),
            "--parameters-json",
            '{"temperature":"0"}',
            "--output",
            str(model_path),
            "--attempt-output",
            str(success_attempt_path),
        ]
    ) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "succeeded"
    assert load_episode_review(model_path)["governance"]["generation_mode"] == (
        "model_assisted"
    )

    fallback_path = tmp_path / "fallback.json"
    fallback_attempt_path = tmp_path / "fallback-attempt.json"
    assert review_main(
        [
            "episode-review-interpret",
            "--artifact",
            str(facts_path),
            "--model-id",
            "unavailable-model",
            "--generated-at",
            ATTEMPTED_AT,
            "--simulate-unavailable",
            "--output",
            str(fallback_path),
            "--attempt-output",
            str(fallback_attempt_path),
        ]
    ) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "fallback_facts_only"
    assert load_episode_review(fallback_path) == context["facts"]
