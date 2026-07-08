from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/build_r5_evidence_plan_from_gaps.py"
PACK_PATH = REPO_ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_pack_source_gapped.yaml"
GAP_PATH = REPO_ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_source_gap_report.md"
VALIDATOR_PATH = REPO_ROOT / ".agents/skills/evidence-ingest/scripts/validate_r5_evidence_plan.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_gap_report_extracts_gap_rows():
    builder = load_module("build_r5_evidence_plan_from_gaps", SCRIPT_PATH)
    rows = builder.parse_gap_report(GAP_PATH)

    assert len(rows) >= 5
    assert any(row["section"] == "valuation" for row in rows)


def test_build_plan_contains_required_bridge_fields():
    builder = load_module("build_r5_evidence_plan_from_gaps", SCRIPT_PATH)
    pack = builder.load_yaml(PACK_PATH)
    plan = builder.build_plan(pack, builder.parse_gap_report(GAP_PATH), str(GAP_PATH))

    assert plan["stock_code"] == "002837"
    assert plan["workflow_id"] == "wf_20260703_stock_first_002837_invic"
    assert plan["priority"] == "high"
    assert plan["blocking_for_r5"] is True
    assert plan["market_snapshot_needed"]
    assert plan["peer_snapshot_needed"]
    assert plan["news_and_event_sources_needed"]


def test_generated_plan_validates(tmp_path: Path):
    builder = load_module("build_r5_evidence_plan_from_gaps", SCRIPT_PATH)
    validator = load_module("validate_r5_evidence_plan", VALIDATOR_PATH)
    out = tmp_path / "R5_evidence_plan_from_gaps.yaml"

    assert builder.main(["--pack", str(PACK_PATH), "--source-gap-report", str(GAP_PATH), "--out", str(out)]) == 0
    plan = yaml.safe_load(out.read_text(encoding="utf-8"))
    issues = validator.validate_plan(plan)

    assert issues == []
    assert validator.decision_for(issues) == "accepted"


def test_builder_does_not_add_live_api_boundary():
    builder = load_module("build_r5_evidence_plan_from_gaps", SCRIPT_PATH)
    pack = builder.load_yaml(PACK_PATH)
    plan = builder.build_plan(pack, builder.parse_gap_report(GAP_PATH), str(GAP_PATH))

    assert plan["implementation_boundary"]["no_live_api"] is True
    assert plan["implementation_boundary"]["plan_only"] is True
