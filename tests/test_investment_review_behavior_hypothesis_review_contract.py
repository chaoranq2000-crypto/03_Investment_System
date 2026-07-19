from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from src.investment_review.artifact_io import canonical_json_bytes


ROOT = Path(__file__).resolve().parents[1]
REQUEST_SCHEMA = (
    ROOT
    / "docs"
    / "contracts"
    / "P2G_4_BEHAVIOR_HYPOTHESIS_REVIEW_REQUEST.schema.json"
)
REVISION_SCHEMA = (
    ROOT
    / "docs"
    / "contracts"
    / "P2G_4_BEHAVIOR_HYPOTHESIS_REVISION.schema.json"
)
PLAYBOOK = ROOT / "docs" / "playbooks" / "INVESTMENT_REVIEW_P2G_4.md"


def _validator(path: Path) -> Draft202012Validator:
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _stable_id(prefix: str, value: object) -> str:
    return prefix + ":" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()[:32]


def _content_id(value: Mapping[str, Any]) -> str:
    material = deepcopy(dict(value))
    material.pop("content_id", None)
    return "sha256:" + hashlib.sha256(canonical_json_bytes(material)).hexdigest()


def _request_id(request: Mapping[str, Any]) -> str:
    material = deepcopy(dict(request))
    material.pop("request_id", None)
    material["actions"] = sorted(
        material["actions"], key=lambda item: item["target_hypothesis_id"]
    )
    return _stable_id("review-request", material)


def _replacement(*, statement: str = "该候选仅在冻结范围内仍需进一步验证。") -> dict[str, Any]:
    return {
        "statement": statement,
        "scope": {
            "episode_ids": ["episode-1", "episode-2"],
            "start_at": "2026-01-01T00:00:00Z",
            "end_at": "2026-06-30T23:59:59Z",
            "market_contexts": ["portfolio_drawdown"],
        },
        "evaluation_refs": ["evaluation:" + "1" * 32],
        "supporting_reasons": ["冻结 evaluation 记录了该有限关系。"],
        "counterevidence_evaluation_refs": [],
        "counterevidence_search": "已检查同一 source set 的其他 evaluation。",
        "alternative_explanations": ["不同 episode 的事件周期可能不可比。"],
        "assumptions": ["引用范围具有最低限度可比性。"],
        "uncertainty_notes": ["样本有限，不能推出长期人格或稳定因果。"],
        "falsification_conditions": ["后续可比样本不再出现该关系时候选减弱。"],
        "next_observations_needed": ["补充更多 cutoff-safe episode。"],
        "temporal_perspective": "retrospective",
    }


def _request() -> dict[str, Any]:
    request: dict[str, Any] = {
        "schema_version": "p2g.behavior_hypothesis_review_request.v1",
        "request_id": "",
        "expected_parent_content_id": "sha256:" + "a" * 64,
        "actor": "reviewer:test",
        "reviewed_at": "2026-07-19T12:00:00Z",
        "actions": [
            {
                "target_hypothesis_id": "hypothesis:" + "1" * 32,
                "action": "accept",
                "reason": "已核对冻结 evaluation、反证和适用范围。",
                "replacement": None,
            },
            {
                "target_hypothesis_id": "hypothesis:" + "2" * 32,
                "action": "correct",
                "reason": "原候选适用范围过宽，需要完整替换。",
                "replacement": _replacement(),
            },
        ],
    }
    request["request_id"] = _request_id(request)
    return request


