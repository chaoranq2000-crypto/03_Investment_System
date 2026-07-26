from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / ".agents/skills/evidence-ingest/scripts/build_r5_evidence_request_queue.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_r5_evidence_request_queue", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_plan(tmp_path: Path) -> Path:
    def request(
        request_id: str,
        evidence_need: str,
        source_type: str,
        pack_section: str,
    ) -> dict:
        return {
            "request_id": request_id,
            "evidence_need": evidence_need,
            "source_type": source_type,
            "source_rank": "A" if source_type == "annual_report" else "B",
            "freshness_policy": "explicit_as_of_date_or_visible_gap",
            "required_for_pack": [pack_section],
            "allowed_usage": ["fact_support"],
            "missing_reason": evidence_need,
            "next_action": "register reviewed evidence",
        }

    plan = {
        "workflow_id": "wf_fixture_request_queue",
        "stock_code": "300001",
        "evidence_requests": {
            "official_filings": [
                request("request_business", "MISSING_DISCLOSURE", "annual_report", "business_breakdown_pack"),
                request("request_exposure", "LOW_CONFIDENCE_CLUE_ONLY", "annual_report", "segment_exposure_pack"),
            ],
            "structured_financial_metrics": [
                request("request_forecast", "TODO_MODEL_INPUT", "structured_financial_data", "forecast_model_pack"),
            ],
            "market_snapshot": [
                request("request_market", "TODO_MARKET_DATA", "market_data_snapshot", "technical_market_pack"),
            ],
            "peer_snapshot": [
                request("request_peer", "TODO_PEER_DATA", "peer_snapshot", "peer_comparison_pack"),
            ],
            "industry_context_clues": [
                request("request_industry", "TODO_SOURCE_REQUIRED industry", "industry_context_clues", "industry_context_pack"),
            ],
            "news_event_clues": [
                request("request_event", "TODO_SOURCE_REQUIRED event", "news_or_event_source", "sentiment_event_pack"),
            ],
            "investor_relations": [
                request("request_ir", "TODO_SOURCE_REQUIRED investor relations", "investor_relations", "business_breakdown_pack"),
            ],
        },
    }
    path = tmp_path / "evidence_plan.yaml"
    path.write_text(
        yaml.safe_dump(plan, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return path


def test_build_queue_flattens_plan_requests(tmp_path: Path):
    builder = load_builder()
    plan_path = write_plan(tmp_path)
    plan = builder.load_yaml(plan_path)
    queue = builder.build_queue(plan, str(plan_path))

    assert queue["artifact_type"] == "R5_evidence_request_queue"
    assert queue["no_live_api"] is True
    assert queue["summary"]["request_count"] >= 8
    assert queue["summary"]["source_gap_count"] >= 5


def test_request_rows_have_required_contract_fields(tmp_path: Path):
    builder = load_builder()
    plan_path = write_plan(tmp_path)
    plan = builder.load_yaml(plan_path)
    request = builder.build_queue(plan, str(plan_path))["requests"][0]

    for key in [
        "request_id",
        "workflow_id",
        "stock_code",
        "source_gap_id",
        "pack_section",
        "evidence_need",
        "source_type",
        "source_rank",
        "freshness_policy",
        "required_for_pack",
        "allowed_usage",
        "owner_skill",
        "status",
        "evidence_id",
        "missing_reason",
        "next_action",
        "no_live_api",
    ]:
        assert key in request
    assert request["status"] == "planned"
    assert request["evidence_id"] is None
    assert request["no_live_api"] is True


def test_cli_writes_multiline_yaml_queue(tmp_path: Path):
    builder = load_builder()
    plan_path = write_plan(tmp_path)
    out = tmp_path / "R5_evidence_request_queue.yaml"

    assert builder.main(["--plan", str(plan_path), "--out", str(out)]) == 0
    queue = yaml.safe_load(out.read_text(encoding="utf-8"))

    assert queue["requests"]
    assert len(out.read_text(encoding="utf-8").splitlines()) > 20
