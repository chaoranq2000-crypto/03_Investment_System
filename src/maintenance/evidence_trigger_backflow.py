"""Deterministic evidence-trigger evaluation for R5 Bundle 14R.

This module does not create research claims and never promotes unreviewed material.
It evaluates whether newly reviewed issuer evidence satisfies explicit operating-
driver or overlap-elimination contracts, then emits a selective backflow plan.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml


ALLOWED_TRIGGER_KINDS = {"operating_driver", "overlap_elimination"}
ALLOWED_OWNER_STAGES = {"T1_evidence_backflow", "T2_mapping_backflow"}
ALLOWED_SOURCE_CLASSES = {
    "issuer_periodic_report",
    "issuer_announcement",
    "issuer_ir_record",
}
REVIEWED_STATUSES = {"reviewed", "accepted"}


class TriggerContractError(ValueError):
    """Raised when a registry or candidate pack violates the Bundle 14R contract."""


@dataclass(frozen=True)
class TriggerMatch:
    trigger_id: str
    status: str
    matched_evidence_ids: tuple[str, ...]
    rejection_reasons: tuple[str, ...]


def _load_yaml(path: str | Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise TriggerContractError(f"YAML root must be a mapping: {path}")
    return payload


def _dump_yaml(path: str | Path, payload: Mapping[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(dict(payload), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_sha256(payload: Any) -> str:
    return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _as_string_set(values: Any, *, field_name: str) -> set[str]:
    if not isinstance(values, list):
        raise TriggerContractError(f"{field_name} must be a list")
    result = {str(item).strip() for item in values if str(item).strip()}
    if len(result) != len(values):
        raise TriggerContractError(f"{field_name} contains blank or duplicate values")
    return result


def validate_registry(registry: Mapping[str, Any]) -> None:
    if int(registry.get("schema_version", 0)) != 1:
        raise TriggerContractError("registry schema_version must be 1")
    for required in (
        "workflow_id",
        "base_commit",
        "source_bundle13r_generation_id",
        "period_anchor_ref",
        "triggers",
    ):
        if not registry.get(required):
            raise TriggerContractError(f"registry missing required field: {required}")

    triggers = registry.get("triggers")
    if not isinstance(triggers, list) or not triggers:
        raise TriggerContractError("registry triggers must be a non-empty list")

    seen: set[str] = set()
    for index, trigger in enumerate(triggers):
        if not isinstance(trigger, dict):
            raise TriggerContractError(f"trigger[{index}] must be a mapping")
        trigger_id = str(trigger.get("trigger_id", "")).strip()
        if not trigger_id or trigger_id in seen:
            raise TriggerContractError(f"invalid or duplicate trigger_id: {trigger_id!r}")
        seen.add(trigger_id)

        kind = str(trigger.get("kind", ""))
        owner_stage = str(trigger.get("owner_stage", ""))
        if kind not in ALLOWED_TRIGGER_KINDS:
            raise TriggerContractError(f"{trigger_id}: unsupported kind {kind!r}")
        if owner_stage not in ALLOWED_OWNER_STAGES:
            raise TriggerContractError(f"{trigger_id}: unsupported owner_stage {owner_stage!r}")
        if kind == "operating_driver" and owner_stage != "T1_evidence_backflow":
            raise TriggerContractError(f"{trigger_id}: operating driver must route to T1")
        if kind == "overlap_elimination" and owner_stage != "T2_mapping_backflow":
            raise TriggerContractError(f"{trigger_id}: overlap elimination must route to T2")

        if not str(trigger.get("metric_key", "")).strip():
            raise TriggerContractError(f"{trigger_id}: metric_key is required")
        if not str(trigger.get("business_scope", "")).strip():
            raise TriggerContractError(f"{trigger_id}: business_scope is required")
        required_fields = _as_string_set(
            trigger.get("required_fields", []), field_name=f"{trigger_id}.required_fields"
        )
        if not required_fields:
            raise TriggerContractError(f"{trigger_id}: required_fields may not be empty")

        source_classes = _as_string_set(
            trigger.get("allowed_source_classes", []),
            field_name=f"{trigger_id}.allowed_source_classes",
        )
        if not source_classes or not source_classes.issubset(ALLOWED_SOURCE_CLASSES):
            raise TriggerContractError(
                f"{trigger_id}: allowed_source_classes must be a non-empty subset of "
                f"{sorted(ALLOWED_SOURCE_CLASSES)}"
            )
        if trigger.get("period_policy") != "same_period_as_anchor":
            raise TriggerContractError(
                f"{trigger_id}: period_policy must be same_period_as_anchor"
            )
        if str(trigger.get("status", "")) not in {"unresolved", "qualified"}:
            raise TriggerContractError(f"{trigger_id}: status must be unresolved or qualified")


def validate_candidate_pack(candidate_pack: Mapping[str, Any], registry: Mapping[str, Any]) -> None:
    if int(candidate_pack.get("schema_version", 0)) != 1:
        raise TriggerContractError("candidate pack schema_version must be 1")
    if candidate_pack.get("workflow_id") != registry.get("workflow_id"):
        raise TriggerContractError("candidate pack workflow_id does not match registry")
    candidates = candidate_pack.get("candidates", [])
    if not isinstance(candidates, list):
        raise TriggerContractError("candidate pack candidates must be a list")
    seen: set[str] = set()
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            raise TriggerContractError(f"candidate[{index}] must be a mapping")
        evidence_id = str(candidate.get("evidence_id", "")).strip()
        if not evidence_id or evidence_id in seen:
            raise TriggerContractError(f"invalid or duplicate evidence_id: {evidence_id!r}")
        seen.add(evidence_id)


def _candidate_rejection_reasons(
    candidate: Mapping[str, Any],
    trigger: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> list[str]:
    reasons: list[str] = []
    source_class = str(candidate.get("source_class", ""))
    if source_class not in set(trigger.get("allowed_source_classes", [])):
        reasons.append("source_class_not_allowed")
    if str(candidate.get("review_status", "")) not in REVIEWED_STATUSES:
        reasons.append("evidence_not_reviewed")
    if not bool(candidate.get("official_issuer_source", False)):
        reasons.append("not_official_issuer_source")

    if not bool(candidate.get("period_compatible", False)):
        reasons.append("period_not_compatible")
    if candidate.get("period_anchor_ref") != registry.get("period_anchor_ref"):
        reasons.append("period_anchor_mismatch")

    metric_keys = {str(item) for item in candidate.get("metric_keys", [])}
    if str(trigger.get("metric_key")) not in metric_keys:
        reasons.append("metric_key_not_covered")

    available_fields = {str(item) for item in candidate.get("available_fields", [])}
    missing_fields = sorted(set(trigger.get("required_fields", [])) - available_fields)
    if missing_fields:
        reasons.append("missing_required_fields:" + ",".join(missing_fields))

    for field in ("evidence_id", "source_hash", "locator", "document_date"):
        if not str(candidate.get(field, "")).strip():
            reasons.append(f"missing_{field}")
    return sorted(set(reasons))


def evaluate_triggers(
    registry: Mapping[str, Any], candidate_pack: Mapping[str, Any]
) -> dict[str, Any]:
    """Evaluate candidates without changing evidence, model, valuation, or Reader state."""

    validate_registry(registry)
    validate_candidate_pack(candidate_pack, registry)

    candidates = sorted(
        candidate_pack.get("candidates", []), key=lambda item: str(item.get("evidence_id", ""))
    )
    results: list[dict[str, Any]] = []
    qualified_stages: set[str] = set()

    for trigger in sorted(registry["triggers"], key=lambda item: str(item["trigger_id"])):
        matched: list[str] = []
        candidate_rejections: list[dict[str, Any]] = []
        for candidate in candidates:
            reasons = _candidate_rejection_reasons(candidate, trigger, registry)
            if not reasons:
                matched.append(str(candidate["evidence_id"]))
            else:
                candidate_rejections.append(
                    {
                        "evidence_id": str(candidate["evidence_id"]),
                        "reasons": reasons,
                    }
                )
        status = "qualified_candidate" if matched else "unresolved"
        if matched:
            qualified_stages.add(str(trigger["owner_stage"]))
        results.append(
            {
                "trigger_id": trigger["trigger_id"],
                "issue_id": trigger.get("issue_id"),
                "kind": trigger["kind"],
                "owner_stage": trigger["owner_stage"],
                "metric_key": trigger["metric_key"],
                "business_scope": trigger["business_scope"],
                "severity": trigger.get("severity", "high"),
                "status": status,
                "matched_evidence_ids": sorted(set(matched)),
                "candidate_rejections": candidate_rejections,
            }
        )

    qualified_count = sum(item["status"] == "qualified_candidate" for item in results)
    unresolved_count = len(results) - qualified_count
    all_contracts_qualified = unresolved_count == 0
    if all_contracts_qualified:
        decision = "R5_BUNDLE14R_READY_FOR_BUNDLE12R_SELECTIVE_RERUN"
    elif qualified_count:
        decision = "R5_BUNDLE14R_PARTIAL_EVIDENCE_TRIGGERED"
    else:
        decision = "R5_BUNDLE14R_WAITING_FOR_OFFICIAL_EVIDENCE"

    normalized_candidate_pack = deepcopy(dict(candidate_pack))
    normalized_candidate_pack["candidates"] = candidates
    core = {
        "schema_version": 1,
        "workflow_id": registry["workflow_id"],
        "base_commit": registry["base_commit"],
        "source_bundle13r_generation_id": registry["source_bundle13r_generation_id"],
        "period_anchor_ref": registry["period_anchor_ref"],
        "registry_hash": canonical_sha256(registry),
        "candidate_pack_hash": canonical_sha256(normalized_candidate_pack),
        "decision": decision,
        "qualified_trigger_count": qualified_count,
        "unresolved_trigger_count": unresolved_count,
        "trigger_results": results,
        "selective_backflow_stages": sorted(qualified_stages),
        "bundle12r_rerun_allowed": all_contracts_qualified,
        "valuation_refresh_allowed": False,
        "model_regeneration_allowed": False,
        "reader_regeneration_allowed": False,
        "new_human_review_allowed": False,
        "sample_quality_allowed": False,
        "p2_allowed": False,
        "guardrails": [
            "candidate qualification does not equal claim acceptance",
            "only reviewed same-period official issuer evidence may qualify",
            "valuation eligibility remains an independent downstream gate",
            "no model or Reader regeneration occurs in Bundle 14R",
            "P2 remains closed",
        ],
    }
    generation_material = deepcopy(core)
    core["generation_id"] = "evidence_trigger_gen_r5_bundle14r_" + canonical_sha256(
        generation_material
    )[:16]
    return core


def build_selective_backflow_plan(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    for stage in evaluation.get("selective_backflow_stages", []):
        matched = [
            item["trigger_id"]
            for item in evaluation.get("trigger_results", [])
            if item.get("owner_stage") == stage
            and item.get("status") == "qualified_candidate"
        ]
        if stage == "T1_evidence_backflow":
            tasks.append(
                {
                    "task_id": "B14R-SELECTIVE-T1",
                    "stage": stage,
                    "owner_skill": "evidence-ingest",
                    "trigger_ids": sorted(matched),
                    "action": "review_and_promote_only_matched_operating_driver_evidence",
                    "may_mutate": [
                        "reviewed evidence claims and metrics for matched drivers",
                        "Bundle 13R unresolved-item ledger",
                    ],
                    "must_not_mutate": ["valuation", "model", "Reader", "P2 state"],
                }
            )
        elif stage == "T2_mapping_backflow":
            tasks.append(
                {
                    "task_id": "B14R-SELECTIVE-T2",
                    "stage": stage,
                    "owner_skill": "stock-deep-dive",
                    "trigger_ids": sorted(matched),
                    "action": "recompute_only_matched_overlap_eliminations",
                    "may_mutate": [
                        "overlap allocation table for matched scopes",
                        "Bundle 13R unresolved-item ledger",
                    ],
                    "must_not_mutate": ["valuation", "model", "Reader", "P2 state"],
                }
            )

    if bool(evaluation.get("bundle12r_rerun_allowed", False)):
        tasks.append(
            {
                "task_id": "B14R-RERUN-B12R",
                "stage": "R5_bundle12r_requalification",
                "owner_skill": "quality-review",
                "trigger_ids": [
                    item["trigger_id"] for item in evaluation.get("trigger_results", [])
                ],
                "action": "rerun_bundle12r_operating_evidence_and_overlap_gates",
                "preconditions": [
                    "all 11 Bundle 14R trigger contracts have reviewed candidates",
                    "T1 and T2 promotion receipts are complete",
                    "no deterministic hash drift",
                ],
                "must_not_mutate": [
                    "valuation until valuation eligibility passes",
                    "Reader until a new model generation is accepted",
                    "P2 state",
                ],
            }
        )

    plan_core = {
        "schema_version": 1,
        "workflow_id": evaluation.get("workflow_id"),
        "source_generation_id": evaluation.get("generation_id"),
        "decision": evaluation.get("decision"),
        "tasks": tasks,
        "bundle12r_rerun_allowed": bool(evaluation.get("bundle12r_rerun_allowed", False)),
        "valuation_refresh_allowed": False,
        "reader_regeneration_allowed": False,
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
    plan_core["plan_id"] = "backflow_plan_r5_bundle14r_" + canonical_sha256(plan_core)[:16]
    return plan_core


def update_workflow_state_copy(
    workflow_state: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a copy with a Bundle 14R status section; never overwrite in place."""

    updated = deepcopy(dict(workflow_state))
    updated["status"] = "in_progress"
    updated["current_stage"] = "R5_bundle14r_evidence_trigger_backflow"
    updated["next_stage"] = (
        "R5_bundle12r_requalification"
        if evaluation.get("bundle12r_rerun_allowed")
        else "R5_bundle14r_evidence_trigger_backflow"
    )
    updated["active_skill"] = (
        "quality-review"
        if evaluation.get("bundle12r_rerun_allowed")
        else "evidence-ingest"
    )
    updated["required_next_skill"] = updated["active_skill"]
    updated["bundle14r_evidence_trigger_backflow"] = {
        "status": evaluation.get("decision"),
        "generation_id": evaluation.get("generation_id"),
        "plan_id": plan.get("plan_id"),
        "qualified_trigger_count": evaluation.get("qualified_trigger_count"),
        "unresolved_trigger_count": evaluation.get("unresolved_trigger_count"),
        "bundle12r_rerun_allowed": evaluation.get("bundle12r_rerun_allowed"),
        "valuation_refresh_allowed": False,
        "model_regeneration_allowed": False,
        "reader_regeneration_allowed": False,
        "human_review_status": "pending",
        "sample_quality_allowed": False,
        "p2_allowed": False,
        "next_trigger": "reviewed_same-period_official_operating_evidence",
    }
    return updated


def evaluate_from_files(
    *,
    registry_path: str | Path,
    candidate_pack_path: str | Path,
    output_dir: str | Path,
    workflow_state_path: str | Path | None = None,
) -> dict[str, Path]:
    registry = _load_yaml(registry_path)
    candidate_pack = _load_yaml(candidate_pack_path)
    evaluation = evaluate_triggers(registry, candidate_pack)
    plan = build_selective_backflow_plan(evaluation)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    evaluation_path = output / "R5_bundle14r_trigger_evaluation.yaml"
    plan_path = output / "R5_bundle14r_selective_backflow_plan.yaml"
    _dump_yaml(evaluation_path, evaluation)
    _dump_yaml(plan_path, plan)

    paths = {"evaluation": evaluation_path, "plan": plan_path}
    if workflow_state_path is not None:
        workflow_state = _load_yaml(workflow_state_path)
        updated_state = update_workflow_state_copy(workflow_state, evaluation, plan)
        state_path = output / "workflow_state.bundle14r.proposed.yaml"
        _dump_yaml(state_path, updated_state)
        paths["workflow_state_copy"] = state_path
    return paths
