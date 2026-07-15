from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from src.research.r5_bundle16r_real_company_regression import (
    GateIssue,
    SCHEMA_VERSION,
    evaluate_suite,
    render_markdown,
    validate_registry,
    write_suite_outputs,
)


CASE_DEFS = [
    ("301217_high_end_copper_foil", "301217", "铜冠铜箔"),
    ("600988_cycle_resource_gold", "600988", "赤峰黄金"),
    ("603259_crdmo_backlog_funnel", "603259", "药明康德"),
    ("600673_multi_business_ma", "600673", "东阳光"),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def registry(tmp_path: Path) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "suite_id": "test_four_company_suite",
        "baseline_commit": "1d4b1f151b97337d8def33c409532f28794b6652",
        "required_artifact_roles": [
            "workflow_state",
            "evidence_pack",
            "operating_driver_pack",
            "forecast_model",
            "valuation_pack",
            "reader_report",
            "quality_readout",
            "generation_lock",
            "human_review",
        ],
        "thresholds": {
            "material_segment_driver_coverage_min": 0.8,
            "revenue_explained_ratio_min": 0.8,
            "gross_profit_explained_ratio_min": 0.8,
            "residual_revenue_ratio_max": 0.2,
            "residual_gross_profit_ratio_max": 0.2,
            "forecast_assumption_traceability_min": 0.9,
            "model_linked_core_section_ratio_min": 0.75,
            "section_novelty_ratio_min": 0.7,
            "citation_resolution_rate_min": 1.0,
            "company_specific_metric_count_min": 8,
            "future_event_model_link_count_min": 2,
            "qualified_peer_count_min_when_peer_multiple_used": 3,
        },
        "runtime_scan": {
            "enabled": True,
            "include_dirs": ["runtime"],
            "extensions": [".py"],
            "allow_paths": [],
        },
        "cases": [
            {
                "case_id": case_id,
                "ticker": ticker,
                "issuer_name": issuer,
                "required_economic_archetypes": ["test_archetype"],
                "material_segments": ["segment_a"],
                "forbidden_runtime_tokens": [],
                "benchmark_policy": {
                    "sample_text_role": "narrative_density_only",
                    "sample_text_may_be_evidence": False,
                },
            }
            for case_id, ticker, issuer in CASE_DEFS
        ],
    }


