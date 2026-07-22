from __future__ import annotations

import csv
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from src.research.r5_bundle16r_evidence_pack_materializer import (
    MAPPING_SCHEMA_VERSION,
    MaterializationContractError,
    atomic_publish_packs,
    load_catalog,
    materialize_suite,
    sha256_file,
    write_materialization_outputs,
)


BASELINE = "233d0cffbea04b69027d9825954e6d49bd62bfab"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def _yaml(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=True), encoding="utf-8")
    return path


def _json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path


def _case(repo: Path) -> Path:
    return _yaml(
        repo / "tests/fixtures/r5_bundle14r/cases/fixture.yaml",
        {
            "schema_version": "r5_bundle14r_case_v1",
            "case_id": "fixture_case",
            "issuer": {"name": "示例制造公司", "ticker": "000001.SZ"},
            "required_source_classes": ["issuer_exchange_filings"],
            "drivers": [
                {"driver_id": "volume", "label": "volume"},
                {"driver_id": "unit_price", "label": "unit price"},
            ],
            "research_questions": [
                {"question_id": "q_volume", "driver_ids": ["volume"], "required": True},
                {"question_id": "q_price", "driver_ids": ["unit_price"], "required": True},
            ],
            "backflow_routes": {
                "EVIDENCE_MISSING": {"stage": "T1_evidence_plan", "skill": "evidence-ingest"},
                "DRIVER_UNQUALIFIED": {"stage": "T2_evidence_acquire_parse", "skill": "evidence-ingest"},
                "OVERLAP_UNRESOLVED": {"stage": "T5_analysis_pack_build", "skill": "stock-deep-dive"},
                "VALUATION_INELIGIBLE": {"stage": "T6_forecast_valuation_model", "skill": "valuation-model"},
                "SEMANTIC_QUALITY_FAILED": {"stage": "T9_quality_review", "skill": "quality-review"},
            },
        },
    )


def _artifacts(repo: Path) -> dict[str, dict[str, str]]:
    overlap = _yaml(
        repo / "reports/fixture/overlap.yaml",
        {
            "overlap_reconciliation": {
                "status": "passed",
                "revenue_overlap_resolved": True,
                "gross_profit_overlap_resolved": True,
                "unresolved_items": [],
            }
        },
    )
    forecast = _yaml(
        repo / "reports/fixture/forecast.yaml",
        {
            "forecast_bridge": {
                "status": "passed",
                "driver_to_statement_reconciliation": True,
                "working_capital_bridge": True,
                "cash_flow_bridge": True,
                "segment_revenue_coverage": 0.9,
                "segment_gross_profit_coverage": 0.85,
            }
        },
    )
    valuation = _yaml(
        repo / "reports/fixture/valuation.yaml",
        {
            "valuation": {
                "methods": [
                    {
                        "method": "reverse_valuation",
                        "eligible": True,
                        "market_value_reconciled": True,
                        "share_count_reconciled": True,
                        "forecast_definition_reconciled": True,
                        "implied_operating_assumptions_documented": True,
                    }
                ]
            }
        },
    )
    semantic = _json(repo / "reports/fixture/semantic.json", {"status": "passed"})
    determinism = _json(
        repo / "reports/fixture/determinism.json",
        {
            "determinism": {
                "rerun_hash_equal": True,
                "input_lock_complete": True,
                "output_lock_complete": True,
            }
        },
    )
    return {
        "overlap_reconciliation": {
            "artifact_path": overlap.relative_to(repo).as_posix(),
            "artifact_sha256": sha256_file(overlap),
            "json_pointer": "/overlap_reconciliation",
        },
        "forecast_bridge": {
            "artifact_path": forecast.relative_to(repo).as_posix(),
            "artifact_sha256": sha256_file(forecast),
            "json_pointer": "/forecast_bridge",
        },
        "valuation": {
            "artifact_path": valuation.relative_to(repo).as_posix(),
            "artifact_sha256": sha256_file(valuation),
            "json_pointer": "/valuation",
        },
        "semantic_candidate": {
            "artifact_path": semantic.relative_to(repo).as_posix(),
            "artifact_sha256": sha256_file(semantic),
            "json_pointer": "/",
        },
        "determinism": {
            "artifact_path": determinism.relative_to(repo).as_posix(),
            "artifact_sha256": sha256_file(determinism),
            "json_pointer": "/determinism",
        },
    }


