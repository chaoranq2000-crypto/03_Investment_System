from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_r5_v1_policy_refresh_002837.py"
VALIDATOR = (
    ROOT
    / ".agents"
    / "skills"
    / "research-orchestrator"
    / "scripts"
    / "validate_workflow_state.py"
)
SEGMENT_EXPOSURE_VALIDATOR = (
    ROOT
    / ".agents"
    / "skills"
    / "segment-company-mapping"
    / "scripts"
    / "validate_segment_exposure.py"
)
STOCK_PACK_VALIDATOR = (
    ROOT
    / ".agents"
    / "skills"
    / "stock-deep-dive"
    / "scripts"
    / "validate_r5_stock_research_pack.py"
)
CANONICAL_INDEX = ROOT / "config" / "r5_readout_canonical_index.yaml"

WORKFLOW_ID = "wf_20260725_stock_first_002837_v1_policy_refresh"
TARGET_RUN_REL = Path("reports") / "workflow_runs" / WORKFLOW_ID
CANONICAL_RUN = ROOT / TARGET_RUN_REL

EXPECTED_OUTPUT_PATHS = {
    "workflow_state.yaml",
    "artifact_manifest.csv",
    "open_todos.csv",
    "quality_gate_report.md",
    "run_log.md",
    "workflow_readout.md",
    "inputs/input_provenance.csv",
    "research/disclosed_facts.yaml",
    "research/limitations.yaml",
    "research/issue_change_log.csv",
    "research/stock_research_pack.yaml",
    "research/segment_exposure.yaml",
    "research/stock_report_draft.md",
    "research/backflow_decision.yaml",
    "validation/artifact_hashes.csv",
    "validation/replay_receipt.yaml",
    "validation/idempotence_report.yaml",
}

MANIFEST_REL = Path("data/manifests/evidence_manifest.csv")
ANNUAL_RAW_REL = Path(
    "data/raw/annual_reports/"
    "cninfo_2025_annual_report_full_002837_2026-04-21.pdf"
)
ANNUAL_TEXT_REL = Path(
    "data/processed/text/002837/"
    "cninfo_2025_annual_report_full_002837_2026-04-21.txt"
)
INTERIM_RAW_REL = Path(
    "data/raw/announcements/"
    "cninfo_2025_interim_report_full_002837_2025-08-19.pdf"
)
INTERIM_TEXT_REL = Path(
    "data/processed/text/002837/"
    "cninfo_2025_interim_report_full_002837_2025-08-19.txt"
)
MINIMAL_INPUT_PATHS = (
    MANIFEST_REL,
    ANNUAL_RAW_REL,
    ANNUAL_TEXT_REL,
    INTERIM_RAW_REL,
    INTERIM_TEXT_REL,
)

EXPECTED_PROVENANCE = {
    "ev_annual_report_002837_20260421_2cbfc5": {
        "raw_path": ANNUAL_RAW_REL.as_posix(),
        "raw_sha256": (
            "2cbfc5dc8a60b01212b68d930fb06d0a25bd74563cd1942bd87161246c3a1472"
        ),
        "processed_path": ANNUAL_TEXT_REL.as_posix(),
        "processed_file_sha256": (
            "0218a5ce464eb23d869ff0fb97b4e7233d0d2f02758eb2e9016d70b525f0f0bb"
        ),
        "processed_canonical_sha256": (
            "503b62a47363ca5c985a22980e4eb36fe883821db92d1d9febe0fffb74224876"
        ),
    },
    "ev_interim_report_002837_20250819_47054e": {
        "raw_path": INTERIM_RAW_REL.as_posix(),
        "raw_sha256": (
            "47054e736c74130385e4cab67f04708599c4bae0df5599b4446614039b3f0ffb"
        ),
        "processed_path": INTERIM_TEXT_REL.as_posix(),
        "processed_file_sha256": (
            "1c26dcc25fe19fa761c72bd709a8dd5d7c703b4f3aca2a0e09241f413cf8c58f"
        ),
        "processed_canonical_sha256": (
            "30c20a4350f114143b4bd7634ce39489a6dba2ed0fd937bb830b52288c858653"
        ),
    },
}

EXPECTED_ISSUES = {
    "R5V1P3-G3-001": {
        "historical_issue_id": "R5B13R-G3-001",
        "gate_id": "G3",
        "active_disposition": "unknown",
        "impact_scope": "claim",
        "affected_capabilities": {
            "room_cooling_driver_disaggregation",
            "cabinet_cooling_driver_disaggregation",
        },
    },
    "R5V1P3-G3-002": {
        "historical_issue_id": "R5B13R-G3-002",
        "gate_id": "G3",
        "active_disposition": "method_unavailable",
        "impact_scope": "method",
        "affected_capabilities": {"liquid_driver_model"},
    },
    "R5V1P3-G6-001": {
        "historical_issue_id": "R5B13R-G6-001",
        "gate_id": "G6",
        "active_disposition": "method_unavailable",
        "impact_scope": "method",
        "affected_capabilities": {
            "room_liquid_exact_allocation",
            "cross_line_aggregation",
        },
    },
    "R5V1P3-G6-002": {
        "historical_issue_id": "R5B13R-G6-002",
        "gate_id": "G6",
        "active_disposition": "unknown",
        "impact_scope": "claim",
        "affected_capabilities": {"cabinet_liquid_relationship"},
    },
}

