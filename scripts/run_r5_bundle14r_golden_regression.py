#!/usr/bin/env python3
"""Run the Bundle 14R contract/evidence qualification regression suite.

The runner writes only to --output-dir.  It never edits workflow_state.yaml,
never marks sample quality or P2 as allowed, and never promotes narrative sample
text into evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.research.r5_bundle14r_golden_regression import (  # noqa: E402
    build_generation_lock,
    build_suite_result,
    discover_case_paths,
    load_yaml_document,
    suite_to_dict,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="repository root (default: inferred from this script)",
    )
    parser.add_argument(
        "--cases-dir",
        type=Path,
        default=REPO_ROOT / "tests" / "fixtures" / "r5_bundle14r" / "cases",
    )
    parser.add_argument(
        "--qualification-dir",
        type=Path,
        help="optional reviewed qualification summaries named <case_id>.yaml/json",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--core-source",
        type=Path,
        action="append",
        default=[],
        help="generic runtime source to scan; may be repeated",
    )
    parser.add_argument(
        "--expected-base",
        help="expected git base commit; exact equality is required unless --allow-descendant is set",
    )
    parser.add_argument(
        "--allow-descendant",
        action="store_true",
        help="accept a HEAD that descends from --expected-base",
    )
    return parser.parse_args()


def run_git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def verify_base(repo_root: Path, expected_base: str | None, allow_descendant: bool) -> str:
    head = run_git(repo_root, "rev-parse", "HEAD")
    if not expected_base:
        return head
    expected = run_git(repo_root, "rev-parse", expected_base)
    if head == expected:
        return head
    if allow_descendant:
        completed = subprocess.run(
            ["git", "merge-base", "--is-ancestor", expected, head],
            cwd=repo_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if completed.returncode == 0:
            return head
    raise SystemExit(
        f"baseline mismatch: HEAD={head}, expected={expected_base}; no files were written"
    )


def load_qualification(path: Path) -> Mapping[str, Any]:
    if path.suffix.lower() in {".yaml", ".yml"}:
        return load_yaml_document(path)
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, Mapping):
            raise ValueError(f"qualification root must be a mapping: {path}")
        return data
    raise ValueError(f"unsupported qualification file: {path}")


def load_qualification_directory(directory: Path | None) -> dict[str, Mapping[str, Any]]:
    if directory is None:
        return {}
    if not directory.exists():
        raise FileNotFoundError(f"qualification directory does not exist: {directory}")
    result: dict[str, Mapping[str, Any]] = {}
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in {".yaml", ".yml", ".json"}:
            continue
        payload = load_qualification(path)
        case_id = str(payload.get("case_id", path.stem))
        result[case_id] = payload
    return result


def write_backflow_csv(output_path: Path, suite_payload: Mapping[str, Any]) -> None:
    rows: list[Mapping[str, Any]] = []
    for qualification in suite_payload.get("qualification_results", []):
        for item in qualification.get("backflow_items", []):
            rows.append(item)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = ["case_id", "issue_code", "stage", "skill", "owner", "reason"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_close_readout(
    output_path: Path,
    *,
    head: str,
    suite_payload: Mapping[str, Any],
    generation_lock: Mapping[str, Any],
) -> None:
    case_rows: list[str] = []
    qualification_by_case = {
        item["case_id"]: item for item in suite_payload.get("qualification_results", [])
    }
    for contract in suite_payload.get("case_results", []):
        qualification = qualification_by_case.get(contract["case_id"], {})
        case_rows.append(
            "| {case_id} | {issuer} | {contract} | {status} | {qualified}/{required} |".format(
                case_id=contract["case_id"],
                issuer=contract["issuer_label"],
                contract="pass" if contract["contract_valid"] else "fail",
                status=qualification.get("status", "unknown"),
                qualified=qualification.get("qualified_driver_count", 0),
                required=qualification.get("required_driver_count", 0),
            )
        )

    text = f"""# R5 Bundle 14R Golden Regression Close Readout

- Git HEAD: `{head}`
- Generation ID: `{generation_lock['generation_id']}`
- Contract suite: `{'pass' if suite_payload['contract_passed'] else 'fail'}`
- Research-ready cases: `{suite_payload['research_ready_case_count']}`
- Exact-hash-review candidates: `{suite_payload['candidate_ready_case_count']}`
- Automated release authority: `false`
- `sample_quality_allowed`: `false`
- `p2_allowed`: `false`
- Workflow-state mutation: `false`

## Case status

| Case | Issuer | Contract | Qualification | Qualified drivers |
|---|---|---:|---|---:|
{chr(10).join(case_rows)}

## Interpretation

A passing contract suite means the four regression cases have valid economic-model,
evidence, forecast, valuation, narrative, backflow, and artifact contracts. It does
**not** mean the cases contain reviewed official evidence or research-ready reports.
Missing evidence remains explicit in the generated backflow queue.

Bundle 14R cannot close the existing issuer-specific Bundle 13R evidence backflow,
cannot invalidate its exact-hash human review, and cannot change sample-quality or
P2 release flags.
"""
    output_path.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    head = verify_base(repo_root, args.expected_base, args.allow_descendant)

    case_paths = discover_case_paths(args.cases_dir)
    case_documents = [(path, load_yaml_document(path)) for path in case_paths]
    qualifications = load_qualification_directory(args.qualification_dir)

    core_paths = list(args.core_source)
    if not core_paths:
        core_paths = [
            repo_root / "src" / "research" / "r5_bundle14r_golden_regression.py",
            repo_root / "src" / "quality" / "r5_bundle14r_semantic_regression.py",
            repo_root / "scripts" / "run_r5_bundle14r_golden_regression.py",
        ]

    suite = build_suite_result(
        case_documents,
        qualification_by_case=qualifications,
        core_source_paths=core_paths,
        path_root=repo_root,
    )
    suite_payload = suite_to_dict(suite)
    generation_lock = build_generation_lock(
        suite_result=suite,
        case_paths=case_paths,
        source_paths=core_paths,
        extra_inputs={"git_head": head},
        path_root=repo_root,
    )

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "R5_bundle14r_suite_result.json", suite_payload)
    write_json(output_dir / "R5_bundle14r_generation_lock.json", generation_lock)
    write_backflow_csv(output_dir / "R5_bundle14r_backflow_queue.csv", suite_payload)
    write_close_readout(
        output_dir / "R5_bundle14r_close_readout.md",
        head=head,
        suite_payload=suite_payload,
        generation_lock=generation_lock,
    )

    print(json.dumps({
        "bundle_id": suite.bundle_id,
        "generation_id": generation_lock["generation_id"],
        "contract_passed": suite.contract_passed,
        "research_ready_case_count": suite.research_ready_case_count,
        "candidate_ready_case_count": suite.candidate_ready_case_count,
        "sample_quality_allowed": False,
        "p2_allowed": False,
        "output_dir": str(output_dir),
    }, ensure_ascii=False, indent=2))
    return 0 if suite.contract_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
