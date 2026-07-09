#!/usr/bin/env python3
"""Compose an R5 report note with reviewed-input gate degradation."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

import yaml

BASE_COMPOSER_PATH = Path(".agents/skills/stock-deep-dive/scripts/compose_r5_report_from_pack.py")


def _load_base_composer():
    spec = importlib.util.spec_from_file_location("stock_deep_dive_r5_composer", BASE_COMPOSER_PATH)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load base composer from {BASE_COMPOSER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_yaml(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def determine_allowed_report_level(
    *,
    gate_result: dict[str, Any],
    market_peer_registry: dict[str, Any],
    forecast_registry: dict[str, Any],
    evidence_ledger: dict[str, Any],
) -> str:
    if gate_result.get("sample_quality_report_allowed") is True or gate_result.get("p2_allowed") is True:
        return "blocked"
    if gate_result.get("source_gapped_real_sample_pilot_allowed") is True:
        if market_peer_registry.get("review_status") in {"reviewed", "explicitly_degraded_but_reviewed"} and forecast_registry.get("review_status") in {
            "reviewed",
            "explicitly_degraded_but_reviewed",
        }:
            return "source_gapped_pilot_note"
    if any(
        registry.get("review_status") == "pending"
        for registry in [market_peer_registry, forecast_registry, evidence_ledger]
    ):
        return "research_draft"
    return "source_gapped_research_draft"


def compose_with_gate(
    *,
    pack_path: Path,
    output_path: Path,
    gate_path: Path | None = None,
    market_peer_registry_path: Path | None = None,
    forecast_registry_path: Path | None = None,
    evidence_ledger_path: Path | None = None,
) -> dict[str, Any]:
    base = _load_base_composer()
    pack = base.load_pack(pack_path)
    gate = load_json(gate_path)
    market_peer = load_yaml(market_peer_registry_path)
    forecast = load_yaml(forecast_registry_path)
    ledger = load_yaml(evidence_ledger_path)
    allowed_level = determine_allowed_report_level(
        gate_result=gate,
        market_peer_registry=market_peer,
        forecast_registry=forecast,
        evidence_ledger=ledger,
    )
    note = base.compose_note(pack)
    prefix = "\n".join(
        [
            "# R5 Composer Gate",
            "",
            f"- allowed_report_level: {allowed_level}",
            "- sample_quality_report_allowed: false",
            "- p2_allowed: false",
            "- reviewed_input_gate: preserve TODO and Source Gap Appendix",
            "",
        ]
    )
    text = prefix + note
    for phrase in ["建议买入", "建议卖出", "持有评级", "仓位建议", "目标价", "保证收益"]:
        if phrase in text:
            raise ValueError(f"forbidden trading phrase generated: {phrase}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    return {
        "output_path": str(output_path),
        "allowed_report_level": allowed_level,
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compose an R5 note with reviewed-input gate degradation.")
    parser.add_argument("pack", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--gate", type=Path)
    parser.add_argument("--market-peer-registry", type=Path)
    parser.add_argument("--forecast-registry", type=Path)
    parser.add_argument("--evidence-ledger", type=Path)
    args = parser.parse_args(argv)
    result = compose_with_gate(
        pack_path=args.pack,
        output_path=args.output,
        gate_path=args.gate,
        market_peer_registry_path=args.market_peer_registry,
        forecast_registry_path=args.forecast_registry,
        evidence_ledger_path=args.evidence_ledger,
    )
    print(
        "compose_r5_report allowed_report_level={level} sample_quality_allowed=false p2_allowed=false output={output}".format(
            level=result["allowed_report_level"],
            output=result["output_path"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
