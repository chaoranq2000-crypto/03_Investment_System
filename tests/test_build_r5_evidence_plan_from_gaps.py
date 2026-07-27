from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/build_r5_evidence_plan_from_gaps.py"
VALIDATOR_PATH = REPO_ROOT / ".agents/skills/evidence-ingest/scripts/validate_r5_evidence_plan.py"
FIXTURE_WORKFLOW_ID = "wf_fixture_source_gap"
FIXTURE_STOCK_CODE = "300001"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    pack_path = tmp_path / "source_gapped_pack.yaml"
    gap_path = tmp_path / "source_gap_report.md"
    pack_path.write_text(
        yaml.safe_dump(
            {
                "workflow_id": FIXTURE_WORKFLOW_ID,
                "stock": {
                    "stock_code": FIXTURE_STOCK_CODE,
                    "company_name": "Fixture Co",
                },
                "as_of_date": "2026-07-10",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    gap_path.write_text(
        """# Source gaps

| gap_id | section | missing_data | evidence_needed | status | next_action |
| --- | --- | --- | --- | --- | --- |
| GAP_BUSINESS | business_breakdown | MISSING_DISCLOSURE | annual filing | open | register official disclosure |
| GAP_FORECAST | forecast | TODO_MODEL_INPUT | reviewed metrics | open | register forecast inputs |
| GAP_VALUATION | valuation | TODO_PEER_DATA | peer snapshot | open | register peer inputs |
| GAP_MARKET | technical_market | TODO_MARKET_DATA | market snapshot | open | register market inputs |
| GAP_EVENT | sentiment_event | TODO_SOURCE_REQUIRED | dated event source | open | register event source |
| GAP_EXPOSURE | segment_exposure | LOW_CONFIDENCE_CLUE_ONLY | official filing | open | preserve uncertainty |
""",
        encoding="utf-8",
    )
    return pack_path, gap_path


def test_parse_gap_report_extracts_gap_rows(tmp_path: Path):
    builder = load_module("build_r5_evidence_plan_from_gaps", SCRIPT_PATH)
    _, gap_path = write_inputs(tmp_path)
    rows = builder.parse_gap_report(gap_path)

    assert len(rows) >= 5
    assert any(row["section"] == "valuation" for row in rows)


def test_build_plan_contains_required_bridge_fields(tmp_path: Path):
    builder = load_module("build_r5_evidence_plan_from_gaps", SCRIPT_PATH)
    pack_path, gap_path = write_inputs(tmp_path)
    pack = builder.load_yaml(pack_path)
    plan = builder.build_plan(pack, builder.parse_gap_report(gap_path), str(gap_path))

    assert plan["stock_code"] == FIXTURE_STOCK_CODE
    assert plan["workflow_id"] == FIXTURE_WORKFLOW_ID
    assert plan["priority"] == "high"
    assert plan["blocking_for_r5"] is True
    assert plan["market_snapshot_needed"]
    assert plan["peer_snapshot_needed"]
    assert plan["news_and_event_sources_needed"]


def test_generated_plan_validates(tmp_path: Path):
    builder = load_module("build_r5_evidence_plan_from_gaps", SCRIPT_PATH)
    validator = load_module("validate_r5_evidence_plan", VALIDATOR_PATH)
    pack_path, gap_path = write_inputs(tmp_path)
    out = tmp_path / "R5_evidence_plan_from_gaps.yaml"

    assert (
        builder.main(
            [
                "--pack",
                str(pack_path),
                "--source-gap-report",
                str(gap_path),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    plan = yaml.safe_load(out.read_text(encoding="utf-8"))
    issues = validator.validate_plan(plan)

    assert issues == []
    assert validator.decision_for(issues) == "accepted"


def test_builder_does_not_add_live_api_boundary(tmp_path: Path):
    builder = load_module("build_r5_evidence_plan_from_gaps", SCRIPT_PATH)
    pack_path, gap_path = write_inputs(tmp_path)
    pack = builder.load_yaml(pack_path)
    plan = builder.build_plan(pack, builder.parse_gap_report(gap_path), str(gap_path))

    assert plan["implementation_boundary"]["no_live_api"] is True
    assert plan["implementation_boundary"]["plan_only"] is True
