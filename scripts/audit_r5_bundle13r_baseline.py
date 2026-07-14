from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
import sys
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research.r5_bundle13r_evidence_backflow import (  # noqa: E402
    load_yaml,
    validate_bundle12r_context,
    write_yaml,
)


def git(args: list[str], cwd: Path) -> tuple[int, str]:
    completed = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=False)
    return completed.returncode, (completed.stdout or completed.stderr).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the commit and exact Bundle 12R generation consumed by Bundle 13R.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--bundle12r-context-dir", required=True)
    parser.add_argument("--contract", default="config/r5_bundle13r_backflow_execution_contract.yaml")
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-compatible-descendant", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo_root).resolve()
    contract = load_yaml(repo / args.contract)
    baseline = contract.get("baseline", {})
    expected = str(baseline.get("target_commit_prefix", ""))
    head_rc, head = git(["rev-parse", "HEAD"], repo)
    branch_rc, branch = git(["branch", "--show-current"], repo)
    commit_ok = head_rc == 0 and head.startswith(expected)
    descendant = False
    if not commit_ok and args.allow_compatible_descendant:
        expected_rc, expected_full = git(["rev-parse", f"{expected}^{{commit}}"], repo)
        if expected_rc == 0:
            ancestor_rc, _ = git(["merge-base", "--is-ancestor", expected_full, head], repo)
            descendant = ancestor_rc == 0
            commit_ok = descendant

    _, context_issues = validate_bundle12r_context(Path(args.bundle12r_context_dir), contract)
    result: dict[str, Any] = {
        "artifact_type": "R5_bundle13r_baseline_audit",
        "schema_version": 1,
        "expected_commit_prefix": expected,
        "observed_head": head if head_rc == 0 else None,
        "observed_branch": branch if branch_rc == 0 else None,
        "commit_exact_or_descendant": commit_ok,
        "compatible_descendant": descendant,
        "bundle12r_context_valid": not context_issues,
        "bundle12r_context_issues": [row.as_dict() for row in context_issues],
        "decision": "pass" if commit_ok and not context_issues else "needs_fix",
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
    write_yaml(Path(args.output), result)
    print(f"decision={result['decision']} head={result['observed_head']} context_valid={result['bundle12r_context_valid']}")
    return 0 if result["decision"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
