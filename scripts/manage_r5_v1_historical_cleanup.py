#!/usr/bin/env python3
"""Build and validate the R5 V1 historical-cleanup control plane.

This module is deliberately incapable of deleting, staging, or committing files.
It inventories the frozen source tree, binds every proposed deletion to a durable
Git blob, restores blobs into a caller-owned temporary directory, scans active
routes, and validates the NUL-delimited vectors produced after a user performs
one contract-authorized manual deletion wave.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

import yaml


CONTRACT_REL = Path(
    "docs/codex_tasks/v1_governance_integration_cleanup_v5/CONTRACT.md"
)
BASELINE_MANIFEST_REL = Path(
    "reports/p1_6/r5_v1_governance_cleanup/historical_baseline_manifest.yaml"
)
CLEANUP_MANIFEST_REL = Path(
    "reports/p1_6/r5_v1_governance_cleanup/historical_cleanup_manifest.yaml"
)
DECOUPLING_RECEIPT_REL = Path(
    "reports/p1_6/r5_v1_governance_cleanup/validation/historical_decoupling.yaml"
)
WAVE_RECEIPT_RELS = {
    "night": Path(
        "reports/p1_6/r5_v1_governance_cleanup/validation/"
        "manual_deletion_wave_night.yaml"
    ),
    "bundle": Path(
        "reports/p1_6/r5_v1_governance_cleanup/validation/"
        "manual_deletion_wave_bundle.yaml"
    ),
    "old002837": Path(
        "reports/p1_6/r5_v1_governance_cleanup/validation/"
        "manual_deletion_wave_old002837.yaml"
    ),
}

EXPECTED_CONTRACT_SHA256 = (
    "7a02675ea94dd9ef83f40df42889720998cbea0d8db26992d158bf3c78135ef4"
)
PACKAGE_SOURCE_BASELINE = "f1dafeb32b08d24a6960f31d4a0f6d8820b95839"
HISTORICAL_SOURCE_SNAPSHOT = "312adc73821706b0b7ca6aa00e80ee608bd10b32"
ENGINEERING_SOURCE = "f60f220ae252262a537c612ce193fc779901984b"
NIGHT_SOURCE = "a96c1b717bf15905d72fd142efd946fa01bce666"
OLD_WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
OLD_RUN_PREFIX = f"reports/workflow_runs/{OLD_WORKFLOW_ID}"
PROTECTED_REVIEWED_INPUT_PREFIX = f"data/reviewed_inputs/{OLD_WORKFLOW_ID}"
EXPECTED_AUTHORITY_COUNTS = {
    "a1": 120,
    "a2": 13,
    "a3": 44,
    "a4": 35,
    "a5": 27,
    "a7": 3,
}
EXPECTED_A1_A5_OVERLAP = {
    "src/research/r5_bundle13r_evidence_backflow.py",
    "tests/test_r5_bundle13r_evidence_backflow.py",
}
EXPECTED_A7 = {
    "tests/test_r5_night_shift_ci_contract.py",
    "tests/test_r5_night_shift_night03_ci_contract.py",
    "tests/test_r5_night_shift_night04_ci_contract.py",
}
EXPECTED_A6 = {
    "path_count": 116,
    "path_vector_bytes": 8065,
    "path_vector_sha256": (
        "6c667b2aa0db007d5e89baf5b7bae837fd62249be3d85613f16aba3d14d32e6a"
    ),
}
ACTIVE_ROOTS = (
    ".github/",
    "src/",
    "scripts/",
    "tests/",
    "config/",
    "schemas/",
    "templates/",
    ".agents/skills/",
)
WAVE_ORDER = ("night", "bundle", "old002837")
RETAINED_EVALUATOR_DEPENDENCIES = {
    "tests/fixtures/r5_bundle12r/ready_manufacturing.yaml",
    "tests/fixtures/r5_bundle12r/invic_gap_template.yaml",
    "tests/fixtures/r5_bundle13r/bundle12r_context/R5_bundle12r_generation_lock.yaml",
    "tests/fixtures/r5_bundle13r/bundle12r_context/R5_bundle12r_backflow_plan.yaml",
    "tests/fixtures/r5_bundle13r/bundle12r_context/R5_bundle12r_research_question_plan.yaml",
    "tests/fixtures/r5_bundle13r/bundle12r_context/R5_bundle12r_operating_evidence_input_snapshot.yaml",
    "tests/fixtures/r5_bundle13r/bundle12r_context/R5_bundle12r_operating_evidence_result.yaml",
    "tests/fixtures/r5_bundle13r/r5_bundle13r_fixture_contract.yaml",
    "tests/fixtures/r5_bundle13r/reviewed_backfill_ready.yaml",
    "tests/fixtures/r5_bundle13r/reviewed_backfill_partial.yaml",
}
V006_TEST_PATHS = (
    "tests/test_r5_v1_historical_baseline_manifest.py",
    "tests/test_r5_v1_historical_cleanup_manifest.py",
    "tests/test_r5_v1_active_routing_retirement.py",
)
RETIRED_CI_MARKERS = (
    "tests/test_r5_night_shift_",
    "reports/p1_6/r5_night_shift/",
    "reports/p1_6/r5_bundle17r",
    "run night-shift contract",
    "069da527452def6c59c3772750e933d8611ccadf",
    "758ab7557d9de9eea42a5aeb5df95e3d68c26f0c",
)

NIGHT_CODEX_PREFIXES = (
    "codex_tasks/night_shift/r5_overnight_01/",
    "codex_tasks/night_shift/r5_overnight_02_20260720/",
    "codex_tasks/night_shift/r5_overnight_03_20260721/",
    "codex_tasks/night_shift/r5_overnight_04_20260722/",
    "codex_tasks/night_shift/r5_overnight_05_20260723/",
)
NIGHT_REPORT_PREFIXES = (
    "reports/p1_6/r5_night_shift/r5_overnight_01_20260719/",
    "reports/p1_6/r5_night_shift/r5_overnight_02_20260720/",
    "reports/p1_6/r5_night_shift/r5_overnight_03_20260721/",
    "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/",
    "reports/p1_6/r5_night_shift/r5_overnight_05_20260723/",
)
NIGHT_EXACT = {
    "scripts/run_r5_night_shift.py",
    "scripts/run_r5_night_shift.ps1",
    "config/r5_night_shift.yaml",
    "config/r5_night_shift_task_schema.json",
    "templates/night_shift_failure_packet.md",
    "templates/night_shift_morning_readout.md",
    "tests/night04_test_support.py",
}
BUNDLE_PREFIXES = (
    "codex_tasks/r5_bundle17r/",
    "codex_tasks/r5_bundle17r_backflow/",
    "reports/p1_6/r5_bundle17r/",
)
BUNDLE_EXACT = {
    "reports/p1_6/R5_BUNDLE17R_CLOSE_READOUT_TEMPLATE.md",
    "reports/p1_6/R5_BUNDLE17R_BACKFLOW_CLOSE_READOUT_TEMPLATE.md",
    ".github/workflows/r5-bundle17r-activation-receipt.yml",
    ".github/workflows/r5-bundle17r-targeted-backflow.yml",
    ".github/workflows/r5_bundle17r_bf2.yml",
    ".github/workflows/r5_bundle17r_bf2_ex1.yml",
}
BUNDLE_BASENAME_RE = re.compile(
    r"^(?:(?:test|run|build|validate|audit|apply|integrate|close|plan)_)?"
    r"r5_bundle(?:11r|12r|13r|14r|15r|16r|17r)(?:_|\.|$)"
)
BUNDLE_FIXTURE_COMPONENT_RE = re.compile(
    r"^r5_bundle(?:11r|12r|13r|14r|15r|16r|17r)(?:_|$)"
)
BUNDLE_DOC_RE = re.compile(r"^R5_BUNDLE(?:11R|12R|13R|14R|15R|16R)_")
BUNDLE_SKILL_REFERENCE_RE = re.compile(r"^bundle(?:12r|13r)_")
BUNDLE_TOKEN_RE = re.compile(
    r"(?i)\br5_bundle(?:11r|12r|13r|14r|15r|16r|17r)\b"
)

A6_PREFIXES = (
    "codex_tasks/r5_after_bundle3/",
    "codex_tasks/r5_after_bundle4/",
    "codex_tasks/r5_after_bundle5/",
    "codex_tasks/r5_after_patch12/",
    "codex_tasks/r5_after_patch24/",
    "codex_tasks/r5_after_patch36/",
    "codex_tasks/r5_after_patch48/",
    "codex_tasks/r5_bundle9r/",
    "data/processed/logs/",
    f"data/reviewed_inputs/{OLD_WORKFLOW_ID}/",
    "docs/codex_tasks/r5_v1_convergence/",
    "docs/codex_tasks/v1_governance_integration_cleanup/",
    "docs/codex_tasks/v1_governance_integration_cleanup_v2/",
    "docs/codex_tasks/v1_governance_integration_cleanup_v3/",
    "reports/p1_6/r5_v1_convergence/",
    "reports/workflow_runs/wf_20260723_stock_first_002837_v1_replay/",
)
A6_EXACT = {
    "docs/codex_tasks/TASK_01_MINERU_PDF_PIPELINE.md",
    "docs/codex_tasks/TASK_DOCS_WORKFLOW_DEDUP_REFACTOR_READOUT.md",
    "docs/plans/CODEX_VALUATION_INPUT_ENRICHMENT_PLAN.md",
    "docs/plans/DATA_LAYER_NEXT_TASKS_MASTER_PLAN.md",
    "docs/plans/DATA_LAYER_R4_READINESS_NEXT_TASKS.md",
    "docs/plans/P1_6_R4_TO_P2_CODEX_NEXT_PLAN_20260703.md",
    "docs/plans/R5_BUNDLE_9R_FORECAST_VALUATION_REBUILD_PLAN.md",
}
A6_DIRECT_CHILD_EXCLUSIONS = {
    "reports/p1_6/R5_BUNDLE17R_CLOSE_READOUT_TEMPLATE.md",
    "reports/p1_6/R5_BUNDLE17R_BACKFLOW_CLOSE_READOUT_TEMPLATE.md",
}

PROTECTED_PREFIXES = (
    "data/raw/",
    "data/processed/",
    "data/manifests/",
    f"data/reviewed_inputs/{OLD_WORKFLOW_ID}/",
    "docs/codex_tasks/r5_v1_convergence/",
    "reports/p1_6/r5_v1_convergence/",
    "reports/workflow_runs/wf_20260723_stock_first_002837_v1_replay/",
    "reports/workflow_runs/wf_20260725_stock_first_002837_v1_policy_refresh/",
)
PROTECTED_EXACT = {
    "AGENTS.md",
    "pyproject.toml",
    CONTRACT_REL.as_posix(),
}


class CleanupValidationError(RuntimeError):
    """Raised when the historical-cleanup contract is not satisfied."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CleanupValidationError(message)


