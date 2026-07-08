from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/r5_patch_inventory_check.py"


def load_inventory():
    spec = importlib.util.spec_from_file_location("r5_patch_inventory_check", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_inventory_distinguishes_validated_complete(tmp_path: Path):
    inventory = load_inventory()
    (tmp_path / "ok.yaml").write_text("schema_version: test\nartifact_type: ok\n", encoding="utf-8")
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (tmp_path / "readout.md").write_text("# Readout\n\nstatus: PASS\n", encoding="utf-8")
    config = {
        "patches": [
            {
                "patch_id": "TEST_PATCH",
                "claimed_status": "claimed_complete",
                "related_readout": "readout.md",
                "blocking_if_missing": True,
                "expected_artifacts": [
                    {"path": "ok.yaml", "artifact_type": "yaml", "required": True},
                    {"path": "test_ok.py", "artifact_type": "pytest", "required": True},
                ],
            }
        ]
    }

    report = inventory.reconcile_inventory(tmp_path, config)

    assert report["inventory_status"] == "validated_complete"
    assert report["accepted"] is True


def test_blocking_missing_artifact_prevents_acceptance(tmp_path: Path):
    inventory = load_inventory()
    (tmp_path / "readout.md").write_text("# Readout\n\nstatus: PASS\n", encoding="utf-8")
    config = {
        "patches": [
            {
                "patch_id": "TEST_PATCH",
                "claimed_status": "claimed_complete",
                "related_readout": "readout.md",
                "blocking_if_missing": True,
                "expected_artifacts": [
                    {"path": "missing.py", "artifact_type": "python", "required": True},
                ],
            }
        ]
    }

    report = inventory.reconcile_inventory(tmp_path, config)

    assert report["inventory_status"] == "claimed_complete_but_validation_failed"
    assert report["accepted"] is False
    assert report["patches"][0]["artifacts"][0]["status"] == "fail"


def test_one_line_yaml_is_a_failure(tmp_path: Path):
    inventory = load_inventory()
    (tmp_path / "one_line.yaml").write_text("schema_version: test", encoding="utf-8")

    result = inventory.validate_artifact(
        tmp_path,
        {"path": "one_line.yaml", "artifact_type": "yaml", "required": True},
    )

    assert result["status"] == "fail"
    assert any("line_count" in note for note in result["notes"])


def test_cli_writes_inventory_report(tmp_path: Path):
    inventory = load_inventory()
    (tmp_path / "ok.yaml").write_text("schema_version: test\nartifact_type: ok\n", encoding="utf-8")
    (tmp_path / "readout.md").write_text("# Readout\n\nstatus: PASS\n", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    out_path = tmp_path / "status.yaml"
    write_yaml(
        config_path,
        {
            "patches": [
                {
                    "patch_id": "TEST_PATCH",
                    "related_readout": "readout.md",
                    "blocking_if_missing": True,
                    "expected_artifacts": [
                        {"path": "ok.yaml", "artifact_type": "yaml", "required": True},
                    ],
                }
            ]
        },
    )

    exit_code = inventory.main(["--repo-root", str(tmp_path), "--config", str(config_path), "--out", str(out_path)])

    assert exit_code == 0
    assert out_path.exists()
    report = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert report["accepted"] is True
