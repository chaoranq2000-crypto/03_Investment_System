"""Truth-preserving BF2 dry-run and deterministic double-run validation."""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Mapping

import yaml

from .backflow import (
    build_analysis_workbooks,
    build_dependency_dag,
    build_evidence_requests,
    build_fallback_backlog,
    build_human_handoffs,
    build_occurrence_queue,
    build_pointer_proposals,
    load_occurrences,
)
from .outcome import queue_metrics
from .queue import atomic_write, queue_bytes
from .readout import build_morning_payload, build_next_queue, markdown_bytes
from .receipts import canonical_json_bytes, sha256_bytes


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )


def _yaml_bytes(value: Any) -> bytes:
    return yaml.safe_dump(
        value,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=1000,
        line_break="\n",
    ).encode("utf-8")


def _write_json(path: Path, value: Any) -> None:
    atomic_write(path, _json_bytes(value))


def _historical_worktree_changes(repo_root: Path) -> list[str]:
    pathspecs = [
        "reports/p1_6/r5_bundle17r",
        "reports/workflow_runs/wf_20260715_stock_first_301217_tongguan_copper_foil/bundle16r/generated",
        "reports/workflow_runs/wf_20260715_stock_first_603259_wuxi_apptec/bundle16r/generated",
        "reports/workflow_runs/wf_20260715_stock_first_600988_chifeng_gold/bundle16r/generated",
        "reports/workflow_runs/wf_20260715_stock_first_600673_hec_tech/bundle16r/generated",
    ]
    changed: set[str] = set()
    for cached in (False, True):
        argv = ["git", "-C", str(repo_root), "diff"]
        if cached:
            argv.append("--cached")
        argv.extend(["--name-only", "--", *pathspecs])
        completed = subprocess.run(
            argv,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        changed.update(line.replace("\\", "/") for line in completed.stdout.splitlines())
    return sorted(item for item in changed if item)


def build_bf2_dry_run_receipt(
    *, repo_root: Path, source_commit: str, output_path: Path
) -> dict[str, Any]:
    occurrences = load_occurrences(repo_root)
    queue = build_occurrence_queue(occurrences, source_commit=source_commit)
    dag = build_dependency_dag(queue)
    evidence = build_evidence_requests(occurrences)
    analysis = build_analysis_workbooks(occurrences)
    human = build_human_handoffs(occurrences)
    pointers = build_pointer_proposals(repo_root)
    historical_changes = _historical_worktree_changes(repo_root)
    payload: dict[str, Any] = {
        "schema_version": "r5_night_shift_bf2_dry_run_receipt_v1",
        "mode": "read_only",
        "source_commit": source_commit,
        "occurrence_count": len(occurrences),
        "parent_work_order_count": len(queue.tasks) - len(occurrences),
        "seeded_task_count": len(queue.tasks),
        "classification_counts": dict(
            sorted(Counter(str(item["classification"]) for item in occurrences).items())
        ),
        "dependency_edge_count": int(dag["edge_count"]),
        "evidence_request_count": int(evidence["request_count"]),
        "analysis_worksheet_count": int(analysis["worksheet_count"]),
        "human_handoff_count": int(human["handoff_count"]),
        "pointer_proposal_count": int(pointers["proposal_count"]),
        "blocker_occurrences_resolved": 0,
        "classification_is_resolution": False,
        "historical_mutations": historical_changes,
        "historical_inputs_unchanged": not historical_changes,
        "research_gate": "needs_targeted_backflow",
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
    payload["stable_receipt_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    _write_json(output_path, payload)
    return payload


def _deterministic_payloads(
    repo_root: Path, *, source_commit: str
) -> dict[str, bytes]:
    occurrences = load_occurrences(repo_root)
    queue = build_occurrence_queue(occurrences, source_commit=source_commit)
    dag = build_dependency_dag(queue)
    evidence = build_evidence_requests(occurrences)
    analysis = build_analysis_workbooks(occurrences)
    human = build_human_handoffs(occurrences)
    pointers = build_pointer_proposals(repo_root)
    fallback = build_fallback_backlog()
    metrics = queue_metrics(queue)
    inventory = {
        "classification_counts": dict(
            sorted(Counter(str(item["classification"]) for item in occurrences).items())
        ),
        "occurrences": occurrences,
    }
    next_queue = build_next_queue(inventory, source_commit=source_commit)
    morning = build_morning_payload(
        run_id="r5_overnight_02_20260720",
        baseline={
            "source_branch": "codex/r5-night01-autonomous-harness",
            "expected_source_sha": "4340945457d661ed62967e949f862ccf2214aff2",
        },
        mission_state=queue,
        seed_receipt={
            "work_orders_pending": 6,
            "blocker_occurrences_resolved": 0,
            "blocker_occurrences_total": 63,
        },
        validation_receipt={"commands": []},
        determinism_receipt={
            "all_byte_for_byte_equal": True,
            "comparisons": [],
            "stable_receipt_sha256": "0" * 64,
        },
        scope_audit={
            "forbidden_paths_changed": 0,
            "tracked_local_runtime_outputs": 0,
            "tracked_bf2_run_outputs": 0,
            "scope_guard_pass": True,
        },
        branch={
            "target_branch": "codex/r5-night02-contract-recovery",
            "local_sha": source_commit,
            "remote_sha": source_commit,
            "remote_sha_equals_local": True,
            "commits": [],
        },
        next_queue=next_queue,
    )
    return {
        "expanded_queue.yaml": queue_bytes(queue),
        "dependency_dag.json": _json_bytes(dag),
        "evidence_requests.yaml": _yaml_bytes(evidence),
        "analysis_workbooks.yaml": _yaml_bytes(analysis),
        "human_gate_handoffs.yaml": _yaml_bytes(human),
        "pointer_contract_proposals.yaml": _yaml_bytes(pointers),
        "fallback_backlog.yaml": _yaml_bytes(fallback),
        "queue_metrics.json": _json_bytes(metrics),
        "morning_readout.md": markdown_bytes(morning),
        "next_night_queue.yaml": queue_bytes(next_queue),
    }


def build_determinism_receipt(
    *, repo_root: Path, source_commit: str, output_path: Path
) -> dict[str, Any]:
    first = _deterministic_payloads(repo_root, source_commit=source_commit)
    second = _deterministic_payloads(repo_root, source_commit=source_commit)
    comparisons = []
    for artifact in sorted(first):
        left = first[artifact]
        right = second[artifact]
        comparisons.append(
            {
                "artifact": artifact,
                "first_sha256": sha256_bytes(left),
                "second_sha256": sha256_bytes(right),
                "byte_for_byte_equal": left == right,
            }
        )
    payload: dict[str, Any] = {
        "schema_version": "r5_night_shift_determinism_receipt_v2",
        "source_commit": source_commit,
        "comparisons": comparisons,
        "all_byte_for_byte_equal": all(
            item["byte_for_byte_equal"] for item in comparisons
        ),
    }
    payload["stable_receipt_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    if not payload["all_byte_for_byte_equal"]:
        raise AssertionError("Night02 deterministic double run produced divergent bytes")
    _write_json(output_path, payload)
    return payload
