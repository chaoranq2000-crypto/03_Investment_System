from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

SHA40 = re.compile(r"^[0-9a-f]{40}$")
FORBIDDEN_COMMAND_FRAGMENTS = (
    "push --force",
    "push -f",
    "gh pr create",
    "git merge main",
    "git checkout main",
    "git switch main",
)

class PackageError(RuntimeError):
    pass

def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise PackageError(f"YAML root must be a mapping: {path}")
    return data

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def validate_dag(tasks: list[dict[str, Any]]) -> None:
    ids = [str(t.get("id")) for t in tasks]
    if len(ids) != len(set(ids)):
        raise PackageError("duplicate task IDs")
    known = set(ids)
    for t in tasks:
        for dep in t.get("depends_on", []):
            if dep not in known:
                raise PackageError(f"{t['id']} has unknown dependency {dep}")
    graph = {t["id"]: list(t.get("depends_on", [])) for t in tasks}
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(node: str) -> None:
        if node in visiting:
            raise PackageError(f"dependency cycle at {node}")
        if node in visited:
            return
        visiting.add(node)
        for dep in graph[node]:
            visit(dep)
        visiting.remove(node)
        visited.add(node)
    for node in graph:
        visit(node)

def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    required = [
        "START_HERE.md",
        "CHECK_REPORT.md",
        "OVERNIGHT_MISSION.md",
        "EXECPLAN.md",
        "task_queue.yaml",
        "source_contract.yaml",
        "acceptance_matrix.yaml",
        "SAFETY_AND_GIT_POLICY.md",
        "AGENT_PROMPT.md",
        "scheduled_task_prompt.txt",
        "WINDOWS_RUNBOOK.md",
        "bootstrap_worktree.ps1",
        "PACKAGE_MANIFEST.yaml",
    ]
    missing = [p for p in required if not (root / p).is_file()]
    if missing:
        raise PackageError(f"missing required files: {missing}")

    q = load_yaml(root / "task_queue.yaml")
    source = load_yaml(root / "source_contract.yaml")
    manifest = load_yaml(root / "PACKAGE_MANIFEST.yaml")

    if q.get("schema_version") != "r5_night_shift_queue_v3_proposed":
        raise PackageError("unexpected queue schema")
    tasks = q.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 40:
        raise PackageError(f"expected 40 wrapper tasks, got {len(tasks) if isinstance(tasks, list) else type(tasks)}")
    validate_dag(tasks)

    baseline = q.get("baseline", {})
    if not SHA40.match(str(baseline.get("source_commit", ""))):
        raise PackageError("source_commit must be 40 lowercase hex")
    if baseline.get("source_commit") != source.get("source_commit"):
        raise PackageError("queue/source contract commit mismatch")

    rq = q.get("authoritative_research_queue", {})
    if rq.get("expected_total_items") != 69:
        raise PackageError("expected_total_items must be 69")
    taxonomy = rq.get("expected_occurrence_taxonomy", {})
    if sum(int(v) for v in taxonomy.values()) != 63:
        raise PackageError("occurrence taxonomy must sum to 63")
    if rq.get("expected_occurrence_items") != 63 or rq.get("expected_parent_aggregators") != 6:
        raise PackageError("expected 63 occurrences + 6 parents")

    goal = q.get("program_goal", {})
    if goal.get("close_allowed") is not False or goal.get("this_mission_may_close_goal") is not False:
        raise PackageError("program goal must remain non-closable")
    policy = q.get("mission_policy", {})
    for key in (
        "pr_creation_allowed",
        "merge_main_allowed",
        "force_push_allowed",
        "canonical_workflow_state_mutation_allowed",
        "automatic_human_review_allowed",
        "sample_quality_allowed",
        "p2_allowed",
    ):
        if policy.get(key) is not False:
            raise PackageError(f"{key} must be false")

    for t in tasks:
        if not t.get("allowed_paths"):
            raise PackageError(f"{t['id']} has empty allowed_paths")
        if not t.get("acceptance_commands"):
            raise PackageError(f"{t['id']} has empty acceptance_commands")
        if not t.get("required_artifacts"):
            raise PackageError(f"{t['id']} has empty required_artifacts")
        command_text = "\n".join(t["acceptance_commands"]).lower()
        for frag in FORBIDDEN_COMMAND_FRAGMENTS:
            if frag in command_text:
                raise PackageError(f"{t['id']} contains forbidden command fragment: {frag}")
        if t.get("resolution_capable") and t.get("external_gate_behavior") == "not_applicable":
            raise PackageError(f"{t['id']} resolution-capable task lacks external-gate behavior")

    files = manifest.get("files", [])
    if not isinstance(files, list) or not files:
        raise PackageError("manifest file list is empty")
    for item in files:
        rel = item["path"]
        expected = item["sha256"]
        path = root / rel
        if not path.is_file():
            raise PackageError(f"manifest path missing: {rel}")
        actual = sha256(path)
        if actual != expected:
            raise PackageError(f"hash mismatch for {rel}: {actual} != {expected}")

    print(json.dumps({
        "package": q["package_id"],
        "mission": q["mission_id"],
        "wrapper_tasks": len(tasks),
        "research_queue_expected": rq["expected_total_items"],
        "source_commit": baseline["source_commit"],
        "target_branch": baseline["target_branch"],
        "manifest_files_verified": len(files),
        "status": "valid",
    }, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