def make_case(
    repo_root: Path,
    case_id: str,
    ticker: str,
    issuer_name: str,
    *,
    human_status: str = "pending",
    exact_human_hashes: bool = True,
) -> dict:
    case_dir = repo_root / "artifacts" / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    role_to_path = {
        "workflow_state": case_dir / "workflow_state.json",
        "evidence_pack": case_dir / "evidence_pack.json",
        "operating_driver_pack": case_dir / "operating_driver_pack.json",
        "forecast_model": case_dir / "forecast_model.json",
        "valuation_pack": case_dir / "valuation_pack.json",
        "reader_report": case_dir / "reader_report.md",
        "quality_readout": case_dir / "quality_readout.json",
        "generation_lock": case_dir / "generation_lock.json",
        "human_review": case_dir / "human_review.json",
    }

    for role, path in role_to_path.items():
        if role in {"generation_lock", "human_review"}:
            continue
        if path.suffix == ".md":
            path.write_text(f"# {issuer_name}\n\nmodel-linked report for {ticker}\n", encoding="utf-8")
        else:
            write_json(path, {"role": role, "case_id": case_id})

    report_sha = sha256(role_to_path["reader_report"])
    write_json(
        role_to_path["generation_lock"],
        {"case_id": case_id, "reader_report_sha256": report_sha},
    )
    lock_sha = sha256(role_to_path["generation_lock"])
    review_payload = {
        "status": human_status,
        "reader_report_sha256": report_sha if exact_human_hashes else "0" * 64,
        "generation_lock_sha256": lock_sha if exact_human_hashes else "f" * 64,
        "reviewer": "reviewer-a" if human_status == "accepted" else "",
        "reviewed_at": "2026-07-15T12:00:00Z" if human_status == "accepted" else "",
    }
    write_json(role_to_path["human_review"], review_payload)

    artifacts = []
    for role, path in role_to_path.items():
        artifacts.append(
            {
                "role": role,
                "path": path.relative_to(repo_root).as_posix(),
                "sha256": sha256(path),
                "source_class": "evidence" if role == "evidence_pack" else "derived",
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case_id,
        "ticker": ticker,
        "issuer_name": issuer_name,
        "artifacts": artifacts,
        "metrics": {
            "material_segment_driver_coverage": 0.85,
            "revenue_explained_ratio": 0.82,
            "gross_profit_explained_ratio": 0.81,
            "residual_revenue_ratio": 0.18,
            "residual_gross_profit_ratio": 0.19,
            "forecast_assumption_traceability": 0.95,
            "model_linked_core_section_ratio": 0.80,
            "section_novelty_ratio": 0.75,
            "citation_resolution_rate": 1.0,
            "company_specific_metric_count": 10,
            "future_event_model_link_count": 3,
            "qualified_peer_count": 3,
            "unresolved_critical_question_count": 0,
        },
        "valuation": {
            "peer_multiple_used": True,
            "peer_definition_compatible": True,
            "peer_periods_aligned": True,
            "alternative_method": "none",
        },
        "truthfulness": {
            "sample_text_used_as_evidence": False,
            "management_guidance_recast_as_fact": False,
            "low_confidence_peer_ranked": False,
            "direct_trading_instruction_present": False,
            "past_event_presented_as_future": False,
            "undisclosed_segment_economics_presented_as_fact": False,
            "consensus_estimate_presented_as_issuer_fact": False,
        },
    }


def all_cases(repo_root: Path, human_status: str = "pending") -> dict[str, dict]:
    return {
        case_id: make_case(repo_root, case_id, ticker, issuer, human_status=human_status)
        for case_id, ticker, issuer in CASE_DEFS
    }


def issue_codes(result) -> set[str]:
    codes = {issue.code for issue in result.issues}
    for case in result.cases:
        codes.update(issue.code for issue in case.issues)
    return codes


def test_gate_issue_serializes_backflow_owner() -> None:
    issue = GateIssue(
        "human_review_exact_hash_mismatch",
        "review does not bind exact hashes",
    ).as_dict()
    assert issue["backflow_owner"] == "review_handoff"
    assert "exact Reader" in issue["next_step"]


def test_four_valid_cases_pass_engineering_but_not_sample_quality(tmp_path: Path) -> None:
    (tmp_path / "runtime").mkdir()
    (tmp_path / "runtime" / "generic.py").write_text("GENERIC = True\n", encoding="utf-8")
    result = evaluate_suite(tmp_path, registry(tmp_path), all_cases(tmp_path))
    assert result.engineering_pass is True
    assert result.all_cases_present is True
    assert result.all_cases_exact_hash_accepted is False
    assert result.sample_quality_allowed is False
    assert result.p2_allowed is False


def test_all_exact_hash_reviews_allow_sample_quality_but_never_p2(tmp_path: Path) -> None:
    (tmp_path / "runtime").mkdir()
    (tmp_path / "runtime" / "generic.py").write_text("GENERIC = True\n", encoding="utf-8")
    result = evaluate_suite(tmp_path, registry(tmp_path), all_cases(tmp_path, human_status="accepted"))
    assert result.engineering_pass is True
    assert result.all_cases_exact_hash_accepted is True
    assert result.sample_quality_allowed is True
    assert result.p2_allowed is False
    assert "p2_manual_authorization_required" in issue_codes(result)


def test_missing_case_blocks_suite(tmp_path: Path) -> None:
    manifests = all_cases(tmp_path)
    manifests.pop(CASE_DEFS[-1][0])
    result = evaluate_suite(tmp_path, registry(tmp_path), manifests)
    assert result.engineering_pass is False
    assert result.all_cases_present is False
    assert "golden_case_missing" in issue_codes(result)


def test_artifact_hash_mismatch_blocks_case(tmp_path: Path) -> None:
    manifests = all_cases(tmp_path)
    first = manifests[CASE_DEFS[0][0]]
    first["artifacts"][0]["sha256"] = "0" * 64
    result = evaluate_suite(tmp_path, registry(tmp_path), manifests)
    assert result.engineering_pass is False
    assert "artifact_sha_mismatch" in issue_codes(result)


def test_sample_path_cannot_be_promoted_to_evidence(tmp_path: Path) -> None:
    manifests = all_cases(tmp_path)
    first = manifests[CASE_DEFS[0][0]]
    evidence = next(item for item in first["artifacts"] if item["role"] == "evidence_pack")
    old = tmp_path / evidence["path"]
    sample = tmp_path / "benchmarks" / "narrative_samples" / "evidence_pack.json"
    sample.parent.mkdir(parents=True)
    sample.write_bytes(old.read_bytes())
    evidence["path"] = sample.relative_to(tmp_path).as_posix()
    evidence["sha256"] = sha256(sample)
    result = evaluate_suite(tmp_path, registry(tmp_path), manifests)
    assert result.engineering_pass is False
    assert "sample_path_used_as_evidence" in issue_codes(result)


@pytest.mark.parametrize(
    "metric,value,expected_code",
    [
        ("material_segment_driver_coverage", 0.79, "metric_below_minimum"),
        ("revenue_explained_ratio", 0.70, "metric_below_minimum"),
        ("gross_profit_explained_ratio", 0.70, "metric_below_minimum"),
        ("residual_revenue_ratio", 0.21, "metric_above_maximum"),
        ("section_novelty_ratio", 0.60, "metric_below_minimum"),
        ("unresolved_critical_question_count", 1, "critical_questions_unresolved"),
    ],
)
def test_metric_threshold_failures(tmp_path: Path, metric: str, value: float, expected_code: str) -> None:
    manifests = all_cases(tmp_path)
    manifests[CASE_DEFS[0][0]]["metrics"][metric] = value
    result = evaluate_suite(tmp_path, registry(tmp_path), manifests)
    assert result.engineering_pass is False
    assert expected_code in issue_codes(result)


def test_peer_multiple_requires_three_qualified_compatible_peers(tmp_path: Path) -> None:
    manifests = all_cases(tmp_path)
    first = manifests[CASE_DEFS[0][0]]
    first["metrics"]["qualified_peer_count"] = 2
    first["valuation"]["peer_definition_compatible"] = False
    result = evaluate_suite(tmp_path, registry(tmp_path), manifests)
    assert result.engineering_pass is False
    assert "peer_multiple_without_qualified_peers" in issue_codes(result)
    assert "peer_definition_incompatible" in issue_codes(result)


def test_peer_fallback_is_allowed_when_multiples_disabled(tmp_path: Path) -> None:
    manifests = all_cases(tmp_path)
    first = manifests[CASE_DEFS[0][0]]
    first["metrics"]["qualified_peer_count"] = 0
    first["valuation"] = {
        "peer_multiple_used": False,
        "peer_definition_compatible": False,
        "peer_periods_aligned": False,
        "alternative_method": "reverse_valuation",
    }
    result = evaluate_suite(tmp_path, registry(tmp_path), manifests)
    assert result.engineering_pass is True


def test_accepted_human_review_must_bind_exact_hashes(tmp_path: Path) -> None:
    manifests = all_cases(tmp_path, human_status="accepted")
    case_id, ticker, issuer = CASE_DEFS[0]
    manifests[case_id] = make_case(
        tmp_path,
        case_id,
        ticker,
        issuer,
        human_status="accepted",
        exact_human_hashes=False,
    )
    result = evaluate_suite(tmp_path, registry(tmp_path), manifests)
    assert result.engineering_pass is False
    assert result.sample_quality_allowed is False
    assert "human_review_exact_hash_mismatch" in issue_codes(result)


def test_issuer_specific_runtime_token_blocks_suite(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    runtime.joinpath("bad.py").write_text("ISSUER = '铜冠铜箔'\n", encoding="utf-8")
    result = evaluate_suite(tmp_path, registry(tmp_path), all_cases(tmp_path))
    assert result.engineering_pass is False
    assert "issuer_specific_runtime_token" in issue_codes(result)


def test_outputs_are_byte_deterministic(tmp_path: Path) -> None:
    (tmp_path / "runtime").mkdir()
    evaluation = evaluate_suite(tmp_path, registry(tmp_path), all_cases(tmp_path))
    out_a = tmp_path / "out_a"
    out_b = tmp_path / "out_b"
    json_a, md_a = write_suite_outputs(out_a, evaluation)
    json_b, md_b = write_suite_outputs(out_b, evaluation)
    assert json_a.read_bytes() == json_b.read_bytes()
    assert md_a.read_bytes() == md_b.read_bytes()
    assert render_markdown(evaluation).endswith("\n")


def test_registry_requires_exactly_four_cases(tmp_path: Path) -> None:
    value = registry(tmp_path)
    value["cases"] = value["cases"][:3]
    with pytest.raises(ValueError, match="exactly four"):
        validate_registry(value)