def _revision() -> dict[str, Any]:
    hypothesis_id = "hypothesis:" + "1" * 32
    request_id = "review-request:" + "2" * 32
    event = {
        "review_event_id": "hypothesis-review-event:" + "3" * 32,
        "request_id": request_id,
        "actor": "reviewer:test",
        "reviewed_at": "2026-07-19T12:00:00Z",
        "action": "accept",
        "reason": "已核对冻结 evaluation、反证和适用范围。",
        "target_hypothesis_id": hypothesis_id,
        "result_hypothesis_id": hypothesis_id,
        "target_status_before": "proposed",
        "target_status_after": "accepted",
        "result_status": "accepted",
    }
    artifact: dict[str, Any] = {
        "schema_version": "p2g.behavior_hypothesis_revision.v1",
        "artifact_type": "behavior_hypothesis_revision",
        "content_id": "sha256:" + "4" * 64,
        "revision_chain_id": "hypothesis-revision-chain:" + "5" * 32,
        "revision": {
            "revision_no": 1,
            "parent_content_id": "sha256:" + "6" * 64,
            "root_hypothesis_set_content_id": "sha256:" + "6" * 64,
            "request_id": request_id,
        },
        "source_hypothesis_set": {
            "schema_version": "p2g.behavior_hypothesis_set.v1",
            "hypothesis_set_id": "hypothesis-set:" + "7" * 32,
            "content_id": "sha256:" + "6" * 64,
        },
        "source_observation_set": {
            "schema_version": "p2g.behavior_observation_set.v1",
            "observation_set_id": "observation-set:" + "8" * 32,
            "content_id": "sha256:" + "9" * 64,
            "release_readiness": "ready",
            "source_verification": "verified",
            "temporal_scope": {
                "effective_from": "2026-01-01T00:00:00Z",
                "effective_to": "2026-07-01T00:00:00Z",
                "knowledge_cutoff": "2026-07-01T08:00:00Z",
            },
        },
        "evaluation_inventory": [
            {
                "evaluation_id": "evaluation:" + "1" * 32,
                "evaluation_sha256": "sha256:" + "a" * 64,
                "detector_id": "adjacent_episode_cadence",
                "detector_version": "1",
                "status": "observed",
                "reason_codes": [],
                "episode_ids": ["episode-1", "episode-2"],
                "review_ids": ["review-1", "review-2"],
            }
        ],
        "model_provenance": {
            "model_id": "recorded-model-v1",
            "generated_at": "2026-07-18T12:00:00Z",
            "response_sha256": "sha256:" + "b" * 64,
        },
        "hypotheses": [
            {
                "hypothesis_id": hypothesis_id,
                "lineage_root_hypothesis_id": hypothesis_id,
                "supersedes_hypothesis_id": None,
                "status": "accepted",
                **_replacement(),
                "warning_codes": [],
                "guardrail_flags": [],
            }
        ],
        "review_events": [event],
        "warnings": [],
        "release_readiness": {"status": "ready", "blocker_codes": []},
        "source_verification": {
            "status": "verified",
            "validation_mode": "p2g3_source_replay",
            "verified_content_id": "sha256:" + "9" * 64,
        },
        "canonicalization": {
            "builder_version": "p2g.behavior_hypothesis_revision.builder.v1",
            "canonical_json": "utf8_nfc_sorted_keys_compact_no_float",
            "content_hash": "sha256",
            "sort_version": "p2g.behavior_hypothesis_revision_sort.v1",
        },
    }
    return artifact


def test_contract_schemas_and_examples_validate() -> None:
    assert list(_validator(REQUEST_SCHEMA).iter_errors(_request())) == []
    assert list(_validator(REVISION_SCHEMA).iter_errors(_revision())) == []


@pytest.mark.parametrize(
    "field",
    ["actor", "reviewed_at", "expected_parent_content_id"],
)
def test_request_requires_audit_and_parent_fields(field: str) -> None:
    request = _request()
    request.pop(field)
    assert list(_validator(REQUEST_SCHEMA).iter_errors(request))


def test_request_rejects_missing_reason_unknown_action_empty_correction_and_extra_fields() -> None:
    validator = _validator(REQUEST_SCHEMA)

    missing_reason = _request()
    missing_reason["actions"][0].pop("reason")
    assert list(validator.iter_errors(missing_reason))

    unknown_action = _request()
    unknown_action["actions"][0]["action"] = "approve"
    assert list(validator.iter_errors(unknown_action))

    empty_correction = _request()
    empty_correction["actions"][1]["replacement"] = None
    assert list(validator.iter_errors(empty_correction))

    extra_field = _request()
    extra_field["implicit_merge"] = True
    assert list(validator.iter_errors(extra_field))

    duplicate_target = _request()
    duplicate_target["actions"].append(deepcopy(duplicate_target["actions"][0]))
    assert list(validator.iter_errors(duplicate_target))


def test_state_machine_is_locked_in_the_canonical_playbook() -> None:
    playbook = PLAYBOOK.read_text(encoding="utf-8")
    transitions = {
        "proposed --accept--> accepted",
        "proposed --reject--> rejected",
        "proposed --correct--> superseded + new proposed",
        "accepted --correct--> superseded + new proposed",
        "rejected --correct--> superseded + new proposed",
        "superseded ----------> terminal",
    }
    assert all(transition in playbook for transition in transitions)


def test_request_and_revision_identity_rules_are_order_and_key_deterministic() -> None:
    request = _request()
    permuted = deepcopy(request)
    permuted["actions"].reverse()
    assert _request_id(request) == _request_id(permuted)
    assert request["request_id"] == _request_id(request)

    revision = _revision()
    reordered = dict(reversed(list(revision.items())))
    assert _content_id(revision) == _content_id(reordered)
    assert revision["canonicalization"] == {
        "builder_version": "p2g.behavior_hypothesis_revision.builder.v1",
        "canonical_json": "utf8_nfc_sorted_keys_compact_no_float",
        "content_hash": "sha256",
        "sort_version": "p2g.behavior_hypothesis_revision_sort.v1",
    }
