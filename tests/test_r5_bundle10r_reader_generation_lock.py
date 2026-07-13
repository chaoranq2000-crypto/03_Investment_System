from pathlib import Path

from src.report.r5_reader_generation import build_reader_generation_lock
from tests.r5_bundle10r_test_fixtures import EVIDENCE_ID, MODEL_ID, MODEL_SHA


def test_reader_generation_lock_is_deterministic(tmp_path: Path):
    (tmp_path / "a.md").write_text("alpha\n", encoding="utf-8")
    (tmp_path / "b.yaml").write_text("beta: 1\n", encoding="utf-8")
    kwargs = dict(
        model_generation_id=MODEL_ID,
        model_aggregate_sha256=MODEL_SHA,
        evidence_generation_id=EVIDENCE_ID,
        created_at="2026-07-13",
        human_review_status="pending",
    )
    first = build_reader_generation_lock(tmp_path, ["a.md", "b.yaml"], **kwargs)
    second = build_reader_generation_lock(tmp_path, ["b.yaml", "a.md"], **kwargs)
    assert first["generation_id"] == second["generation_id"]
    assert first["aggregate_sha256"] == second["aggregate_sha256"]
    assert first["missing_artifact_count"] == 0
    assert first["sample_quality_allowed"] is False


def test_reader_generation_lock_supports_versioned_identity(tmp_path: Path):
    (tmp_path / "reader.md").write_text("version five\n", encoding="utf-8")
    result = build_reader_generation_lock(
        tmp_path,
        ["reader.md"],
        model_generation_id=MODEL_ID,
        model_aggregate_sha256=MODEL_SHA,
        evidence_generation_id=EVIDENCE_ID,
        created_at="2026-07-13",
        human_review_status="pending",
        generation_label="r5_bundle10r_reader_v5",
        generation_id_prefix="reader_gen_r5_bundle10r_v5",
    )
    assert result["generation_label"] == "r5_bundle10r_reader_v5"
    assert result["generation_id"].startswith("reader_gen_r5_bundle10r_v5_")
