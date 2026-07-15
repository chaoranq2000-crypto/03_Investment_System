from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from src.research.r5_bundle17r_activation_receipt import (
    ActivationContractError,
    evaluate_activation,
    sha256_file,
    write_activation_outputs,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config" / "r5_bundle17r_activation_policy.yaml"
BASELINE = "7ab395283f432faac7bbc0e83a0b0cf4976ed5dc"


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def write_yaml(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def binding(root: Path, path: Path) -> dict[str, str]:
    return {"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path)}


def build_valid_fixture(tmp_path: Path) -> tuple[Path, dict]:
    reports = tmp_path / "reports" / "runs"
    stage_docs = {
        "materialization": {
            "case_count": 4,
            "pack_materialized_count": 4,
            "fully_mapped_case_count": 4,
            "blocker_count": 0,
            "canonical_workflow_state_mutation_allowed": False,
            "sample_quality_allowed": False,
            "p2_allowed": False,
        },
        "qualification": {
            "case_count": 4,
            "evidence_pack_complete_count": 4,
            "bundle14r_candidate_ready_count": 4,
            "blocker_count": 0,
            "workflow_state_mutation_allowed": False,
            "sample_quality_allowed": False,
            "p2_allowed": False,
        },
        "regression": {
            "contract_passed": True,
            "research_ready_case_count": 4,
            "candidate_ready_case_count": 4,
            "release_authority": False,
            "workflow_state_mutation_allowed": False,
            "sample_quality_allowed": False,
            "p2_allowed": False,
        },
    }
    stage_bindings = {}
    stage_assertions = {
        "materialization": {
            "case_count": "/case_count",
            "packs_materialized": "/pack_materialized_count",
            "fully_mapped": "/fully_mapped_case_count",
            "blockers_zero": "/blocker_count",
            "canonical_mutation_false": "/canonical_workflow_state_mutation_allowed",
            "sample_quality_false": "/sample_quality_allowed",
            "p2_false": "/p2_allowed",
            "suite_hash_bound": {"artifact": "generation_lock", "pointer": "/suite_sha256"},
            "generation_id_present": {"artifact": "generation_lock", "pointer": "/generation_id"},
        },
        "qualification": {
            "case_count": "/case_count",
            "packs_complete": "/evidence_pack_complete_count",
            "bundle14_ready": "/bundle14r_candidate_ready_count",
            "blockers_zero": "/blocker_count",
            "canonical_mutation_false": "/workflow_state_mutation_allowed",
            "sample_quality_false": "/sample_quality_allowed",
            "p2_false": "/p2_allowed",
            "suite_hash_bound": {"artifact": "generation_lock", "pointer": "/suite_sha256"},
            "generation_id_present": {"artifact": "generation_lock", "pointer": "/generation_id"},
        },
        "regression": {
            "contract_passed": "/contract_passed",
            "research_ready_count": "/research_ready_case_count",
            "candidate_ready_count": "/candidate_ready_case_count",
            "release_authority_false": "/release_authority",
            "canonical_mutation_false": "/workflow_state_mutation_allowed",
            "sample_quality_false": "/sample_quality_allowed",
            "p2_false": "/p2_allowed",
            "suite_hash_bound": {"artifact": "generation_lock", "pointer": "/suite_result_sha256"},
            "generation_id_present": {"artifact": "generation_lock", "pointer": "/generation_id"},
        },
    }
    for stage, document in stage_docs.items():
        suite = reports / stage / "suite.json"
        lock = reports / stage / "generation_lock.json"
        write_json(suite, document)
        lock_hash_field = "suite_result_sha256" if stage == "regression" else "suite_sha256"
        write_json(lock, {"generation_id": f"{stage}_gen_1", lock_hash_field: sha256_file(suite)})
        stage_bindings[stage] = {
            "suite": binding(tmp_path, suite),
            "generation_lock": binding(tmp_path, lock),
            "assertions": stage_assertions[stage],
        }

    cases = []
    for index in range(4):
        case_id = f"case_{index + 1}"
        ticker = f"00000{index + 1}.SZ"
        case_root = reports / "cases" / case_id
        case_contract = case_root / "case_contract.yaml"
        qualification = case_root / "qualification.yaml"
        regression = case_root / "regression.json"
        reader = case_root / "reader.md"
        quality = case_root / "quality.yaml"
        traceability = case_root / "traceability.yaml"
        lock = case_root / "generation_lock.json"
        write_yaml(case_contract, {"case_id": case_id, "issuer": {"ticker": ticker}})
        write_yaml(
            qualification,
            {
                "case_id": case_id,
                "qualified_driver_ids": ["driver_1"],
                "reviewed_official_source_count": 2,
                "overlap_resolved": True,
                "forecast_bridge_complete": True,
                "valuation_eligible": True,
                "semantic_gate_passed": True,
                "deterministic_rerun": True,
                "exact_hash_human_review_status": "pending",
                "bundle15r_audit": {"evidence_pack_complete": True},
            },
        )
        write_json(
            regression,
            {
                "case_id": case_id,
                "research_ready": True,
                "candidate_ready_for_exact_hash_review": True,
            },
        )
        reader.parent.mkdir(parents=True, exist_ok=True)
        reader.write_text((f"# {case_id}\n\n" + "company-specific research evidence and causal analysis. " * 40), encoding="utf-8")
        write_yaml(quality, {"case_id": case_id, "candidate_ready_for_exact_hash_review": True})
        write_yaml(traceability, {"case_id": case_id, "resolved_citations": 12})
        write_json(
            lock,
            {
                "generation_id": f"reader_gen_{case_id}",
                "artifacts": {
                    "reader": {"sha256": sha256_file(reader)},
                    "quality_scorecard": {"sha256": sha256_file(quality)},
                    "traceability": {"sha256": sha256_file(traceability)},
                },
            },
        )
        cases.append(
            {
                "case_id": case_id,
                "issuer_ticker": ticker,
                "artifacts": {
                    "case_contract": binding(tmp_path, case_contract),
                    "qualification": binding(tmp_path, qualification),
                    "regression_result": binding(tmp_path, regression),
                    "reader": binding(tmp_path, reader),
                    "generation_lock": binding(tmp_path, lock),
                    "quality_scorecard": binding(tmp_path, quality),
                    "traceability": binding(tmp_path, traceability),
                },
                "assertions": {
                    "contract_case_id": {"artifact": "case_contract", "pointer": "/case_id"},
                    "contract_issuer_ticker": {"artifact": "case_contract", "pointer": "/issuer/ticker"},
                    "qualification_case_id": {"artifact": "qualification", "pointer": "/case_id"},
                    "qualification_evidence_complete": {"artifact": "qualification", "pointer": "/bundle15r_audit/evidence_pack_complete"},
                    "qualification_official_sources_present": {"artifact": "qualification", "pointer": "/reviewed_official_source_count"},
                    "qualification_drivers_present": {"artifact": "qualification", "pointer": "/qualified_driver_ids"},
                    "qualification_overlap_resolved": {"artifact": "qualification", "pointer": "/overlap_resolved"},
                    "qualification_forecast_bridge_complete": {"artifact": "qualification", "pointer": "/forecast_bridge_complete"},
                    "qualification_valuation_eligible": {"artifact": "qualification", "pointer": "/valuation_eligible"},
                    "qualification_semantic_gate_passed": {"artifact": "qualification", "pointer": "/semantic_gate_passed"},
                    "qualification_deterministic_rerun": {"artifact": "qualification", "pointer": "/deterministic_rerun"},
                    "qualification_review_status_present": {"artifact": "qualification", "pointer": "/exact_hash_human_review_status"},
                    "regression_case_id": {"artifact": "regression_result", "pointer": "/case_id"},
                    "regression_research_ready": {"artifact": "regression_result", "pointer": "/research_ready"},
                    "regression_candidate_ready": {"artifact": "regression_result", "pointer": "/candidate_ready_for_exact_hash_review"},
                    "quality_case_id": {"artifact": "quality_scorecard", "pointer": "/case_id"},
                    "quality_gate_pass": {"artifact": "quality_scorecard", "pointer": "/candidate_ready_for_exact_hash_review"},
                    "generation_id_present": {"artifact": "generation_lock", "pointer": "/generation_id"},
                    "reader_hash_bound": {"artifact": "generation_lock", "pointer": "/artifacts/reader/sha256"},
                    "quality_hash_bound": {"artifact": "generation_lock", "pointer": "/artifacts/quality_scorecard/sha256"},
                    "traceability_hash_bound": {"artifact": "generation_lock", "pointer": "/artifacts/traceability/sha256"},
                },
            }
        )
    manifest = {
        "schema_version": "r5_bundle17r_activation_manifest_v1",
        "baseline_commit": BASELINE,
        "run_id": "synthetic_valid_run",
        "stage_bindings": stage_bindings,
        "cases": cases,
    }
    manifest_path = tmp_path / "reports" / "activation_manifest.yaml"
    write_yaml(manifest_path, manifest)
    return manifest_path, manifest


def evaluate(tmp_path: Path, manifest_path: Path):
    return evaluate_activation(repo_root=tmp_path, manifest_path=manifest_path, policy_path=POLICY)


def rewrite_manifest(path: Path, manifest: dict) -> None:
    write_yaml(path, manifest)


def test_valid_four_case_activation_is_ready_but_not_released(tmp_path):
    manifest_path, _ = build_valid_fixture(tmp_path)
    result = evaluate(tmp_path, manifest_path)
    assert result.receipt.decision == "activation_ready_for_exact_hash_human_review"
    assert result.receipt.run_id == "synthetic_valid_run"
    assert len(result.receipt.policy_sha256) == 64
    assert len(result.receipt.runtime_sha256) == 64
    assert result.receipt.next_stage == "R5_bundle18r_exact_hash_human_review"
    assert result.receipt.engineering_pass_count == 4
    assert result.receipt.blocker_count == 0
    assert result.receipt.sample_quality_allowed is False
    assert result.receipt.p2_allowed is False
    assert all(item["review_status"] == "pending" for item in result.handoffs.values())
    assert all(item["reviewer"] is None for item in result.handoffs.values())


def test_missing_run_id_is_rejected(tmp_path):
    manifest_path, manifest = build_valid_fixture(tmp_path)
    manifest["run_id"] = ""
    rewrite_manifest(manifest_path, manifest)
    with pytest.raises(ActivationContractError):
        evaluate(tmp_path, manifest_path)


def test_missing_case_fails_closed(tmp_path):
    manifest_path, manifest = build_valid_fixture(tmp_path)
    manifest["cases"] = manifest["cases"][:3]
    rewrite_manifest(manifest_path, manifest)
    result = evaluate(tmp_path, manifest_path)
    assert result.receipt.decision == "needs_targeted_backflow"
    assert "CASE_COUNT_MISMATCH" in {issue.code for issue in result.issues}


def test_duplicate_case_fails_closed(tmp_path):
    manifest_path, manifest = build_valid_fixture(tmp_path)
    manifest["cases"][1]["case_id"] = manifest["cases"][0]["case_id"]
    rewrite_manifest(manifest_path, manifest)
    result = evaluate(tmp_path, manifest_path)
    assert "CASE_ID_DUPLICATE" in {issue.code for issue in result.issues}


def test_manifest_ticker_must_match_registered_case_contract(tmp_path):
    manifest_path, manifest = build_valid_fixture(tmp_path)
    manifest["cases"][0]["issuer_ticker"] = "999999.SZ"
    rewrite_manifest(manifest_path, manifest)
    result = evaluate(tmp_path, manifest_path)
    assert result.receipt.engineering_pass_count == 3
    assert "ASSERTION_FAILED" in {issue.code for issue in result.issues}


def test_hash_mismatch_fails_closed(tmp_path):
    manifest_path, manifest = build_valid_fixture(tmp_path)
    manifest["cases"][0]["artifacts"]["reader"]["sha256"] = "0" * 64
    rewrite_manifest(manifest_path, manifest)
    result = evaluate(tmp_path, manifest_path)
    assert "ARTIFACT_HASH_MISMATCH" in {issue.code for issue in result.issues}


def test_path_traversal_is_rejected(tmp_path):
    manifest_path, manifest = build_valid_fixture(tmp_path)
    manifest["cases"][0]["artifacts"]["reader"]["path"] = "../escape.md"
    rewrite_manifest(manifest_path, manifest)
    result = evaluate(tmp_path, manifest_path)
    assert "UNSAFE_ARTIFACT_PATH" in {issue.code for issue in result.issues}


def test_sample_path_is_rejected(tmp_path):
    manifest_path, manifest = build_valid_fixture(tmp_path)
    old = tmp_path / manifest["cases"][0]["artifacts"]["reader"]["path"]
    sample = tmp_path / "reports" / "samples" / "reader.md"
    sample.parent.mkdir(parents=True)
    sample.write_bytes(old.read_bytes())
    manifest["cases"][0]["artifacts"]["reader"] = binding(tmp_path, sample)
    rewrite_manifest(manifest_path, manifest)
    result = evaluate(tmp_path, manifest_path)
    assert "UNSAFE_ARTIFACT_PATH" in {issue.code for issue in result.issues}


def test_suite_assertion_failure_routes_backflow(tmp_path):
    manifest_path, manifest = build_valid_fixture(tmp_path)
    suite_path = tmp_path / manifest["stage_bindings"]["materialization"]["suite"]["path"]
    suite = json.loads(suite_path.read_text())
    suite["pack_materialized_count"] = 3
    write_json(suite_path, suite)
    manifest["stage_bindings"]["materialization"]["suite"]["sha256"] = sha256_file(suite_path)
    rewrite_manifest(manifest_path, manifest)
    result = evaluate(tmp_path, manifest_path)
    assert "ASSERTION_FAILED" in {issue.code for issue in result.issues}
    assert result.receipt.engineering_pass_count == 0
    assert all(item["review_status"] == "not_ready" for item in result.handoffs.values())
    assert result.receipt.decision == "needs_targeted_backflow"


def test_missing_required_assertion_fails(tmp_path):
    manifest_path, manifest = build_valid_fixture(tmp_path)
    del manifest["cases"][0]["assertions"]["quality_gate_pass"]
    rewrite_manifest(manifest_path, manifest)
    result = evaluate(tmp_path, manifest_path)
    assert "ASSERTION_BINDING_MISSING" in {issue.code for issue in result.issues}


def test_case_qualification_false_fails(tmp_path):
    manifest_path, manifest = build_valid_fixture(tmp_path)
    path = tmp_path / manifest["cases"][0]["artifacts"]["qualification"]["path"]
    qualification = yaml.safe_load(path.read_text(encoding="utf-8"))
    qualification["forecast_bridge_complete"] = False
    write_yaml(path, qualification)
    manifest["cases"][0]["artifacts"]["qualification"]["sha256"] = sha256_file(path)
    rewrite_manifest(manifest_path, manifest)
    result = evaluate(tmp_path, manifest_path)
    assert result.receipt.engineering_pass_count == 3


def test_preexisting_human_acceptance_is_rejected(tmp_path):
    manifest_path, manifest = build_valid_fixture(tmp_path)
    path = tmp_path / manifest["cases"][0]["artifacts"]["qualification"]["path"]
    qualification = yaml.safe_load(path.read_text(encoding="utf-8"))
    qualification["exact_hash_human_review_status"] = "accepted"
    write_yaml(path, qualification)
    manifest["cases"][0]["artifacts"]["qualification"]["sha256"] = sha256_file(path)
    rewrite_manifest(manifest_path, manifest)
    result = evaluate(tmp_path, manifest_path)
    assert result.receipt.engineering_pass_count == 3
    assert "ASSERTION_FAILED" in {issue.code for issue in result.issues}


def test_reader_hash_must_be_bound_by_generation_lock(tmp_path):
    manifest_path, manifest = build_valid_fixture(tmp_path)
    path = tmp_path / manifest["cases"][0]["artifacts"]["generation_lock"]["path"]
    lock = json.loads(path.read_text())
    lock["artifacts"]["reader"]["sha256"] = "f" * 64
    write_json(path, lock)
    manifest["cases"][0]["artifacts"]["generation_lock"]["sha256"] = sha256_file(path)
    rewrite_manifest(manifest_path, manifest)
    result = evaluate(tmp_path, manifest_path)
    assert result.receipt.engineering_pass_count == 3
    assert "ASSERTION_FAILED" in {issue.code for issue in result.issues}


def test_quality_hash_must_be_bound_by_generation_lock(tmp_path):
    manifest_path, manifest = build_valid_fixture(tmp_path)
    path = tmp_path / manifest["cases"][0]["artifacts"]["generation_lock"]["path"]
    lock = json.loads(path.read_text())
    lock["artifacts"]["quality_scorecard"]["sha256"] = "e" * 64
    write_json(path, lock)
    manifest["cases"][0]["artifacts"]["generation_lock"]["sha256"] = sha256_file(path)
    rewrite_manifest(manifest_path, manifest)
    result = evaluate(tmp_path, manifest_path)
    assert result.receipt.engineering_pass_count == 3


def test_traceability_hash_must_be_bound_by_generation_lock(tmp_path):
    manifest_path, manifest = build_valid_fixture(tmp_path)
    path = tmp_path / manifest["cases"][0]["artifacts"]["generation_lock"]["path"]
    lock = json.loads(path.read_text())
    lock["artifacts"]["traceability"]["sha256"] = "d" * 64
    write_json(path, lock)
    manifest["cases"][0]["artifacts"]["generation_lock"]["sha256"] = sha256_file(path)
    rewrite_manifest(manifest_path, manifest)
    result = evaluate(tmp_path, manifest_path)
    assert result.receipt.engineering_pass_count == 3


def test_generation_id_must_be_nonempty(tmp_path):
    manifest_path, manifest = build_valid_fixture(tmp_path)
    path = tmp_path / manifest["cases"][0]["artifacts"]["generation_lock"]["path"]
    lock = json.loads(path.read_text())
    lock["generation_id"] = ""
    write_json(path, lock)
    manifest["cases"][0]["artifacts"]["generation_lock"]["sha256"] = sha256_file(path)
    rewrite_manifest(manifest_path, manifest)
    result = evaluate(tmp_path, manifest_path)
    assert result.receipt.engineering_pass_count == 3


def test_small_reader_fails(tmp_path):
    manifest_path, manifest = build_valid_fixture(tmp_path)
    path = tmp_path / manifest["cases"][0]["artifacts"]["reader"]["path"]
    path.write_text("tiny", encoding="utf-8")
    manifest["cases"][0]["artifacts"]["reader"]["sha256"] = sha256_file(path)
    lock_path = tmp_path / manifest["cases"][0]["artifacts"]["generation_lock"]["path"]
    lock = json.loads(lock_path.read_text())
    lock["artifacts"]["reader"]["sha256"] = sha256_file(path)
    write_json(lock_path, lock)
    manifest["cases"][0]["artifacts"]["generation_lock"]["sha256"] = sha256_file(lock_path)
    rewrite_manifest(manifest_path, manifest)
    result = evaluate(tmp_path, manifest_path)
    assert "READER_TOO_SMALL" in {issue.code for issue in result.issues}


def test_output_tree_is_byte_deterministic(tmp_path):
    manifest_path, _ = build_valid_fixture(tmp_path)
    result_a = evaluate(tmp_path, manifest_path)
    result_b = evaluate(tmp_path, manifest_path)
    out_a = tmp_path / "out_a"
    out_b = tmp_path / "out_b"
    write_activation_outputs(out_a, result_a)
    write_activation_outputs(out_b, result_b)
    files_a = {p.relative_to(out_a): p.read_bytes() for p in out_a.rglob("*") if p.is_file()}
    files_b = {p.relative_to(out_b): p.read_bytes() for p in out_b.rglob("*") if p.is_file()}
    assert files_a == files_b


def test_handoffs_never_auto_accept(tmp_path):
    manifest_path, _ = build_valid_fixture(tmp_path)
    result = evaluate(tmp_path, manifest_path)
    for handoff in result.handoffs.values():
        assert handoff["review_status"] == "pending"
        assert handoff["reviewer"] is None
        assert handoff["reviewed_at"] is None
        assert handoff["automated_acceptance_allowed"] is False


def test_blocked_case_handoff_is_not_ready(tmp_path):
    manifest_path, manifest = build_valid_fixture(tmp_path)
    path = tmp_path / manifest["cases"][0]["artifacts"]["quality_scorecard"]["path"]
    write_yaml(path, {"case_id": "case_1", "candidate_ready_for_exact_hash_review": False})
    manifest["cases"][0]["artifacts"]["quality_scorecard"]["sha256"] = sha256_file(path)
    lock_path = tmp_path / manifest["cases"][0]["artifacts"]["generation_lock"]["path"]
    lock = json.loads(lock_path.read_text())
    lock["artifacts"]["quality_scorecard"]["sha256"] = sha256_file(path)
    write_json(lock_path, lock)
    manifest["cases"][0]["artifacts"]["generation_lock"]["sha256"] = sha256_file(lock_path)
    rewrite_manifest(manifest_path, manifest)
    result = evaluate(tmp_path, manifest_path)
    assert result.handoffs["case_1"]["review_status"] == "not_ready"


def test_wrong_baseline_is_rejected(tmp_path):
    manifest_path, manifest = build_valid_fixture(tmp_path)
    manifest["baseline_commit"] = "0" * 40
    rewrite_manifest(manifest_path, manifest)
    with pytest.raises(ActivationContractError):
        evaluate(tmp_path, manifest_path)


def test_generic_runtime_has_no_registered_issuer_tokens():
    tokens = ["铜冠铜箔", "赤峰黄金", "药明康德", "东阳光", "301217", "600988", "603259", "600673"]
    paths = [
        ROOT / "src" / "research" / "r5_bundle17r_activation_receipt.py",
        ROOT / "scripts" / "run_r5_bundle17r_activation_receipt.py",
        ROOT / "config" / "r5_bundle17r_activation_policy.yaml",
        ROOT / "schemas" / "r5_bundle17r_activation_manifest.schema.yaml",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert not any(token in text for token in tokens)
