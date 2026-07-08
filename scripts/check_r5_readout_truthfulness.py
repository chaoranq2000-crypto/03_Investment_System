#!/usr/bin/env python3
"""Check R5 patch readouts for auditable command evidence."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml


DEFAULT_RULES = {
    "canonical_index_path": "config/r5_readout_canonical_index.yaml",
    "required_tokens": {
        "status": ["status"],
        "files_added": ["files_added", "files added"],
        "files_modified": ["files_modified", "files modified"],
        "commands_run": ["commands_run", "commands run"],
        "exit_codes": ["exit_code", "exit codes"],
        "stdout_or_stderr_summary": ["stdout_or_stderr_summary", "stdout or stderr", "stdout/stderr"],
        "known_todos": ["known_todos", "known todos"],
        "next_recommended_patch": ["next_recommended_patch", "next recommended patch"],
    },
    "pytest_summary_regex": r"\b\d+\s+(passed|failed|error|errors|skipped)\b",
    "critical_evidence_regex": r"(sha256|line[_ -]?count|before_lines|after_lines|checked=\d+|inventory_status)",
    "summary_only_phrases": ["pytest passed", "all tests passed", "validation ok"],
}


def load_rules(path: Path | None) -> dict[str, Any]:
    if path is None:
        return DEFAULT_RULES
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    merged = dict(DEFAULT_RULES)
    merged.update(data)
    return merged


def load_canonical_index(repo_root: Path, rules: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index_path_value = rules.get("canonical_index_path")
    if not index_path_value:
        return {}
    index_path = repo_root / str(index_path_value)
    if not index_path.exists():
        return {}
    data = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{index_path} must contain a mapping")
    entries = data.get("readouts", [])
    if not isinstance(entries, list):
        raise ValueError(f"{index_path} readouts must be a list")
    indexed: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or "path" not in entry:
            raise ValueError(f"{index_path} contains an invalid readout entry")
        indexed[str(entry["path"])] = entry
    return indexed


def _has_any(text_lower: str, tokens: list[str]) -> bool:
    return any(token.lower() in text_lower for token in tokens)


def check_readout(path: Path, rules: dict[str, Any]) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    text_lower = text.lower()
    issues: list[str] = []

    required_tokens = rules.get("required_tokens", {})
    for field, tokens in required_tokens.items():
        if not _has_any(text_lower, list(tokens)):
            issues.append(f"missing {field}")

    exit_code_present = bool(re.search(r"\b(?:exit_code|exit codes|first_exit_code|rerun_exit_code)\b", text_lower))
    if not exit_code_present:
        issues.append("missing explicit exit_code evidence")

    if "pytest" in text_lower and not re.search(str(rules["pytest_summary_regex"]), text_lower):
        issues.append("pytest mentioned without pytest result summary")

    if not re.search(str(rules["critical_evidence_regex"]), text_lower):
        issues.append("missing artifact hash, line count, checked count, or inventory status evidence")

    for phrase in rules.get("summary_only_phrases", []):
        if phrase.lower() in text_lower and not exit_code_present:
            issues.append(f"summary-only phrase without exit code: {phrase}")

    return {
        "path": str(path),
        "status": "fail" if issues else "pass",
        "issues": issues,
    }


def _relative_path(repo_root: Path, path: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def check_indexed_readout(path: Path, repo_root: Path, rules: dict[str, Any], index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rel_path = _relative_path(repo_root, path)
    entry = index.get(rel_path, {})
    canonical_status = str(entry.get("canonical_status", "canonical"))
    if canonical_status in {"legacy_noncanonical", "superseded"}:
        return {
            "path": str(path),
            "canonical_status": canonical_status,
            "status": "pass",
            "issues": [],
            "reason": entry.get("reason", ""),
            "replacement_or_supplement_path": entry.get("replacement_or_supplement_path"),
            "blocking_for_strict_smoke": bool(entry.get("blocking_for_strict_smoke", False)),
        }
    result = check_readout(path, rules)
    result["canonical_status"] = canonical_status
    result["reason"] = entry.get("reason", "")
    result["replacement_or_supplement_path"] = entry.get("replacement_or_supplement_path")
    result["blocking_for_strict_smoke"] = bool(entry.get("blocking_for_strict_smoke", True))
    return result


def check_glob(repo_root: Path, pattern: str, rules: dict[str, Any]) -> dict[str, Any]:
    paths = sorted(repo_root.glob(pattern))
    index = load_canonical_index(repo_root, rules)
    results = [check_indexed_readout(path, repo_root, rules, index) for path in paths if path.is_file()]
    failures = [
        result
        for result in results
        if result["status"] == "fail" and result.get("blocking_for_strict_smoke", True)
    ]
    return {
        "truthfulness_status": "fail" if failures else "pass",
        "checked": len(results),
        "failed": len(failures),
        "canonical_checked": sum(1 for result in results if result.get("canonical_status") == "canonical"),
        "legacy_noncanonical": sum(1 for result in results if result.get("canonical_status") == "legacy_noncanonical"),
        "superseded": sum(1 for result in results if result.get("canonical_status") == "superseded"),
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check R5 patch readout truthfulness evidence.")
    parser.add_argument("--glob", required=True, help="Glob relative to repo root.")
    parser.add_argument("--repo-root", default=".", type=Path)
    parser.add_argument("--rules", type=Path, help="Optional YAML rules file.")
    parser.add_argument("--json", type=Path, help="Optional JSON report path.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero if any readout fails.")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    rules = load_rules(args.rules)
    report = check_glob(repo_root, args.glob, rules)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        "truthfulness_status={status} checked={checked} failed={failed}".format(
            status=report["truthfulness_status"],
            checked=report["checked"],
            failed=report["failed"],
        )
    )
    for result in report["results"]:
        if result["status"] == "fail":
            print(f"{result['path']}: {'; '.join(result['issues'])}")

    if args.strict and report["truthfulness_status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
