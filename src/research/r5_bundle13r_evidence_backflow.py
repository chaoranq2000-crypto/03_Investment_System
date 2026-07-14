from __future__ import annotations

from copy import deepcopy
import csv
from dataclasses import dataclass, asdict
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

import yaml


SEVERITY_RANK = {"critical": 3, "high": 2, "medium": 1, "low": 0}
QUALIFIED_STATUSES = {"confirmed", "bounded_estimate"}
NONQUALIFIED_STATUSES = {"missing", "conflicting"}
ALL_STATUSES = QUALIFIED_STATUSES | NONQUALIFIED_STATUSES
TODO_PATTERN = re.compile(r"(?:\bTODO\b|\bTBD\b|MISSING|待补|暂缺|未知占位)", re.IGNORECASE)


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str
    message: str
    scope: str = ""
    target_stage: str = ""
    owner_skill: str = ""

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def issue(
    code: str,
    severity: str,
    message: str,
    *,
    scope: str = "",
    target_stage: str = "",
    owner_skill: str = "",
) -> Issue:
    return Issue(code, severity, message, scope, target_stage, owner_skill)


def load_yaml(path: Path | str) -> dict[str, Any]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"expected YAML mapping: {path}")
    return raw


def write_text_lf(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def write_yaml(path: Path, payload: object) -> None:
    write_text_lf(
        path,
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=120),
    )


def canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path | str) -> str:
    return sha256_bytes(Path(path).read_bytes())


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _numeric(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in {float("inf"), float("-inf")}:
        return None
    return number


def _valid_iso_date(value: Any) -> bool:
    try:
        date.fromisoformat(_text(value))
        return True
    except (TypeError, ValueError):
        return False


def _nonempty_strings(value: Any) -> list[str]:
    return [str(item).strip() for item in _list(value) if str(item).strip()]


def _contains_placeholder(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_contains_placeholder(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_placeholder(item) for item in value)
    return bool(TODO_PATTERN.search(str(value))) if value is not None else False


def _sort_issues(items: Iterable[Issue]) -> list[Issue]:
    return sorted(
        items,
        key=lambda row: (
            -SEVERITY_RANK.get(row.severity, -1),
            row.code,
            row.scope,
            row.message,
        ),
    )


def validate_contract(contract: Mapping[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    if contract.get("artifact_type") != "R5_bundle13r_backflow_execution_contract":
        issues.append(issue("CONTRACT_ARTIFACT_TYPE_INVALID", "critical", "Unexpected Bundle 13R contract type"))
    if contract.get("schema_version") != 1:
        issues.append(issue("CONTRACT_SCHEMA_VERSION_INVALID", "critical", "Bundle 13R contract schema_version must be 1"))
    order = [str(item) for item in _list(contract.get("execution_order"))]
    required = ["BF12R-002", "BF12R-003", "RERUN_BUNDLE12R_OPERATING_GATE", "BF12R-001"]
    if order != required:
        issues.append(
            issue(
                "CONTRACT_DEPENDENCY_ORDER_INVALID",
                "critical",
                f"execution_order must be {required!r}",
            )
        )
    boundaries = _mapping(contract.get("fixed_boundaries"))
    for key in ("sample_quality_allowed", "p2_allowed"):
        if boundaries.get(key) is not False:
            issues.append(issue("CONTRACT_PROMOTION_BOUNDARY_OPEN", "critical", f"{key} must remain false"))
    return _sort_issues(issues)


def validate_bundle12r_context(
    context_dir: Path | str,
    contract: Mapping[str, Any],
    *,
    verify_artifact_hashes: bool = True,
) -> tuple[dict[str, dict[str, Any]], list[Issue]]:
    root = Path(context_dir)
    names = {
        "lock": "R5_bundle12r_generation_lock.yaml",
        "backflow": "R5_bundle12r_backflow_plan.yaml",
        "questions": "R5_bundle12r_research_question_plan.yaml",
        "input": "R5_bundle12r_operating_evidence_input_snapshot.yaml",
        "result": "R5_bundle12r_operating_evidence_result.yaml",
    }
    artifacts: dict[str, dict[str, Any]] = {}
    issues: list[Issue] = []
    for key, name in names.items():
        path = root / name
        if not path.is_file():
            issues.append(
                issue(
                    "BUNDLE12R_CONTEXT_ARTIFACT_MISSING",
                    "critical",
                    f"Required Bundle 12R artifact is missing: {name}",
                    scope=name,
                    target_stage="T0",
                    owner_skill="research-orchestrator",
                )
            )
            continue
        try:
            artifacts[key] = load_yaml(path)
        except Exception as exc:  # pragma: no cover - defensive boundary
            issues.append(
                issue(
                    "BUNDLE12R_CONTEXT_ARTIFACT_INVALID",
                    "critical",
                    f"Cannot parse {name}: {type(exc).__name__}: {exc}",
                    scope=name,
                    target_stage="T0",
                    owner_skill="research-orchestrator",
                )
            )

    if issues:
        return artifacts, _sort_issues(issues)

    baseline = _mapping(contract.get("baseline"))
    lock = artifacts["lock"]
    result = artifacts["result"]
    backflow = artifacts["backflow"]
    questions = artifacts["questions"]
    expected_generation = _text(baseline.get("bundle12r_generation_id"))
    expected_workflow = _text(baseline.get("bundle12r_workflow_id"))
    expected_decision = _text(baseline.get("bundle12r_decision"))

    if lock.get("artifact_type") != "R5_bundle12r_generation_lock":
        issues.append(issue("BUNDLE12R_LOCK_TYPE_INVALID", "critical", "Unexpected Bundle 12R generation lock type"))
    if _text(lock.get("generation_id")) != expected_generation:
        issues.append(
            issue(
                "BUNDLE12R_GENERATION_ID_MISMATCH",
                "critical",
                f"Expected {expected_generation}, found {_text(lock.get('generation_id'))}",
                scope="generation_id",
            )
        )
    for payload_name, payload in (("lock", lock), ("result", result), ("backflow", backflow), ("questions", questions)):
        if _text(payload.get("workflow_id")) != expected_workflow:
            issues.append(
                issue(
                    "BUNDLE12R_WORKFLOW_ID_MISMATCH",
                    "critical",
                    f"{payload_name} workflow_id does not match {expected_workflow}",
                    scope=payload_name,
                )
            )
    if _text(lock.get("decision")) != expected_decision or _text(result.get("decision")) != expected_decision:
        issues.append(
            issue(
                "BUNDLE12R_DECISION_MISMATCH",
                "critical",
                f"Bundle 13R requires Bundle 12R decision={expected_decision}",
            )
        )
    if _text(backflow.get("decision")) != "backflow_required":
        issues.append(issue("BUNDLE12R_BACKFLOW_NOT_REQUIRED", "critical", "Expected an open Bundle 12R backflow plan"))
    required_actions = {"BF12R-001", "BF12R-002", "BF12R-003"}
    action_ids = {_text(row.get("action_id")) for row in _list(backflow.get("actions")) if isinstance(row, Mapping)}
    if not required_actions.issubset(action_ids):
        issues.append(
            issue(
                "BUNDLE12R_BACKFLOW_ACTIONS_INCOMPLETE",
                "critical",
                f"Missing actions: {sorted(required_actions - action_ids)}",
            )
        )
    for payload_name, payload in (("lock", lock), ("result", result), ("backflow", backflow), ("questions", questions)):
        if payload.get("sample_quality_allowed") is not False or payload.get("p2_allowed") is not False:
            issues.append(
                issue(
                    "UPSTREAM_PROMOTION_BOUNDARY_OPEN",
                    "critical",
                    f"{payload_name} must keep sample quality and P2 closed",
                    scope=payload_name,
                )
            )

    if verify_artifact_hashes:
        lock_hashes = _mapping(lock.get("artifact_hashes"))
        required_hashes = _mapping(baseline.get("required_bundle12r_artifacts"))
        for name, expected in required_hashes.items():
            actual_in_lock = _text(lock_hashes.get(name))
            if actual_in_lock != _text(expected):
                issues.append(
                    issue(
                        "BUNDLE12R_LOCKED_HASH_MISMATCH",
                        "critical",
                        f"Lock hash for {name} does not match the Bundle 13R binding",
                        scope=name,
                    )
                )
            path = root / str(name)
            if not path.is_file() or sha256_file(path) != _text(expected):
                issues.append(
                    issue(
                        "BUNDLE12R_PHYSICAL_HASH_MISMATCH",
                        "critical",
                        f"Physical hash mismatch for {name}",
                        scope=name,
                    )
                )

    return artifacts, _sort_issues(issues)


def _action_order(contract: Mapping[str, Any]) -> dict[str, int]:
    return {str(action_id): index for index, action_id in enumerate(_list(contract.get("execution_order")))}


def _base_queue_item(
    *,
    item_id: str,
    action_id: str,
    target_kind: str,
    target_stage: str,
    owner_skill: str,
    priority: str = "high",
    dependencies: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "action_id": action_id,
        "target_kind": target_kind,
        "target_stage": target_stage,
        "owner_skill": owner_skill,
        "priority": priority,
        "dependencies": list(dependencies),
        "status": "open",
    }


def build_execution_queue(
    backflow: Mapping[str, Any],
    questions: Mapping[str, Any],
    base_input: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    actions = {_text(row.get("action_id")): _mapping(row) for row in _list(backflow.get("actions"))}
    queue: list[dict[str, Any]] = []

    for raw_question in _list(questions.get("questions")):
        question = _mapping(raw_question)
        question_id = _text(question.get("question_id"))
        if not question_id:
            continue
        owner = _text(question.get("owner_skill"))
        # Bundle 12R may emit generic overlap questions without a concrete pair.
        # Bundle 13R replaces those with one deterministic item per physical overlap row.
        if not _text(question.get("segment_id")):
            continue
        action_id = "BF12R-002" if owner == "evidence-ingest" else "BF12R-003"
        row = _base_queue_item(
            item_id=f"Q-{question_id}",
            action_id=action_id,
            target_kind="driver" if _text(question.get("segment_id")) else "overlap",
            target_stage=_text(question.get("target_stage")) or _text(actions.get(action_id, {}).get("target_stage")),
            owner_skill=owner or _text(actions.get(action_id, {}).get("required_next_skill")),
            priority=_text(question.get("priority")) or "high",
            dependencies=(),
        )
        row.update(
            {
                "question_id": question_id,
                "segment_id": _text(question.get("segment_id")),
                "driver_id": _text(question.get("driver_id")),
                "question": _text(question.get("question")),
                "target_source_types": _nonempty_strings(question.get("target_source_types")),
                "acceptance": _mapping(question.get("acceptance")),
            }
        )
        queue.append(row)

    for metric in ("revenue", "gross_profit"):
        queue.append(
            {
                **_base_queue_item(
                    item_id=f"FIN-{metric.upper()}",
                    action_id="BF12R-002",
                    target_kind="financial_total",
                    target_stage="T1",
                    owner_skill="evidence-ingest",
                ),
                "metric_id": metric,
                "question": f"Qualify the consolidated {metric} denominator for the same period and accounting boundary.",
                "target_source_types": ["audited_financial_statement", "exchange_filing"],
            }
        )

    material_segments = [
        _mapping(row)
        for row in _list(base_input.get("segments"))
        if _text(_mapping(row).get("materiality")) == "material"
    ]
    for segment in material_segments:
        segment_id = _text(segment.get("segment_id"))
        queue.append(
            {
                **_base_queue_item(
                    item_id=f"EXP-{segment_id}",
                    action_id="BF12R-003",
                    target_kind="independent_exposure",
                    target_stage="T2",
                    owner_skill="stock-deep-dive",
                    dependencies=("FIN-REVENUE", "FIN-GROSS_PROFIT"),
                ),
                "segment_id": segment_id,
                "question": f"Qualify independent quantitative exposure for {segment_id} without double counting contained themes.",
                "target_source_types": ["audited_segment_note", "issuer_operating_data", "bounded_reconciliation"],
            }
        )

    for index, raw_overlap in enumerate(_list(base_input.get("overlaps")), start=1):
        overlap = _mapping(raw_overlap)
        left = _text(overlap.get("left_segment_id"))
        right = _text(overlap.get("right_segment_id"))
        queue.append(
            {
                **_base_queue_item(
                    item_id=f"OVL-{index:03d}",
                    action_id="BF12R-003",
                    target_kind="overlap",
                    target_stage="T2",
                    owner_skill="stock-deep-dive",
                    dependencies=(f"EXP-{left}", f"EXP-{right}"),
                ),
                "left_segment_id": left,
                "right_segment_id": right,
                "question": "Classify the relationship and supply an evidence-backed numeric allocation or deduction rule.",
                "target_source_types": ["audited_segment_note", "issuer_ir", "accounting_reconciliation"],
            }
        )

    queue.append(
        {
            **_base_queue_item(
                item_id="RERUN-B12R",
                action_id="RERUN_BUNDLE12R_OPERATING_GATE",
                target_kind="gate_rerun",
                target_stage="RP-12R-OE",
                owner_skill="research-orchestrator",
                dependencies=tuple(row["item_id"] for row in queue if row["action_id"] in {"BF12R-002", "BF12R-003"}),
            ),
            "question": "Re-run Bundle 12R on the promoted input and preserve the exact output generation.",
        }
    )

    for target_artifact in _nonempty_strings(actions.get("BF12R-001", {}).get("target_artifacts")):
        queue.append(
            {
                **_base_queue_item(
                    item_id=f"VAL-{target_artifact.replace('.yaml', '').upper()}",
                    action_id="BF12R-001",
                    target_kind="valuation_eligibility",
                    target_stage="RP6",
                    owner_skill="company-valuation",
                    dependencies=("RERUN-B12R",),
                    priority="medium",
                ),
                "target_artifact": target_artifact,
                "question": "Refresh this method-eligibility pack only after Bundle 12R returns operating_evidence_ready.",
                "deferred": True,
            }
        )

    order = _action_order(contract)
    queue.sort(key=lambda row: (order.get(_text(row.get("action_id")), 99), _text(row.get("item_id"))))
    return {
        "artifact_type": "R5_bundle13r_execution_queue",
        "schema_version": 1,
        "workflow_id": backflow.get("workflow_id"),
        "source_bundle12r_generation_id": _mapping(contract.get("baseline")).get("bundle12r_generation_id"),
        "execution_order": _list(contract.get("execution_order")),
        "item_count": len(queue),
        "items": queue,
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }


def _validate_replacement_trigger(value: Any, *, scope: str) -> list[Issue]:
    trigger = _mapping(value)
    issues: list[Issue] = []
    if not (_text(trigger.get("metric_or_event")) or _text(trigger.get("source_plan"))):
        issues.append(
            issue(
                "REPLACEMENT_TRIGGER_MISSING",
                "high",
                "A missing, conflicting or bounded item needs a replacement metric/event or source plan",
                scope=scope,
            )
        )
    due = trigger.get("due_or_review_date")
    if not _valid_iso_date(due):
        issues.append(
            issue(
                "REPLACEMENT_TRIGGER_DATE_INVALID",
                "high",
                "replacement_trigger.due_or_review_date must be an ISO date",
                scope=scope,
            )
        )
    return issues


def validate_observation(
    raw: Any,
    contract: Mapping[str, Any],
    *,
    scope: str,
    require_financial_mapping: bool = False,
) -> list[Issue]:
    row = _mapping(raw)
    issues: list[Issue] = []
    status = _text(row.get("status"))
    qualification = _mapping(contract.get("qualification"))
    tiers = _mapping(contract.get("source_tiers"))
    if status not in ALL_STATUSES:
        return [issue("OBSERVATION_STATUS_INVALID", "high", f"Unsupported status {status!r}", scope=scope)]

    if _contains_placeholder(row) and status in QUALIFIED_STATUSES:
        issues.append(
            issue(
                "QUALIFIED_OBSERVATION_CONTAINS_PLACEHOLDER",
                "critical",
                "A qualified observation contains a TODO/MISSING placeholder",
                scope=scope,
            )
        )

    if status in QUALIFIED_STATUSES:
        confidence = _numeric(row.get("confidence"))
        tier = _text(row.get("source_tier"))
        minimum = float(
            qualification.get(
                "confirmed_min_confidence" if status == "confirmed" else "bounded_estimate_min_confidence",
                1.0,
            )
        )
        allowed_key = "allowed_for_confirmed" if status == "confirmed" else "allowed_for_bounded_estimate"
        if confidence is None or not (0 <= confidence <= 1) or confidence < minimum:
            issues.append(
                issue(
                    "OBSERVATION_CONFIDENCE_INSUFFICIENT",
                    "high",
                    f"{status} confidence must be at least {minimum:.2f}",
                    scope=scope,
                )
            )
        if not bool(_mapping(tiers.get(tier)).get(allowed_key)):
            issues.append(
                issue(
                    "OBSERVATION_SOURCE_TIER_INELIGIBLE",
                    "high",
                    f"source_tier {tier!r} is not eligible for {status}",
                    scope=scope,
                )
            )
        for field in ("unit", "period"):
            if not _text(row.get(field)):
                issues.append(issue("OBSERVATION_REQUIRED_FIELD_MISSING", "high", f"{field} is required", scope=scope))
        if not _nonempty_strings(row.get("evidence_ids")):
            issues.append(issue("OBSERVATION_EVIDENCE_IDS_MISSING", "critical", "evidence_ids are required", scope=scope))
        if not _nonempty_strings(row.get("locators")):
            issues.append(issue("OBSERVATION_LOCATORS_MISSING", "high", "source locators are required", scope=scope))
        if require_financial_mapping and not _text(row.get("financial_mapping")):
            issues.append(
                issue(
                    "OBSERVATION_FINANCIAL_MAPPING_MISSING",
                    "high",
                    "Driver evidence requires financial_mapping",
                    scope=scope,
                )
            )
        if status == "confirmed":
            if _numeric(row.get("value")) is None:
                issues.append(issue("CONFIRMED_VALUE_INVALID", "high", "confirmed status needs a numeric value", scope=scope))
        else:
            lower = _numeric(row.get("lower_bound"))
            upper = _numeric(row.get("upper_bound"))
            if lower is None or upper is None or lower > upper:
                issues.append(
                    issue(
                        "BOUNDED_ESTIMATE_BOUNDS_INVALID",
                        "high",
                        "bounded_estimate requires ordered numeric lower_bound and upper_bound",
                        scope=scope,
                    )
                )
            if not _text(row.get("methodology")):
                issues.append(issue("BOUNDED_ESTIMATE_METHODOLOGY_MISSING", "high", "methodology is required", scope=scope))
            if not _text(row.get("overlap_treatment")):
                issues.append(
                    issue(
                        "BOUNDED_ESTIMATE_OVERLAP_TREATMENT_MISSING",
                        "high",
                        "overlap_treatment is required",
                        scope=scope,
                    )
                )
            issues.extend(_validate_replacement_trigger(row.get("replacement_trigger"), scope=scope))
    else:
        if any(_numeric(row.get(field)) is not None for field in ("value", "lower_bound", "upper_bound")):
            issues.append(
                issue(
                    "NONQUALIFIED_OBSERVATION_PROMOTES_NUMERIC_VALUE",
                    "critical",
                    "missing/conflicting status cannot carry a promoted numeric value or bound",
                    scope=scope,
                )
            )
        if not _text(row.get("report_limitation")):
            issues.append(
                issue(
                    "NONQUALIFIED_REPORT_LIMITATION_MISSING",
                    "high",
                    "missing/conflicting status needs a visible report limitation",
                    scope=scope,
                )
            )
        issues.extend(_validate_replacement_trigger(row.get("replacement_trigger"), scope=scope))
    return _sort_issues(issues)


def validate_reviewed_backfill(
    payload: Mapping[str, Any],
    queue: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> list[Issue]:
    issues: list[Issue] = validate_contract(contract)
    if payload.get("artifact_type") != "R5_bundle13r_reviewed_backfill_input":
        issues.append(issue("BACKFILL_ARTIFACT_TYPE_INVALID", "critical", "Unexpected backfill artifact_type"))
    if payload.get("schema_version") != 1:
        issues.append(issue("BACKFILL_SCHEMA_VERSION_INVALID", "critical", "schema_version must be 1"))
    if _text(payload.get("workflow_id")) != _text(queue.get("workflow_id")):
        issues.append(issue("BACKFILL_WORKFLOW_ID_MISMATCH", "critical", "Backfill workflow_id does not match Bundle 12R"))
    expected_generation = _text(queue.get("source_bundle12r_generation_id"))
    if _text(payload.get("source_bundle12r_generation_id")) != expected_generation:
        issues.append(
            issue(
                "BACKFILL_SOURCE_GENERATION_MISMATCH",
                "critical",
                f"Backfill must bind to {expected_generation}",
            )
        )
    review = _mapping(payload.get("review"))
    if _text(review.get("status")) != _text(_mapping(contract.get("qualification")).get("require_review_status")):
        issues.append(
            issue(
                "BACKFILL_REVIEW_NOT_COMPLETED",
                "high",
                "Promotion requires review.status=reviewed",
                scope="review.status",
                target_stage="T1",
                owner_skill="evidence-ingest",
            )
        )
    if _text(review.get("status")) == "reviewed":
        if not _text(review.get("reviewer")) or not _valid_iso_date(review.get("reviewed_at")):
            issues.append(
                issue(
                    "BACKFILL_REVIEW_METADATA_INCOMPLETE",
                    "high",
                    "reviewed input needs reviewer and ISO reviewed_at",
                    scope="review",
                )
            )

    queue_items = {_text(row.get("item_id")): _mapping(row) for row in _list(queue.get("items"))}
    question_items = {
        _text(row.get("question_id")): row
        for row in queue_items.values()
        if _text(row.get("question_id"))
    }
    responses = [_mapping(row) for row in _list(payload.get("responses"))]
    seen_question_ids: set[str] = set()
    for index, row in enumerate(responses):
        scope = f"responses[{index}]"
        question_id = _text(row.get("question_id"))
        if question_id not in question_items:
            issues.append(issue("BACKFILL_RESPONSE_UNKNOWN_QUESTION", "high", f"Unknown question_id {question_id!r}", scope=scope))
            continue
        if question_id in seen_question_ids:
            issues.append(issue("BACKFILL_RESPONSE_DUPLICATE_QUESTION", "high", f"Duplicate response for {question_id}", scope=scope))
        seen_question_ids.add(question_id)
        expected = question_items[question_id]
        for field in ("segment_id", "driver_id"):
            if _text(expected.get(field)) and _text(row.get(field)) != _text(expected.get(field)):
                issues.append(
                    issue(
                        "BACKFILL_RESPONSE_TARGET_MISMATCH",
                        "critical",
                        f"{field} does not match question {question_id}",
                        scope=scope,
                    )
                )
        issues.extend(validate_observation(row, contract, scope=scope, require_financial_mapping=True))

    financial_totals = _mapping(payload.get("financial_totals"))
    for metric in _mapping(contract.get("promotion_requirements")).get("required_financial_denominators", []):
        issues.extend(
            validate_observation(
                financial_totals.get(str(metric)),
                contract,
                scope=f"financial_totals.{metric}",
                require_financial_mapping=False,
            )
        )

    exposures = [_mapping(row) for row in _list(payload.get("independent_exposures"))]
    seen_segments: set[str] = set()
    for index, row in enumerate(exposures):
        scope = f"independent_exposures[{index}]"
        segment_id = _text(row.get("segment_id"))
        if not segment_id:
            issues.append(issue("INDEPENDENT_EXPOSURE_SEGMENT_ID_MISSING", "high", "segment_id is required", scope=scope))
        elif segment_id in seen_segments:
            issues.append(issue("INDEPENDENT_EXPOSURE_DUPLICATE", "high", f"Duplicate {segment_id}", scope=scope))
        seen_segments.add(segment_id)
        issues.extend(validate_observation(row, contract, scope=scope))
        if _text(row.get("status")) in QUALIFIED_STATUSES and not _nonempty_strings(row.get("quantitative_metric_ids")):
            issues.append(
                issue(
                    "INDEPENDENT_EXPOSURE_METRIC_IDS_MISSING",
                    "high",
                    "Qualified independent exposure needs quantitative_metric_ids",
                    scope=scope,
                )
            )

    allowed_relations = set(_mapping(contract.get("promotion_requirements")).get("overlap_relations", []))
    numeric_required = set(
        _mapping(contract.get("promotion_requirements")).get("overlap_numeric_adjustment_required_for", [])
    )
    overlaps = [_mapping(row) for row in _list(payload.get("overlaps"))]
    seen_pairs: set[tuple[str, str]] = set()
    for index, row in enumerate(overlaps):
        scope = f"overlaps[{index}]"
        pair = (_text(row.get("left_segment_id")), _text(row.get("right_segment_id")))
        if not all(pair):
            issues.append(issue("OVERLAP_PAIR_INCOMPLETE", "high", "Both segment IDs are required", scope=scope))
        if pair in seen_pairs:
            issues.append(issue("OVERLAP_PAIR_DUPLICATE", "high", f"Duplicate overlap pair {pair}", scope=scope))
        seen_pairs.add(pair)
        relation = _text(row.get("relation"))
        if relation not in allowed_relations:
            issues.append(issue("OVERLAP_RELATION_INVALID", "high", f"Unsupported relation {relation!r}", scope=scope))
        if not _text(row.get("allocation_method")):
            issues.append(issue("OVERLAP_ALLOCATION_METHOD_MISSING", "high", "allocation_method is required", scope=scope))
        if not _nonempty_strings(row.get("evidence_ids")) or not _nonempty_strings(row.get("locators")):
            issues.append(issue("OVERLAP_EVIDENCE_MISSING", "critical", "Overlap classification needs evidence IDs and locators", scope=scope))
        if relation in numeric_required:
            for metric in ("revenue_adjustment", "gross_profit_adjustment"):
                issues.extend(validate_observation(row.get(metric), contract, scope=f"{scope}.{metric}"))

    if payload.get("sample_quality_allowed") is not False or payload.get("p2_allowed") is not False:
        issues.append(issue("BACKFILL_PROMOTION_BOUNDARY_OPEN", "critical", "sample quality and P2 must remain false"))
    return _sort_issues(issues)


def _by_segment(segments: list[Any]) -> dict[str, dict[str, Any]]:
    return {_text(_mapping(row).get("segment_id")): _mapping(row) for row in segments}


def merge_reviewed_backfill(
    base_input: Mapping[str, Any],
    reviewed_backfill: Mapping[str, Any],
    *,
    generation_id: str | None = None,
) -> dict[str, Any]:
    promoted = deepcopy(dict(base_input))
    segments = _by_segment(_list(promoted.get("segments")))

    for raw in _list(reviewed_backfill.get("responses")):
        response = deepcopy(_mapping(raw))
        segment_id = _text(response.get("segment_id"))
        driver_id = _text(response.get("driver_id"))
        if segment_id not in segments or not driver_id:
            continue
        drivers = [_mapping(row) for row in _list(segments[segment_id].get("drivers"))]
        for index, driver in enumerate(drivers):
            if _text(driver.get("driver_id")) == driver_id:
                retained_id = driver.get("driver_id")
                response.pop("question_id", None)
                response.pop("response_id", None)
                response["driver_id"] = retained_id
                drivers[index] = response
                break
        segments[segment_id]["drivers"] = drivers

    financial_totals = _mapping(promoted.get("financial_totals"))
    for key, value in _mapping(reviewed_backfill.get("financial_totals")).items():
        if value not in (None, {}, []):
            financial_totals[str(key)] = deepcopy(value)
    promoted["financial_totals"] = financial_totals

    for raw in _list(reviewed_backfill.get("independent_exposures")):
        exposure = deepcopy(_mapping(raw))
        segment_id = _text(exposure.pop("segment_id", ""))
        if segment_id in segments:
            segments[segment_id]["independent_exposure"] = exposure

    promoted["segments"] = list(segments.values())

    overlap_updates = {
        (_text(_mapping(row).get("left_segment_id")), _text(_mapping(row).get("right_segment_id"))): deepcopy(_mapping(row))
        for row in _list(reviewed_backfill.get("overlaps"))
    }
    overlaps: list[dict[str, Any]] = []
    for raw in _list(promoted.get("overlaps")):
        row = _mapping(raw)
        pair = (_text(row.get("left_segment_id")), _text(row.get("right_segment_id")))
        overlaps.append(overlap_updates.pop(pair, deepcopy(row)))
    overlaps.extend(overlap_updates.values())
    promoted["overlaps"] = overlaps

    reviewed_valuation = _mapping(reviewed_backfill.get("valuation_inputs"))
    if reviewed_valuation:
        base_valuation = _mapping(promoted.get("valuation_inputs"))
        for key, value in reviewed_valuation.items():
            if value not in (None, {}, []):
                base_valuation[str(key)] = deepcopy(value)
        promoted["valuation_inputs"] = base_valuation

    promoted["artifact_type"] = "R5_bundle12r_operating_evidence_input"
    promoted["schema_version"] = 1
    promoted["as_of_date"] = reviewed_backfill.get("as_of_date") or promoted.get("as_of_date")
    promoted.pop("fixture_type", None)
    promoted["bundle13r_backfill_lineage"] = {
        "source_bundle12r_generation_id": reviewed_backfill.get("source_bundle12r_generation_id"),
        "backfill_generation_id": generation_id or "pending_generation_lock",
        "review": deepcopy(reviewed_backfill.get("review")),
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
    return promoted


def _qualified(row: Any) -> bool:
    return _text(_mapping(row).get("status")) in QUALIFIED_STATUSES


def _t1_t2_resolution(
    queue: Mapping[str, Any],
    reviewed_backfill: Mapping[str, Any],
    validation_issues: Sequence[Issue],
) -> tuple[set[str], set[str]]:
    blocked_scopes = {row.scope for row in validation_issues if row.severity in {"critical", "high"}}
    responses = {_text(_mapping(row).get("question_id")): _mapping(row) for row in _list(reviewed_backfill.get("responses"))}
    totals = _mapping(reviewed_backfill.get("financial_totals"))
    exposures = {_text(_mapping(row).get("segment_id")): _mapping(row) for row in _list(reviewed_backfill.get("independent_exposures"))}
    overlap_rows = [_mapping(row) for row in _list(reviewed_backfill.get("overlaps"))]
    resolved: set[str] = set()
    unresolved: set[str] = set()

    for raw in _list(queue.get("items")):
        item = _mapping(raw)
        item_id = _text(item.get("item_id"))
        if _text(item.get("action_id")) not in {"BF12R-002", "BF12R-003"}:
            continue
        kind = _text(item.get("target_kind"))
        is_resolved = False
        if kind == "driver":
            row = responses.get(_text(item.get("question_id")), {})
            is_resolved = _qualified(row)
        elif kind == "financial_total":
            is_resolved = _qualified(totals.get(_text(item.get("metric_id"))))
        elif kind == "independent_exposure":
            row = exposures.get(_text(item.get("segment_id")), {})
            is_resolved = _qualified(row) and bool(_nonempty_strings(row.get("quantitative_metric_ids")))
        elif kind == "overlap":
            pair = (_text(item.get("left_segment_id")), _text(item.get("right_segment_id")))
            row = next(
                (
                    candidate
                    for candidate in overlap_rows
                    if (_text(candidate.get("left_segment_id")), _text(candidate.get("right_segment_id"))) == pair
                ),
                {},
            )
            relation = _text(row.get("relation"))
            is_resolved = relation in {"disjoint", "contains", "overlaps"} and bool(_text(row.get("allocation_method")))
            if relation in {"contains", "overlaps"}:
                is_resolved = is_resolved and _qualified(row.get("revenue_adjustment")) and _qualified(
                    row.get("gross_profit_adjustment")
                )
        if any(scope.startswith(item_id) for scope in blocked_scopes):
            is_resolved = False
        (resolved if is_resolved else unresolved).add(item_id)
    return resolved, unresolved


def evaluate_backflow_execution(
    *,
    queue: Mapping[str, Any],
    reviewed_backfill: Mapping[str, Any],
    validation_issues: Sequence[Issue],
    downstream_bundle12r_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    blockers = [row for row in validation_issues if row.severity in {"critical", "high"}]
    resolved, unresolved = _t1_t2_resolution(queue, reviewed_backfill, validation_issues)
    downstream_decision = _text(_mapping(downstream_bundle12r_result).get("decision"))

    if blockers:
        decision = "blocked_invalid_reviewed_backfill"
    elif downstream_decision == "operating_evidence_ready":
        decision = "operating_evidence_requalified"
    elif not unresolved:
        decision = "ready_for_bundle12r_rerun"
    else:
        decision = "backflow_execution_in_progress"

    valuation_allowed = decision == "operating_evidence_requalified"
    return {
        "artifact_type": "R5_bundle13r_backflow_execution_result",
        "schema_version": 1,
        "workflow_id": queue.get("workflow_id"),
        "source_bundle12r_generation_id": queue.get("source_bundle12r_generation_id"),
        "decision": decision,
        "resolved_t1_t2_item_count": len(resolved),
        "unresolved_t1_t2_item_count": len(unresolved),
        "resolved_t1_t2_items": sorted(resolved),
        "unresolved_t1_t2_items": sorted(unresolved),
        "validation_issue_count": len(validation_issues),
        "blocker_count": len(blockers),
        "issues": [row.as_dict() for row in _sort_issues(validation_issues)],
        "bundle12r_rerun_decision": downstream_decision or None,
        "valuation_backflow_allowed": valuation_allowed,
        "required_next_skill": (
            "company-valuation"
            if valuation_allowed
            else "research-orchestrator"
            if decision == "ready_for_bundle12r_rerun"
            else "evidence-ingest"
        ),
        "human_review_status": "pending",
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }


def render_rerun_command(promoted_input_name: str, output_dir_hint: str) -> str:
    return "\n".join(
        [
            "# Bundle 12R 重跑命令",
            "",
            "仅当 Bundle 13R 结果为 `ready_for_bundle12r_rerun` 时执行：",
            "",
            "```bash",
            "python scripts/run_r5_bundle12r_operating_evidence_gate.py \\",
            f"  --input {promoted_input_name} \\",
            "  --contract config/r5_bundle12r_operating_evidence_contract.yaml \\",
            f"  --output-dir {output_dir_hint} \\",
            "  --strict",
            "```",
            "",
            "重跑结果仍为 `needs_backflow` 时，不得启动 BF12R-001 估值资格刷新。",
            "无论结果如何，`sample_quality_allowed=false`、`p2_allowed=false`。",
            "",
        ]
    )


def _write_unresolved_csv(path: Path, queue: Mapping[str, Any], result: Mapping[str, Any]) -> None:
    unresolved = set(_nonempty_strings(result.get("unresolved_t1_t2_items")))
    fields = [
        "item_id",
        "action_id",
        "target_kind",
        "target_stage",
        "owner_skill",
        "segment_id",
        "driver_id",
        "question",
        "dependencies",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for raw in _list(queue.get("items")):
            row = _mapping(raw)
            if _text(row.get("item_id")) not in unresolved:
                continue
            writer.writerow(
                {
                    "item_id": row.get("item_id", ""),
                    "action_id": row.get("action_id", ""),
                    "target_kind": row.get("target_kind", ""),
                    "target_stage": row.get("target_stage", ""),
                    "owner_skill": row.get("owner_skill", ""),
                    "segment_id": row.get("segment_id", ""),
                    "driver_id": row.get("driver_id", ""),
                    "question": row.get("question", ""),
                    "dependencies": ";".join(_nonempty_strings(row.get("dependencies"))),
                }
            )


def validate_generation_lock(lock_path: Path | str) -> list[str]:
    path = Path(lock_path)
    lock = load_yaml(path)
    issues: list[str] = []
    root = path.parent
    if lock.get("sample_quality_allowed") is not False:
        issues.append("sample_quality_allowed must remain false")
    if lock.get("p2_allowed") is not False:
        issues.append("p2_allowed must remain false")
    for group_name in ("input_hashes", "artifact_hashes"):
        for label, raw in _mapping(lock.get(group_name)).items():
            entry = _mapping(raw)
            file_name = _text(entry.get("file")) if entry else _text(label)
            expected = _text(entry.get("sha256")) if entry else _text(raw)
            physical = root / file_name
            if not physical.is_file():
                issues.append(f"missing {group_name[:-1]}: {physical}")
            elif sha256_file(physical) != expected:
                issues.append(f"hash mismatch: {physical}")
    return issues


def write_bundle13r_outputs(
    *,
    context_dir: Path | str,
    reviewed_backfill_path: Path | str,
    contract_path: Path | str,
    output_dir: Path | str,
    downstream_bundle12r_result_path: Path | str | None = None,
    verify_bundle12r_hashes: bool = True,
) -> dict[str, Any]:
    context_root = Path(context_dir)
    reviewed_path = Path(reviewed_backfill_path)
    contract_file = Path(contract_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    contract = load_yaml(contract_file)
    artifacts, context_issues = validate_bundle12r_context(
        context_root,
        contract,
        verify_artifact_hashes=verify_bundle12r_hashes,
    )
    if context_issues:
        queue = {
            "artifact_type": "R5_bundle13r_execution_queue",
            "schema_version": 1,
            "workflow_id": _mapping(contract.get("baseline")).get("bundle12r_workflow_id"),
            "source_bundle12r_generation_id": _mapping(contract.get("baseline")).get("bundle12r_generation_id"),
            "execution_order": _list(contract.get("execution_order")),
            "item_count": 0,
            "items": [],
            "sample_quality_allowed": False,
            "p2_allowed": False,
        }
        reviewed = load_yaml(reviewed_path)
        validation_issues = context_issues
        promoted = {}
    else:
        queue = build_execution_queue(artifacts["backflow"], artifacts["questions"], artifacts["input"], contract)
        reviewed = load_yaml(reviewed_path)
        validation_issues = validate_reviewed_backfill(reviewed, queue, contract)
        promoted = merge_reviewed_backfill(artifacts["input"], reviewed)

    downstream = load_yaml(Path(downstream_bundle12r_result_path)) if downstream_bundle12r_result_path else None
    result = evaluate_backflow_execution(
        queue=queue,
        reviewed_backfill=reviewed,
        validation_issues=validation_issues,
        downstream_bundle12r_result=downstream,
    )

    paths = {
        "contract_snapshot": output_root / "R5_bundle13r_backflow_execution_contract_snapshot.yaml",
        "reviewed_input_snapshot": output_root / "R5_bundle13r_reviewed_backfill_input_snapshot.yaml",
        "queue": output_root / "R5_bundle13r_execution_queue.yaml",
        "result": output_root / "R5_bundle13r_backflow_execution_result.yaml",
        "promoted_input": output_root / "R5_bundle13r_promoted_operating_evidence_input.yaml",
        "unresolved": output_root / "R5_bundle13r_unresolved_items.csv",
        "rerun": output_root / "R5_bundle13r_rerun_bundle12r.md",
        "lock": output_root / "R5_bundle13r_generation_lock.yaml",
    }
    paths["contract_snapshot"].write_bytes(contract_file.read_bytes())
    paths["reviewed_input_snapshot"].write_bytes(reviewed_path.read_bytes())
    write_yaml(paths["queue"], queue)
    write_yaml(paths["result"], result)
    write_yaml(paths["promoted_input"], promoted)
    _write_unresolved_csv(paths["unresolved"], queue, result)
    write_text_lf(
        paths["rerun"],
        render_rerun_command(
            paths["promoted_input"].name,
            "reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle12r_rerun_after_13r",
        ),
    )

    prelock = {
        "source_bundle12r_generation_id": queue.get("source_bundle12r_generation_id"),
        "decision": result.get("decision"),
        "contract_sha256": sha256_file(contract_file),
        "reviewed_input_sha256": sha256_file(reviewed_path),
        "artifact_hashes": {
            path.name: sha256_file(path)
            for key, path in paths.items()
            if key != "lock"
        },
    }
    generation_id = "backflow_gen_r5_bundle13r_" + sha256_bytes(canonical_json(prelock).encode("utf-8"))[:16]
    if promoted:
        promoted["bundle13r_backfill_lineage"]["backfill_generation_id"] = generation_id
        write_yaml(paths["promoted_input"], promoted)
        prelock["artifact_hashes"][paths["promoted_input"].name] = sha256_file(paths["promoted_input"])

    lock = {
        "artifact_type": "R5_bundle13r_generation_lock",
        "schema_version": 1,
        "generation_id": generation_id,
        "workflow_id": queue.get("workflow_id"),
        "source_bundle12r_generation_id": queue.get("source_bundle12r_generation_id"),
        "decision": result.get("decision"),
        "input_hashes": {
            "contract": {"file": paths["contract_snapshot"].name, "sha256": sha256_file(paths["contract_snapshot"])},
            "reviewed_backfill": {
                "file": paths["reviewed_input_snapshot"].name,
                "sha256": sha256_file(paths["reviewed_input_snapshot"]),
            },
        },
        "artifact_hashes": {
            path.name: sha256_file(path)
            for key, path in paths.items()
            if key not in {"lock", "contract_snapshot", "reviewed_input_snapshot"}
        },
        "preserves_bundle11r_exact_hash_review": True,
        "preserves_bundle12r_generation": True,
        "human_review_status": "pending",
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
    write_yaml(paths["lock"], lock)
    return {"result": result, "queue": queue, "promoted_input": promoted, "generation_lock": lock, "paths": paths}
