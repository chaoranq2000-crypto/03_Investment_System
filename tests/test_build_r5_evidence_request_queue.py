from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / ".agents/skills/evidence-ingest/scripts/build_r5_evidence_request_queue.py"
PLAN_PATH = REPO_ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_plan_from_gaps.yaml"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_r5_evidence_request_queue", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_queue_flattens_plan_requests():
    builder = load_builder()
    plan = builder.load_yaml(PLAN_PATH)
    queue = builder.build_queue(plan, str(PLAN_PATH))

    assert queue["artifact_type"] == "R5_evidence_request_queue"
    assert queue["no_live_api"] is True
    assert queue["summary"]["request_count"] >= 8
    assert queue["summary"]["source_gap_count"] >= 5


def test_request_rows_have_required_contract_fields():
    builder = load_builder()
    plan = builder.load_yaml(PLAN_PATH)
    request = builder.build_queue(plan, str(PLAN_PATH))["requests"][0]

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
    out = tmp_path / "R5_evidence_request_queue.yaml"

    assert builder.main(["--plan", str(PLAN_PATH), "--out", str(out)]) == 0
    queue = yaml.safe_load(out.read_text(encoding="utf-8"))

    assert queue["requests"]
    assert len(out.read_text(encoding="utf-8").splitlines()) > 20
