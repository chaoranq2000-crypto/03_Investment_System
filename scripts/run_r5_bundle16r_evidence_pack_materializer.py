#!/usr/bin/env python3
"""Materialize reviewed evidence catalogs into Bundle 15R-compatible pack candidates."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.research.r5_bundle16r_evidence_pack_materializer import (  # noqa: E402
    MaterializationContractError,
    atomic_publish_packs,
    discover_document_paths,
    load_document,
    materialize_suite,
    write_materialization_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--cases-dir",
        type=Path,
        default=Path("tests/fixtures/r5_bundle14r/cases"),
        help="Bundle 14R case-contract directory",
    )
    parser.add_argument("--catalog", type=Path, action="append", default=[], help="reviewed source/record catalog; repeatable")
    parser.add_argument("--catalog-dir", type=Path, action="append", default=[], help="directory of reviewed catalogs; repeatable")
    parser.add_argument("--mapping", type=Path, action="append", default=[], help="reviewer-authored Bundle 16R mapping; repeatable")
    parser.add_argument("--mapping-dir", type=Path, action="append", default=[], help="directory of review mappings; repeatable")
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path("config/r5_bundle16r_pack_materialization_policy.yaml"),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--packs-dir",
        type=Path,
        help="destination for atomically published Bundle 15R packs; requires --apply-packs",
    )
    parser.add_argument("--apply-packs", action="store_true", help="publish generated packs atomically to --packs-dir")
    parser.add_argument("--run-bundle15r", action="store_true", help="invoke the existing Bundle 15R compiler after materialization")
    parser.add_argument("--bundle15r-output-dir", type=Path, help="required with --run-bundle15r")
    parser.add_argument("--run-bundle14r", action="store_true", help="pass --run-bundle14r through the existing Bundle 15R runner")
    parser.add_argument("--bundle14r-output-dir", type=Path, help="required with --run-bundle14r")
    parser.add_argument("--expected-base", default=None, help="exact expected Git HEAD")
    parser.add_argument("--allow-descendant", action="store_true")
    parser.add_argument("--fail-on-blockers", action="store_true")
    parser.add_argument("--require-all-packs", action="store_true")
    return parser.parse_args()


def resolve(repo_root: Path, path: Path | None) -> Path | None:
    if path is None:
        return None
    return path if path.is_absolute() else repo_root / path


def git_head(repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def verify_head(repo_root: Path, expected: str | None, allow_descendant: bool) -> str:
    head = git_head(repo_root)
    if expected is None:
        return head
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
    raise MaterializationContractError(f"Git HEAD mismatch: expected {expected}, got {head}")


def collect_paths(
    repo_root: Path,
    explicit: Iterable[Path],
    directories: Iterable[Path],
    *,
    extensions: set[str],
) -> list[Path]:
    paths: list[Path] = []
    for value in explicit:
        path = resolve(repo_root, value)
        if path is not None:
            paths.extend(discover_document_paths(path, extensions=extensions))
    for value in directories:
        path = resolve(repo_root, value)
        if path is not None:
            paths.extend(discover_document_paths(path, extensions=extensions))
    return sorted(set(item.resolve() for item in paths))


def invoke_bundle15r(
    *,
    repo_root: Path,
    cases_dir: Path,
    packs_dir: Path,
    output_dir: Path,
    expected_base: str | None,
    allow_descendant: bool,
    run_bundle14r: bool,
    bundle14r_output_dir: Path | None,
) -> int:
    runner = repo_root / "scripts" / "run_r5_bundle15r_evidence_qualification.py"
    if not runner.is_file():
        raise MaterializationContractError(f"Bundle 15R runner is missing: {runner}")
    command = [
        sys.executable,
        str(runner),
        "--repo-root",
        str(repo_root),
        "--cases-dir",
        str(cases_dir),
        "--packs-dir",
        str(packs_dir),
        "--output-dir",
        str(output_dir),
    ]
    if expected_base:
        command.extend(["--expected-base", expected_base])
    if allow_descendant:
        command.append("--allow-descendant")
    if run_bundle14r:
        if bundle14r_output_dir is None:
            raise MaterializationContractError("--bundle14r-output-dir is required with --run-bundle14r")
        command.extend(["--run-bundle14r", "--bundle14r-output-dir", str(bundle14r_output_dir)])
    completed = subprocess.run(command, cwd=repo_root, check=False)
    return completed.returncode


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    try:
        head = verify_head(repo_root, args.expected_base, args.allow_descendant)
        cases_dir = resolve(repo_root, args.cases_dir)
        output_dir = resolve(repo_root, args.output_dir)
        policy_path = resolve(repo_root, args.policy)
        packs_dir = resolve(repo_root, args.packs_dir)
        bundle15r_output_dir = resolve(repo_root, args.bundle15r_output_dir)
        bundle14r_output_dir = resolve(repo_root, args.bundle14r_output_dir)
        assert cases_dir is not None and output_dir is not None
        if args.apply_packs and packs_dir is None:
            raise MaterializationContractError("--packs-dir is required with --apply-packs")
        if args.run_bundle15r and bundle15r_output_dir is None:
            raise MaterializationContractError("--bundle15r-output-dir is required with --run-bundle15r")
        if args.run_bundle14r and not args.run_bundle15r:
            raise MaterializationContractError("--run-bundle14r requires --run-bundle15r")

        catalog_paths = collect_paths(
            repo_root,
            args.catalog,
            args.catalog_dir,
            extensions={".yaml", ".yml", ".json", ".csv"},
        )
        mapping_paths = collect_paths(
            repo_root,
            args.mapping,
            args.mapping_dir,
            extensions={".yaml", ".yml", ".json"},
        )
        policy_document = load_document(policy_path) if policy_path and policy_path.is_file() else {}
        artifacts = materialize_suite(
            repo_root=repo_root,
            cases_dir=cases_dir,
            catalog_paths=catalog_paths,
            mapping_paths=mapping_paths,
            policy_document=policy_document,
            baseline_commit=head,
        )
        write_materialization_outputs(output_dir, artifacts)

        effective_packs_dir = output_dir / "pack_candidates"
        published: list[str] = []
        if args.apply_packs:
            assert packs_dir is not None
            published = [str(path) for path in atomic_publish_packs(effective_packs_dir, packs_dir)]
            effective_packs_dir = packs_dir

        bundle15r_exit_code = None
        if args.run_bundle15r:
            assert bundle15r_output_dir is not None
            bundle15r_exit_code = invoke_bundle15r(
                repo_root=repo_root,
                cases_dir=cases_dir,
                packs_dir=effective_packs_dir,
                output_dir=bundle15r_output_dir,
                expected_base=args.expected_base,
                allow_descendant=args.allow_descendant,
                run_bundle14r=args.run_bundle14r,
                bundle14r_output_dir=bundle14r_output_dir,
            )

        summary = {
            "bundle_id": artifacts.suite.bundle_id,
            "generation_id": artifacts.generation_lock["generation_id"],
            "git_head": head,
            "decision": artifacts.suite.decision,
            "case_count": artifacts.suite.case_count,
            "pack_materialized_count": artifacts.suite.pack_materialized_count,
            "fully_mapped_case_count": artifacts.suite.fully_mapped_case_count,
            "blocker_count": artifacts.suite.blocker_count,
            "published_packs": published,
            "bundle15r_exit_code": bundle15r_exit_code,
            "sample_quality_allowed": False,
            "p2_allowed": False,
            "canonical_workflow_state_mutation_allowed": False,
        }
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        if bundle15r_exit_code not in (None, 0):
            return int(bundle15r_exit_code)
        if args.require_all_packs and artifacts.suite.fully_mapped_case_count != artifacts.suite.case_count:
            return 3
        if args.fail_on_blockers and artifacts.suite.blocker_count:
            return 2
        return 0
    except (MaterializationContractError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Bundle 16R materialization failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
