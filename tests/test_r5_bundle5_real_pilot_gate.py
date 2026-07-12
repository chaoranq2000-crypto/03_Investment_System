from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
RUN_DIR = REPO_ROOT / "reports/workflow_runs" / WORKFLOW_ID
RUNNER_PATH = REPO_ROOT / "scripts/run_r5_bundle5_research_draft_quality_gate.py"
PACK_VALIDATOR_PATH = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_r5_stock_research_pack.py"
SCORECARD_VALIDATOR_PATH = REPO_ROOT / ".agents/skills/quality-review/scripts/validate_r5_quality_scorecard.py"
PROMOTION_GATE_PATH = REPO_ROOT / "scripts/r5_pack_promotion_gate.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = load_module("r5_bundle5_card56_runner_test", RUNNER_PATH)
PACK_VALIDATOR = load_module("r5_bundle5_card56_pack_validator_test", PACK_VALIDATOR_PATH)
SCORECARD_VALIDATOR = load_module("r5_bundle5_card56_scorecard_validator_test", SCORECARD_VALIDATOR_PATH)
PROMOTION_GATE = load_module("r5_bundle5_card56_promotion_gate_test", PROMOTION_GATE_PATH)


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_real_pilot_gate_is_open_but_capped_at_reviewed_input() -> None:
    gate = json.loads((RUN_DIR / "R5_bundle5_real_pilot_gate_result.json").read_text(encoding="utf-8"))

    assert gate["current_r5_state"] == "R5_REVIEWED_INPUT_PILOT_ALLOWED"
    assert gate["reviewed_input_pilot_allowed"] is True
    assert gate["blockers"] == []
    assert gate["input_summary"]["raw_pack_promotion_level"] == "sample_quality_candidate"
    assert gate["input_summary"]["pack_promotion_level"] == "reviewed_input_research_draft"
    assert gate["sample_quality_report_allowed"] is False
    assert gate["p2_allowed"] is False


def test_bundle5_fixed_boundary_cannot_be_opened_by_empty_sample_blockers() -> None:
    rules = load_yaml(REPO_ROOT / "config/r5_bundle5_pilot_gate_rules.yaml")
    inputs = RUNNER.pilot_gate.collect_inputs(REPO_ROOT, rules)
    inputs["quality_scorecard_v2"] = dict(inputs["quality_scorecard_v2"])
    inputs["quality_scorecard_v2"]["sample_quality_blockers"] = []

    result = RUNNER.pilot_gate.evaluate_gate(inputs, rules)

    assert result["reviewed_input_pilot_allowed"] is True
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False
    assert result["input_summary"]["pack_promotion_level"] == "reviewed_input_research_draft"


def test_render_consumes_bundle5_real_artifacts_and_preserves_markers() -> None:
    result = load_yaml(RUN_DIR / "R5_reviewed_input_render_result.yaml")

    assert result["rendered_output_type"] == "reviewed_input_research_draft"
    assert result["forbidden_language_check"] == {"status": "pass", "forbidden_found": []}
    assert all(result["required_markers"].values())
    assert result["remaining_todos"] == []
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False
    assert result["input_artifacts"]["pack"]["path"].endswith("R5_bundle5_stock_research_pack.yaml")
    assert result["input_artifacts"]["gate"]["path"].endswith("R5_bundle5_real_pilot_gate_result.json")
    assert result["input_artifacts"]["scorecard"]["path"].endswith("R5_bundle5_quality_scorecard.yaml")
    assert all(len(row["sha256"]) == 64 for row in result["input_artifacts"].values())


