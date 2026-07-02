from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_evidence_ingest_contract_files_exist() -> None:
    root = repo_root()
    required = [
        ".agents/skills/evidence-ingest/SKILL.md",
        ".agents/skills/evidence-ingest/references/source_types.md",
        ".agents/skills/evidence-ingest/references/source_registry_contract.md",
        ".agents/skills/evidence-ingest/references/ingest_modes.md",
        ".agents/skills/evidence-ingest/references/storage_manifest_contract.md",
        ".agents/skills/evidence-ingest/references/candidate_generation_contract.md",
        ".agents/skills/evidence-ingest/references/ingest_quality_gate.md",
        ".agents/skills/evidence-ingest/scripts/compute_hash.py",
        ".agents/skills/evidence-ingest/scripts/validate_manifest.py",
        ".agents/skills/evidence-ingest/scripts/validate_candidates.py",
        ".agents/skills/evidence-ingest/assets/evidence_manifest.example.csv",
        ".agents/skills/evidence-ingest/assets/claim_candidates.example.csv",
        ".agents/skills/evidence-ingest/assets/metric_candidates.example.csv",
    ]
    missing = [p for p in required if not (root / p).exists()]
    assert not missing, f"Missing Phase B1 files: {missing}"


def test_evidence_ingest_skill_front_matter() -> None:
    skill = repo_root() / ".agents/skills/evidence-ingest/SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "SKILL.md must have YAML front matter"
    assert "name: evidence-ingest" in text
    assert "description:" in text
    assert "Do not use when" in text
    assert "No buy/sell/hold" in text or "buy/sell/hold" in text


def test_b1_debug_cases_pass() -> None:
    root = repo_root()
    script = root / ".agents/skills/evidence-ingest/scripts/run_debug_cases.py"
    result = subprocess.run([sys.executable, str(script), "--repo", str(root)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert result.returncode == 0, result.stdout
    assert "B1_DEBUG_READOUT=PASS" in result.stdout
