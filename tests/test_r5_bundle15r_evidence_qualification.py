from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import yaml

from src.research.r5_bundle15r_evidence_qualification import (
    BUNDLE14R_QUALIFICATION_SCHEMA_VERSION,
    PACK_SCHEMA_VERSION,
    QualificationContractError,
    bundle14r_qualification_payload,
    compile_qualification_suite,
    evaluate_evidence_pack,
    extract_case_contract,
    load_yaml_document,
    scaffold_pack,
    sha256_file,
    write_compilation_outputs,
)


def _write(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return sha256_file(path)


def _case_document() -> dict:
    return {
        "schema_version": "r5_bundle14r_case_v1",
        "case_id": "golden_fixture_manufacturing",
        "issuer": {"name": "示例制造", "ticker": "000000.SZ", "jurisdiction": "CN"},
        "release_policy": {
            "automated_sample_quality_allowed": False,
            "automated_p2_allowed": False,
            "workflow_state_mutation_allowed": False,
            "exact_hash_human_review_required": True,
        },
        "required_source_classes": [
            "issuer_exchange_filings",
            "market_data_primary_or_licensed",
        ],
        "forecast_contract": {
            "minimum_segment_revenue_coverage": 0.8,
            "minimum_segment_gross_profit_coverage": 0.8,
        },
        "valuation_methods": [
            {"method": "reverse_valuation", "eligibility": "conditional"},
            {"method": "peer_multiples", "eligibility": "conditional"},
            {"method": "dcf_or_sotp", "eligibility": "conditional"},
        ],
        "drivers": [
            {"driver_id": "volume", "label": "volume"},
            {"driver_id": "unit_price", "label": "price"},
        ],
        "economic_archetypes": [
            {
                "archetype_id": "volume_price_mix",
                "required_driver_ids": ["volume", "unit_price"],
            }
        ],
        "research_questions": [
            {"question_id": "q_volume", "question": "volume?"},
            {"question_id": "q_price", "question": "price?"},
        ],
    }


def _contract(tmp_path: Path):
    case_path = tmp_path / "cases" / "fixture.yaml"
    case_path.parent.mkdir(parents=True, exist_ok=True)
    case_path.write_text(yaml.safe_dump(_case_document(), allow_unicode=True), encoding="utf-8")
    return extract_case_contract(_case_document(), source_path=case_path, path_root=tmp_path), case_path


def _valid_pack(tmp_path: Path) -> dict:
    issuer_hash = _write(tmp_path / "data/raw/issuer.txt", "official issuer evidence\n")
    market_hash = _write(tmp_path / "data/raw/market.txt", "licensed market evidence\n")
    semantic_hash = _write(tmp_path / "reports/fixture/semantic.json", '{"decision":"pass"}\n')
    return {
        "schema_version": PACK_SCHEMA_VERSION,
        "case_id": "golden_fixture_manufacturing",
        "issuer": {"ticker": "000000.SZ"},
        "as_of_date": "2026-07-15",
        "review": {
            "status": "accepted",
            "reviewer": "fixture_reviewer",
            "reviewed_at": "2026-07-15T08:00:00+00:00",
        },
        "sources": [
            {
                "source_id": "src_issuer",
                "source_class": "issuer_exchange_filings",
                "official": True,
                "review_status": "accepted",
                "archive_path": "data/raw/issuer.txt",
                "sha256": issuer_hash,
                "publication_date": "2026-04-30",
                "covered_period": "FY2025",
            },
            {
                "source_id": "src_market",
                "source_class": "market_data_primary_or_licensed",
                "official": True,
                "review_status": "accepted",
                "archive_path": "data/raw/market.txt",
                "sha256": market_hash,
                "publication_date": "2026-07-15",
                "covered_period": "2026-07-15",
            },
        ],
        "records": [
            {
                "record_id": "rec_volume",
                "driver_id": "volume",
                "question_ids": ["q_volume"],
                "status": "confirmed",
                "value": 100,
                "unit": "tonnes",
                "period": "FY2025",
                "definition": "physical shipment volume",
                "confidence": "high",
                "review_status": "accepted",
                "source_ids": ["src_issuer"],
                "overlap_rule": "issuer segment volume only",
                "stale_trigger": "new annual or interim filing",
            },
            {
                "record_id": "rec_price",
                "driver_id": "unit_price",
                "question_ids": ["q_price"],
                "status": "bounded_estimate",
                "value": {"low": 9.5, "high": 10.5},
                "unit": "currency_per_tonne",
                "period": "FY2025",
                "definition": "realized unit price range",
                "confidence": "medium",
                "review_status": "accepted_with_limitations",
                "source_ids": ["src_issuer", "src_market"],
                "overlap_rule": "same product and fiscal period",
                "stale_trigger": "new price or revenue disclosure",
            },
        ],
        "overlap_reconciliation": {
            "status": "passed",
            "revenue_overlap_resolved": True,
            "gross_profit_overlap_resolved": True,
            "unresolved_items": [],
        },
        "forecast_bridge": {
            "status": "passed",
            "driver_to_statement_reconciliation": True,
            "working_capital_bridge": True,
            "cash_flow_bridge": True,
            "segment_revenue_coverage": 0.9,
            "segment_gross_profit_coverage": 0.88,
        },
        "valuation": {
            "methods": [
                {
                    "method": "reverse_valuation",
                    "eligible": True,
                    "market_value_reconciled": True,
                    "share_count_reconciled": True,
                    "forecast_definition_reconciled": True,
                    "implied_operating_assumptions_documented": True,
                }
            ]
        },
        "semantic_candidate": {
            "status": "passed",
            "semantic_gate_path": "reports/fixture/semantic.json",
            "semantic_gate_sha256": semantic_hash,
        },
        "determinism": {
            "rerun_hash_equal": True,
            "input_lock_complete": True,
            "output_lock_complete": True,
        },
        "exact_hash_human_review": {"status": "pending"},
        "release": {
            "sample_quality_allowed": False,
            "p2_allowed": False,
            "workflow_state_mutation_allowed": False,
        },
    }


def _evaluate(tmp_path: Path, pack: dict | None = None):
    contract, _ = _contract(tmp_path)
    return evaluate_evidence_pack(
        contract,
        pack,
        pack_source_path=tmp_path / "packs/fixture.yaml" if pack else None,
        repo_root=tmp_path,
        policy_document=None,
        verify_paths=True,
    )


def test_extract_case_contract_reads_bundle14r_dimensions(tmp_path: Path) -> None:
    contract, _ = _contract(tmp_path)
    assert contract.required_driver_ids == ("unit_price", "volume")
    assert contract.research_question_ids == ("q_price", "q_volume")
    assert contract.minimum_segment_revenue_coverage == 0.8
    assert contract.allowed_valuation_methods == ("dcf_or_sotp", "peer_multiples", "reverse_valuation")


def test_missing_pack_is_truthful_pending(tmp_path: Path) -> None:
    result = _evaluate(tmp_path, None)
    assert result.decision == "evidence_qualification_pending"
    assert result.reviewed_official_source_count == 0
    assert result.bundle14r_candidate_ready is False
    assert result.sample_quality_allowed is False
    assert result.p2_allowed is False


def test_valid_pack_compiles_exact_bundle14r_qualification_keys(tmp_path: Path) -> None:
    result = _evaluate(tmp_path, _valid_pack(tmp_path))
    assert result.decision == "qualification_ready_for_bundle14r"
    assert result.evidence_pack_complete is True
    assert result.bundle14r_candidate_ready is True
    payload = bundle14r_qualification_payload(result)
    assert payload["schema_version"] == BUNDLE14R_QUALIFICATION_SCHEMA_VERSION
    for key in (
        "qualified_driver_ids",
        "reviewed_official_source_count",
        "overlap_resolved",
        "forecast_bridge_complete",
        "valuation_eligible",
        "semantic_gate_passed",
        "deterministic_rerun",
        "exact_hash_human_review_status",
    ):
        assert key in payload
    assert payload["bundle15r_audit"]["sample_quality_allowed"] is False


def test_sample_report_cannot_be_evidence(tmp_path: Path) -> None:
    pack = _valid_pack(tmp_path)
    pack["sources"][0]["source_class"] = "sample_report"
    result = _evaluate(tmp_path, pack)
    assert result.bundle14r_candidate_ready is False
    assert any(issue.code == "SOURCE_INVALID" for issue in result.issues)


def test_unreviewed_or_nonofficial_source_cannot_qualify_driver(tmp_path: Path) -> None:
    pack = _valid_pack(tmp_path)
    pack["sources"][0]["review_status"] = "pending"
    pack["sources"][1]["official"] = False
    result = _evaluate(tmp_path, pack)
    assert result.reviewed_official_source_count == 0
    assert result.qualified_driver_ids == ()


def test_source_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    pack = _valid_pack(tmp_path)
    pack["sources"][0]["sha256"] = "0" * 64
    result = _evaluate(tmp_path, pack)
    assert result.bundle14r_candidate_ready is False
    assert any(issue.code == "SOURCE_HASH_MISMATCH" for issue in result.issues)


def test_unknown_driver_is_contract_failure(tmp_path: Path) -> None:
    pack = _valid_pack(tmp_path)
    pack["records"][0]["driver_id"] = "unknown_driver"
    result = _evaluate(tmp_path, pack)
    assert result.input_contract_valid is False
    assert result.decision == "input_contract_failed"


def test_equal_duplicate_is_suppressed_deterministically(tmp_path: Path) -> None:
    pack = _valid_pack(tmp_path)
    duplicate = copy.deepcopy(pack["records"][0])
    duplicate["record_id"] = "rec_volume_duplicate"
    pack["records"].append(duplicate)
    result = _evaluate(tmp_path, pack)
    assert result.duplicate_record_count == 1
    assert result.conflict_count == 0
    assert "volume" in result.qualified_driver_ids


def test_conflicting_reviewed_values_block_driver(tmp_path: Path) -> None:
    pack = _valid_pack(tmp_path)
    conflict = copy.deepcopy(pack["records"][0])
    conflict["record_id"] = "rec_volume_conflict"
    conflict["value"] = 120
    pack["records"].append(conflict)
    result = _evaluate(tmp_path, pack)
    assert result.conflict_count == 1
    assert "volume" not in result.qualified_driver_ids
    assert result.bundle14r_candidate_ready is False


def test_missing_required_source_class_blocks_pack_completeness(tmp_path: Path) -> None:
    pack = _valid_pack(tmp_path)
    pack["sources"] = pack["sources"][:1]
    pack["records"][1]["source_ids"] = ["src_issuer"]
    result = _evaluate(tmp_path, pack)
    assert result.missing_source_classes == ("market_data_primary_or_licensed",)
    assert result.evidence_pack_complete is False


def test_every_research_question_must_be_classified(tmp_path: Path) -> None:
    pack = _valid_pack(tmp_path)
    pack["records"][1]["question_ids"] = []
    result = _evaluate(tmp_path, pack)
    assert result.missing_question_ids == ("q_price",)
    assert result.semantic_gate_passed is False


def test_overlap_is_non_compensating(tmp_path: Path) -> None:
    pack = _valid_pack(tmp_path)
    pack["overlap_reconciliation"]["gross_profit_overlap_resolved"] = False
    result = _evaluate(tmp_path, pack)
    assert result.overlap_resolved is False
    assert result.bundle14r_candidate_ready is False


def test_forecast_bridge_enforces_case_coverage_thresholds(tmp_path: Path) -> None:
    pack = _valid_pack(tmp_path)
    pack["forecast_bridge"]["segment_revenue_coverage"] = 0.79
    result = _evaluate(tmp_path, pack)
    assert result.forecast_bridge_complete is False
    assert any(issue.code == "FORECAST_BRIDGE_INCOMPLETE" for issue in result.issues)


def test_peer_multiples_needs_three_compatible_peers(tmp_path: Path) -> None:
    pack = _valid_pack(tmp_path)
    pack["valuation"]["methods"] = [
        {
            "method": "peer_multiples",
            "eligible": True,
            "qualified_peer_count": 2,
            "definition_compatible": True,
            "period_compatible": True,
            "metric_compatible": True,
        }
    ]
    result = _evaluate(tmp_path, pack)
    assert result.valuation_eligible is False
    pack["valuation"]["methods"][0]["qualified_peer_count"] = 3
    result2 = _evaluate(tmp_path, pack)
    assert result2.valuation_eligible is True


def test_semantic_gate_must_be_physically_hash_bound(tmp_path: Path) -> None:
    pack = _valid_pack(tmp_path)
    pack["semantic_candidate"]["semantic_gate_sha256"] = "f" * 64
    result = _evaluate(tmp_path, pack)
    assert result.semantic_gate_passed is False
    assert result.bundle14r_candidate_ready is False


def test_deterministic_rerun_is_required(tmp_path: Path) -> None:
    pack = _valid_pack(tmp_path)
    pack["determinism"]["output_lock_complete"] = False
    result = _evaluate(tmp_path, pack)
    assert result.deterministic_rerun is False
    assert result.bundle14r_candidate_ready is False


def test_release_flags_are_rejected(tmp_path: Path) -> None:
    pack = _valid_pack(tmp_path)
    pack["release"]["sample_quality_allowed"] = True
    result = _evaluate(tmp_path, pack)
    assert result.input_contract_valid is False
    assert any(issue.code == "RELEASE_BOUNDARY_VIOLATION" for issue in result.issues)


def test_accepted_human_review_requires_exact_physical_hash(tmp_path: Path) -> None:
    pack = _valid_pack(tmp_path)
    pack["exact_hash_human_review"] = {
        "status": "accepted",
        "reviewer": "human",
        "reviewed_at": "2026-07-15T09:00:00+00:00",
        "review_path": "reports/fixture/review.yaml",
        "review_sha256": "0" * 64,
    }
    result = _evaluate(tmp_path, pack)
    assert result.exact_hash_human_review_status == "rejected"
    review_hash = _write(tmp_path / "reports/fixture/review.yaml", "status: accepted\n")
    pack["exact_hash_human_review"]["review_sha256"] = review_hash
    result2 = _evaluate(tmp_path, pack)
    assert result2.exact_hash_human_review_status == "accepted"
    assert result2.sample_quality_allowed is False


def test_scaffold_is_deterministic_and_visibly_incomplete(tmp_path: Path) -> None:
    contract, _ = _contract(tmp_path)
    first = scaffold_pack(contract)
    second = scaffold_pack(contract)
    assert first == second
    assert first["review"]["status"] == "pending"
    assert all(record["status"] == "blocked" for record in first["records"])
    assert first["release"]["p2_allowed"] is False


def test_suite_and_outputs_are_byte_deterministic(tmp_path: Path) -> None:
    contract, case_path = _contract(tmp_path)
    pack = _valid_pack(tmp_path)
    pack_path = tmp_path / "packs/fixture.yaml"
    pack_path.parent.mkdir(parents=True, exist_ok=True)
    pack_path.write_text(yaml.safe_dump(pack, allow_unicode=True), encoding="utf-8")
    inputs = [(case_path, _case_document())]
    kwargs = dict(
        pack_by_case={contract.case_id: (pack_path, pack)},
        repo_root=tmp_path,
        policy_document=None,
        verify_paths=True,
        core_paths=[],
        extra_lock_inputs={"git_head": "fixture"},
    )
    first = compile_qualification_suite(inputs, **kwargs)
    second = compile_qualification_suite(inputs, **kwargs)
    assert asdict(first.suite) == asdict(second.suite)
    assert first.generation_lock == second.generation_lock
    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"
    write_compilation_outputs(out1, first, git_head="fixture")
    write_compilation_outputs(out2, second, git_head="fixture")
    files1 = {p.relative_to(out1): p.read_bytes() for p in out1.rglob("*") if p.is_file()}
    files2 = {p.relative_to(out2): p.read_bytes() for p in out2.rglob("*") if p.is_file()}
    assert files1 == files2


def test_compiler_does_not_mutate_canonical_workflow_state(tmp_path: Path) -> None:
    contract, case_path = _contract(tmp_path)
    pack = _valid_pack(tmp_path)
    pack_path = tmp_path / "packs/fixture.yaml"
    pack_path.parent.mkdir(parents=True, exist_ok=True)
    pack_path.write_text(yaml.safe_dump(pack, allow_unicode=True), encoding="utf-8")
    state = tmp_path / "reports/workflow_runs/fixture/workflow_state.yaml"
    state_hash = _write(state, "status: accepted_with_todos\n")
    artifacts = compile_qualification_suite(
        [(case_path, _case_document())],
        pack_by_case={contract.case_id: (pack_path, pack)},
        repo_root=tmp_path,
        verify_paths=True,
        core_paths=[],
    )
    write_compilation_outputs(tmp_path / "generated", artifacts, git_head="fixture")
    assert sha256_file(state) == state_hash
    proposal = load_yaml_document(tmp_path / "generated/R5_bundle15r_status_proposal.yaml")
    assert proposal["canonical_workflow_state_mutation_allowed"] is False
    assert proposal["p2_allowed"] is False


def test_orphan_pack_is_rejected(tmp_path: Path) -> None:
    _, case_path = _contract(tmp_path)
    pack = _valid_pack(tmp_path)
    try:
        compile_qualification_suite(
            [(case_path, _case_document())],
            pack_by_case={"unknown_case": (tmp_path / "unknown.yaml", pack)},
            repo_root=tmp_path,
            verify_paths=False,
        )
    except QualificationContractError as exc:
        assert "unknown cases" in str(exc)
    else:
        raise AssertionError("orphan pack should fail")


def test_cli_empty_input_lane_emits_pending_qualification(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    # Copy only the Bundle 15R implementation into an isolated runnable tree.
    source_root = Path(__file__).resolve().parents[1]
    for relative in (
        "src/research/r5_bundle15r_evidence_qualification.py",
        "scripts/run_r5_bundle15r_evidence_qualification.py",
        "config/r5_bundle15r_evidence_qualification_policy.yaml",
    ):
        src = source_root / relative
        dst = repo / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
    cases = repo / "cases"
    cases.mkdir()
    (cases / "fixture.yaml").write_text(
        yaml.safe_dump(_case_document(), allow_unicode=True), encoding="utf-8"
    )
    output = repo / "generated"
    completed = subprocess.run(
        [
            sys.executable,
            str(repo / "scripts/run_r5_bundle15r_evidence_qualification.py"),
            "--repo-root",
            str(repo),
            "--cases-dir",
            str(cases),
            "--output-dir",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads((output / "R5_bundle15r_qualification_suite.json").read_text())
    assert payload["bundle14r_candidate_ready_count"] == 0
    qualification = load_yaml_document(
        output / "qualification/golden_fixture_manufacturing.yaml"
    )
    assert qualification["reviewed_official_source_count"] == 0
    assert qualification["bundle15r_audit"]["p2_allowed"] is False
