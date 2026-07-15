#!/usr/bin/env python3
"""Validate Bundle 16R→15R→14R outputs and emit the Bundle 17R activation receipt."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.research.r5_bundle17r_activation_receipt import (  # noqa: E402
    ActivationContractError,
    evaluate_activation,
    load_document,
    write_activation_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path("config/r5_bundle17r_activation_policy.yaml"),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--expected-base",
        default=None,
        help="optional override for the Bundle 16R implementation ancestor; defaults to policy",
    )
    parser.add_argument(
        "--allow-descendant",
        action="store_true",
        help="allow HEAD to be a descendant of an explicitly supplied --expected-base",
    )
    parser.add_argument("--fail-on-blockers", action="store_true")
    return parser.parse_args()


def resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def git_head(repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def verify_head(repo_root: Path, expected: str, allow_descendant: bool) -> str:
    head = git_head(repo_root)
    if head == expected:
        return head
    if allow_descendant and head != "unknown":
        completed = subprocess.run(
            ["git", "merge-base", "--is-ancestor", expected, head],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0:
            return head
    raise ActivationContractError(
        f"Git HEAD {head!r} does not match or descend from expected base {expected!r}"
    )


def policy_base(policy_path: Path) -> str:
    document = load_document(policy_path)
    if not isinstance(document, Mapping):
        raise ActivationContractError("Bundle 17R policy root must be a mapping")
    expected = document.get("required_ancestor_commit")
    if not isinstance(expected, str) or len(expected) != 40:
        raise ActivationContractError("Bundle 17R policy must declare a 40-character required_ancestor_commit")
    return expected


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    policy_path = resolve(repo_root, args.policy)
    try:
        declared_base = policy_base(policy_path)
        expected_base = args.expected_base or declared_base
        # The normal path is a reviewed descendant after Bundle 17R itself is committed.
        allow_descendant = args.allow_descendant or args.expected_base is None
        verify_head(repo_root, expected_base, allow_descendant)
        artifacts = evaluate_activation(
            repo_root=repo_root,
            manifest_path=resolve(repo_root, args.manifest),
            policy_path=policy_path,
        )
        output_dir = resolve(repo_root, args.output_dir)
        write_activation_outputs(output_dir, artifacts)
        print(
            "Bundle 17R: decision={decision} cases={passed}/{total} blockers={blockers} generation={generation}".format(
                decision=artifacts.receipt.decision,
                passed=artifacts.receipt.engineering_pass_count,
                total=artifacts.receipt.expected_case_count,
                blockers=artifacts.receipt.blocker_count,
                generation=artifacts.receipt.generation_id,
            )
        )
        if args.fail_on_blockers and artifacts.receipt.blocker_count:
            return 2
        return 0
    except (ActivationContractError, OSError, ValueError) as exc:
        print(f"Bundle 17R activation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
