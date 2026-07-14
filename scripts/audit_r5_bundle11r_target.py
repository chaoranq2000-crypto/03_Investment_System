from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

EXPECTED_BRANCH = "codex/r5-bundle10r-reader-rebuild"
EXPECTED_BASE = "3bc55a61"
EXPECTED_MODEL_GENERATION = "model_gen_r5_bundle9r_1cd42241e6a38fb3"
WORKFLOW = Path("reports/workflow_runs/wf_20260703_stock_first_002837_invic")


def git(root: Path, *args: str) -> tuple[int, str]:
    proc = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)
    return proc.returncode, (proc.stdout or proc.stderr).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_recursive(value: Any, needle: str) -> list[Any]:
    found: list[Any] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) == needle:
                found.append(child)
            found.extend(find_recursive(child, needle))
    elif isinstance(value, list):
        for child in value:
            found.extend(find_recursive(child, needle))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Bundle 11R target branch and Bundle 10R generation")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output-json")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--allow-compatible-branch", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    check("git_repository", (root / ".git").exists(), str(root))
    rc, branch = git(root, "branch", "--show-current")
    branch_ok = rc == 0 and (branch == EXPECTED_BRANCH or args.allow_compatible_branch)
    check("target_branch", branch_ok, {"actual": branch, "expected": EXPECTED_BRANCH})
    rc, head = git(root, "rev-parse", "HEAD")
    check("head_resolved", rc == 0, head)
    base_rc, base_full = git(root, "rev-parse", f"{EXPECTED_BASE}^{{commit}}")
    if base_rc == 0:
        ancestor_rc, _ = git(root, "merge-base", "--is-ancestor", base_full, "HEAD")
        base_ok = ancestor_rc == 0
        base_detail = {"base": base_full, "head": head, "is_ancestor": base_ok}
    else:
        base_ok = not args.strict
        base_detail = {"base": EXPECTED_BASE, "resolved": False, "note": "strict mode requires the design baseline object locally"}
    check("target_commit_or_descendant", base_ok, base_detail)

    required_static = [
        Path("docs/workflows/RESEARCH_WORKFLOW.md"),
        Path("docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md"),
        Path(".agents/skills/research-orchestrator/SKILL.md"),
        Path(".agents/skills/stock-deep-dive/SKILL.md"),
        Path(".agents/skills/quality-review/SKILL.md"),
        WORKFLOW / "R5_bundle9r_model_generation_lock.yaml",
        WORKFLOW / "R5_bundle10r_reader_generation_lock.yaml",
    ]
    for rel in required_static:
        check(f"file:{rel}", (root / rel).is_file(), sha256(root / rel) if (root / rel).is_file() else None)

    candidate_groups = {
        "reader_payload": [WORKFLOW / "R5_bundle10r_reader_payload_v5.yaml", WORKFLOW / "R5_bundle10r_reader_payload_v4.yaml"],
        "reader_report": [WORKFLOW / "R5_bundle10r_reader_v5.md", WORKFLOW / "R5_bundle10r_reader_v4.md"],
        "traceability": [WORKFLOW / "R5_bundle10r_traceability_v5.yaml", WORKFLOW / "R5_bundle10r_traceability_v4.yaml"],
    }
    selected: dict[str, str | None] = {}
    for group, candidates in candidate_groups.items():
        matched = next((rel for rel in candidates if (root / rel).is_file()), None)
        selected[group] = str(matched) if matched else None
        check(f"candidate_group:{group}", matched is not None, selected[group])

    lock_path = root / WORKFLOW / "R5_bundle10r_reader_generation_lock.yaml"
    generation_ok = False
    generation_values: list[Any] = []
    if lock_path.is_file():
        try:
            lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
            generation_values = find_recursive(lock, "model_generation_id") + find_recursive(lock, "input_model_generation_id")
            generation_ok = EXPECTED_MODEL_GENERATION in [str(x) for x in generation_values]
        except Exception as exc:  # noqa: BLE001
            generation_values = [f"parse error: {exc}"]
    check("bundle10r_model_generation_binding", generation_ok, generation_values)

    result = {
        "schema_version": 1,
        "artifact_type": "r5_bundle11r_target_audit",
        "target_branch": EXPECTED_BRANCH,
        "design_baseline": EXPECTED_BASE,
        "expected_model_generation": EXPECTED_MODEL_GENERATION,
        "selected_artifacts": selected,
        "checks": checks,
        "pass": all(item["ok"] for item in checks),
    }
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
