from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.investment_review.review_pack import (
    INDEX_SCHEMA_VERSION,
    INTERPRETATION_STATUS,
    SCHEMA_VERSION,
    ReviewPackError,
    build_review_packs,
    validate_review_pack_directory,
)


def _write_source(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sample_document() -> dict[str, object]:
    return {
        "schema_version": "investment-review.trade-episodes.v1",
        "cutoff_at": "2026-07-15T15:00:00+08:00",
        "episodes": [
            {
                "episode_id": "ep:600519:20260701",
                "symbol": "600519.SH",
                "opened_at": "2026-07-01T09:35:00+08:00",
                "closed_at": "2026-07-10T14:50:00+08:00",
                "status": "closed",
                "fills": [
                    {
                        "fill_id": "f2",
                        "filled_at": "2026-07-10T14:50:00+08:00",
                        "side": "sell",
                        "quantity": 100,
                        "price": 1500.0,
                    },
                    {
                        "fill_id": "f1",
                        "filled_at": "2026-07-01T09:35:00+08:00",
                        "side": "buy",
                        "quantity": 100,
                        "price": 1480.0,
                    },
                ],
                "portfolio_snapshot_link": {
                    "status": "missing",
                    "requested_as_of": "2026-07-01",
                },
                "decision_link": {"link_status": "unlinked"},
            },
            {
                "episode_id": "ep:510300:20260702",
                "ticker": "510300.SH",
                "started_at": "2026-07-02T10:00:00+08:00",
                "state": "open",
                "events": [
                    {
                        "type": "fill",
                        "occurred_at": "2026-07-02T10:00:00+08:00",
                        "side": "buy",
                    }
                ],
            },
        ],
    }


def test_build_is_byte_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "episodes.json"
    _write_source(source, _sample_document())
    first = tmp_path / "first"
    second = tmp_path / "second"

    first_index = build_review_packs(source, first)
    second_index = build_review_packs(source, second)

    assert first_index == second_index
    assert sorted(path.name for path in first.iterdir()) == sorted(
        path.name for path in second.iterdir()
    )
    for first_file in first.iterdir():
        assert first_file.read_bytes() == (second / first_file.name).read_bytes()


def test_build_preserves_source_and_surfaces_unresolved_links(tmp_path: Path) -> None:
    source = tmp_path / "episodes.json"
    document = _sample_document()
    _write_source(source, document)
    output = tmp_path / "bundles"

    index = build_review_packs(source, output, selected_ids=["ep:600519:20260701"])

    assert index["schema_version"] == INDEX_SCHEMA_VERSION
    assert index["episode_count"] == 1
    bundle = json.loads((output / index["bundles"][0]["file"]).read_text(encoding="utf-8"))
    assert bundle["schema_version"] == SCHEMA_VERSION
    assert bundle["source_episode"] == document["episodes"][0]
    statuses = {item["status"] for item in bundle["linkage_diagnostics"]["unresolved"]}
    assert statuses == {"missing", "unlinked"}
    assert bundle["interpretation"]["status"] == INTERPRETATION_STATUS
    assert "motive" not in bundle
    assert "score" not in bundle


def test_timeline_is_sorted_without_mutating_source_order(tmp_path: Path) -> None:
    source = tmp_path / "episodes.json"
    document = _sample_document()
    _write_source(source, document)
    output = tmp_path / "bundles"

    index = build_review_packs(source, output, selected_ids=["ep:600519:20260701"])
    bundle = json.loads((output / index["bundles"][0]["file"]).read_text(encoding="utf-8"))

    assert [item["facts"]["fill_id"] for item in bundle["timeline"]] == ["f1", "f2"]
    assert [item["fill_id"] for item in bundle["source_episode"]["fills"]] == ["f2", "f1"]


def test_missing_episode_id_gets_stable_synthetic_id(tmp_path: Path) -> None:
    source = tmp_path / "episodes.json"
    _write_source(
        source,
        [
            {
                "symbol": "000001.SZ",
                "opened_at": "2026-07-03T10:00:00+08:00",
                "fills": [],
            }
        ],
    )
    output = tmp_path / "bundles"

    index = build_review_packs(source, output)
    entry = index["bundles"][0]
    assert entry["episode_id"].startswith("synthetic:")
    bundle = json.loads((output / entry["file"]).read_text(encoding="utf-8"))
    assert bundle["completeness"]["missing_core_fields"] == ["episode_id"]
    assert bundle["completeness"]["warnings"]


def test_validate_detects_tampering(tmp_path: Path) -> None:
    source = tmp_path / "episodes.json"
    _write_source(source, _sample_document())
    output = tmp_path / "bundles"
    index = build_review_packs(source, output)
    assert validate_review_pack_directory(output, source_path=source) == []

    bundle_path = output / index["bundles"][0]["file"]
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle["source_episode"]["status"] = "tampered"
    bundle_path.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    errors = validate_review_pack_directory(output, source_path=source)
    assert any("bundle file hash mismatch" in error for error in errors)
    assert any("source episode hash mismatch" in error for error in errors)


def test_validate_detects_wrong_source_artifact(tmp_path: Path) -> None:
    source = tmp_path / "episodes.json"
    other = tmp_path / "other.json"
    _write_source(source, _sample_document())
    _write_source(other, {"episodes": []})
    output = tmp_path / "bundles"
    build_review_packs(source, output)

    errors = validate_review_pack_directory(output, source_path=other)
    assert any("source artifact hash mismatch" in error for error in errors)


def test_non_empty_output_requires_explicit_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "episodes.json"
    _write_source(source, _sample_document())
    output = tmp_path / "bundles"
    output.mkdir()
    (output / "keep.txt").write_text("do not silently delete", encoding="utf-8")

    with pytest.raises(ReviewPackError, match="not empty"):
        build_review_packs(source, output)


def test_overwrite_rebuilds_output(tmp_path: Path) -> None:
    source = tmp_path / "episodes.json"
    _write_source(source, _sample_document())
    output = tmp_path / "bundles"
    output.mkdir()
    (output / "stale.txt").write_text("stale", encoding="utf-8")

    index = build_review_packs(source, output, overwrite=True)

    assert index["episode_count"] == 2
    assert not (output / "stale.txt").exists()
    assert (output / "index.json").exists()


def test_source_hash_is_exact_file_hash(tmp_path: Path) -> None:
    source = tmp_path / "episodes.json"
    _write_source(source, _sample_document())
    output = tmp_path / "bundles"
    index = build_review_packs(source, output)

    assert index["source"]["artifact_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_existing_canonical_timeline_is_not_duplicated(tmp_path: Path) -> None:
    source = tmp_path / "episodes.json"
    _write_source(
        source,
        {
            "episodes": [
                {
                    "episode_id": "ep:canonical",
                    "symbol": "600000.SH",
                    "opened_at": "2026-07-01T09:30:00+08:00",
                    "timeline": [
                        {"type": "fill", "occurred_at": "2026-07-01T09:30:00+08:00", "id": "t1"}
                    ],
                    "fills": [
                        {"filled_at": "2026-07-01T09:30:00+08:00", "fill_id": "f1"}
                    ],
                }
            ]
        },
    )
    output = tmp_path / "bundles"

    index = build_review_packs(source, output)
    bundle = json.loads((output / index["bundles"][0]["file"]).read_text(encoding="utf-8"))

    assert len(bundle["timeline"]) == 1
    assert bundle["timeline"][0]["source_collection"] == "timeline"


def test_current_p2c_event_refs_and_snapshot_links_form_timeline(tmp_path: Path) -> None:
    source = tmp_path / "episodes.json"
    _write_source(
        source,
        {
            "schema_version": "portfolio.trade_episode.collection.v1",
            "episodes": [
                {
                    "schema_version": "portfolio.trade_episode.v1",
                    "episode_id": "te_current_p2c",
                    "scope": {"symbol": "600000.SH"},
                    "opened_at": "2026-07-01T09:30:00+08:00",
                    "status": "closed",
                    "event_refs": [
                        {
                            "event_id": "e2",
                            "event_type": "fill",
                            "effective_at": "2026-07-02T14:50:00+08:00",
                        },
                        {
                            "event_id": "e1",
                            "event_type": "fill",
                            "effective_at": "2026-07-01T09:30:00+08:00",
                        },
                    ],
                    "snapshot_links": [
                        {
                            "link_role": "before_open",
                            "event_time": "2026-07-01T09:30:00+08:00",
                            "snapshot_as_of": "2026-07-01T09:25:00+08:00",
                            "validation_status": "missing",
                        }
                    ],
                }
            ],
        },
    )
    output = tmp_path / "bundles"

    index = build_review_packs(source, output)
    bundle = json.loads((output / index["bundles"][0]["file"]).read_text(encoding="utf-8"))

    assert [item["source_collection"] for item in bundle["timeline"]] == [
        "event_refs",
        "snapshot_links",
        "event_refs",
    ]
    assert [item["facts"].get("event_id") for item in bundle["timeline"]] == [
        "e1",
        None,
        "e2",
    ]
    assert bundle["identity"]["symbol"] == "600000.SH"
    assert bundle["completeness"]["timeline_entry_count"] == 3
    assert bundle["linkage_diagnostics"]["by_status"]["missing"] == [
        {"pointer": "/snapshot_links/0/validation_status", "status": "missing"}
    ]


def test_single_episode_without_explicit_id_is_accepted(tmp_path: Path) -> None:
    source = tmp_path / "episode.json"
    _write_source(
        source,
        {
            "symbol": "000001.SZ",
            "opened_at": "2026-07-03T10:00:00+08:00",
            "events": [],
        },
    )
    output = tmp_path / "bundles"

    index = build_review_packs(source, output)

    assert index["episode_count"] == 1
    assert index["bundles"][0]["episode_id"].startswith("synthetic:")


def test_non_standard_json_constants_are_rejected(tmp_path: Path) -> None:
    source = tmp_path / "episodes.json"
    source.write_text('[{"episode_id":"ep:bad","price":NaN}]', encoding="utf-8")

    with pytest.raises(ReviewPackError, match="non-standard JSON constant"):
        build_review_packs(source, tmp_path / "bundles")
