from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml


def _stable_hash(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def start_requalification(
    state: Mapping[str, Any],
    *,
    baseline_commit: str,
    activated_at: str,
) -> dict[str, Any]:
    updated = copy.deepcopy(dict(state))
    historical_hashes = {
        "bundle8_close_sha256": _stable_hash(updated.get("bundle8_close")),
        "bundle9_close_sha256": _stable_hash(updated.get("bundle9_close")),
        "bundle10_close_sha256": _stable_hash(updated.get("bundle10_close")),
    }
    updated["status"] = "needs_fix"
    updated["quality_target"] = "R5_sample_quality_requalification"
    updated["updated_at"] = activated_at
    updated["current_stage"] = "R5_bundle8r_forward_requalification"
    updated["next_stage"] = "R5_bundle8r_0_capability_audit"
    updated["active_skill"] = "research-orchestrator"
    updated["required_next_skill"] = "evidence-ingest"
    updated["bundle8r_requalification"] = {
        "mode": "forward_requalification_not_rollback",
        "status": "active",
        "baseline_commit": baseline_commit,
        "activated_at": activated_at,
        "reason": "Bundle 9 and Bundle 10 are retained, but their research quality is not accepted by the owner; rebuild upstream evidence capability first.",
        "historical_closures_preserved": ["bundle8_close", "bundle9_close", "bundle10_close"],
        "historical_close_hashes": historical_hashes,
        "canonical_reader_status": "stale_pending_bundle8r_evidence_generation",
        "canonical_sample_quality_allowed": False,
        "p2_allowed": False,
        "backflow_target": "evidence-ingest",
        "required_close_artifact": "R5_bundle8r_evidence_generation_lock.yaml",
        "downstream_plan": {
            "bundle9": "preserved_historical_then_rebuild_as_bundle9r",
            "bundle10": "preserved_historical_then_rebuild_as_bundle10r",
        },
    }
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Start forward Bundle 8R requalification without deleting Bundle 9/10 history")
    parser.add_argument("--workflow-state", required=True)
    parser.add_argument("--baseline-commit", default="08acbf9084dc32dade6d899ed3e8bbdbbc107efd")
    parser.add_argument("--activated-at", default="2026-07-13")
    parser.add_argument("--output", default="")
    parser.add_argument("--write", action="store_true", help="Replace the source state after writing a backup")
    args = parser.parse_args()

    source = Path(args.workflow_state)
    state = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    if not isinstance(state, dict):
        raise SystemExit("workflow state root must be a mapping")
    updated = start_requalification(state, baseline_commit=args.baseline_commit, activated_at=args.activated_at)
    if _stable_hash(state.get("bundle9_close")) != updated["bundle8r_requalification"]["historical_close_hashes"]["bundle9_close_sha256"]:
        raise SystemExit("bundle9 historical close changed unexpectedly")
    if _stable_hash(state.get("bundle10_close")) != updated["bundle8r_requalification"]["historical_close_hashes"]["bundle10_close_sha256"]:
        raise SystemExit("bundle10 historical close changed unexpectedly")

    if args.write:
        backup = source.with_suffix(source.suffix + ".pre_bundle8r")
        if not backup.exists():
            backup.write_bytes(source.read_bytes())
        destination = source
    else:
        destination = Path(args.output) if args.output else source.with_name("R5_bundle8r_forward_requalification_state_preview.yaml")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(yaml.safe_dump(updated, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"mode={'write' if args.write else 'preview'} output={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