def _filesystem_path(path: Path) -> Path:
    """Return a Windows extended-length path for filesystem I/O."""
    if os.name != "nt":
        return path
    value = os.path.abspath(os.fspath(path))
    if value.startswith("\\\\?\\"):
        return Path(value)
    if value.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + value[2:])
    return Path("\\\\?\\" + value)


def canonical_text_sha256(path: Path) -> str:
    payload = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(payload).hexdigest()


def path_vector(paths: Iterable[str]) -> tuple[int, str]:
    payload = b"".join(
        path.encode("utf-8") + b"\0" for path in sorted(set(paths))
    )
    return len(payload), hashlib.sha256(payload).hexdigest()


def _git(
    repo_root: Path,
    *args: str,
    input_bytes: bytes | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def git_text(repo_root: Path, *args: str) -> str:
    return _git(repo_root, *args).stdout.decode("utf-8", errors="strict").strip()


def git_paths(repo_root: Path, revision: str) -> list[str]:
    payload = _git(repo_root, "ls-tree", "-r", "-z", "--name-only", revision).stdout
    paths = [
        item.decode("utf-8", errors="surrogateescape")
        for item in payload.split(b"\0")
        if item
    ]
    require(paths == sorted(paths), f"{revision}: Git tree path order is not ordinal")
    return paths


def git_blob(repo_root: Path, revision: str, path: str) -> bytes:
    spec = f"{revision}:{path}"
    completed = _git(repo_root, "cat-file", "blob", spec, check=False)
    if completed.returncode:
        raise CleanupValidationError(
            f"missing Git blob {spec}: "
            f"{completed.stderr.decode('utf-8', errors='replace').strip()}"
        )
    return completed.stdout


def git_blob_or_none(repo_root: Path, revision: str, path: str) -> bytes | None:
    completed = _git(
        repo_root, "cat-file", "blob", f"{revision}:{path}", check=False
    )
    return completed.stdout if completed.returncode == 0 else None


def git_blob_oid(repo_root: Path, revision: str, path: str) -> str:
    spec = f"{revision}:{path}"
    oid = git_text(repo_root, "rev-parse", "--verify", spec)
    require(
        git_text(repo_root, "cat-file", "-t", oid) == "blob",
        f"{spec} is not a blob",
    )
    return oid


def verify_contract(repo_root: Path) -> dict[str, str]:
    contract = repo_root / CONTRACT_REL
    require(contract.is_file(), f"missing frozen contract: {CONTRACT_REL.as_posix()}")
    observed = canonical_text_sha256(contract)
    require(
        observed == EXPECTED_CONTRACT_SHA256,
        f"frozen contract SHA-256 drift: {observed}",
    )
    text = contract.read_text(encoding="utf-8")
    require('status: "frozen"' in text, "contract is not frozen")
    require(
        f'source_baseline: "{PACKAGE_SOURCE_BASELINE}"' in text,
        "contract package baseline drift",
    )
    return {
        "path": CONTRACT_REL.as_posix(),
        "canonical_sha256": observed,
        "status": "frozen",
        "source_baseline": PACKAGE_SOURCE_BASELINE,
    }


def _section_paths(text: str, heading: str, next_heading: str) -> set[str]:
    lines = text.splitlines()
    try:
        start = lines.index(heading)
        end = lines.index(next_heading, start + 1)
    except ValueError as exc:
        raise CleanupValidationError(f"missing contract section {heading}") from exc
    paths: set[str] = set()
    for line in lines[start + 1 : end]:
        match = re.fullmatch(r"- `([^`]+)`", line)
        if match:
            paths.add(match.group(1))
    return paths


def parse_authority(repo_root: Path) -> dict[str, set[str]]:
    verify_contract(repo_root)
    text = (repo_root / CONTRACT_REL).read_text(encoding="utf-8")
    sections = {
        "a1": _section_paths(
            text, "### A.1 `modify_existing_exact`", "### A.2 `add_exact`"
        ),
        "a2": _section_paths(
            text, "### A.2 `add_exact`", "### A.3 `manual_delete_boundary`"
        ),
        "a3": _section_paths(
            text,
            "### A.3 `manual_delete_boundary`",
            "### A.4 `retain_legacy_literal_exact`",
        ),
        "a4": _section_paths(
            text,
            "### A.4 `retain_legacy_literal_exact`",
            "### A.5 Retained Bundle capability evaluators",
        ),
        "a5": _section_paths(
            text,
            "### A.5 Retained Bundle capability evaluators",
            "### A.6 `protected_historical_literal_families`",
        ),
        "a7": _section_paths(
            text,
            "### A.7 `transition_modify_then_delete_exact`",
            "## Deliverables",
        ),
    }
    for key, expected in EXPECTED_AUTHORITY_COUNTS.items():
        require(
            len(sections[key]) == expected,
            f"{key.upper()} count drift: {len(sections[key])} != {expected}",
        )
    for left in sections:
        for right in sections:
            if left >= right:
                continue
            overlap = sections[left] & sections[right]
            expected = (
                EXPECTED_A1_A5_OVERLAP
                if {left, right} == {"a1", "a5"}
                else set()
            )
            require(
                overlap == expected,
                f"unexpected {left.upper()}/{right.upper()} overlap: "
                f"{sorted(overlap ^ expected)}",
            )
    require(sections["a7"] == EXPECTED_A7, "A7 transition path set drift")
    return sections


def is_a6_family(path: str) -> bool:
    if path in A6_EXACT or path.startswith(A6_PREFIXES):
        return True
    posix = PurePosixPath(path)
    return (
        posix.parent.as_posix() == "reports/p1_6"
        and path not in A6_DIRECT_CHILD_EXCLUSIONS
    )


def expand_a6(repo_root: Path) -> set[str]:
    paths = git_paths(repo_root, HISTORICAL_SOURCE_SNAPSHOT)
    candidates = [path for path in paths if is_a6_family(path)]
    inventory = {
        path
        for path in candidates
        if OLD_WORKFLOW_ID.encode("utf-8")
        in git_blob(repo_root, HISTORICAL_SOURCE_SNAPSHOT, path)
    }
    vector_bytes, vector_sha = path_vector(inventory)
    require(
        len(inventory) == EXPECTED_A6["path_count"],
        f"A6 path count drift: {len(inventory)}",
    )
    require(
        vector_bytes == EXPECTED_A6["path_vector_bytes"],
        f"A6 path-vector bytes drift: {vector_bytes}",
    )
    require(
        vector_sha == EXPECTED_A6["path_vector_sha256"],
        f"A6 path-vector SHA-256 drift: {vector_sha}",
    )
    return inventory


def night_eligible(path: str) -> bool:
    name = PurePosixPath(path).name
    return bool(
        path.startswith(NIGHT_CODEX_PREFIXES)
        or path.startswith(NIGHT_REPORT_PREFIXES)
        or path.startswith("src/maintenance/night_shift/")
        or path in NIGHT_EXACT
        or path.startswith("tests/fixtures/r5_night_shift/")
        or (
            path.startswith("tests/")
            and name.startswith("test_r5_night_shift_")
            and name.endswith(".py")
        )
    )


def bundle_eligible(path: str, a3: set[str]) -> bool:
    posix = PurePosixPath(path)
    name = posix.name
    parts = posix.parts
    if path in a3 or path in BUNDLE_EXACT or path.startswith(BUNDLE_PREFIXES):
        return True
    if parts and parts[0] in {
        "src",
        "scripts",
        "config",
        "schemas",
        "templates",
        "tests",
    } and BUNDLE_BASENAME_RE.match(name):
        return True
    if path.startswith("tests/fixtures/") and any(
        BUNDLE_FIXTURE_COMPONENT_RE.match(part) for part in parts[2:]
    ):
        return True
    if path.startswith("docs/workflows/") and BUNDLE_DOC_RE.match(name):
        return True
    return bool(
        path.startswith(".agents/skills/")
        and "/references/" in path
        and BUNDLE_SKILL_REFERENCE_RE.match(name)
    )


def classify_wave(path: str, a3: set[str]) -> str | None:
    if path == OLD_RUN_PREFIX or path.startswith(OLD_RUN_PREFIX + "/"):
        return "old002837"
    if night_eligible(path):
        return "night"
    if bundle_eligible(path, a3):
        return "bundle"
    return None


def is_protected(path: str, a6: set[str]) -> bool:
    return (
        path in PROTECTED_EXACT
        or path in a6
        or path.startswith(PROTECTED_PREFIXES)
        or path == ".git"
        or path.startswith(".git/")
    )


def build_candidate_inventory(
    repo_root: Path,
    authority: Mapping[str, set[str]],
    a6: set[str],
) -> dict[str, str]:
    tracked = set(git_paths(repo_root, HISTORICAL_SOURCE_SNAPSHOT))
    for path in authority["a3"]:
        require(path in tracked, f"A3 path is not tracked at package baseline: {path}")
    require(
        RETAINED_EVALUATOR_DEPENDENCIES <= tracked,
        "retained evaluator dependency set is not fully tracked at historical snapshot",
    )
    classified = {
        path: wave
        for path in tracked
        if (wave := classify_wave(path, authority["a3"])) is not None
    }
    retained = (
        authority["a1"]
        | authority["a2"]
        | authority["a4"]
        | authority["a5"]
        | a6
    )
    actual = {
        path: wave
        for path, wave in classified.items()
        if path not in retained
        and path not in RETAINED_EVALUATOR_DEPENDENCIES
        and not is_protected(path, a6)
    }
    require(
        set(actual).isdisjoint(retained),
        "actual cleanup inventory intersects retained authority",
    )
    require(
        set(actual) & authority["a7"] == authority["a7"],
        "actual cleanup inventory does not contain exactly all A7 transition paths",
    )
    require(
        all(actual[path] == "night" for path in authority["a7"]),
        "an A7 transition path is not assigned to the Night wave",
    )
    require(
        set(actual).issuperset(authority["a3"]),
        "actual cleanup inventory omits an A3 eligible path",
    )
    require(
        all(not is_protected(path, a6) for path in actual),
        "actual cleanup inventory intersects protected paths",
    )
    return dict(sorted(actual.items()))


def _baseline_for(
    repo_root: Path, wave: str, path: str, expected: bytes
) -> tuple[str, bytes]:
    preferences = (
        (NIGHT_SOURCE, ENGINEERING_SOURCE)
        if wave == "night"
        else (ENGINEERING_SOURCE, NIGHT_SOURCE)
    )
    for revision in preferences:
        payload = git_blob_or_none(repo_root, revision, path)
        if payload == expected:
            return revision, payload
    raise CleanupValidationError(
        f"{path}: no durable baseline contains the package-baseline blob"
    )


def _restore_command(revision: str, path: str) -> str:
    escaped = path.replace('"', '\\"')
    return f'git restore --source={revision} --worktree -- "{escaped}"'


def build_baseline_rows(
    repo_root: Path, inventory: Mapping[str, str]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path, wave in inventory.items():
        package_payload = git_blob(repo_root, HISTORICAL_SOURCE_SNAPSHOT, path)
        baseline, payload = _baseline_for(repo_root, wave, path, package_payload)
        rows.append(
            {
                "path": path,
                "wave": wave,
                "source_snapshot": HISTORICAL_SOURCE_SNAPSHOT,
                "baseline_commit": baseline,
                "blob_oid": git_blob_oid(repo_root, baseline, path),
                "byte_count": len(payload),
                "content_sha256": hashlib.sha256(payload).hexdigest(),
                "cat_file_spec": f"{baseline}:{path}",
                "restore_command": _restore_command(baseline, path),
            }
        )
    return rows


def _aggregate(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    paths = [str(row["path"]) for row in rows]
    vector_bytes, vector_sha = path_vector(paths)
    return {
        "file_count": len(rows),
        "content_byte_count": sum(int(row["byte_count"]) for row in rows),
        "path_vector_encoding": "ordinal_utf8_nul",
        "path_vector_byte_count": vector_bytes,
        "path_vector_sha256": vector_sha,
    }


def _candidate_tokens(value: str) -> set[str]:
    normalized = value.replace("\\", "/")
    targets: set[str] = set()
    if OLD_WORKFLOW_ID in normalized and (
        PROTECTED_REVIEWED_INPUT_PREFIX not in normalized
        or OLD_RUN_PREFIX in normalized
    ):
        targets.add(OLD_RUN_PREFIX)
    if "night_shift" in normalized.lower() or "r5_overnight_" in normalized.lower():
        targets.add("night:*")
    for match in BUNDLE_TOKEN_RE.finditer(normalized):
        targets.add("bundle:" + match.group(0).lower())
    return targets


def _expr_strings(
    node: ast.AST | None,
    assignments: Mapping[str, set[str]],
    seen: frozenset[str] = frozenset(),
) -> set[str]:
    if node is None:
        return set()
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, ast.Name):
        if node.id in seen:
            return set()
        values = set(assignments.get(node.id, set()))
        return values
    if isinstance(node, ast.JoinedStr):
        pieces: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                pieces.append(value.value)
        return {"".join(pieces)} if pieces else set()
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Div)):
        left = _expr_strings(node.left, assignments, seen)
        right = _expr_strings(node.right, assignments, seen)
        if not left:
            return right
        if not right:
            return left
        separator = "/" if isinstance(node.op, ast.Div) else ""
        return {f"{a}{separator}{b}" for a in left for b in right}
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return {
            value
            for item in node.elts
            for value in _expr_strings(item, assignments, seen)
        }
    if isinstance(node, ast.Call):
        return {
            value
            for arg in node.args
            for value in _expr_strings(arg, assignments, seen)
        }
    if isinstance(node, ast.Attribute):
        return _expr_strings(node.value, assignments, seen)
    return set()


