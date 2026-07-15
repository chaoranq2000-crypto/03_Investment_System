from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from scripts.build_r5_bundle16r_case_pack import CaseInputError, build_case, route_gate_issues


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _truthfulness() -> dict[str, bool]:
    return {
        "sample_text_used_as_evidence": False,
        "management_guidance_recast_as_fact": False,
        "low_confidence_peer_ranked": False,
        "direct_trading_instruction_present": False,
        "past_event_presented_as_future": False,
        "undisclosed_segment_economics_presented_as_fact": False,
        "consensus_estimate_presented_as_issuer_fact": False,
    }


def _fixture(repo: Path) -> tuple[Path, Path]:
    raw = repo / "data/raw/source.pdf"
    text = repo / "data/processed/source.md"
    raw.parent.mkdir(parents=True)
    text.parent.mkdir(parents=True)
    raw.write_bytes(b"%PDF-test-fixture")
    text.write_text("# reviewed source\n", encoding="utf-8")
    registry = {
        "schema_version": "r5_bundle16r_real_company_regression_v1",
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
        "cases": [{"case_id": "case_alpha", "ticker": "000001", "issuer_name": "测试发行人"}],
    }
    registry_path = repo / "config/registry.yaml"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(yaml.safe_dump(registry, allow_unicode=True), encoding="utf-8")
    metrics = [
        {
            "metric_id": f"metric_{index}",
            "name": f"指标{index}",
            "value": index,
            "unit": "unit",
            "period": "2025A",
            "evidence_id": "ev_source",
            "locator": "page:1",
        }
        for index in range(8)
    ]
    segments = []
    for segment_id, revenue, cost in (("segment_a", 60.0, 45.0), ("segment_b", 40.0, 35.0)):
        segments.append(
            {
                "segment_id": segment_id,
                "display_name": segment_id,
                "material": True,
                "revenue": revenue,
                "cost": cost,
                "driver_contract": {
                    "archetype_id": "volume_price_mix",
                    "equation": "volume * price",
                    "driver_topics": ["volume", "price"],
                    "source_evidence_ids": ["ev_source"],
                },
            }
        )
    forecast_segments = [
        {
            "segment_id": row["segment_id"],
            "base_revenue": row["revenue"],
            "growth_rates": {scenario: [0.05, 0.05, 0.05] for scenario in ("bear", "base", "bull")},
            "gross_margins": {scenario: [0.2, 0.2, 0.2] for scenario in ("bear", "base", "bull")},
        }
        for row in segments
    ]
    sections = [
        {
            "section_id": f"section_{index}",
            "title": f"章节{index}",
            "judgment": f"这是第{index}个独立判断，描述不同经营变量与验证边界。",
            "paragraphs": [
                {
                    "text": f"第{index}部分使用事实来源说明专属机制，并保留反证条件。",
                    "refs": ["ev_source", f"metric_{index}"],
                }
            ],
            "model_links": ["segment_a"],
        }
        for index in range(8)
    ]
    payload = {
        "schema_version": "r5_bundle16r_case_input_v1",
        "case_id": "case_alpha",
        "ticker": "000001",
        "issuer_name": "测试发行人",
        "company_id": "company_alpha",
        "workflow_id": "wf_case_alpha",
        "as_of_date": "2026-07-15",
        "generated_at": "2026-07-15T00:00:00+08:00",
        "sources": [
            {
                "evidence_id": "ev_source",
                "source_class": "official",
                "source_type": "annual_report",
                "title": "年度报告",
                "source_path": "data/raw/source.pdf",
                "processed_text_path": "data/processed/source.md",
                "file_hash": _sha(raw),
                "page_count": 1,
                "review_status": "reviewed",
            }
        ],
        "historical": {
            "period": "2025A",
            "unit": "CNY",
            "total_revenue": 100.0,
            "total_gross_profit": 20.0,
            "segments": segments,
        },
        "company_metrics": metrics,
        "claims": [],
        "research_questions": [],
        "forecast": {
            "periods": ["2026E", "2027E", "2028E"],
            "scenarios": ["bear", "base", "bull"],
            "assumptions": [
                {
                    "assumption_id": f"assumption_{index}",
                    "estimate_logic": "explicit scenario estimate",
                }
                for index in range(4)
            ],
            "segments": forecast_segments,
            "future_events": [
                {
                    "event_id": "event_one",
                    "verification_metric": "revenue",
                    "model_links": ["segment_a"],
                },
                {
                    "event_id": "event_two",
                    "verification_metric": "margin",
                    "model_links": ["segment_b"],
                },
            ],
        },
        "valuation": {
            "peer_multiple_used": False,
            "qualified_peers": [],
            "alternative_method": "scenario_valuation",
        },
        "reader": {"sections": sections},
        "truthfulness": _truthfulness(),
    }
    input_path = repo / "reports/input.yaml"
    input_path.parent.mkdir(parents=True)
    input_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return input_path, registry_path


def test_case_builder_derives_metrics_and_is_deterministic(tmp_path: Path) -> None:
    input_path, registry_path = _fixture(tmp_path)
    kwargs = {
        "repo_root": tmp_path,
        "input_path": input_path,
        "registry_path": registry_path,
        "output_dir": tmp_path / "reports/output",
        "case_results_dir": tmp_path / "bundle16r/generated/case_results",
    }
    first = build_case(**kwargs)
    manifest = tmp_path / first["case_manifest"]
    reader = tmp_path / first["output_dir"] / "reader_report.md"
    first_manifest = manifest.read_bytes()
    first_reader = reader.read_bytes()
    second = build_case(**kwargs)
    assert manifest.read_bytes() == first_manifest
    assert reader.read_bytes() == first_reader
    assert first == second
    assert first["gate_issues"] == []
    assert first["metrics"]["material_segment_driver_coverage"] == 1.0
    assert first["metrics"]["citation_resolution_rate"] == 1.0
    assert first["human_review_status"] == "pending"


def test_case_builder_rejects_unreconciled_historical_bridge(tmp_path: Path) -> None:
    input_path, registry_path = _fixture(tmp_path)
    payload = yaml.safe_load(input_path.read_text(encoding="utf-8"))
    payload["historical"]["total_revenue"] = 101.0
    input_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    with pytest.raises(CaseInputError, match="does not reconcile"):
        build_case(
            repo_root=tmp_path,
            input_path=input_path,
            registry_path=registry_path,
            output_dir=tmp_path / "reports/output",
            case_results_dir=tmp_path / "bundle16r/generated/case_results",
        )


def test_gate_failures_route_to_owning_stage() -> None:
    routed = route_gate_issues(
        [
            {"code": "METRIC_BELOW_MINIMUM", "metric": "forecast_assumption_traceability"},
            {"code": "CRITICAL_QUESTION_OPEN", "metric": "unresolved_critical_question_count"},
            {"code": "METRIC_BELOW_MINIMUM", "metric": "citation_resolution_rate"},
        ]
    )
    assert [row["owner"] for row in routed] == [
        "forecast_model",
        "research_question_planner",
        "quality_review",
    ]
    assert all(row["severity"] == "critical" and row["next_step"] for row in routed)
