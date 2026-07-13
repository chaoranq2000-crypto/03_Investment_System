from pathlib import Path

import yaml

from src.ingest.adapter_contracts import validate_contract_registry


ROOT = Path(__file__).resolve().parents[1]


def test_adapter_contract_registry_is_structurally_valid() -> None:
    registry = yaml.safe_load((ROOT / "config/adapter_contract_registry.yaml").read_text(encoding="utf-8"))
    issues = validate_contract_registry(registry, repo_root=ROOT)
    assert not [item for item in issues if item["severity"] in {"critical", "high"}], issues


def test_ready_binding_requires_all_operational_receipts() -> None:
    payload = {
        "adapters": {
            "bad": {
                "module": "x",
                "entrypoint": "main",
                "default_status": "planned",
                "source_bindings": {"s": {"status": "operational", "supported_endpoint_hints": ["x"]}},
            }
        }
    }
    issues = validate_contract_registry(payload)
    assert any(item["issue_id"] == "OPERATIONAL_PROOF_MISSING" for item in issues)
    assert any(item["issue_id"] == "OPERATIONAL_PROOF_PATH_MISSING" for item in issues)


def test_ready_binding_rejects_missing_proof_file() -> None:
    payload = {
        "adapters": {
            "bad": {
                "module": "x",
                "entrypoint": "main",
                "default_status": "planned",
                "source_bindings": {
                    "s": {
                        "status": "operational",
                        **{field: True for field in (
                            "fixture_verified", "live_smoke_verified", "raw_archive_verified",
                            "manifest_write_verified", "schema_fingerprint_verified",
                            "claim_boundary_verified",
                        )},
                        "proof_paths": ["reports/quality/does_not_exist.yaml"],
                    }
                },
            }
        }
    }
    issues = validate_contract_registry(payload, repo_root=ROOT)
    assert any(item["issue_id"] == "OPERATIONAL_PROOF_PATH_INVALID" for item in issues)
