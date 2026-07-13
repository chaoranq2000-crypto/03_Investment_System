"""Shared contracts for the R5 Bundle 10R Reader rebuild.

This module is intentionally dependency-light and deterministic. It does not
contain issuer-specific prose or facts.
"""

from __future__ import annotations

import copy
import hashlib
import re
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

DISPLAY_REF_RE = re.compile(r"\bE[1-9][0-9]*\b")
INTERNAL_ID_RE = re.compile(r"\b(?:ev_|metric_|claim_|gap_|todo_)[A-Za-z0-9_\-]+", re.I)
INTERNAL_PATH_RE = re.compile(r"(?:reports/workflow_runs/|data/raw/|registry/|workflow_state\.yaml)", re.I)
MACHINE_TOKEN_RE = re.compile(r"\b(?:TODO|MISSING|UNREVIEWED|READY_FOR|NEEDS_FIX)\b", re.I)
ACTION_RE = re.compile(
    r"(?:买入|卖出|持有评级|加仓|减仓|仓位|目标价|止损|建仓|take\s+profit|\bbuy\b|\bsell\b|position\s+sizing|target\s+price)",
    re.I,
)
FABRICATED_REVIEW_RE = re.compile(r"(?:人工审核已通过|human\s+review\s+accepted)", re.I)
NUMBER_RE = re.compile(r"(?:\d|[<>≤≥±%])")

DEFAULT_REQUIRED_SECTIONS = (
    "executive_summary",
    "company_context_and_scope",
    "financial_quality",
    "segment_economics",
    "industry_and_competition",
    "forecast_and_scenarios",
    "valuation_and_market_implied_expectations",
    "market_technical_sentiment_and_events",
    "risks_and_falsification",
    "conclusion_and_watchlist",
)
DEFAULT_CORE_SECTIONS = (
    "financial_quality",
    "segment_economics",
    "industry_and_competition",
    "forecast_and_scenarios",
    "valuation_and_market_implied_expectations",
    "risks_and_falsification",
    "conclusion_and_watchlist",
)
DEFAULT_ANALYSIS_FIELDS = (
    "judgment",
    "facts",
    "causal_mechanism",
    "economic_implications",
    "counterevidence",
    "uncertainty",
    "watchpoints",
    "references",
)


def load_yaml(path: str | Path) -> dict[str, Any]:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected YAML mapping: {path}")
    return value


