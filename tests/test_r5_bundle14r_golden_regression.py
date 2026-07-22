from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.quality.r5_bundle14r_semantic_regression import evaluate_semantic_candidate
from src.research.r5_bundle14r_golden_regression import (
    build_generation_lock,
    build_suite_result,
    discover_case_paths,
    load_yaml_document,
    scan_core_generality,
    suite_to_dict,
    validate_case_document,
)


CASES_DIR = REPO_ROOT / "tests" / "fixtures" / "r5_bundle14r" / "cases"
CORE_SOURCES = [
    REPO_ROOT / "src" / "research" / "r5_bundle14r_golden_regression.py",
    REPO_ROOT / "src" / "quality" / "r5_bundle14r_semantic_regression.py",
    REPO_ROOT / "scripts" / "run_r5_bundle14r_golden_regression.py",
]


def case_documents():
    return [(path, load_yaml_document(path)) for path in discover_case_paths(CASES_DIR)]


def good_semantic_candidate():
    return {
        "truthfulness": {
            "unresolved_claim_count": 0,
            "sample_evidence_claim_count": 0,
            "source_conflict_count": 0,
        },
        "economic_model": {
            "qualified_required_driver_ratio": 1.0,
            "statement_reconciliation_passed": True,
            "overlap_resolved": True,
        },
        "narrative": {
            "company_specific_metric_count": 8,
            "quantified_driver_to_financial_link_count": 5,
            "unique_core_conclusion_count": 5,
            "duplicate_insight_ratio": 0.10,
            "generic_sentence_ratio": 0.20,
            "empty_core_section_count": 0,
        },
        "valuation": {
            "eligible_method_count": 1,
            "ineligible_methods_used": [],
        },
        "backflow": {
            "unresolved_issue_count": 0,
            "routed_issue_count": 0,
            "actionable_issue_count": 0,
            "invalid_route_count": 0,
        },
        "determinism": {
            "rerun_hash_equal": True,
            "input_lock_complete": True,
            "output_lock_complete": True,
        },
        "future_events": {
            "dated_or_windowed_event_count": 2,
            "event_with_operating_transmission_count": 2,
            "past_event_misclassified_count": 0,
        },
    }


def test_four_real_case_contracts_are_present_and_valid():
    documents = case_documents()
    assert len(documents) == 4
    labels = set()
    for path, document in documents:
        result = validate_case_document(document, source_path=path)
        assert result.contract_valid, result.issues
        assert result.required_driver_count >= 8
        assert result.archetype_count >= 3
        assert result.report_emphasis_top3_weight >= 0.60
        assert result.sample_quality_allowed is False
        assert result.p2_allowed is False
        assert result.workflow_state_mutation_allowed is False
        labels.add(result.issuer_label)
    assert len(labels) == 4


def test_sample_text_cannot_be_promoted_to_factual_evidence():
    path, document = case_documents()[0]
    mutated = deepcopy(document)
    mutated["benchmark_policy"]["sample_text_as_evidence"] = "allowed"
    result = validate_case_document(mutated, source_path=path)
    assert result.contract_valid is False
    assert any(issue.code == "SAMPLE_EVIDENCE_PROMOTION_FORBIDDEN" for issue in result.issues)


def test_missing_required_driver_is_a_contract_blocker():
    path, document = case_documents()[0]
    mutated = deepcopy(document)
    removed = mutated["drivers"].pop(0)["driver_id"]
    result = validate_case_document(mutated, source_path=path)
    assert result.contract_valid is False
    assert any(
        issue.code == "ARCHETYPE_REFERENCES_UNKNOWN_DRIVER" and removed in issue.message
        for issue in result.issues
    )


def test_automated_release_flags_are_forbidden():
    path, document = case_documents()[0]
    mutated = deepcopy(document)
    mutated["release_policy"]["automated_sample_quality_allowed"] = True
    result = validate_case_document(mutated, source_path=path)
    assert result.contract_valid is False
    assert result.sample_quality_allowed is True
    assert any(issue.code == "AUTOMATED_RELEASE_FORBIDDEN" for issue in result.issues)


def test_generic_runtime_contains_no_case_issuer_tokens():
    suite = build_suite_result(case_documents(), core_source_paths=CORE_SOURCES, path_root=REPO_ROOT)
    assert suite.contract_passed is True
    assert suite.core_generality.passed is True
    assert suite.release_authority is False
    assert suite.sample_quality_allowed is False
    assert suite.p2_allowed is False
    assert suite.workflow_state_mutation_allowed is False


def test_core_scan_rejects_issuer_specific_logic(tmp_path: Path):
    source = tmp_path / "bad_core.py"
    source.write_text("SPECIAL_CASE = '铜冠铜箔'\n", encoding="utf-8")
    result = scan_core_generality([source], ["铜冠铜箔", "301217.SZ"])
    assert result.passed is False
    assert result.violations


