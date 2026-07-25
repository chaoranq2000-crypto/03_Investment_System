#!/usr/bin/env python3
"""Validate a minimal workflow_state.yaml file for research-orchestrator.

Usage:
    python .agents/skills/research-orchestrator/scripts/validate_workflow_state.py reports/workflow_runs/<workflow_id>/workflow_state.yaml
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required: pip install pyyaml") from exc

REQUIRED_FIELDS = [
    "workflow_id",
    "workflow_type",
    "status",
    "created_at",
    "updated_at",
    "current_stage",
    "completed_stages",
    "next_stage",
    "active_skill",
    "required_next_skill",
    "evidence_snapshot",
    "claims_snapshot",
    "metrics_snapshot",
    "artifacts",
    "open_todos",
    "quality_gates",
]

VALID_WORKFLOW_TYPES = {
    "segment_to_stock_closed_loop",
    "stock_first_closed_loop",
    "segment_stock_interlock",
    "refresh_existing_research",
    "comparison_readiness_gate",
}

VALID_STATUSES = {
    "planned",
    "in_progress",
    "blocked",
    "needs_fix",
    "ready_for_review",
    "accepted",
    "accepted_with_todos",
    "archived",
}

V1_STATE_SCHEMA_VERSION = "r5_v1"
VALID_RUN_MODES = {"normal", "diagnostic"}
VALID_GATE_IDS = {f"G{i}" for i in range(11)}
VALID_GATE_STATUSES = {"pass", "fail", "not_checked", "not_applicable"}
VALID_TODO_SEVERITIES = {"high", "medium", "low"}
VALID_TODO_STATUSES = {"open", "in_progress", "blocked", "closed"}
GOAL_SCOPED_SEMANTICS_VERSION = "current_goal_v1"
FINAL_REPORT_REVIEW_SEMANTICS_VERSION = "final_report_review_v1"
VALID_FINAL_REPORT_REVIEW_STATUSES = {
    "not_requested",
    "pending",
    "approved",
    "changes_requested",
}
VALID_FINAL_REPORT_CHANGE_SCOPES = {
    "automated_quality_defect",
    "report_revision",
}
VALID_IMPACT_SCOPES = {"workflow", "report", "section", "claim", "method", "none"}
VALID_ACTIVE_DISPOSITIONS = {
    "active_defect",
    "unknown",
    "method_unavailable",
    "report_limitation",
    "historical_backlog",
    "policy_retired",
    "not_required_for_active_v1",
}
NON_ACTIVE_DISPOSITIONS = {
    "historical_backlog",
    "policy_retired",
    "not_required_for_active_v1",
}
CURRENT_ASSET_NAMES = (
    "workflow_state.yaml",
    "open_todos.csv",
    "quality_gate_report.md",
    "workflow_readout.md",
)
REPO_ROOT = Path(__file__).resolve().parents[4]
FINAL_REPORT_REVIEW_FIELDS = {
    "report_path",
    "report_sha256",
    "reviewer",
    "reviewed_at",
    "decision",
    "notes",
    "change_scope",
}
FINAL_REVIEW_TRUTH_FIELDS = (
    "automated_report_quality_passed",
    "system_v1_complete",
    "sample_quality_ready",
    "p2_ready",
    "release_ready",
)
FORBIDDEN_ACTIVE_HUMAN_FIELD_FRAGMENTS = (
    "approval",
    "approved_by",
    "approver",
    "human_review",
    "human_decision",
    "human_signoff",
    "human_approval",
    "independent_receipt",
    "review_decision",
    "review_status",
    "reviewed_by",
    "reviewer",
    "reviewer_authority",
    "signature",
    "signed_by",
    "signoff",
)
FORBIDDEN_ACTIVE_HUMAN_FIELDS = {
    "approval",
    "reviewer",
    "reviewed_at",
    "reviewed_by",
    "review_decision",
    "reviewer_authored_mapping",
    "reviewer_authored_mappings",
    "candidate_decision",
    "candidate_decisions",
    "approver",
    "approved_by",
    "approval_status",
    "signature",
    "signed_by",
}
FORBIDDEN_ACTIVE_HUMAN_FIELDS_COMPACT = {
    re.sub(r"[^a-z0-9]+", "", field)
    for field in FORBIDDEN_ACTIVE_HUMAN_FIELDS
}
FORBIDDEN_ACTIVE_HUMAN_FIELD_FRAGMENTS_COMPACT = tuple(
    re.sub(r"[^a-z0-9]+", "", fragment)
    for fragment in FORBIDDEN_ACTIVE_HUMAN_FIELD_FRAGMENTS
)
RESERVED_MACHINE_REVIEWERS = {
    "ai",
    "automation",
    "automated",
    "bot",
    "chatgpt",
    "codex",
    "codexagent",
    "fixture",
    "gpt",
    "human",
    "humanreviewer",
    "llm",
    "machine",
    "openai",
    "placeholder",
    "reviewer",
    "externalreviewer",
    "system",
    "test",
    "todo",
    "unknown",
}
RESERVED_MACHINE_REVIEWER_TOKENS = RESERVED_MACHINE_REVIEWERS - {"openai"}
RESERVED_MACHINE_REVIEWER_FRAGMENTS = (
    "人工智能",
    "占位",
    "大模型",
    "待定",
    "机器人",
    "机器",
    "测试",
    "未知",
    "系统",
    "自动",
)
RESERVED_MACHINE_REVIEWER_NAMES = {
    "人工审核员",
    "外部审核员",
    "审核员",
    "真人审核员",
}
WINDOWS_RESERVED_BASENAMES = {
    "aux",
    "con",
    "nul",
    "prn",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}
WINDOWS_RESERVED_PATH_CHARACTERS = set('<>:"|?*')
VALID_FINAL_REPORT_CATEGORIES = {"segments", "stocks"}
VALID_FINAL_REPORT_SUFFIXES = {".docx", ".html", ".md", ".pdf"}
VALID_MACHINE_QUALIFICATION_REVIEW_STATUSES = {
    "blocked",
    "candidate",
    "missing",
    "reviewed",
    "todo",
}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        fail(f"file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        fail("workflow_state.yaml must contain a YAML mapping")
    return data


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_final_report_path(raw_path: Any, *, repo_root: Path) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        fail("final_report_review.report_path must be a non-empty repo-relative path")
    if raw_path != raw_path.strip() or "\\" in raw_path:
        fail("final_report_review.report_path must use canonical repo-relative POSIX form")

    posix_path = PurePosixPath(raw_path)
    windows_path = PureWindowsPath(raw_path)
    if posix_path.is_absolute() or windows_path.is_absolute():
        fail("final_report_review.report_path must be repo-relative")
    for part in raw_path.split("/"):
        if part in {"", ".", ".."}:
            fail("final_report_review.report_path contains an unsafe path component")
        if (
            any(ord(character) < 32 for character in part)
            or WINDOWS_RESERVED_PATH_CHARACTERS.intersection(part)
            or part.endswith((" ", "."))
            or part.split(".", 1)[0].casefold() in WINDOWS_RESERVED_BASENAMES
        ):
            fail(
                "final_report_review.report_path contains Windows-reserved "
                "path syntax"
            )
    if (
        len(posix_path.parts) < 4
        or posix_path.parts[0] != "reports"
        or posix_path.parts[1] not in VALID_FINAL_REPORT_CATEGORIES
        or not re.fullmatch(r"[a-z0-9][a-z0-9_]*", posix_path.parts[2])
    ):
        fail(
            "final_report_review.report_path must be under the canonical "
            "reports/stocks/<id>/ or reports/segments/<id>/ root"
        )
    if posix_path.suffix.casefold() not in VALID_FINAL_REPORT_SUFFIXES:
        fail(
            "final_report_review.report_path must name a report file "
            "(.md, .pdf, .html, or .docx)"
        )

    root = repo_root.resolve()
    resolved = (root / Path(*posix_path.parts)).resolve()
    canonical_container = (
        root
        / posix_path.parts[0]
        / posix_path.parts[1]
        / posix_path.parts[2]
    ).resolve()
    try:
        resolved.relative_to(root)
        resolved.relative_to(canonical_container)
    except ValueError:
        fail("final_report_review.report_path escapes its canonical report root")
    if not resolved.is_file():
        fail(f"final_report_review.report_path is not a file: {raw_path}")
    return resolved


def _validate_reviewer_identity(reviewer: Any) -> None:
    if not isinstance(reviewer, str) or not reviewer.strip():
        fail("final_report_review.reviewer must identify a real external reviewer")
    if reviewer != reviewer.strip():
        fail("final_report_review.reviewer must not have surrounding whitespace")
    if not any(character.isalnum() for character in reviewer):
        fail("final_report_review.reviewer cannot be a machine or placeholder identity")
    normalized = re.sub(r"[\s_.-]+", "", reviewer.casefold())
    tokens = set(re.findall(r"[a-z0-9]+", reviewer.casefold()))
    if (
        normalized in RESERVED_MACHINE_REVIEWERS
        or tokens & RESERVED_MACHINE_REVIEWER_TOKENS
        or any(
            fragment in reviewer.casefold()
            for fragment in RESERVED_MACHINE_REVIEWER_FRAGMENTS
        )
        or reviewer.casefold() in RESERVED_MACHINE_REVIEWER_NAMES
    ):
        fail("final_report_review.reviewer cannot be a machine or placeholder identity")


def _validate_reviewed_at(reviewed_at: Any) -> datetime:
    if not isinstance(reviewed_at, str) or not reviewed_at.strip():
        fail("final_report_review.reviewed_at must be an ISO-8601 datetime")
    try:
        parsed = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
    except ValueError:
        fail("final_report_review.reviewed_at must be an ISO-8601 datetime")
    if parsed.tzinfo is None:
        fail("final_report_review.reviewed_at must include a timezone")
    return parsed


def validate_final_report_review_transition(
    data: dict[str, Any],
    previous: dict[str, Any] | None,
    prior_human_review: dict[str, Any] | None = None,
) -> None:
    """Reject reuse of an old human event after review-bound content changes."""

    human_statuses = {"approved", "changes_requested"}
    current_status = data.get("final_report_review_status")
    if current_status not in human_statuses:
        return

    previous_status = (
        previous.get("final_report_review_status")
        if isinstance(previous, dict)
        else None
    )
    baseline = (
        previous
        if previous_status in human_statuses
        else prior_human_review
    )
    if (
        not isinstance(baseline, dict)
        or baseline.get("final_report_review_semantics_version")
        != FINAL_REPORT_REVIEW_SEMANTICS_VERSION
        or baseline.get("final_report_review_status") not in human_statuses
    ):
        return

    current_review = data.get("final_report_review")
    baseline_review = baseline.get("final_report_review")
    if not isinstance(current_review, dict) or not isinstance(baseline_review, dict):
        return
    if (
        previous_status in human_statuses
        and current_status == previous_status
        and current_review == baseline_review
    ):
        return

    current_time = _validate_reviewed_at(current_review.get("reviewed_at"))
    baseline_time = _validate_reviewed_at(baseline_review.get("reviewed_at"))
    if current_time <= baseline_time:
        fail(
            "changed final-report bytes or human decision requires a new "
            "review event with a later reviewed_at"
        )


def _load_git_state(
    repo_root: Path,
    state_path: Path,
    ref: str,
) -> dict[str, Any] | None:
    try:
        relative = state_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None
    result = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"{ref}:{relative}"],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    loaded = yaml.safe_load(result.stdout)
    return loaded if isinstance(loaded, dict) else None


def _latest_committed_human_review(
    repo_root: Path,
    state_path: Path,
    baseline_ref: str,
) -> dict[str, Any] | None:
    try:
        relative = state_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None
    commits = subprocess.run(
        ["git", "-C", str(repo_root), "rev-list", baseline_ref, "--", relative],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if commits.returncode != 0:
        return None
    for commit in commits.stdout.splitlines():
        candidate = _load_git_state(repo_root, state_path, commit)
        if (
            isinstance(candidate, dict)
            and candidate.get("final_report_review_semantics_version")
            == FINAL_REPORT_REVIEW_SEMANTICS_VERSION
            and candidate.get("final_report_review_status")
            in {"approved", "changes_requested"}
        ):
            return candidate
    return None


def _committed_review_context(
    state_path: Path,
    data: dict[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    head_state = _load_git_state(repo_root, state_path, "HEAD")
    if head_state is None:
        return None, None
    baseline_ref = "HEAD^" if head_state == data else "HEAD"
    return (
        _load_git_state(repo_root, state_path, baseline_ref),
        _latest_committed_human_review(repo_root, state_path, baseline_ref),
    )


def _is_forbidden_active_human_field(key: str) -> bool:
    normalized = key.casefold()
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    return (
        compact.startswith("finalreportreview")
        or compact in FORBIDDEN_ACTIVE_HUMAN_FIELDS_COMPACT
        or any(
            fragment in compact
            for fragment in FORBIDDEN_ACTIVE_HUMAN_FIELD_FRAGMENTS_COMPACT
        )
    )


def _reject_parallel_human_review_fields(
    value: Any,
    *,
    path: str = "workflow_state",
    in_final_record: bool = False,
) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                continue
            item_path = f"{path}.{key}"
            if path == "workflow_state" and key in {
                "final_report_review_semantics_version",
                "final_report_review_status",
            }:
                continue
            if path == "workflow_state" and key == "final_report_review":
                _reject_parallel_human_review_fields(
                    item,
                    path=item_path,
                    in_final_record=True,
                )
                continue
            compact_key = re.sub(r"[^a-z0-9]+", "", key.casefold())
            if not in_final_record and compact_key == "reviewstatus":
                if (
                    not isinstance(item, str)
                    or item.casefold()
                    not in VALID_MACHINE_QUALIFICATION_REVIEW_STATUSES
                ):
                    fail(
                        f"{item_path} may contain only machine-qualification "
                        "statuses: reviewed, candidate, TODO, MISSING, blocked"
                    )
                continue
            if not in_final_record and _is_forbidden_active_human_field(key):
                fail(
                    f"{item_path} is a parallel or intermediate human-review field; "
                    "active state may use only final_report_review"
                )
            _reject_parallel_human_review_fields(
                item,
                path=item_path,
                in_final_record=in_final_record,
            )
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_parallel_human_review_fields(
                item,
                path=f"{path}[{index}]",
                in_final_record=in_final_record,
            )


def _validate_final_report_binding(
    data: dict[str, Any],
    review: dict[str, Any],
    *,
    repo_root: Path,
) -> None:
    declared = [
        item
        for item in data.get("artifacts", [])
        if isinstance(item, dict) and item.get("artifact_type") == "final_report"
    ]
    if len(declared) != 1:
        fail(
            "a bound final report requires exactly one "
            "artifacts[] item with artifact_type=final_report"
        )
    artifact = declared[0]
    if artifact.get("path") != review["report_path"]:
        fail(
            "final_report_review.report_path must equal the declared "
            "final_report artifact path"
        )
    if artifact.get("status") != "current" or artifact.get("required") is not True:
        fail(
            "the declared final_report artifact must be current and required"
        )

    report = _resolve_final_report_path(review["report_path"], repo_root=repo_root)
    expected = review["report_sha256"]
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        fail("final_report_review.report_sha256 must be a lowercase SHA-256")
    observed = _sha256_file(report)
    if observed != expected:
        fail(
            "final_report_review approval/binding is stale: report bytes do not "
            "match report_sha256"
        )


def validate_final_report_review(
    data: dict[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
) -> None:
    """Validate the only active human boundary: the final report review."""

    _reject_parallel_human_review_fields(data)

    for field in FINAL_REVIEW_TRUTH_FIELDS:
        if field not in data:
            fail(f"{field} is required for final_report_review_v1")
        if not isinstance(data[field], bool):
            fail(f"{field} must be a boolean")

    status = data.get("final_report_review_status")
    if status not in VALID_FINAL_REPORT_REVIEW_STATUSES:
        fail(f"invalid or missing final_report_review_status: {status}")

    review = data.get("final_report_review")
    if not isinstance(review, dict):
        fail("final_report_review must be a mapping")
    missing = sorted(FINAL_REPORT_REVIEW_FIELDS - set(review))
    extra = sorted(set(review) - FINAL_REPORT_REVIEW_FIELDS)
    if missing:
        fail("final_report_review missing fields: " + ", ".join(missing))
    if extra:
        fail("final_report_review has unsupported fields: " + ", ".join(extra))
    if review["decision"] != status:
        fail("final_report_review.decision must equal final_report_review_status")

    automated_pass = data["automated_report_quality_passed"]
    if automated_pass:
        gates = {
            item.get("gate_id"): item.get("status")
            for item in data.get("quality_gates", [])
            if isinstance(item, dict)
        }
        missing_gates = sorted(VALID_GATE_IDS - set(gates))
        non_passing_gates = sorted(
            gate_id
            for gate_id, gate_status in gates.items()
            if gate_id in VALID_GATE_IDS
            and gate_status not in {"pass", "not_applicable"}
        )
        if missing_gates or non_passing_gates:
            details = []
            if missing_gates:
                details.append("missing=" + ",".join(missing_gates))
            if non_passing_gates:
                details.append("not_passed=" + ",".join(non_passing_gates))
            fail(
                "automated_report_quality_passed=true requires complete G0-G10 "
                "machine evidence with pass/not_applicable statuses; "
                + "; ".join(details)
            )
        if data["status"] not in {"accepted", "accepted_with_todos"}:
            fail(
                "automated_report_quality_passed=true requires a completed "
                "automatic workflow status"
            )

    if status == "not_requested":
        for field in (
            "report_path",
            "report_sha256",
            "reviewer",
            "reviewed_at",
            "notes",
            "change_scope",
        ):
            if review[field] is not None:
                fail(
                    f"final_report_review.{field} must be null when review is "
                    "not_requested"
                )
    else:
        _validate_final_report_binding(data, review, repo_root=repo_root)

    if status == "pending":
        if review["reviewer"] is not None or review["reviewed_at"] is not None:
            fail("pending final report review cannot contain reviewer or reviewed_at")
        if review["notes"] is not None:
            fail("pending final report review requires notes=null")
        if review["change_scope"] is not None:
            fail("pending final report review requires change_scope=null")

    if status in {"approved", "changes_requested"}:
        _validate_reviewer_identity(review["reviewer"])
        _validate_reviewed_at(review["reviewed_at"])
        if not isinstance(review["notes"], str) or not review["notes"].strip():
            fail(f"{status} final report review requires non-empty notes")

    if status == "approved" and review["change_scope"] is not None:
        fail("approved final report review requires change_scope=null")

    if status == "changes_requested":
        change_scope = review["change_scope"]
        if change_scope not in VALID_FINAL_REPORT_CHANGE_SCOPES:
            fail(
                "changes_requested final report review requires change_scope "
                "automated_quality_defect or report_revision"
            )
        if change_scope == "automated_quality_defect":
            if data["status"] != "needs_fix":
                fail(
                    "changes_requested with automated_quality_defect requires "
                    "workflow status needs_fix"
                )
            if automated_pass:
                fail(
                    "automated_quality_defect cannot coexist with "
                    "automated_report_quality_passed=true"
                )

    if data["sample_quality_ready"]:
        if not automated_pass:
            fail(
                "sample_quality_ready=true requires "
                "automated_report_quality_passed=true"
            )
        if status != "approved":
            fail(
                "sample_quality_ready=true requires "
                "final_report_review_status=approved"
            )
        if data["status"] not in {"accepted", "accepted_with_todos"}:
            fail(
                "sample_quality_ready=true requires a completed automatic "
                "workflow status"
            )

    if (
        data["system_v1_complete"]
        and data["status"] not in {"accepted", "accepted_with_todos"}
    ):
        fail(
            "system_v1_complete=true requires a completed automatic "
            "workflow status"
        )


def _validate_scoped_issue(item: dict[str, Any], label: str) -> str:
    """Validate one current-goal issue and return its row-level outcome."""

    for field in (
        "impact_scope",
        "active_disposition",
        "affected_capabilities",
        "blocks_current_goal",
    ):
        if field not in item:
            fail(f"{label}.{field} is required for current_goal_v1")

    impact_scope = item["impact_scope"]
    disposition = item["active_disposition"]
    capabilities = item["affected_capabilities"]
    blocks = item["blocks_current_goal"]

    if impact_scope not in VALID_IMPACT_SCOPES:
        fail(f"{label}.impact_scope is invalid: {impact_scope}")
    if disposition not in VALID_ACTIVE_DISPOSITIONS:
        fail(f"{label}.active_disposition is invalid: {disposition}")
    if (
        not isinstance(capabilities, list)
        or any(not isinstance(value, str) or not value.strip() for value in capabilities)
        or len(capabilities) != len(set(capabilities))
    ):
        fail(f"{label}.affected_capabilities must be a unique list of non-empty strings")
    if not isinstance(blocks, bool):
        fail(f"{label}.blocks_current_goal must be a boolean")

    if disposition in NON_ACTIVE_DISPOSITIONS:
        if impact_scope != "none" or capabilities or blocks:
            fail(
                f"{label}: {disposition} requires impact_scope=none, "
                "no affected_capabilities, and blocks_current_goal=false"
            )
        return "accepted"

    if impact_scope == "none":
        fail(f"{label}: {disposition} cannot use impact_scope=none")
    if not capabilities:
        fail(f"{label}: {disposition} requires affected_capabilities")

    if disposition == "active_defect":
        if not blocks:
            fail(f"{label}: active_defect must block the current goal")
        return "blocked" if impact_scope == "workflow" else "needs_fix"

    if disposition == "unknown":
        if impact_scope == "workflow":
            fail(f"{label}: unknown must be scoped below workflow")
        return "needs_fix" if blocks else "accepted_with_todos"

    if disposition == "method_unavailable":
        if impact_scope != "method":
            fail(f"{label}: method_unavailable requires impact_scope=method")
        return "blocked" if blocks else "accepted_with_todos"

    if disposition == "report_limitation":
        if blocks:
            fail(f"{label}: a visible report_limitation cannot block the current goal")
        if impact_scope == "workflow":
            fail(f"{label}: report_limitation must be scoped below workflow")
        return "accepted_with_todos"

    raise AssertionError(f"unhandled active disposition: {disposition}")


def _derive_scoped_outcome(items: list[dict[str, Any]]) -> str:
    outcomes = [
        _validate_scoped_issue(item, f"open_todos[{index}]")
        for index, item in enumerate(items)
        if item.get("status") != "closed"
    ]
    if "blocked" in outcomes:
        return "blocked"
    if "needs_fix" in outcomes:
        return "needs_fix"
    if "accepted_with_todos" in outcomes:
        return "accepted_with_todos"
    return "accepted"


def validate_v1_controls(data: dict[str, Any], *, goal_scoped: bool) -> None:
    """Validate the active V1 control plane without rewriting legacy states."""

    if data.get("run_mode") not in VALID_RUN_MODES:
        fail(f"invalid or missing run_mode: {data.get('run_mode')}")

    seen_gate_ids: set[str] = set()
    for index, item in enumerate(data.get("quality_gates", [])):
        if not isinstance(item, dict):
            fail(f"quality_gates[{index}] must be a mapping")
        gate_id = item.get("gate_id")
        if gate_id not in VALID_GATE_IDS:
            fail(f"quality_gates[{index}].gate_id is not canonical G0-G10: {gate_id}")
        if gate_id in seen_gate_ids:
            fail(f"duplicate canonical quality gate: {gate_id}")
        seen_gate_ids.add(gate_id)

        gate_status = item.get("status")
        if gate_status not in VALID_GATE_STATUSES:
            fail(f"quality_gates[{index}].status is invalid: {gate_status}")

        local_check_id = item.get("local_check_id")
        mapped_gate_ids = item.get("mapped_global_gate_ids")
        if local_check_id:
            if not isinstance(mapped_gate_ids, list) or not mapped_gate_ids:
                fail(
                    f"quality_gates[{index}] local_check_id requires "
                    "mapped_global_gate_ids"
                )
            invalid_mapped = [gate for gate in mapped_gate_ids if gate not in VALID_GATE_IDS]
            if invalid_mapped:
                fail(
                    f"quality_gates[{index}].mapped_global_gate_ids contains "
                    f"non-canonical values: {', '.join(invalid_mapped)}"
                )
            if gate_id not in mapped_gate_ids:
                fail(
                    f"quality_gates[{index}].gate_id must be included in "
                    "mapped_global_gate_ids"
                )

    for index, item in enumerate(data.get("open_todos", [])):
        if not isinstance(item, dict):
            fail(f"open_todos[{index}] must be a mapping")
        for field in ("issue_id", "severity", "stage", "description", "fix_owner_skill", "status"):
            if not item.get(field):
                fail(f"open_todos[{index}].{field} is required")
        if item.get("severity") not in VALID_TODO_SEVERITIES:
            fail(f"open_todos[{index}].severity is invalid: {item.get('severity')}")
        if item.get("status") not in VALID_TODO_STATUSES:
            fail(f"open_todos[{index}].status is invalid: {item.get('status')}")
        todo_gate_id = item.get("gate_id")
        if todo_gate_id and todo_gate_id not in VALID_GATE_IDS:
            fail(f"open_todos[{index}].gate_id is not canonical G0-G10: {todo_gate_id}")

        if goal_scoped:
            _validate_scoped_issue(item, f"open_todos[{index}]")

    if not goal_scoped:
        return

    status = data["status"]
    if status in {"accepted", "accepted_with_todos", "needs_fix", "blocked"}:
        derived = _derive_scoped_outcome(data.get("open_todos", []))
        if status != derived:
            fail(
                f"workflow status {status} is inconsistent with current-goal "
                f"issue semantics; expected {derived}"
            )
    if status == "needs_fix":
        if not data.get("required_next_skill") or not data.get("next_stage"):
            fail("needs_fix requires required_next_skill and next_stage")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip())
        return 2

    path = Path(argv[1])
    data = load_yaml(path)

    missing = [field for field in REQUIRED_FIELDS if field not in data]
    if missing:
        fail("missing required fields: " + ", ".join(missing))

    if data["workflow_type"] not in VALID_WORKFLOW_TYPES:
        fail(f"invalid workflow_type: {data['workflow_type']}")

    if data["status"] not in VALID_STATUSES:
        fail(f"invalid status: {data['status']}")

    if not isinstance(data["completed_stages"], list):
        fail("completed_stages must be a list")
    if not isinstance(data["artifacts"], list):
        fail("artifacts must be a list")
    if not isinstance(data["open_todos"], list):
        fail("open_todos must be a list")
    if not isinstance(data["quality_gates"], list):
        fail("quality_gates must be a list")

    schema_version = data.get("state_schema_version")
    if schema_version is not None and schema_version != V1_STATE_SCHEMA_VERSION:
        fail(f"unsupported state_schema_version: {schema_version}")
    semantics_version = data.get("decision_semantics_version")
    if semantics_version is not None and semantics_version != GOAL_SCOPED_SEMANTICS_VERSION:
        fail(f"unsupported decision_semantics_version: {semantics_version}")
    goal_scoped = semantics_version == GOAL_SCOPED_SEMANTICS_VERSION

    review_semantics_version = data.get("final_report_review_semantics_version")
    if (
        review_semantics_version is not None
        and review_semantics_version != FINAL_REPORT_REVIEW_SEMANTICS_VERSION
    ):
        fail(
            "unsupported final_report_review_semantics_version: "
            f"{review_semantics_version}"
        )
    review_scoped = (
        review_semantics_version == FINAL_REPORT_REVIEW_SEMANTICS_VERSION
    )
    if review_semantics_version is None:
        marker_controlled_fields = [
            "automated_report_quality_passed",
            "final_report_review_status",
            "final_report_review",
        ]
        if goal_scoped:
            marker_controlled_fields.extend(FINAL_REVIEW_TRUTH_FIELDS)
        else:
            legacy_truth_claims = sorted(
                field
                for field in FINAL_REVIEW_TRUTH_FIELDS
                if field in data and data[field] is not False
            )
            if legacy_truth_claims:
                fail(
                    "legacy final-report truth claims require "
                    "final_report_review_semantics_version=final_report_review_v1: "
                    + ", ".join(legacy_truth_claims)
                )
        partial_review_fields = sorted(
            field
            for field in marker_controlled_fields
            if field in data
        )
        if partial_review_fields:
            fail(
                "final-report review fields require "
                "final_report_review_semantics_version=final_report_review_v1: "
                + ", ".join(partial_review_fields)
            )
    if review_scoped and not goal_scoped:
        fail(
            "final_report_review_v1 requires "
            "decision_semantics_version=current_goal_v1"
        )
    if goal_scoped and not review_scoped:
        fail(
            "decision_semantics_version=current_goal_v1 requires "
            "final_report_review_semantics_version=final_report_review_v1"
        )
    if review_scoped and schema_version != V1_STATE_SCHEMA_VERSION:
        fail(
            "final_report_review_v1 requires "
            "state_schema_version=r5_v1"
        )

    if schema_version == V1_STATE_SCHEMA_VERSION:
        validate_v1_controls(data, goal_scoped=goal_scoped)
    if review_scoped:
        validate_final_report_review(data)
        previous_state, prior_human_review = _committed_review_context(path, data)
        validate_final_report_review_transition(
            data,
            previous_state,
            prior_human_review,
        )

    if not goal_scoped:
        high_open = []
        for item in data.get("open_todos", []):
            if (
                isinstance(item, dict)
                and item.get("severity") == "high"
                and item.get("status") != "closed"
            ):
                high_open.append(item.get("issue_id", "<unknown>"))

        if high_open and data["status"] in {"accepted", "accepted_with_todos"}:
            fail(
                "accepted status is not allowed while high severity issues remain "
                "open in legacy compatibility: "
                + ", ".join(high_open)
            )

    if schema_version != V1_STATE_SCHEMA_VERSION:
        compatibility = " (legacy compatibility)"
    elif not goal_scoped:
        compatibility = " (legacy r5_v1 compatibility; read-only)"
    else:
        compatibility = ""
    print(f"OK{compatibility}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
