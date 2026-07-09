from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".agents/skills/evidence-ingest/scripts/build_r5_evidence_request_review_ledger.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_r5_evidence_request_review_ledger", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_builder_preserves_null_evidence_as_pending():
    builder = load_builder()
    ledger = builder.build_ledger(
        {
            "workflow_id": "wf",
            "stock_code": "002837",
            "requests": [
                {
                    "request_id": "req_1",
                    "source_gap_id": "gap_1",
                    "pack_section": "valuation_pack",
                    "evidence_id": None,
                    "source_rank": "B",
                    "missing_reason": "TODO_MARKET_DATA",
                    "next_action": "manual collection",
                }
            ],
        },
        "queue.yaml",
    )

    assert ledger["items"][0]["review_decision"] == "pending"
    assert ledger["summary"]["pending_count"] == 1
    assert ledger["summary"]["accepted_count"] == 0


def test_builder_accepts_rows_only_when_evidence_id_exists():
    builder = load_builder()
    ledger = builder.build_ledger(
        {
            "workflow_id": "wf",
            "stock_code": "002837",
            "requests": [
                {
                    "request_id": "req_1",
                    "source_gap_id": "gap_1",
                    "pack_section": "valuation_pack",
                    "evidence_id": "ev_1",
                    "source_rank": "A",
                }
            ],
        },
        "queue.yaml",
    )

    assert ledger["items"][0]["review_decision"] == "accepted"
    assert ledger["summary"]["accepted_count"] == 1
