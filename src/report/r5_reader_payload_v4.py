"""Normalize and validate structured Reader payloads for Bundle 10R."""

from __future__ import annotations

from typing import Any, Mapping

from src.report.r5_bundle10r_contracts import (
    clone_mapping,
    extract_display_refs,
    stable_sha256,
    validate_payload_structure,
)


def _normalize_item(item: Any) -> Any:
    if isinstance(item, str):
        return {"text": item, "refs": sorted(extract_display_refs(item))}
    if isinstance(item, Mapping):
        out = clone_mapping(item)
        refs = set(out.get("refs") or [])
        refs.update(extract_display_refs(out.get("text")))
        if refs:
            out["refs"] = sorted(refs)
        return out
    return item


def normalize_reader_payload(
    raw: Mapping[str, Any],
    *,
    model_generation_id: str,
    model_aggregate_sha256: str,
    reader_contract: Mapping[str, Any] | None = None,
    schema_version: str = "v4",
) -> dict[str, Any]:
    payload = clone_mapping(raw)
    payload["artifact_type"] = "R5_bundle10r_reader_payload"
    payload["schema_version"] = schema_version
    payload["input_model_generation_id"] = model_generation_id
    payload["input_model_aggregate_sha256"] = model_aggregate_sha256

    sections: list[dict[str, Any]] = []
    for raw_section in payload.get("sections") or []:
        section = clone_mapping(raw_section)
        for field in (
            "facts",
            "causal_mechanism",
            "economic_implications",
            "counterevidence",
            "uncertainty",
            "watchpoints",
        ):
            section[field] = [_normalize_item(x) for x in section.get(field) or []]
        refs = set(section.get("references") or [])
        refs.update(extract_display_refs(section))
        section["references"] = sorted(refs)
        sections.append(section)
    payload["sections"] = sections

    chapters: list[dict[str, Any]] = []
    for raw_chapter in payload.get("narrative_chapters") or []:
        if not isinstance(raw_chapter, Mapping):
            raise ValueError("narrative_chapters must contain mappings")
        chapter = clone_mapping(raw_chapter)
        for field in ("lead", "paragraphs", "paragraphs_after_tables", "watchpoints", "events"):
            value = chapter.get(field)
            if field == "lead":
                if value:
                    chapter[field] = _normalize_item(value)
            else:
                chapter[field] = [_normalize_item(x) for x in value or []]
        chapters.append(chapter)
    if chapters:
        payload["narrative_chapters"] = chapters

    payload["payload_content_sha256"] = stable_sha256({k: v for k, v in payload.items() if k != "payload_content_sha256"})

    validation = validate_payload_structure(payload, reader_contract)
    if validation["decision"] != "pass":
        messages = "; ".join(x["message"] for x in validation["issues"][:12])
        raise ValueError(f"invalid Reader payload: {messages}")
    return payload
