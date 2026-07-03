from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "report"))

from stock_report_writer import render_report  # noqa: E402


def test_stock_report_writer_outputs_sections_and_evidence_map(tmp_path: Path) -> None:
    run_dir = tmp_path / "wf"
    run_dir.mkdir()
    (run_dir / "stock_analysis_pack.yaml").write_text(
        yaml.safe_dump(
            {
                "metadata": {
                    "stock_code": "002837",
                    "stock_name": "英维克",
                    "company_id": "cn_002837_invic",
                    "analysis_date": "2026-07-03",
                    "quality_target": "R3_sample_quality_draft",
                    "evidence_snapshot": "manifest.csv",
                    "claim_ids": ["claim_001"],
                    "metric_ids": ["metric_001"],
                },
                "core_thesis": {"one_sentence": "核心主线。"},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    for name, payload in {
        "financial_quality.yaml": {"ratios": []},
        "business_breakdown.yaml": {"business_lines": [], "segment_links": []},
        "industry_context_card.yaml": {},
        "forecast_model.yaml": {"revenue_forecast": []},
        "valuation_model.yaml": {"peer_comparison": str(run_dir / "peer_comparison.csv"), "conclusion": "框架"},
        "risk_counter_evidence.yaml": {"risks": ["风险"]},
        "evidence_gap_requests.yaml": [{"gap_id": "gap_1", "missing_claim_or_metric": "缺口"}],
    }.items():
        (run_dir / name).write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    (run_dir / "peer_comparison.csv").write_text("company,code,business_relevance,pe_ttm,2026E_PE,2027E_PE,notes\n", encoding="utf-8")
    result = render_report(run_dir=run_dir, template_path=ROOT / "templates/stock_report_sample_quality.md", output_path=run_dir / "draft.md")
    text = (run_dir / "draft.md").read_text(encoding="utf-8")
    assert result["evidence_rows"] == 2
    assert "## 前言" in text
    assert "## 附录 A：Evidence Map" in text
    assert "买入" not in text
