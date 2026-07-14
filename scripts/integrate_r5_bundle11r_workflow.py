from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

BEGIN = "<!-- BEGIN R5_BUNDLE11R_RUNTIME_INTEGRATION -->"
END = "<!-- END R5_BUNDLE11R_RUNTIME_INTEGRATION -->"

BLOCKS = {
    "docs/workflows/RESEARCH_WORKFLOW.md": """
## R5 Bundle 11R operating-research inner loop

This extension preserves the global T0–T10 workflow. Inside stock-deep-dive report production, execute the following non-optional loop before Reader rendering:

1. assign one or more economic archetypes to every material business line;
2. generate a research-question matrix from required operating drivers;
3. acquire or explicitly bound each thesis-critical driver;
4. calculate segment economics and reconcile them to consolidated statements;
5. qualify peers by operating definition before using peer multiples;
6. run the semantic research gate;
7. route every failed issue to its owning stage and skill;
8. render only after high/critical research blockers are cleared or visibly retained as a non-sample-quality limitation.

The runtime entrypoint is `scripts/run_r5_bundle11r_runtime.py`. Automation never sets human review, sample quality, or P2 to true.
""",
    "docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md": """
## R5 Bundle 11R issue backflow contract

The orchestrator consumes `r5_bundle11r_backflow_plan` and must set `next_stage` and `required_next_skill` from the highest-severity blocking task. Typical routes are:

- missing operating drivers or excessive proxy share → `RP2_operating_evidence` / `evidence-ingest`;
- broken operating equation or missing model link → `RP4_operating_model` / `stock-deep-dive`;
- ineligible peer set → `RP5_peer_valuation` / `compare-stocks`;
- generic analysis or non-falsifiable watchpoints → `RP6_analysis_synthesis` / `stock-deep-dive`;
- duplicated narrative or flat emphasis → `RP7_report_planning` / `memo-writer`;
- direct trading language → `RP8_quality_review` / `quality-review`;
- generation mismatch → `T0_orchestration` / `research-orchestrator`.

A passing structure score cannot offset a high/critical research blocker.
""",
    ".agents/skills/research-orchestrator/SKILL.md": """
## Bundle 11R runtime routing

For a stock research workflow that has reached the post-10R research-depth stage, invoke `scripts/run_r5_bundle11r_runtime.py` with the business-line driver plan, evidence status, peer pack, and semantic payload. Persist its question matrix, driver pack, peer eligibility, semantic scorecard, and backflow plan under the workflow-run directory. Route the next action from `backflow_plan.tasks`; do not replace a failed operating-research gate by asking the Writer to add prose.
""",
    ".agents/skills/stock-deep-dive/SKILL.md": """
## Bundle 11R business-line operating contract

Before forecasting, assign each material business line an economic archetype from `config/economic_archetype_registry.yaml`. A company may use several archetypes. Each thesis-critical assumption must carry source, unit, period, scenario, confidence, overlap treatment, and financial-statement mapping. A broad revenue-growth proxy is allowed only when labelled, bounded, and below the configured company-level proxy-share ceiling.
""",
    ".agents/skills/quality-review/SKILL.md": """
## Bundle 11R semantic research gate

Review both truthfulness and decision usefulness. Fail a candidate when a core section lacks issuer-specific metrics, an economic section lacks a model link, peer multiples use an ineligible peer set, watchpoints are not falsifiable, the same insight is repeated across sections, proxy share exceeds the contract, or direct trading/target-price language appears. Extra length, citations, technical indicators, or unrelated passing sections cannot compensate for these failures.
""",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def integrate(repo_root: Path, *, write: bool, backup_root: Path | None = None) -> dict[str, Any]:
    changes: list[dict[str, Any]] = []
    backups: list[tuple[Path, Path]] = []
    try:
        for relative, body in BLOCKS.items():
            target = repo_root / relative
            if not target.is_file():
                raise FileNotFoundError(target)
            before = target.read_text(encoding="utf-8")
            before_hash = sha256(target)
            if BEGIN in before and END in before:
                action = "already_integrated"
                after = before
            else:
                block = f"\n\n{BEGIN}\n{body.strip()}\n{END}\n"
                after = before.rstrip() + block
                action = "would_append" if not write else "appended"
                if write:
                    if backup_root is not None:
                        backup = backup_root / relative
                        backup.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(target, backup)
                        backups.append((target, backup))
                    target.write_text(after, encoding="utf-8")
            after_hash = hashlib.sha256(after.encode("utf-8")).hexdigest()
            changes.append({"path": relative, "action": action, "before_sha256": before_hash, "after_sha256": after_hash})
    except Exception:
        for target, backup in reversed(backups):
            shutil.copy2(backup, target)
        raise
    return {"schema_version": 1, "artifact_type": "r5_bundle11r_workflow_integration", "write": write, "changes": changes}


def main() -> int:
    parser = argparse.ArgumentParser(description="Idempotently connect Bundle 11R runtime to existing workflow and skills")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--backup-root")
    parser.add_argument("--output-json")
    args = parser.parse_args()
    result = integrate(
        Path(args.repo_root).resolve(),
        write=args.write,
        backup_root=Path(args.backup_root).resolve() if args.backup_root else None,
    )
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
