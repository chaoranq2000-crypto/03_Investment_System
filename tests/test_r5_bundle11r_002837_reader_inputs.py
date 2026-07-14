from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "reports" / "workflow_runs" / "wf_20260703_stock_first_002837_invic"
SCRIPT = ROOT / "scripts" / "build_r5_bundle11r_002837_reader_inputs.py"


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_r5_bundle11r_002837_reader_inputs", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _build(tmp_path: Path):
    builder = _load_builder()
    shutil.copy2(RUN_DIR / "bundle11r" / "R5_bundle11r_runtime_result.yaml", tmp_path)
    outputs = builder.build_reader_inputs(ROOT, tmp_path)
    return builder, outputs


def test_reader_inputs_split_runtime_and_reconcile_to_9r(tmp_path: Path) -> None:
    _, outputs = _build(tmp_path)
    expected = {
        "research_question_matrix",
        "operating_driver_pack",
        "peer_eligibility",
        "semantic_quality",
        "backflow_plan",
        "reconciliation",
    }
    assert expected.issubset(outputs)
    assert all(outputs[key].exists() for key in expected)

    reconciliation = yaml.safe_load(outputs["reconciliation"].read_text(encoding="utf-8"))
    assert reconciliation["decision"] == "pass"
    assert reconciliation["summary"]["row_count"] == 9
    assert reconciliation["summary"]["passed_row_count"] == 9
    assert reconciliation["summary"]["max_absolute_revenue_difference_CNY"] <= 0.02
    assert reconciliation["summary"]["max_absolute_gross_profit_difference_CNY"] <= 0.02
    assert reconciliation["summary"]["forecast_and_valuation_values_changed"] is False


def test_reader_input_adds_11r_references_and_preserves_boundaries(tmp_path: Path) -> None:
    _, outputs = _build(tmp_path)
    reader_input = yaml.safe_load(outputs["reader_input"].read_text(encoding="utf-8"))
    refs = {item["display_reference_id"] for item in reader_input["reference_catalog"]}
    assert {"E23", "E24", "E25", "E26", "E27", "E28"}.issubset(refs)
    assert reader_input["human_review_status"] == "pending"
    assert reader_input["guardrails"]["sample_quality_allowed"] is False
    assert reader_input["guardrails"]["p2_allowed"] is False
    assert reader_input["guardrails"]["peer_multiples_allowed"] is False

    plan = yaml.safe_load(outputs["narrative_plan"].read_text(encoding="utf-8"))
    assert len(plan["narrative_chapters"]) == 6
    embedded_refs = {
        ref
        for chapter in plan["narrative_chapters"]
        for collection in (chapter.get("paragraphs") or [], chapter.get("paragraphs_after_tables") or [])
        for item in collection
        for ref in item.get("refs") or []
    }
    assert {"E23", "E24", "E25", "E26", "E27", "E28"}.issubset(embedded_refs)
