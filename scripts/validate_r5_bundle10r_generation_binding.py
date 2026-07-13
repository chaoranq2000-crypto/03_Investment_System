#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from src.report.r5_bundle10r_contracts import dump_yaml, load_yaml, validate_model_generation_lock


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Bundle 10R model-generation binding")
    parser.add_argument("--binding", required=True)
    parser.add_argument("--model-lock", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--verify-artifact-hashes", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()

    result = validate_model_generation_lock(
        load_yaml(args.model_lock),
        load_yaml(args.binding),
        repo_root=Path(args.repo_root),
        verify_artifact_hashes=args.verify_artifact_hashes,
    )
    if args.output:
        dump_yaml(result, args.output)
    print(f"decision={result['decision']} issues={result['issue_count']} verified={result['verified_artifact_hash_count']}")
    return 0 if result["decision"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
