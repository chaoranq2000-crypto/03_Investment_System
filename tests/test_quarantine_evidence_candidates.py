from __future__ import annotations

from pathlib import Path

from scripts.quarantine_evidence_candidates import quarantine


def test_quarantine_marks_manifest_and_removes_only_matching_drafts(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "evidence_id,status,candidate_status,review_status,superseded_by,notes\n"
        "old,active,generated,draft,,scope too broad\n"
        "keep,active,generated,draft,,ok\n",
        encoding="utf-8",
    )
    metrics = tmp_path / "metrics.csv"
    metrics.write_text(
        "metric_candidate_id,source_evidence_id\nmetric_old,old\nmetric_keep,keep\n",
        encoding="utf-8",
    )
    claims = tmp_path / "claims.csv"
    claims.write_text(
        "claim_candidate_id,evidence_id\nclaim_old,old\nclaim_keep,keep\n",
        encoding="utf-8",
    )
    result = quarantine(
        manifest_path=manifest,
        metrics_path=metrics,
        claims_path=claims,
        evidence_id="old",
        superseded_by="new",
        reason="over-broad fixture",
    )
    assert result["metric_candidates_removed"] == 1
    assert result["claim_candidates_removed"] == 1
    assert "old,superseded,blocked,rejected,new" in manifest.read_text(encoding="utf-8")
    assert "metric_old" not in metrics.read_text(encoding="utf-8")
    assert "metric_keep" in metrics.read_text(encoding="utf-8")
