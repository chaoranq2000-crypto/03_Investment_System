from __future__ import annotations

import copy
import subprocess
from pathlib import Path

import pytest

from src.maintenance.night_shift.contracts import (
    capture_tree_snapshot,
    enforce_task_scope,
    generate_contract_proposal,
    route_pointer_contract,
    validate_allowed_paths,
    validate_review_packet,
)
from src.maintenance.night_shift.models import ContractError
from src.maintenance.night_shift.outcome import MissionOutcome, outcome_for_pilot_evidence
from src.maintenance.night_shift.publication import require_sha256, resolve_baseline
from src.maintenance.night_shift.receipts import parse_trusted_command
from src.maintenance.night_shift.targets import GitTarget


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_empty_paths_and_placeholder_commands_fail_closed() -> None:
    with pytest.raises(ContractError, match="declare exact paths"):
        validate_allowed_paths([])
    with pytest.raises(ContractError, match="placeholder"):
        parse_trusted_command("python <resolved_command>")


def test_no_safe_pilot_and_stale_baseline_cannot_fake_success() -> None:
    assert outcome_for_pilot_evidence("no_safe_pilot") is MissionOutcome.BLOCKED
    resolved = resolve_baseline(
        tracked_source_commit="a" * 40,
        final_remote_head="b" * 40,
    )
    assert resolved["stale"] is True
    assert resolved["resolved_source_commit"] == "b" * 40


def test_malformed_digest_and_path_branch_glue_are_rejected() -> None:
    with pytest.raises(ContractError):
        require_sha256("a" * 41, field="receipt_sha256")
    with pytest.raises(ContractError, match="branch fragment"):
        GitTarget.create(
            r"C:\Projects\03_Investment_System_night02codex/r5-night02-contract-recovery",
            "codex/r5-night02-contract-recovery",
        )


def test_out_of_scope_diff_is_rejected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    (repo / "src").mkdir()
    (repo / "reports").mkdir()
    (repo / "src/allowed.py").write_text("ok\n", encoding="utf-8")
    (repo / "reports/immutable.md").write_text("before\n", encoding="utf-8")
    _git(repo, "add", ".")
    before = capture_tree_snapshot(repo)
    (repo / "reports/immutable.md").write_text("after\n", encoding="utf-8")
    with pytest.raises(ContractError, match="scope violation"):
        enforce_task_scope(
            before,
            capture_tree_snapshot(repo),
            allowed_paths=["src/**"],
            forbidden_paths=["reports/**"],
        )


def test_fake_human_review_and_legacy_field_mapping_are_rejected() -> None:
    packet = generate_contract_proposal(
        task_id="ns02_t25_review_packet_hash_lock",
        source_artifact="reports/source.json",
        owner_skill="quality-review",
        requested_action="review exact contract",
        candidate_paths=["src/maintenance/night_shift/contracts.py"],
        acceptance_commands=["python -m pytest -q tests/test_r5_night_shift_adversarial.py"],
        generator_version="night02-v1",
    )
    fake = copy.deepcopy(packet)
    fake.update(
        {
            "review_state": "approved",
            "review_sha": packet["proposal_sha256"],
            "reviewer": "",
            "reviewed_at": "",
            "decision": "approved",
        }
    )
    with pytest.raises(ContractError):
        validate_review_packet(fake, require_approved=True)

    route = route_pointer_contract(
        missing_pointer="/generation_id",
        observed_fields=["/case_id", "/artifact_type", "/legacy_generation"],
    )
    assert route["candidate_pointer"] is None
    assert route["resolution_claim_allowed"] is False
