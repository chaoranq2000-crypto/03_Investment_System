#!/usr/bin/env python3
"""Render the highest gate-allowed R5 reviewed-input output."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import yaml

WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
FORBIDDEN = re.compile(
    r"买入|卖出|持有|仓位|目标价|保证收益|buy\s+rating|sell\s+rating|hold\s+rating|position\s+sizing",
    re.IGNORECASE,
)


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_writer(repo_root: Path):
    writer_path = repo_root / "src/report/stock_report_writer.py"
    spec = importlib.util.spec_from_file_location("stock_report_writer", writer_path)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load writer from {writer_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_gap_count(pack: dict[str, Any]) -> int:
    gaps = pack.get("source_gap_register")
    return len(gaps) if isinstance(gaps, list) else 0


def _rendered_type(gate: dict[str, Any], promotion: dict[str, Any], staging: dict[str, Any]) -> str:
    if gate.get("sample_quality_report_allowed") is True or promotion.get("sample_quality_report_allowed") is True:
        return "sample_quality_candidate_blocked_in_patch54"
    if gate.get("reviewed_input_pilot_allowed") is True and staging.get("allowed_report_level") == "reviewed_input_research_draft":
        return "reviewed_input_research_draft"
    return "source_gapped_research_draft"


def render_output(
    *,
    repo_root: Path,
    workflow_id: str,
    result_path: Path,
    output_path: Path,
    pack_path: Path | None = None,
    gate_path: Path | None = None,
    staging_path: Path | None = None,
    promotion_path: Path | None = None,
    scorecard_path: Path | None = None,
) -> dict[str, Any]:
    run_dir = repo_root / "reports/workflow_runs" / workflow_id
    pack_path = pack_path or run_dir / "R5_stock_research_pack_source_gapped.yaml"
    gate_path = gate_path or repo_root / "reports/p1_6/r5_reviewed_input_pilot_gate_result.json"
    staging_path = staging_path or run_dir / "R5_reviewed_input_staging_result.yaml"
    promotion_path = promotion_path or run_dir / "R5_reviewed_input_registry_promotion_result.yaml"
    scorecard_path = scorecard_path or repo_root / ".agents/skills/quality-review/assets/r5_quality_scorecard.example.yaml"

    pack = load_yaml(pack_path)
    gate = load_json(gate_path)
    staging = load_yaml(staging_path)
    promotion = load_yaml(promotion_path)
    writer = load_writer(repo_root)
    desired_type = _rendered_type(gate, promotion, staging)

    if desired_type == "reviewed_input_research_draft":
        render_result = writer.render_reviewed_input_research_draft(
            pack_path=pack_path,
            scorecard_path=scorecard_path,
            promotion_path=promotion_path,
            output_path=output_path,
        )
    else:
        render_result = writer.render_source_gapped_research_draft(pack_path=pack_path, output_path=output_path)
        desired_type = "source_gapped_research_draft"

    text = output_path.read_text(encoding="utf-8")
    forbidden_found = sorted(set(match.group(0) for match in FORBIDDEN.finditer(text)))
    if forbidden_found:
        raise ValueError("forbidden direct trading language generated: " + ", ".join(forbidden_found))
    if gate.get("sample_quality_report_allowed") is not True and "sample_quality_candidate" in text:
        raise ValueError("sample-quality marker generated while sample-quality is not allowed")

    remaining_todos = list(promotion.get("remaining_todos", staging.get("remaining_todos") or []))
    required_markers = {
        "source_gap_appendix": "Source Gap Appendix" in text,
        "open_questions": "Open Questions" in text,
        "no_advice_boundary": "no_advice_boundary" in text,
        "remaining_todos": all(str(token) in text for token in remaining_todos),
    }
    result = {
        "artifact_type": "R5_reviewed_input_render_result",
        "schema_version": "r5_reviewed_input_render_result_v0.1",
        "workflow_id": workflow_id,
        "input_gate_state": gate.get("current_r5_state"),
        "promotion_level": staging.get("allowed_report_level", promotion.get("allowed_report_level")),
        "promotion_status": promotion.get("promotion_status"),
        "rendered_output_type": desired_type,
        "rendered_output_path": str(output_path),
        "input_artifacts": {
            "pack": {"path": str(pack_path), "sha256": _sha256(pack_path)},
            "gate": {"path": str(gate_path), "sha256": _sha256(gate_path)},
            "staging": {"path": str(staging_path), "sha256": _sha256(staging_path)},
            "promotion": {"path": str(promotion_path), "sha256": _sha256(promotion_path)},
            "scorecard": {"path": str(scorecard_path), "sha256": _sha256(scorecard_path)},
        },
        "sample_quality_report_allowed": bool(gate.get("sample_quality_report_allowed") and promotion.get("sample_quality_report_allowed")),
        "p2_allowed": bool(gate.get("p2_allowed") and promotion.get("p2_allowed")),
        "source_gap_count": _source_gap_count(pack),
        "forbidden_language_check": {
            "status": "pass",
            "forbidden_found": forbidden_found,
        },
        "required_markers": required_markers,
        "writer_result": render_result,
        "remaining_todos": remaining_todos,
        "notes": [
            "Blocked gate renders source_gapped_research_draft only.",
            "Source Gap Appendix, Open Questions, no-advice boundary, and remaining TODOs are preserved.",
        ],
    }
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render R5 reviewed-input output according to gates.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--workflow-id", default=WORKFLOW_ID)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/workflow_runs") / WORKFLOW_ID / "R5_stock_research_note_reviewed_input_draft.md",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("reports/workflow_runs") / WORKFLOW_ID / "R5_reviewed_input_render_result.yaml",
    )
    parser.add_argument("--pack", type=Path, help="Explicit research-pack path.")
    parser.add_argument("--gate", type=Path, help="Explicit pilot-gate result path.")
    parser.add_argument("--staging", type=Path, help="Explicit reviewed-input staging path.")
    parser.add_argument("--promotion", type=Path, help="Explicit registry-promotion result path.")
    parser.add_argument("--scorecard", type=Path, help="Explicit quality-scorecard path.")
    args = parser.parse_args(argv)

    result = render_output(
        repo_root=args.repo_root.resolve(),
        workflow_id=args.workflow_id,
        result_path=args.json,
        output_path=args.output,
        pack_path=args.pack,
        gate_path=args.gate,
        staging_path=args.staging,
        promotion_path=args.promotion,
        scorecard_path=args.scorecard,
    )
    print(
        "r5_reviewed_input_render_type={rendered} sample_quality_allowed={sample} p2_allowed={p2} source_gap_count={gaps} forbidden_language_check={forbidden}".format(
            rendered=result["rendered_output_type"],
            sample=str(result["sample_quality_report_allowed"]).lower(),
            p2=str(result["p2_allowed"]).lower(),
            gaps=result["source_gap_count"],
            forbidden=result["forbidden_language_check"]["status"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
