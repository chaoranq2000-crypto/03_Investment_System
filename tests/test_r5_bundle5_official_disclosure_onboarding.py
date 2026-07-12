from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = REPO_ROOT / "scripts/build_r5_bundle5_official_disclosure_onboarding.py"
SKILL_SCRIPTS = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BUILDER = load_module("r5_bundle5_official_disclosure_builder_test", BUILDER_PATH)
FINANCIAL_VALIDATOR = load_module(
    "r5_bundle5_financial_validator_test",
    SKILL_SCRIPTS / "validate_r5_financial_history_pack.py",
)
BUSINESS_VALIDATOR = load_module(
    "r5_bundle5_business_validator_test",
    SKILL_SCRIPTS / "validate_r5_business_breakdown_pack.py",
)


def test_archived_official_sources_match_declared_hashes() -> None:
    verified = BUILDER.verify_sources(REPO_ROOT)
    assert {row["evidence_id"] for row in verified} == {
        BUILDER.ANNUAL_EVIDENCE_ID,
        BUILDER.INTERIM_EVIDENCE_ID,
        BUILDER.Q1_EVIDENCE_ID,
    }
    assert {row["page_count"] for row in verified} == {196, 162, 11}


def test_reviewed_business_records_are_accepted_and_boundary_safe() -> None:
    records = BUILDER.build_business_records("2026-07-12T01:15:00+08:00")
    assert len(records) == 9
    assert len({row["input_id"] for row in records}) == len(records)
    forbidden = {
        "TODO_MARKET_DATA",
        "TODO_PEER_DATA",
        "TODO_MODEL_INPUT",
        "TODO_SOURCE_REQUIRED",
        "MISSING_DISCLOSURE",
        "LOW_CONFIDENCE_CLUE_ONLY",
    }
    text = yaml.safe_dump(records, allow_unicode=True)
    assert not any(token in text for token in forbidden)
    for row in records:
        assert row["review_status"] == "accepted"
        assert row["reviewer"] == "codex"
        assert row["source_evidence_id"] == BUILDER.ANNUAL_EVIDENCE_ID
        assert row["no_live_api"] is True
        assert row["sample_quality_allowed"] is False
        assert row["claim_type"] == "fact"


def test_financial_history_candidate_validates_as_accepted() -> None:
    pack = BUILDER.build_financial_history_pack()
    assert FINANCIAL_VALIDATOR.validate_financial_history_pack(pack) == []
    assert FINANCIAL_VALIDATOR.derive_outcome([], pack) == "accepted"
    assert pack["status"] == "ready"
    assert pack["periods"] == ["2023A", "2024A", "2025A", "2026Q1"]
    q1_margin = next(
        row
        for row in pack["key_metrics"]
        if row["metric_name"] == "gross_margin" and row["period"] == "2026Q1"
    )
    assert q1_margin["claim_type"] == "inference"
    assert q1_margin["value"] == 24.2935


def test_business_breakdown_reconciles_and_keeps_liquid_split_missing() -> None:
    pack = BUILDER.build_business_breakdown_pack()
    assert BUSINESS_VALIDATOR.validate_business_breakdown_pack(pack) == []
    assert BUSINESS_VALIDATOR.derive_outcome([], pack) == "accepted_with_todos"
    assert pack["profit_pool_summary"]["reconciliation_residual"] == 0.0
    liquid = next(row for row in pack["business_lines"] if row["business_name"] == "liquid_cooling_specific")
    assert liquid["confidence"] == "medium"
    for metric_name in ("revenue", "revenue_pct", "gross_margin", "gross_profit", "gross_profit_pct"):
        assert liquid[metric_name]["value"] is None
        assert liquid[metric_name]["missing_reason"] == "MISSING_DISCLOSURE"
    room = next(row for row in pack["business_lines"] if row["business_name"] == "room_cooling")
    cabinet = next(row for row in pack["business_lines"] if row["business_name"] == "cabinet_cooling")
    assert room["gross_profit"]["value"] == 977_827_266.53
    assert cabinet["gross_profit"]["value"] == 538_639_525.94


def test_card_5_2_partial_preflight_preserves_hard_boundaries() -> None:
    result = BUILDER.build_partial_core_preflight()
    assert result["status"] == "pass_for_card_5_2_partial_core"
    assert result["blocking_for_card_5_2"] == []
    assert result["canonical_registry_write_allowed"] is False
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False
