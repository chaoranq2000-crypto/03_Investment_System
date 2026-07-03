from __future__ import annotations

import csv
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "research"))

from stock_analysis_pack_builder import build_stock_analysis_pack  # noqa: E402


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_stock_analysis_pack_preserves_missing_business_revenue(tmp_path: Path) -> None:
    run_dir = tmp_path / "wf"
    claims = run_dir / "claims_registry.csv"
    metrics = run_dir / "metrics_registry.csv"
    _write_csv(
        claims,
        ["claim_id", "evidence_id", "entity_type", "entity_id", "claim_text", "claim_type", "quote_or_excerpt", "page_no_or_section", "confidence"],
        [
            {
                "claim_id": "claim_001",
                "evidence_id": "ev_001",
                "entity_type": "company",
                "entity_id": "cn_002837_invic",
                "claim_text": "公司披露数据中心液冷相关产品。",
                "claim_type": "fact",
                "quote_or_excerpt": "液冷",
                "page_no_or_section": "page:2",
                "confidence": "medium",
            }
        ],
    )
    _write_csv(
        metrics,
        ["metric_id", "entity_type", "entity_id", "metric_name", "period", "value", "unit", "source_evidence_id", "calculation_method", "is_estimate", "confidence"],
        [
            {
                "metric_id": "metric_001",
                "entity_type": "company",
                "entity_id": "cn_002837_invic",
                "metric_name": "total_revenue",
                "period": "20251231",
                "value": "100",
                "unit": "CNY",
                "source_evidence_id": "ev_metric",
                "calculation_method": "reported",
                "is_estimate": "false",
                "confidence": "medium",
            }
        ],
    )
    build_stock_analysis_pack(
        run_dir=run_dir,
        claims_registry=claims,
        metrics_registry=metrics,
        stock_code="002837",
        stock_name="英维克",
        company_id="cn_002837_invic",
        as_of_date="2026-07-03",
    )
    pack = yaml.safe_load((run_dir / "stock_analysis_pack.yaml").read_text(encoding="utf-8"))
    assert pack["business_breakdown"]["business_lines"][0]["revenue"] == "MISSING_DISCLOSURE"
    assert (run_dir / "forecast_model.yaml").exists()
    assert (run_dir / "peer_comparison.csv").exists()
