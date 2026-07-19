"""Occurrence-level Bundle17R backflow queue and truth-preserving owner packets."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

import yaml

from .bf2_seed import GLOBAL_CASE_ID, classify_occurrence
from .contracts import generate_contract_proposal, route_pointer_contract
from .models import ContractError, QueueDocument, Task, QUEUE_SCHEMA_VERSION_V2
from .outcome import queue_metrics
from .queue import atomic_write, save_queue
from .receipts import canonical_json_bytes, sha256_bytes, sha256_file


BACKFLOW_QUEUE_PATH = Path(
    "reports/p1_6/r5_bundle17r/activation_run_a/R5_bundle17r_backflow_queue.csv"
)
POINTER_SEED_PATH = Path(
    "codex_tasks/night_shift/r5_overnight_02_20260720/pointer_occurrences.yaml"
)
EXPECTED_CLASSIFICATION = {
    "analysis_required": 24,
    "dependency_blocked": 20,
    "engineering_local": 8,
    "evidence_required": 8,
    "human_gate": 3,
}
CASE_WORK_ORDER_IDS = {
    GLOBAL_CASE_ID: "BF17R-WO-29d90bec175ab7",
    "golden_multi_business_ai_infrastructure": "BF17R-WO-5ce21a3390be8b",
    "golden_copper_foil_product_generation": "BF17R-WO-ca803d73d4b2b1",
    "golden_gold_mining_cycle": "BF17R-WO-dd409a4bffcd9d",
    "golden_crdmo_backlog_conversion": "BF17R-WO-df7ea35a97ead0",
}
RERUN_WORK_ORDER_ID = "BF17R-WO-67f7a4ec1b0f54"
SOURCE_PATH_PATTERN = re.compile(r"\s+in\s+(?P<path>[^:]+):\s+actual=")
GLOBAL_FORBIDDEN_PATHS = (
    "data/raw/**",
    "config/r5_readout_canonical_index.yaml",
    "reports/workflow_runs/**/workflow_state.yaml",
    "reports/p1_6/r5_bundle17r/**",
    ".local/**",
    "**/__pycache__/**",
    "**/*.pyc",
)
CASE_TICKERS = {
    "golden_copper_foil_product_generation": "301217.SZ",
    "golden_crdmo_backlog_conversion": "603259.SH",
    "golden_gold_mining_cycle": "600988.SH",
    "golden_multi_business_ai_infrastructure": "600673.SH",
}


def _safe_suffix(value: str, *, length: int = 16) -> str:
    return sha256_bytes(value.encode("utf-8"))[:length]


def _row_identity(row: Mapping[str, str]) -> str:
    normalized = {str(key): str(value or "").strip() for key, value in row.items()}
    return "BF17R-I-" + sha256_bytes(canonical_json_bytes(normalized))[:16]


def _task_id(kind: str, identifier: str) -> str:
    return f"ns02_t30_{kind}_{_safe_suffix(identifier)}"


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ContractError(f"backflow queue[{path}]: missing CSV header")
            return [
                {str(key): str(value or "").strip() for key, value in row.items()}
                for row in reader
            ]
    except OSError as exc:
        raise ContractError(f"backflow queue[{path}]: cannot read: {exc}") from exc


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ContractError(f"YAML[{path}]: cannot read: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"YAML[{path}]: root must be an object")
    return value


def _source_artifact(message: str, repo_root: Path) -> tuple[str | None, str | None]:
    match = SOURCE_PATH_PATTERN.search(message)
    if not match:
        return None, None
    relative = match.group("path").replace("\\", "/").strip()
    candidate = (repo_root / PurePosixPath(relative)).resolve()
    root = repo_root.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return relative, None
    if not candidate.is_file() or candidate.is_symlink():
        return relative, None
    return relative, sha256_file(candidate)


def load_occurrences(repo_root: Path) -> list[dict[str, Any]]:
    rows = _read_csv(repo_root / BACKFLOW_QUEUE_PATH)
    if len(rows) != 63:
        raise ContractError(f"expected 63 blocker occurrences, found {len(rows)}")
    occurrences: list[dict[str, Any]] = []
    for row in rows:
        case_id = str(row.get("case_id") or "").strip() or GLOBAL_CASE_ID
        if case_id not in CASE_WORK_ORDER_IDS:
            raise ContractError(f"unknown golden-case identity: {case_id}")
        source_path, source_hash = _source_artifact(row.get("message", ""), repo_root)
        occurrences.append(
            {
                "blocker_occurrence_id": _row_identity(row),
                "work_order_id": CASE_WORK_ORDER_IDS[case_id],
                "case_id": case_id,
                "issuer_ticker": CASE_TICKERS.get(case_id),
                "code": row.get("code", ""),
                "stage": row.get("stage", ""),
                "field": row.get("field", ""),
                "owner_skill": row.get("owner_skill", ""),
                "target_stage": row.get("target_stage", ""),
                "message": row.get("message", ""),
                "requested_action": row.get("requested_action", ""),
                "classification": classify_occurrence(row),
                "classification_is_resolution": False,
                "source_artifact_path": source_path,
                "source_artifact_sha256": source_hash,
                "resolved": False,
                "resolution_receipt_sha256": None,
            }
        )
    occurrences.sort(key=lambda item: item["blocker_occurrence_id"])
    counts = Counter(item["classification"] for item in occurrences)
    if dict(sorted(counts.items())) != EXPECTED_CLASSIFICATION:
        raise ContractError(
            f"classification mismatch: expected {EXPECTED_CLASSIFICATION}, got {dict(counts)}"
        )
    return occurrences


def _occurrence_status(classification: str) -> tuple[str, bool]:
    if classification == "evidence_required":
        return "evidence_required", False
    if classification == "human_gate":
        return "human_gate", True
    if classification == "dependency_blocked":
        return "dependency_blocked", False
    return "blocked_external", False


def build_occurrence_queue(
    occurrences: Sequence[Mapping[str, Any]],
    *,
    source_commit: str,
) -> QueueDocument:
    task_ids = {
        str(item["blocker_occurrence_id"]): _task_id(
            "occ", str(item["blocker_occurrence_id"])
        )
        for item in occurrences
    }
    non_dependency_by_case: dict[str, list[str]] = defaultdict(list)
    for item in occurrences:
        if item["classification"] != "dependency_blocked":
            non_dependency_by_case[str(item["case_id"])].append(
                task_ids[str(item["blocker_occurrence_id"])]
            )

    tasks: list[Task] = []
    for item in occurrences:
        classification = str(item["classification"])
        status, human_gate = _occurrence_status(classification)
        case_id = str(item["case_id"])
        dependencies: tuple[str, ...] = ()
        if classification == "dependency_blocked":
            if case_id == GLOBAL_CASE_ID:
                dependencies = tuple(
                    sorted(
                        task_id
                        for values in non_dependency_by_case.values()
                        for task_id in values
                    )
                )
            else:
                dependencies = tuple(sorted(non_dependency_by_case[case_id]))
            if not dependencies:
                raise ContractError(
                    f"dependency occurrence {item['blocker_occurrence_id']} has no prerequisite"
                )
        notes = (
            f"work_order_id={item['work_order_id']}",
            f"case_id={case_id}",
            f"field={item['field']}",
            f"classification={classification}",
            "classification_is_resolution=false",
            f"source_artifact_path={item.get('source_artifact_path') or 'UNKNOWN'}",
            f"source_artifact_sha256={item.get('source_artifact_sha256') or 'UNKNOWN'}",
        )
        tasks.append(
            Task(
                id=task_ids[str(item["blocker_occurrence_id"])],
                title=f"Bundle17R blocker {item['blocker_occurrence_id']}",
                phase="D_backflow",
                priority=200,
                estimated_work_units=1,
                status=status,
                depends_on=dependencies,
                work_type=classification,
                delivery_required=False,
                goal=str(item.get("requested_action") or item.get("message")),
                allowed_paths=(),
                forbidden_paths=GLOBAL_FORBIDDEN_PATHS,
                acceptance_commands=(),
                required_artifacts=(),
                commit_policy="workstream",
                retry_limit=0,
                on_success={"record_receipt": True},
                on_failure={"emit_failure_packet": True},
                human_gate=human_gate,
                notes=notes,
                contract_origin="source_occurrence_classification",
                path_authority="not_granted",
                acceptance_authority="not_granted",
                review_state="proposed",
                review_sha=None,
                resolution_claims=(),
            )
        )

    parent_task_ids = {
        case_id: _task_id("wo", work_order_id)
        for case_id, work_order_id in CASE_WORK_ORDER_IDS.items()
    }
    for case_id, work_order_id in sorted(CASE_WORK_ORDER_IDS.items()):
        occurrence_dependencies = tuple(
            sorted(
                task_ids[str(item["blocker_occurrence_id"])]
                for item in occurrences
                if item["case_id"] == case_id
            )
        )
        tasks.append(
            Task(
                id=parent_task_ids[case_id],
                title=f"Bundle17R work order {work_order_id}",
                phase="D_backflow",
                priority=120,
                estimated_work_units=1,
                status="pending",
                depends_on=occurrence_dependencies,
                work_type="bf2_work_order",
                delivery_required=False,
                goal="Close every occurrence with independently accepted receipts",
                allowed_paths=(),
                forbidden_paths=GLOBAL_FORBIDDEN_PATHS,
                acceptance_commands=(),
                required_artifacts=(),
                commit_policy="workstream",
                retry_limit=0,
                on_success={"record_receipt": True},
                on_failure={"emit_failure_packet": True},
                human_gate=False,
                notes=(
                    f"source_work_order_id={work_order_id}",
                    f"case_id={case_id}",
                    "resolved_count_requires_independent_receipts=true",
                ),
                contract_origin="night01_verified_work_order_inventory",
                path_authority="not_granted",
                acceptance_authority="not_granted",
                review_state="proposed",
                review_sha=None,
                resolution_claims=(),
            )
        )
    rerun_id = _task_id("wo", RERUN_WORK_ORDER_ID)
    tasks.append(
        Task(
            id=rerun_id,
            title=f"Bundle17R work order {RERUN_WORK_ORDER_ID}",
            phase="D_backflow",
            priority=100,
            estimated_work_units=1,
            status="pending",
            depends_on=tuple(sorted(parent_task_ids.values())),
            work_type="bf2_work_order",
            delivery_required=False,
            goal="Rerun the 16R→15R→14R→17R chain only after five source work orders pass",
            allowed_paths=(),
            forbidden_paths=GLOBAL_FORBIDDEN_PATHS,
            acceptance_commands=(),
            required_artifacts=(),
            commit_policy="workstream",
            retry_limit=0,
            on_success={"record_receipt": True},
            on_failure={"emit_failure_packet": True},
            human_gate=False,
            notes=(
                f"source_work_order_id={RERUN_WORK_ORDER_ID}",
                "research_gate=needs_targeted_backflow",
                "resolved_count_requires_independent_receipts=true",
            ),
            contract_origin="night01_verified_work_order_inventory",
            path_authority="not_granted",
            acceptance_authority="not_granted",
            review_state="proposed",
            review_sha=None,
            resolution_claims=(),
        )
    )
    payload = {
        "schema_version": QUEUE_SCHEMA_VERSION_V2,
        "package_id": "R5_Overnight_Mission_02_20260719",
        "mission_id": "r5_overnight_02_bf2_occurrence_queue",
        "long_term_goal": {
            "id": "r5_bundle17r_bf2_four_case_activation",
            "close_allowed": False,
            "this_mission_may_close_goal": False,
        },
        "baseline": {
            "source_commit": source_commit,
            "work_orders_pending": 6,
            "blocker_occurrences_total": 63,
            "blocker_occurrences_resolved": 0,
            "research_gate": "needs_targeted_backflow",
            "sample_quality_allowed": False,
            "p2_allowed": False,
        },
        "run_window": {
            "timezone": "Europe/London",
            "start_at": "23:00",
            "stop_claiming_at": "06:15",
        },
        "mission_policy": {
            "no_safe_pilot_is_success": False,
            "resolution_requires_independent_receipt": True,
        },
        "task_selection": {
            "order": ["priority_desc", "dependency_ready", "task_id_asc"]
        },
        "read_only_inputs": [BACKFLOW_QUEUE_PATH.as_posix()],
        "tasks": [task.to_mapping() for task in sorted(tasks, key=lambda child: child.id)],
    }
    return QueueDocument.from_mapping(payload, path="occurrence_queue")


def build_dependency_dag(queue: QueueDocument) -> dict[str, Any]:
    nodes = [
        {
            "task_id": task.id,
            "status": task.status,
            "work_type": task.work_type,
            "unlock_condition": (
                "all_dependencies_have_stable_passed_receipts"
                if task.depends_on
                else "external_authority_or_owner_packet"
            ),
        }
        for task in queue.tasks
    ]
    edges = [
        {"from": dependency, "to": task.id}
        for task in queue.tasks
        for dependency in task.depends_on
    ]
    dependent_ids = {item["to"] for item in edges}
    dependency_occurrences = [
        task.id for task in queue.tasks if task.work_type == "dependency_blocked"
    ]
    orphan_dependencies = sorted(set(dependency_occurrences) - dependent_ids)
    result: dict[str, Any] = {
        "schema_version": "r5_night_shift_dependency_dag_v1",
        "node_count": len(nodes),
        "edge_count": len(edges),
        "dependency_blocker_count": len(dependency_occurrences),
        "orphan_dependency_blockers": orphan_dependencies,
        "cycle_count": 0,
        "nodes": nodes,
        "edges": edges,
    }
    result["stable_receipt_sha256"] = sha256_bytes(canonical_json_bytes(result))
    return result


def build_evidence_requests(occurrences: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    requests = []
    for item in occurrences:
        if item["classification"] != "evidence_required":
            continue
        requests.append(
            {
                "request_id": "ER-" + _safe_suffix(str(item["blocker_occurrence_id"]), length=12),
                "blocker_occurrence_id": item["blocker_occurrence_id"],
                "case_id": item["case_id"],
                "issuer_ticker": item.get("issuer_ticker"),
                "field": item["field"],
                "missing_source_class_or_driver": item["field"].split(".")[-1],
                "research_question": item["requested_action"],
                "owner_skill": "evidence-ingest",
                "reviewer_action": "locate, archive, register, and explicitly accept or reject physical official evidence",
                "review_state": "requested",
                "evidence_acceptance": None,
                "auto_accept_allowed": False,
                "backflow_command": "rerun occurrence contract after reviewed evidence receipt exists",
            }
        )
    return {
        "schema_version": "r5_night_shift_evidence_requests_v1",
        "request_count": len(requests),
        "requests": sorted(requests, key=lambda child: child["request_id"]),
    }


def build_analysis_workbooks(occurrences: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    entries = []
    for item in occurrences:
        if item["classification"] != "analysis_required":
            continue
        entries.append(
            {
                "worksheet_id": "AW-" + _safe_suffix(str(item["blocker_occurrence_id"]), length=12),
                "blocker_occurrence_id": item["blocker_occurrence_id"],
                "case_id": item["case_id"],
                "issuer_ticker": item.get("issuer_ticker"),
                "field": item["field"],
                "question": item["requested_action"],
                "model_link": item.get("source_artifact_path"),
                "falsification_condition": "reviewed evidence or a deterministic rerun contradicts the proposed operating relation",
                "required_evidence": "locator-bound reviewed evidence with period, unit, source class, and calculation method",
                "analyst_conclusion": None,
                "auto_judgment_allowed": False,
            }
        )
    return {
        "schema_version": "r5_night_shift_analysis_workbooks_v1",
        "worksheet_count": len(entries),
        "worksheets": sorted(entries, key=lambda child: child["worksheet_id"]),
    }


def build_human_handoffs(occurrences: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    handoffs = []
    for item in occurrences:
        if item["classification"] != "human_gate":
            continue
        handoffs.append(
            {
                "handoff_id": "HG-" + _safe_suffix(str(item["blocker_occurrence_id"]), length=12),
                "blocker_occurrence_id": item["blocker_occurrence_id"],
                "case_id": item["case_id"],
                "candidate_artifact": item.get("source_artifact_path"),
                "candidate_sha256": item.get("source_artifact_sha256"),
                "validation_checklist": [
                    "candidate artifact path and physical hash match",
                    "generation IDs and upstream suite hashes match",
                    "reviewer decision is independently recorded",
                ],
                "reviewer": None,
                "reviewed_at": None,
                "decision": None,
                "decision_notes": None,
                "auto_accept_allowed": False,
            }
        )
    return {
        "schema_version": "r5_night_shift_human_gate_handoffs_v1",
        "handoff_count": len(handoffs),
        "handoffs": sorted(handoffs, key=lambda child: child["handoff_id"]),
    }


def build_pointer_proposals(repo_root: Path) -> dict[str, Any]:
    seed = _read_yaml(repo_root / POINTER_SEED_PATH)
    raw = seed.get("occurrences")
    if not isinstance(raw, list) or len(raw) != 8:
        raise ContractError("pointer occurrence seed must contain exactly eight entries")
    proposals = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ContractError(f"pointer occurrence[{index}] must be an object")
        missing_pointer = str(item.get("missing_pointer") or "")
        observed_fields = [str(value) for value in item.get("observed_legacy_fields") or []]
        route = route_pointer_contract(
            missing_pointer=missing_pointer,
            observed_fields=observed_fields,
        )
        case_id = str(item.get("case_id") or "")
        action = (
            "make a new Bundle16R generation emit generation_id and bind it in a new lock"
            if missing_pointer == "/generation_id"
            else "make a new Bundle16R quality generation emit candidate_ready_for_exact_hash_review after its gates"
        )
        proposal = generate_contract_proposal(
            task_id=f"ns02_t35_pointer_{index:02d}_{_safe_suffix(case_id, length=8)}",
            source_artifact=str(item.get("artifact") or ""),
            owner_skill="quality-review",
            requested_action=action,
            candidate_paths=[
                "scripts/build_r5_bundle16r_case_pack.py",
                "tests/test_r5_bundle16r_case_pack_builder.py",
            ],
            acceptance_commands=[
                "python -m pytest -q tests/test_r5_bundle16r_case_pack_builder.py"
            ],
            generator_version="r5_night02_pointer_contract_v1",
        )
        proposal.update(
            {
                "case_id": case_id,
                "issuer_ticker": item.get("issuer_ticker"),
                "legacy_case_id": item.get("legacy_case_id"),
                "missing_pointer": missing_pointer,
                "observed_legacy_fields": observed_fields,
                "semantic_route": route["route"],
                "historical_artifact_read_only": True,
                "legacy_pointer_substitution_allowed": False,
            }
        )
        proposal["proposal_sha256"] = sha256_bytes(
            canonical_json_bytes(
                {
                    key: value
                    for key, value in proposal.items()
                    if key
                    not in {
                        "proposal_sha256",
                        "review_state",
                        "review_sha",
                        "reviewer",
                        "reviewed_at",
                        "decision",
                        "decision_notes",
                    }
                }
            )
        )
        proposals.append(proposal)
    return {
        "schema_version": "r5_night_shift_pointer_contract_proposals_v1",
        "proposal_count": len(proposals),
        "resolved_blocker_count": 0,
        "proposals": sorted(
            proposals, key=lambda child: (child["case_id"], child["missing_pointer"])
        ),
    }


def build_fallback_backlog() -> dict[str, Any]:
    tasks = [
        {
            "task_id": "ns02_t50_golden_case_inventory",
            "work_type": "analysis_automation",
            "ready_when": ["ns02_t00_exact_baseline_preflight:passed"],
        },
        {
            "task_id": "ns02_t51_semantic_quality_negative_fixtures",
            "work_type": "engineering",
            "ready_when": ["ns02_t50_golden_case_inventory:passed"],
        },
        {
            "task_id": "ns02_t52_driver_contract_gap_matrix",
            "work_type": "analysis_automation",
            "ready_when": ["ns02_t50_golden_case_inventory:passed"],
        },
        {
            "task_id": "ns02_t53_bundle18_readiness_precheck",
            "work_type": "engineering",
            "ready_when": [
                "ns02_t34_human_gate_handoffs:passed",
                "ns02_t43_bf2_dry_run_truth_preservation:passed",
            ],
        },
        {
            "task_id": "ns02_t54_next_mission_seed",
            "work_type": "engineering",
            "ready_when": [
                "ns02_t38_queue_metrics_and_capacity:passed",
                "ns02_t50_golden_case_inventory:passed",
            ],
        },
    ]
    return {
        "schema_version": "r5_night_shift_fallback_backlog_v1",
        "fallback_task_count": len(tasks),
        "no_ready_research_task_causes_exit": False,
        "tasks": tasks,
    }


def spawn_retry_task(
    task: Task,
    *,
    failure_type: str,
    max_spawn_depth: int = 2,
) -> Task:
    if failure_type in {"safety_violation", "authority_failure", "scope_violation"}:
        raise ContractError(f"{failure_type} is terminal and cannot spawn a retry")
    next_depth = task.spawn_depth + 1
    if next_depth > max_spawn_depth:
        raise ContractError("failure-spawn depth limit reached")
    retry_id = f"ns02_t37_retry_{_safe_suffix(task.id + ':' + str(next_depth))}"
    return replace(
        task,
        id=retry_id,
        title=f"Bounded retry for {task.id}",
        status="ready",
        depends_on=task.depends_on,
        spawn_depth=next_depth,
        parent_task_id=task.id,
        notes=task.notes + (f"failure_type={failure_type}",),
        resolution_claims=(),
    )


def _write_json(path: Path, value: Any) -> None:
    atomic_write(
        path,
        (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
            "utf-8"
        ),
    )


def _write_yaml(path: Path, value: Any) -> None:
    text = yaml.safe_dump(
        value,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=1000,
        line_break="\n",
    )
    atomic_write(path, text.encode("utf-8"))


def _write_packet_markdown(
    path: Path,
    *,
    title: str,
    count_label: str,
    count: int,
    rows: Sequence[Mapping[str, Any]],
) -> None:
    lines = [f"# {title}", "", f"- {count_label}: `{count}`", "- Auto-accept: `false`", ""]
    for row in rows:
        identifier = next(
            (
                row.get(key)
                for key in ("request_id", "worksheet_id", "task_id", "case_id")
                if row.get(key)
            ),
            "UNKNOWN",
        )
        lines.append(f"- `{identifier}` — `{row.get('case_id') or GLOBAL_CASE_ID}`")
    lines.append("")
    atomic_write(path, "\n".join(lines).encode("utf-8"))


def compile_backflow(
    *,
    repo_root: Path,
    output_dir: Path,
    source_commit: str,
) -> dict[str, Any]:
    occurrences = load_occurrences(repo_root)
    queue = build_occurrence_queue(occurrences, source_commit=source_commit)
    dag = build_dependency_dag(queue)
    evidence = build_evidence_requests(occurrences)
    analysis = build_analysis_workbooks(occurrences)
    human = build_human_handoffs(occurrences)
    pointers = build_pointer_proposals(repo_root)
    fallback = build_fallback_backlog()
    metrics = queue_metrics(queue)
    metrics.update(
        {
            "schema_version": "r5_night_shift_queue_metrics_v1",
            "classification_counts": dict(
                sorted(Counter(item["classification"] for item in occurrences).items())
            ),
            "work_orders_pending": 6,
            "blocker_occurrences_total": 63,
            "blocker_occurrences_resolved": 0,
            "fallback_ready_count": 1,
        }
    )
    summary: dict[str, Any] = {
        "schema_version": "r5_night_shift_bf2_expansion_receipt_v1",
        "source_commit": source_commit,
        "occurrence_task_count": 63,
        "parent_work_order_count": 6,
        "seeded_task_count": len(queue.tasks),
        "classification_counts": metrics["classification_counts"],
        "work_orders_pending": 6,
        "blocker_occurrences_total": 63,
        "blocker_occurrences_resolved": 0,
        "resolved_blocker_count": 0,
        "research_gate": "needs_targeted_backflow",
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
    summary["stable_receipt_sha256"] = sha256_bytes(canonical_json_bytes(summary))
    inventory = {
        "schema_version": "r5_night_shift_occurrence_inventory_v1",
        "source_path": BACKFLOW_QUEUE_PATH.as_posix(),
        "occurrence_count": len(occurrences),
        "classification_counts": metrics["classification_counts"],
        "resolved_blocker_count": 0,
        "occurrences": list(occurrences),
    }

    backflow_dir = output_dir / "backflow"
    _write_json(backflow_dir / "occurrence_inventory.json", inventory)
    save_queue(backflow_dir / "expanded_queue.yaml", queue)
    _write_json(backflow_dir / "dependency_dag.json", dag)
    _write_yaml(backflow_dir / "evidence_requests.yaml", evidence)
    _write_packet_markdown(
        backflow_dir / "evidence_requests.md",
        title="Bundle17R evidence request packets",
        count_label="Requests",
        count=evidence["request_count"],
        rows=evidence["requests"],
    )
    _write_yaml(backflow_dir / "analysis_workbooks.yaml", analysis)
    _write_packet_markdown(
        backflow_dir / "analysis_workbooks.md",
        title="Bundle17R analysis workbooks",
        count_label="Worksheets",
        count=analysis["worksheet_count"],
        rows=analysis["worksheets"],
    )
    _write_yaml(backflow_dir / "human_gate_handoffs.yaml", human)
    _write_yaml(backflow_dir / "pointer_contract_proposals.yaml", pointers)
    _write_packet_markdown(
        backflow_dir / "pointer_contract_proposals.md",
        title="Bundle17R pointer contract proposals",
        count_label="Proposals",
        count=pointers["proposal_count"],
        rows=pointers["proposals"],
    )
    _write_yaml(backflow_dir / "fallback_backlog.yaml", fallback)
    _write_json(backflow_dir / "queue_metrics.json", metrics)
    _write_json(backflow_dir / "expansion_receipt.json", summary)
    return summary