def _inputs(repo: Path) -> tuple[Path, Path]:
    source = _write(repo / "data/raw/annual_reports/fixture.txt", "official evidence\n")
    catalog = _yaml(
        repo / "data/processed/normalized/catalog.yaml",
        {
            "sources": [
                {
                    "source_id": "src_issuer",
                    "source_class": "issuer_exchange_filings",
                    "official": True,
                    "review_status": "accepted",
                    "archive_path": source.relative_to(repo).as_posix(),
                    "sha256": sha256_file(source),
                    "publication_date": "2026-03-31",
                    "covered_period": "FY2025",
                    "locator": "p.1",
                    "limitations": "",
                }
            ],
            "records": [
                {
                    "record_id": "rec_volume",
                    "review_status": "accepted",
                    "value": 100,
                    "unit": "tonnes",
                    "period": "FY2025",
                    "definition": "physical shipment volume",
                    "confidence": "high",
                    "source_ids": ["src_issuer"],
                },
                {
                    "record_id": "rec_price",
                    "review_status": "accepted_with_limitations",
                    "value": {"low": 9.5, "high": 10.5},
                    "unit": "currency_per_tonne",
                    "period": "FY2025",
                    "definition": "realized unit price range",
                    "confidence": "medium",
                    "source_ids": ["src_issuer"],
                },
            ],
        },
    )
    mapping = _yaml(
        repo / "reports/reviewed_mappings/fixture_case.yaml",
        {
            "schema_version": MAPPING_SCHEMA_VERSION,
            "case_id": "fixture_case",
            "issuer_ticker": "000001.SZ",
            "as_of_date": "2026-07-15",
            "pack_review": {
                "status": "accepted_with_limitations",
                "reviewer": "human-reviewer",
                "reviewed_at": "2026-07-15T12:00:00+01:00",
            },
            "source_bindings": [{"catalog_source_id": "src_issuer"}],
            "record_bindings": [
                {
                    "catalog_record_id": "rec_volume",
                    "driver_id": "volume",
                    "question_ids": ["q_volume"],
                    "status": "confirmed",
                    "overlap_rule": "issuer segment volume only",
                    "stale_trigger": "new interim or annual filing",
                    "dependencies": [],
                },
                {
                    "catalog_record_id": "rec_price",
                    "driver_id": "unit_price",
                    "question_ids": ["q_price"],
                    "status": "bounded_estimate",
                    "overlap_rule": "same product and period",
                    "stale_trigger": "new price or revenue disclosure",
                    "dependencies": ["rec_volume"],
                },
            ],
            "artifact_bindings": _artifacts(repo),
        },
    )
    return catalog, mapping


def _suite(repo: Path, catalog: Path | None, mapping: Path | None):
    return materialize_suite(
        repo_root=repo,
        cases_dir=repo / "tests/fixtures/r5_bundle14r/cases",
        catalog_paths=[catalog] if catalog else [],
        mapping_paths=[mapping] if mapping else [],
        policy_document={},
        baseline_commit=BASELINE,
    )


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _case(repo)
    return repo


