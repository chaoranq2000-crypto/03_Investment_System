"""Non-compensating Bundle 10R Reader quality gate."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date
from typing import Any, Iterable, Mapping

from src.report.r5_bundle10r_contracts import (
    DEFAULT_CORE_SECTIONS,
    DEFAULT_REQUIRED_SECTIONS,
    extract_display_refs,
    han_count,
    parse_iso_date,
    scan_main_report,
    section_index,
    validate_analysis_section,
)


def _issue(code: str, message: str, route: str, severity: str = "high") -> dict[str, Any]:
    return {"code": code, "message": message, "route": route, "severity": severity}


def _dedupe(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (item["code"], item["message"])
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _claim_boundary_issues(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for claim in payload.get("claims") or []:
        if not isinstance(claim, Mapping):
            continue
        topic = claim.get("topic")
        claim_type = claim.get("claim_type")
        if topic == "consensus" and claim_type not in {"analyst_view", "estimate"}:
            issues.append(_issue("consensus_claim_type_inflated", str(claim_type), "claim_boundary"))
        if topic == "liquid_cooling_standalone_economics":
            if claim_type not in {"estimate", "analytical_view", "unknown"}:
                issues.append(_issue("liquid_cooling_claim_inflated_to_fact", str(claim_type), "claim_boundary"))
            if claim.get("additivity") != "non_additive":
                issues.append(_issue("liquid_cooling_double_counting_risk", str(claim.get("additivity")), "claim_boundary"))
        if topic == "peer_comparison" and str(claim.get("peer_confidence") or "").lower() in {"low", "low_confidence_peer_set"}:
            if claim.get("ranking_performed") is True:
                issues.append(_issue("low_confidence_peer_ranking_performed", str(claim.get("claim_id")), "valuation"))
    return issues


def _market_event_issues(payload: Mapping[str, Any], market_section: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not market_section:
        return [_issue("market_context_section_missing", "market section absent", "market")]
    technical = market_section.get("technical_context") or {}
    sentiment = market_section.get("sentiment_context") or {}
    if technical.get("status") != "reviewed" or not technical.get("as_of_date"):
        issues.append(_issue("reviewed_technical_context_missing", "technical context must be reviewed and dated", "market"))
    if sentiment.get("status") != "reviewed" or not sentiment.get("as_of_date"):
        issues.append(_issue("reviewed_sentiment_context_missing", "sentiment context must be reviewed and dated", "market"))

    try:
        as_of = parse_iso_date((payload.get("company") or {}).get("as_of_date"))
    except Exception as exc:  # noqa: BLE001
        return issues + [_issue("invalid_reader_as_of_date", str(exc), "market")]
    events = market_section.get("events") or []
    future_count = 0
    for event in events:
        if not isinstance(event, Mapping):
            continue
        try:
            event_date = parse_iso_date(event.get("date"))
        except Exception as exc:  # noqa: BLE001
            issues.append(_issue("invalid_event_date", str(exc), "market"))
            continue
        status = event.get("status")
        if status == "future":
            future_count += 1
            if event_date < as_of:
                issues.append(_issue("past_event_presented_as_future", str(event.get("date")), "market"))
            required = ("impact_path", "verification_metric", "counterevidence_condition", "refs")
            missing = [key for key in required if not event.get(key)]
            if missing:
                issues.append(_issue("future_event_chain_incomplete", f"{event.get('date')}: {','.join(missing)}", "market"))
    if future_count == 0:
        issues.append(_issue("future_event_chain_missing", "no future event with a complete verification chain", "market"))
    return issues


def _source_diagnostics(appendix: Mapping[str, Any]) -> dict[str, Any]:
    records = appendix.get("records") or []
    categories = Counter(str(item.get("source_category") or "unknown") for item in records if isinstance(item, Mapping))
    independent = {
        str(item.get("underlying_source_id"))
        for item in records
        if isinstance(item, Mapping) and item.get("independent") is True and item.get("underlying_source_id")
    }
    peer_sources = {
        str(item.get("underlying_source_id"))
        for item in records
        if isinstance(item, Mapping) and item.get("source_category") == "peer" and item.get("underlying_source_id")
    }
    return {
        "category_counts": dict(sorted(categories.items())),
        "independent_source_count": len(independent),
        "peer_source_count": len(peer_sources),
        "underlying_source_count": len({str(item.get("underlying_source_id")) for item in records if isinstance(item, Mapping)}),
    }


def _extract_main_narrative(report: str) -> str:
    """Return reader-facing H2 content, excluding metadata and audit tail notes."""
    match = re.search(r"^##\s+", report, re.M)
    if not match:
        return ""
    body = report[match.start():]
    body = re.split(r"^---\s*$", body, maxsplit=1, flags=re.M)[0]
    return re.sub(r"```.*?```", "", body, flags=re.S)


def _split_h2_sections(body: str) -> list[str]:
    starts = list(re.finditer(r"^##\s+.*$", body, re.M))
    return [body[item.start() : starts[index + 1].start() if index + 1 < len(starts) else len(body)] for index, item in enumerate(starts)]


def _narrative_paragraphs(body: str) -> list[str]:
    paragraphs: list[str] = []
    for block in re.split(r"\n\s*\n", body):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if any(line.startswith("|") for line in lines):
            continue
        first = lines[0]
        if first.startswith(("#", "- ", "* ", ">")):
            continue
        paragraphs.append(" ".join(lines))
    return paragraphs


def _normalize_narrative_block(text: str) -> str:
    text = re.sub(r"\[E[1-9][0-9]*\]", "", text)
    return "".join(re.findall(r"[\u3400-\u9fff]", text))


def _narrative_style_diagnostics(
    report: str,
    payload: Mapping[str, Any],
    quality_contract: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    schema_version = str(payload.get("schema_version") or "")
    config = quality_contract.get("narrative_quality")
    if schema_version != "v5":
        return {"enforced": False, "report_schema_version": schema_version}, [], False
    if not isinstance(config, Mapping) or schema_version not in set(config.get("applies_to_report_schema_versions") or []):
        issue = _issue(
            "reader_narrative_gate_config_missing",
            f"report schema {schema_version} requires an explicit narrative_quality policy",
            "narrative",
        )
        return {"enforced": True, "report_schema_version": schema_version, "configuration_valid": False}, [issue], True

    issues: list[dict[str, Any]] = []
    body = _extract_main_narrative(report)
    sections = _split_h2_sections(body)
    paragraphs = _narrative_paragraphs(body)
    normalized_paragraphs = [_normalize_narrative_block(value) for value in paragraphs]

    template_cfg = config.get("template_repetition") or {}
    labels = [str(value) for value in template_cfg.get("labels") or []]
    min_sections = int(template_cfg.get("min_sections", 3))
    min_ratio = float(template_cfg.get("min_section_ratio", 0.60))
    max_types = int(template_cfg.get("max_repeated_label_types", 2))
    template_counts = {label: sum(label in section for section in sections) for label in labels}
    repeated_labels = [
        label
        for label, count in template_counts.items()
        if count >= min_sections and count / max(len(sections), 1) >= min_ratio
    ]
    if len(repeated_labels) > max_types:
        issues.append(_issue("reader_template_scaffolding_excessive", ",".join(repeated_labels), "narrative"))

    process_cfg = config.get("process_audit_language") or {}
    process_hits: dict[str, list[str]] = {}
    for name, pattern in (process_cfg.get("patterns") or {}).items():
        matches = [match.group(0) for match in re.finditer(str(pattern), body, re.I)]
        if matches:
            process_hits[str(name)] = matches
    process_occurrences = sum(len(values) for values in process_hits.values())
    if process_occurrences > int(process_cfg.get("max_occurrences", 0)):
        issues.append(_issue("reader_process_audit_language_leaked", ",".join(sorted(process_hits)), "narrative"))

    opening_cfg = config.get("opening_repetition") or {}
    min_opening_length = int(opening_cfg.get("min_paragraph_han_chars", 45))
    opening_length = int(opening_cfg.get("opening_han_chars", 12))
    opening_counts = Counter(
        value[:opening_length]
        for value in normalized_paragraphs
        if len(value) >= min_opening_length and len(value) >= opening_length
    )
    repeated_openings = {key: count for key, count in opening_counts.items() if count > int(opening_cfg.get("max_same_opening_occurrences", 2))}
    if repeated_openings:
        issues.append(_issue("reader_opening_repetition_excessive", repr(repeated_openings), "narrative"))

    similarity_cfg = config.get("paragraph_similarity") or {}
    min_similarity_length = int(similarity_cfg.get("min_paragraph_han_chars", 60))
    shingle_length = int(similarity_cfg.get("shingle_han_chars", 4))
    threshold = float(similarity_cfg.get("similarity_threshold", 0.72))
    eligible = [(index, value) for index, value in enumerate(normalized_paragraphs) if len(value) >= min_similarity_length]
    similar_pairs: list[dict[str, Any]] = []
    for left_index, (left_paragraph, left) in enumerate(eligible):
        left_shingles = {left[offset : offset + shingle_length] for offset in range(max(len(left) - shingle_length + 1, 0))}
        for right_paragraph, right in eligible[left_index + 1 :]:
            right_shingles = {right[offset : offset + shingle_length] for offset in range(max(len(right) - shingle_length + 1, 0))}
            union = left_shingles | right_shingles
            similarity = len(left_shingles & right_shingles) / len(union) if union else 0.0
            if similarity >= threshold:
                similar_pairs.append({"left": left_paragraph + 1, "right": right_paragraph + 1, "similarity": round(similarity, 3)})
    if len(similar_pairs) > int(similarity_cfg.get("max_similar_pairs", 1)):
        issues.append(_issue("reader_paragraph_similarity_excessive", repr(similar_pairs[:8]), "narrative"))

    fragmentation_cfg = config.get("heading_fragmentation") or {}
    body_han = han_count(body)
    h2_per_1000_han = len(sections) * 1000 / max(body_han, 1)
    min_section_han = int(fragmentation_cfg.get("min_section_han_chars", 180))
    thin_sections = sum(han_count(section) < min_section_han for section in sections)
    thin_ratio = thin_sections / max(len(sections), 1)
    if (
        h2_per_1000_han > float(fragmentation_cfg.get("max_h2_per_1000_han", 2.5))
        or thin_ratio > float(fragmentation_cfg.get("max_thin_section_ratio", 0.40))
    ):
        issues.append(
            _issue(
                "reader_heading_fragmentation_excessive",
                f"h2_per_1000_han={h2_per_1000_han:.2f}; thin_section_ratio={thin_ratio:.2f}",
                "narrative",
            )
        )

    diagnostics = {
        "enforced": True,
        "report_schema_version": schema_version,
        "configuration_valid": True,
        "body_han_chars": body_han,
        "h2_section_count": len(sections),
        "narrative_paragraph_count": len(paragraphs),
        "template_label_section_counts": template_counts,
        "repeated_template_labels": repeated_labels,
        "process_audit_hits": process_hits,
        "repeated_openings": repeated_openings,
        "similar_paragraph_pairs": similar_pairs,
        "h2_per_1000_han": round(h2_per_1000_han, 3),
        "thin_section_count": thin_sections,
        "thin_section_ratio": round(thin_ratio, 3),
        "decision": "pass" if not issues else "needs_fix",
    }
    return diagnostics, issues, True


def evaluate_reader_candidate(
    payload: Mapping[str, Any],
    report: str,
    appendix: Mapping[str, Any],
    binding: Mapping[str, Any],
    reader_contract: Mapping[str, Any],
    quality_contract: Mapping[str, Any],
) -> dict[str, Any]:
    truthfulness: list[dict[str, Any]] = []
    core_blockers: list[dict[str, Any]] = []
    candidate_blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for raw in scan_main_report(report):
        truthfulness.append(_issue(raw["code"], raw["message"], "narrative", "critical"))

    expected_id = binding.get("expected_model_generation_id")
    expected_hash = binding.get("expected_model_aggregate_sha256")
    if payload.get("input_model_generation_id") != expected_id:
        truthfulness.append(_issue("stale_or_wrong_model_generation", str(payload.get("input_model_generation_id")), "generation", "critical"))
    if payload.get("input_model_aggregate_sha256") != expected_hash:
        truthfulness.append(_issue("stale_or_wrong_model_aggregate", str(payload.get("input_model_aggregate_sha256")), "generation", "critical"))

    report_refs = extract_display_refs(report)
    appendix_refs = [x.get("display_reference_id") for x in appendix.get("records") or [] if isinstance(x, Mapping)]
    unresolved = sorted(ref for ref in report_refs if appendix_refs.count(ref) != 1)
    duplicates = sorted({ref for ref in appendix_refs if appendix_refs.count(ref) > 1})
    if not report_refs:
        truthfulness.append(_issue("main_report_has_no_display_references", "no [E#] references", "evidence", "critical"))
    if unresolved:
        truthfulness.append(_issue("unresolved_traceability_reference", ",".join(unresolved), "evidence", "critical"))
    if duplicates:
        truthfulness.append(_issue("duplicate_traceability_reference", ",".join(duplicates), "evidence", "critical"))

    required_sections = tuple(reader_contract.get("required_sections") or DEFAULT_REQUIRED_SECTIONS)
    core_sections = set(reader_contract.get("core_sections") or DEFAULT_CORE_SECTIONS)
    sections = section_index(payload)
    section_diagnostics: dict[str, Any] = {}
    for section_id in required_sections:
        section = sections.get(section_id)
        if section is None:
            blocker = _issue("required_section_missing", section_id, "analysis")
            (core_blockers if section_id in core_sections else candidate_blockers).append(blocker)
            continue
        diagnostic = validate_analysis_section(section, core=section_id in core_sections, contract=reader_contract)
        section_diagnostics[section_id] = diagnostic
        if diagnostic["decision"] != "pass":
            target = core_blockers if section_id in core_sections else candidate_blockers
            target.append(_issue("core_section_analysis_unit_failed" if section_id in core_sections else "section_analysis_unit_failed", section_id, "analysis"))

    truthfulness.extend(_claim_boundary_issues(payload))
    candidate_blockers.extend(_market_event_issues(payload, sections.get("market_technical_sentiment_and_events")))

    source_diag = _source_diagnostics(appendix)
    candidate_cfg = quality_contract.get("candidate_requirements") or {}
    min_independent = int(candidate_cfg.get("min_independent_underlying_sources", 4))
    if source_diag["independent_source_count"] < min_independent:
        candidate_blockers.append(_issue("independent_sources_below_minimum", f"{source_diag['independent_source_count']} < {min_independent}", "evidence"))
    for category in candidate_cfg.get("required_source_categories") or []:
        if source_diag["category_counts"].get(category, 0) == 0:
            candidate_blockers.append(_issue("required_source_category_missing", str(category), "evidence"))
    min_peers = int(candidate_cfg.get("min_peer_sources", 3))
    if source_diag["peer_source_count"] < min_peers:
        candidate_blockers.append(_issue("peer_operating_sources_below_minimum", f"{source_diag['peer_source_count']} < {min_peers}", "valuation"))

    total_han = han_count(report)
    min_han = int(candidate_cfg.get("min_total_han_chars", 3200))
    if total_han < min_han:
        candidate_blockers.append(_issue("reader_report_below_density_floor", f"han_chars={total_han}; required={min_han}", "narrative"))

    narrative_diagnostics, narrative_issues, narrative_gate_enforced = _narrative_style_diagnostics(report, payload, quality_contract)
    candidate_blockers.extend(narrative_issues)

    truthfulness = _dedupe(truthfulness)
    core_blockers = _dedupe(core_blockers)
    candidate_blockers = _dedupe(candidate_blockers)

    # Positive-from-zero scoring. The score cannot override blockers.
    max_scores = quality_contract.get("dimensions") or {
        "evidence_integrity": 20,
        "coverage_completeness": 15,
        "analytical_synthesis": 20,
        "forecast_and_valuation": 15,
        "narrative_and_readability": 15,
        "presentation_hygiene": 10,
        "risks_and_watch_conditions": 5,
    }
    resolved_ratio = 1.0 if report_refs and not unresolved and not duplicates else 0.0
    category_ratio = min(len(source_diag["category_counts"]) / 4, 1.0)
    evidence_score = round(max_scores["evidence_integrity"] * (0.45 * resolved_ratio + 0.30 * min(source_diag["independent_source_count"] / max(min_independent, 1), 1.0) + 0.25 * category_ratio))

    required_present = sum(section_id in sections for section_id in required_sections)
    core_pass = sum(section_diagnostics.get(section_id, {}).get("decision") == "pass" for section_id in core_sections)
    coverage_ratio = 0.45 * required_present / max(len(required_sections), 1) + 0.55 * core_pass / max(len(core_sections), 1)
    coverage_score = round(max_scores["coverage_completeness"] * coverage_ratio)

    all_pass = sum(diag.get("decision") == "pass" for diag in section_diagnostics.values())
    analysis_score = round(max_scores["analytical_synthesis"] * all_pass / max(len(required_sections), 1))

    forecast_ok = section_diagnostics.get("forecast_and_scenarios", {}).get("decision") == "pass"
    valuation_ok = section_diagnostics.get("valuation_and_market_implied_expectations", {}).get("decision") == "pass"
    generation_ok = payload.get("input_model_generation_id") == expected_id and payload.get("input_model_aggregate_sha256") == expected_hash
    claim_ok = not _claim_boundary_issues(payload)
    fv_score = round(max_scores["forecast_and_valuation"] * sum([forecast_ok, valuation_ok, generation_ok, claim_ok]) / 4)

    density_ratio = min(total_han / max(min_han, 1), 1.0)
    heading_count = len(re.findall(r"^##\s+", report, re.M))
    if narrative_gate_enforced:
        narrative_score = round(
            max_scores["narrative_and_readability"]
            * (0.50 * density_ratio + 0.50 * float(not narrative_issues))
        )
    else:
        narrative_score = round(max_scores["narrative_and_readability"] * (0.55 * density_ratio + 0.45 * min(heading_count / max(len(required_sections), 1), 1.0)))
    hygiene_score = max_scores["presentation_hygiene"] if not truthfulness else 0
    risk_ok = section_diagnostics.get("risks_and_falsification", {}).get("decision") == "pass"
    conclusion_ok = section_diagnostics.get("conclusion_and_watchlist", {}).get("decision") == "pass"
    risk_score = round(max_scores["risks_and_watch_conditions"] * sum([risk_ok, conclusion_ok]) / 2)

    dimension_scores = {
        "evidence_integrity": evidence_score,
        "coverage_completeness": coverage_score,
        "analytical_synthesis": analysis_score,
        "forecast_and_valuation": fv_score,
        "narrative_and_readability": narrative_score,
        "presentation_hygiene": hygiene_score,
        "risks_and_watch_conditions": risk_score,
    }
    score = sum(dimension_scores.values())
    threshold = int(quality_contract.get("candidate_threshold", 82))
    draft_threshold = int(quality_contract.get("research_draft_threshold", 45))

    if truthfulness:
        quality_band = "blocked"
    elif score >= threshold and not core_blockers and not candidate_blockers:
        quality_band = "candidate_ready_for_human_review"
    elif score >= draft_threshold:
        quality_band = "research_draft"
    else:
        quality_band = "source_gapped_draft"
    decision = "candidate_ready_for_human_review" if quality_band == "candidate_ready_for_human_review" else "rejected"

    result = {
        "artifact_type": "R5_bundle10r_reader_quality_scorecard",
        "schema_version": 1,
        "scoring_method": "positive_from_zero_non_compensating_core",
        "decision": decision,
        "quality_band": quality_band,
        "score": score,
        "threshold": threshold,
        "truthfulness_blockers": truthfulness,
        "core_section_blockers": core_blockers,
        "candidate_blockers": candidate_blockers,
        "warnings": warnings,
        "critical_blocker_count": len(truthfulness) + len(core_blockers) + len(candidate_blockers),
        "dimension_scores": dimension_scores,
        "dimension_max_scores": max_scores,
        "section_diagnostics": section_diagnostics,
        **({"narrative_style_diagnostics": narrative_diagnostics} if narrative_gate_enforced else {}),
        "source_diagnostics": source_diag,
        "display_citations": {
            "used": sorted(report_refs, key=lambda x: (len(x), x)),
            "unresolved": unresolved,
            "duplicates": duplicates,
        },
        "input_model_generation_id": payload.get("input_model_generation_id"),
        "input_model_aggregate_sha256": payload.get("input_model_aggregate_sha256"),
        "human_review_required": True,
        "human_review_status": "pending",
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
    }
    return result
