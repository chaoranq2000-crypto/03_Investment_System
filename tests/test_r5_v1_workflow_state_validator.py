from __future__ import annotations

import copy
import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


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
HISTORICAL_BASELINE = "f60f220ae252262a537c612ce193fc779901984b"
LEGACY_STATE_REL = (
    "reports/workflow_runs/wf_20260703_stock_first_002837_invic/"
    "workflow_state.yaml"
)
LEGACY_STATE_BLOB_OID = "3a9d29405e3f0b5342cf1a2469f1e25c025e50ac"
LEGACY_STATE_BYTES = 81447
LEGACY_STATE_SHA256 = "aabe24082ff80facc55ba5eb51530199e9c2ba9d92d3b43c36e9189d0cdfed10"
V1_REPLAY_STATE_REL = (
    "reports/workflow_runs/wf_20260723_stock_first_002837_v1_replay/"
    "workflow_state.yaml"
)
V1_REPLAY_STATE_BLOB_OID = "18b27d1d27f9f401850b15510954a68c3a1f1323"
V1_REPLAY_STATE_BYTES = 10261
V1_REPLAY_STATE_SHA256 = "23331ce5c47d3a5185e7a098de9af94a5a49f0e461289a9dcdc686066b1972a6"
FIXED_HISTORICAL_STATE_BLOBS = {
    LEGACY_STATE_REL: (
        LEGACY_STATE_BLOB_OID,
        LEGACY_STATE_BYTES,
        LEGACY_STATE_SHA256,
    ),
    V1_REPLAY_STATE_REL: (
        V1_REPLAY_STATE_BLOB_OID,
        V1_REPLAY_STATE_BYTES,
        V1_REPLAY_STATE_SHA256,
    ),
}
FINAL_REVIEW_STATE_FIELDS = {
    "final_report_review_semantics_version",
    "sample_quality_ready",
    "final_report_review_status",
    "final_report_review",
}


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_workflow_state", VALIDATOR_PATH)
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


def git_blob_bytes(revision: str, relative_path: str) -> bytes:
    assert revision == HISTORICAL_BASELINE
    expected_oid, expected_bytes, expected_sha256 = FIXED_HISTORICAL_STATE_BLOBS[
        relative_path
    ]
    spec = f"{revision}:{relative_path}"
    observed_oid = subprocess.check_output(
        ["git", "rev-parse", "--verify", spec],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).strip()
    assert observed_oid == expected_oid
    object_type = subprocess.check_output(
        ["git", "cat-file", "-t", spec],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).strip()
    assert object_type == "blob"
    observed_bytes = int(
        subprocess.check_output(
            ["git", "cat-file", "-s", spec],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
        ).strip()
    )
    assert observed_bytes == expected_bytes
    payload = subprocess.check_output(
        ["git", "cat-file", "blob", spec],
        cwd=ROOT,
    )
    assert len(payload) == expected_bytes
    assert hashlib.sha256(payload).hexdigest() == expected_sha256
    return payload


@pytest.fixture
def legacy_state_fixture(tmp_path: Path) -> Path:
    payload = git_blob_bytes(HISTORICAL_BASELINE, LEGACY_STATE_REL)
    assert hashlib.sha256(payload).hexdigest() == LEGACY_STATE_SHA256
    path = tmp_path / "legacy_workflow_state.yaml"
    path.write_bytes(payload)
    return path


@pytest.fixture
def v1_replay_state_fixture(tmp_path: Path) -> Path:
    payload = git_blob_bytes(HISTORICAL_BASELINE, V1_REPLAY_STATE_REL)
    assert hashlib.sha256(payload).hexdigest() == V1_REPLAY_STATE_SHA256
    path = tmp_path / "v1_replay_workflow_state.yaml"
    path.write_bytes(payload)
    return path