EXPECTED_FACTS = {
    "room_cooling_revenue": {
        "value": Decimal("3448477492.62"),
        "unit": "CNY",
        "period": "2025A",
        "page_no": 15,
        "evidence_id": "ev_annual_report_002837_20260421_2cbfc5",
        "locator_fragment": "3,448,477,492.62",
        "comparison_operator": "equal",
    },
    "room_cooling_revenue_share": {
        "value": Decimal("56.83"),
        "unit": "percent",
        "period": "2025A",
        "page_no": 15,
        "evidence_id": "ev_annual_report_002837_20260421_2cbfc5",
        "locator_fragment": "56.83%",
        "comparison_operator": "equal",
    },
    "room_cooling_cost": {
        "value": Decimal("2470650226.09"),
        "unit": "CNY",
        "period": "2025A",
        "page_no": 16,
        "evidence_id": "ev_annual_report_002837_20260421_2cbfc5",
        "locator_fragment": "2,470,650,226.09",
        "comparison_operator": "equal",
    },
    "room_cooling_gross_margin": {
        "value": Decimal("28.36"),
        "unit": "percent",
        "period": "2025A",
        "page_no": 16,
        "evidence_id": "ev_annual_report_002837_20260421_2cbfc5",
        "locator_fragment": "28.36%",
        "comparison_operator": "equal",
    },
    "cabinet_cooling_revenue": {
        "value": Decimal("1977423139.19"),
        "unit": "CNY",
        "period": "2025A",
        "page_no": 15,
        "evidence_id": "ev_annual_report_002837_20260421_2cbfc5",
        "locator_fragment": "1,977,423,139.19",
        "comparison_operator": "equal",
    },
    "cabinet_cooling_revenue_share": {
        "value": Decimal("32.59"),
        "unit": "percent",
        "period": "2025A",
        "page_no": 15,
        "evidence_id": "ev_annual_report_002837_20260421_2cbfc5",
        "locator_fragment": "32.59%",
        "comparison_operator": "equal",
    },
    "cabinet_cooling_cost": {
        "value": Decimal("1438783613.25"),
        "unit": "CNY",
        "period": "2025A",
        "page_no": 16,
        "evidence_id": "ev_annual_report_002837_20260421_2cbfc5",
        "locator_fragment": "1,438,783,613.25",
        "comparison_operator": "equal",
    },
    "cabinet_cooling_gross_margin": {
        "value": Decimal("27.24"),
        "unit": "percent",
        "period": "2025A",
        "page_no": 16,
        "evidence_id": "ev_annual_report_002837_20260421_2cbfc5",
        "locator_fragment": "27.24%",
        "comparison_operator": "equal",
    },
    "precision_temperature_control_industry_sales_volume": {
        "value": Decimal("324058"),
        "unit": "unit",
        "period": "2025A",
        "page_no": 16,
        "evidence_id": "ev_annual_report_002837_20260421_2cbfc5",
        "locator_fragment": "销售量 台 324,058",
        "comparison_operator": "equal",
    },
    "liquid_cooling_related_revenue": {
        "value": Decimal("200000000"),
        "unit": "CNY",
        "period": "2025H1",
        "page_no": 9,
        "evidence_id": "ev_interim_report_002837_20250819_47054e",
        "locator_fragment": "液冷相关营业收入超过 2 亿元",
        "comparison_operator": "greater_than",
    },
}


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_r5_v1_policy_refresh_002837",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_official_processed_text_receipts_use_cross_platform_crlf_checkout() -> None:
    paths = [
        "data/processed/text/002837/"
        "cninfo_2025_annual_report_full_002837_2026-04-21.txt",
        "data/processed/text/002837/"
        "cninfo_2025_interim_report_full_002837_2025-08-19.txt",
    ]
    completed = subprocess.run(
        ["git", "check-attr", "text", "eol", "--", *paths],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    for path in paths:
        assert f"{path}: text: set" in completed.stdout
        assert f"{path}: eol: crlf" in completed.stdout


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_lf_sha256(path: Path) -> str:
    payload = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(payload).hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def copy_minimal_repo(destination: Path) -> dict[str, str]:
    before: dict[str, str] = {}
    for relative_path in MINIMAL_INPUT_PATHS:
        source = ROOT / relative_path
        target = destination / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        before[relative_path.as_posix()] = sha256_file(target)
    return before


def normalise_period(value: Any) -> str:
    return str(value).strip().removesuffix("A")


def parse_capabilities(value: Any) -> set[str]:
    if isinstance(value, list):
        return {str(item) for item in value}
    return {item for item in str(value).split("|") if item}


def is_sha256(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value)))


