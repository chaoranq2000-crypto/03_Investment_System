from pathlib import Path

from src.ingest.evidence_generation import build_generation_record, downstream_freshness


def test_generation_changes_when_an_input_changes(tmp_path: Path) -> None:
    file_path = tmp_path / "manifest.csv"
    file_path.write_text("a\n1\n", encoding="utf-8")
    first = build_generation_record(repo_root=tmp_path, input_paths=["manifest.csv"], generation_label="b8r", created_at="x")
    file_path.write_text("a\n2\n", encoding="utf-8")
    second = build_generation_record(repo_root=tmp_path, input_paths=["manifest.csv"], generation_label="b8r", created_at="x")
    assert first["generation_id"] != second["generation_id"]
    assert downstream_freshness(second["generation_id"], first["generation_id"])["fresh"] is False
