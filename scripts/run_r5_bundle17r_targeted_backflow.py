#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research.r5_bundle17r_targeted_backflow import (  # noqa: E402
    BackflowContractError,
    compile_backflow,
    load_document,
    write_backflow_outputs,
)

DEFAULT_POLICY = ROOT / "config" / "r5_bundle17r_backflow_routes.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a physical Bundle 17R targeted-backflow run and compile "
            "all blockers into deterministic work orders and execution batches."
        )
    )
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--expected-base",
        help="Override the policy base only for reviewed descendant validation.",
    )
    parser.add_argument(
        "--allow-descendant",
        action="store_true",
        help="Allow HEAD to be a descendant of the expected base.",
    )
    parser.add_argument(
        "--fail-on-manual-route",
        action="store_true",
        help="Return exit code 3 when any blocker requires manual route review.",
    )
    return parser.parse_args()


def _policy_base(path: Path) -> str:
    value = load_document(path)
    if not isinstance(value, dict):
        raise BackflowContractError("policy root must be a mapping")
    base = value.get("required_ancestor_commit")
    if not isinstance(base, str) or len(base) != 40:
        raise BackflowContractError("policy required_ancestor_commit must be a 40-character SHA")
    return base


def _verify_git_head(repo_root: Path, expected: str, allow_descendant: bool) -> str:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head == expected:
        return head
    if allow_descendant:
        completed = subprocess.run(
            ["git", "merge-base", "--is-ancestor", expected, head],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0:
            return head
    raise BackflowContractError(
        f"Git HEAD {head!r} does not match or descend from expected base {expected!r}"
    )


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    policy_path = _resolve(repo_root, args.policy).resolve()
    manifest_path = _resolve(repo_root, args.manifest).resolve()
    output_dir = _resolve(repo_root, args.output_dir).resolve()
    try:
        expected = args.expected_base or _policy_base(policy_path)
        _verify_git_head(
            repo_root,
            expected,
            allow_descendant=args.allow_descendant or args.expected_base is None,
        )
        compilation = compile_backflow(
            repo_root=repo_root,
            manifest_path=manifest_path,
            policy_path=policy_path,
        )
        paths = write_backflow_outputs(output_dir, compilation)
        print(
            "Bundle 17R-BF1: decision={decision} issues={issues} routed={routed} "
            "manual={manual} work_orders={orders} validation_errors={errors}".format(
                decision=compilation.decision,
                issues=compilation.compiled_issue_count,
                routed=compilation.routed_issue_count,
                manual=compilation.manual_route_issue_count,
                orders=compilation.work_order_count,
                errors=compilation.validation_error_count,
            )
        )
        for name, path in sorted(paths.items()):
            print(f"{name}: {path}")
        if compilation.validation_error_count:
            return 2
        if args.fail_on_manual_route and compilation.manual_route_issue_count:
            return 3
        return 0
    except (BackflowContractError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Bundle 17R-BF1 failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
