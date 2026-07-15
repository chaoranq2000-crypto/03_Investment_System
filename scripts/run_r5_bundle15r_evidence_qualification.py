#!/usr/bin/env python3
"""Compile reviewed evidence packs into Bundle 14R qualification inputs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.research.r5_bundle15r_evidence_qualification import (  # noqa: E402
    QualificationContractError,
    compile_qualification_suite,
    discover_yaml_paths,
    extract_case_contract,
    load_pack_directory,
    load_yaml_document,
    scaffold_pack,
    write_compilation_outputs,
    write_yaml,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Qualify reviewed official evidence for the Bundle 14R golden-regression cases. "
            "Missing evidence remains blocked; no release flag is opened."
        )
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--cases-dir",
        type=Path,
        default=Path("tests/fixtures/r5_bundle14r/cases"),
    )
    parser.add_argument("--packs-dir", type=Path)
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path("config/r5_bundle15r_evidence_qualification_policy.yaml"),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--scaffold-dir",
        type=Path,
        help="optionally write one visibly incomplete reviewed-evidence template per case",
    )
    parser.add_argument(
        "--skip-source-path-verification",
        action="store_true",
        help="contract development only; never use for a release or real qualification run",
    )
    parser.add_argument(
        "--run-bundle14r",
        action="store_true",
        help="after compilation, invoke the existing Bundle 14R runner with the generated qualification directory",
    )
    parser.add_argument(
        "--bundle14r-output-dir",
        type=Path,
        help="required with --run-bundle14r",
    )
    parser.add_argument(
        "--expected-base",
        default=None,
        help="optional exact Git HEAD; when set, descendants are rejected unless --allow-descendant is used",
    )
    parser.add_argument("--allow-descendant", action="store_true")
    return parser.parse_args()


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
    if not expected:
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
    raise QualificationContractError(
        f"Git HEAD mismatch: expected {expected}, got {head}; rebase or explicitly allow a verified descendant"
    )


def resolve(repo_root: Path, value: Path | None) -> Path | None:
    if value is None:
        return None
    return value if value.is_absolute() else repo_root / value


def load_cases(cases_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    paths = discover_yaml_paths(cases_dir)
    if not paths:
        raise QualificationContractError(f"no Bundle 14R case YAML files found in {cases_dir}")
    return [(path, load_yaml_document(path)) for path in paths]


def write_scaffolds(
    *,
    case_documents: list[tuple[Path, dict[str, Any]]],
    scaffold_dir: Path,
    repo_root: Path,
) -> None:
    scaffold_dir.mkdir(parents=True, exist_ok=True)
    for path, document in case_documents:
        contract = extract_case_contract(document, source_path=path, path_root=repo_root)
        write_yaml(scaffold_dir / f"{contract.case_id}.yaml", scaffold_pack(contract))


def invoke_bundle14r(
    *,
    repo_root: Path,
    cases_dir: Path,
    qualification_dir: Path,
    output_dir: Path,
) -> int:
    runner = repo_root / "scripts" / "run_r5_bundle14r_golden_regression.py"
    if not runner.is_file():
        raise QualificationContractError(f"Bundle 14R runner is missing: {runner}")
    command = [
        sys.executable,
        str(runner),
        "--repo-root",
        str(repo_root),
        "--cases-dir",
        str(cases_dir),
        "--qualification-dir",
        str(qualification_dir),
        "--output-dir",
        str(output_dir),
    ]
    completed = subprocess.run(command, cwd=repo_root, check=False)
    return completed.returncode


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    try:
        head = verify_head(repo_root, args.expected_base, args.allow_descendant)
        cases_dir = resolve(repo_root, args.cases_dir)
        policy_path = resolve(repo_root, args.policy)
        packs_dir = resolve(repo_root, args.packs_dir)
        output_dir = resolve(repo_root, args.output_dir)
        scaffold_dir = resolve(repo_root, args.scaffold_dir)
        assert cases_dir is not None and output_dir is not None

        case_documents = load_cases(cases_dir)
        policy_document = load_yaml_document(policy_path) if policy_path and policy_path.is_file() else {}
        pack_by_case = load_pack_directory(packs_dir)

        if scaffold_dir is not None:
            write_scaffolds(
                case_documents=case_documents,
                scaffold_dir=scaffold_dir,
                repo_root=repo_root,
            )

        core_paths = [
            repo_root / "src" / "research" / "r5_bundle15r_evidence_qualification.py",
            repo_root / "scripts" / "run_r5_bundle15r_evidence_qualification.py",
            policy_path,
        ]
        artifacts = compile_qualification_suite(
            case_documents,
            pack_by_case=pack_by_case,
            repo_root=repo_root,
            policy_document=policy_document,
            verify_paths=not args.skip_source_path_verification,
            core_paths=[path for path in core_paths if path is not None],
            extra_lock_inputs={"git_head": head},
        )
        write_compilation_outputs(output_dir, artifacts, git_head=head)

        bundle14r_returncode = None
        if args.run_bundle14r:
            if args.bundle14r_output_dir is None:
                raise QualificationContractError(
                    "--bundle14r-output-dir is required with --run-bundle14r"
                )
            bundle14r_output_dir = resolve(repo_root, args.bundle14r_output_dir)
            assert bundle14r_output_dir is not None
            bundle14r_returncode = invoke_bundle14r(
                repo_root=repo_root,
                cases_dir=cases_dir,
                qualification_dir=output_dir / "qualification",
                output_dir=bundle14r_output_dir,
            )

        print(
            json.dumps(
                {
                    "bundle_id": artifacts.suite.bundle_id,
                    "generation_id": artifacts.generation_lock["generation_id"],
                    "input_contract_passed": artifacts.suite.input_contract_passed,
                    "case_count": artifacts.suite.case_count,
                    "evidence_pack_present_count": artifacts.suite.evidence_pack_present_count,
                    "evidence_pack_complete_count": artifacts.suite.evidence_pack_complete_count,
                    "bundle14r_candidate_ready_count": artifacts.suite.bundle14r_candidate_ready_count,
                    "blocker_count": artifacts.suite.blocker_count,
                    "conflict_count": artifacts.suite.conflict_count,
                    "bundle14r_returncode": bundle14r_returncode,
                    "sample_quality_allowed": False,
                    "p2_allowed": False,
                    "workflow_state_mutation_allowed": False,
                    "output_dir": str(output_dir),
                },
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
        )
        if not artifacts.suite.input_contract_passed:
            return 2
        if bundle14r_returncode not in {None, 0}:
            return int(bundle14r_returncode)
        return 0
    except (OSError, QualificationContractError, ValueError) as exc:
        print(f"Bundle 15R qualification failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