def write_state(tmp_path: Path, state: dict) -> Path:
    path = tmp_path / "workflow_state.yaml"
    path.write_text(
        yaml.safe_dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return path


def template_state() -> dict:
    return yaml.safe_load(TEMPLATE_PATH.read_text(encoding="utf-8"))


def strip_final_review_semantics(state: dict) -> None:
    for field in FINAL_REVIEW_STATE_FIELDS:
        state.pop(field, None)


def scoped_todo(**overrides) -> dict:
    todo = {
        "issue_id": "ISSUE-001",
        "severity": "high",
        "stage": "T9",
        "gate_id": "G7",
        "target_artifact": "reports/workflow_runs/example/report.md",
        "description": "Visible current-goal issue.",
        "fix_owner_skill": "stock-deep-dive",
        "status": "open",
        "impact_scope": "claim",
        "active_disposition": "unknown",
        "affected_capabilities": ["unused_driver"],
        "blocks_current_goal": False,
    }
    todo.update(overrides)
    return todo


def test_versioned_template_and_singleton_names_are_canonical() -> None:
    validator = load_validator()
    assert (
        template_state()["decision_semantics_version"]
        == validator.GOAL_SCOPED_SEMANTICS_VERSION
    )
    assert (
        template_state()["final_report_review_semantics_version"]
        == validator.FINAL_REPORT_REVIEW_SEMANTICS_VERSION
    )
    assert validator.CURRENT_ASSET_NAMES == (
        "workflow_state.yaml",
        "open_todos.csv",
        "quality_gate_report.md",
        "workflow_readout.md",
    )
    result = run_validator(TEMPLATE_PATH)
    assert result.returncode == 0, result.stderr
    assert "legacy compatibility" not in result.stdout

    state = template_state()
    for retired_default in (
        "automated_report_quality_passed",
        "system_v1_complete",
        "p2_ready",
        "release_ready",
    ):
        assert retired_default not in state
    assert "decision" not in state["final_report_review"]


def test_versioned_state_accepts_only_mapped_canonical_gates(tmp_path: Path) -> None:
    state = template_state()
    state["quality_gates"] = [
        {"gate_id": "G0", "status": "pass"},
        {
            "gate_id": "G9",
            "local_check_id": "R5-G10",
            "mapped_global_gate_ids": ["G9"],
            "status": "pass",
        },
        {"gate_id": "G10", "status": "not_checked"},
    ]
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("gate_id", "status"),
    [
        ("G11", "pass"),
        ("G6_G7", "pass"),
        ("R5-G10", "pass"),
        ("G7", "fail_needs_fix"),
    ],
)
def test_versioned_state_rejects_legacy_gate_values(
    tmp_path: Path, gate_id: str, status: str
) -> None:
    state = template_state()
    state["quality_gates"] = [{"gate_id": gate_id, "status": status}]
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1


def test_versioned_state_rejects_duplicate_canonical_gate(tmp_path: Path) -> None:
    state = template_state()
    state["quality_gates"] = [
        {"gate_id": "G7", "status": "pass"},
        {"gate_id": "G7", "status": "not_checked"},
    ]
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "duplicate canonical quality gate" in result.stderr


def test_versioned_state_rejects_night_mission_status(tmp_path: Path) -> None:
    state = template_state()
    state["status"] = "review_intake_ready"
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "invalid status" in result.stderr


def test_protected_legacy_state_remains_read_only_compatible(
    legacy_state_fixture: Path,
) -> None:
    before = hashlib.sha256(legacy_state_fixture.read_bytes()).hexdigest()
    result = run_validator(legacy_state_fixture)
    after = hashlib.sha256(legacy_state_fixture.read_bytes()).hexdigest()
    assert result.returncode == 0, result.stderr
    assert "legacy compatibility" in result.stdout
    assert after == before == LEGACY_STATE_SHA256


def test_protected_v1_replay_state_remains_read_only_compatible(
    v1_replay_state_fixture: Path,
) -> None:
    before = hashlib.sha256(v1_replay_state_fixture.read_bytes()).hexdigest()
    result = run_validator(v1_replay_state_fixture)
    after = hashlib.sha256(v1_replay_state_fixture.read_bytes()).hexdigest()
    assert result.returncode == 0, result.stderr
    assert "legacy r5_v1 compatibility; read-only" in result.stdout
    assert after == before == V1_REPLAY_STATE_SHA256


def test_protected_v1_replay_cannot_claim_sample_quality_without_final_review_marker(
    tmp_path: Path,
    v1_replay_state_fixture: Path,
) -> None:
    state = yaml.safe_load(
        v1_replay_state_fixture.read_text(encoding="utf-8")
    )
    state["sample_quality_ready"] = True
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "legacy sample_quality_ready=true requires" in result.stderr


def test_legacy_project_truth_booleans_remain_optional_and_decoupled(
    tmp_path: Path,
) -> None:
    state = template_state()
    state["system_v1_complete"] = True
    state["release_ready"] = True
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 0, result.stderr


def test_p2_ready_true_is_scoped_to_comparison_readiness_runs(tmp_path: Path) -> None:
    state = template_state()
    state["p2_ready"] = True
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert (
        "p2_ready=true requires workflow_type=comparison_readiness_gate"
        in result.stderr
    )

    state["workflow_type"] = "comparison_readiness_gate"
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 0, result.stderr


def test_legacy_automated_quality_boolean_must_equal_derived_value(
    tmp_path: Path,
) -> None:
    state = template_state()
    state["automated_report_quality_passed"] = False
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 0, result.stderr

    state["automated_report_quality_passed"] = True
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "must equal the value derived" in result.stderr

    state["status"] = "accepted"
    state["quality_gates"] = [
        {"gate_id": f"G{index}", "status": "pass"} for index in range(11)
    ]
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 0, result.stderr

    state["automated_report_quality_passed"] = False
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "must equal the value derived" in result.stderr