def test_rendered_report_is_grounded_and_does_not_restore_resolved_todos() -> None:
    text = (RUN_DIR / "R5_stock_research_note_reviewed_input_draft.md").read_text(encoding="utf-8")

    for evidence_id in [
        "ev_annual_report_002837_20260421_2cbfc5",
        "ev_quarterly_report_002837_20260421_2f00c7",
        "ev_structured_market_data_002837_20260710_eb0c08",
    ]:
        assert evidence_id in text
    for claim_type in ["fact", "estimate", "inference"]:
        assert claim_type in text
    for resolved_token in ["TODO_MARKET_DATA", "TODO_PEER_DATA", "TODO_MODEL_INPUT"]:
        assert resolved_token not in text
    assert "MISSING_DISCLOSURE" in text
    assert "Source Gap Appendix" in text
    assert "Open Questions" in text
    assert "风险、反证与开放问题" in text
    assert "PS | 15.4449" in text
    assert "PS TTM | 14.8507" in text
    assert "sample_quality_candidate" not in text
    assert RUNNER.renderer.FORBIDDEN.search(text) is None


def test_transient_segment_exposure_uses_current_evidence_and_visible_missing_state() -> None:
    pack = load_yaml(RUN_DIR / "R5_bundle5_stock_research_pack.yaml")
    exposure = pack["segment_exposure_pack"]["exposures"][0]

    assert exposure["segment_id"] == "ai_server_liquid_cooling"
    assert exposure["evidence_ids"] == ["ev_annual_report_002837_20260421_2cbfc5"]
    assert exposure["confidence"] == "medium"
    assert exposure["revenue_pct"] == "MISSING_DISCLOSURE"
    assert exposure["profit_pct"] == "MISSING_DISCLOSURE"
    assert "ce7f64" not in yaml.safe_dump(pack, allow_unicode=True)


def test_policy_enum_does_not_reactivate_resolved_todos() -> None:
    pack = load_yaml(RUN_DIR / "R5_bundle5_stock_research_pack.yaml")
    dry_run = load_yaml(RUN_DIR / "R5_reviewed_input_dry_run_result.yaml")
    rules = load_yaml(REPO_ROOT / "config/r5_pack_promotion_rules.yaml")

    pack_issues = PACK_VALIDATOR.validate_pack_issues(pack)
    assert not [issue for issue in pack_issues if issue["issue_id"] == "R5P-GAP-002"]
    promotion = PROMOTION_GATE.evaluate_promotion(pack, dry_run, rules)
    assert promotion["blockers"] == []


def test_reviewed_input_scorecard_keeps_level_with_sample_blockers() -> None:
    scorecard = load_yaml(RUN_DIR / "R5_bundle5_quality_scorecard.yaml")
    issues = SCORECARD_VALIDATOR.validate_scorecard(scorecard)

    assert not [issue for issue in issues if issue["severity"] == "high"]
    assert scorecard["sample_quality_blockers"]
    assert SCORECARD_VALIDATOR.derive_decision(scorecard, issues) == "reviewed_input_research_draft"
    assert scorecard["sample_quality_report_allowed"] is False
    assert scorecard["p2_allowed"] is False


def test_quality_gate_has_zero_critical_blockers_and_visible_noncritical_issues() -> None:
    quality = load_yaml(RUN_DIR / "R5_bundle5_quality_gate_result.yaml")

    assert quality["quality_decision"] == "accepted_with_todos"
    assert quality["allowed_report_level"] == "reviewed_input_research_draft"
    assert quality["rendered_output_type"] == "reviewed_input_research_draft"
    assert quality["critical_quality_blockers"] == 0
    assert quality["blocker_details"] == []
    assert quality["sample_quality_report_allowed"] is False
    assert quality["p2_allowed"] is False
    assert quality["remaining_registry_todos"] == []
    assert set(quality["resolved_registry_todos"]) == {"TODO_MARKET_DATA", "TODO_PEER_DATA", "TODO_MODEL_INPUT"}
    assert quality["visible_source_gaps"]
    assert quality["issues"]
    for issue in quality["issues"]:
        assert issue["blocking_decision"] is False
        assert issue["fix_owner_skill"]
        assert issue["next_action"]
        assert issue["status"] == "open_visible"
