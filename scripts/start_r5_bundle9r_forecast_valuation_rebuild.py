from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research.r5_bundle9r_contracts import load_yaml, validate_evidence_generation_lock  # noqa: E402

PACKAGE_DATE = "2026-07-13"
CONSUMER = "R5_BUNDLE_9R_FORECAST_VALUATION_REBUILD"


def build_state(state: dict, lock: dict) -> dict:
    issues = validate_evidence_generation_lock(lock, required_consumer=CONSUMER)
    if issues:
        raise ValueError("Evidence generation lock is not eligible for Bundle 9R: " + "; ".join(x.code for x in issues))
    current_id = str(lock["generation_id"])
    recorded = str((state.get("evidence_snapshot") or {}).get("input_evidence_generation_id") or "")
    if recorded != current_id:
        raise ValueError(f"workflow evidence generation {recorded or '<missing>'} does not match {current_id}")

    out = copy.deepcopy(state)
    out["status"] = "in_progress"
    out["quality_target"] = "R5_bundle9r_forecast_valuation_rebuild"
    out["updated_at"] = PACKAGE_DATE
    out["current_stage"] = "R5_bundle9r_0_generation_binding"
    out["next_stage"] = "R5_bundle9r_1_input_review"
    out["active_skill"] = "stock-deep-dive"
    out["required_next_skill"] = "stock-deep-dive"
    out["bundle9r_rebuild"] = {
        "mode": "forward_rebuild_not_history_rewrite",
        "status": "in_progress",
        "started_at": PACKAGE_DATE,
        "input_evidence_generation_id": current_id,
        "historical_bundle9_preserved": True,
        "historical_bundle10_preserved": True,
        "required_close_artifact": "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_model_generation_lock.yaml",
        "downstream_bundle": "R5_BUNDLE_10R_READER_REBUILD",
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
    backflow = dict(out.get("quality_backflow") or {})
    backflow.update({
        "canonical_reader_status": "stale_pending_bundle9r_and_bundle10r",
        "canonical_sample_quality_allowed": False,
        "current_first_route": "forecast_valuation_rebuild",
        "current_first_stage": "R5_bundle9r_0_generation_binding",
    })
    out["quality_backflow"] = backflow
    close = dict(out.get("bundle8r_close") or {})
    close["next_bundle"] = CONSUMER
    close["notes"] = "Bundle 9R explicitly started from the Bundle 8R evidence generation; historical Bundle 9/10 remain snapshots."
    out["bundle8r_close"] = close
    requal = dict(out.get("bundle8r_requalification") or {})
    requal["bundle9r_rebuilt"] = False
    requal["bundle10r_rebuilt"] = False
    requal["canonical_reader_status"] = "stale_pending_bundle9r_and_bundle10r"
    requal["canonical_sample_quality_allowed"] = False
    out["bundle8r_requalification"] = requal
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview or write the forward Bundle 9R workflow-state transition.")
    parser.add_argument("--workflow-state", required=True)
    parser.add_argument("--evidence-lock", required=True)
    parser.add_argument("--output")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    state_path = Path(args.workflow_state)
    state = load_yaml(state_path)
    lock = load_yaml(Path(args.evidence_lock))
    updated = build_state(state, lock)
    rendered = yaml.safe_dump(updated, allow_unicode=True, sort_keys=False)

    if args.write:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = state_path.with_name(state_path.name + f".pre_bundle9r_{stamp}.bak")
        backup.write_bytes(state_path.read_bytes())
        state_path.write_bytes(rendered.encode("utf-8"))
        print(f"wrote={state_path} backup={backup}")
    else:
        output = Path(args.output or (str(state_path) + ".bundle9r_preview.yaml"))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(rendered.encode("utf-8"))
        print(f"preview={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
