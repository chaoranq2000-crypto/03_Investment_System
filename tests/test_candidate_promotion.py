from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "review"))

from promote_claim_candidates import promote_claim_candidates  # noqa: E402
from promote_metric_candidates import promote_metric_candidates  # noqa: E402


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_candidate_promotion_blocks_missing_locator_and_promotes_valid(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    _write_csv(manifest, ["evidence_id"], [{"evidence_id": "ev_001"}])
    claims = tmp_path / "claim_candidates.csv"
    _write_csv(
        claims,
        [
            "claim_candidate_id",
            "evidence_id",
            "entity_type",
            "entity_id",
            "claim_text",
            "claim_type",
            "quote_or_excerpt",
            "page_no_or_section",
            "confidence",
            "materiality",
            "claim_scope",
            "reliability_rank",
            "notes",
        ],
        [
            {
                "claim_candidate_id": "bad",
                "evidence_id": "ev_001",
                "claim_text": "bad",
                "materiality": "material",
                "reliability_rank": "A",
            },
            {
                "claim_candidate_id": "good",
                "evidence_id": "ev_001",
                "entity_type": "company",
                "entity_id": "cn_002837_invic",
                "claim_text": "公司披露液冷产品。",
                "claim_type": "fact",
                "quote_or_excerpt": "液冷产品",
                "page_no_or_section": "page:2",
                "confidence": "medium",
                "materiality": "material",
                "claim_scope": "business_exposure",
                "reliability_rank": "A",
                "notes": "locator ok",
            },
        ],
    )
    result = promote_claim_candidates(
        candidates_path=claims,
        manifest_path=manifest,
        output_registry_path=tmp_path / "claims_registry.csv",
        promotion_log_path=tmp_path / "claim_promotion_log.csv",
    )
    assert result == {"promoted": 1, "rejected": 1}


def test_metric_promotion_requires_period_value_unit(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    _write_csv(manifest, ["evidence_id"], [{"evidence_id": "ev_metric"}])
    metrics = tmp_path / "metric_candidates.csv"
    _write_csv(
        metrics,
        [
            "metric_candidate_id",
            "source_evidence_id",
            "entity_type",
            "entity_id",
            "metric_name",
            "period",
            "value",
            "unit",
            "calculation_method",
            "is_estimate",
            "confidence",
            "notes",
        ],
        [
            {
                "metric_candidate_id": "metric_good",
                "source_evidence_id": "ev_metric",
                "entity_type": "company",
                "entity_id": "cn_002837_invic",
                "metric_name": "total_revenue",
                "period": "20251231",
                "value": "100",
                "unit": "CNY",
                "calculation_method": "reported",
                "is_estimate": "false",
                "confidence": "medium",
            }
        ],
    )
    result = promote_metric_candidates(
        candidates_path=metrics,
        manifest_path=manifest,
        output_registry_path=tmp_path / "metrics_registry.csv",
        promotion_log_path=tmp_path / "metric_promotion_log.csv",
    )
    assert result["promoted"] == 1
