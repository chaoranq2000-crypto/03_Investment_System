from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import random
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Mapping

import pytest

from src.investment_review.artifact_io import canonical_json_bytes
from src.investment_review.behavior_cohort import (
    EXCLUSION_REASON_REGISTRY,
    BehaviorCohortError,
    build_behavior_cohort,
    load_behavior_cohort,
    query_behavior_cohort,
    replay_validate_behavior_cohort,
    save_behavior_cohort,
    validate_behavior_cohort,
)
from src.investment_review.cli import main as review_main
from src.investment_review.episode_interpretation import facts_only_projection
from src.investment_review.episode_review import (
    build_facts_only_episode_review,
    save_episode_review,
)
from src.investment_review.episode_revision import apply_human_review
from src.investment_review.review_input_bundle import save_review_input_bundle


EFFECTIVE_FROM = "2026-07-01T00:00:00Z"
EFFECTIVE_TO = "2026-07-02T00:00:00Z"
KNOWLEDGE_CUTOFF = "2026-07-01T10:00:00Z"


def _load_p2f3_helpers() -> ModuleType:
    module_name = "_investment_review_p2g_fixture_helpers"
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
def context(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    chain = P2F1._fixture_chain(tmp_path_factory.mktemp("p2g"))
    bundle = P2F1._build_bundle(chain)
    facts = build_facts_only_episode_review(bundle)
    model = P2F3._build(facts).artifact
    main_id = model["interpretation_sections"]["main_tensions"][0]["finding_id"]
    request = {
        "schema_version": "p2f.human_review_request.v1",
        "action": "accept",
        "reviewed_at": "2026-07-01T09:00:00Z",
        "actor_ref": "reviewer:p2g-fixture",
        "reason": "The recorded finding was reviewed for the P2G fixture.",
        "target_ids": [main_id],
        "corrections": [],
    }
    revised = apply_human_review(model, request)
    reject_request = deepcopy(request)
    reject_request["action"] = "reject"
    reject_request["reason"] = "The interpretation was rejected; facts remain immutable."
    rejected = apply_human_review(model, reject_request)
    return {
        "chain": chain,
        "bundle": bundle,
        "facts": facts,
        "model": model,
        "revised": revised,
        "rejected": rejected,
    }


def _build(
    reviews: Iterable[Mapping[str, Any]],
    bundles: Iterable[Mapping[str, Any]],
    **overrides: Any,
) -> dict[str, Any]:
    options = {
        "effective_from": EFFECTIVE_FROM,
        "effective_to": EFFECTIVE_TO,
        "knowledge_cutoff": KNOWLEDGE_CUTOFF,
        "effective_anchor": "episode_opened_at",
    }
    options.update(overrides)
    return build_behavior_cohort(reviews, bundles, **options)


def _codes(validation: Mapping[str, Any]) -> set[str]:
    return {
        str(item.get("code"))
        for item in validation.get("findings", [])
        if isinstance(item, Mapping)
    }


def _reason_codes(artifact: Mapping[str, Any]) -> set[str]:
    return {
        str(reason)
        for item in artifact.get("excluded_candidates", [])
        if isinstance(item, Mapping)
        for reason in item.get("reason_codes", [])
    }


def _all_values(value: object) -> Iterable[object]:
    yield value
    if isinstance(value, Mapping):
        for nested in value.values():
            yield from _all_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _all_values(nested)


def _rehash(document: dict[str, Any]) -> None:
    material = deepcopy(document)
    material.pop("content_id", None)
    document["content_id"] = "sha256:" + hashlib.sha256(
        canonical_json_bytes(material)
    ).hexdigest()


def _rehash_fact(fact: dict[str, Any]) -> None:
    material = deepcopy(fact)
    material.pop("fact_id", None)
    fact["fact_id"] = "fact:" + hashlib.sha256(
        canonical_json_bytes(material)
    ).hexdigest()[:32]


def _lifecycle(review: Mapping[str, Any]) -> Mapping[str, Any]:
    return next(
        fact
        for fact in review["fact_sections"]["timeline"]["facts"]
        if fact["kind"] == "episode_lifecycle"
    )


def test_sch_01_minimal_valid_cohort_is_release_ready(
    context: dict[str, Any],
) -> None:
    artifact = _build([context["facts"]], [context["bundle"]])
    assert artifact["schema_version"] == "p2g.behavior_cohort.v1"
    assert artifact["release_readiness"] == {"status": "ready", "blocker_codes": []}
    assert artifact["source_verification"]["status"] == "verified"
    assert artifact["counts"]["included_review_count"] == 1
    assert validate_behavior_cohort(artifact)["validation_status"] == "accepted"


def test_fact_projection_is_exact_and_contains_no_interpretation(
    context: dict[str, Any],
) -> None:
    artifact = _build([context["model"]], [context["bundle"]])
    included = artifact["included_reviews"][0]
    expected = facts_only_projection(context["model"])
    assert canonical_json_bytes(included["facts_projection"]) == canonical_json_bytes(
        expected
    )
    assert all(
        values == []
        for values in included["facts_projection"]["interpretation_sections"].values()
    )
    assert included["facts_projection"]["governance"]["generation_mode"] == "facts_only"


def test_fact_states_warnings_gaps_and_counterevidence_sources_are_preserved(
    context: dict[str, Any],
) -> None:
    artifact = _build([context["facts"]], [context["bundle"]])
    projection = artifact["included_reviews"][0]["facts_projection"]
    assert canonical_json_bytes(projection["fact_sections"]) == canonical_json_bytes(
        context["facts"]["fact_sections"]
    )
    assert canonical_json_bytes(projection["warnings"]) == canonical_json_bytes(
        context["facts"]["warnings"]
    )
    assert artifact["included_reviews"][0]["source_refs"]


def test_det_01_revision_and_bundle_input_order_is_irrelevant(
    context: dict[str, Any],
) -> None:
    first = _build(
        [context["model"], context["revised"]],
        [context["bundle"], context["bundle"]],
    )
    second = _build(
        [context["revised"], context["model"]],
        [context["bundle"]],
    )
    assert canonical_json_bytes(first) == canonical_json_bytes(second)


def test_det_property_random_input_permutations_are_byte_stable(
    context: dict[str, Any],
) -> None:
    expected = _build([context["model"], context["revised"]], [context["bundle"]])
    randomizer = random.Random(20260717)
    for _ in range(12):
        reviews = [context["model"], context["revised"]]
        bundles = [context["bundle"], context["bundle"]]
        randomizer.shuffle(reviews)
        randomizer.shuffle(bundles)
        assert canonical_json_bytes(_build(reviews, bundles)) == canonical_json_bytes(
            expected
        )


def test_det_duplicate_identical_sources_do_not_change_identity(
    context: dict[str, Any],
) -> None:
    single = _build([context["facts"]], [context["bundle"]])
    duplicated = _build(
        [context["facts"], context["facts"]],
        [context["bundle"], context["bundle"]],
    )
    assert duplicated["content_id"] == single["content_id"]
    assert canonical_json_bytes(duplicated) == canonical_json_bytes(single)


def test_det_conflicting_claimed_content_id_is_order_independent(
    context: dict[str, Any],
) -> None:
    tampered = deepcopy(context["facts"])
    tampered["content_id"] = "sha256:" + "0" * 64
    first = _build([context["facts"], tampered], [context["bundle"]])
    second = _build([tampered, context["facts"]], [context["bundle"]])
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert "content_id_mismatch" in _reason_codes(first)


def test_det_environment_tz_and_hash_seed_do_not_enter_artifact(
    context: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _build([context["facts"]], [context["bundle"]])
    monkeypatch.setenv("TZ", "Pacific/Honolulu")
    monkeypatch.setenv("PYTHONHASHSEED", "731")
    second = _build([context["facts"]], [context["bundle"]])
    assert canonical_json_bytes(first) == canonical_json_bytes(second)


def test_det_no_absolute_source_path_enters_artifact(context: dict[str, Any]) -> None:
    artifact = _build([context["facts"]], [context["bundle"]])
    forbidden = {
        str(context["chain"].portfolio_db.parent),
        str(context["chain"].portfolio_db),
    }
    strings = {value for value in _all_values(artifact) if isinstance(value, str)}
    assert not any(path in value for path in forbidden for value in strings)


def test_det_06_two_valid_revision_one_roots_are_ambiguous(
    context: dict[str, Any],
) -> None:
    artifact = _build([context["facts"], context["model"]], [context["bundle"]])
    assert artifact["release_readiness"]["status"] == "blocked"
    assert "ambiguous_current_revision" in _reason_codes(artifact)


def test_tim_01_effective_from_is_inclusive(context: dict[str, Any]) -> None:
    opened_at = _lifecycle(context["facts"])["data"]["opened_at"]
    artifact = _build(
        [context["facts"]],
        [context["bundle"]],
        effective_from=opened_at,
    )
    assert artifact["counts"]["included_review_count"] == 1


def test_tim_02_effective_to_is_exclusive(context: dict[str, Any]) -> None:
    opened_at = _lifecycle(context["facts"])["data"]["opened_at"]
    artifact = _build(
        [context["facts"]],
        [context["bundle"]],
        effective_to=opened_at,
    )
    assert artifact["counts"]["included_review_count"] == 0
    assert "outside_effective_window" in _reason_codes(artifact)
    assert artifact["release_readiness"]["status"] == "ready"


def test_tim_03_knowledge_equal_to_cutoff_is_included(
    context: dict[str, Any],
) -> None:
    artifact = _build(
        [context["model"]],
        [context["bundle"]],
        knowledge_cutoff="2026-07-01T08:00:00Z",
    )
    assert artifact["counts"]["included_review_count"] == 1


def test_tim_04_all_revisions_after_cutoff_are_excluded_with_reason(
    context: dict[str, Any],
) -> None:
    artifact = _build(
        [context["model"]],
        [context["bundle"]],
        knowledge_cutoff="2026-07-01T07:59:59Z",
    )
    assert artifact["counts"]["included_review_count"] == 0
    assert "knowledge_after_cutoff" in _reason_codes(artifact)
    assert artifact["release_readiness"]["status"] == "ready"


def test_tim_05_future_correction_cannot_change_earlier_cohort(
    context: dict[str, Any],
) -> None:
    before = _build(
        [context["model"]],
        [context["bundle"]],
        knowledge_cutoff="2026-07-01T08:30:00Z",
    )
    after = _build(
        [context["revised"], context["model"]],
        [context["bundle"]],
        knowledge_cutoff="2026-07-01T08:30:00Z",
    )
    assert canonical_json_bytes(before) == canonical_json_bytes(after)


def test_tim_07_missing_closed_anchor_is_explicit_for_open_episode(
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
    review = build_facts_only_episode_review(bundle)
    artifact = _build(
        [review],
        [bundle],
        effective_anchor="episode_closed_at",
    )
    assert "missing_effective_anchor" in _reason_codes(artifact)
    assert artifact["release_readiness"]["status"] == "ready"


def test_rev_03_ambiguous_leaf_is_fail_closed(context: dict[str, Any]) -> None:
    artifact = _build([context["facts"], context["model"]], [context["bundle"]])
    assert artifact["source_verification"]["status"] == "blocked"
    assert artifact["counts"]["blocking_exclusion_count"] == 1


def test_rev_04_missing_predecessor_is_fail_closed(context: dict[str, Any]) -> None:
    artifact = _build([context["revised"]], [context["bundle"]])
    assert "revision_chain_invalid" in _reason_codes(artifact)
    assert artifact["release_readiness"]["status"] == "blocked"


def test_rev_06_rejected_interpretation_does_not_reject_immutable_facts(
    context: dict[str, Any],
) -> None:
    artifact = _build(
        [context["model"], context["rejected"]], [context["bundle"]]
    )
    assert artifact["release_readiness"]["status"] == "ready"
    assert artifact["included_reviews"][0]["revision_no"] == 2
    assert all(
        section == []
        for section in artifact["included_reviews"][0]["facts_projection"][
            "interpretation_sections"
        ].values()
    )


def test_src_01_exact_source_replay_is_verified(context: dict[str, Any]) -> None:
    artifact = _build(
        [context["model"], context["revised"]], [context["bundle"]]
    )
    replay = replay_validate_behavior_cohort(
        artifact,
        episode_reviews=[context["revised"], context["model"]],
        input_bundles=[context["bundle"]],
    )
    assert replay["validation_status"] == "accepted"
    assert replay["source_verification"]["status"] == "verified"


def test_src_02_fact_tamper_is_replay_mismatch(context: dict[str, Any]) -> None:
    tampered = deepcopy(context["facts"])
    fact = tampered["fact_sections"]["timeline"]["facts"][0]
    fact["warning_codes"] = sorted(set(fact["warning_codes"]) | {"P2G_TAMPER"})
    _rehash_fact(fact)
    _rehash(tampered)
    artifact = _build([tampered], [context["bundle"]])
    assert "source_replay_mismatch" in _reason_codes(artifact)
    assert artifact["release_readiness"]["status"] == "blocked"


def test_src_03_content_id_tamper_is_blocked(context: dict[str, Any]) -> None:
    tampered = deepcopy(context["facts"])
    tampered["content_id"] = "sha256:" + "0" * 64
    artifact = _build([tampered], [context["bundle"]])
    assert "content_id_mismatch" in _reason_codes(artifact)


def test_src_04_missing_input_bundle_is_fail_closed(context: dict[str, Any]) -> None:
    artifact = _build([context["facts"]], [])
    assert "missing_source" in _reason_codes(artifact)
    assert artifact["release_readiness"]["status"] == "blocked"


def test_src_05_unreferenced_extra_bundle_is_fail_closed(
    context: dict[str, Any],
) -> None:
    extra = deepcopy(context["bundle"])
    extra["build_request"]["episode_id"] = "EXTRA-EPISODE"
    _rehash(extra)
    artifact = _build([context["facts"]], [context["bundle"], extra])
    assert "extra_source" in _reason_codes(artifact)
    assert artifact["release_readiness"]["status"] == "blocked"


def test_src_06_nonverified_bundle_is_not_ready(context: dict[str, Any]) -> None:
    tampered = deepcopy(context["bundle"])
    tampered["source_verification"]["status"] = "missing"
    tampered["release_readiness"]["status"] = "blocked"
    tampered["release_readiness"]["blocker_codes"] = ["SOURCE_NOT_VERIFIED"]
    tampered["release_readiness"]["reasons"] = ["Fixture source is not verified."]
    _rehash(tampered)
    review = deepcopy(context["facts"])
    review["input_bundle_ref"]["content_id"] = tampered["content_id"]
    _rehash(review)
    artifact = _build([review], [tampered])
    assert {"release_not_ready", "source_not_verified"} <= _reason_codes(artifact)


def test_fact_02_missing_required_section_is_blocked(context: dict[str, Any]) -> None:
    tampered = deepcopy(context["facts"])
    tampered["fact_sections"].pop("market_context")
    _rehash(tampered)
    artifact = _build([tampered], [context["bundle"]])
    assert "missing_required_fact_section" in _reason_codes(artifact)


def test_filters_are_normalized_and_mismatch_is_nonblocking(
    context: dict[str, Any],
) -> None:
    matching = _build(
        [context["facts"]],
        [context["bundle"]],
        filters={"instrument_ids": ["600000.sh", "600000.SH"]},
    )
    assert matching["selection_spec"]["filters"]["instrument_ids"] == ["600000.SH"]
    assert matching["counts"]["included_review_count"] == 1
    missing = _build(
        [context["facts"]],
        [context["bundle"]],
        filters={"account_ids": ["not-the-fixture-account"]},
    )
    assert "filter_mismatch" in _reason_codes(missing)
    assert missing["release_readiness"]["status"] == "ready"


def test_cli_01_build_show_validate_and_replay(
    context: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    review_path = tmp_path / "review.json"
    bundle_path = tmp_path / "bundle.json"
    output = tmp_path / "cohort.json"
    save_episode_review(review_path, context["facts"])
    save_review_input_bundle(bundle_path, context["bundle"])
    assert (
        review_main(
            [
                "behavior-cohort-build",
                "--episode-review",
                str(review_path),
                "--input-bundle",
                str(bundle_path),
                "--effective-from",
                EFFECTIVE_FROM,
                "--effective-to",
                EFFECTIVE_TO,
                "--knowledge-cutoff",
                KNOWLEDGE_CUTOFF,
                "--effective-anchor",
                "episode_opened_at",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)
    assert summary["release_readiness"] == "ready"
    assert review_main(["behavior-cohort-show", str(output)]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown[0]["content_id"] == summary["content_id"]
    assert review_main(["behavior-cohort-validate", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["validation_status"] == "accepted"
    assert (
        review_main(
            [
                "behavior-cohort-validate",
                str(output),
                "--source-replay",
                "--episode-review",
                str(review_path),
                "--input-bundle",
                str(bundle_path),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["source_verification"]["status"] == "verified"


def test_cli_02_create_only_output_refuses_overwrite(
    context: dict[str, Any], tmp_path: Path
) -> None:
    artifact = _build([context["facts"]], [context["bundle"]])
    output = tmp_path / "cohort.json"
    save_behavior_cohort(output, artifact)
    before = output.read_bytes()
    with pytest.raises(BehaviorCohortError):
        save_behavior_cohort(output, artifact)
    assert output.read_bytes() == before


def test_cli_03_blocked_build_writes_artifact_but_returns_nonzero(
    context: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    review_path = tmp_path / "review.json"
    wrong_bundle_path = tmp_path / "wrong-bundle.json"
    output = tmp_path / "blocked-cohort.json"
    save_episode_review(review_path, context["facts"])
    wrong = deepcopy(context["bundle"])
    wrong["build_request"]["episode_id"] = "UNREFERENCED"
    _rehash(wrong)
    wrong_bundle_path.write_text(json.dumps(wrong), encoding="utf-8")
    code = review_main(
        [
            "behavior-cohort-build",
            "--episode-review",
            str(review_path),
            "--input-bundle",
            str(wrong_bundle_path),
            "--effective-from",
            EFFECTIVE_FROM,
            "--effective-to",
            EFFECTIVE_TO,
            "--knowledge-cutoff",
            KNOWLEDGE_CUTOFF,
            "--effective-anchor",
            "episode_opened_at",
            "--output",
            str(output),
        ]
    )
    assert code == 2
    assert output.exists()
    assert load_behavior_cohort(output)["release_readiness"]["status"] == "blocked"
    capsys.readouterr()


def test_cli_04_source_replay_requires_explicit_sources(
    context: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "cohort.json"
    save_behavior_cohort(output, _build([context["facts"]], [context["bundle"]]))
    assert review_main(["behavior-cohort-validate", str(output), "--source-replay"]) == 2
    error = json.loads(capsys.readouterr().err)
    assert "requires --episode-review and --input-bundle" in error["error"]


def test_cli_06_query_is_read_only(context: dict[str, Any]) -> None:
    artifact = _build([context["facts"]], [context["bundle"]])
    before = canonical_json_bytes(artifact)
    episode_id = artifact["included_reviews"][0]["episode_id"]
    assert query_behavior_cohort(artifact, episode_id=episode_id)
    assert canonical_json_bytes(artifact) == before


def test_query_reason_and_content_filters(context: dict[str, Any]) -> None:
    artifact = _build(
        [context["facts"]],
        [context["bundle"]],
        filters={"account_ids": ["missing"]},
    )
    assert query_behavior_cohort(artifact, reason_code="filter_mismatch")
    assert query_behavior_cohort(artifact, content_id="sha256:" + "0" * 64) == []
    with pytest.raises(BehaviorCohortError):
        query_behavior_cohort(artifact, reason_code="unknown_reason")


def test_sch_02_missing_cutoff_is_schema_invalid(context: dict[str, Any]) -> None:
    artifact = _build([context["facts"]], [context["bundle"]])
    tampered = deepcopy(artifact)
    tampered["selection_spec"].pop("knowledge_cutoff")
    _rehash(tampered)
    validation = validate_behavior_cohort(tampered)
    assert validation["validation_status"] == "blocked"
    assert "SCHEMA_VIOLATION" in _codes(validation)


def test_sch_03_unknown_reason_code_is_rejected(context: dict[str, Any]) -> None:
    artifact = _build(
        [context["facts"]],
        [context["bundle"]],
        filters={"account_ids": ["missing"]},
    )
    tampered = deepcopy(artifact)
    tampered["excluded_candidates"][0]["reason_codes"] = ["unknown_reason"]
    _rehash(tampered)
    assert validate_behavior_cohort(tampered)["validation_status"] == "blocked"


def test_sch_04_counts_mismatch_is_blocked(context: dict[str, Any]) -> None:
    artifact = _build([context["facts"]], [context["bundle"]])
    tampered = deepcopy(artifact)
    tampered["counts"]["fact_count"] += 1
    _rehash(tampered)
    validation = validate_behavior_cohort(tampered)
    assert "COUNTS_MISMATCH" in _codes(validation)
    candidate_tamper = deepcopy(artifact)
    candidate_tamper["counts"]["candidate_chain_count"] += 1
    _rehash(candidate_tamper)
    assert "COUNTS_MISMATCH" in _codes(
        validate_behavior_cohort(candidate_tamper)
    )


def test_artifact_hash_inventory_and_source_ref_tamper_are_blocked(
    context: dict[str, Any],
) -> None:
    artifact = _build([context["facts"]], [context["bundle"]])
    hash_tamper = deepcopy(artifact)
    hash_tamper["cohort_id"] = "cohort:" + "0" * 32
    assert validate_behavior_cohort(hash_tamper)["validation_status"] == "blocked"

    inventory_tamper = deepcopy(artifact)
    inventory_tamper["source_inventory"].pop()
    _rehash(inventory_tamper)
    assert "SOURCE_INVENTORY_MISMATCH" in _codes(
        validate_behavior_cohort(inventory_tamper)
    )

    ref_tamper = deepcopy(artifact)
    refs = ref_tamper["included_reviews"][0]["source_refs"]
    refs.reverse()
    _rehash(ref_tamper)
    assert "SOURCE_REFS_MISMATCH" in _codes(validate_behavior_cohort(ref_tamper))


@pytest.mark.parametrize("payload", [None, {}, [], "invalid"])
def test_validator_is_total_for_malformed_inputs(payload: object) -> None:
    validation = validate_behavior_cohort(payload)  # type: ignore[arg-type]
    assert validation["validation_status"] == "blocked"


def test_invalid_window_and_naive_time_are_rejected(context: dict[str, Any]) -> None:
    with pytest.raises(BehaviorCohortError):
        _build(
            [context["facts"]],
            [context["bundle"]],
            effective_from=EFFECTIVE_TO,
            effective_to=EFFECTIVE_FROM,
        )
    with pytest.raises(BehaviorCohortError):
        _build(
            [context["facts"]],
            [context["bundle"]],
            knowledge_cutoff="2026-07-01 10:00:00",
        )


def test_registry_blocking_semantics_are_closed() -> None:
    assert EXCLUSION_REASON_REGISTRY["outside_effective_window"] is False
    assert EXCLUSION_REASON_REGISTRY["knowledge_after_cutoff"] is False
    assert EXCLUSION_REASON_REGISTRY["ambiguous_current_revision"] is True
    assert EXCLUSION_REASON_REGISTRY["source_replay_mismatch"] is True
    assert EXCLUSION_REASON_REGISTRY["human_rejected"] is False
    assert set(EXCLUSION_REASON_REGISTRY) == {
        "outside_effective_window",
        "knowledge_after_cutoff",
        "missing_effective_anchor",
        "missing_knowledge_time",
        "schema_invalid",
        "release_not_ready",
        "source_not_verified",
        "source_replay_mismatch",
        "revision_chain_invalid",
        "ambiguous_current_revision",
        "human_rejected",
        "missing_required_fact_section",
        "duplicate_logical_episode",
        "content_id_mismatch",
        "filter_mismatch",
        "missing_source",
        "extra_source",
        "interpretation_contamination",
    }


def test_no_model_network_database_or_runtime_path_dependency_in_builder(
    context: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    before_db = Path(context["chain"].portfolio_db).read_bytes()
    artifact = _build([context["facts"]], [context["bundle"]])
    assert artifact["release_readiness"]["status"] == "ready"
    assert Path(context["chain"].portfolio_db).read_bytes() == before_db
    assert not any(
        key in {"recommendation", "advice", "score", "psychology_label"}
        for value in artifact["included_reviews"]
        for item in _all_values(value)
        if isinstance(item, Mapping)
        for key in item
    )


def test_module_has_no_hidden_environment_output(context: dict[str, Any]) -> None:
    artifact = _build([context["facts"]], [context["bundle"]])
    rendered = canonical_json_bytes(artifact).decode("utf-8")
    assert os.getcwd() not in rendered
    assert "created_at" not in artifact
    assert "latest.json" not in rendered
