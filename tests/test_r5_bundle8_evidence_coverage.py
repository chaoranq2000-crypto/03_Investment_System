from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import yaml

from src.research.r5_evidence_coverage import (
    build_coverage_matrix,
    build_evidence_packs,
    validate_coverage_matrix,
)


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "r5_bundle8_research_depth.yaml"


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def source(
    source_id: str,
    *,
    owner_type: str,
    classes: list[str],
    sections: list[str],
    underlying: str | None = None,
    peer_ids: list[str] | None = None,
    counter_for: list[str] | None = None,
    metrics: list[str] | None = None,
) -> dict:
    return {
        "source_id": source_id,
        "underlying_source_id": underlying or source_id,
        "title": source_id,
        "owner_type": owner_type,
        "source_type": "test_fixture",
        "review_status": "reviewed",
        "as_of_date": "2026-06-30",
        "evidence_classes": classes,
        "sections": sections,
        "peer_ids": peer_ids or [],
        "counterevidence_for": counter_for or [],
        "claim_ids": [f"CLAIM-{source_id}"],
        "metric_ids": metrics or [f"METRIC-{source_id}"],
        "source_path": f"fixtures/{source_id}.yaml",
    }


def complete_catalog() -> dict:
    sources = [
        source(
            "ISS-ANNUAL",
            owner_type="issuer",
            classes=[
                "issuer_financial",
                "issuer_business_disclosure",
                "company_operating",
            ],
            sections=["financial_quality", "business_breakdown", "business_driver"],
            metrics=["M-REV", "M-GM", "M-SEGMENT"],
        ),
        source(
            "ISS-Q1",
            owner_type="issuer",
            classes=["issuer_financial"],
            sections=["financial_quality"],
            metrics=["M-CFO", "M-NP"],
        ),
        source(
            "ISS-IR",
            owner_type="issuer_ir",
            classes=["issuer_business_disclosure", "company_operating"],
            sections=["business_breakdown", "business_driver"],
            metrics=["M-ORDER", "M-CAPACITY"],
        ),
        source(
            "CUSTOMER-CHECK",
            owner_type="customer",
            classes=["company_operating", "risk_counterevidence"],
            sections=["business_driver", "risk_counterevidence"],
            counter_for=["B8-COV-COMPANY-OPERATING"],
            metrics=["M-CUSTOMER-DEMAND"],
        ),
        source(
            "IND-DEMAND-1",
            owner_type="industry_association",
            classes=["industry_demand"],
            sections=["industry_context"],
            metrics=["M-IND-DEMAND"],
        ),
        source(
            "IND-DEMAND-2",
            owner_type="research_institution",
            classes=["industry_demand", "risk_counterevidence"],
            sections=["industry_context", "risk_counterevidence"],
            counter_for=["B8-COV-INDUSTRY-DEMAND"],
            metrics=["M-IND-PENETRATION"],
        ),
        source(
            "IND-SUPPLY-1",
            owner_type="government",
            classes=["industry_supply_competition"],
            sections=["industry_context"],
            metrics=["M-IND-SUPPLY"],
        ),
        source(
            "IND-SUPPLY-2",
            owner_type="research_institution",
            classes=["industry_supply_competition", "risk_counterevidence"],
            sections=["industry_context", "risk_counterevidence"],
            counter_for=["B8-COV-INDUSTRY-SUPPLY"],
            metrics=["M-PRICE-PRESSURE"],
        ),
        source(
            "PEER-A",
            owner_type="peer_company",
            classes=["peer_operating"],
            sections=["competitive_position"],
            peer_ids=["peer_a"],
            metrics=["M-PEER-A-GM"],
        ),
        source(
            "PEER-B",
            owner_type="peer_company",
            classes=["peer_operating"],
            sections=["competitive_position"],
            peer_ids=["peer_b"],
            metrics=["M-PEER-B-GM"],
        ),
        source(
            "PEER-C",
            owner_type="peer_company",
            classes=["peer_operating"],
            sections=["competitive_position"],
            peer_ids=["peer_c"],
            metrics=["M-PEER-C-GM"],
        ),
        source(
            "RISK-1",
            owner_type="research_institution",
            classes=["risk_counterevidence"],
            sections=["risk_counterevidence"],
            counter_for=["B8-COV-RISK", "all"],
            metrics=["M-RISK-TRIGGER"],
        ),
    ]
    return {
        "schema_version": "v0.1",
        "workflow_id": "wf_test",
        "as_of_date": "2026-07-12",
        "sources": sources,
    }


def single_requirement_config(coverage_id: str) -> dict:
    config = load_config()
    requirement = next(
        row
        for row in config["coverage_gate"]["requirements"]
        if row["coverage_id"] == coverage_id
    )
    config["coverage_gate"]["requirements"] = [deepcopy(requirement)]
    config["coverage_gate"]["min_covered_requirements"] = 1
    config["coverage_gate"]["min_total_underlying_sources"] = 1
    config["coverage_gate"]["min_total_independent_underlying_sources"] = 0
    return config


def test_complete_catalog_passes_all_coverage_requirements() -> None:
    config = load_config()
    matrix = build_coverage_matrix(
        config,
        complete_catalog(),
        workflow_id="wf_test",
        as_of_date="2026-07-12",
        source_catalog_path="fixture.yaml",
    )
    result = validate_coverage_matrix(matrix, config)
    assert matrix["summary"]["decision"] == "evidence_inputs_ready"
    assert matrix["summary"]["covered_requirements"] == 7
    assert matrix["summary"]["blocking_requirements_open"] == 0
    assert result["decision"] == "pass"


