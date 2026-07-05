#!/usr/bin/env python3
"""Validate P1.6 stock skill consolidation into stock-deep-dive."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
SKILLS = ROOT / ".agents" / "skills"
SDD = SKILLS / "stock-deep-dive"
OLD_SKILL_NAMES = ["stock-" + "research-analyst", "stock-" + "report-writer", "stock-" + "report-write"]


def fail(message: str, errors: list[str]) -> None:
    errors.append(message)


def main() -> int:
    errors: list[str] = []

    for name in OLD_SKILL_NAMES:
        if (SKILLS / name).exists():
            fail(f"legacy skill directory still exists: {SKILLS / name}", errors)

    required_paths = [
        SDD / "references" / "analysis_pack_contract.md",
        SDD / "references" / "business_breakdown_contract.md",
        SDD / "references" / "forecast_valuation_contract.md",
        SDD / "references" / "market_sentiment_event_contract.md",
        SDD / "references" / "report_style_guide.md",
        SDD / "assets" / "stock_analysis_pack_template.yaml",
        SDD / "assets" / "stock_deep_dive_report_template.md",
    ]
    for path in required_paths:
        if not path.exists():
            fail(f"required merged artifact missing: {path}", errors)

    config_path = ROOT / ".codex" / "config.toml"
    if config_path.exists():
        config = config_path.read_text(encoding="utf-8")
        for name in OLD_SKILL_NAMES:
            if name in config:
                fail(f"legacy skill name remains in .codex/config.toml: {name}", errors)
        if ".agents/skills/stock-deep-dive" not in config:
            fail("stock-deep-dive path is not present in .codex/config.toml", errors)
    else:
        fail(".codex/config.toml missing", errors)

    skill_path = SDD / "SKILL.md"
    if not skill_path.exists():
        fail("stock-deep-dive/SKILL.md missing", errors)
    else:
        skill = skill_path.read_text(encoding="utf-8")
        required_phrases = [
            "stock_analysis_pack",
            "segment_exposure",
            "backflow_decision",
            "publishable_ready_with_disclosure_todos",
            "MISSING_DISCLOSURE",
            "no buy/sell/hold",
            "product_line_clue",
            "revenue_pct",
            "profit_pct",
        ]
        for phrase in required_phrases:
            if phrase not in skill:
                fail(f"required phrase missing from stock-deep-dive/SKILL.md: {phrase}", errors)

    active_docs = [
        ROOT / "README.md",
        ROOT / "docs" / "workflows" / "RESEARCH_WORKFLOW.md",
        ROOT / "docs" / "workflows" / "WORKFLOW_ORCHESTRATION_SPEC.md",
        ROOT / ".agents" / "skills" / "research-orchestrator" / "references" / "skill_routing_matrix.md",
        ROOT / ".agents" / "skills" / "research-orchestrator" / "SKILL.md",
    ]
    for path in active_docs:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for name in OLD_SKILL_NAMES:
            if name in text:
                fail(f"legacy skill name remains in active doc {path}: {name}", errors)

    if errors:
        print("stock-deep-dive merge validation FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    print("stock-deep-dive merge validation PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
