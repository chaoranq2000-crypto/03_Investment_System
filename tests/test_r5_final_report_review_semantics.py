from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = (
    ROOT
    / ".agents"
    / "skills"
    / "research-orchestrator"
    / "scripts"
    / "validate_workflow_state.py"
)
TEMPLATE_PATH = (
    ROOT
    / ".agents"
    / "skills"
    / "research-orchestrator"
    / "assets"
    / "workflow_state_template.yaml"
)
SCHEMA_PATH = ROOT / "schemas" / "r5_final_report_review.schema.json"
REPORT_PATH = "reports/stocks/002837_invic/2026-07-01_stock_deep_dive.md"
TEMP_REPORT_PATH = "reports/stocks/000001_test/final_report.md"


def load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_workflow_state_final_review",
        VALIDATOR_PATH,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_validator(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(VALIDATOR_PATH), str(path)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def write_state(tmp_path: Path, state: dict) -> Path:
    path = tmp_path / "workflow_state.yaml"
    path.write_text(
        yaml.safe_dump(state, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return path


def template_state() -> dict:
    return yaml.safe_load(TEMPLATE_PATH.read_text(encoding="utf-8"))


def report_sha256(report_path: str = REPORT_PATH) -> str:
    return hashlib.sha256((ROOT / report_path).read_bytes()).hexdigest()


def write_temp_report(tmp_path: Path, content: bytes) -> Path:
    report = tmp_path / TEMP_REPORT_PATH
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_bytes(content)
    return report


def complete_machine_gates() -> list[dict[str, str]]:
    return [
        {
            "gate_id": f"G{index}",
            "status": "pass" if index != 5 else "not_applicable",
        }
        for index in range(11)
    ]


def bind_review(
    state: dict,
    status: str,
    *,
    report_path: str = REPORT_PATH,
    digest: str | None = None,
    reviewer: str | None = None,
    reviewed_at: str | None = None,
    notes: str | None = None,
    change_scope: str | None = None,
) -> None:
    state["artifacts"] = [
        item
        for item in state.get("artifacts", [])
        if item.get("artifact_type") != "final_report"
    ]
    state["artifacts"].append(
        {
            "artifact_type": "final_report",
            "path": report_path,
            "created_by_skill": "stock-deep-dive",
            "stage": "T9",
            "status": "current",
            "required": True,
        }
    )
    state["final_report_review_status"] = status
    state["final_report_review"] = {
        "report_path": report_path,
        "report_sha256": digest or report_sha256(report_path),
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "notes": notes,
        "change_scope": change_scope,
    }


def approve_review(state: dict) -> None:
    bind_review(
        state,
        "approved",
        reviewer="Zhang Wei",
        reviewed_at="2026-07-25T14:30:00+08:00",
        notes="Final report quality approved against the bound bytes.",
    )


def request_changes(state: dict, change_scope: str) -> None:
    bind_review(
        state,
        "changes_requested",
        reviewer="Zhang Wei",
        reviewed_at="2026-07-25T14:30:00+08:00",
        notes="Revise the final report as described.",
        change_scope=change_scope,
    )


def active_report_defect() -> dict:
    return {
        "issue_id": "FINAL-REPORT-001",
        "severity": "high",
        "stage": "T9",
        "gate_id": "G7",
        "target_artifact": REPORT_PATH,
        "description": "Human review revealed an automated-quality defect.",
        "fix_owner_skill": "stock-deep-dive",
        "status": "open",
        "impact_scope": "report",
        "active_disposition": "active_defect",
        "affected_capabilities": ["final_report"],
        "blocks_current_goal": True,
    }


def test_final_report_review_schema_accepts_the_active_template() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    assert list(validator.iter_errors(template_state())) == []
    approved = template_state()
    approve_review(approved)
    assert list(validator.iter_errors(approved)) == []

    sample_ready = template_state()
    sample_ready["status"] = "accepted"
    sample_ready["sample_quality_ready"] = True
    approve_review(sample_ready)
    assert "automated_report_quality_passed" not in sample_ready
    assert list(validator.iter_errors(sample_ready)) == []


def test_not_requested_does_not_block_derived_automatic_completion(
    tmp_path: Path,
) -> None:
    state = template_state()
    state["status"] = "accepted"
    state["quality_gates"] = complete_machine_gates()
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 0, result.stderr
    assert "compatibility" not in result.stdout


def test_pending_binds_current_report_without_blocking_completion(
    tmp_path: Path,
) -> None:
    state = template_state()
    state["status"] = "accepted"
    state["quality_gates"] = complete_machine_gates()
    bind_review(state, "pending")
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 0, result.stderr


def test_record_decision_must_match_top_level_status(tmp_path: Path) -> None:
    state = template_state()
    state["final_report_review"]["decision"] = "pending"
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "decision must equal final_report_review_status" in result.stderr


def test_matching_legacy_record_decision_remains_compatible(tmp_path: Path) -> None:
    state = template_state()
    state["final_report_review"]["decision"] = "not_requested"
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 0, result.stderr


def test_final_review_marker_requires_active_v1_state_schema(tmp_path: Path) -> None:
    state = template_state()
    state.pop("state_schema_version")
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "requires state_schema_version=r5_v1" in result.stderr


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "../outside.md",
        "reports/../outside.md",
        "/absolute/report.md",
        "C:/absolute/report.md",
        "reports\\workflow_runs\\report.md",
        "reports/final_report.md:reviewed_copy",
        "docs/workflows/RESEARCH_WORKFLOW.md::$DATA",
        "reports/CON.md",
        "reports/final_report.md.",
        "reports/final_report.md ",
        "reports/final?.md",
        ".git/config",
        "docs/codex_tasks/v1_governance_integration_cleanup_v2/CONTRACT.md",
        "reports/workflow_runs/example/final_report.md",
        "reports/stocks/000001_test/final_report.yaml",
    ],
)
def test_final_report_path_must_be_canonical_and_repo_relative(
    tmp_path: Path,
    unsafe_path: str,
) -> None:
    state = template_state()
    bind_review(
        state,
        "pending",
        report_path=unsafe_path,
        digest="0" * 64,
    )
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "report_path" in result.stderr


def test_report_byte_change_invalidates_existing_binding(tmp_path: Path) -> None:
    validator = load_validator()
    report = write_temp_report(tmp_path, b"reviewed bytes\n")
    state = template_state()
    bind_review(
        state,
        "approved",
        report_path=TEMP_REPORT_PATH,
        digest=hashlib.sha256(report.read_bytes()).hexdigest(),
        reviewer="Li Ming",
        reviewed_at="2026-07-25T14:30:00+08:00",
        notes="Approved these exact bytes.",
    )

    validator.validate_final_report_review(state, repo_root=tmp_path)
    report.write_bytes(b"changed bytes\n")

    with pytest.raises(SystemExit) as exc_info:
        validator.validate_final_report_review(state, repo_root=tmp_path)
    assert exc_info.value.code == 1


def test_new_report_hash_cannot_reuse_an_old_human_review_event(
    tmp_path: Path,
) -> None:
    validator = load_validator()
    report = write_temp_report(tmp_path, b"first reviewed bytes\n")
    previous = template_state()
    bind_review(
        previous,
        "approved",
        report_path=TEMP_REPORT_PATH,
        digest=hashlib.sha256(report.read_bytes()).hexdigest(),
        reviewer="Li Ming",
        reviewed_at="2026-07-25T14:30:00+08:00",
        notes="Approved the first report bytes.",
    )

    report.write_bytes(b"second report bytes\n")
    current = copy.deepcopy(previous)
    current["final_report_review"]["report_sha256"] = hashlib.sha256(
        report.read_bytes()
    ).hexdigest()
    validator.validate_final_report_review(current, repo_root=tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        validator.validate_final_report_review_transition(current, previous)
    assert exc_info.value.code == 1

    current["final_report_review"]["reviewed_at"] = "2026-07-25T14:31:00+08:00"
    current["final_report_review"]["notes"] = "Re-reviewed the second report bytes."
    validator.validate_final_report_review_transition(current, previous)


def test_removing_redundant_legacy_decision_is_not_a_new_review_event() -> None:
    validator = load_validator()
    previous = template_state()
    approve_review(previous)
    previous["final_report_review"]["decision"] = "approved"
    current = copy.deepcopy(previous)
    current["final_report_review"].pop("decision")

    validator.validate_final_report_review_transition(current, previous)


def test_pending_reset_cannot_restore_an_older_human_review_event(
    tmp_path: Path,
) -> None:
    validator = load_validator()
    report = write_temp_report(tmp_path, b"first reviewed bytes\n")
    old_approval = template_state()
    bind_review(
        old_approval,
        "approved",
        report_path=TEMP_REPORT_PATH,
        digest=hashlib.sha256(report.read_bytes()).hexdigest(),
        reviewer="Li Ming",
        reviewed_at="2026-07-25T14:30:00+08:00",
        notes="Approved the first report bytes.",
    )

    report.write_bytes(b"replacement bytes\n")
    pending = template_state()
    bind_review(
        pending,
        "pending",
        report_path=TEMP_REPORT_PATH,
        digest=hashlib.sha256(report.read_bytes()).hexdigest(),
    )
    reused = copy.deepcopy(old_approval)
    reused["final_report_review"]["report_sha256"] = hashlib.sha256(
        report.read_bytes()
    ).hexdigest()
    validator.validate_final_report_review(reused, repo_root=tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        validator.validate_final_report_review_transition(
            reused,
            pending,
            old_approval,
        )
    assert exc_info.value.code == 1

    reused["final_report_review"]["reviewed_at"] = "2026-07-25T14:31:00+08:00"
    reused["final_report_review"]["notes"] = "Re-reviewed the replacement bytes."
    validator.validate_final_report_review_transition(
        reused,
        pending,
        old_approval,
    )


def test_stored_report_hash_must_be_machine_computed(tmp_path: Path) -> None:
    state = template_state()
    bind_review(state, "pending", digest="0" * 64)
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "report bytes do not match report_sha256" in result.stderr


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing", "exactly one"),
        ("duplicate", "exactly one"),
        ("wrong_path", "must equal"),
        ("stale", "must be current and required"),
        ("optional", "must be current and required"),
    ],
)
def test_bound_report_must_be_the_unique_current_required_final_artifact(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    state = template_state()
    bind_review(state, "pending")
    if mutation == "missing":
        state["artifacts"] = []
    elif mutation == "duplicate":
        state["artifacts"].append(copy.deepcopy(state["artifacts"][0]))
    elif mutation == "wrong_path":
        state["artifacts"][0]["path"] = "reports/other_report.md"
    elif mutation == "stale":
        state["artifacts"][0]["status"] = "stale"
    elif mutation == "optional":
        state["artifacts"][0]["required"] = False

    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert message in result.stderr


@pytest.mark.parametrize(
    "parallel_field",
    [
        "human_review_status",
        "reviewer_authority",
        "independent_receipt",
        "candidate_decisions",
        "exact_hash_human_review_status",
        "final_report_review_sha256",
        "human-review-status",
        "independentReceipt",
        "approved_by",
        "reviewer_name",
        "humanDecision",
        "review_decision",
        "approverIdentity",
        "humanSignoff",
        "external_review_status",
        "manualReviewStatus",
        "peer_review_status",
        "external_review_decision",
    ],
)
def test_marked_active_state_rejects_parallel_human_review_fields(
    tmp_path: Path,
    parallel_field: str,
) -> None:
    state = template_state()
    state["evidence_snapshot"][parallel_field] = "pending"
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "parallel or intermediate human-review field" in result.stderr


def test_intermediate_review_status_allows_only_machine_qualification_values(
    tmp_path: Path,
) -> None:
    state = template_state()
    state["evidence_snapshot"]["review_status"] = "approved"
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "only machine-qualification statuses" in result.stderr

    state["evidence_snapshot"]["review_status"] = "reviewed"
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "reviewer",
    [
        "Codex agent",
        "OpenAI Codex",
        "system reviewer",
        "AI reviewer",
        "placeholder",
        "机器审核员",
        "自动化审核",
        "系统审核员",
        "测试审核员",
        "待定",
        "Reviewer 1",
        "审核员",
        "🤖",
    ],
)
def test_machine_or_placeholder_reviewer_cannot_approve(
    tmp_path: Path,
    reviewer: str,
) -> None:
    state = template_state()
    bind_review(
        state,
        "approved",
        reviewer=reviewer,
        reviewed_at="2026-07-25T14:30:00+08:00",
        notes="Automatically approved.",
    )
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "machine or placeholder identity" in result.stderr


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("reviewer", None, "real external reviewer"),
        ("reviewed_at", "2026-07-25T14:30:00", "include a timezone"),
        ("notes", "", "requires non-empty notes"),
    ],
)
def test_approved_review_requires_reviewer_time_and_notes(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    state = template_state()
    approve_review(state)
    state["final_report_review"][field] = value
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert message in result.stderr


def test_legacy_automated_quality_true_requires_complete_machine_gate_evidence(
    tmp_path: Path,
) -> None:
    state = template_state()
    state["automated_report_quality_passed"] = True
    state["quality_gates"] = [{"gate_id": "G0", "status": "pass"}]
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "must equal the value derived" in result.stderr


def test_legacy_automated_quality_true_requires_completed_automatic_status(
    tmp_path: Path,
) -> None:
    state = template_state()
    state["automated_report_quality_passed"] = True
    state["quality_gates"] = complete_machine_gates()
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "must equal the value derived" in result.stderr


def test_sample_quality_true_requires_automated_pass_and_current_approval(
    tmp_path: Path,
) -> None:
    state = template_state()
    state["quality_gates"] = complete_machine_gates()
    state["sample_quality_ready"] = True
    state["status"] = "accepted"
    approve_review(state)
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 0, result.stderr

    pending = copy.deepcopy(state)
    pending["sample_quality_ready"] = True
    bind_review(pending, "pending")
    result = run_validator(write_state(tmp_path, pending))
    assert result.returncode == 1
    assert "final_report_review_status=approved" in result.stderr

    automatic_failure = copy.deepcopy(state)
    automatic_failure["quality_gates"][0]["status"] = "fail"
    result = run_validator(write_state(tmp_path, automatic_failure))
    assert result.returncode == 1
    assert "requires derived automated report quality to pass" in result.stderr


def test_sample_quality_true_requires_completed_automatic_status(
    tmp_path: Path,
) -> None:
    state = template_state()
    state["quality_gates"] = complete_machine_gates()
    state["sample_quality_ready"] = True
    approve_review(state)
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "requires derived automated report quality to pass" in result.stderr


def test_approved_and_automatic_pass_do_not_force_sample_quality_true(
    tmp_path: Path,
) -> None:
    state = template_state()
    state["quality_gates"] = complete_machine_gates()
    state["sample_quality_ready"] = False
    state["status"] = "accepted"
    approve_review(state)
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 0, result.stderr


def test_report_revision_request_does_not_change_machine_outcome(
    tmp_path: Path,
) -> None:
    state = template_state()
    state.update(
        {
            "status": "accepted",
            "quality_gates": complete_machine_gates(),
            "sample_quality_ready": False,
        }
    )
    request_changes(state, "report_revision")
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 0, result.stderr


def test_automated_quality_defect_change_request_routes_to_needs_fix(
    tmp_path: Path,
) -> None:
    state = template_state()
    request_changes(state, "automated_quality_defect")
    state.update(
        {
            "status": "needs_fix",
            "next_stage": "T9",
            "required_next_skill": "stock-deep-dive",
            "open_todos": [active_report_defect()],
        }
    )
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 0, result.stderr

    invalid = template_state()
    invalid["status"] = "accepted"
    request_changes(invalid, "automated_quality_defect")
    result = run_validator(write_state(tmp_path, invalid))
    assert result.returncode == 1
    assert "requires workflow status needs_fix" in result.stderr


def test_human_approval_cannot_override_automatic_quality_failure(
    tmp_path: Path,
) -> None:
    state = template_state()
    state["sample_quality_ready"] = False
    approve_review(state)
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 0, result.stderr

    state["sample_quality_ready"] = True
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "requires derived automated report quality to pass" in result.stderr