def _python_references(path: str, text: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError as exc:
        return [
            {
                "source_path": path,
                "line": exc.lineno or 1,
                "kind": "python_parse_failure",
                "target": "active_scan",
                "evidence": str(exc),
            }
        ]
    assignments: dict[str, set[str]] = defaultdict(set)
    assignment_nodes: list[tuple[str, ast.AST]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            names: list[str] = []
            if isinstance(node, ast.Assign):
                names = [
                    target.id for target in node.targets if isinstance(target, ast.Name)
                ]
            elif isinstance(node.target, ast.Name):
                names = [node.target.id]
            strings = _expr_strings(value, assignments)
            for name in names:
                assignments[name].update(strings)
                if value is not None:
                    assignment_nodes.append((name, value))

    temporary_names = {
        argument.arg
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for argument in (
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        )
        if argument.arg in {"tmp_path", "tmp_path_factory"}
    }
    for node in ast.walk(tree):
        if not isinstance(node, (ast.With, ast.AsyncWith)):
            continue
        for item in node.items:
            call = item.context_expr
            target = item.optional_vars
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr
                in {"TemporaryDirectory", "NamedTemporaryFile"}
                and isinstance(target, ast.Name)
            ):
                temporary_names.add(target.id)

    def expression_is_temporary(node: ast.AST | None) -> bool:
        if node is None:
            return False
        if isinstance(node, ast.Name):
            return node.id in temporary_names
        if isinstance(node, ast.Attribute):
            if node.attr in {"name", "stem", "suffix"}:
                return False
            return expression_is_temporary(node.value)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            return expression_is_temporary(node.left)
        if isinstance(node, ast.IfExp):
            return expression_is_temporary(
                node.body
            ) and expression_is_temporary(node.orelse)
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return bool(node.elts) and all(
                expression_is_temporary(item) for item in node.elts
            )
        if isinstance(node, ast.JoinedStr):
            formatted = [
                value.value
                for value in node.values
                if isinstance(value, ast.FormattedValue)
            ]
            return bool(formatted) and all(
                expression_is_temporary(value) for value in formatted
            )
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "Path":
                return bool(node.args) and expression_is_temporary(node.args[0])
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in {
                    "absolute",
                    "resolve",
                    "with_name",
                    "with_suffix",
                }:
                    return expression_is_temporary(node.func.value)
                if node.func.attr in {"join", "joinpath", "mktemp"}:
                    candidates = [node.func.value, *node.args]
                    return any(
                        expression_is_temporary(candidate)
                        for candidate in candidates
                    )
        return False

    assignments_by_name: dict[str, list[ast.AST]] = defaultdict(list)
    for name, value in assignment_nodes:
        assignments_by_name[name].append(value)
    changed = True
    while changed:
        changed = False
        for name, values in assignments_by_name.items():
            if name in temporary_names:
                continue
            if values and all(expression_is_temporary(value) for value in values):
                temporary_names.add(name)
                changed = True

    references: list[dict[str, Any]] = []

    def add(node: ast.AST, kind: str, values: Iterable[str]) -> None:
        evidence = " | ".join(sorted(set(values)))
        for target in sorted(_candidate_tokens(evidence)):
            references.append(
                {
                    "source_path": path,
                    "line": int(getattr(node, "lineno", 1)),
                    "kind": kind,
                    "target": target,
                    "evidence": evidence[:500],
                }
            )

    physical_methods = {
        "open",
        "read",
        "read_bytes",
        "read_text",
        "exists",
        "is_file",
        "is_dir",
        "stat",
        "glob",
        "rglob",
        "iterdir",
        "load",
        "load_yaml",
        "load_json",
        "read_csv",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
            add(node, "candidate_module_import", names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            add(node, "candidate_module_import", [module])
        elif isinstance(node, ast.Call):
            function_name = ""
            receiver: ast.AST | None = None
            if isinstance(node.func, ast.Name):
                function_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                function_name = node.func.attr
                receiver = node.func.value
            values = set(_expr_strings(receiver, assignments))
            for arg in node.args:
                values.update(_expr_strings(arg, assignments))
            for keyword in node.keywords:
                values.update(_expr_strings(keyword.value, assignments))
            temporary_operation = expression_is_temporary(
                receiver
            ) or (
                bool(node.args)
                and expression_is_temporary(node.args[0])
            )
            if (
                function_name in physical_methods
                and not temporary_operation
                and _candidate_tokens(" ".join(values))
            ):
                add(node, "candidate_worktree_path_operation", values)
            if function_name == "add_argument":
                defaults = {
                    value
                    for keyword in node.keywords
                    if keyword.arg == "default"
                    for value in _expr_strings(keyword.value, assignments)
                }
                if _candidate_tokens(" ".join(defaults)):
                    add(node, "candidate_default_routing", defaults)
    return references


def _text_references(path: str, text: str) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    physical_context = re.compile(
        r"(?i)(run:|pytest|git diff|path:|proof_path|source_path|"
        r"(?:input|output|workflow|run)_(?:path|root|dir)|"
        r"eol=|include|uses:|read|open|exists|glob)"
    )
    for line_number, line in enumerate(text.splitlines(), 1):
        targets = _candidate_tokens(line)
        if not targets or not physical_context.search(line):
            continue
        for target in sorted(targets):
            references.append(
                {
                    "source_path": path,
                    "line": line_number,
                    "kind": "candidate_text_route_or_path",
                    "target": target,
                    "evidence": line.strip()[:500],
                }
            )
    return references


def scan_active_references(
    repo_root: Path,
    inventory: Mapping[str, str],
    authority: Mapping[str, set[str]],
) -> dict[str, Any]:
    tracked = [
        path
        for path in git_text(repo_root, "ls-files", "-z").split("\0")
        if path
    ]
    references: list[dict[str, Any]] = []
    allowed_literals: list[dict[str, Any]] = []
    unknown_classifications: list[str] = []
    for path in sorted(tracked):
        if not path.startswith(ACTIVE_ROOTS) or path in inventory:
            continue
        file_path = repo_root / path
        if not file_path.is_file():
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if not _candidate_tokens(text):
            continue
        if path in authority["a2"]:
            allowed_literals.append(
                {"path": path, "classification": "cleanup_control_plane"}
            )
            continue
        if path in RETAINED_EVALUATOR_DEPENDENCIES:
            allowed_literals.append(
                {
                    "path": path,
                    "classification": "retained_evaluator_dependency",
                }
            )
            continue
        classified = (
            "a1_modify"
            if path in authority["a1"]
            else "a4_metadata"
            if path in authority["a4"]
            else "a5_explicit_evaluator"
            if path in authority["a5"]
            else None
        )
        if classified is None:
            file_references = (
                _python_references(path, text)
                if path.endswith(".py")
                else _text_references(path, text)
            )
            if file_references:
                unknown_classifications.append(path)
                references.extend(file_references)
            else:
                allowed_literals.append(
                    {
                        "path": path,
                        "classification": "negative_assertion_or_metadata",
                    }
                )
            continue
        if path in authority["a4"] and not path.endswith(".py"):
            allowed_literals.append(
                {"path": path, "classification": "a4_metadata_literal"}
            )
            continue
        file_references = (
            _python_references(path, text)
            if path.endswith(".py")
            else _text_references(path, text)
        )
        if path in authority["a4"]:
            if file_references:
                references.extend(file_references)
            else:
                allowed_literals.append(
                    {"path": path, "classification": "a4_metadata_literal"}
                )
        elif path in authority["a5"]:
            forbidden = [
                row
                for row in file_references
                if row["target"] == OLD_RUN_PREFIX
            ]
            canonical_writes = [
                token
                for token in ("workflow_state.yaml", "validate_workflow_state")
                if token in text
            ]
            if forbidden or canonical_writes:
                references.extend(forbidden)
                for token in canonical_writes:
                    references.append(
                        {
                            "source_path": path,
                            "line": 1,
                            "kind": "retained_evaluator_canonical_state_access",
                            "target": "active_scan",
                            "evidence": token,
                        }
                    )
            else:
                allowed_literals.append(
                    {"path": path, "classification": "a5_explicit_evaluator"}
                )
        else:
            references.extend(file_references)
    references.sort(
        key=lambda row: (
            str(row["source_path"]),
            int(row["line"]),
            str(row["kind"]),
            str(row["target"]),
        )
    )
    allowed_literals.sort(key=lambda row: str(row["path"]))
    return {
        "roots": list(ACTIVE_ROOTS),
        "reference_count": len(references),
        "unknown_classification_count": len(set(unknown_classifications)),
        "unknown_classifications": sorted(set(unknown_classifications)),
        "allowed_literal_count": len(allowed_literals),
        "allowed_literals": allowed_literals,
        "references": references,
    }


def validate_transition_contract(
    repo_root: Path,
    authority: Mapping[str, set[str]],
) -> dict[str, Any]:
    require(authority["a7"] == EXPECTED_A7, "A7 transition path set drift")

    workflow_path = repo_root / ".github/workflows/ci.yml"
    require(workflow_path.is_file(), "missing retained CI workflow")
    workflow_text = workflow_path.read_text(encoding="utf-8")
    workflow_lowered = workflow_text.casefold()
    workflow = yaml.safe_load(workflow_text)
    require(isinstance(workflow, dict), "CI workflow root must be an object")
    jobs = workflow.get("jobs")
    require(isinstance(jobs, dict), "CI workflow jobs must be an object")
    tests_job = jobs.get("tests")
    require(isinstance(tests_job, dict), "CI workflow tests job is missing")
    steps = tests_job.get("steps")
    require(isinstance(steps, list), "CI workflow tests steps must be a list")
    require(
        all(isinstance(step, dict) for step in steps),
        "CI workflow contains a non-object step",
    )
    commands = [str(step.get("run", "")) for step in steps]

    require(
        all(marker not in workflow_lowered for marker in RETIRED_CI_MARKERS),
        "CI workflow still contains a retired Night route or history guard",
    )
    require(
        all("tests/test_r5_night_shift_" not in command for command in commands),
        "CI run command still contains the retired Night test route",
    )
    require(
        all(
            "reports/p1_6/r5_night_shift/" not in command
            for command in commands
        ),
        "CI run command still contains the retired Night report route",
    )
    require(
        "continue-on-error: true" not in workflow_lowered
        and "|| true" not in workflow_lowered,
        "CI workflow contains an assertion-bypass route",
    )
    for step in steps:
        continue_on_error = step.get("continue-on-error")
        require(
            continue_on_error not in (True, 1)
            and str(continue_on_error).casefold() != "true",
            "CI workflow contains continue-on-error",
        )
        condition = str(step.get("if", "")).replace(" ", "").casefold()
        require(
            condition not in {"false", "0", "${{false}}"},
            "CI workflow contains an unreachable constant-false step",
        )

    checkout_steps = [
        step
        for step in steps
        if str(step.get("uses", "")).startswith("actions/checkout@")
    ]
    require(len(checkout_steps) == 1, "CI must contain exactly one checkout step")
    checkout_with = checkout_steps[0].get("with")
    require(isinstance(checkout_with, dict), "checkout step is missing settings")
    require(
        str(checkout_with.get("fetch-depth")) == "0",
        "checkout fetch-depth is not 0",
    )
    require(
        commands.count("python -m pytest -q") == 1,
        "CI must contain exactly one full pytest command",
    )
    require(
        sum("run_source_route_quality_gate.py" in command for command in commands)
        == 1,
        "CI must contain exactly one source-route quality gate",
    )
    v006_commands = [
        command
        for command in commands
        if all(test_path in command for test_path in V006_TEST_PATHS)
    ]
    require(
        len(v006_commands) == 1,
        "CI must contain one command with all three V-006 tests",
    )
    require(
        all(
            marker not in workflow_lowered
            for marker in ("git push", "gh pr create", "--force")
        ),
        "CI workflow contains a publication mutation",
    )

    required_source_literals = {
        *RETIRED_CI_MARKERS,
        "fetch-depth",
        "python -m pytest -q",
        "run_source_route_quality_gate.py",
        *V006_TEST_PATHS,
        "git push",
        "gh pr create",
        "--force",
        "continue-on-error: true",
        "|| true",
    }
    forbidden_source_literals = (
        "src.maintenance.night_shift",
        "tests.night04_test_support",
        "build_ci_contract",
        "monkeypatch",
        "unittest.mock",
        "mock.patch",
        "pytest.mark.skip",
        "pytest.mark.xfail",
        "collect_ignore",
    )
    test_rows: list[dict[str, Any]] = []
    for relative in sorted(authority["a7"]):
        path = repo_root / relative
        require(path.is_file(), f"missing A7 transition test: {relative}")
        source = path.read_text(encoding="utf-8")
        lowered = source.casefold()
        missing_literals = sorted(
            literal for literal in required_source_literals if literal not in lowered
        )
        require(
            not missing_literals,
            f"{relative}: missing equal-strength literals {missing_literals}",
        )
        forbidden = sorted(
            literal for literal in forbidden_source_literals if literal in lowered
        )
        require(
            not forbidden,
            f"{relative}: forbidden transition-test bypass {forbidden}",
        )
        tree = ast.parse(source, filename=relative)
        test_functions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        ]
        require(test_functions, f"{relative}: no executable test function")
        require(
            all(
                any(isinstance(node, ast.Assert) for node in ast.walk(function))
                for function in test_functions
            ),
            f"{relative}: a test function has no live assertion",
        )
        require(
            not any(
                isinstance(node, ast.If)
                and isinstance(node.test, ast.Constant)
                and node.test.value in (False, 0)
                for node in ast.walk(tree)
            ),
            f"{relative}: constant-false branch is forbidden",
        )
        test_rows.append(
            {
                "path": relative,
                "test_function_count": len(test_functions),
                "assertion_count": sum(
                    isinstance(node, ast.Assert) for node in ast.walk(tree)
                ),
                "equal_strength_retirement_assertions": True,
            }
        )

    return {
        "path_count": len(test_rows),
        "paths": [row["path"] for row in test_rows],
        "tests": test_rows,
        "ci": {
            "retired_night_routes_absent": True,
            "checkout_fetch_depth_zero": True,
            "source_route_gate_count": 1,
            "v006_command_count": 1,
            "full_pytest_command_count": 1,
            "publication_mutation_absent": True,
            "bypass_route_absent": True,
        },
    }


def _reference_applies(reference: Mapping[str, Any], path: str, wave: str) -> bool:
    target = str(reference["target"])
    if target == OLD_RUN_PREFIX:
        return wave == "old002837"
    if target == "night:*":
        return wave == "night"
    if target.startswith("bundle:"):
        token = target.split(":", 1)[1]
        return wave == "bundle" and token in path.lower()
    return False


def build_documents(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    contract = verify_contract(repo_root)
    authority = parse_authority(repo_root)
    a6 = expand_a6(repo_root)
    inventory = build_candidate_inventory(repo_root, authority, a6)
    transition = validate_transition_contract(repo_root, authority)
    baseline_rows = build_baseline_rows(repo_root, inventory)
    active_scan = scan_active_references(repo_root, inventory, authority)
    by_path = {str(row["path"]): row for row in baseline_rows}

    baseline_manifest = {
        "schema_version": "r5_v1_historical_baseline_manifest_v1",
        "contract": contract,
        "source_snapshot": HISTORICAL_SOURCE_SNAPSHOT,
        "durable_restore_refs": {
            "night_source": NIGHT_SOURCE,
            "engineering_source": ENGINEERING_SOURCE,
        },
        "aggregate": _aggregate(baseline_rows),
        "files": baseline_rows,
    }

    cleanup_rows: list[dict[str, Any]] = []
    for path, wave in inventory.items():
        baseline = by_path[path]
        reference_count = sum(
            _reference_applies(reference, path, wave)
            for reference in active_scan["references"]
        )
        cleanup_rows.append(
            {
                "path": path,
                "wave": wave,
                "artifact_kind": (
                    "night_history"
                    if wave == "night"
                    else "bundle_pipeline"
                    if wave == "bundle"
                    else "old_002837_workflow_run"
                ),
                "eligibility_rule": (
                    "night_family"
                    if wave == "night"
                    else "bundle_family_or_a3_exact"
                    if wave == "bundle"
                    else "old_002837_exact_root"
                ),
                "baseline_commit": baseline["baseline_commit"],
                "blob_oid": baseline["blob_oid"],
                "byte_count": baseline["byte_count"],
                "content_sha256": baseline["content_sha256"],
                "active_reference_count": reference_count,
                "reference_scan_scope": "tracked_active_roots",
                "deletion_preconditions": [
                    "active_reference_count_equals_zero",
                    "baseline_blob_and_full_restore_verified",
                    "current_wave_armed_in_start_here",
                    "user_manually_deletes_only_this_exact_path",
                ],
                "restore_command": baseline["restore_command"],
            }
        )
    wave_documents: list[dict[str, Any]] = []
    for wave in WAVE_ORDER:
        wave_rows = [row for row in cleanup_rows if row["wave"] == wave]
        wave_documents.append(
            {
                "wave": wave,
                "order": WAVE_ORDER.index(wave) + 1,
                "aggregate": _aggregate(wave_rows),
                "paths": [str(row["path"]) for row in wave_rows],
            }
        )
    cleanup_manifest = {
        "schema_version": "r5_v1_historical_cleanup_manifest_v1",
        "contract": contract,
        "source_snapshot": HISTORICAL_SOURCE_SNAPSHOT,
        "deletion_actor": "user_manual_only",
        "codex_delete_authorized": False,
        "wave_order": list(WAVE_ORDER),
        "aggregate": _aggregate(cleanup_rows),
        "waves": wave_documents,
        "files": cleanup_rows,
    }

    a6_bytes, a6_sha = path_vector(a6)
    actual_paths = set(inventory)
    retained_paths = (
        authority["a1"]
        | authority["a2"]
        | authority["a4"]
        | authority["a5"]
        | a6
    )
    retained_overlap = actual_paths & retained_paths
    protected_overlap = {
        path for path in actual_paths if is_protected(path, a6)
    }
    scan_passed = (
        active_scan["reference_count"] == 0
        and active_scan["unknown_classification_count"] == 0
    )
    decision = "pass" if scan_passed else "fail"
    receipt = {
        "schema_version": "r5_v1_historical_decoupling_validation_v1",
        "validation_id": "V-006",
        "phase": "P5",
        "decision": decision,
        "contract": contract,
        "authority": {
            "a1_modify_existing_exact_count": len(authority["a1"]),
            "a2_add_exact_count": len(authority["a2"]),
            "a3_manual_delete_boundary_count": len(authority["a3"]),
            "a4_retain_legacy_literal_exact_count": len(authority["a4"]),
            "a5_retained_capability_evaluator_count": len(authority["a5"]),
            "a7_transition_modify_then_delete_exact_count": len(authority["a7"]),
            "a1_a5_overlap": sorted(authority["a1"] & authority["a5"]),
            "a7_all_authority_overlaps_empty": all(
                not (authority["a7"] & authority[key])
                for key in ("a1", "a2", "a3", "a4", "a5")
            )
            and not (authority["a7"] & a6),
            "all_other_authority_pairwise_overlaps_empty": True,
        },
        "a6_inventory": {
            "path_count": len(a6),
            "path_vector_encoding": "ordinal_utf8_nul",
            "path_vector_byte_count": a6_bytes,
            "path_vector_sha256": a6_sha,
        },
        "cleanup_inventory": {
            **_aggregate(cleanup_rows),
            "wave_file_counts": {
                wave["wave"]: wave["aggregate"]["file_count"]
                for wave in wave_documents
            },
            "retained_overlap_count": len(retained_overlap),
            "protected_overlap_count": len(protected_overlap),
            "a7_actual_overlap_count": len(actual_paths & authority["a7"]),
            "a7_actual_overlap": sorted(actual_paths & authority["a7"]),
            "a7_all_assigned_to_night": all(
                inventory[path] == "night" for path in authority["a7"]
            ),
            "retained_evaluator_dependencies": sorted(
                RETAINED_EVALUATOR_DEPENDENCIES
            ),
        },
        "transition_validation": transition,
        "active_reference_scan": active_scan,
        "restore_verification": {
            "cat_file_e_verified": False,
            "content_hash_verified": False,
            "full_restore_verified": False,
            "note": "Set by validate/verify-restore; build does not claim a restore run.",
        },
        "guards": {
            "codex_delete_command_exists": False,
            "actual_manifest_uses_wildcards": False,
            "actual_manifest_paths_are_repo_relative": True,
            "actual_manifest_disjoint_from_retained_and_protected": not (
                retained_overlap or protected_overlap
            ),
            "actual_manifest_intersection_a7_equals_a7": (
                actual_paths & authority["a7"] == authority["a7"]
            ),
            "ci_fetch_depth_zero_required": True,
        },
    }
    return baseline_manifest, cleanup_manifest, receipt


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path}: YAML root must be an object")
    return value


def render_yaml(value: Mapping[str, Any]) -> str:
    return yaml.safe_dump(
        dict(value),
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=100,
    )


def write_yaml_exact(repo_root: Path, relative: Path, value: Mapping[str, Any]) -> None:
    target = (repo_root / relative).resolve()
    root = repo_root.resolve()
    require(target.is_relative_to(root), f"output escapes repository: {target}")
    allowed = {
        BASELINE_MANIFEST_REL,
        CLEANUP_MANIFEST_REL,
        DECOUPLING_RECEIPT_REL,
        *WAVE_RECEIPT_RELS.values(),
    }
    require(relative in allowed, f"unauthorized output path: {relative.as_posix()}")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = render_yaml(value)
    if target.exists() and target.read_text(encoding="utf-8") == payload:
        return
    target.write_text(payload, encoding="utf-8", newline="\n")


def validate_documents(
    repo_root: Path,
    baseline_manifest: Mapping[str, Any],
    cleanup_manifest: Mapping[str, Any],
    *,
    require_zero_active_references: bool = False,
    verify_each_cat_file: bool = False,
) -> dict[str, Any]:
    expected_baseline, expected_cleanup, receipt = build_documents(repo_root)
    require(
        baseline_manifest == expected_baseline,
        "historical baseline manifest is not the deterministic expected document",
    )
    require(
        cleanup_manifest == expected_cleanup,
        "historical cleanup manifest is not the deterministic expected document",
    )
    baseline_rows = list(baseline_manifest["files"])
    cleanup_rows = list(cleanup_manifest["files"])
    require(
        [row["path"] for row in baseline_rows]
        == sorted(row["path"] for row in baseline_rows),
        "baseline rows are not ordinal sorted",
    )
    require(
        [row["path"] for row in cleanup_rows]
        == sorted(row["path"] for row in cleanup_rows),
        "cleanup rows are not ordinal sorted",
    )
    require(
        {row["path"] for row in baseline_rows}
        == {row["path"] for row in cleanup_rows},
        "baseline/cleanup manifest path sets differ",
    )
    for row in baseline_rows:
        path = str(row["path"])
        revision = str(row["baseline_commit"])
        spec = f"{revision}:{path}"
        if verify_each_cat_file:
            completed = _git(repo_root, "cat-file", "-e", spec, check=False)
            require(completed.returncode == 0, f"git cat-file -e failed: {spec}")
        payload = git_blob(repo_root, revision, path)
        require(len(payload) == row["byte_count"], f"{path}: byte count mismatch")
        require(
            hashlib.sha256(payload).hexdigest() == row["content_sha256"],
            f"{path}: content SHA-256 mismatch",
        )
        require(
            git_blob_oid(repo_root, revision, path) == row["blob_oid"],
            f"{path}: blob OID mismatch",
        )
        require(row["restore_command"] == _restore_command(revision, path), f"{path}: restore command drift")
    if require_zero_active_references:
        require(
            receipt["active_reference_scan"]["reference_count"] == 0,
            "active candidate-tree references remain",
        )
        require(
            receipt["active_reference_scan"]["unknown_classification_count"] == 0,
            "active candidate-tree classifications remain unknown",
        )
    receipt["restore_verification"].update(
        {
            "cat_file_e_verified": verify_each_cat_file,
            "content_hash_verified": True,
            "full_restore_verified": False,
        }
    )
    receipt["decision"] = (
        "pass"
        if receipt["active_reference_scan"]["reference_count"] == 0
        and receipt["active_reference_scan"]["unknown_classification_count"] == 0
        else "fail"
    )
    return receipt


def validate_repository(
    repo_root: Path,
    *,
    require_zero_active_references: bool = False,
    verify_each_cat_file: bool = False,
) -> dict[str, Any]:
    return validate_documents(
        repo_root,
        load_yaml(repo_root / BASELINE_MANIFEST_REL),
        load_yaml(repo_root / CLEANUP_MANIFEST_REL),
        require_zero_active_references=require_zero_active_references,
        verify_each_cat_file=verify_each_cat_file,
    )


def restore_all(
    repo_root: Path,
    restore_root: Path,
    baseline_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    root = repo_root.resolve()
    target_root = restore_root.resolve()
    target_filesystem_root = _filesystem_path(target_root)
    require(
        not target_root.is_relative_to(root),
        "restore root must be outside the repository",
    )
    if target_filesystem_root.exists():
        require(
            not any(target_filesystem_root.iterdir()),
            "restore root must be new or empty",
        )
    else:
        target_filesystem_root.mkdir(parents=True)
    rows = list(baseline_manifest["files"])
    restored_bytes = 0
    for row in rows:
        path = str(row["path"])
        completed = _git(
            repo_root,
            "cat-file",
            "-e",
            f"{row['baseline_commit']}:{path}",
            check=False,
        )
        require(completed.returncode == 0, f"git cat-file -e failed: {path}")
        payload = git_blob(repo_root, str(row["baseline_commit"]), path)
        destination = (target_root / PurePosixPath(path)).resolve()
        require(destination.is_relative_to(target_root), f"restore path escapes: {path}")
        filesystem_destination = _filesystem_path(destination)
        filesystem_destination.parent.mkdir(parents=True, exist_ok=True)
        filesystem_destination.write_bytes(payload)
        restored = filesystem_destination.read_bytes()
        require(restored == payload, f"{path}: restored bytes differ")
        require(
            hashlib.sha256(restored).hexdigest() == row["content_sha256"],
            f"{path}: restored SHA-256 differs",
        )
        restored_bytes += len(restored)
    return {
        "file_count": len(rows),
        "content_byte_count": restored_bytes,
        "restore_root": str(target_root),
        "cat_file_e_verified": True,
        "content_hash_verified": True,
        "full_restore_verified": True,
        "byte_for_byte_match": True,
    }


def parse_porcelain_v1_z(payload: bytes) -> list[dict[str, str]]:
    require(not payload or payload.endswith(b"\0"), "porcelain v1 -z payload is not NUL terminated")
    fields = payload.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    records: list[dict[str, str]] = []
    index = 0
    while index < len(fields):
        field = fields[index]
        require(len(field) >= 4 and field[2:3] == b" ", "malformed porcelain v1 -z record")
        xy = field[:2].decode("ascii", errors="strict")
        path = field[3:].decode("utf-8", errors="surrogateescape")
        record = {"status": xy, "path": path}
        index += 1
        if "R" in xy or "C" in xy:
            require(index < len(fields), "rename/copy porcelain record missing source path")
            record["source_path"] = fields[index].decode(
                "utf-8", errors="surrogateescape"
            )
            index += 1
        records.append(record)
    return records


def parse_name_status_z(payload: bytes) -> list[dict[str, str]]:
    require(not payload or payload.endswith(b"\0"), "name-status -z payload is not NUL terminated")
    fields = payload.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    records: list[dict[str, str]] = []
    index = 0
    while index < len(fields):
        status = fields[index].decode("ascii", errors="strict")
        require(status, "empty name-status code")
        index += 1
        require(index < len(fields), "name-status record missing path")
        path = fields[index].decode("utf-8", errors="surrogateescape")
        index += 1
        record = {"status": status, "path": path}
        if status.startswith(("R", "C")):
            require(index < len(fields), "rename/copy name-status missing destination")
            record["destination_path"] = fields[index].decode(
                "utf-8", errors="surrogateescape"
            )
            index += 1
        records.append(record)
    return records


def verify_wave(
    repo_root: Path,
    cleanup_manifest: Mapping[str, Any],
    wave: str,
    wave_parent: str,
) -> dict[str, Any]:
    require(wave in WAVE_ORDER, f"unknown wave: {wave}")
    require(
        git_text(repo_root, "rev-parse", "HEAD") == wave_parent,
        "current HEAD is not the clean arm-wave parent",
    )
    expected = {
        str(row["path"])
        for row in cleanup_manifest["files"]
        if row["wave"] == wave
    }
    status_bytes = _git(
        repo_root, "status", "--porcelain=v1", "-z", "-uall"
    ).stdout
    diff_bytes = _git(
        repo_root,
        "diff",
        "--name-status",
        "-z",
        "--no-renames",
        wave_parent,
    ).stdout
    status_rows = parse_porcelain_v1_z(status_bytes)
    diff_rows = parse_name_status_z(diff_bytes)
    require(
        all(row["status"] == " D" for row in status_rows),
        "status vector contains a non-worktree-deletion record",
    )
    require(
        all(row["status"] == "D" for row in diff_rows),
        "name-status vector contains a non-deletion record",
    )
    require(
        {row["path"] for row in status_rows} == expected,
        "status deletion set differs from current wave manifest",
    )
    require(
        {row["path"] for row in diff_rows} == expected,
        "name-status deletion set differs from current wave manifest",
    )
    status_vector_bytes, status_vector_sha = path_vector(
        row["path"] for row in status_rows
    )
    diff_vector_bytes, diff_vector_sha = path_vector(
        row["path"] for row in diff_rows
    )
    return {
        "schema_version": "r5_v1_manual_deletion_wave_validation_v1",
        "validation_id": "V-007",
        "decision": "pass",
        "wave": wave,
        "wave_parent_commit": wave_parent,
        "expected_file_count": len(expected),
        "status": {
            "raw_byte_count": len(status_bytes),
            "raw_sha256": hashlib.sha256(status_bytes).hexdigest(),
            "record_count": len(status_rows),
            "path_vector_byte_count": status_vector_bytes,
            "path_vector_sha256": status_vector_sha,
            "all_status_codes": [" D"],
        },
        "name_status": {
            "raw_byte_count": len(diff_bytes),
            "raw_sha256": hashlib.sha256(diff_bytes).hexdigest(),
            "record_count": len(diff_rows),
            "path_vector_byte_count": diff_vector_bytes,
            "path_vector_sha256": diff_vector_sha,
            "all_status_codes": ["D"],
        },
        "guards": {
            "rename_present": False,
            "untracked_present": False,
            "modification_present": False,
            "type_change_present": False,
            "unexpected_path_present": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build")
    validate = subparsers.add_parser("validate")
    validate.add_argument("--require-zero-active-references", action="store_true")
    validate.add_argument("--verify-each-cat-file", action="store_true")
    restore = subparsers.add_parser("verify-restore")
    restore.add_argument("--restore-root", type=Path, required=True)
    wave = subparsers.add_parser("verify-wave")
    wave.add_argument("--wave", choices=WAVE_ORDER, required=True)
    wave.add_argument("--wave-parent", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.repo_root.resolve()
    try:
        if args.command == "build":
            baseline, cleanup, receipt = build_documents(root)
            write_yaml_exact(root, BASELINE_MANIFEST_REL, baseline)
            write_yaml_exact(root, CLEANUP_MANIFEST_REL, cleanup)
            write_yaml_exact(root, DECOUPLING_RECEIPT_REL, receipt)
        elif args.command == "validate":
            receipt = validate_repository(
                root,
                require_zero_active_references=args.require_zero_active_references,
                verify_each_cat_file=args.verify_each_cat_file,
            )
            write_yaml_exact(root, DECOUPLING_RECEIPT_REL, receipt)
        elif args.command == "verify-restore":
            manifest = load_yaml(root / BASELINE_MANIFEST_REL)
            result = restore_all(root, args.restore_root, manifest)
            receipt = validate_repository(root, verify_each_cat_file=True)
            receipt["restore_verification"] = result
            if (
                receipt["active_reference_scan"]["reference_count"] == 0
                and receipt["active_reference_scan"][
                    "unknown_classification_count"
                ]
                == 0
            ):
                receipt["decision"] = "pass"
            write_yaml_exact(root, DECOUPLING_RECEIPT_REL, receipt)
        elif args.command == "verify-wave":
            cleanup = load_yaml(root / CLEANUP_MANIFEST_REL)
            receipt = verify_wave(root, cleanup, args.wave, args.wave_parent)
            write_yaml_exact(root, WAVE_RECEIPT_RELS[args.wave], receipt)
        else:  # pragma: no cover
            raise CleanupValidationError(f"unsupported command: {args.command}")
    except (CleanupValidationError, OSError, ValueError, yaml.YAMLError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.command == "verify-wave":
        print(f"decision=pass wave={args.wave}")
    elif args.command == "verify-restore":
        print(
            "decision=pass "
            f"files={result['file_count']} bytes={result['content_byte_count']}"
        )
    else:
        print(
            f"decision={receipt['decision']} "
            f"files={receipt['cleanup_inventory']['file_count']} "
            f"active_references={receipt['active_reference_scan']['reference_count']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