@pytest.fixture(scope="module")
def built_refresh(tmp_path_factory: pytest.TempPathFactory):
    runner = load_runner()
    output_a = tmp_path_factory.mktemp("r5_v1_policy_refresh_a") / "run"
    output_b = tmp_path_factory.mktemp("r5_v1_policy_refresh_b") / "run"
    result_a = runner.materialize_refresh(ROOT, output_a)
    result_b = runner.materialize_refresh(ROOT, output_b)
    return runner, output_a, result_a, output_b, result_b


def test_control_plane_status_and_current_validator(built_refresh) -> None:
    runner, output, result, _, _ = built_refresh
    assert runner.WORKFLOW_ID == WORKFLOW_ID
    assert Path(runner.TARGET_RUN_REL) == TARGET_RUN_REL
    assert {
        Path(str(path)).as_posix() for path in runner.EXPECTED_ARTIFACT_PATHS
    } == EXPECTED_OUTPUT_PATHS
    assert set(tree_hashes(output)) == EXPECTED_OUTPUT_PATHS

    state = yaml.safe_load((output / "workflow_state.yaml").read_text(encoding="utf-8"))
    assert state["workflow_id"] == WORKFLOW_ID
    assert state["state_schema_version"] == "r5_v1"
    assert state["decision_semantics_version"] == "current_goal_v1"
    assert (
        state["final_report_review_semantics_version"]
        == "final_report_review_v1"
    )
    assert state["status"] == result["status"] == "accepted_with_todos"
    assert state["automated_report_quality_passed"] is True
    assert state["system_v1_complete"] is False
    assert state["sample_quality_ready"] is False
    assert state["p2_ready"] is False
    assert state["release_ready"] is False
    assert state["final_report_review_status"] == "not_requested"
    assert state["final_report_review"] == {
        "report_path": None,
        "report_sha256": None,
        "reviewer": None,
        "reviewed_at": None,
        "decision": "not_requested",
        "notes": None,
        "change_scope": None,
    }
    for retired_field in (
        "human_review_status",
        "sample_quality_allowed",
        "p2_allowed",
    ):
        assert retired_field not in state

    expected_gates = {
        **{f"G{index}": "pass" for index in range(5)},
        "G5": "not_applicable",
        **{f"G{index}": "pass" for index in range(6, 11)},
    }
    gates = {row["gate_id"]: row["status"] for row in state["quality_gates"]}
    assert gates == expected_gates
    quality_report = (output / "quality_gate_report.md").read_text(encoding="utf-8")
    for gate_id, gate_status in expected_gates.items():
        assert re.search(
            rf"\|\s*{re.escape(gate_id)}\s*\|\s*{re.escape(gate_status)}\s*\|",
            quality_report,
        )

    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    completed = subprocess.run(
        [sys.executable, "-B", str(VALIDATOR), str(output / "workflow_state.yaml")],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr
    assert "OK" in completed.stdout


def test_active_stock_pack_and_segment_exposure_validators(built_refresh) -> None:
    _, output, _, _, _ = built_refresh
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    segment = subprocess.run(
        [
            sys.executable,
            "-B",
            str(SEGMENT_EXPOSURE_VALIDATOR),
            str(output / "research/segment_exposure.yaml"),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        env=env,
    )
    assert segment.returncode == 0, segment.stderr
    assert "outcome: accepted_with_todos" in segment.stdout

    stock_pack = subprocess.run(
        [
            sys.executable,
            "-B",
            str(STOCK_PACK_VALIDATOR),
            "--pack",
            str(output / "research/stock_research_pack.yaml"),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        env=env,
    )
    assert stock_pack.returncode == 0, stock_pack.stdout + stock_pack.stderr
    payload = json.loads(stock_pack.stdout)
    assert payload["decision"] == "accepted_with_todos"
    assert payload["issues"] == []


def test_exact_official_sources_and_hashes(built_refresh) -> None:
    runner, output, _, _, _ = built_refresh
    fields, rows = read_csv(output / "inputs/input_provenance.csv")
    assert {
        "input_kind",
        "evidence_id",
        "source_type",
        "source_group",
        "review_status",
        "source_path",
        "hash_scope",
        "expected_sha256",
        "observed_sha256",
        "file_sha256",
        "paired_input_path",
        "usage_boundary",
    }.issubset(fields)
    assert len(rows) == 4
    assert {row["evidence_id"] for row in rows} == set(EXPECTED_PROVENANCE)

    for evidence_id, expected in EXPECTED_PROVENANCE.items():
        evidence_rows = [row for row in rows if row["evidence_id"] == evidence_id]
        assert len(evidence_rows) == 2
        raw = next(
            row for row in evidence_rows if row["input_kind"] == "raw_official_pdf"
        )
        processed = next(
            row
            for row in evidence_rows
            if row["input_kind"] == "processed_official_text"
        )
        for row in evidence_rows:
            assert row["source_group"] == "official_disclosure"
            assert row["review_status"] == "reviewed"
            assert row["expected_sha256"] == row["observed_sha256"]
            assert "official" in row["usage_boundary"].lower()
        assert raw["source_path"] == expected["raw_path"]
        assert raw["paired_input_path"] == expected["processed_path"]
        assert raw["hash_scope"] == "file_bytes"
        assert raw["observed_sha256"] == expected["raw_sha256"]
        assert raw["file_sha256"] == expected["raw_sha256"]
        assert runner.sha256_file(ROOT / raw["source_path"]) == raw["observed_sha256"]
        assert processed["source_path"] == expected["processed_path"]
        assert processed["paired_input_path"] == expected["raw_path"]
        assert processed["hash_scope"] == "canonical_lf_text_bytes"
        assert (
            processed["observed_sha256"]
            == expected["processed_canonical_sha256"]
        )
        assert processed["file_sha256"] == expected["processed_file_sha256"]
        assert (
            canonical_lf_sha256(ROOT / processed["source_path"])
            == processed["observed_sha256"]
        )
        assert "fixture" not in (
            raw["source_path"] + processed["source_path"]
        ).lower()


def test_disclosed_facts_have_exact_values_pages_units_and_locators(
    built_refresh,
) -> None:
    runner, output, _, _, _ = built_refresh
    document = yaml.safe_load(
        (output / "research/disclosed_facts.yaml").read_text(encoding="utf-8")
    )
    facts = document["facts"]
    by_key = {row["metric"]: row for row in facts}
    assert len(by_key) == len(facts)
    assert set(by_key) == set(EXPECTED_FACTS) | {
        "room_liquid_classification_relationship"
    }

    for key, expected in EXPECTED_FACTS.items():
        fact = by_key[key]
        assert fact["claim_type"] == "fact"
        assert Decimal(str(fact["value"])) == expected["value"]
        assert fact["unit"] == expected["unit"]
        assert str(fact["period"]) == expected["period"]
        assert int(fact["page_no"]) == expected["page_no"]
        assert fact["evidence_id"] == expected["evidence_id"]
        assert fact["comparison_operator"] == expected["comparison_operator"]

        provenance = EXPECTED_PROVENANCE[fact["evidence_id"]]
        assert fact["source_path"] == provenance["raw_path"]
        assert fact["processed_text_path"] == provenance["processed_path"]
        locator = fact["locator"]
        assert isinstance(locator, str) and len(locator) >= 12
        assert expected["locator_fragment"] in locator
        page_text = runner.resolve_printed_page(
            (ROOT / fact["processed_text_path"]).read_text(encoding="utf-8"),
            int(fact["page_no"]),
            locator,
        )
        assert isinstance(page_text, str)
        assert locator in page_text

    relationship = by_key["room_liquid_classification_relationship"]
    assert relationship["claim_type"] == "inference"
    assert relationship["value"] == "partial_overlap_confirmed"
    assert relationship["overlap_amount"] == "UNKNOWN_NOT_DISCLOSED"
    assert relationship["cabinet_relationship"] == "UNKNOWN_NOT_DISCLOSED"
    assert relationship["numeric_use"] == "prohibited"
    relationship_page = runner.resolve_printed_page(
        (ROOT / relationship["processed_text_path"]).read_text(encoding="utf-8"),
        int(relationship["page_no"]),
        relationship["locator"],
    )
    assert "部分计入“机房温控" in relationship_page
    assert "部分计入“其他”" in relationship_page

    pack = yaml.safe_load(
        (output / "research/stock_research_pack.yaml").read_text(encoding="utf-8")
    )
    business_lines = {
        row["business_name"]: row
        for row in pack["business_breakdown_pack"]["business_lines"]
    }
    expected_lines = {
        "机房温控节能产品": {
            "revenue": EXPECTED_FACTS["room_cooling_revenue"]["value"],
            "cost": EXPECTED_FACTS["room_cooling_cost"]["value"],
            "gross_margin": EXPECTED_FACTS["room_cooling_gross_margin"]["value"],
        },
        "机柜温控节能产品": {
            "revenue": EXPECTED_FACTS["cabinet_cooling_revenue"]["value"],
            "cost": EXPECTED_FACTS["cabinet_cooling_cost"]["value"],
            "gross_margin": EXPECTED_FACTS[
                "cabinet_cooling_gross_margin"
            ]["value"],
        },
    }
    assert set(business_lines) == set(expected_lines)
    for name, expected in expected_lines.items():
        line = business_lines[name]
        for metric in ("revenue", "cost", "gross_margin"):
            assert Decimal(str(line[metric]["value"])) == expected[metric]
        for undisclosed_metric in ("gross_profit", "gross_profit_pct"):
            assert line[undisclosed_metric] == {
                "value": None,
                "missing_reason": "MISSING_DISCLOSURE",
            }


def test_limitations_keep_unknown_numbers_unused_and_overlap_bounded(
    built_refresh,
) -> None:
    _, output, _, _, _ = built_refresh
    document = yaml.safe_load(
        (output / "research/limitations.yaml").read_text(encoding="utf-8")
    )
    limitations = {
        row["limitation_id"]: row for row in document["unknowns"]
    }
    assert {
        "lim_room_cabinet_driver_disaggregation",
        "lim_liquid_unit_economics",
        "lim_room_liquid_exact_allocation",
        "lim_cabinet_liquid_relationship",
    } <= limitations.keys()
    assert all(row["numeric_use"] == "prohibited" for row in limitations.values())

    line_drivers = limitations["lim_room_cabinet_driver_disaggregation"]
    assert line_drivers["status"] == "UNKNOWN_NOT_DISCLOSED"
    assert set(line_drivers["fields"]) == {
        "room_cooling_volume",
        "room_cooling_unit_price",
        "room_cooling_product_mix",
        "cabinet_cooling_volume",
        "cabinet_cooling_unit_price",
        "cabinet_cooling_product_mix",
    }
    assert "cannot be split" in line_drivers["reason"]

    liquid = limitations["lim_liquid_unit_economics"]
    assert liquid["status"] == "METHOD_UNAVAILABLE"
    assert set(liquid["fields"]) == {
        "liquid_unit_value",
        "liquid_acceptance_rate",
        "liquid_standalone_gross_margin",
    }

    room_liquid = limitations["lim_room_liquid_exact_allocation"]
    assert room_liquid["known_relationship"] == "partial_overlap_confirmed"
    assert set(room_liquid["fields"]) == {
        "overlap_revenue_amount",
        "overlap_gross_profit_amount",
    }

    cabinet_liquid = limitations["lim_cabinet_liquid_relationship"]
    assert cabinet_liquid["status"] == "UNKNOWN_NOT_DISCLOSED"
    assert set(cabinet_liquid["assertions_forbidden"]) == {
        "overlaps",
        "never_overlaps",
    }

    pack = yaml.safe_load(
        (output / "research/stock_research_pack.yaml").read_text(encoding="utf-8")
    )
    extension = pack["policy_refresh_extension"]
    assert extension["calculation_policy"]["calculations"] == []
    assert (
        extension["calculation_policy"]["cross_line_aggregation_allowed"]
        is False
    )
    assert extension["calculation_policy"]["unknown_values_used"] is False
    assert extension["industry_sales_volume"]["allocation_allowed"] is False
    relationships = extension["liquid_cooling_related"]["classification"]
    assert relationships["room_cooling"] == "partial_overlap_confirmed"
    assert relationships["cabinet_cooling"] == "UNKNOWN_NOT_DISCLOSED"
    assert pack["artifact_type"] == "R5_stock_research_pack"
    assert pack["pack_status"] == "research_draft"
    assert pack["quality_status"]["active_defect_count"] == 0
    assert pack["quality_status"]["descriptive_high_limitation_count"] == 4

    exposure = yaml.safe_load(
        (output / "research/segment_exposure.yaml").read_text(encoding="utf-8")
    )["exposures"][0]
    assert exposure["exposure_type"] == "revenue"
    assert exposure["exposure_score"] == 4
    assert exposure["confidence"] == "high"
    assert exposure["backflow_decision"] == "update_exposure"
    cabinet = exposure["line_relationships"]["cabinet_cooling"]
    assert cabinet == {
        "relationship": "UNKNOWN_NOT_DISCLOSED",
        "overlap_asserted": False,
        "never_overlap_asserted": False,
    }
    assert exposure["aggregation_allowed"] is False


def test_four_issues_are_reclassified_and_status_is_derived(built_refresh) -> None:
    runner, output, result, _, _ = built_refresh
    state = yaml.safe_load((output / "workflow_state.yaml").read_text(encoding="utf-8"))
    fields, csv_todos = read_csv(output / "open_todos.csv")
    assert {
        "issue_id",
        "severity",
        "stage",
        "gate_id",
        "description",
        "fix_owner_skill",
        "status",
        "impact_scope",
        "active_disposition",
        "affected_capabilities",
        "blocks_current_goal",
    }.issubset(fields)
    assert {row["issue_id"] for row in csv_todos} == set(EXPECTED_ISSUES)
    assert {row["issue_id"] for row in state["open_todos"]} == set(EXPECTED_ISSUES)

    state_by_id = {row["issue_id"]: row for row in state["open_todos"]}
    csv_by_id = {row["issue_id"]: row for row in csv_todos}
    for issue_id, expected in EXPECTED_ISSUES.items():
        state_row = state_by_id[issue_id]
        csv_row = csv_by_id[issue_id]
        assert state_row["historical_issue_id"] == expected["historical_issue_id"]
        assert state_row["severity"] == csv_row["severity"] == "high"
        assert state_row["status"] == csv_row["status"] == "open"
        assert state_row["gate_id"] == csv_row["gate_id"] == expected["gate_id"]
        assert (
            state_row["active_disposition"]
            == csv_row["active_disposition"]
            == expected["active_disposition"]
        )
        assert (
            state_row["impact_scope"]
            == csv_row["impact_scope"]
            == expected["impact_scope"]
        )
        assert state_row["blocks_current_goal"] is False
        assert csv_row["blocks_current_goal"].lower() == "false"
        assert (
            parse_capabilities(state_row["affected_capabilities"])
            == parse_capabilities(csv_row["affected_capabilities"])
            == expected["affected_capabilities"]
        )

    _, change_rows = read_csv(output / "research/issue_change_log.csv")
    assert {row["current_issue_id"] for row in change_rows} == set(EXPECTED_ISSUES)
    for row in change_rows:
        expected = EXPECTED_ISSUES[row["current_issue_id"]]
        assert row["prior_issue_id"] == expected["historical_issue_id"]
        assert row["change_type"] == "policy_reclassification"
        assert row["historical_resolved"].lower() == "false"
        assert row["current_disposition"] == expected["active_disposition"]
        assert row["impact_scope"] == expected["impact_scope"]
        assert row["blocks_current_goal"].lower() == "false"
        assert parse_capabilities(row["affected_capabilities"]) == expected[
            "affected_capabilities"
        ]
        assert row["rationale"].strip()
        assert row["numeric_use"] == "unused"

    cabinet_change = next(
        row
        for row in change_rows
        if row["prior_issue_id"] == "R5B13R-G6-002"
    )
    summary = cabinet_change["rationale"].lower()
    assert cabinet_change["current_disposition"] == "unknown"
    assert "overlaps" in cabinet_change["prior_assertion"].lower()
    assert "overlap" in summary
    assert "never_overlap_confirmed" not in summary

    assert runner.derive_status(state["open_todos"]) == "accepted_with_todos"
    assert result["status"] == state["status"] == "accepted_with_todos"


def test_derive_status_uses_scope_and_disposition_not_severity() -> None:
    runner = load_runner()

    def issue(
        disposition: str,
        *,
        scope: str,
        blocks: bool,
        description: str = "test issue",
    ) -> dict[str, Any]:
        return {
            "issue_id": "TEST-001",
            "severity": "high",
            "stage": "T9",
            "gate_id": "G7",
            "description": description,
            "fix_owner_skill": "quality-review",
            "status": "open",
            "impact_scope": scope,
            "active_disposition": disposition,
            "affected_capabilities": ["test_capability"],
            "blocks_current_goal": blocks,
        }

    assert runner.derive_status([]) == "accepted"
    assert (
        runner.derive_status([issue("unknown", scope="claim", blocks=False)])
        == "accepted_with_todos"
    )
    assert (
        runner.derive_status(
            [issue("method_unavailable", scope="method", blocks=False)]
        )
        == "accepted_with_todos"
    )
    assert (
        runner.derive_status(
            [issue("method_unavailable", scope="method", blocks=True)]
        )
        == "blocked"
    )
    assert (
        runner.derive_status(
            [issue("report_limitation", scope="report", blocks=False)]
        )
        == "accepted_with_todos"
    )
    assert (
        runner.derive_status([issue("unknown", scope="claim", blocks=True)])
        == "needs_fix"
    )
    for defect in (
        "unsupported used number",
        "true double count",
        "hidden TODO",
        "no-advice violation",
    ):
        assert (
            runner.derive_status(
                [
                    issue(
                        "active_defect",
                        scope="report",
                        blocks=True,
                        description=defect,
                    )
                ]
            )
            == "needs_fix"
        )
    assert (
        runner.derive_status(
            [
                issue(
                    "active_defect",
                    scope="workflow",
                    blocks=True,
                    description="source identity prevents honest output",
                )
            ]
        )
        == "blocked"
    )
    with pytest.raises(runner.ReplayContractError):
        runner.derive_status(
            [issue("method_unavailable", scope="claim", blocks=False)]
        )
    with pytest.raises(runner.ReplayContractError):
        runner.derive_status(
            [issue("active_defect", scope="report", blocks=False)]
        )


def test_two_unique_output_directories_are_byte_identical(built_refresh) -> None:
    _, output_a, result_a, output_b, result_b = built_refresh
    assert output_a.resolve() != output_b.resolve()
    assert tree_hashes(output_a) == tree_hashes(output_b)
    for field in ("semantic_digest", "status", "tree_digest"):
        assert result_a[field] == result_b[field]
    assert result_a["status"] == "accepted_with_todos"
    assert is_sha256(result_a["semantic_digest"])
    assert is_sha256(result_a["tree_digest"])
    for output in (output_a, output_b):
        all_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(output.rglob("*"))
            if path.is_file() and path.suffix.lower() in {".csv", ".md", ".yaml"}
        )
        assert str(output) not in all_text

    idempotence = yaml.safe_load(
        (output_a / "validation/idempotence_report.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert idempotence["decision"] == "pass"
    assert idempotence["semantic_drift_count"] == 0
    assert idempotence["allowed_normalizations"] == []
    assert idempotence["first_semantic_digest"] == result_a["semantic_digest"]
    assert idempotence["second_semantic_digest"] == result_a["semantic_digest"]


def test_minimal_repo_with_only_manifest_and_four_inputs_is_sufficient(
    tmp_path: Path,
) -> None:
    runner = load_runner()
    minimal_repo = tmp_path / "minimal_repo"
    source_hashes_before = copy_minimal_repo(minimal_repo)
    assert set(tree_hashes(minimal_repo)) == {
        path.as_posix() for path in MINIMAL_INPUT_PATHS
    }

    output = tmp_path / "isolated_output"
    result = runner.materialize_refresh(minimal_repo, output)
    assert result["status"] == "accepted_with_todos"
    assert set(tree_hashes(output)) == EXPECTED_OUTPUT_PATHS
    source_hashes_after = {
        relative_path: sha256_file(minimal_repo / relative_path)
        for relative_path in source_hashes_before
    }
    assert source_hashes_after == source_hashes_before


def test_source_tamper_and_locator_mismatch_fail_closed(tmp_path: Path) -> None:
    runner = load_runner()
    minimal_repo = tmp_path / "tampered_repo"
    copy_minimal_repo(minimal_repo)
    processed = minimal_repo / ANNUAL_TEXT_REL
    processed.write_bytes(processed.read_bytes() + b"\ntampered\n")
    with pytest.raises(runner.ReplayContractError, match=r"(?i)hash|sha[- ]?256"):
        runner.materialize_refresh(minimal_repo, tmp_path / "tampered_output")

    separator = r"\n\f\n"
    page_14 = "Example report\n14\nother content"
    page_15 = "Example report\n15\nunique locator value 3,448,477,492.62"
    page_16 = "Example report\n16\nnext page"
    text = separator.join((page_14, page_15, page_16))
    resolved = runner.resolve_printed_page(
        text,
        15,
        "unique locator value 3,448,477,492.62",
    )
    assert resolved == page_15
    with pytest.raises(runner.ReplayContractError):
        runner.resolve_printed_page(text, 16, "unique locator value")
    with pytest.raises(runner.ReplayContractError):
        runner.resolve_printed_page(text, 99, "missing page")
    duplicate = separator.join((page_15, page_15))
    with pytest.raises(runner.ReplayContractError):
        runner.resolve_printed_page(
            duplicate,
            15,
            "unique locator value 3,448,477,492.62",
        )


def test_artifact_manifest_and_hash_index_are_complete(built_refresh) -> None:
    runner, output, _, _, _ = built_refresh
    fields, manifest_rows = read_csv(output / "artifact_manifest.csv")
    assert {
        "artifact_id",
        "artifact_type",
        "path",
        "created_by_skill",
        "stage",
        "required",
        "exists",
        "status",
        "notes",
    }.issubset(fields)
    assert len(manifest_rows) == len(EXPECTED_OUTPUT_PATHS)
    assert len({row["artifact_id"] for row in manifest_rows}) == len(manifest_rows)
    assert len({row["path"] for row in manifest_rows}) == len(manifest_rows)

    prefix = TARGET_RUN_REL.as_posix() + "/"
    manifest_rel_paths: set[str] = set()
    for row in manifest_rows:
        assert row["path"].startswith(prefix)
        assert "\\" not in row["path"]
        relative_path = row["path"][len(prefix) :]
        manifest_rel_paths.add(relative_path)
        artifact_path = output / relative_path
        assert row["exists"] == "true"
        assert row["status"] == "current"
        assert artifact_path.is_file()
        if relative_path == "artifact_manifest.csv":
            assert "recursive self-hash intentionally omitted" in row["notes"]
        else:
            match = re.search(r"sha256=([0-9a-f]{64})", row["notes"])
            assert match, row
            assert match.group(1) == runner.sha256_file(artifact_path)
    assert manifest_rel_paths == EXPECTED_OUTPUT_PATHS

    hash_fields, hash_rows = read_csv(output / "validation/artifact_hashes.csv")
    assert {"path", "sha256", "bytes", "hash_scope", "source_trace"}.issubset(
        hash_fields
    )
    expected_hashed_paths = EXPECTED_OUTPUT_PATHS - {
        "artifact_manifest.csv",
        "validation/artifact_hashes.csv",
        "validation/replay_receipt.yaml",
        "validation/idempotence_report.yaml",
    }
    actual_hashed_paths: set[str] = set()
    for row in hash_rows:
        assert row["path"].startswith(prefix)
        relative_path = row["path"][len(prefix) :]
        actual_hashed_paths.add(relative_path)
        artifact_path = output / relative_path
        assert row["hash_scope"] == "file_bytes"
        assert row["sha256"] == runner.sha256_file(artifact_path)
        assert int(row["bytes"]) == artifact_path.stat().st_size
        assert row["source_trace"].strip()
    assert actual_hashed_paths == expected_hashed_paths


def test_checked_in_canonical_tree_matches_materializer(built_refresh) -> None:
    _, output, _, _, _ = built_refresh
    assert CANONICAL_RUN.is_dir()
    assert tree_hashes(CANONICAL_RUN) == tree_hashes(output)


def test_runner_has_no_historical_workflow_dependency() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    historical_workflow_ids = (
        "wf_" + "20260703_stock_first_002837_invic",
        "wf_" + "20260723_stock_first_002837_v1_replay",
    )
    for workflow_id in historical_workflow_ids:
        assert workflow_id not in source
    assert "run_r5_v1_replay_002837" not in source
    assert "SOURCE_RUN" not in source


def test_output_has_no_fake_human_review_or_trading_advice(built_refresh) -> None:
    _, output, _, _, _ = built_refresh
    state = yaml.safe_load((output / "workflow_state.yaml").read_text(encoding="utf-8"))
    review = state["final_report_review"]
    assert review["decision"] == "not_requested"
    assert review["reviewer"] is None
    assert review["reviewed_at"] is None
    assert review["report_path"] is None
    assert review["report_sha256"] is None

    _, manifest_rows = read_csv(output / "artifact_manifest.csv")
    report_row = next(
        row
        for row in manifest_rows
        if row["path"].endswith("/research/stock_report_draft.md")
    )
    assert report_row["artifact_type"] in {"report", "report_draft"}
    assert report_row["artifact_type"] != "final_report"

    report = (output / "research/stock_report_draft.md").read_text(
        encoding="utf-8"
    )
    lowered = report.lower()
    assert not re.search(r"\b(?:buy|sell|hold)\b", lowered)
    for prohibited in (
        "建议买入",
        "建议卖出",
        "建议持有",
        "仓位建议",
        "目标价",
        "保证收益",
    ):
        assert prohibited not in report
    assert "不构成投资建议" in report

    backflow = yaml.safe_load(
        (output / "research/backflow_decision.yaml").read_text(encoding="utf-8")
    )
    decision = backflow.get("backflow_decision", backflow.get("decision"))
    assert decision == "update_exposure"
    assert backflow["global_state_updated"] is False
    assert backflow["run_scoped_update_recorded"] is True


def test_protected_output_paths_are_rejected(tmp_path: Path) -> None:
    runner = load_runner()
    minimal_repo = tmp_path / "guard_repo"
    copy_minimal_repo(minimal_repo)
    historical_workflow_id = "wf_" + "20260703_stock_first_002837_invic"
    protected_outputs = (
        minimal_repo / "data/raw/policy_refresh_guard",
        minimal_repo / "data/processed/policy_refresh_guard",
        minimal_repo / "reports/workflow_runs" / historical_workflow_id,
    )
    for output_path in protected_outputs:
        with pytest.raises(runner.ReplayContractError, match="(?i)output|protected"):
            runner.materialize_refresh(minimal_repo, output_path)

    dirty_main_guard = (
        ROOT.parent
        / "03_Investment_System"
        / "reports"
        / "workflow_runs"
        / "policy_refresh_guard"
    )
    assert not dirty_main_guard.exists()
    with pytest.raises(runner.ReplayContractError, match="(?i)temporary"):
        runner.materialize_refresh(minimal_repo, dirty_main_guard)
    assert not dirty_main_guard.exists()


def test_canonical_index_points_to_current_policy_refresh() -> None:
    index = yaml.safe_load(CANONICAL_INDEX.read_text(encoding="utf-8"))
    pointer = index["current_runs"]["stock_002837"]
    assert pointer["workflow_id"] == WORKFLOW_ID
    assert pointer["state_path"] == (
        TARGET_RUN_REL / "workflow_state.yaml"
    ).as_posix()
    assert pointer["readout_path"] == (
        TARGET_RUN_REL / "workflow_readout.md"
    ).as_posix()
    assert pointer["status"] == "accepted_with_todos"
    historical_workflow_id = "wf_" + "20260703_stock_first_002837_invic"
    assert historical_workflow_id not in yaml.safe_dump(
        pointer,
        allow_unicode=True,
        sort_keys=True,
    )
