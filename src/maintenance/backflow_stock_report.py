from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import yaml


def write_backflow_decision(
    *,
    run_dir: Path,
    status: str = "no_global_exposure_update_with_todos",
    reason: str = "Reviewed claims support product exposure, but revenue/profit exposure remains missing.",
) -> dict[str, object]:
    payload = {
        "run_id": run_dir.name,
        "backflow_decision": status,
        "exposure_registry_update": "not_updated",
        "claims_registry_update": "workflow_local_reviewed",
        "metrics_registry_update": "workflow_local_reviewed",
        "reason": reason,
        "next_refresh_tasks": [
            "补充分业务收入/毛利率表格证据",
            "补充订单/客户/产能公告证据",
        ],
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "backflow_decision.yaml").write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write explicit stock report backflow decision.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--status", default="no_global_exposure_update_with_todos")
    parser.add_argument("--reason", default="Reviewed claims support product exposure, but revenue/profit exposure remains missing.")
    args = parser.parse_args(argv)
    print(write_backflow_decision(run_dir=Path(args.run_dir), status=args.status, reason=args.reason))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