def test_generation_lock_is_deterministic():
    documents = case_documents()
    suite = build_suite_result(documents, core_source_paths=CORE_SOURCES, path_root=REPO_ROOT)
    kwargs = {
        "suite_result": suite,
        "case_paths": [path for path, _ in documents],
        "source_paths": CORE_SOURCES,
        "extra_inputs": {"git_head": "0966b914476b8f0a89b39d0f06a58dca5d3b20a7"},
        "path_root": REPO_ROOT,
    }
    first = build_generation_lock(**kwargs)
    second = build_generation_lock(**kwargs)
    assert first == second
    assert first["generation_id"].startswith("golden_regression_gen_")
    assert first["sample_quality_allowed"] is False
    assert first["p2_allowed"] is False
    repo_keys = [key for key in first["input_sha256"] if key.startswith("repo:")]
    assert repo_keys
    assert all(not key.startswith("repo:/") for key in repo_keys)


def test_seeded_cases_remain_evidence_pending_and_emit_targeted_backflow():
    suite = build_suite_result(case_documents(), core_source_paths=CORE_SOURCES, path_root=REPO_ROOT)
    assert suite.research_ready_case_count == 0
    assert suite.candidate_ready_case_count == 0
    for result in suite.qualification_results:
        assert result.status == "evidence_qualification_pending"
        issue_codes = {item.issue_code for item in result.backflow_items}
        assert "EVIDENCE_MISSING" in issue_codes
        assert "DRIVER_UNQUALIFIED" in issue_codes
        assert "OVERLAP_UNRESOLVED" in issue_codes
        assert "VALUATION_INELIGIBLE" in issue_codes
        assert "SEMANTIC_QUALITY_FAILED" in issue_codes
        assert result.sample_quality_allowed is False
        assert result.p2_allowed is False


def test_semantic_gate_can_only_prepare_exact_hash_review():
    result = evaluate_semantic_candidate(
        "case",
        good_semantic_candidate(),
        company_specific_metric_minimum=5,
        quantified_links_minimum=3,
        unique_conclusions_minimum=3,
        maximum_duplicate_insight_ratio=0.25,
    )
    assert result.decision == "candidate_ready_for_exact_hash_review"
    assert result.candidate_ready_for_exact_hash_review is True
    assert result.total_score >= result.threshold
    assert result.release_authority is False
    assert result.sample_quality_allowed is False
    assert result.p2_allowed is False


def test_long_but_generic_narrative_fails_non_compensating_gate():
    candidate = good_semantic_candidate()
    candidate["narrative"] = {
        "company_specific_metric_count": 1,
        "quantified_driver_to_financial_link_count": 0,
        "unique_core_conclusion_count": 1,
        "duplicate_insight_ratio": 0.75,
        "generic_sentence_ratio": 0.90,
        "empty_core_section_count": 0,
        "character_count": 50000,
    }
    result = evaluate_semantic_candidate(
        "case",
        candidate,
        company_specific_metric_minimum=5,
        quantified_links_minimum=3,
        unique_conclusions_minimum=3,
        maximum_duplicate_insight_ratio=0.25,
    )
    assert result.decision == "needs_backflow"
    assert result.core_gate_passed is False
    assert any(
        check.gate == "semantic_incrementality" and check.passed is False
        for check in result.checks
    )


def test_ineligible_valuation_cannot_be_compensated_by_other_sections():
    candidate = good_semantic_candidate()
    candidate["valuation"] = {
        "eligible_method_count": 0,
        "ineligible_methods_used": ["peer_multiples"],
    }
    result = evaluate_semantic_candidate(
        "case",
        candidate,
        company_specific_metric_minimum=5,
        quantified_links_minimum=3,
        unique_conclusions_minimum=3,
        maximum_duplicate_insight_ratio=0.25,
    )
    assert result.decision == "needs_backflow"
    assert result.blocker_count >= 1


def test_cli_writes_only_external_output_directory(tmp_path: Path):
    output_dir = tmp_path / "out"
    before = {
        str(path.relative_to(REPO_ROOT)): path.read_bytes()
        for path in CORE_SOURCES
    }
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            str(REPO_ROOT / "scripts" / "run_r5_bundle14r_golden_regression.py"),
            "--repo-root",
            str(REPO_ROOT),
            "--cases-dir",
            str(CASES_DIR),
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads((output_dir / "R5_bundle14r_suite_result.json").read_text(encoding="utf-8"))
    assert payload["contract_passed"] is True
    assert payload["sample_quality_allowed"] is False
    assert payload["p2_allowed"] is False
    assert (output_dir / "R5_bundle14r_generation_lock.json").exists()
    assert (output_dir / "R5_bundle14r_backflow_queue.csv").exists()
    assert (output_dir / "R5_bundle14r_close_readout.md").exists()
    after = {
        str(path.relative_to(REPO_ROOT)): path.read_bytes()
        for path in CORE_SOURCES
    }
    assert before == after