def test_unknown_state_schema_version_fails(tmp_path: Path) -> None:
    state = copy.deepcopy(template_state())
    state["state_schema_version"] = "r5_v2"
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "unsupported state_schema_version" in result.stderr


def test_unmarked_r5_v1_state_is_explicit_read_only_compatibility(
    tmp_path: Path,
) -> None:
    state = template_state()
    state.pop("decision_semantics_version")
    strip_final_review_semantics(state)
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 0, result.stderr
    assert "legacy r5_v1 compatibility; read-only" in result.stdout


def test_current_goal_state_cannot_downgrade_away_final_review_semantics(
    tmp_path: Path,
) -> None:
    state = template_state()
    strip_final_review_semantics(state)
    state["human_review_status"] = "historical_pending"
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "current_goal_v1 requires" in result.stderr


def test_unknown_final_report_review_semantics_version_fails(tmp_path: Path) -> None:
    state = template_state()
    state["final_report_review_semantics_version"] = "final_report_review_v2"
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "unsupported final_report_review_semantics_version" in result.stderr


def test_partial_final_report_review_schema_cannot_bypass_marker(
    tmp_path: Path,
) -> None:
    state = template_state()
    state.pop("final_report_review_semantics_version")
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "final-report review fields require" in result.stderr


def test_sample_quality_cannot_bypass_final_review_marker(tmp_path: Path) -> None:
    state = template_state()
    strip_final_review_semantics(state)
    state["sample_quality_ready"] = True
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "final-report review fields require" in result.stderr


def test_current_goal_state_requires_scoped_issue_fields(tmp_path: Path) -> None:
    state = template_state()
    todo = scoped_todo()
    todo.pop("impact_scope")
    state["open_todos"] = [todo]
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "impact_scope is required for current_goal_v1" in result.stderr


def test_visible_unused_high_unknown_allows_accepted_with_todos(
    tmp_path: Path,
) -> None:
    state = template_state()
    state["status"] = "accepted_with_todos"
    state["open_todos"] = [scoped_todo(severity="high")]
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "description",
    [
        "unsupported number used by the report",
        "real double-count in a calculation",
        "hidden TODO in a material section",
        "no-advice violation in the report",
    ],
)
def test_current_output_defects_require_needs_fix(
    tmp_path: Path, description: str
) -> None:
    state = template_state()
    state.update(
        {
            "status": "needs_fix",
            "next_stage": "T7",
            "required_next_skill": "stock-deep-dive",
            "open_todos": [
                scoped_todo(
                    description=description,
                    impact_scope="report",
                    active_disposition="active_defect",
                    affected_capabilities=["current_report"],
                    blocks_current_goal=True,
                )
            ],
        }
    )
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 0, result.stderr

    state["status"] = "accepted_with_todos"
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "expected needs_fix" in result.stderr


@pytest.mark.parametrize("failure_kind", ["identity", "path", "parse", "source"])
def test_failure_preventing_any_honest_output_is_blocked(
    tmp_path: Path, failure_kind: str
) -> None:
    state = template_state()
    state["status"] = "blocked"
    state["open_todos"] = [
        scoped_todo(
            description=f"{failure_kind} failure prevents any honest target output",
            impact_scope="workflow",
            active_disposition="active_defect",
            affected_capabilities=["honest_target_output"],
            blocks_current_goal=True,
        )
    ]
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 0, result.stderr


def test_required_method_unavailable_is_blocked(tmp_path: Path) -> None:
    state = template_state()
    state["status"] = "blocked"
    state["open_todos"] = [
        scoped_todo(
            impact_scope="method",
            active_disposition="method_unavailable",
            affected_capabilities=["contract_required_method"],
            blocks_current_goal=True,
        )
    ]
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 0, result.stderr


def test_optional_method_unavailable_allows_accepted_with_todos(
    tmp_path: Path,
) -> None:
    state = template_state()
    state["status"] = "accepted_with_todos"
    state["open_todos"] = [
        scoped_todo(
            impact_scope="method",
            active_disposition="method_unavailable",
            affected_capabilities=["optional_valuation_method"],
            blocks_current_goal=False,
        )
    ]
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 0, result.stderr


def test_policy_retired_has_no_canonical_impact(tmp_path: Path) -> None:
    state = template_state()
    state["status"] = "accepted"
    state["open_todos"] = [
        scoped_todo(
            impact_scope="none",
            active_disposition="policy_retired",
            affected_capabilities=[],
            blocks_current_goal=False,
        )
    ]
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 0, result.stderr


def test_active_defect_cannot_be_nonblocking(tmp_path: Path) -> None:
    state = template_state()
    state["status"] = "accepted_with_todos"
    state["open_todos"] = [
        scoped_todo(
            impact_scope="report",
            active_disposition="active_defect",
            affected_capabilities=["current_report"],
            blocks_current_goal=False,
        )
    ]
    result = run_validator(write_state(tmp_path, state))
    assert result.returncode == 1
    assert "active_defect must block the current goal" in result.stderr
