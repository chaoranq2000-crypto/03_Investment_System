from __future__ import annotations

import csv
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "qa"))
sys.path.insert(0, str(ROOT / "src" / "maintenance"))

from backflow_stock_report import write_backflow_decision  # noqa: E402
from stock_report_quality_review import review_stock_report  # noqa: E402


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_quality_review_accepts_traceable_report(tmp_path: Path) -> None:
    run_dir = tmp_path / "wf"
    run_dir.mkdir()
    (run_dir / "stock_report_sample_quality_draft.md").write_text(
        "# 报告\n\n## 附录 A：Evidence Map\n\n| claim_id / metric_id | evidence_id |\n|---|---|\n| claim_001 | ev_001 |\n",
        encoding="utf-8",
    )
    (run_dir / "report_evidence_map.md").write_text("| x |\n", encoding="utf-8")
    (run_dir / "forecast_model.yaml").write_text(
        yaml.safe_dump({"key_assumptions": ["a"], "sensitivity": ["s"]}, allow_unicode=True),
        encoding="utf-8",
    )
    (run_dir / "valuation_model.yaml").write_text(
        yaml.safe_dump({"as_of_date": "2026-07-03"}, allow_unicode=True),
        encoding="utf-8",
    )
    (run_dir / "peer_comparison.csv").write_text("company,code\n英维克,002837\n", encoding="utf-8")
    (run_dir / "stock_analysis_pack.yaml").write_text(
        yaml.safe_dump(
            {
                "business_breakdown": {
                    "business_lines": [{"revenue": "MISSING_DISCLOSURE", "claim_ids": ["claim_001"]}],
                    "segment_links": [{"exposure_score": 3, "claim_ids": ["claim_001"]}],
                },
                "technical_sentiment_event": {"technical_snapshot": {"as_of_date": "2026-07-03"}},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    _write_csv(
        run_dir / "claims_registry.csv",
        ["claim_id", "evidence_id", "quote_or_excerpt", "page_no_or_section", "claim_type"],
        [{"claim_id": "claim_001", "evidence_id": "ev_001", "quote_or_excerpt": "液冷", "page_no_or_section": "page:1", "claim_type": "fact"}],
    )
    _write_csv(
        run_dir / "metrics_registry.csv",
        ["metric_id", "period", "value", "unit", "source_evidence_id", "metric_name"],
        [{"metric_id": "metric_001", "period": "20251231", "value": "100", "unit": "CNY", "source_evidence_id": "ev_metric", "metric_name": "total_revenue"}],
    )
    write_backflow_decision(run_dir=run_dir)
    result = review_stock_report(run_dir)
    assert result["final_status"] == "accepted_sample_quality"
    assert result["high_issues"] == 0
