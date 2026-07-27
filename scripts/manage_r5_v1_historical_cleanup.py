#!/usr/bin/env python3
"""Build and validate the R5 V1 historical-cleanup control plane.

This module inventories the frozen source tree, binds every proposed deletion to
a durable Git blob, restores blobs into a caller-owned temporary directory, and
validates NUL-delimited deletion vectors.  Its destructive surface rejects the
completed Night wave and accepts only the next v8-armed Bundle or old002837 wave.
It unlinks one validated literal regular file per operation and cannot stage or
commit changes.  After all 501 old002837 files have a validated deletion vector,
it may remove the frozen 29-row empty-directory manifest one literal directory
per non-recursive operation.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import os
import re
import stat
import subprocess
import sys
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

import yaml


CONTRACT_REL = Path(
    "docs/codex_tasks/v1_governance_integration_cleanup_v8/CONTRACT.md"
)
START_HERE_REL = Path(
    "docs/codex_tasks/v1_governance_integration_cleanup_v8/START_HERE.md"
)
AGENTS_REL = Path("AGENTS.md")
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
    "c8f19b03dd2fa17016bab3995eaa48fe8604bdb7e7027e5197aedcbfac01eb8b"
)
PACKAGE_SOURCE_BASELINE = "fe986a0359c0268ac94eea696c3a4795403e4614"
PACKAGE_SETUP_CHECKPOINT = "37d312b00bfbad33bf66a7e1a3169a9fd0559ad8"
DECOUPLING_CHECKPOINT = "805b8e3e9624e4e93057aa950cba4db1b3010cb3"
OLD_NIGHT_ARM_COMMIT = "82f7d37a10a9677af631c1a5863661a64df3270b"
COMPLETED_NIGHT_ARM_COMMIT = "e3b7ac48b784749e32252faf543c8d9ab796d830"
COMPLETED_NIGHT_DELETION_COMMIT = "be42857bf88223e01c71e4a4dfbac8e3a47080aa"
COMPLETED_NIGHT_EVIDENCE_COMMIT = "ada5ebff67e5604232463deb7effdcac1cd61d9e"
SUPERSEDED_BUNDLE_ARM_COMMIT = "a75ade4a74d620830860fa05723936502a58661a"
ARM_COMMIT_SUBJECTS = {
    "bundle": "chore(v1): arm bundle codex exact-file deletion checkpoint",
    "old002837": "chore(v1): arm 002837 codex exact-path deletion checkpoint",
}
ARM_SECTION_HEADINGS = {
    "bundle": "### P5 Bundle exact-manifest retained for next v8 arm",
    "old002837": "### P5 old002837 exact-path arm",
}
ARM_STATE_MARKER = "- Arm state: `armed_clean_checkpoint`"
EXPECTED_AGENTS_BLOB_OID = "e9619f0e919764ff092c0cfe3550a41b618b0ea2"
EXPECTED_AGENTS_BYTE_COUNT = 9605
EXPECTED_AGENTS_SHA256 = (
    "e79ccc75e02041be1aec6948206bad70405958753511e633fc0394c1eb0c5fbf"
)
HISTORICAL_SOURCE_SNAPSHOT = "312adc73821706b0b7ca6aa00e80ee608bd10b32"
ENGINEERING_SOURCE = "f60f220ae252262a537c612ce193fc779901984b"
NIGHT_SOURCE = "a96c1b717bf15905d72fd142efd946fa01bce666"
DEDICATED_WORKTREE_ROOT = Path(
    r"C:\Projects\03_Investment_System_v1_governance_cleanup"
)
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
WAVE_ACTORS = {
    "night": {
        "deletion_actor": "codex_exact_manifest_one_file_at_a_time",
        "codex_delete_authorized": True,
    },
    "bundle": {
        "deletion_actor": "codex_exact_manifest_one_file_at_a_time",
        "codex_delete_authorized": True,
    },
    "old002837": {
        "deletion_actor": "codex_exact_manifest_one_file_at_a_time",
        "codex_delete_authorized": True,
    },
}
REMAINING_CODEX_WAVES = ("bundle", "old002837")
OLD002837_DIRECTORY_ACTOR = {
    "deletion_actor": "codex_exact_manifest_one_empty_directory_at_a_time",
    "codex_delete_authorized": True,
}
OLD002837_DIRECTORIES = (
    f"{OLD_RUN_PREFIX}/data/processed/candidates",
    f"{OLD_RUN_PREFIX}/data/processed/layout",
    f"{OLD_RUN_PREFIX}/data/processed/logs",
    f"{OLD_RUN_PREFIX}/data/processed/normalized",
    f"{OLD_RUN_PREFIX}/data/processed/page_maps",
    f"{OLD_RUN_PREFIX}/data/processed/tables",
    f"{OLD_RUN_PREFIX}/data/processed/text",
    f"{OLD_RUN_PREFIX}/data/raw/annual_reports",
    f"{OLD_RUN_PREFIX}/data/raw/market_data",
    f"{OLD_RUN_PREFIX}/adapter_receipts/bundle8r",
    f"{OLD_RUN_PREFIX}/backups/r5_bundle5_pre_promotion_c7e2146bff39",
    f"{OLD_RUN_PREFIX}/data/manifests",
    f"{OLD_RUN_PREFIX}/data/processed",
    f"{OLD_RUN_PREFIX}/data/raw",
    f"{OLD_RUN_PREFIX}/adapter_receipts",
    f"{OLD_RUN_PREFIX}/adapter_runs",
    f"{OLD_RUN_PREFIX}/backups",
    f"{OLD_RUN_PREFIX}/bundle10_cross_industry_regression",
    f"{OLD_RUN_PREFIX}/bundle11r",
    f"{OLD_RUN_PREFIX}/bundle12r",
    f"{OLD_RUN_PREFIX}/bundle13r",
    f"{OLD_RUN_PREFIX}/bundle14r",
    f"{OLD_RUN_PREFIX}/bundle15r",
    f"{OLD_RUN_PREFIX}/data",
    f"{OLD_RUN_PREFIX}/fixtures",
    f"{OLD_RUN_PREFIX}/handoffs",
    f"{OLD_RUN_PREFIX}/reviewed_inputs_staging",
    f"{OLD_RUN_PREFIX}/valuation",
    OLD_RUN_PREFIX,
)
EXPECTED_OLD002837_DIRECTORY_VECTOR = {
    "path_count": 29,
    "path_vector_byte_count": 2208,
    "path_vector_sha256": (
        "1e987f07ab4aa9b7c54a7444b053949b5c5d377655903d9715d8948e42446cd3"
    ),
    "absolute_path_vector_byte_count": 3803,
    "absolute_path_vector_sha256": (
        "31669a8f873c2510709a7f9828b27dad4eab9fe49a159071d40345693e770b75"
    ),
}
EXPECTED_CLEANUP_AGGREGATE = {
    "file_count": 1386,
    "content_byte_count": 9787412,
    "path_vector_encoding": "ordinal_utf8_nul",
    "path_vector_byte_count": 121264,
    "path_vector_sha256": (
        "974d45610144d616f69c3c368d9ea1a0a27d66601a24f748aa8148e2ee702f33"
    ),
}
EXPECTED_WAVE_AGGREGATES = {
    "night": {
        "file_count": 680,
        "content_byte_count": 4480614,
        "path_vector_encoding": "ordinal_utf8_nul",
        "path_vector_byte_count": 55881,
        "path_vector_sha256": (
            "1ec2f42b84c1078f6b26caa377e9c1fb3efff9221196bc2e02bd819588a59c59"
        ),
    },
    "bundle": {
        "file_count": 205,
        "content_byte_count": 1770109,
        "path_vector_encoding": "ordinal_utf8_nul",
        "path_vector_byte_count": 13852,
        "path_vector_sha256": (
            "fc8912dfe6d20d92bd8fe907d4400ae90b724826a7c468ba5286232dc3b3363a"
        ),
    },
    "old002837": {
        "file_count": 501,
        "content_byte_count": 3536689,
        "path_vector_encoding": "ordinal_utf8_nul",
        "path_vector_byte_count": 51531,
        "path_vector_sha256": (
            "73d0a405b928fa3fa615d5b0d527f16f7c1182bb16239fb9ef89266d9868862f"
        ),
    },
}
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


def canonical_payload_sha256(payload: bytes) -> str:
    normalized = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def path_vector(paths: Iterable[str]) -> tuple[int, str]:
    payload = b"".join(
        path.encode("utf-8") + b"\0" for path in sorted(set(paths))
    )
    return len(payload), hashlib.sha256(payload).hexdigest()


def ordered_path_vector(paths: Sequence[str]) -> tuple[int, str]:
    values = [str(path) for path in paths]
    require(len(values) == len(set(values)), "ordered path vector has duplicates")
    payload = b"".join(path.encode("utf-8") + b"\0" for path in values)
    return len(payload), hashlib.sha256(payload).hexdigest()


def _absolute_manifest_path(repo_root: Path, relative_path: str) -> str:
    pure = _validate_repo_relative_literal(relative_path)
    root = repo_root.resolve(strict=True)
    target = root.joinpath(*pure.parts)
    require(target != root, "manifest path resolves to the repository root")
    require(
        target.resolve(strict=False).is_relative_to(root),
        f"manifest path escapes repository: {relative_path}",
    )
    return str(target.resolve(strict=False))


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


def _git_hash_object(repo_root: Path, payload: bytes) -> str:
    return _git(repo_root, "hash-object", "--stdin", input_bytes=payload).stdout.decode(
        "ascii", errors="strict"
    ).strip()


def _agents_identity(repo_root: Path, payload: bytes) -> dict[str, Any]:
    identity = {
        "path": AGENTS_REL.as_posix(),
        "blob_oid": _git_hash_object(repo_root, payload),
        "byte_count": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    require(
        identity["blob_oid"] == EXPECTED_AGENTS_BLOB_OID,
        f"root AGENTS blob drift: {identity['blob_oid']}",
    )
    require(
        identity["byte_count"] == EXPECTED_AGENTS_BYTE_COUNT,
        f"root AGENTS byte count drift: {identity['byte_count']}",
    )
    require(
        identity["sha256"] == EXPECTED_AGENTS_SHA256,
        f"root AGENTS SHA-256 drift: {identity['sha256']}",
    )
    return identity


def verify_root_agents(
    repo_root: Path, *, revision: str | None = None
) -> dict[str, Any]:
    payload = (
        git_blob(repo_root, revision, AGENTS_REL.as_posix())
        if revision is not None
        else (repo_root / AGENTS_REL).read_bytes()
    )
    return _agents_identity(repo_root, payload)


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


def verify_committed_contract(repo_root: Path, revision: str) -> dict[str, str]:
    payload = git_blob(repo_root, revision, CONTRACT_REL.as_posix())
    observed = canonical_payload_sha256(payload)
    require(
        observed == EXPECTED_CONTRACT_SHA256,
        f"committed frozen contract SHA-256 drift: {observed}",
    )
    text = payload.decode("utf-8", errors="strict")
    require('status: "frozen"' in text, "committed contract is not frozen")
    require(
        f'source_baseline: "{PACKAGE_SOURCE_BASELINE}"' in text,
        "committed contract package baseline drift",
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
        source = git_blob(repo_root, DECOUPLING_CHECKPOINT, relative).decode(
            "utf-8", errors="strict"
        )
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
                "source_commit": DECOUPLING_CHECKPOINT,
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


def build_old002837_directory_manifest(repo_root: Path) -> dict[str, Any]:
    paths = list(OLD002837_DIRECTORIES)
    require(
        len(paths) == EXPECTED_OLD002837_DIRECTORY_VECTOR["path_count"],
        "old002837 directory count drift",
    )
    for path in paths:
        pure = _validate_repo_relative_literal(path)
        require(
            path == OLD_RUN_PREFIX or path.startswith(OLD_RUN_PREFIX + "/"),
            f"directory path escapes old002837 root: {path}",
        )
        require(
            pure.as_posix() != ".",
            "directory manifest contains the repository root",
        )

    position = {path: index for index, path in enumerate(paths)}
    for child in paths:
        parent = PurePosixPath(child).parent
        while parent.as_posix() != ".":
            parent_text = parent.as_posix()
            if parent_text in position:
                require(
                    position[child] < position[parent_text],
                    f"directory manifest is not deepest-first: {child}",
                )
            parent = parent.parent

    relative_bytes, relative_sha = ordered_path_vector(paths)
    require(
        relative_bytes
        == EXPECTED_OLD002837_DIRECTORY_VECTOR["path_vector_byte_count"],
        "old002837 relative directory-vector byte count drift",
    )
    require(
        relative_sha
        == EXPECTED_OLD002837_DIRECTORY_VECTOR["path_vector_sha256"],
        "old002837 relative directory-vector SHA-256 drift",
    )

    dedicated_root = DEDICATED_WORKTREE_ROOT
    absolute_paths = [
        str(dedicated_root.joinpath(*PurePosixPath(path).parts))
        for path in paths
    ]
    absolute_bytes, absolute_sha = ordered_path_vector(absolute_paths)
    require(
        absolute_bytes
        == EXPECTED_OLD002837_DIRECTORY_VECTOR[
            "absolute_path_vector_byte_count"
        ],
        "old002837 absolute directory-vector byte count drift",
    )
    require(
        absolute_sha
        == EXPECTED_OLD002837_DIRECTORY_VECTOR["absolute_path_vector_sha256"],
        "old002837 absolute directory-vector SHA-256 drift",
    )
    return {
        "wave": "old002837",
        **OLD002837_DIRECTORY_ACTOR,
        "root": OLD_RUN_PREFIX,
        "dedicated_worktree_root": str(dedicated_root),
        "order": "deepest_first",
        "removal_mode": "one_literal_empty_non_reparse_directory_non_recursive",
        "preconditions": [
            "old002837_file_deletion_vector_complete_501",
            "git_vectors_unchanged_before_and_after_each_directory",
            "processed_ordinal_prefix_absent",
            "remaining_ordinal_suffix_present",
            "complete_entry_enumeration_matches_remaining_directory_suffix",
            "all_existing_path_components_non_reparse",
            "current_directory_empty",
        ],
        "aggregate": {
            "directory_count": len(paths),
            "path_vector_encoding": "deepest_first_utf8_nul",
            "path_vector_byte_count": relative_bytes,
            "path_vector_sha256": relative_sha,
            "absolute_path_vector_byte_count": absolute_bytes,
            "absolute_path_vector_sha256": absolute_sha,
        },
        "paths": paths,
        "absolute_paths": absolute_paths,
    }


def build_documents(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    contract = verify_contract(repo_root)
    agents_identity = verify_root_agents(repo_root)
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
    wave_ordinals: defaultdict[str, int] = defaultdict(int)
    for path, wave in inventory.items():
        baseline = by_path[path]
        wave_ordinals[wave] += 1
        actor = WAVE_ACTORS[wave]
        reference_count = sum(
            _reference_applies(reference, path, wave)
            for reference in active_scan["references"]
        )
        cleanup_rows.append(
            {
                "path": path,
                "wave": wave,
                "wave_ordinal": wave_ordinals[wave],
                **actor,
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
                    "codex_unlinks_only_this_exact_literal_regular_file",
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
                **WAVE_ACTORS[wave],
                "aggregate": _aggregate(wave_rows),
                "paths": [str(row["path"]) for row in wave_rows],
            }
        )
    cleanup_manifest = {
        "schema_version": "r5_v1_historical_cleanup_manifest_v1",
        "contract": contract,
        "source_snapshot": HISTORICAL_SOURCE_SNAPSHOT,
        "deletion_actor": "wave_specific",
        "codex_delete_authorized": False,
        "authorization_scope": "wave_specific_only",
        "wave_order": list(WAVE_ORDER),
        "aggregate": _aggregate(cleanup_rows),
        "waves": wave_documents,
        "old002837_empty_directory_cleanup": build_old002837_directory_manifest(
            repo_root
        ),
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
        "deletion_control": {
            "root_agents": agents_identity,
            "wave_actors": {
                wave: dict(WAVE_ACTORS[wave]) for wave in WAVE_ORDER
            },
            "file_delete_surface": {
                "command": "delete-wave",
                "eligible_waves": list(REMAINING_CODEX_WAVES),
                "completed_night_rejected": True,
                "single_literal_path_per_unlink": True,
                "ordinal_prefix_resume_only": True,
                "head_and_index_blob_match_manifest": True,
                "rejects_stage_and_commit": True,
                "writes_receipt_only_after_complete_vector_validation": True,
            },
            "old002837_directory_surface": {
                "command": "delete-wave",
                "requires_complete_501_file_deletion_vector": True,
                "single_literal_directory_per_non_recursive_removal": True,
                "deepest_first_prefix_suffix_resume_only": True,
                "requires_empty_non_reparse_directory": True,
                "complete_entry_enumeration": True,
                "git_vectors_unchanged_per_directory": True,
                "rejects_stage_and_commit": True,
            },
        },
        "restore_verification": {
            "cat_file_e_verified": False,
            "content_hash_verified": False,
            "full_restore_verified": False,
            "note": "Set by validate/verify-restore; build does not claim a restore run.",
        },
        "guards": {
            "codex_delete_command_exists": True,
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


def load_yaml_payload(payload: bytes, label: str) -> dict[str, Any]:
    value = yaml.safe_load(payload.decode("utf-8", errors="strict"))
    require(isinstance(value, dict), f"{label}: YAML root must be an object")
    return value


def load_committed_yaml(repo_root: Path, revision: str, relative: Path) -> dict[str, Any]:
    return load_yaml_payload(
        git_blob(repo_root, revision, relative.as_posix()),
        f"{revision}:{relative.as_posix()}",
    )


def validate_actor_bindings(cleanup_manifest: Mapping[str, Any]) -> None:
    require(
        cleanup_manifest.get("deletion_actor") == "wave_specific",
        "cleanup manifest deletion actor is not wave-specific",
    )
    require(
        cleanup_manifest.get("codex_delete_authorized") is False,
        "cleanup manifest grants blanket Codex deletion authority",
    )
    require(
        cleanup_manifest.get("authorization_scope") == "wave_specific_only",
        "cleanup manifest authorization scope drift",
    )
    waves = list(cleanup_manifest.get("waves", []))
    require(
        [wave.get("wave") for wave in waves] == list(WAVE_ORDER),
        "cleanup wave order drift",
    )
    for wave_document in waves:
        wave = str(wave_document["wave"])
        expected_actor = WAVE_ACTORS[wave]
        for key, value in expected_actor.items():
            require(
                wave_document.get(key) == value,
                f"{wave}: wave actor/authorization drift for {key}",
            )

    ordinal_by_wave: defaultdict[str, int] = defaultdict(int)
    for row in cleanup_manifest.get("files", []):
        wave = str(row.get("wave"))
        require(wave in WAVE_ORDER, f"unknown cleanup row wave: {wave}")
        ordinal_by_wave[wave] += 1
        require(
            row.get("wave_ordinal") == ordinal_by_wave[wave],
            f"{row.get('path')}: non-contiguous wave ordinal",
        )
        expected_actor = WAVE_ACTORS[wave]
        for key, value in expected_actor.items():
            require(
                row.get(key) == value,
                f"{row.get('path')}: row actor/authorization drift for {key}",
            )
        expected_last_precondition = (
            "codex_unlinks_only_this_exact_literal_regular_file"
        )
        require(
            row.get("deletion_preconditions")
            == [
                "active_reference_count_equals_zero",
                "baseline_blob_and_full_restore_verified",
                "current_wave_armed_in_start_here",
                expected_last_precondition,
            ],
            f"{row.get('path')}: deletion preconditions drift",
        )


def validate_old002837_directory_manifest(
    repo_root: Path, cleanup_manifest: Mapping[str, Any]
) -> dict[str, Any]:
    expected = build_old002837_directory_manifest(repo_root)
    observed = cleanup_manifest.get("old002837_empty_directory_cleanup")
    require(
        observed == expected,
        "old002837 empty-directory manifest differs from the frozen v8 vector",
    )
    file_paths = {
        str(row.get("path")) for row in cleanup_manifest.get("files", [])
    }
    require(
        file_paths.isdisjoint(expected["paths"]),
        "directory manifest path leaked into the file manifest",
    )
    wave_paths = {
        str(path)
        for wave in cleanup_manifest.get("waves", [])
        for path in wave.get("paths", [])
    }
    require(
        wave_paths.isdisjoint(expected["paths"]),
        "directory manifest path leaked into a wave file vector",
    )
    return expected


def validate_fixed_cleanup_aggregates(cleanup_manifest: Mapping[str, Any]) -> None:
    require(
        cleanup_manifest.get("aggregate") == EXPECTED_CLEANUP_AGGREGATE,
        "cleanup aggregate differs from the frozen v8 file aggregate",
    )
    waves = list(cleanup_manifest.get("waves", []))
    require(len(waves) == len(WAVE_ORDER), "cleanup wave document count drift")
    for order, (wave, wave_document) in enumerate(zip(WAVE_ORDER, waves), start=1):
        require(wave_document.get("wave") == wave, f"{wave}: wave name drift")
        require(wave_document.get("order") == order, f"{wave}: wave order drift")
        require(
            wave_document.get("aggregate") == EXPECTED_WAVE_AGGREGATES[wave],
            f"{wave}: frozen aggregate drift",
        )


def _validate_repo_relative_literal(path: str) -> PurePosixPath:
    pure = PurePosixPath(path)
    require(path == pure.as_posix(), f"non-canonical repo-relative path: {path}")
    require(not pure.is_absolute(), f"absolute manifest path: {path}")
    require(".." not in pure.parts, f"escaping manifest path: {path}")
    require("\\" not in path, f"backslash in manifest path: {path}")
    require(
        not any(token in path for token in ("*", "?", "[", "]", "{", "}")),
        f"wildcard token in manifest path: {path}",
    )
    return pure


def _validate_baseline_row(repo_root: Path, row: Mapping[str, Any]) -> None:
    path = str(row["path"])
    _validate_repo_relative_literal(path)
    revision = str(row["baseline_commit"])
    require(
        revision in {NIGHT_SOURCE, ENGINEERING_SOURCE},
        f"{path}: unapproved durable baseline",
    )
    require(
        row.get("cat_file_spec") == f"{revision}:{path}",
        f"{path}: cat-file spec drift",
    )
    require(
        row.get("restore_command") == _restore_command(revision, path),
        f"{path}: restore command drift",
    )
    payload = git_blob(repo_root, revision, path)
    require(len(payload) == row.get("byte_count"), f"{path}: byte count mismatch")
    require(
        hashlib.sha256(payload).hexdigest() == row.get("content_sha256"),
        f"{path}: content SHA-256 mismatch",
    )
    require(
        git_blob_oid(repo_root, revision, path) == row.get("blob_oid"),
        f"{path}: blob OID mismatch",
    )


def _markdown_section(text: str, heading: str) -> str:
    lines = text.splitlines()
    try:
        start = lines.index(heading)
    except ValueError as exc:
        raise CleanupValidationError(f"missing START section: {heading}") from exc
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("### "):
            end = index
            break
    return "\n".join(lines[start:end])


def _absolute_list_after_subheading(section: str, subheading: str) -> list[str]:
    lines = section.splitlines()
    try:
        start = lines.index(subheading)
    except ValueError as exc:
        raise CleanupValidationError(
            f"missing START manifest subheading: {subheading}"
        ) from exc
    values: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("#### "):
            break
        match = re.fullmatch(r"(?:-|\d+\.) `([^`]+)`", line)
        if match:
            values.append(match.group(1))
    return values


def _relative_values_from_absolute_start_paths(
    repo_root: Path, absolute_values: Sequence[str], *, label: str
) -> list[str]:
    root = repo_root.resolve(strict=True)
    values: list[str] = []
    for value in absolute_values:
        absolute = Path(value)
        require(absolute.is_absolute(), f"{label} path is not absolute: {value}")
        resolved = absolute.resolve(strict=False)
        require(
            resolved.is_relative_to(root),
            f"{label} path escapes the dedicated worktree: {value}",
        )
        values.append(resolved.relative_to(root).as_posix())
    return values


def validate_wave_arm_identity(
    repo_root: Path,
    revision: str,
    wave: str,
    expected_paths: Sequence[str],
    directory_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    require(
        wave in REMAINING_CODEX_WAVES,
        f"completed or unauthorized wave cannot be armed: {wave}",
    )
    require(
        revision != SUPERSEDED_BUNDLE_ARM_COMMIT,
        "the superseded v7 Bundle manual arm cannot be reused",
    )
    subject = git_text(repo_root, "show", "-s", "--format=%s", revision)
    require(
        subject == ARM_COMMIT_SUBJECTS[wave],
        f"{wave} wave parent commit subject is not the exact v8 arm checkpoint: {subject}",
    )
    payload = git_blob(repo_root, revision, START_HERE_REL.as_posix())
    text = payload.decode("utf-8", errors="strict")
    for literal in (
        'task_id: "v1_governance_integration_cleanup_v8"',
        f'contract_sha256: "{EXPECTED_CONTRACT_SHA256}"',
        f'source_baseline: "{PACKAGE_SOURCE_BASELINE}"',
        'state: "running"',
    ):
        require(literal in text, f"committed v8 START identity drift: {literal}")

    section = _markdown_section(text, ARM_SECTION_HEADINGS[wave])
    for literal in (
        f"- Wave: `{wave}`",
        ARM_STATE_MARKER,
        "- Contract deletion actor: `codex_exact_manifest_one_file_at_a_time`",
        "- Contract Codex deletion authorization: `true`",
        f"- Expected deletion count: {len(expected_paths)}",
        EXPECTED_WAVE_AGGREGATES[wave]["path_vector_sha256"],
    ):
        require(literal in section, f"committed v8 START lacks {wave} arm marker: {literal}")

    file_heading = (
        "#### Bundle exact absolute per-file manifest"
        if wave == "bundle"
        else "#### old002837 exact absolute per-file manifest"
    )
    absolute_values = _absolute_list_after_subheading(section, file_heading)
    relative_values = _relative_values_from_absolute_start_paths(
        repo_root, absolute_values, label=f"START {wave} file"
    )
    require(
        relative_values == list(expected_paths),
        f"committed v8 START {wave} file list differs from the ordinal cleanup manifest",
    )
    vector_bytes, vector_sha = path_vector(relative_values)
    require(
        vector_bytes == EXPECTED_WAVE_AGGREGATES[wave]["path_vector_byte_count"],
        f"committed v8 START {wave} file-vector byte count drift",
    )
    require(
        vector_sha == EXPECTED_WAVE_AGGREGATES[wave]["path_vector_sha256"],
        f"committed v8 START {wave} file-vector SHA-256 drift",
    )

    identity: dict[str, Any] = {
        "path": START_HERE_REL.as_posix(),
        "commit_subject": subject,
        "arm_state": "armed_clean_checkpoint",
        "path_count": len(relative_values),
        "path_vector_byte_count": vector_bytes,
        "path_vector_sha256": vector_sha,
    }
    if wave == "old002837":
        require(directory_manifest is not None, "old002837 arm lacks directory manifest")
        for literal in (
            "- Expected empty-directory count: 29",
            EXPECTED_OLD002837_DIRECTORY_VECTOR["path_vector_sha256"],
            EXPECTED_OLD002837_DIRECTORY_VECTOR["absolute_path_vector_sha256"],
        ):
            require(
                literal in section,
                f"committed v8 START lacks old002837 directory marker: {literal}",
            )
        directory_values = _absolute_list_after_subheading(
            section, "#### old002837 exact absolute directory manifest"
        )
        expected_absolute = list(directory_manifest["absolute_paths"])
        require(
            directory_values == expected_absolute,
            "committed v8 START old002837 directory list differs from the manifest",
        )
        directory_relative = _relative_values_from_absolute_start_paths(
            repo_root,
            directory_values,
            label="START old002837 directory",
        )
        require(
            directory_relative == list(directory_manifest["paths"]),
            "committed v8 START old002837 relative directory order drift",
        )
        directory_bytes, directory_sha = ordered_path_vector(directory_relative)
        absolute_bytes, absolute_sha = ordered_path_vector(directory_values)
        require(
            directory_bytes
            == EXPECTED_OLD002837_DIRECTORY_VECTOR["path_vector_byte_count"]
            and directory_sha
            == EXPECTED_OLD002837_DIRECTORY_VECTOR["path_vector_sha256"],
            "committed v8 START old002837 relative directory vector drift",
        )
        require(
            absolute_bytes
            == EXPECTED_OLD002837_DIRECTORY_VECTOR[
                "absolute_path_vector_byte_count"
            ]
            and absolute_sha
            == EXPECTED_OLD002837_DIRECTORY_VECTOR[
                "absolute_path_vector_sha256"
            ],
            "committed v8 START old002837 absolute directory vector drift",
        )
        identity["directory_manifest"] = {
            "directory_count": len(directory_values),
            "path_vector_byte_count": directory_bytes,
            "path_vector_sha256": directory_sha,
            "absolute_path_vector_byte_count": absolute_bytes,
            "absolute_path_vector_sha256": absolute_sha,
        }
    return identity


def _require_ancestor(repo_root: Path, ancestor: str, descendant: str, label: str) -> None:
    require(
        _git(
            repo_root,
            "merge-base",
            "--is-ancestor",
            ancestor,
            descendant,
            check=False,
        ).returncode
        == 0,
        f"{label} is not an ancestor of the wave parent",
    )


def _latest_commit_for_path(repo_root: Path, revision: str, relative: Path) -> tuple[str, str]:
    payload = git_text(
        repo_root,
        "log",
        "-1",
        "--format=%H%x00%s",
        revision,
        "--",
        relative.as_posix(),
    )
    commit, separator, subject = payload.partition("\0")
    require(separator == "\0" and commit and subject, f"missing path history: {relative}")
    return commit, subject


def _require_paths_absent(
    repo_root: Path, paths: Sequence[str], *, label: str
) -> None:
    root = repo_root.resolve(strict=True)
    present = [
        path
        for path in paths
        if os.path.lexists(root.joinpath(*PurePosixPath(path).parts))
    ]
    require(not present, f"{label} paths unexpectedly present: {present[:3]}")


def _validate_completed_night(
    repo_root: Path, head: str, night_paths: Sequence[str]
) -> dict[str, Any]:
    _require_ancestor(
        repo_root, COMPLETED_NIGHT_ARM_COMMIT, head, "completed Night arm"
    )
    _require_ancestor(
        repo_root,
        COMPLETED_NIGHT_DELETION_COMMIT,
        head,
        "completed Night deletion",
    )
    _require_ancestor(
        repo_root,
        COMPLETED_NIGHT_EVIDENCE_COMMIT,
        head,
        "completed Night evidence",
    )
    receipt = load_committed_yaml(repo_root, head, WAVE_RECEIPT_RELS["night"])
    require(receipt.get("decision") == "pass", "completed Night receipt is not pass")
    require(receipt.get("wave") == "night", "completed Night receipt wave drift")
    require(
        receipt.get("wave_parent_commit") == COMPLETED_NIGHT_ARM_COMMIT,
        "completed Night receipt arm drift",
    )
    require(
        receipt.get("deletion_actor")
        == WAVE_ACTORS["night"]["deletion_actor"]
        and receipt.get("codex_delete_authorized") is True,
        "completed Night receipt actor drift",
    )
    require(
        receipt.get("expected_file_count") == len(night_paths) == 680,
        "completed Night receipt count drift",
    )
    require(
        receipt.get("status", {}).get("path_vector_sha256")
        == EXPECTED_WAVE_AGGREGATES["night"]["path_vector_sha256"],
        "completed Night receipt file vector drift",
    )
    latest_commit, latest_subject = _latest_commit_for_path(
        repo_root, head, WAVE_RECEIPT_RELS["night"]
    )
    require(
        latest_commit == COMPLETED_NIGHT_DELETION_COMMIT,
        "completed Night receipt was rewritten after its deletion commit",
    )
    require(
        latest_subject == "chore(v1): remove retired night workflow history",
        "completed Night receipt commit subject drift",
    )
    _require_paths_absent(repo_root, night_paths, label="completed Night")
    return {
        "arm_commit": COMPLETED_NIGHT_ARM_COMMIT,
        "deletion_commit": COMPLETED_NIGHT_DELETION_COMMIT,
        "evidence_commit": COMPLETED_NIGHT_EVIDENCE_COMMIT,
        "receipt": receipt,
    }


def _validate_prior_bundle_completion(
    repo_root: Path, head: str, bundle_paths: Sequence[str]
) -> dict[str, Any]:
    receipt = load_committed_yaml(repo_root, head, WAVE_RECEIPT_RELS["bundle"])
    require(receipt.get("decision") == "pass", "Bundle receipt is not pass")
    require(receipt.get("wave") == "bundle", "Bundle receipt wave drift")
    require(
        receipt.get("deletion_actor") == WAVE_ACTORS["bundle"]["deletion_actor"]
        and receipt.get("codex_delete_authorized") is True,
        "Bundle receipt actor drift",
    )
    require(
        receipt.get("expected_file_count") == len(bundle_paths) == 205,
        "Bundle receipt count drift",
    )
    require(
        receipt.get("status", {}).get("path_vector_sha256")
        == EXPECTED_WAVE_AGGREGATES["bundle"]["path_vector_sha256"],
        "Bundle receipt file vector drift",
    )
    arm_commit = str(receipt.get("wave_parent_commit"))
    _require_ancestor(repo_root, arm_commit, head, "Bundle arm")
    require(
        git_text(repo_root, "show", "-s", "--format=%s", arm_commit)
        == ARM_COMMIT_SUBJECTS["bundle"],
        "Bundle receipt references a non-v8 arm",
    )
    latest_commit, latest_subject = _latest_commit_for_path(
        repo_root, head, WAVE_RECEIPT_RELS["bundle"]
    )
    require(
        latest_subject == "chore(v1): remove retired bundle workflow history",
        "Bundle receipt was not committed by the exact deletion checkpoint",
    )
    _require_ancestor(repo_root, latest_commit, head, "Bundle deletion")
    _require_paths_absent(repo_root, bundle_paths, label="completed Bundle")
    return {
        "arm_commit": arm_commit,
        "deletion_commit": latest_commit,
        "receipt": receipt,
    }


def validate_committed_control_plane(
    repo_root: Path, wave: str, wave_parent: str
) -> dict[str, Any]:
    require(
        wave in REMAINING_CODEX_WAVES,
        f"completed or unauthorized wave cannot enter delete surface: {wave}",
    )
    head = git_text(repo_root, "rev-parse", "HEAD")
    require(head == wave_parent, "current HEAD is not the supplied wave parent")
    require(
        head not in {OLD_NIGHT_ARM_COMMIT, SUPERSEDED_BUNDLE_ARM_COMMIT},
        "a superseded arm checkpoint cannot be reused",
    )
    require(
        repo_root.resolve(strict=True)
        == DEDICATED_WORKTREE_ROOT.resolve(strict=True),
        "delete surface is not running in the dedicated worktree",
    )
    _require_ancestor(repo_root, PACKAGE_SOURCE_BASELINE, head, "v8 package baseline")
    _require_ancestor(repo_root, PACKAGE_SETUP_CHECKPOINT, head, "v8 package setup")
    _require_ancestor(
        repo_root, DECOUPLING_CHECKPOINT, head, "historical decoupling checkpoint"
    )

    contract = verify_committed_contract(repo_root, head)
    agents_identity = verify_root_agents(repo_root, revision=head)
    baseline = load_committed_yaml(repo_root, head, BASELINE_MANIFEST_REL)
    cleanup = load_committed_yaml(repo_root, head, CLEANUP_MANIFEST_REL)
    receipt = load_committed_yaml(repo_root, head, DECOUPLING_RECEIPT_REL)

    for document, label in ((baseline, "baseline"), (cleanup, "cleanup")):
        require(document.get("contract") == contract, f"{label} contract identity drift")
        require(
            document.get("source_snapshot") == HISTORICAL_SOURCE_SNAPSHOT,
            f"{label} historical source snapshot drift",
        )
    require(
        baseline.get("aggregate") == EXPECTED_CLEANUP_AGGREGATE,
        "baseline aggregate differs from the frozen v8 file aggregate",
    )
    validate_fixed_cleanup_aggregates(cleanup)
    validate_actor_bindings(cleanup)
    directory_manifest = validate_old002837_directory_manifest(repo_root, cleanup)

    baseline_rows = list(baseline.get("files", []))
    cleanup_rows = list(cleanup.get("files", []))
    baseline_paths = [str(row["path"]) for row in baseline_rows]
    cleanup_paths = [str(row["path"]) for row in cleanup_rows]
    require(baseline_paths == sorted(baseline_paths), "baseline rows are not ordinal")
    require(cleanup_paths == sorted(cleanup_paths), "cleanup rows are not ordinal")
    require(
        len(baseline_paths) == len(set(baseline_paths)) == 1386,
        "baseline path count/uniqueness drift",
    )
    require(baseline_paths == cleanup_paths, "baseline/cleanup path vectors differ")
    baseline_by_path = {str(row["path"]): row for row in baseline_rows}
    rows_by_wave = {
        candidate: [
            row for row in cleanup_rows if str(row.get("wave")) == candidate
        ]
        for candidate in WAVE_ORDER
    }
    for candidate, expected_count in (("night", 680), ("bundle", 205), ("old002837", 501)):
        require(
            len(rows_by_wave[candidate]) == expected_count,
            f"{candidate} cleanup row count drift",
        )
    for cleanup_row in cleanup_rows:
        path = str(cleanup_row["path"])
        _validate_repo_relative_literal(path)
        baseline_row = baseline_by_path[path]
        for key in (
            "baseline_commit",
            "blob_oid",
            "byte_count",
            "content_sha256",
            "restore_command",
        ):
            require(
                cleanup_row.get(key) == baseline_row.get(key),
                f"{path}: cleanup/baseline {key} drift",
            )
        require(
            cleanup_row.get("active_reference_count") == 0,
            f"{path}: active references are not zero",
        )
    for cleanup_row in rows_by_wave[wave]:
        _validate_baseline_row(repo_root, baseline_by_path[str(cleanup_row["path"])])

    require(receipt.get("contract") == contract, "decoupling receipt contract drift")
    require(receipt.get("decision") == "pass", "decoupling receipt is not pass")
    require(
        {
            key: receipt.get("cleanup_inventory", {}).get(key)
            for key in EXPECTED_CLEANUP_AGGREGATE
        }
        == EXPECTED_CLEANUP_AGGREGATE,
        "decoupling receipt cleanup aggregate drift",
    )
    active_scan = receipt.get("active_reference_scan", {})
    require(active_scan.get("reference_count") == 0, "receipt active references remain")
    require(
        active_scan.get("unknown_classification_count") == 0,
        "receipt unknown classifications remain",
    )
    restore = receipt.get("restore_verification", {})
    for key in (
        "cat_file_e_verified",
        "content_hash_verified",
        "full_restore_verified",
        "byte_for_byte_match",
    ):
        require(restore.get(key) is True, f"receipt restore guard is not true: {key}")
    require(restore.get("file_count") == 1386, "receipt restore file count drift")
    require(
        restore.get("content_byte_count") == 9787412,
        "receipt restore content byte count drift",
    )
    deletion_control = receipt.get("deletion_control", {})
    require(
        deletion_control.get("root_agents") == agents_identity,
        "receipt root AGENTS identity drift",
    )
    require(
        deletion_control.get("wave_actors")
        == {candidate: dict(WAVE_ACTORS[candidate]) for candidate in WAVE_ORDER},
        "receipt wave actor bindings drift",
    )
    require(
        deletion_control.get("file_delete_surface")
        == {
            "command": "delete-wave",
            "eligible_waves": list(REMAINING_CODEX_WAVES),
            "completed_night_rejected": True,
            "single_literal_path_per_unlink": True,
            "ordinal_prefix_resume_only": True,
            "head_and_index_blob_match_manifest": True,
            "rejects_stage_and_commit": True,
            "writes_receipt_only_after_complete_vector_validation": True,
        },
        "receipt file delete-surface guards drift",
    )
    require(
        deletion_control.get("old002837_directory_surface")
        == {
            "command": "delete-wave",
            "requires_complete_501_file_deletion_vector": True,
            "single_literal_directory_per_non_recursive_removal": True,
            "deepest_first_prefix_suffix_resume_only": True,
            "requires_empty_non_reparse_directory": True,
            "complete_entry_enumeration": True,
            "git_vectors_unchanged_per_directory": True,
            "rejects_stage_and_commit": True,
        },
        "receipt old002837 directory-surface guards drift",
    )

    night_completion = _validate_completed_night(
        repo_root,
        head,
        [str(row["path"]) for row in rows_by_wave["night"]],
    )
    prior_bundle = None
    if wave == "old002837":
        prior_bundle = _validate_prior_bundle_completion(
            repo_root,
            head,
            [str(row["path"]) for row in rows_by_wave["bundle"]],
        )
    arm = validate_wave_arm_identity(
        repo_root,
        head,
        wave,
        [str(row["path"]) for row in rows_by_wave[wave]],
        directory_manifest if wave == "old002837" else None,
    )
    return {
        "contract": contract,
        "root_agents": agents_identity,
        "arm": arm,
        "baseline": baseline,
        "cleanup": cleanup,
        "receipt": receipt,
        "wave_rows": rows_by_wave[wave],
        "night_completion": night_completion,
        "prior_bundle": prior_bundle,
        "directory_manifest": directory_manifest,
    }


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
    verify_root_agents(repo_root)
    validate_fixed_cleanup_aggregates(cleanup_manifest)
    validate_actor_bindings(cleanup_manifest)
    validate_old002837_directory_manifest(repo_root, cleanup_manifest)
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


def capture_deletion_vectors(
    repo_root: Path, wave_parent: str
) -> tuple[bytes, bytes, bytes]:
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
        "--",
    ).stdout
    cached_bytes = _git(
        repo_root,
        "diff",
        "--cached",
        "--name-status",
        "-z",
        "--no-renames",
        wave_parent,
        "--",
    ).stdout
    return status_bytes, diff_bytes, cached_bytes


def validate_deletion_prefix_vectors(
    status_bytes: bytes,
    diff_bytes: bytes,
    cached_bytes: bytes,
    expected_paths: Sequence[str],
    *,
    require_complete: bool = False,
) -> dict[str, Any]:
    expected = [str(path) for path in expected_paths]
    require(expected == sorted(expected), "expected deletion vector is not ordinal")
    require(len(expected) == len(set(expected)), "expected deletion vector has duplicates")
    require(not cached_bytes, "index contains staged changes")
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
    status_paths = sorted(str(row["path"]) for row in status_rows)
    diff_paths = sorted(str(row["path"]) for row in diff_rows)
    require(
        len(status_paths) == len(set(status_paths)),
        "status deletion vector contains duplicates",
    )
    require(
        len(diff_paths) == len(set(diff_paths)),
        "name-status deletion vector contains duplicates",
    )
    require(status_paths == diff_paths, "status/name-status deletion vectors differ")
    expected_prefix = expected[: len(status_paths)]
    require(
        status_paths == expected_prefix,
        "current deletion set is not an exact ordinal manifest prefix",
    )
    if require_complete:
        require(
            len(status_paths) == len(expected),
            "deletion vector is not the complete wave manifest",
        )
    vector_bytes, vector_sha = path_vector(status_paths)
    return {
        "prefix_count": len(status_paths),
        "complete": len(status_paths) == len(expected),
        "status_rows": status_rows,
        "diff_rows": diff_rows,
        "path_vector_byte_count": vector_bytes,
        "path_vector_sha256": vector_sha,
        "status_raw_byte_count": len(status_bytes),
        "status_raw_sha256": hashlib.sha256(status_bytes).hexdigest(),
        "name_status_raw_byte_count": len(diff_bytes),
        "name_status_raw_sha256": hashlib.sha256(diff_bytes).hexdigest(),
    }


def _is_reparse_stat(value: Any) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(value, "st_file_attributes", 0) & reparse_flag)


def validate_manifest_git_identity(
    repo_root: Path,
    relative_path: str,
    expected_blob_oid: str,
    *,
    revision: str = "HEAD",
) -> None:
    _validate_repo_relative_literal(relative_path)
    stage = _git(
        repo_root,
        "ls-files",
        "--stage",
        "-z",
        "--",
        relative_path,
        check=False,
    )
    require(stage.returncode == 0 and stage.stdout, f"untracked deletion target: {relative_path}")
    records = [field for field in stage.stdout.split(b"\0") if field]
    require(len(records) == 1, f"ambiguous tracked target: {relative_path}")
    prefix, separator, encoded_path = records[0].partition(b"\t")
    require(separator == b"\t", f"malformed index entry: {relative_path}")
    prefix_fields = prefix.split(b" ")
    require(len(prefix_fields) == 3, f"malformed index metadata: {relative_path}")
    mode, index_oid_bytes, stage_bytes = prefix_fields
    require(mode in {b"100644", b"100755"}, f"non-regular index mode: {relative_path}")
    require(stage_bytes == b"0", f"non-zero index stage: {relative_path}")
    require(
        encoded_path.decode("utf-8", errors="surrogateescape") == relative_path,
        f"index path identity drift: {relative_path}",
    )
    index_oid = index_oid_bytes.decode("ascii", errors="strict")
    require(
        index_oid == expected_blob_oid,
        f"index blob OID drift: {relative_path}",
    )
    head_oid = git_blob_oid(repo_root, revision, relative_path)
    require(
        head_oid == expected_blob_oid,
        f"{revision} blob OID drift: {relative_path}",
    )


def validate_literal_tracked_file(
    repo_root: Path,
    relative_path: str,
    *,
    expected_blob_oid: str | None = None,
    revision: str = "HEAD",
) -> Path:
    pure = _validate_repo_relative_literal(relative_path)
    root = repo_root.resolve(strict=True)
    target = root.joinpath(*pure.parts)
    require(target != root, "repository root is not a file target")
    try:
        metadata = target.lstat()
    except FileNotFoundError as exc:
        raise CleanupValidationError(f"missing deletion target: {relative_path}") from exc
    require(not target.is_symlink(), f"symlink deletion target: {relative_path}")
    require(not _is_reparse_stat(metadata), f"reparse deletion target: {relative_path}")
    require(stat.S_ISREG(metadata.st_mode), f"non-regular deletion target: {relative_path}")
    resolved = target.resolve(strict=True)
    require(resolved.is_relative_to(root), f"deletion target escapes repository: {relative_path}")

    parent = target.parent
    while parent != root:
        parent_metadata = parent.lstat()
        require(
            not parent.is_symlink() and not _is_reparse_stat(parent_metadata),
            f"deletion target traverses a symlink/reparse point: {relative_path}",
        )
        parent = parent.parent

    if expected_blob_oid is None:
        stage = _git(
            repo_root,
            "ls-files",
            "--stage",
            "-z",
            "--",
            relative_path,
            check=False,
        )
        require(
            stage.returncode == 0 and stage.stdout,
            f"untracked deletion target: {relative_path}",
        )
    else:
        validate_manifest_git_identity(
            repo_root,
            relative_path,
            expected_blob_oid,
            revision=revision,
        )
    return target


def _unlink_one_literal(target: Path) -> None:
    metadata = target.lstat()
    require(not target.is_symlink(), f"refusing symlink unlink: {target}")
    require(not _is_reparse_stat(metadata), f"refusing reparse unlink: {target}")
    require(stat.S_ISREG(metadata.st_mode), f"refusing non-regular unlink: {target}")
    target.unlink()


def _require_existing_components_non_reparse(
    repo_root: Path, relative_path: str
) -> None:
    root = repo_root.resolve(strict=True)
    current = root
    for part in _validate_repo_relative_literal(relative_path).parts:
        current = current / part
        if not os.path.lexists(current):
            break
        metadata = current.lstat()
        require(
            not current.is_symlink() and not _is_reparse_stat(metadata),
            f"directory path traverses a symlink/reparse point: {relative_path}",
        )


def _enumerate_directory_only_tree(
    repo_root: Path, root_relative: str
) -> set[str]:
    root = repo_root.resolve(strict=True)
    tree_root = root.joinpath(*_validate_repo_relative_literal(root_relative).parts)
    if not os.path.lexists(tree_root):
        return set()
    tree_metadata = tree_root.lstat()
    require(
        tree_root != root,
        "refusing to enumerate the repository/worktree root as a cleanup tree",
    )
    require(
        tree_root.is_dir()
        and not tree_root.is_symlink()
        and not _is_reparse_stat(tree_metadata),
        "old002837 cleanup root is not a real non-reparse directory",
    )
    discovered: set[str] = set()
    pending = [tree_root]
    while pending:
        current = pending.pop()
        relative_current = current.relative_to(root).as_posix()
        require(
            relative_current not in discovered,
            f"duplicate directory encountered during complete enumeration: {relative_current}",
        )
        discovered.add(relative_current)
        with os.scandir(current) as iterator:
            entries = list(iterator)
        for entry in entries:
            entry_path = Path(entry.path)
            metadata = entry.stat(follow_symlinks=False)
            relative_entry = entry_path.relative_to(root).as_posix()
            require(
                not entry.is_symlink() and not _is_reparse_stat(metadata),
                f"symlink/reparse entry in directory cleanup tree: {relative_entry}",
            )
            require(
                entry.is_dir(follow_symlinks=False),
                f"non-directory entry remains in directory cleanup tree: {relative_entry}",
            )
            pending.append(entry_path)
    return discovered


def validate_directory_prefix_state(
    repo_root: Path,
    expected_paths: Sequence[str],
    *,
    processed_count: int | None = None,
) -> dict[str, Any]:
    paths = [str(path) for path in expected_paths]
    require(paths, "empty directory manifest")
    require(len(paths) == len(set(paths)), "directory manifest has duplicates")
    root = repo_root.resolve(strict=True)
    for path in paths:
        pure = _validate_repo_relative_literal(path)
        require(
            root.joinpath(*pure.parts) != root,
            "directory manifest contains repository/worktree root",
        )
        _require_existing_components_non_reparse(repo_root, path)

    positions = {path: index for index, path in enumerate(paths)}
    for child in paths:
        parent = PurePosixPath(child).parent
        while parent.as_posix() != ".":
            parent_text = parent.as_posix()
            if parent_text in positions:
                require(
                    positions[child] < positions[parent_text],
                    f"directory manifest is not deepest-first: {child}",
                )
            parent = parent.parent

    present = [
        os.path.lexists(root.joinpath(*PurePosixPath(path).parts))
        for path in paths
    ]
    inferred = 0
    while inferred < len(paths) and not present[inferred]:
        inferred += 1
    require(
        not any(not value for value in present[inferred:]),
        "directory state is not a processed-prefix/remaining-suffix split",
    )
    if processed_count is not None:
        require(
            inferred == processed_count,
            "directory processed-prefix count changed between operations",
        )
    for path in paths[inferred:]:
        target = root.joinpath(*PurePosixPath(path).parts)
        metadata = target.lstat()
        require(
            target.is_dir()
            and not target.is_symlink()
            and not _is_reparse_stat(metadata),
            f"remaining manifest target is not a real non-reparse directory: {path}",
        )

    root_relative = paths[-1]
    discovered = _enumerate_directory_only_tree(repo_root, root_relative)
    require(
        discovered == set(paths[inferred:]),
        "complete directory enumeration differs from the remaining manifest suffix",
    )
    current_path = paths[inferred] if inferred < len(paths) else None
    if current_path is not None:
        current = root.joinpath(*PurePosixPath(current_path).parts)
        with os.scandir(current) as iterator:
            entries = list(iterator)
        require(
            not entries,
            f"current directory removal target is not empty: {current_path}",
        )
    return {
        "processed_count": inferred,
        "complete": inferred == len(paths),
        "processed_paths": paths[:inferred],
        "remaining_paths": paths[inferred:],
        "current_path": current_path,
    }


def validate_runtime_directory_manifest(
    repo_root: Path, directory_manifest: Mapping[str, Any]
) -> dict[str, Any]:
    root = repo_root.resolve(strict=True)
    dedicated = DEDICATED_WORKTREE_ROOT.resolve(strict=True)
    require(root == dedicated, "directory surface is not in the dedicated worktree")
    require(
        directory_manifest.get("paths") == list(OLD002837_DIRECTORIES),
        "runtime directory paths differ from the frozen manifest",
    )
    actual_absolute = [
        _absolute_manifest_path(repo_root, path)
        for path in directory_manifest["paths"]
    ]
    require(
        actual_absolute == list(directory_manifest.get("absolute_paths", [])),
        "runtime absolute directory paths differ from the frozen manifest",
    )
    absolute_bytes, absolute_sha = ordered_path_vector(actual_absolute)
    require(
        absolute_bytes
        == EXPECTED_OLD002837_DIRECTORY_VECTOR[
            "absolute_path_vector_byte_count"
        ]
        and absolute_sha
        == EXPECTED_OLD002837_DIRECTORY_VECTOR[
            "absolute_path_vector_sha256"
        ],
        "runtime absolute directory vector drift",
    )
    return validate_directory_prefix_state(
        repo_root, list(directory_manifest["paths"])
    )


def _rmdir_one_literal(target: Path) -> None:
    metadata = target.lstat()
    require(not target.is_symlink(), f"refusing symlink directory removal: {target}")
    require(not _is_reparse_stat(metadata), f"refusing reparse directory removal: {target}")
    require(stat.S_ISDIR(metadata.st_mode), f"refusing non-directory removal: {target}")
    with os.scandir(target) as iterator:
        entries = list(iterator)
    require(not entries, f"refusing non-empty directory removal: {target}")
    target.rmdir()


def _wave_validation_receipt(
    wave: str,
    wave_parent: str,
    expected_paths: Sequence[str],
    status_bytes: bytes,
    diff_bytes: bytes,
    validation: Mapping[str, Any],
    directory_validation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    actor = WAVE_ACTORS[wave]
    receipt = {
        "schema_version": "r5_v1_deletion_wave_validation_v2",
        "validation_id": "V-007",
        "decision": "pass",
        "wave": wave,
        "wave_parent_commit": wave_parent,
        **actor,
        "expected_file_count": len(expected_paths),
        "status": {
            "raw_byte_count": len(status_bytes),
            "raw_sha256": hashlib.sha256(status_bytes).hexdigest(),
            "record_count": len(validation["status_rows"]),
            "path_vector_byte_count": validation["path_vector_byte_count"],
            "path_vector_sha256": validation["path_vector_sha256"],
            "all_status_codes": [" D"],
        },
        "name_status": {
            "raw_byte_count": len(diff_bytes),
            "raw_sha256": hashlib.sha256(diff_bytes).hexdigest(),
            "record_count": len(validation["diff_rows"]),
            "path_vector_byte_count": validation["path_vector_byte_count"],
            "path_vector_sha256": validation["path_vector_sha256"],
            "all_status_codes": ["D"],
        },
        "guards": {
            "complete_vector_validated_in_memory_before_receipt_write": True,
            "index_clean_before_receipt_write": True,
            "ordinal_prefix_resume_only": True,
            "rename_present": False,
            "untracked_present": False,
            "modification_present": False,
            "type_change_present": False,
            "unexpected_path_present": False,
            "stage_or_commit_performed": False,
        },
    }
    if directory_validation is not None:
        receipt["directory_cleanup"] = dict(directory_validation)
    return receipt


def verify_wave(
    repo_root: Path,
    cleanup_manifest: Mapping[str, Any],
    wave: str,
    wave_parent: str,
) -> dict[str, Any]:
    control = validate_committed_control_plane(repo_root, wave, wave_parent)
    require(
        dict(cleanup_manifest) == control["cleanup"],
        "provided cleanup manifest differs from the committed control plane",
    )
    committed_cleanup = load_committed_yaml(
        repo_root, wave_parent, CLEANUP_MANIFEST_REL
    )
    require(
        dict(cleanup_manifest) == committed_cleanup,
        "worktree cleanup manifest differs from the committed wave parent",
    )
    expected = next(
        list(document["paths"])
        for document in cleanup_manifest["waves"]
        if document["wave"] == wave
    )
    status_bytes, diff_bytes, cached_bytes = capture_deletion_vectors(
        repo_root, wave_parent
    )
    validation = validate_deletion_prefix_vectors(
        status_bytes,
        diff_bytes,
        cached_bytes,
        expected,
        require_complete=True,
    )
    directory_validation = None
    if wave == "old002837":
        state = validate_runtime_directory_manifest(
            repo_root, control["directory_manifest"]
        )
        require(state["complete"] is True, "old002837 directory vector is not complete")
        directory_validation = {
            **OLD002837_DIRECTORY_ACTOR,
            "expected_directory_count": len(
                control["directory_manifest"]["paths"]
            ),
            "processed_directory_count": state["processed_count"],
            "complete": True,
            "exact_root_absent": not os.path.lexists(
                repo_root.resolve(strict=True)
                .joinpath(*PurePosixPath(OLD_RUN_PREFIX).parts)
            ),
            "git_vectors_unchanged_during_directory_removal": True,
            "relative_vector": {
                "byte_count": EXPECTED_OLD002837_DIRECTORY_VECTOR[
                    "path_vector_byte_count"
                ],
                "sha256": EXPECTED_OLD002837_DIRECTORY_VECTOR[
                    "path_vector_sha256"
                ],
            },
            "absolute_vector": {
                "byte_count": EXPECTED_OLD002837_DIRECTORY_VECTOR[
                    "absolute_path_vector_byte_count"
                ],
                "sha256": EXPECTED_OLD002837_DIRECTORY_VECTOR[
                    "absolute_path_vector_sha256"
                ],
            },
        }
    return _wave_validation_receipt(
        wave,
        wave_parent,
        expected,
        status_bytes,
        diff_bytes,
        validation,
        directory_validation,
    )


def delete_file_wave(
    repo_root: Path, wave: str, wave_parent: str
) -> dict[str, Any]:
    control = validate_committed_control_plane(repo_root, wave, wave_parent)
    cleanup = control["cleanup"]
    wave_document = next(
        document for document in cleanup["waves"] if document["wave"] == wave
    )
    expected = [str(path) for path in wave_document["paths"]]
    rows = list(control["wave_rows"])
    require(
        [str(row["path"]) for row in rows] == expected,
        f"{wave} cleanup rows differ from the wave path vector",
    )
    require(
        wave_document.get("deletion_actor")
        == "codex_exact_manifest_one_file_at_a_time"
        and wave_document.get("codex_delete_authorized") is True,
        f"{wave} is not authorized for Codex exact-file deletion",
    )

    status_bytes, diff_bytes, cached_bytes = capture_deletion_vectors(
        repo_root, wave_parent
    )
    validation = validate_deletion_prefix_vectors(
        status_bytes, diff_bytes, cached_bytes, expected
    )
    prefix_count = int(validation["prefix_count"])
    root = repo_root.resolve(strict=True)
    for row in rows:
        validate_manifest_git_identity(
            repo_root,
            str(row["path"]),
            str(row["blob_oid"]),
            revision=wave_parent,
        )
    for path in expected[:prefix_count]:
        target = root.joinpath(*PurePosixPath(path).parts)
        require(
            not os.path.lexists(target),
            f"deleted ordinal prefix target still exists: {path}",
        )
    for row in rows[prefix_count:]:
        validate_literal_tracked_file(
            repo_root,
            str(row["path"]),
            expected_blob_oid=str(row["blob_oid"]),
            revision=wave_parent,
        )

    for index in range(prefix_count, len(expected)):
        status_bytes, diff_bytes, cached_bytes = capture_deletion_vectors(
            repo_root, wave_parent
        )
        current = validate_deletion_prefix_vectors(
            status_bytes, diff_bytes, cached_bytes, expected
        )
        require(
            current["prefix_count"] == index,
            f"{wave} deletion prefix changed between literal unlink operations",
        )
        row = rows[index]
        path = str(row["path"])
        target = validate_literal_tracked_file(
            repo_root,
            path,
            expected_blob_oid=str(row["blob_oid"]),
            revision=wave_parent,
        )
        _unlink_one_literal(target)
        require(not os.path.lexists(target), f"literal unlink did not remove: {path}")
        after_status, after_diff, after_cached = capture_deletion_vectors(
            repo_root, wave_parent
        )
        after = validate_deletion_prefix_vectors(
            after_status, after_diff, after_cached, expected
        )
        require(
            after["prefix_count"] == index + 1,
            f"{wave} deletion prefix did not advance by one literal file",
        )

    status_bytes, diff_bytes, cached_bytes = capture_deletion_vectors(
        repo_root, wave_parent
    )
    final_validation = validate_deletion_prefix_vectors(
        status_bytes,
        diff_bytes,
        cached_bytes,
        expected,
        require_complete=True,
    )
    directory_validation = None
    if wave == "old002837":
        directory_manifest = control["directory_manifest"]
        directory_paths = list(directory_manifest["paths"])
        state = validate_runtime_directory_manifest(repo_root, directory_manifest)
        directory_start = int(state["processed_count"])
        frozen_status = status_bytes
        frozen_diff = diff_bytes
        frozen_cached = cached_bytes
        for index in range(directory_start, len(directory_paths)):
            before_status, before_diff, before_cached = capture_deletion_vectors(
                repo_root, wave_parent
            )
            require(
                before_status == frozen_status
                and before_diff == frozen_diff
                and before_cached == frozen_cached,
                "Git vectors changed before a directory removal",
            )
            validate_deletion_prefix_vectors(
                before_status,
                before_diff,
                before_cached,
                expected,
                require_complete=True,
            )
            before_state = validate_directory_prefix_state(
                repo_root, directory_paths, processed_count=index
            )
            current_path = str(before_state["current_path"])
            require(
                current_path == directory_paths[index],
                "directory current ordinal drift",
            )
            target = root.joinpath(*PurePosixPath(current_path).parts)
            expected_absolute = str(directory_manifest["absolute_paths"][index])
            require(
                str(target.resolve(strict=True)) == expected_absolute,
                "directory absolute literal identity drift",
            )
            _rmdir_one_literal(target)
            require(
                not os.path.lexists(target),
                f"literal directory removal did not remove: {current_path}",
            )
            after_state = validate_directory_prefix_state(
                repo_root, directory_paths, processed_count=index + 1
            )
            require(
                after_state["processed_count"] == index + 1,
                "directory processed prefix did not advance by one",
            )
            after_status, after_diff, after_cached = capture_deletion_vectors(
                repo_root, wave_parent
            )
            require(
                after_status == frozen_status
                and after_diff == frozen_diff
                and after_cached == frozen_cached,
                "Git vectors changed during a directory removal",
            )
        final_directory_state = validate_directory_prefix_state(
            repo_root, directory_paths, processed_count=len(directory_paths)
        )
        require(
            final_directory_state["complete"] is True,
            "old002837 directory cleanup is incomplete",
        )
        require(
            not os.path.lexists(root.joinpath(*PurePosixPath(OLD_RUN_PREFIX).parts)),
            "old002837 exact run root still exists",
        )
        status_bytes, diff_bytes, cached_bytes = capture_deletion_vectors(
            repo_root, wave_parent
        )
        require(
            status_bytes == frozen_status
            and diff_bytes == frozen_diff
            and cached_bytes == frozen_cached,
            "final Git vectors changed during directory cleanup",
        )
        final_validation = validate_deletion_prefix_vectors(
            status_bytes,
            diff_bytes,
            cached_bytes,
            expected,
            require_complete=True,
        )
        directory_validation = {
            **OLD002837_DIRECTORY_ACTOR,
            "expected_directory_count": len(directory_paths),
            "processed_directory_count": len(directory_paths),
            "complete": True,
            "exact_root_absent": True,
            "git_vectors_unchanged_during_directory_removal": True,
            "file_vectors_validated_before_directory_removal": True,
            "relative_vector": {
                "byte_count": EXPECTED_OLD002837_DIRECTORY_VECTOR[
                    "path_vector_byte_count"
                ],
                "sha256": EXPECTED_OLD002837_DIRECTORY_VECTOR[
                    "path_vector_sha256"
                ],
            },
            "absolute_vector": {
                "byte_count": EXPECTED_OLD002837_DIRECTORY_VECTOR[
                    "absolute_path_vector_byte_count"
                ],
                "sha256": EXPECTED_OLD002837_DIRECTORY_VECTOR[
                    "absolute_path_vector_sha256"
                ],
            },
        }

    receipt = _wave_validation_receipt(
        wave,
        wave_parent,
        expected,
        status_bytes,
        diff_bytes,
        final_validation,
        directory_validation,
    )
    write_yaml_exact(repo_root, WAVE_RECEIPT_RELS[wave], receipt)
    return receipt


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
    wave.add_argument("--wave", choices=REMAINING_CODEX_WAVES, required=True)
    wave.add_argument("--wave-parent", required=True)
    delete = subparsers.add_parser("delete-wave")
    delete.add_argument("--wave", choices=REMAINING_CODEX_WAVES, required=True)
    delete.add_argument("--wave-parent", required=True)
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
        elif args.command == "delete-wave":
            receipt = delete_file_wave(root, args.wave, args.wave_parent)
        else:  # pragma: no cover
            raise CleanupValidationError(f"unsupported command: {args.command}")
    except (
        CleanupValidationError,
        OSError,
        ValueError,
        yaml.YAMLError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.command in {"verify-wave", "delete-wave"}:
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