def test_issuer_only_industry_evidence_cannot_pass() -> None:
    config = single_requirement_config("B8-COV-INDUSTRY-DEMAND")
    catalog = {
        "workflow_id": "wf_test",
        "as_of_date": "2026-07-12",
        "sources": [
            source(
                "ISSUER-INDUSTRY-1",
                owner_type="issuer",
                classes=["industry_demand", "risk_counterevidence"],
                sections=["industry_context"],
                counter_for=["B8-COV-INDUSTRY-DEMAND"],
            ),
            source(
                "ISSUER-INDUSTRY-2",
                owner_type="issuer_ir",
                classes=["industry_demand"],
                sections=["industry_context"],
            ),
        ],
    }
    matrix = build_coverage_matrix(config, catalog, as_of_date="2026-07-12")
    row = matrix["requirements"][0]
    assert row["status"] == "blocked"
    assert "independent_source_below_minimum" in row["reason_codes"]


def test_multiple_extracts_from_one_document_count_once() -> None:
    config = single_requirement_config("B8-COV-INDUSTRY-DEMAND")
    catalog = {
        "workflow_id": "wf_test",
        "as_of_date": "2026-07-12",
        "sources": [
            source(
                "IND-EXTRACT-1",
                owner_type="industry_association",
                classes=["industry_demand", "risk_counterevidence"],
                sections=["industry_context"],
                underlying="SAME-DOCUMENT",
                counter_for=["B8-COV-INDUSTRY-DEMAND"],
            ),
            source(
                "IND-EXTRACT-2",
                owner_type="industry_association",
                classes=["industry_demand"],
                sections=["industry_context"],
                underlying="SAME-DOCUMENT",
            ),
        ],
    }
    matrix = build_coverage_matrix(config, catalog, as_of_date="2026-07-12")
    row = matrix["requirements"][0]
    assert len(row["underlying_source_ids"]) == 1
    assert row["status"] == "blocked"


def test_peer_requirement_needs_three_unique_peer_entities() -> None:
    config = single_requirement_config("B8-COV-PEERS")
    catalog = {
        "workflow_id": "wf_test",
        "as_of_date": "2026-07-12",
        "sources": [
            source(
                "PEER-A-ANNUAL",
                owner_type="peer_company",
                classes=["peer_operating"],
                sections=["competitive_position"],
                peer_ids=["peer_a"],
            ),
            source(
                "PEER-A-Q1",
                owner_type="peer_company",
                classes=["peer_operating"],
                sections=["competitive_position"],
                peer_ids=["peer_a"],
            ),
            source(
                "PEER-B",
                owner_type="peer_company",
                classes=["peer_operating"],
                sections=["competitive_position"],
                peer_ids=["peer_b"],
            ),
        ],
    }
    matrix = build_coverage_matrix(config, catalog, as_of_date="2026-07-12")
    row = matrix["requirements"][0]
    assert row["peer_ids"] == ["peer_a", "peer_b"]
    assert "credible_peer_below_minimum" in row["reason_codes"]


def test_stale_or_unreviewed_sources_are_excluded() -> None:
    config = single_requirement_config("B8-COV-RISK")
    stale = source(
        "STALE-RISK",
        owner_type="research_institution",
        classes=["risk_counterevidence"],
        sections=["risk_counterevidence"],
        counter_for=["B8-COV-RISK"],
    )
    stale["as_of_date"] = "2020-01-01"
    draft = source(
        "DRAFT-RISK",
        owner_type="research_institution",
        classes=["risk_counterevidence"],
        sections=["risk_counterevidence"],
        counter_for=["B8-COV-RISK"],
    )
    draft["review_status"] = "draft"
    catalog = {
        "workflow_id": "wf_test",
        "as_of_date": "2026-07-12",
        "sources": [stale, draft],
    }
    matrix = build_coverage_matrix(config, catalog, as_of_date="2026-07-12")
    row = matrix["requirements"][0]
    assert row["status"] == "blocked"
    assert not row["source_ids"]


def test_source_only_handoff_packs_do_not_add_narrative_claims() -> None:
    config = load_config()
    catalog = complete_catalog()
    matrix = build_coverage_matrix(config, catalog, as_of_date="2026-07-12")
    packs = build_evidence_packs(catalog, matrix, config)
    assert packs["industry_evidence_pack"]["source_count"] == 4
    assert packs["peer_operating_pack"]["source_count"] == 3
    assert "conclusion" not in packs["company_operating_evidence_pack"]


def test_validator_rejects_tampered_summary_when_catalog_is_available() -> None:
    config = load_config()
    catalog = complete_catalog()
    matrix = build_coverage_matrix(
        config,
        catalog,
        workflow_id="wf_test",
        as_of_date="2026-07-12",
        source_catalog_path="fixture.yaml",
    )
    matrix["summary"]["independent_underlying_sources"] = 999
    result = validate_coverage_matrix(matrix, config, catalog)
    assert result["decision"] == "fail"
    assert "matrix_summary_not_reproducible" in result["errors"]


def test_source_handoff_packs_exclude_unreviewed_matching_clues() -> None:
    config = load_config()
    catalog = complete_catalog()
    clue = source(
        "DRAFT-INDUSTRY-CLUE",
        owner_type="research_institution",
        classes=["industry_demand"],
        sections=["industry_context"],
    )
    clue["review_status"] = "draft"
    catalog["sources"].append(clue)
    matrix = build_coverage_matrix(config, catalog, as_of_date="2026-07-12")
    packs = build_evidence_packs(catalog, matrix, config)
    industry_ids = {
        row["source_id"] for row in packs["industry_evidence_pack"]["sources"]
    }
    assert "DRAFT-INDUSTRY-CLUE" not in industry_ids
