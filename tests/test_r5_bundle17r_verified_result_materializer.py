from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.research.r5_bundle17r_verified_result_materializer import (
    VerifiedResultError,
    build_work_orders,
    row_sha256,
    run_materialization,
    sha256_file,
)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_yaml(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=True), encoding="utf-8")


def init_git(root: Path) -> str:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Tests"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture baseline"], cwd=root, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def build_fixture(root: Path, *, manual_route: bool = False) -> dict[str, Any]:
    policy = {
        "schema_version": "fixture",
        "require_generation_lock_coverage": True,
        "allowed_source_roots": [".local/", "reports/", "src/", "tests/", "docs/", "config/"],
        "allowed_repo_prefixes": ["src/", "tests/", "docs/", "config/", "reports/"],
        "repo_candidate_extensions": [".py", ".md", ".json", ".yaml", ".csv"],
        "archive_extensions": [".zip", ".png", ".log"],
        "reject_path_patterns": ["*__pycache__*", "*.pyc", "*.env*", "*secret*", "*token*"],
        "manual_routes": ["evidence_mapping_qualification"] if manual_route else [],
    }
    write_yaml(root / "config/policy.yaml", policy)

    work_a = {
        "work_order_id": "WO-A",
        "case_id": "CASE-A",
        "route_id": "evidence_mapping_qualification" if manual_route else "physical_binding_integrity",
        "issue_ids": "BLK-A",
        "acceptance_checks": "check A exact",
        "depends_on": "",
    }
    work_b = {
        "work_order_id": "WO-B",
        "case_id": "CASE-A",
        "route_id": "operating_driver_economics",
        "issue_ids": "BLK-B",
        "acceptance_checks": "check B exact",
        "depends_on": "WO-A",
    }
    work_fields = list(work_a)
    write_csv(root / "reports/bf1/work_orders.csv", work_fields, [work_a, work_b])
    write_csv(
        root / "reports/bf1/issues.csv",
        ["issue_id", "case_id", "work_order_id", "message"],
        [
            {"issue_id": "BLK-A", "case_id": "CASE-A", "work_order_id": "WO-A", "message": "a"},
            {"issue_id": "BLK-B", "case_id": "CASE-A", "work_order_id": "WO-B", "message": "b"},
        ],
    )
    lock = {
        "schema_version": "fixture",
        "artifacts": [
            {"path": "reports/bf1/work_orders.csv", "sha256": sha256_file(root / "reports/bf1/work_orders.csv")},
            {"path": "reports/bf1/issues.csv", "sha256": sha256_file(root / "reports/bf1/issues.csv")},
        ],
    }
    (root / "reports/bf1/generation_lock.json").write_text(
        json.dumps(lock, sort_keys=True), encoding="utf-8"
    )

    # Commit the source BF1 generation and policy so the declared baseline is a real ancestor.
    baseline = init_git(root)

    specs = root / ".local/specs"
    for work_id, text in (("WO-A", "evidence A\n"), ("WO-B", "evidence B\n")):
        (specs / work_id / "evidence").mkdir(parents=True, exist_ok=True)
        (specs / work_id / "outputs").mkdir(parents=True, exist_ok=True)
        (specs / work_id / "evidence/check.txt").write_text(text, encoding="utf-8")
        (specs / work_id / "outputs/fix.py").write_text(
            f"VALUE = '{work_id}'\n", encoding="utf-8"
        )
    if manual_route:
        (specs / "WO-A/review").mkdir(parents=True, exist_ok=True)
        (specs / "WO-A/review/attestation.yaml").write_text(
            "reviewer: human@example\naccepted: true\n", encoding="utf-8"
        )

    def spec_payload(work: dict[str, str], acceptance: str) -> dict[str, Any]:
        work_id = work["work_order_id"]
        result: dict[str, Any] = {
            "schema_version": "r5_bundle17r_bf2_ex1_work_order_spec_v1",
            "work_order_id": work_id,
            "case_id": work["case_id"],
            "execution_status": "passed",
            "resolved_blocker_ids": [work["issue_ids"]],
            "checks": [
                {
                    "id": f"check-{work_id}",
                    "acceptance_check": acceptance,
                    "status": "passed",
                    "verifier": "pytest",
                    "evidence": {
                        "source_root": "spec_dir",
                        "path": f"{work_id}/evidence/check.txt",
                        "sha256": sha256_file(specs / work_id / "evidence/check.txt"),
                        "kind": "test_report",
                    },
                }
            ],
            "produced_artifacts": [
                {
                    "source_root": "spec_dir",
                    "path": f"{work_id}/outputs/fix.py",
                    "sha256": sha256_file(specs / work_id / "outputs/fix.py"),
                    "disposition": "repo_candidate",
                    "promotion_target": f"src/research/{work_id.lower()}_fix.py",
                }
            ],
        }
        return result

    spec_a = spec_payload(work_a, "check A exact")
    if manual_route:
        spec_a["manual_attestation"] = {
            "reviewer": "human@example",
            "signed": True,
            "source_root": "spec_dir",
            "attestation_path": "WO-A/review/attestation.yaml",
            "attestation_sha256": sha256_file(specs / "WO-A/review/attestation.yaml"),
        }
    write_yaml(specs / "WO-A/spec.yaml", spec_a)
    write_yaml(specs / "WO-B/spec.yaml", spec_payload(work_b, "check B exact"))

    manifest = {
        "schema_version": "r5_bundle17r_bf2_ex1_manifest_v1",
        "bundle_id": "fixture-ex1",
        "source_baseline_commit": baseline,
        "as_of": "2026-07-18",
        "policy_path": "config/policy.yaml",
        "inputs": {
            "generation_lock": {
                "path": "reports/bf1/generation_lock.json",
                "sha256": sha256_file(root / "reports/bf1/generation_lock.json"),
            },
            "work_orders": {
                "path": "reports/bf1/work_orders.csv",
                "sha256": sha256_file(root / "reports/bf1/work_orders.csv"),
            },
            "issue_ledger": {
                "path": "reports/bf1/issues.csv",
                "sha256": sha256_file(root / "reports/bf1/issues.csv"),
            },
        },
        "result_specs_dir": ".local/specs",
        "output_dropzone": ".local/results",
        "output_dir": "reports/ex1",
    }
    manifest_path = root / ".local/ex1_manifest.yaml"
    write_yaml(manifest_path, manifest)
    return {
        "root": root,
        "manifest_path": manifest_path,
        "specs": specs,
        "work_a": work_a,
        "work_b": work_b,
    }


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_materializes_hash_backed_bf2_results_and_dependencies(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    result = run_materialization(tmp_path, fixture["manifest_path"])
    report = result["report"]
    assert report["engineering_pass_count"] == 2
    assert report["resolved_blocker_occurrence_count"] == 2
    assert report["unresolved_blocker_occurrence_count"] == 0
    assert report["sample_quality_allowed"] is False
    assert report["p2_allowed"] is False

    payload_a = yaml.safe_load((tmp_path / ".local/results/WO-A/result.yaml").read_text())
    payload_b = yaml.safe_load((tmp_path / ".local/results/WO-B/result.yaml").read_text())
    assert payload_a["source_work_order_sha256"] == row_sha256(fixture["work_a"])
    assert payload_b["materialization"]["verified_dependencies"] == ["WO-A"]
    assert len(payload_a["checks"][0]["evidence_sha256"]) == 64
    assert payload_a["produced_artifacts"][0]["source_root"] == "dropzone"
    assert payload_a["execution_status"] == "engineering_pass"


def test_accepts_mapping_keyed_bf1_generation_lock(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    root = fixture["root"]
    work_orders_path = root / "reports/bf1/work_orders.csv"
    issues_path = root / "reports/bf1/issues.csv"
    lock_path = root / "reports/bf1/generation_lock.json"
    lock_path.write_text(
        json.dumps(
            {
                "schema_version": "real_bf1_shape",
                "output_artifacts": {
                    work_orders_path.name: {
                        "sha256": sha256_file(work_orders_path),
                        "size_bytes": work_orders_path.stat().st_size,
                    },
                    issues_path.name: {
                        "sha256": sha256_file(issues_path),
                        "size_bytes": issues_path.stat().st_size,
                    },
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    manifest = yaml.safe_load(fixture["manifest_path"].read_text(encoding="utf-8"))
    manifest["inputs"]["generation_lock"]["sha256"] = sha256_file(lock_path)
    write_yaml(fixture["manifest_path"], manifest)

    result = run_materialization(root, fixture["manifest_path"])

    assert result["report"]["source_work_orders"]["count"] == 2
    assert result["report"]["source_issue_ledger"]["occurrence_count"] == 2


def test_normalizes_empty_suite_case_id_for_bf2() -> None:
    work_orders = build_work_orders(
        [
            {
                "work_order_id": "WO-SUITE",
                "case_id": "",
                "route_id": "rerun_chain",
                "issue_ids": "",
                "acceptance_checks": "suite check",
                "depends_on": "",
            }
        ]
    )

    assert work_orders["WO-SUITE"].case_id == "__suite__"


def test_missing_or_mismatched_check_evidence_fails_closed(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    spec_path = fixture["specs"] / "WO-A/spec.yaml"
    spec = yaml.safe_load(spec_path.read_text())
    spec["checks"][0]["evidence"]["sha256"] = "0" * 64
    write_yaml(spec_path, spec)
    with pytest.raises(VerifiedResultError, match="hash mismatch"):
        run_materialization(tmp_path, fixture["manifest_path"])


def test_pass_claim_fails_when_dependency_is_pending(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    (fixture["specs"] / "WO-A/spec.yaml").unlink()
    with pytest.raises(VerifiedResultError, match="incomplete dependencies"):
        run_materialization(tmp_path, fixture["manifest_path"])


def test_promotion_target_collision_with_different_hashes_fails(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    spec_path = fixture["specs"] / "WO-B/spec.yaml"
    spec = yaml.safe_load(spec_path.read_text())
    spec["produced_artifacts"][0]["promotion_target"] = "src/research/wo-a_fix.py"
    write_yaml(spec_path, spec)
    with pytest.raises(VerifiedResultError, match="promotion target collision"):
        run_materialization(tmp_path, fixture["manifest_path"])


def test_manual_route_requires_hash_backed_attestation(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path, manual_route=True)
    run_materialization(tmp_path, fixture["manifest_path"])
    result = yaml.safe_load((tmp_path / ".local/results/WO-A/result.yaml").read_text())
    assert result["manual_attestation"]["signed"] is True
    assert len(result["manual_attestation"]["attestation_sha256"]) == 64

    spec_path = fixture["specs"] / "WO-A/spec.yaml"
    spec = yaml.safe_load(spec_path.read_text())
    del spec["manual_attestation"]
    write_yaml(spec_path, spec)
    with pytest.raises(VerifiedResultError, match="requires manual_attestation"):
        run_materialization(tmp_path, fixture["manifest_path"])



def test_acceptance_check_text_must_match_bf1_exactly(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    spec_path = fixture["specs"] / "WO-A/spec.yaml"
    spec = yaml.safe_load(spec_path.read_text())
    spec["checks"][0]["acceptance_check"] = "paraphrased check"
    write_yaml(spec_path, spec)
    with pytest.raises(VerifiedResultError, match="acceptance-check coverage mismatch"):
        run_materialization(tmp_path, fixture["manifest_path"])


def test_work_order_cannot_resolve_blocker_absent_from_source_ledger(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    work_orders = tmp_path / "reports/bf1/work_orders.csv"
    rows = list(csv.DictReader(work_orders.open(encoding="utf-8", newline="")))
    rows[0]["issue_ids"] = "BLK-NOT-IN-LEDGER"
    write_csv(work_orders, list(rows[0]), rows)
    lock_path = tmp_path / "reports/bf1/generation_lock.json"
    lock = json.loads(lock_path.read_text())
    for artifact in lock["artifacts"]:
        if artifact["path"] == "reports/bf1/work_orders.csv":
            artifact["sha256"] = sha256_file(work_orders)
    lock_path.write_text(json.dumps(lock, sort_keys=True), encoding="utf-8")
    manifest = yaml.safe_load(fixture["manifest_path"].read_text())
    manifest["inputs"]["generation_lock"]["sha256"] = sha256_file(lock_path)
    manifest["inputs"]["work_orders"]["sha256"] = sha256_file(work_orders)
    write_yaml(fixture["manifest_path"], manifest)
    subprocess.run(["git", "add", "reports/bf1/work_orders.csv", "reports/bf1/generation_lock.json"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "updated fixture generation"], cwd=tmp_path, check=True)
    manifest["source_baseline_commit"] = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True, capture_output=True, text=True
    ).stdout.strip()
    write_yaml(fixture["manifest_path"], manifest)
    with pytest.raises(VerifiedResultError, match="absent from issue ledger"):
        run_materialization(tmp_path, fixture["manifest_path"])


def test_orphan_existing_result_directory_fails_closed(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    orphan = tmp_path / ".local/results/WO-ORPHAN"
    orphan.mkdir(parents=True)
    write_yaml(orphan / "result.yaml", {"work_order_id": "WO-ORPHAN"})
    with pytest.raises(VerifiedResultError, match="orphan BF2 result directories"):
        run_materialization(tmp_path, fixture["manifest_path"])

def test_identical_inputs_produce_identical_output_tree(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    out_a = tmp_path / "out-a"
    out_b = tmp_path / "out-b"
    run_materialization(tmp_path, fixture["manifest_path"], out_a)
    first = snapshot(out_a)
    run_materialization(tmp_path, fixture["manifest_path"], out_b)
    second = snapshot(out_b)
    assert first == second