def dump_yaml(value: Mapping[str, Any], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(dict(value), allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
        newline="\n",
    )


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_sha256(value: Any) -> str:
    encoded = yaml.safe_dump(value, allow_unicode=True, sort_keys=True, width=120).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_iso_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError(f"expected ISO date string, received {value!r}")
    return date.fromisoformat(value[:10])


def extract_display_refs(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return set(DISPLAY_REF_RE.findall(value))
    if isinstance(value, Mapping):
        out: set[str] = set()
        for item in value.values():
            out.update(extract_display_refs(item))
        return out
    if isinstance(value, Iterable):
        out: set[str] = set()
        for item in value:
            out.update(extract_display_refs(item))
        return out
    return set()


def han_count(text: str) -> int:
    return len(re.findall(r"[\u3400-\u9fff]", text))


def _issue(code: str, message: str, severity: str = "critical", **context: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"code": code, "severity": severity, "message": message}
    if context:
        item["context"] = context
    return item


def validate_model_generation_lock(
    model_lock: Mapping[str, Any],
    binding: Mapping[str, Any],
    *,
    repo_root: str | Path | None = None,
    verify_artifact_hashes: bool = False,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    checks = (
        ("generation_id", "expected_model_generation_id", "model_generation_id_mismatch"),
        ("aggregate_sha256", "expected_model_aggregate_sha256", "model_aggregate_hash_mismatch"),
        ("input_evidence_generation_id", "expected_evidence_generation_id", "evidence_generation_id_mismatch"),
    )
    for lock_key, binding_key, code in checks:
        actual = model_lock.get(lock_key)
        expected = binding.get(binding_key)
        if actual != expected:
            issues.append(_issue(code, f"{lock_key}: expected={expected!r}; actual={actual!r}"))

    if int(model_lock.get("missing_artifact_count", -1)) != 0:
        issues.append(_issue("model_lock_has_missing_artifacts", f"missing={model_lock.get('missing_artifact_count')}"))
    artifacts = model_lock.get("artifacts") or []
    if not isinstance(artifacts, list) or not artifacts:
        issues.append(_issue("model_lock_artifact_list_missing", "locked artifact list is empty"))
    if model_lock.get("artifact_count") != len(artifacts):
        issues.append(_issue("model_lock_artifact_count_mismatch", f"declared={model_lock.get('artifact_count')}; actual={len(artifacts)}"))
    required_consumer = binding.get("required_downstream_consumer")
    consumers = model_lock.get("downstream_consumers") or []
    if required_consumer and required_consumer not in consumers:
        issues.append(_issue("bundle10r_not_registered_as_downstream_consumer", str(required_consumer)))

    verified = 0
    if verify_artifact_hashes:
        if repo_root is None:
            issues.append(_issue("repo_root_required_for_hash_verification", "--verify-artifact-hashes requires a repository root"))
        else:
            root = Path(repo_root)
            for artifact in artifacts:
                rel = artifact.get("path")
                expected = artifact.get("sha256")
                if not rel or not expected:
                    issues.append(_issue("invalid_locked_artifact_record", repr(artifact)))
                    continue
                path = root / rel
                if not path.is_file():
                    issues.append(_issue("locked_model_artifact_missing", rel))
                    continue
                actual = sha256_file(path)
                if actual != expected:
                    issues.append(_issue("locked_model_artifact_hash_mismatch", rel, expected=expected, actual=actual))
                else:
                    verified += 1

    return {
        "artifact_type": "R5_bundle10r_generation_binding_validation",
        "schema_version": 1,
        "decision": "pass" if not issues else "needs_fix",
        "issue_count": len(issues),
        "issues": issues,
        "model_generation_id": model_lock.get("generation_id"),
        "model_aggregate_sha256": model_lock.get("aggregate_sha256"),
        "artifact_count": len(artifacts),
        "verified_artifact_hash_count": verified,
    }


def section_index(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    sections = payload.get("sections") or []
    out: dict[str, dict[str, Any]] = {}
    for raw in sections:
        if not isinstance(raw, dict):
            continue
        section_id = raw.get("section_id")
        if isinstance(section_id, str):
            out[section_id] = raw
    return out


def _list_count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _watchpoint_is_quantified(item: Any) -> bool:
    if isinstance(item, str):
        return bool(NUMBER_RE.search(item))
    if isinstance(item, Mapping):
        trigger = str(item.get("trigger") or item.get("condition") or "")
        return bool(NUMBER_RE.search(trigger))
    return False


def validate_analysis_section(
    section: Mapping[str, Any],
    *,
    core: bool,
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    contract = contract or {}
    minimums = contract.get("minimums") or {}
    required_fields = contract.get("required_analysis_fields") or list(DEFAULT_ANALYSIS_FIELDS)
    issues: list[dict[str, Any]] = []
    section_id = str(section.get("section_id") or "unknown")

    for field in required_fields:
        value = section.get(field)
        if value is None or value == "" or value == []:
            issues.append(_issue("analysis_field_missing", f"{section_id}.{field}", severity="high"))

    counts = {
        "facts": _list_count(section.get("facts")),
        "causal_mechanism": _list_count(section.get("causal_mechanism")),
        "economic_implications": _list_count(section.get("economic_implications")),
        "counterevidence": _list_count(section.get("counterevidence")),
        "uncertainty": _list_count(section.get("uncertainty")),
        "watchpoints": _list_count(section.get("watchpoints")),
        "references": _list_count(section.get("references")),
    }
    expected = {
        "facts": int(minimums.get("facts_per_section", 2)),
        "causal_mechanism": int(minimums.get("causal_mechanisms_per_section", 1)),
        "economic_implications": int(minimums.get("implications_per_section", 1)),
        "counterevidence": int(minimums.get("counterevidence_per_section", 1)),
        "uncertainty": int(minimums.get("uncertainties_per_section", 1)),
        "watchpoints": int(minimums.get("watchpoints_per_section", 2)),
        "references": 1,
    }
    for field, minimum in expected.items():
        if counts[field] < minimum:
            issues.append(_issue("analysis_field_below_minimum", f"{section_id}.{field}: {counts[field]} < {minimum}", severity="high"))

    quantified = sum(_watchpoint_is_quantified(x) for x in section.get("watchpoints") or [])
    if core and quantified < int(minimums.get("quantified_watchpoints_per_core_section", 1)):
        issues.append(_issue("core_section_lacks_quantified_watchpoint", section_id, severity="high"))

    refs = set(section.get("references") or [])
    embedded = extract_display_refs(section)
    if not refs:
        issues.append(_issue("section_has_no_display_references", section_id, severity="high"))
    if embedded and not embedded.issubset(refs):
        issues.append(_issue("section_reference_declaration_incomplete", section_id, severity="high", undeclared=sorted(embedded - refs)))

    return {
        "section_id": section_id,
        "core": core,
        "decision": "pass" if not issues else "needs_fix",
        "issues": issues,
        "counts": counts,
        "quantified_watchpoint_count": quantified,
    }


def validate_payload_structure(
    payload: Mapping[str, Any],
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    contract = contract or {}
    required = tuple(contract.get("required_sections") or DEFAULT_REQUIRED_SECTIONS)
    core = set(contract.get("core_sections") or DEFAULT_CORE_SECTIONS)
    by_id = section_index(payload)
    issues: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {}

    duplicates: set[str] = set()
    seen: set[str] = set()
    for raw in payload.get("sections") or []:
        section_id = raw.get("section_id") if isinstance(raw, Mapping) else None
        if section_id in seen:
            duplicates.add(str(section_id))
        seen.add(section_id)
    if duplicates:
        issues.append(_issue("duplicate_reader_sections", ",".join(sorted(duplicates))))

    for section_id in required:
        section = by_id.get(section_id)
        if section is None:
            issues.append(_issue("required_reader_section_missing", section_id, severity="high"))
            continue
        diag = validate_analysis_section(section, core=section_id in core, contract=contract)
        diagnostics[section_id] = diag
        issues.extend(diag["issues"])

    company = payload.get("company") or {}
    for key in ("name", "ticker", "as_of_date"):
        if not company.get(key):
            issues.append(_issue("company_metadata_missing", key, severity="high"))
    try:
        parse_iso_date(company.get("as_of_date"))
    except Exception as exc:  # noqa: BLE001
        issues.append(_issue("invalid_as_of_date", str(exc), severity="high"))

    if not payload.get("input_model_generation_id"):
        issues.append(_issue("payload_model_generation_missing", "input_model_generation_id", severity="high"))
    if not payload.get("input_model_aggregate_sha256"):
        issues.append(_issue("payload_model_aggregate_missing", "input_model_aggregate_sha256", severity="high"))

    return {
        "decision": "pass" if not issues else "needs_fix",
        "issue_count": len(issues),
        "issues": issues,
        "section_diagnostics": diagnostics,
        "required_sections": list(required),
        "core_sections": sorted(core),
    }


def scan_main_report(report: str) -> list[dict[str, Any]]:
    checks = (
        ("internal_evidence_id_in_main_report", INTERNAL_ID_RE),
        ("internal_path_in_main_report", INTERNAL_PATH_RE),
        ("machine_token_in_main_report", MACHINE_TOKEN_RE),
        ("direct_action_language_in_main_report", ACTION_RE),
        ("fabricated_human_review_status", FABRICATED_REVIEW_RE),
    )
    issues: list[dict[str, Any]] = []
    for code, pattern in checks:
        match = pattern.search(report)
        if match:
            issues.append(_issue(code, match.group(0)[:120]))
    return issues


def clone_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(dict(value))
