from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "ingest"))

from structured_api_pull import main as structured_main  # noqa: E402


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_plan_dry_run_blocks_missing_tushare_token_without_leaking_value(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    plan = tmp_path / "data_request_plan.yaml"
    plan.write_text(
        yaml.safe_dump(
            {
                "workflow_id": "wf_test",
                "object": {
                    "stock_code": "002837",
                    "company_id": "cn_002837_invic",
                    "company_name": "Invic",
                },
                "time_range": {"as_of_date": "2026-07-01"},
                "source_layers": {
                    "structured_database": {
                        "primary": "tushare",
                        "token_env": "TUSHARE_TOKEN",
                        "APIs": {"tushare": ["income"]},
                    }
                },
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    readout = tmp_path / "dry_run.json"

    structured_main(
        [
            "--repo-root",
            str(tmp_path),
            "--plan",
            str(plan),
            "--dry-run",
            "--readout-output",
            str(readout),
        ]
    )

    payload = json.loads(readout.read_text(encoding="utf-8"))
    assert payload["source_name"] == "tushare"
    assert payload["api_name"] == "income"
    assert payload["result"] == "BLOCKED"
    assert payload["params"]["token_env"] == "TUSHARE_TOKEN"
    assert "token_value" not in readout.read_text(encoding="utf-8")


def test_fixture_manifest_enums_pass_validator(tmp_path: Path) -> None:
    fixture = tmp_path / "income_fixture.csv"
    fixture.write_text(
        "ts_code,end_date,total_revenue,n_income_attr_p\n"
        "002837.SZ,20251231,1000,120\n",
        encoding="utf-8",
    )

    structured_main(
        [
            "--repo-root",
            str(tmp_path),
            "--source-name",
            "local_fixture",
            "--api-name",
            "income",
            "--stock-code",
            "002837",
            "--company-id",
            "cn_002837_invic",
            "--input-csv",
            str(fixture),
            "--as-of-date",
            "2026-07-01",
            "--publish-date",
            "2026-07-01",
            "--unit",
            "CNY",
        ]
    )

    manifest_path = tmp_path / "data" / "manifests" / "evidence_manifest.csv"
    manifest = read_csv(manifest_path)
    assert manifest[0]["raw_archive_policy"] == "snapshot_archived"
    assert manifest[0]["source_group"] == "structured_database"
    assert manifest[0]["allowed_claim_types"] == "metric_statement"
    assert manifest[0]["parse_status"] == "parsed"
    assert manifest[0]["candidate_status"] == "generated"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / ".agents/skills/evidence-ingest/scripts/validate_manifest.py"),
            "--repo",
            str(tmp_path),
            str(manifest_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert result.returncode == 0, result.stdout
