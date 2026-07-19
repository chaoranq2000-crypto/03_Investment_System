from __future__ import annotations

from pathlib import Path

import pytest

from src.maintenance.night_shift.models import ContractError
from src.maintenance.night_shift.publication import (
    build_implementation_identity,
    build_publication_identity,
    resolve_baseline,
    validate_stable_digest,
)


def test_stale_tracked_baseline_resolves_to_final_remote_head() -> None:
    resolution = resolve_baseline(
        tracked_source_commit="f89a3ab71fa8dbb43d004f01bd19b64111721e80",
        final_remote_head="4340945457d661ed62967e949f862ccf2214aff2",
    )
    assert resolution["stale"] is True
    assert resolution["resolved_source_commit"] == "4340945457d661ed62967e949f862ccf2214aff2"


def test_two_phase_identity_does_not_self_reference() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    implementation = build_implementation_identity(repo_root)
    assert implementation["publication_head"] is None
    receipt = build_publication_identity(
        implementation_receipt_sha256="a" * 64,
        local_head="b" * 40,
        remote_head="b" * 40,
        ci_status="success",
        ci_run_id="123",
    )
    assert receipt["publication_head"] == "b" * 40
    assert validate_stable_digest(receipt) == receipt["stable_receipt_sha256"]


def test_publication_refuses_remote_mismatch() -> None:
    with pytest.raises(ContractError, match="mismatch"):
        build_publication_identity(
            implementation_receipt_sha256="a" * 64,
            local_head="b" * 40,
            remote_head="c" * 40,
            ci_status="success",
        )