def test_missing_mapping_fails_closed_and_emits_queues(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    artifacts = _suite(repo, None, None)
    case = artifacts.suite.cases[0]
    assert case.decision == "review_mapping_required"
    assert case.pack_materialized is False
    assert artifacts.suite.sample_quality_allowed is False
    assert artifacts.suite.p2_allowed is False
    assert artifacts.source_requests
    assert artifacts.mapping_tasks


def test_valid_mapping_materializes_bundle15r_pack_without_release_authority(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    catalog, mapping = _inputs(repo)
    artifacts = _suite(repo, catalog, mapping)
    case = artifacts.suite.cases[0]
    assert case.decision == "pack_ready_for_bundle15r_qualification"
    pack = artifacts.packs["fixture_case"]
    assert pack["schema_version"] == "r5_bundle15r_reviewed_evidence_pack_v1"
    assert pack["release"] == {
        "sample_quality_allowed": False,
        "p2_allowed": False,
        "workflow_state_mutation_allowed": False,
    }
    assert {item["driver_id"] for item in pack["records"]} == {"volume", "unit_price"}
    assert pack["semantic_candidate"]["status"] == "passed"


def test_mapping_cannot_override_numeric_evidence_fields(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    catalog, mapping = _inputs(repo)
    doc = yaml.safe_load(mapping.read_text(encoding="utf-8"))
    doc["record_bindings"][0]["value"] = 999
    _yaml(mapping, doc)
    artifacts = _suite(repo, catalog, mapping)
    case = artifacts.suite.cases[0]
    assert "volume" in case.missing_driver_ids
    assert any(issue.code == "RECORD_VALUE_OVERRIDE_FORBIDDEN" for issue in case.issues)


def test_source_hash_mismatch_is_blocking_and_no_invalid_pack_is_emitted(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    catalog, mapping = _inputs(repo)
    source = repo / "data/raw/annual_reports/fixture.txt"
    source.write_text("changed\n", encoding="utf-8")
    artifacts = _suite(repo, catalog, mapping)
    case = artifacts.suite.cases[0]
    assert case.pack_materialized is False
    assert any(issue.code == "SOURCE_HASH_MISMATCH" for issue in case.issues)


def test_unreviewed_or_nonofficial_source_is_rejected(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    catalog, mapping = _inputs(repo)
    doc = yaml.safe_load(catalog.read_text(encoding="utf-8"))
    doc["sources"][0]["official"] = False
    doc["sources"][0]["review_status"] = "pending"
    _yaml(catalog, doc)
    artifacts = _suite(repo, catalog, mapping)
    codes = {issue.code for issue in artifacts.suite.cases[0].issues}
    assert "SOURCE_UNQUALIFIED" in codes
    assert artifacts.suite.pack_materialized_count == 0


def test_narrative_sample_path_is_forbidden_even_when_hash_matches(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    catalog, mapping = _inputs(repo)
    sample = _write(repo / "data/raw/个股研究报告样例.txt", "narrative\n")
    doc = yaml.safe_load(catalog.read_text(encoding="utf-8"))
    doc["sources"][0]["archive_path"] = sample.relative_to(repo).as_posix()
    doc["sources"][0]["sha256"] = sha256_file(sample)
    _yaml(catalog, doc)
    artifacts = _suite(repo, catalog, mapping)
    assert any(issue.code == "SAMPLE_PATH_FORBIDDEN" for issue in artifacts.suite.cases[0].issues)


def test_unknown_driver_and_question_do_not_enter_pack(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    catalog, mapping = _inputs(repo)
    doc = yaml.safe_load(mapping.read_text(encoding="utf-8"))
    doc["record_bindings"][0]["driver_id"] = "issuer_specific_hardcode"
    doc["record_bindings"][1]["question_ids"] = ["unknown_question"]
    _yaml(mapping, doc)
    artifacts = _suite(repo, catalog, mapping)
    codes = {issue.code for issue in artifacts.suite.cases[0].issues}
    assert "RECORD_DRIVER_UNKNOWN" in codes
    assert "RECORD_QUESTION_UNKNOWN" in codes
    assert artifacts.suite.cases[0].bound_record_count == 0


def test_low_confidence_cannot_qualify_confirmed_or_bounded_record(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    catalog, mapping = _inputs(repo)
    doc = yaml.safe_load(catalog.read_text(encoding="utf-8"))
    doc["records"][0]["confidence"] = "low"
    _yaml(catalog, doc)
    artifacts = _suite(repo, catalog, mapping)
    case = artifacts.suite.cases[0]
    assert "volume" in case.missing_driver_ids
    assert any(issue.code == "RECORD_CONFIDENCE_UNQUALIFIED" for issue in case.issues)


def test_record_source_must_be_bound_to_pack(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    catalog, mapping = _inputs(repo)
    doc = yaml.safe_load(mapping.read_text(encoding="utf-8"))
    doc["source_bindings"] = []
    _yaml(mapping, doc)
    artifacts = _suite(repo, catalog, mapping)
    codes = {issue.code for issue in artifacts.suite.cases[0].issues}
    assert "RECORD_SOURCE_UNBOUND" in codes
    assert artifacts.suite.pack_materialized_count == 0


def test_missing_artifact_bindings_are_safe_blocked_defaults(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    catalog, mapping = _inputs(repo)
    doc = yaml.safe_load(mapping.read_text(encoding="utf-8"))
    doc["artifact_bindings"] = {}
    _yaml(mapping, doc)
    artifacts = _suite(repo, catalog, mapping)
    pack = artifacts.packs["fixture_case"]
    assert pack["overlap_reconciliation"]["status"] == "blocked"
    assert pack["forecast_bridge"]["status"] == "blocked"
    assert pack["valuation"]["methods"] == []
    assert pack["semantic_candidate"]["status"] == "pending"
    assert pack["determinism"]["rerun_hash_equal"] is False
    assert artifacts.suite.cases[0].decision == "pack_materialized_with_targeted_backflow"


def test_artifact_hash_mismatch_does_not_promote_passed_block(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    catalog, mapping = _inputs(repo)
    doc = yaml.safe_load(mapping.read_text(encoding="utf-8"))
    doc["artifact_bindings"]["forecast_bridge"]["artifact_sha256"] = "f" * 64
    _yaml(mapping, doc)
    artifacts = _suite(repo, catalog, mapping)
    pack = artifacts.packs["fixture_case"]
    assert pack["forecast_bridge"]["status"] == "blocked"
    assert any("HASH_MISMATCH" in issue.code for issue in artifacts.suite.cases[0].issues)


def test_review_mapping_requires_real_identity_and_time(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    catalog, mapping = _inputs(repo)
    doc = yaml.safe_load(mapping.read_text(encoding="utf-8"))
    doc["pack_review"]["reviewer"] = ""
    doc["pack_review"]["reviewed_at"] = "not-a-time"
    _yaml(mapping, doc)
    artifacts = _suite(repo, catalog, mapping)
    case = artifacts.suite.cases[0]
    assert case.mapping_valid is False
    assert case.pack_materialized is False
    assert any(issue.code == "REVIEW_MAPPING_UNREVIEWED" for issue in case.issues)


def test_deterministic_output_tree_is_byte_identical(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    catalog, mapping = _inputs(repo)
    first = _suite(repo, catalog, mapping)
    second = _suite(repo, catalog, mapping)
    out_a = tmp_path / "out-a"
    out_b = tmp_path / "out-b"
    write_materialization_outputs(out_a, first)
    write_materialization_outputs(out_b, second)
    files_a = sorted(path.relative_to(out_a) for path in out_a.rglob("*") if path.is_file())
    files_b = sorted(path.relative_to(out_b) for path in out_b.rglob("*") if path.is_file())
    assert files_a == files_b
    for relative in files_a:
        assert (out_a / relative).read_bytes() == (out_b / relative).read_bytes()
    assert first.generation_lock["generation_id"] == second.generation_lock["generation_id"]


def test_atomic_pack_publish_is_idempotent(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates"
    destination = tmp_path / "packs"
    _yaml(candidates / "case.yaml", {"value": 1})
    published = atomic_publish_packs(candidates, destination)
    assert published == [destination / "case.yaml"]
    first_hash = sha256_file(destination / "case.yaml")
    atomic_publish_packs(candidates, destination)
    assert sha256_file(destination / "case.yaml") == first_hash
    assert not list(destination.glob(".*.tmp"))


def test_catalog_csv_aliases_are_supported(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    source = _write(repo / "data/raw/fixture.txt", "official\n")
    csv_path = repo / "data/processed/normalized/catalog.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "evidence_id",
                "source_type",
                "official",
                "review_status",
                "raw_path",
                "file_sha256",
                "publication_date",
                "covered_period",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "evidence_id": "src_csv",
                "source_type": "issuer_exchange_filings",
                "official": "true",
                "review_status": "accepted",
                "raw_path": source.relative_to(repo).as_posix(),
                "file_sha256": sha256_file(source),
                "publication_date": "2026-01-01",
                "covered_period": "FY2025",
            }
        )
    catalog = load_catalog([csv_path], repo_root=repo, policy_document={})
    assert "src_csv" in catalog.sources


def test_repository_manifest_and_research_input_aliases_are_supported(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    source = _write(repo / "data/raw/annual_reports/fixture.pdf", "official filing\n")
    manifest = repo / "data/manifests/evidence_manifest.csv"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "evidence_id",
                "source_type",
                "source_group",
                "review_status",
                "raw_file_path",
                "file_hash",
                "publish_date",
                "as_of_date",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "evidence_id": "src_manifest",
                "source_type": "annual_report",
                "source_group": "official_disclosure",
                "review_status": "reviewed",
                "raw_file_path": source.relative_to(repo).as_posix(),
                "file_hash": sha256_file(source),
                "publish_date": "2026-04-01",
                "as_of_date": "2025-12-31",
            }
        )
    research_input = _yaml(
        repo / "reports/workflow_runs/example/bundle16r/research_input.yaml",
        {
            "company_metrics": [
                {
                    "metric_id": "metric_manifest",
                    "evidence_id": "src_manifest",
                    "name": "reported revenue",
                    "period": "2025A",
                    "unit": "CNY",
                    "value": 1,
                }
            ]
        },
    )

    catalog = load_catalog([manifest, research_input], repo_root=repo, policy_document={})

    assert catalog.sources["src_manifest"]["official"] is True
    assert catalog.sources["src_manifest"]["source_class"] == "issuer_exchange_filings"
    assert catalog.sources["src_manifest"]["review_status"] == "reviewed"
    assert "metric_manifest" in catalog.records


def test_equal_duplicate_catalog_rows_are_deduplicated(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    catalog, _ = _inputs(repo)
    doc = yaml.safe_load(catalog.read_text(encoding="utf-8"))
    doc["sources"].append(deepcopy(doc["sources"][0]))
    doc["records"].append(deepcopy(doc["records"][0]))
    _yaml(catalog, doc)
    loaded = load_catalog([catalog], repo_root=repo, policy_document={})
    assert loaded.duplicate_source_count == 1
    assert loaded.duplicate_record_count == 1


def test_conflicting_duplicate_catalog_rows_are_blocking(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    catalog, mapping = _inputs(repo)
    doc = yaml.safe_load(catalog.read_text(encoding="utf-8"))
    conflict = deepcopy(doc["records"][0])
    conflict["value"] = 999
    doc["records"].append(conflict)
    _yaml(catalog, doc)
    artifacts = _suite(repo, catalog, mapping)
    assert any(issue.code == "CATALOG_RECORD_CONFLICT" for issue in artifacts.suite.cases[0].issues)
    assert artifacts.suite.cases[0].blocker_count > 0


def test_unsafe_absolute_or_parent_source_path_is_rejected(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    catalog, mapping = _inputs(repo)
    doc = yaml.safe_load(catalog.read_text(encoding="utf-8"))
    doc["sources"][0]["archive_path"] = "../outside.txt"
    _yaml(catalog, doc)
    artifacts = _suite(repo, catalog, mapping)
    assert any(issue.code == "SOURCE_PATH_INVALID" for issue in artifacts.suite.cases[0].issues)


def test_no_mapping_of_context_only_record_can_qualify_driver(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    catalog, mapping = _inputs(repo)
    doc = yaml.safe_load(mapping.read_text(encoding="utf-8"))
    doc["record_bindings"][0]["status"] = "context_only"
    _yaml(mapping, doc)
    artifacts = _suite(repo, catalog, mapping)
    assert "volume" in artifacts.suite.cases[0].missing_driver_ids


def test_cli_rejects_wrong_exact_baseline(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True)
    script = Path(__file__).resolve().parents[1] / "scripts/run_r5_bundle16r_evidence_pack_materializer.py"
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            str(script),
            "--repo-root",
            str(repo),
            "--output-dir",
            str(tmp_path / "out"),
            "--expected-base",
            BASELINE,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert "Git HEAD mismatch" in completed.stderr


def test_runtime_implementation_contains_no_golden_issuer_tokens() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "src/research/r5_bundle16r_evidence_pack_materializer.py").read_text(encoding="utf-8")
    for token in ("铜冠铜箔", "赤峰黄金", "药明康德", "东阳光", "301217", "600988", "603259", "600673"):
        assert token not in text


def test_generation_lock_and_status_proposal_never_open_release(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    catalog, mapping = _inputs(repo)
    artifacts = _suite(repo, catalog, mapping)
    lock = artifacts.generation_lock
    proposal = artifacts.status_proposal
    assert lock["release_authority"] is False
    assert lock["sample_quality_allowed"] is False
    assert lock["p2_allowed"] is False
    assert proposal["canonical_workflow_state_mutation_allowed"] is False
    assert proposal["sample_quality_allowed"] is False
    assert proposal["p2_allowed"] is False


def test_mapping_loader_rejects_duplicate_case_mapping(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    catalog, mapping = _inputs(repo)
    duplicate = repo / "reports/reviewed_mappings/duplicate.yaml"
    duplicate.write_bytes(mapping.read_bytes())
    with pytest.raises(MaterializationContractError, match="duplicate review mapping"):
        materialize_suite(
            repo_root=repo,
            cases_dir=repo / "tests/fixtures/r5_bundle14r/cases",
            catalog_paths=[catalog],
            mapping_paths=[mapping, duplicate],
            policy_document={},
            baseline_commit=BASELINE,
        )
