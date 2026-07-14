from pathlib import Path

from scripts.integrate_r5_bundle11r_workflow import BEGIN, integrate

TARGETS = [
    "docs/workflows/RESEARCH_WORKFLOW.md",
    "docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md",
    ".agents/skills/research-orchestrator/SKILL.md",
    ".agents/skills/stock-deep-dive/SKILL.md",
    ".agents/skills/quality-review/SKILL.md",
]


def test_integration_is_idempotent_and_writes_only_marked_blocks(tmp_path: Path) -> None:
    for relative in TARGETS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {relative}\noriginal\n", encoding="utf-8")
    preview = integrate(tmp_path, write=False)
    assert all(item["action"] == "would_append" for item in preview["changes"])
    backup = tmp_path / "backups"
    first = integrate(tmp_path, write=True, backup_root=backup)
    assert all(item["action"] == "appended" for item in first["changes"])
    second = integrate(tmp_path, write=True, backup_root=backup)
    assert all(item["action"] == "already_integrated" for item in second["changes"])
    for relative in TARGETS:
        text = (tmp_path / relative).read_text(encoding="utf-8")
        assert text.count(BEGIN) == 1
        assert "original" in text


def test_integration_restores_prior_files_when_a_later_target_is_missing(tmp_path: Path) -> None:
    # Deliberately omit the final quality-review target so integration fails after prior writes.
    existing = TARGETS[:-1]
    originals = {}
    for relative in existing:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        text = f"# {relative}\noriginal\n"
        path.write_text(text, encoding="utf-8")
        originals[relative] = text
    backup = tmp_path / "backups"
    try:
        integrate(tmp_path, write=True, backup_root=backup)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("expected missing target to trigger rollback")
    for relative, expected in originals.items():
        assert (tmp_path / relative).read_text(encoding="utf-8") == expected
