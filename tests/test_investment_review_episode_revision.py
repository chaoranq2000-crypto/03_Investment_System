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
from src.investment_review.episode_interpretation import finding_content_id
from src.investment_review.episode_review import (
    build_facts_only_episode_review,
    render_episode_review_markdown,
    replay_validate_episode_review,
    save_episode_review,
    validate_episode_review,
)
from src.investment_review.episode_revision import (
    EpisodeRevisionError,
    apply_human_review,
    diff_episode_reviews,
    list_episode_review_revisions,
    query_episode_review_revision,
    save_new_episode_review,
    validate_human_review_request,
    validate_revision_chain,
)


def _load_p2f3_helpers() -> ModuleType:
    module_name = "_investment_review_p2f3_revision_fixture_helpers"
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


@pytest.fixture(scope="module")
def context(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    chain = P2F3.P2F1._fixture_chain(tmp_path_factory.mktemp("p2f4"))
    bundle = P2F3.P2F1._build_bundle(chain)
    facts = build_facts_only_episode_review(bundle)
    model = P2F3._build(facts).artifact
    assert validate_episode_review(model)["validation_status"] == "accepted"
    return {"chain": chain, "bundle": bundle, "facts": facts, "model": model}


def _request(
    action: str,
    target_ids: list[str],
    *,
    reviewed_at: str = "2026-07-01T09:00:00Z",
    actor_ref: str = "reviewer:fixture",
    reason: str = "Evidence links checked by the fixture reviewer.",
    corrections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "p2f.human_review_request.v1",
        "action": action,
        "reviewed_at": reviewed_at,
        "actor_ref": actor_ref,
        "reason": reason,
        "target_ids": target_ids,
        "corrections": corrections or [],
    }


def _index(artifact: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    sections = artifact["interpretation_sections"]
    for section_name in (
        "main_tensions",
        "hypotheses",
        "alternative_explanations",
    ):
        result.update({item["finding_id"]: item for item in sections[section_name]})
    result.update(
        {item["option_id"]: item for item in sections["counterfactual_options"]}
    )
    return result


def _all_facts(artifact: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        fact
        for section in artifact["fact_sections"].values()
        for fact in section["facts"]
    ]


def _main_id(artifact: Mapping[str, Any]) -> str:
    return artifact["interpretation_sections"]["main_tensions"][0]["finding_id"]


def _alternative_id(artifact: Mapping[str, Any]) -> str:
    return artifact["interpretation_sections"]["alternative_explanations"][0][
        "finding_id"
    ]


def _option_id(artifact: Mapping[str, Any]) -> str:
    return artifact["interpretation_sections"]["counterfactual_options"][0][
        "option_id"
    ]


def _rehash(artifact: dict[str, Any]) -> None:
    material = deepcopy(artifact)
    material.pop("content_id", None)
    artifact["content_id"] = "sha256:" + hashlib.sha256(
        canonical_json_bytes(material)
    ).hexdigest()


def _rehash_event(event: dict[str, Any]) -> None:
    material = deepcopy(event)
    material.pop("review_event_id", None)
    event["review_event_id"] = "review-event:" + hashlib.sha256(
        canonical_json_bytes(material)
    ).hexdigest()[:32]


def _codes(validation: Mapping[str, Any]) -> set[str]:
    return {
        str(item.get("code"))
        for item in validation.get("findings", [])
        if isinstance(item, Mapping)
    }


def _accept_revision(model: Mapping[str, Any]) -> dict[str, Any]:
    return apply_human_review(model, _request("accept", [_main_id(model)]))


def test_f4_01_accept_appends_event_without_mutating_source(
    context: dict[str, Any],
) -> None:
    model = context["model"]
    before = canonical_json_bytes(model)
    source_id = _main_id(model)
    revised = apply_human_review(model, _request("accept", [source_id]))
    event = revised["governance"]["human_reviews"][-1]
    assert canonical_json_bytes(model) == before
    assert revised["content_id"] != model["content_id"]
    assert revised["revision"]["revision_no"] == 2
    assert revised["revision"]["status"] == "reviewed"
    assert event["action"] == "accept"
    assert event["source_content_id"] == model["content_id"]
    assert event["target_ids"] == [source_id]
    assert _index(revised)[event["result_target_ids"][0]]["review_status"] == "accepted"
    assert validate_episode_review(revised)["validation_status"] == "accepted"


def test_f4_02_reject_is_auditable(context: dict[str, Any]) -> None:
    model = context["model"]
    source_id = _alternative_id(model)
    revised = apply_human_review(model, _request("reject", [source_id]))
    event = revised["governance"]["human_reviews"][-1]
    assert event["action"] == "reject"
    assert event["reason"]
    assert event["actor_ref"] == "reviewer:fixture"
    assert _index(revised)[event["result_target_ids"][0]]["review_status"] == "rejected"


def test_f4_03_correct_fact_link_creates_corrected_revision(
    context: dict[str, Any],
) -> None:
    model = context["model"]
    source_id = _main_id(model)
    original_refs = set(_index(model)[source_id]["fact_refs"])
    replacement = next(
        fact["fact_id"] for fact in _all_facts(model) if fact["fact_id"] not in original_refs
    )
    reason = "Replace the support link with the reviewed frozen fact."
    revised = apply_human_review(
        model,
        _request(
            "correct",
            [source_id],
            reason=reason,
            corrections=[
                {
                    "operation": "replace_fact_refs",
                    "target_id": source_id,
                    "fact_refs": [replacement],
                }
            ],
        ),
    )
    event = revised["governance"]["human_reviews"][-1]
    result = _index(revised)[event["result_target_ids"][0]]
    assert revised["revision"]["status"] == "corrected"
    assert revised["revision"]["correction_reason"] == reason
    assert result["fact_refs"] == [replacement]
    assert result["review_status"] == "revised"
    assert result["finding_id"] != source_id


def test_correct_counterfactual_fact_link(context: dict[str, Any]) -> None:
    model = context["model"]
    source_id = _option_id(model)
    original_refs = set(_index(model)[source_id]["fact_refs"])
    replacement = next(
        fact["fact_id"]
        for fact in _all_facts(model)
        if fact["kind"] == "execution_event" and fact["fact_id"] not in original_refs
    )
    revised = apply_human_review(
        model,
        _request(
            "correct",
            [source_id],
            corrections=[
                {
                    "operation": "replace_fact_refs",
                    "target_id": source_id,
                    "fact_refs": [replacement],
                }
            ],
        ),
    )
    result_id = revised["governance"]["human_reviews"][-1]["result_target_ids"][0]
    assert _index(revised)[result_id]["fact_refs"] == [replacement]
    assert result_id != source_id


def test_f4_04_supersedes_chain_and_event_prefix(context: dict[str, Any]) -> None:
    model = context["model"]
    rev2 = _accept_revision(model)
    rev3 = apply_human_review(
        rev2,
        _request(
            "reject",
            [_alternative_id(rev2)],
            reviewed_at="2026-07-01T10:00:00Z",
        ),
    )
    assert rev2["revision"]["supersedes_content_id"] == model["content_id"]
    assert rev3["revision"]["supersedes_content_id"] == rev2["content_id"]
    assert rev3["governance"]["human_reviews"][:-1] == rev2["governance"][
        "human_reviews"
    ]
    assert validate_revision_chain([rev3, model, rev2])["validation_status"] == "accepted"


def test_f4_05_supersedes_cycle_is_rejected(context: dict[str, Any]) -> None:
    model = context["model"]
    rev2 = _accept_revision(model)
    cyclic_root = deepcopy(model)
    cyclic_root["revision"]["supersedes_content_id"] = rev2["content_id"]
    validation = validate_revision_chain([cyclic_root, rev2])
    assert validation["validation_status"] == "blocked"
    assert "REVISION_CHAIN_CYCLE" in _codes(validation)


def test_f4_06_duplicate_or_rollback_revision_number_is_rejected(
    context: dict[str, Any],
) -> None:
    model = context["model"]
    rev2 = _accept_revision(model)
    invalid = deepcopy(rev2)
    invalid["revision"]["revision_no"] = 1
    _rehash(invalid)
    validation = validate_revision_chain([model, invalid])
    assert validation["validation_status"] == "blocked"
    assert "REVISION_NUMBER_SEQUENCE_INVALID" in _codes(validation)


def test_f4_07_invalid_revision_is_never_written(
    context: dict[str, Any], tmp_path: Path
) -> None:
    invalid = _accept_revision(context["model"])
    invalid["revision"]["revision_no"] = 0
    _rehash(invalid)
    output = tmp_path / "invalid-revision.json"
    with pytest.raises(EpisodeRevisionError):
        save_new_episode_review(output, invalid)
    assert not output.exists()


def test_f4_08_render_and_diff_show_revision_while_preserving_sources(
    context: dict[str, Any],
) -> None:
    model = context["model"]
    rev2 = _accept_revision(model)
    before_markdown = render_episode_review_markdown(model)
    after_markdown = render_episode_review_markdown(rev2)
    source_ref = _all_facts(model)[0]["source_refs"][0]
    for value in (
        source_ref["source_id"],
        source_ref["content_id"],
        source_ref["frozen_pointer"],
    ):
        assert value in before_markdown
        assert value in after_markdown
    assert "revision_status: `draft`" in before_markdown
    assert "revision_status: `reviewed`" in after_markdown
    assert rev2["governance"]["human_reviews"][-1]["review_event_id"] in after_markdown
    difference = diff_episode_reviews(model, rev2)
    assert difference["facts_unchanged"] is True
    assert difference["input_binding_unchanged"] is True
    assert difference["declared_target_ids"] == [_main_id(model)]


def test_f4_09_markdown_injection_and_control_characters_are_escaped(
    context: dict[str, Any],
) -> None:
    payload = P2F3._response_payload(context["facts"])
    payload["interpretation_sections"]["main_tensions"][0]["statement"] = (
        "<script>alert(1)</script>\n# injected\x00\u202e"
    )
    result = P2F3._build(context["facts"], payload)
    assert result.used_fallback is False
    markdown = render_episode_review_markdown(result.artifact)
    assert "<script>" not in markdown
    assert "\n# injected" not in markdown
    assert "\x00" not in markdown
    assert "\u202e" not in markdown
    assert "&lt;script&gt;" in markdown


def test_f4_10_missing_actor_is_rejected(context: dict[str, Any]) -> None:
    request = _request("accept", [_main_id(context["model"])], actor_ref="")
    validation = validate_human_review_request(request)
    assert validation["validation_status"] == "blocked"
    assert "ACTOR_REF_INVALID" in _codes(validation)
    with pytest.raises(EpisodeRevisionError):
        apply_human_review(context["model"], request)


def test_f4_11_revision_never_writes_source_portfolio_database(
    context: dict[str, Any],
) -> None:
    database = context["chain"].portfolio_db
    before_hash = hashlib.sha256(database.read_bytes()).hexdigest()
    _accept_revision(context["model"])
    after_hash = hashlib.sha256(database.read_bytes()).hexdigest()
    assert after_hash == before_hash


def test_f4_12_old_revision_remains_queryable(context: dict[str, Any]) -> None:
    model = context["model"]
    rev2 = _accept_revision(model)
    revisions = list_episode_review_revisions([rev2, model])
    assert revisions[0]["effective_status"] == "superseded"
    assert revisions[1]["effective_status"] == "reviewed"
    queried = query_episode_review_revision([rev2, model], revision_no=1)
    assert canonical_json_bytes(queried) == canonical_json_bytes(model)
    assert (
        query_episode_review_revision([model, rev2], content_id=model["content_id"])[
            "content_id"
        ]
        == model["content_id"]
    )


def test_request_targets_and_corrections_must_match(context: dict[str, Any]) -> None:
    target = _main_id(context["model"])
    request = _request(
        "correct",
        [target],
        corrections=[
            {
                "operation": "replace_fact_refs",
                "target_id": _alternative_id(context["model"]),
                "fact_refs": [_all_facts(context["model"])[0]["fact_id"]],
            }
        ],
    )
    validation = validate_human_review_request(request)
    assert validation["validation_status"] == "blocked"
    assert "CORRECTION_TARGET_MISMATCH" in _codes(validation)


def test_unknown_interpretation_target_is_rejected(context: dict[str, Any]) -> None:
    with pytest.raises(EpisodeRevisionError, match="unknown interpretation"):
        apply_human_review(
            context["model"],
            _request("accept", ["finding:" + "0" * 32]),
        )


def test_unknown_fact_reference_is_rejected(context: dict[str, Any]) -> None:
    target = _main_id(context["model"])
    request = _request(
        "correct",
        [target],
        corrections=[
            {
                "operation": "replace_fact_refs",
                "target_id": target,
                "fact_refs": ["fact:" + "0" * 32],
            }
        ],
    )
    with pytest.raises(EpisodeRevisionError, match="unknown facts"):
        apply_human_review(context["model"], request)


def test_option_rejects_finding_only_counterevidence_fields(
    context: dict[str, Any],
) -> None:
    target = _option_id(context["model"])
    fact_ref = _index(context["model"])[target]["fact_refs"][0]
    request = _request(
        "correct",
        [target],
        corrections=[
            {
                "operation": "replace_fact_refs",
                "target_id": target,
                "fact_refs": [fact_ref],
                "counterevidence_status": "missing",
            }
        ],
    )
    with pytest.raises(EpisodeRevisionError, match="counterevidence fields"):
        apply_human_review(context["model"], request)


def test_correction_cannot_introduce_temporal_leakage(
    context: dict[str, Any],
) -> None:
    target = _option_id(context["model"])
    outcome_id = next(
        fact["fact_id"]
        for fact in _all_facts(context["model"])
        if fact["kind"] == "outcome_record"
    )
    request = _request(
        "correct",
        [target],
        corrections=[
            {
                "operation": "replace_fact_refs",
                "target_id": target,
                "fact_refs": [outcome_id],
            }
        ],
    )
    with pytest.raises(EpisodeRevisionError, match="failed validation"):
        apply_human_review(context["model"], request)


def test_review_time_cannot_precede_prior_provenance(context: dict[str, Any]) -> None:
    rev2 = _accept_revision(context["model"])
    with pytest.raises(EpisodeRevisionError, match="cannot precede"):
        apply_human_review(
            rev2,
            _request(
                "reject",
                [_alternative_id(rev2)],
                reviewed_at="2026-07-01T08:30:00Z",
            ),
        )


def test_target_order_is_canonical_and_reproducible(context: dict[str, Any]) -> None:
    targets = [_main_id(context["model"]), _alternative_id(context["model"])]
    forward = apply_human_review(context["model"], _request("accept", targets))
    reverse = apply_human_review(
        context["model"], _request("accept", list(reversed(targets)))
    )
    assert canonical_json_bytes(forward) == canonical_json_bytes(reverse)


def test_event_id_tampering_is_rejected(context: dict[str, Any]) -> None:
    revised = _accept_revision(context["model"])
    revised["governance"]["human_reviews"][-1]["actor_ref"] = "reviewer:tampered"
    _rehash(revised)
    validation = validate_episode_review(revised)
    assert validation["validation_status"] == "blocked"
    assert "HUMAN_REVIEW_EVENT_ID_MISMATCH" in _codes(validation)


def test_chain_rejects_undeclared_interpretation_change(
    context: dict[str, Any],
) -> None:
    model = context["model"]
    rev2 = _accept_revision(model)
    tampered = deepcopy(rev2)
    item = tampered["interpretation_sections"]["alternative_explanations"][0]
    item["statement"] = item["statement"] + " Additional undeclared text."
    item["finding_id"] = finding_content_id("alternative_explanations", item)
    tampered["interpretation_sections"]["alternative_explanations"].sort(
        key=lambda value: value["finding_id"]
    )
    _rehash(tampered)
    assert validate_episode_review(tampered)["validation_status"] == "accepted"
    validation = validate_revision_chain([model, tampered])
    assert validation["validation_status"] == "blocked"
    assert "UNSCOPED_INTERPRETATION_CHANGE" in _codes(validation)


def test_chain_rejects_extra_change_inside_declared_accept_target(
    context: dict[str, Any],
) -> None:
    model = context["model"]
    rev2 = _accept_revision(model)
    tampered = deepcopy(rev2)
    event = tampered["governance"]["human_reviews"][-1]
    old_result_id = event["result_target_ids"][0]
    item = _index(tampered)[old_result_id]
    item["statement"] = item["statement"] + " Undeclared extra text."
    item["finding_id"] = finding_content_id("main_tensions", item)
    tampered["interpretation_sections"]["main_tensions"].sort(
        key=lambda value: value["finding_id"]
    )
    event["result_target_ids"] = [item["finding_id"]]
    _rehash_event(event)
    _rehash(tampered)
    assert validate_episode_review(tampered)["validation_status"] == "accepted"
    validation = validate_revision_chain([model, tampered])
    assert validation["validation_status"] == "blocked"
    assert "HUMAN_REVIEW_TRANSITION_MISMATCH" in _codes(validation)


@pytest.mark.parametrize("payload", [None, {}, ["invalid"]])
def test_revision_chain_validator_is_total(payload: object) -> None:
    validation = validate_revision_chain(payload)  # type: ignore[arg-type]
    assert validation["validation_status"] == "blocked"


def test_human_revision_source_replay_verifies_immutable_facts(
    context: dict[str, Any],
) -> None:
    revised = _accept_revision(context["model"])
    replay = replay_validate_episode_review(revised, input_bundle=context["bundle"])
    assert replay["validation_status"] == "accepted"
    assert replay["source_verification"]["status"] == "verified"
    assert replay["source_verification"]["generation_mode"] == "human_authored"


def test_new_revision_save_refuses_overwrite(
    context: dict[str, Any], tmp_path: Path
) -> None:
    revised = _accept_revision(context["model"])
    output = tmp_path / "revision-2.json"
    save_new_episode_review(output, revised)
    before = output.read_bytes()
    with pytest.raises(EpisodeRevisionError):
        save_new_episode_review(output, revised)
    assert output.read_bytes() == before


def test_cli_correct_render_diff_and_revision_list(
    context: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source_path = tmp_path / "revision-1.json"
    request_path = tmp_path / "request.json"
    revised_path = tmp_path / "revision-2.json"
    markdown_path = tmp_path / "revision-2.md"
    save_episode_review(source_path, context["model"])
    request_path.write_text(
        json.dumps(
            _request("accept", [_main_id(context["model"])]),
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    assert (
        review_main(
            [
                "episode-review-correct",
                "--artifact",
                str(source_path),
                "--request",
                str(request_path),
                "--output",
                str(revised_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        review_main(
            [
                "episode-review-render",
                "--artifact",
                str(revised_path),
                "--output",
                str(markdown_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert review_main(["episode-review-diff", str(source_path), str(revised_path)]) == 0
    capsys.readouterr()
    assert (
        review_main(
            [
                "episode-review-revision-list",
                str(revised_path),
                str(source_path),
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert '"effective_status": "superseded"' in output
    assert revised_path.exists()
    assert "不是交易建议" in markdown_path.read_text(encoding="utf-8")
