#!/usr/bin/env python3
"""Skill-local wrapper for the Bundle 8 analysis-pack validator."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pack")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[4]))
    parser.add_argument("--config", default="config/r5_bundle8_research_depth.yaml")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from src.research.r5_analysis_engine import validate_analysis_pack

    pack_path = Path(args.pack)
    if not pack_path.is_absolute():
        pack_path = root / pack_path
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = root / config_path
    pack = yaml.safe_load(pack_path.read_text(encoding="utf-8")) or {}
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    result = validate_analysis_pack(pack, config)
    print(
        "analysis_pack_v2 "
        f"decision={result['decision']} complete={result['stats']['complete_units']} "
        f"errors={len(result['errors'])}"
    )
    for error in result["errors"]:
        print(error)
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
