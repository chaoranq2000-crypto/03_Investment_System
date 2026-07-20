"""Night04 review acceleration, ranking, briefs, and dashboards."""

from __future__ import annotations

import html
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from .night03 import load_yaml, stable_payload, write_yaml
from .night04 import OUTPUT_ROOT, _note_fields, authoritative_queue
from .night04_review import EXPECTED_KIND_COUNTS, _candidate_items
from .queue import atomic_write


def _registry(repo_root: Path) -> dict[str, Any]:
    return load_yaml(repo_root / OUTPUT_ROOT / "review_control/candidate_registry.yaml")


def _candidate_memberships(repo_root: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    tasks = authoritative_queue(repo_root)["tasks"]
    by_id = {str(task["id"]): task for task in tasks}
    dependencies = [task for task in tasks if task.get("work_type") == "dependency_blocked"]
    parents = [task for task in tasks if task.get("work_type") == "bf2_work_order"]
    return by_id, dependencies, parents


def _reachable_parents(start: str, tasks: Sequence[Mapping[str, Any]]) -> list[str]:
    reverse: dict[str, list[str]] = defaultdict(list)
    by_id = {str(task["id"]): task for task in tasks}
    for task in tasks:
        for dep in task.get("depends_on") or []:
            reverse[str(dep)].append(str(task["id"]))
    seen: set[str] = set()
    stack = list(reverse.get(start, []))
    parents: set[str] = set()
    while stack:
        item = stack.pop()
        if item in seen:
            continue
        seen.add(item)
        task = by_id[item]
        if task.get("work_type") == "bf2_work_order":
            parents.add(item)
        stack.extend(reverse.get(item, []))
    return sorted(parents)


def build_unblock_leverage(repo_root: Path) -> dict[str, Any]:
    registry = _registry(repo_root)
    tasks = authoritative_queue(repo_root)["tasks"]
    _, dependencies, parents = _candidate_memberships(repo_root)
    rankings: list[dict[str, Any]] = []
    for candidate in registry["candidates"]:
        occurrence_id = str(candidate["occurrence_id"])
        dependency_ids = sorted(
            str(task["id"])
            for task in dependencies
            if occurrence_id in {str(dep) for dep in task.get("depends_on") or []}
        )
        direct_parent_ids = sorted(
            str(task["id"])
            for task in parents
            if occurrence_id in {str(dep) for dep in task.get("depends_on") or []}
        )
        reachable_parent_ids = _reachable_parents(occurrence_id, tasks)
        score = 100 * len(dependency_ids) + 25 * len(reachable_parent_ids) + 10 * len(direct_parent_ids)
        rankings.append(
            {
                "occurrence_id": occurrence_id,
                "case_id": candidate["case_id"],
                "candidate_kind": candidate["candidate_kind"],
                "unblock_leverage_score": score,
                "dependency_membership_count": len(dependency_ids),
                "dependency_ids": dependency_ids,
                "direct_parent_ids": direct_parent_ids,
                "reachable_parent_ids": reachable_parent_ids,
                "interpretation": "engineering_review_priority_only_not_research_confidence",
            }
        )
    rankings.sort(key=lambda item: (-int(item["unblock_leverage_score"]), str(item["occurrence_id"])))
    for index, item in enumerate(rankings, start=1):
        item["rank"] = index
    return stable_payload(
        {
            "schema_version": "r5_night04_unblock_leverage_v1",
            "candidate_count": len(rankings),
            "score_formula": "100*dependency_memberships + 25*reachable_parents + 10*direct_parents",
            "resolution_effect": "none_without_external_decision_and_independent_receipt",
            "rankings": rankings,
        }
    )


def _candidate_closure(task_id: str, by_id: Mapping[str, Mapping[str, Any]], candidate_ids: set[str]) -> set[str]:
    if task_id in candidate_ids:
        return {task_id}
    task = by_id.get(task_id)
    if task is None:
        return set()
    result: set[str] = set()
    for dep in task.get("depends_on") or []:
        result |= _candidate_closure(str(dep), by_id, candidate_ids)
    return result


def build_first_parent_path(repo_root: Path, leverage: Mapping[str, Any]) -> dict[str, Any]:
    by_id, _, parents = _candidate_memberships(repo_root)
    candidate_ids = {str(item["occurrence_id"]) for item in leverage["rankings"]}
    rank = {str(item["occurrence_id"]): int(item["rank"]) for item in leverage["rankings"]}
    options: list[dict[str, Any]] = []
    for parent in parents:
        notes = _note_fields(parent)
        if notes.get("case_id") in {None, "__suite__"}:
            continue
        required = _candidate_closure(str(parent["id"]), by_id, candidate_ids)
        options.append(
            {
                "parent_id": str(parent["id"]),
                "source_work_order_id": notes.get("source_work_order_id"),
                "case_id": notes.get("case_id"),
                "candidate_count": len(required),
                "candidate_ids": sorted(required, key=lambda item: (rank[item], item)),
            }
        )
    options.sort(key=lambda item: (int(item["candidate_count"]), sum(rank[item] for item in item["candidate_ids"]), str(item["parent_id"])))
    selected = options[0]
    return stable_payload(
        {
            "schema_version": "r5_night04_first_parent_path_v1",
            "selected_parent": selected,
            "parent_options": options,
            "completion_rule": "all_atomic_occurrences_require_independent_passed_receipts",
            "simulation_only": True,
        }
    )


def build_max_unlock_path(repo_root: Path, leverage: Mapping[str, Any]) -> dict[str, Any]:
    ordered = sorted(
        leverage["rankings"],
        key=lambda item: (-int(item["dependency_membership_count"]), int(item["rank"]), str(item["occurrence_id"])),
    )
    covered: set[str] = set()
    steps: list[dict[str, Any]] = []
    for item in ordered:
        new = sorted(set(item["dependency_ids"]) - covered)
        covered.update(item["dependency_ids"])
        steps.append(
            {
                "step": len(steps) + 1,
                "occurrence_id": item["occurrence_id"],
                "new_dependency_memberships": new,
                "cumulative_dependency_memberships": len(covered),
                "actual_dependencies_unlocked": 0,
            }
        )
    return stable_payload(
        {
            "schema_version": "r5_night04_max_unlock_path_v1",
            "candidate_count": len(steps),
            "dependency_universe_count": len(covered),
            "steps": steps,
            "simulation_only": True,
            "warning": "membership coverage is not resolution; every dependency requires all prerequisite receipts",
        }
    )


def build_review_groups(repo_root: Path) -> dict[str, Any]:
    registry = _registry(repo_root)
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for item in registry["candidates"]:
        grouped[(str(item["case_id"]), str(item["candidate_kind"]))].append(str(item["occurrence_id"]))
    groups = [
        {
            "case_id": case_id,
            "candidate_kind": kind,
            "count": len(ids),
            "occurrence_ids": sorted(ids),
        }
        for (case_id, kind), ids in sorted(grouped.items())
    ]
    return stable_payload(
        {
            "schema_version": "r5_night04_review_groups_v1",
            "candidate_count": sum(item["count"] for item in groups),
            "group_count": len(groups),
            "groups": groups,
        }
    )


def _candidate_source_map(repo_root: Path) -> dict[str, dict[str, Any]]:
    return {
        str(item["candidate"]["occurrence_id"]): {
            "kind": item["candidate_kind"],
            "candidate": item["candidate"],
        }
        for item in _candidate_items(repo_root)
    }


def _subject_summary(kind: str, candidate: Mapping[str, Any]) -> dict[str, Any]:
    if kind == "evidence_required":
        return {
            "subject": candidate.get("field"),
            "evidence_links": candidate.get("candidate_source_paths") or [],
            "proposed_review": candidate.get("acceptance_criteria") or [],
            "automatic_change": "none",
        }
    if kind == "analysis_required":
        return {
            "subject": candidate.get("field"),
            "candidate_conclusion": candidate.get("candidate_conclusion"),
            "causal_chain": candidate.get("causal_chain") or [],
            "quantitative_bridge": candidate.get("quantitative_bridge") or {},
            "falsification_condition": candidate.get("falsification_condition"),
        }
    if kind == "human_exact_hash_gate":
        return {
            "subject": "human_exact_hash_gate",
            "generation_ids": candidate.get("generation_ids") or [],
            "quality_booleans": candidate.get("quality_booleans") or {},
            "automatic_change": "none",
        }
    return {
        "subject": candidate.get("missing_pointer"),
        "exact_paths": candidate.get("exact_paths") or [],
        "acceptance_commands": candidate.get("acceptance_commands") or [],
        "automatic_change": "dry_run_only_without_external_approval",
    }


def build_review_briefs(repo_root: Path, leverage: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    registry = _registry(repo_root)
    source = _candidate_source_map(repo_root)
    rank = {str(item["occurrence_id"]): item for item in leverage["rankings"]}
    by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in registry["candidates"]:
        occurrence_id = str(entry["occurrence_id"])
        source_item = source[occurrence_id]
        brief = {
            "occurrence_id": occurrence_id,
            "parent_id": entry["parent_id"],
            "case_id": entry["case_id"],
            "candidate_kind": entry["candidate_kind"],
            "candidate_sha256": entry["candidate_sha256"],
            "review_packet_path": entry["review_packet_path"],
            "review_packet_sha256": entry["review_packet_sha256"],
            "rank": rank[occurrence_id]["rank"],
            "unblock_leverage_score": rank[occurrence_id]["unblock_leverage_score"],
            "source_lineage": entry["source_lineage"],
            "subject_summary": _subject_summary(str(entry["candidate_kind"]), source_item["candidate"]),
            "counterevidence": entry["counterevidence"],
            "uncertainties": entry["uncertainties"],
            "downstream_impact": entry["downstream_impact"],
            "decision_options": entry["decision_options"],
            "reviewer_fields_machine_empty": True,
        }
        by_kind[str(entry["candidate_kind"])].append(brief)
    result: dict[str, dict[str, Any]] = {}
    for kind, expected in EXPECTED_KIND_COUNTS.items():
        briefs = sorted(by_kind[kind], key=lambda item: (int(item["rank"]), str(item["occurrence_id"])))
        if len(briefs) != expected:
            raise ValueError(f"brief count mismatch for {kind}")
        result[kind] = stable_payload(
            {
                "schema_version": f"r5_night04_{kind}_review_briefs_v1",
                "candidate_kind": kind,
                "brief_count": len(briefs),
                "briefs": briefs,
            }
        )
    return result


def build_diff_index(briefs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    records = [
        {
            "occurrence_id": brief["occurrence_id"],
            "candidate_kind": kind,
            "source_lineage": brief["source_lineage"],
            "subject_summary": brief["subject_summary"],
            "candidate_sha256": brief["candidate_sha256"],
            "review_packet_sha256": brief["review_packet_sha256"],
        }
        for kind, payload in briefs.items()
        for brief in payload["briefs"]
    ]
    records.sort(key=lambda item: str(item["occurrence_id"]))
    return stable_payload({"schema_version": "r5_night04_evidence_claim_diff_index_v1", "record_count": len(records), "records": records})


def build_counterevidence_index(briefs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    records = [
        {
            "occurrence_id": brief["occurrence_id"],
            "counterevidence": brief["counterevidence"],
            "uncertainties": brief["uncertainties"],
        }
        for payload in briefs.values()
        for brief in payload["briefs"]
    ]
    records.sort(key=lambda item: str(item["occurrence_id"]))
    return stable_payload({"schema_version": "r5_night04_counterevidence_index_v1", "record_count": len(records), "records": records})


def build_downstream_impact(briefs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    records = [
        {"occurrence_id": brief["occurrence_id"], **dict(brief["downstream_impact"])}
        for payload in briefs.values()
        for brief in payload["briefs"]
    ]
    records.sort(key=lambda item: str(item["occurrence_id"]))
    return stable_payload(
        {
            "schema_version": "r5_night04_downstream_impact_v1",
            "record_count": len(records),
            "resolution_delta": 0,
            "records": records,
        }
    )


def build_reviewer_dashboard(
    leverage: Mapping[str, Any],
    first_parent: Mapping[str, Any],
    max_unlock: Mapping[str, Any],
    groups: Mapping[str, Any],
) -> dict[str, Any]:
    return stable_payload(
        {
            "schema_version": "r5_night04_reviewer_dashboard_v1",
            "mission_id": "r5_overnight_04_20260722",
            "review_candidates": 43,
            "pointer_dry_runs_target": 8,
            "research_truth": {
                "resolved_occurrences": 0,
                "total_occurrences": 63,
                "candidate_ready": 43,
                "dependency_blocked": 20,
                "parent_pending": 6,
            },
            "ranking_is_research_confidence": False,
            "ranking_is_engineering_review_priority": True,
            "first_parent_path": first_parent["selected_parent"],
            "dependency_membership_universe": max_unlock["dependency_universe_count"],
            "groups": groups["groups"],
            "rankings": leverage["rankings"],
        }
    )


def dashboard_markdown(payload: Mapping[str, Any]) -> str:
    truth = payload["research_truth"]
    lines = [
        "# Night04 Reviewer Dashboard",
        "",
        "> Ranking indicates engineering review leverage, not research confidence or resolution.",
        "",
        f"- Research truth: `{truth['resolved_occurrences']}/{truth['total_occurrences']} resolved`",
        f"- Candidate-ready: `{truth['candidate_ready']}`",
        f"- Dependency-blocked: `{truth['dependency_blocked']}`",
        f"- Parent pending: `{truth['parent_pending']}`",
        "",
        "| Rank | Occurrence | Case | Kind | Leverage |",
        "|---:|---|---|---|---:|",
    ]
    for item in payload["rankings"]:
        lines.append(
            f"| {item['rank']} | `{item['occurrence_id']}` | `{item['case_id']}` | `{item['candidate_kind']}` | {item['unblock_leverage_score']} |"
        )
    return "\n".join(lines) + "\n"


def dashboard_html(payload: Mapping[str, Any]) -> str:
    truth = payload["research_truth"]
    rows = "".join(
        "<tr>"
        f"<td>{item['rank']}</td><td><code>{html.escape(str(item['occurrence_id']))}</code></td>"
        f"<td>{html.escape(str(item['case_id']))}</td><td>{html.escape(str(item['candidate_kind']))}</td>"
        f"<td>{item['unblock_leverage_score']}</td></tr>"
        for item in payload["rankings"]
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Night04 Reviewer Dashboard</title>
<style>body{{font:15px system-ui;margin:2rem;max-width:1100px}}.truth{{padding:1rem;background:#f4f6f8;border-left:4px solid #485fc7}}table{{border-collapse:collapse;width:100%}}th,td{{padding:.45rem;border:1px solid #ccd2d8;text-align:left}}th{{background:#eef1f4}}code{{font-size:.9em}}</style></head>
<body><h1>Night04 Reviewer Dashboard</h1><div class="truth"><strong>{truth['resolved_occurrences']}/{truth['total_occurrences']} resolved.</strong> Ranking is engineering review leverage, not research confidence. Candidate-ready={truth['candidate_ready']}; dependency-blocked={truth['dependency_blocked']}; parent-pending={truth['parent_pending']}.</div>
<h2>Exact-hash review order</h2><table><thead><tr><th>Rank</th><th>Occurrence</th><th>Case</th><th>Kind</th><th>Leverage</th></tr></thead><tbody>{rows}</tbody></table></body></html>\n"""


def materialize_phase_c(repo_root: Path) -> dict[str, Any]:
    root = repo_root / OUTPUT_ROOT / "review_acceleration"
    leverage = build_unblock_leverage(repo_root)
    first_parent = build_first_parent_path(repo_root, leverage)
    max_unlock = build_max_unlock_path(repo_root, leverage)
    groups = build_review_groups(repo_root)
    briefs = build_review_briefs(repo_root, leverage)
    diff_index = build_diff_index(briefs)
    counterevidence = build_counterevidence_index(briefs)
    downstream = build_downstream_impact(briefs)
    dashboard = build_reviewer_dashboard(leverage, first_parent, max_unlock, groups)
    write_yaml(root / "unblock_leverage.yaml", leverage)
    write_yaml(root / "first_parent_path.yaml", first_parent)
    write_yaml(root / "max_unlock_path.yaml", max_unlock)
    write_yaml(root / "review_groups.yaml", groups)
    names = {
        "evidence_required": "evidence_review_briefs.yaml",
        "analysis_required": "analysis_review_briefs.yaml",
        "human_exact_hash_gate": "human_review_briefs.yaml",
        "engineering_local_pointer": "pointer_review_briefs.yaml",
    }
    for kind, name in names.items():
        write_yaml(root / name, briefs[kind])
    write_yaml(root / "evidence_claim_diff_index.yaml", diff_index)
    write_yaml(root / "counterevidence_index.yaml", counterevidence)
    write_yaml(root / "downstream_impact.yaml", downstream)
    write_yaml(root / "reviewer_dashboard.yaml", dashboard)
    atomic_write(root / "reviewer_dashboard.md", dashboard_markdown(dashboard).encode("utf-8"))
    atomic_write(root / "reviewer_dashboard.html", dashboard_html(dashboard).encode("utf-8"))
    return {"leverage": leverage, "briefs": briefs, "dashboard": dashboard}
