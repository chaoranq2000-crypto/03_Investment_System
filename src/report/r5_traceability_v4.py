"""Build and validate the separate Bundle 10R traceability appendix."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from src.report.r5_bundle10r_contracts import extract_display_refs, stable_sha256


def build_traceability_appendix(
    payload: Mapping[str, Any],
    report: str,
    *,
    schema_version: str = "v4",
) -> dict[str, Any]:
    catalog = payload.get("reference_catalog") or []
    by_ref: dict[str, list[dict[str, Any]]] = {}
    for raw in catalog:
        if not isinstance(raw, Mapping):
            continue
        ref = raw.get("display_reference_id")
        if isinstance(ref, str):
            by_ref.setdefault(ref, []).append(dict(raw))

    used = sorted(extract_display_refs(report), key=lambda x: (len(x), x))
    unresolved = [ref for ref in used if len(by_ref.get(ref, [])) != 1]
    records = [by_ref[ref][0] for ref in used if len(by_ref.get(ref, [])) == 1]
    duplicates = sorted(ref for ref, values in by_ref.items() if len(values) > 1)
    unused = sorted(ref for ref in by_ref if ref not in used)
    if unresolved or duplicates:
        raise ValueError(f"traceability failure: unresolved={unresolved}; duplicates={duplicates}")

    categories = Counter(str(item.get("source_category") or "unknown") for item in records)
    independent = sorted(
        {
            str(item.get("underlying_source_id"))
            for item in records
            if item.get("independent") is True and item.get("underlying_source_id")
        }
    )
    appendix = {
        "artifact_type": "R5_bundle10r_traceability_appendix",
        "schema_version": schema_version,
        "workflow_id": payload.get("workflow_id"),
        "input_model_generation_id": payload.get("input_model_generation_id"),
        "used_display_reference_count": len(used),
        "records": records,
        "unresolved_references": unresolved,
        "duplicate_references": duplicates,
        "unused_catalog_references": unused,
        "source_diagnostics": {
            "category_counts": dict(sorted(categories.items())),
            "independent_underlying_source_count": len(independent),
            "independent_underlying_source_ids": independent,
        },
    }
    appendix["appendix_content_sha256"] = stable_sha256(appendix)
    return appendix
