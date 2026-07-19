"""Candidate closure and truthful blocker accounting for Night03."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from .night03 import (
    EXPECTED_QUEUE_SHA256,
    MISSION_ID,
    OUTPUT_ROOT,
    SOURCE_ROOT,
    Night03Error,
    authoritative_queue,
    load_json,
    load_yaml,
    sha256_file,
    stable_payload,
    write_json,
    write_yaml,
)
from .night03_decisions import validate_decision_manifest
from .night03_execution import note_fields
from .queue import atomic_write
from .receipts import canonical_json_bytes, sha256_bytes


BLOCKER_ID_RE = re.compile(r"(BF17R-I-[A-Za-z0-9]+)")


def packet_hash(packet: Mapping[str, Any]) -> str:
    projection = {key: value for key, value in packet.items() if key != "packet_sha256"}
    return sha256_bytes(canonical_json_bytes(projection))


def with_packet_hash(packet: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(packet)
    result["packet_sha256"] = packet_hash(result)
    return result


def blocker_id(task: Mapping[str, Any]) -> str:
    match = BLOCKER_ID_RE.search(str(task.get("title") or ""))
    if not match:
        raise Night03Error(f"cannot recover blocker occurrence ID from {task.get('id')}")
    return match.group(1)


def _source_yaml(repo_root: Path, relative: str) -> dict[str, Any]:
    return load_yaml(repo_root / SOURCE_ROOT / relative)


def _case_inventory(repo_root: Path) -> dict[str, dict[str, Any]]:
    payload = _source_yaml(repo_root, "strategic/golden_case_inventory.yaml")
    cases = payload.get("cases") or []
    if not isinstance(cases, list) or len(cases) != 4:
        raise Night03Error("Night02 golden case inventory must contain four cases")
    return {str(case["case_id"]): case for case in cases}


def _queue_maps(repo_root: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    tasks = authoritative_queue(repo_root)["tasks"]
    occurrences = [task for task in tasks if task.get("work_type") != "bf2_work_order"]
    by_blocker = {blocker_id(task): task for task in occurrences}
    if len(by_blocker) != 63:
        raise Night03Error("authoritative queue blocker IDs are not one-to-one")
    return tasks, by_blocker


def _lineage_candidates(case: Mapping[str, Any], repo_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for artifact in case.get("artifact_lineage") or []:
        path_value = str(artifact.get("path") or "")
        expected = str(artifact.get("physical_sha256") or "").casefold()
        path = repo_root / path_value
        actual = sha256_file(path) if path.is_file() else None
        records.append(
            {
                "role": artifact.get("role"),
                "path": path_value,
                "physical_sha256": expected or None,
                "hash_verified": bool(actual and actual == expected),
                "claim_evidence_status": "lineage_candidate_not_accepted_for_occurrence",
            }
        )
    return records


def build_evidence_candidates(repo_root: Path) -> dict[str, Any]:
    source = _source_yaml(repo_root, "backflow/evidence_requests.yaml")
    requests = source.get("requests") or []
    _, queue_by_blocker = _queue_maps(repo_root)
    cases = _case_inventory(repo_root)
    packets: list[dict[str, Any]] = []
    for request in requests:
        source_blocker = str(request["blocker_occurrence_id"])
        task = queue_by_blocker.get(source_blocker)
        if task is None or task.get("work_type") != "evidence_required":
            raise Night03Error(f"evidence request is not bound to authoritative queue: {source_blocker}")
        fields = note_fields(task)
        case = cases[str(request["case_id"])]
        packet = with_packet_hash(
            {
                "schema_version": "r5_night03_evidence_candidate_v1",
                "occurrence_id": task["id"],
                "blocker_occurrence_id": source_blocker,
                "case_id": request["case_id"],
                "issuer_ticker": request.get("issuer_ticker"),
                "field": request.get("field"),
                "status": "candidate_pending_review",
                "source_queue_sha256": EXPECTED_QUEUE_SHA256,
                "bound_source_artifact": {
                    "path": fields.get("source_artifact_path"),
                    "sha256": fields.get("source_artifact_sha256"),
                },
                "candidate_source_paths": _lineage_candidates(case, repo_root),
                "research_question": request.get("research_question"),
                "visible_gaps": [
                    "MISSING_REVIEWED_EVIDENCE_ACCEPTANCE",
                    "MISSING_PERIOD_UNIT_SOURCE_CLASS_AND_CLAIM_BOUNDARY_REVIEW",
                ],
                "acceptance_criteria": [
                    "physical source hash verified",
                    "evidence_id registered",
                    "source class reviewed",
                    "period unit and claim boundary explicit",
                    "counter-evidence reviewed",
                    "external reviewer decision exact-hash bound",
                ],
                "conflict_evidence": [],
                "conflict_evidence_status": "UNKNOWN_NOT_REVIEWED",
                "backflow_command": request.get("backflow_command"),
                "reviewer": None,
                "reviewed_at": None,
                "decision": None,
                "auto_accept_allowed": False,
            }
        )
        packets.append(packet)
    if len(packets) != 8:
        raise Night03Error(f"expected 8 evidence candidates, got {len(packets)}")
    return {
        "schema_version": "r5_night03_evidence_candidates_v1",
        "source_queue_sha256": EXPECTED_QUEUE_SHA256,
        "candidate_count": len(packets),
        "accepted_count": 0,
        "resolved_count": 0,
        "candidates": sorted(packets, key=lambda item: item["occurrence_id"]),
    }


def build_analysis_candidates(repo_root: Path) -> dict[str, Any]:
    source = _source_yaml(repo_root, "backflow/analysis_workbooks.yaml")
    worksheets = source.get("worksheets") or []
    _, queue_by_blocker = _queue_maps(repo_root)
    cases = _case_inventory(repo_root)
    packets: list[dict[str, Any]] = []
    for worksheet in worksheets:
        source_blocker = str(worksheet["blocker_occurrence_id"])
        task = queue_by_blocker.get(source_blocker)
        if task is None or task.get("work_type") != "analysis_required":
            raise Night03Error(f"analysis worksheet is not authoritative: {source_blocker}")
        fields = note_fields(task)
        case = cases[str(worksheet["case_id"])]
        packet = with_packet_hash(
            {
                "schema_version": "r5_night03_analysis_candidate_v1",
                "occurrence_id": task["id"],
                "blocker_occurrence_id": source_blocker,
                "case_id": worksheet["case_id"],
                "issuer_ticker": worksheet.get("issuer_ticker"),
                "company": case.get("company"),
                "economic_archetype": case.get("economic_archetype"),
                "field": worksheet.get("field"),
                "status": "candidate_pending_review",
                "source_queue_sha256": EXPECTED_QUEUE_SHA256,
                "company_specific_question": worksheet.get("question"),
                "evidence_mapping": [
                    {
                        "role": "bound_failure_source",
                        "path": fields.get("source_artifact_path"),
                        "sha256": fields.get("source_artifact_sha256"),
                        "status": "verified_lineage_not_accepted_conclusion_evidence",
                    },
                    *_lineage_candidates(case, repo_root),
                ],
                "candidate_conclusion": "UNKNOWN_PENDING_EXTERNAL_ANALYST_REVIEW",
                "causal_chain": [
                    "business_driver_UNKNOWN",
                    "operating_metric_UNKNOWN",
                    "financial_effect_UNKNOWN",
                    "valuation_or_quality_link_UNKNOWN",
                ],
                "quantitative_bridge": {
                    "period": "MISSING",
                    "unit": "MISSING",
                    "input_metrics": [],
                    "calculation_method": "MISSING",
                    "result": "MISSING",
                },
                "counter_evidence": ["MISSING_REVIEWED_COUNTER_EVIDENCE"],
                "unknowns": [
                    str(worksheet.get("required_evidence") or "MISSING_REQUIRED_EVIDENCE"),
                    "MISSING_REVIEWED_ANALYST_CONCLUSION",
                ],
                "model_link": worksheet.get("model_link"),
                "falsification_condition": worksheet.get("falsification_condition"),
                "reviewer_checklist": [
                    "evidence IDs and source hashes match",
                    "causal chain is company-specific",
                    "quantitative bridge includes period unit and method",
                    "counter-evidence and unknowns remain visible",
                    "decision binds this packet SHA-256",
                ],
                "reviewer": None,
                "reviewed_at": None,
                "decision": None,
                "auto_judgment_allowed": False,
            }
        )
        packets.append(packet)
    if len(packets) != 24:
        raise Night03Error(f"expected 24 analysis candidates, got {len(packets)}")
    return {
        "schema_version": "r5_night03_analysis_candidates_v1",
        "source_queue_sha256": EXPECTED_QUEUE_SHA256,
        "candidate_count": len(packets),
        "accepted_count": 0,
        "resolved_count": 0,
        "candidates": sorted(packets, key=lambda item: item["occurrence_id"]),
    }


def _walk_key_values(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    result: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            result.append((path, child))
            result.extend(_walk_key_values(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.extend(_walk_key_values(child, f"{prefix}[{index}]"))
    return result


def build_human_handoffs(repo_root: Path) -> dict[str, Any]:
    source = _source_yaml(repo_root, "backflow/human_gate_handoffs.yaml")
    handoffs = source.get("handoffs") or []
    _, queue_by_blocker = _queue_maps(repo_root)
    packets: list[dict[str, Any]] = []
    for handoff in handoffs:
        source_blocker = str(handoff["blocker_occurrence_id"])
        task = queue_by_blocker.get(source_blocker)
        if task is None or task.get("work_type") != "human_gate":
            raise Night03Error(f"human handoff is not authoritative: {source_blocker}")
        candidate_path = repo_root / str(handoff["candidate_artifact"])
        expected = str(handoff["candidate_sha256"]).casefold()
        actual = sha256_file(candidate_path) if candidate_path.is_file() else None
        if actual != expected:
            raise Night03Error(f"human handoff candidate hash mismatch: {source_blocker}")
        structured = (
            json.loads(candidate_path.read_text(encoding="utf-8"))
            if candidate_path.suffix.casefold() == ".json"
            else yaml.safe_load(candidate_path.read_text(encoding="utf-8"))
        )
        values = _walk_key_values(structured)
        generation_ids = sorted(
            {str(value) for path, value in values if path.endswith("generation_id") and value}
        )
        quality_booleans = {
            path: value
            for path, value in values
            if isinstance(value, bool)
            and any(token in path.casefold() for token in ("quality", "allowed", "eligible", "ready"))
        }
        packets.append(
            with_packet_hash(
                {
                    "schema_version": "r5_night03_human_gate_handoff_v1",
                    "occurrence_id": task["id"],
                    "blocker_occurrence_id": source_blocker,
                    "case_id": handoff.get("case_id"),
                    "status": "candidate_pending_review",
                    "candidate_artifact_path": handoff["candidate_artifact"],
                    "candidate_artifact_sha256": expected,
                    "generation_ids": generation_ids,
                    "quality_booleans": quality_booleans,
                    "validation_checklist": handoff.get("validation_checklist") or [],
                    "reviewer": None,
                    "reviewed_at": None,
                    "decision": None,
                    "auto_accept_allowed": False,
                }
            )
        )
    if len(packets) != 3:
        raise Night03Error(f"expected 3 human handoffs, got {len(packets)}")
    return {
        "schema_version": "r5_night03_human_gate_handoffs_v1",
        "source_queue_sha256": EXPECTED_QUEUE_SHA256,
        "handoff_count": len(packets),
        "approved_count": 0,
        "resolved_count": 0,
        "handoffs": sorted(packets, key=lambda item: item["occurrence_id"]),
    }


def _pointer_key(task: Mapping[str, Any]) -> tuple[str, str]:
    fields = note_fields(task)
    field = fields.get("field") or ""
    pointer = "/generation_id" if "generation_id_present" in field else "/candidate_ready_for_exact_hash_review"
    return fields.get("case_id") or "", pointer


def build_pointer_index(repo_root: Path) -> dict[str, Any]:
    source = _source_yaml(repo_root, "backflow/pointer_contract_proposals.yaml")
    proposals = source.get("proposals") or []
    tasks, _ = _queue_maps(repo_root)
    engineering = [task for task in tasks if task.get("work_type") == "engineering_local"]
    proposal_map = {
        (str(item.get("case_id") or ""), str(item.get("missing_pointer") or "")): item
        for item in proposals
    }
    packets: list[dict[str, Any]] = []
    for task in engineering:
        key = _pointer_key(task)
        proposal = proposal_map.get(key)
        if proposal is None:
            raise Night03Error(f"pointer proposal missing for {task['id']}: {key}")
        exact_paths = list(proposal.get("candidate_paths") or [])
        commands = list(proposal.get("acceptance_commands") or [])
        packet = with_packet_hash(
            {
                "schema_version": "r5_night03_pointer_review_index_item_v1",
                "occurrence_id": task["id"],
                "blocker_occurrence_id": blocker_id(task),
                "case_id": key[0],
                "issuer_ticker": proposal.get("issuer_ticker"),
                "missing_pointer": key[1],
                "status": "candidate_pending_review",
                "source_artifact": proposal.get("source_artifact"),
                "source_proposal_sha256": proposal.get("proposal_sha256"),
                "exact_paths": exact_paths,
                "acceptance_commands": commands,
                "acceptance_command_sha256": {
                    command: sha256_bytes(str(command).encode("utf-8")) for command in commands
                },
                "diff_ceiling": {
                    "allowed_paths": exact_paths,
                    "max_changed_paths": len(exact_paths),
                },
                "risks": [
                    "pointer alias can hide an upstream semantic contract gap",
                    "approved child diff must remain a strict subset of exact paths",
                    "historical Bundle17R artifacts remain read-only",
                ],
                "review_state": "proposed",
                "review_sha": None,
                "reviewer": None,
                "reviewed_at": None,
                "decision": None,
                "resolution_claim_allowed": False,
            }
        )
        packets.append(packet)
    if len(packets) != 8:
        raise Night03Error(f"expected 8 pointer proposals, got {len(packets)}")
    return {
        "schema_version": "r5_night03_pointer_review_index_v1",
        "source_queue_sha256": EXPECTED_QUEUE_SHA256,
        "proposal_count": len(packets),
        "approved_count": 0,
        "resolved_count": 0,
        "max_tasks_per_wave": 2,
        "proposals": sorted(packets, key=lambda item: item["occurrence_id"]),
    }


def build_dependency_matrix(repo_root: Path) -> dict[str, Any]:
    tasks = authoritative_queue(repo_root)["tasks"]
    task_map = {str(task["id"]): task for task in tasks}
    required_authority = {
        "engineering_local": "pointer_contract_approval + execution_receipt",
        "evidence_required": "evidence_acceptance + acceptance_receipt",
        "analysis_required": "analysis_acceptance + acceptance_receipt",
        "human_gate": "human_exact_hash + acceptance_receipt",
        "dependency_blocked": "upstream_dependency_resolution_receipt",
    }
    rows: list[dict[str, Any]] = []
    for task in tasks:
        if task.get("work_type") != "dependency_blocked":
            continue
        prerequisites = [str(item) for item in task.get("depends_on") or []]
        rows.append(
            with_packet_hash(
                {
                    "schema_version": "r5_night03_dependency_unlock_item_v1",
                    "occurrence_id": task["id"],
                    "blocker_occurrence_id": blocker_id(task),
                    "case_id": note_fields(task).get("case_id"),
                    "current_status": "dependency_blocked",
                    "prerequisites": [
                        {
                            "occurrence_id": item,
                            "work_type": task_map[item]["work_type"],
                            "required_decision_or_receipt": required_authority[
                                task_map[item]["work_type"]
                            ],
                            "current_status": task_map[item]["status"],
                            "resolved": False,
                        }
                        for item in prerequisites
                    ],
                    "unresolved_prerequisite_count": len(prerequisites),
                    "non_substitutable_condition": "every prerequisite needs an independent lineage-matched resolution receipt",
                    "shortest_unlock_path": prerequisites,
                    "unlocked": False,
                }
            )
        )
    if len(rows) != 20:
        raise Night03Error(f"expected 20 dependency rows, got {len(rows)}")
    return {
        "schema_version": "r5_night03_dependency_unlock_matrix_v1",
        "source_queue_sha256": EXPECTED_QUEUE_SHA256,
        "dependency_count": len(rows),
        "unlocked_count": 0,
        "dependencies": sorted(rows, key=lambda item: item["occurrence_id"]),
    }


def build_four_case_dashboard(repo_root: Path) -> dict[str, Any]:
    tasks = authoritative_queue(repo_root)["tasks"]
    cases = _case_inventory(repo_root)
    rows: list[dict[str, Any]] = []
    for case_id, case in cases.items():
        occurrences = [
            task
            for task in tasks
            if task.get("work_type") != "bf2_work_order"
            and note_fields(task).get("case_id") == case_id
        ]
        counts = Counter(str(task["work_type"]) for task in occurrences)
        parents = [
            task["id"]
            for task in tasks
            if task.get("work_type") == "bf2_work_order"
            and note_fields(task).get("case_id") == case_id
        ]
        rows.append(
            {
                "case_id": case_id,
                "ticker": case.get("ticker"),
                "company": case.get("company"),
                "economic_archetype": case.get("economic_archetype"),
                "occurrence_count": len(occurrences),
                "candidate_ready_count": sum(
                    counts.get(key, 0)
                    for key in (
                        "engineering_local",
                        "evidence_required",
                        "analysis_required",
                        "human_gate",
                    )
                ),
                "approved_count": 0,
                "resolved_count": 0,
                "dependency_blocked_count": counts.get("dependency_blocked", 0),
                "work_type_counts": dict(sorted(counts.items())),
                "parent_work_order_ids": parents,
                "next_actions": [
                    "external reviewers decide exact-hash candidate packets",
                    "independent acceptance receipts resolve occurrences",
                    "dependency matrix recomputes only after real receipts",
                ],
            }
        )
    return {
        "schema_version": "r5_night03_four_case_dashboard_v1",
        "source_queue_sha256": EXPECTED_QUEUE_SHA256,
        "case_count": len(rows),
        "score_aggregation_used": False,
        "cases": rows,
        "suite_level_occurrences": sum(
            task.get("work_type") != "bf2_work_order"
            and note_fields(task).get("case_id") == "__suite__"
            for task in tasks
        ),
    }


def build_blocker_ledger(repo_root: Path) -> dict[str, Any]:
    tasks = authoritative_queue(repo_root)["tasks"]
    rows: list[dict[str, Any]] = []
    for task in tasks:
        if task.get("work_type") == "bf2_work_order":
            continue
        work_type = str(task["work_type"])
        status = "dependency_blocked" if work_type == "dependency_blocked" else "candidate_ready"
        rows.append(
            {
                "occurrence_id": task["id"],
                "blocker_occurrence_id": blocker_id(task),
                "case_id": note_fields(task).get("case_id"),
                "work_type": work_type,
                "status": status,
                "external_gate": "blocked_external" if status == "candidate_ready" else None,
                "resolved": False,
                "resolution_receipt_sha256": None,
            }
        )
    counts = Counter(row["status"] for row in rows)
    if len(rows) != 63 or counts != Counter({"candidate_ready": 43, "dependency_blocked": 20}):
        raise Night03Error(f"unexpected blocker ledger counts: {counts}")
    return stable_payload(
        {
            "schema_version": "r5_night03_blocker_ledger_v1",
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "blocker_occurrences_total": 63,
            "blocker_occurrences_resolved_start": 0,
            "blocker_occurrences_resolved_end": 0,
            "resolved_delta": 0,
            "status_counts": dict(sorted(counts.items())),
            "external_decision_pending_count": 43,
            "parent_work_orders_total": 6,
            "parent_work_orders_resolved": 0,
            "program_goal_state": "open_needs_targeted_backflow",
            "sample_quality_allowed": False,
            "p2_allowed": False,
            "occurrences": sorted(rows, key=lambda item: item["occurrence_id"]),
        }
    )


def _simple_markdown(title: str, count_label: str, count: int, rows: Sequence[str]) -> str:
    return "\n".join([f"# {title}", "", f"- {count_label}: `{count}`", "", *rows, ""])


def materialize_candidate_closure(repo_root: Path) -> dict[str, Any]:
    evidence = build_evidence_candidates(repo_root)
    analysis = build_analysis_candidates(repo_root)
    human = build_human_handoffs(repo_root)
    pointer = build_pointer_index(repo_root)
    dependency = build_dependency_matrix(repo_root)
    dashboard = build_four_case_dashboard(repo_root)
    ledger = build_blocker_ledger(repo_root)
    root = repo_root / OUTPUT_ROOT
    write_yaml(root / "candidates/evidence_candidates.yaml", evidence)
    atomic_write(
        root / "candidates/evidence_candidates.md",
        _simple_markdown(
            "Night03 Evidence Candidates",
            "Candidate count",
            evidence["candidate_count"],
            [
                f"- `{item['occurrence_id']}` — `{item['case_id']}` — `candidate_pending_review`"
                for item in evidence["candidates"]
            ],
        ).encode("utf-8"),
    )
    write_yaml(root / "candidates/analysis_candidates.yaml", analysis)
    atomic_write(
        root / "candidates/analysis_candidates.md",
        _simple_markdown(
            "Night03 Analysis Candidates",
            "Candidate count",
            analysis["candidate_count"],
            [
                f"- `{item['occurrence_id']}` — {item['company']} — `{item['candidate_conclusion']}`"
                for item in analysis["candidates"]
            ],
        ).encode("utf-8"),
    )
    write_yaml(root / "candidates/human_gate_handoffs.yaml", human)
    atomic_write(
        root / "candidates/human_gate_handoffs.md",
        _simple_markdown(
            "Night03 Human Gate Handoffs",
            "Handoff count",
            human["handoff_count"],
            [
                f"- `{item['occurrence_id']}` — `{item['candidate_artifact_path']}` — reviewer `MISSING`"
                for item in human["handoffs"]
            ],
        ).encode("utf-8"),
    )
    write_yaml(root / "candidates/pointer_review_index.yaml", pointer)
    atomic_write(
        root / "candidates/pointer_review_index.md",
        _simple_markdown(
            "Night03 Pointer Review Index",
            "Proposal count",
            pointer["proposal_count"],
            [
                f"- `{item['occurrence_id']}` — `{item['missing_pointer']}` — `proposed`"
                for item in pointer["proposals"]
            ],
        ).encode("utf-8"),
    )
    write_yaml(root / "candidates/dependency_unlock_matrix.yaml", dependency)
    atomic_write(
        root / "candidates/dependency_unlock_matrix.md",
        _simple_markdown(
            "Night03 Dependency Unlock Matrix",
            "Dependency count",
            dependency["dependency_count"],
            [
                f"- `{item['occurrence_id']}` — {item['unresolved_prerequisite_count']} unresolved prerequisites"
                for item in dependency["dependencies"]
            ],
        ).encode("utf-8"),
    )
    write_yaml(root / "progress/four_case_dashboard.yaml", dashboard)
    dashboard_rows = [
        "| company | case | occurrences | candidates | dependencies | resolved |",
        "|---|---|---:|---:|---:|---:|",
        *[
            f"| {item['company']} | `{item['case_id']}` | {item['occurrence_count']} | {item['candidate_ready_count']} | {item['dependency_blocked_count']} | {item['resolved_count']} |"
            for item in dashboard["cases"]
        ],
    ]
    atomic_write(
        root / "progress/four_case_dashboard.md",
        _simple_markdown(
            "Night03 Four-case Dashboard", "Case count", dashboard["case_count"], dashboard_rows
        ).encode("utf-8"),
    )
    write_json(root / "progress/blocker_ledger.json", ledger)
    atomic_write(
        root / "progress/blocker_ledger.md",
        _simple_markdown(
            "Night03 Blocker Ledger",
            "Resolved",
            ledger["blocker_occurrences_resolved_end"],
            [
                "- Total blocker occurrences: `63`",
                "- Candidate ready: `43` (all still externally gated)",
                "- Dependency blocked: `20`",
                "- Resolved delta: `0`",
                "- Program Goal: `open_needs_targeted_backflow`",
            ],
        ).encode("utf-8"),
    )
    return {
        "evidence": evidence,
        "analysis": analysis,
        "human": human,
        "pointer": pointer,
        "dependency": dependency,
        "dashboard": dashboard,
        "ledger": ledger,
    }


def consume_approved_inputs(
    repo_root: Path, *, continue_on_external_block: bool
) -> dict[str, Any]:
    decision_root = repo_root / OUTPUT_ROOT / "external_decisions"
    files = (
        sorted(
            [
                path
                for path in decision_root.iterdir()
                if path.is_file() and path.suffix.casefold() in {".yaml", ".yml", ".json"}
            ]
        )
        if decision_root.is_dir()
        else []
    )
    decisions: list[dict[str, Any]] = []
    manifests: list[dict[str, Any]] = []
    for path in files:
        raw = (
            json.loads(path.read_text(encoding="utf-8"))
            if path.suffix.casefold() == ".json"
            else yaml.safe_load(path.read_text(encoding="utf-8"))
        )
        if not isinstance(raw, dict):
            raise Night03Error(f"external decision manifest is not a mapping: {path}")
        validated = validate_decision_manifest(repo_root, raw)
        manifests.append(
            {
                "path": path.relative_to(repo_root).as_posix(),
                "sha256": sha256_file(path),
                "decision_count": validated["decision_count"],
            }
        )
        decisions.extend(validated["decisions"])
    approved = [item for item in decisions if item.get("decision") == "approved"]
    outcome = (
        "no_approved_inputs"
        if not approved
        else "validated_approved_inputs_pending_independent_acceptance_receipts"
    )
    payload = stable_payload(
        {
            "schema_version": "r5_night03_approved_input_consumption_v1",
            "mission_id": MISSION_ID,
            "source_queue_sha256": EXPECTED_QUEUE_SHA256,
            "scanned_manifest_count": len(files),
            "manifests": manifests,
            "validated_decision_count": len(decisions),
            "approved_decision_count": len(approved),
            "consumed_count": len(approved),
            "resolved_delta": 0,
            "outcome": outcome,
            "continue_on_external_block": continue_on_external_block,
            "program_goal_state": "open_needs_targeted_backflow",
        }
    )
    write_json(repo_root / OUTPUT_ROOT / "execution/approved_input_consumption.json", payload)
    if not approved and not continue_on_external_block:
        raise Night03Error("no approved external inputs are available")
    return payload
