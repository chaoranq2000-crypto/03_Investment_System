from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "AGENTS.md",
    "README.md",
    "pyproject.toml",
    ".env.example",
    ".gitignore",
    ".codex/config.toml",
    "docs/index.md",
    "docs/project/PROJECT_CHARTER.md",
    "docs/architecture/WORKSPACE_STRUCTURE.md",
    "docs/architecture/RESEARCH_OBJECT_MODEL.md",
    "docs/policies/EVIDENCE_AND_CITATION_POLICY.md",
    "docs/policies/QUALITY_GUARDRAILS.md",
    "docs/playbooks/OPERATING_PLAYBOOK.md",
    "docs/plans/plan_template.md",
    "docs/plans/p0_acceptance_checklist.md",
    "docs/plans/p0_execution_plan.md",
    "docs/logs/README.md",
    "docs/logs/2026-07-01_docs_structure_cleanup_log.md",
    "docs/logs/p0/2026-07-01_p0_preplanning_confirmation.md",
    "docs/logs/p0/2026-07-01_p0_smoke_test.md",
    "docs/logs/p0/2026-07-01_p0_closeout.md",
    "config/research_config.yaml",
    "config/segment_taxonomy.yaml",
    "config/source_registry.yaml",
    "config/metric_definitions.yaml",
    "config/scoring_frameworks.yaml",
    "config/watchlist.yaml",
    "templates/segment_report.md",
    "templates/stock_report.md",
    "templates/evidence_card.md",
    "templates/comparison_matrix.md",
    "templates/investment_memo.md",
    "decisions/thesis_log.md",
    "decisions/watchlist_changes.md",
    "data/manifests/evidence_manifest.csv",
    "data/manifests/refresh_log.csv",
]

REQUIRED_DIRS = [
    ".agents/skills",
    "docs/logs",
    "docs/logs/p0",
    "config",
    "data/raw/announcements",
    "data/raw/annual_reports",
    "data/raw/industry_reports",
    "data/raw/transcripts",
    "data/raw/market_data",
    "data/processed/text",
    "data/processed/tables",
    "data/processed/embeddings",
    "data/processed/normalized",
    "data/db",
    "data/manifests",
    "src/ingest",
    "src/extract",
    "src/normalize",
    "src/research",
    "src/scoring",
    "src/report",
    "src/qa",
    "src/utils",
    "templates",
    "reports/segments",
    "reports/stocks",
    "reports/comparisons",
    "reports/refresh",
    "reports/memos",
    "decisions/postmortems",
    "tests",
]

SKILLS = [
    "evidence-ingest",
    "segment-research",
    "company-universe",
    "segment-company-mapping",
    "stock-deep-dive",
    "compare-segments",
    "compare-stocks",
    "refresh-research",
    "quality-review",
    "memo-writer",
]

TEMPLATES = [
    "templates/segment_report.md",
    "templates/stock_report.md",
    "templates/evidence_card.md",
    "templates/comparison_matrix.md",
    "templates/investment_memo.md",
]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def collect_errors() -> list[str]:
    errors: list[str] = []

    for path in REQUIRED_FILES:
        if not (ROOT / path).is_file():
            errors.append(f"missing required file: {path}")

    for path in REQUIRED_DIRS:
        if not (ROOT / path).is_dir():
            errors.append(f"missing required directory: {path}")

    config = read_text(".codex/config.toml")
    for skill in SKILLS:
        skill_path = f".agents/skills/{skill}/SKILL.md"
        if not (ROOT / skill_path).is_file():
            errors.append(f"missing skill file: {skill_path}")
            continue
        content = read_text(skill_path)
        required_markers = [
            f"name: {skill}",
            "description:",
            "## When to use",
            "## Responsibilities",
            "## Out of scope",
            "## Guardrails",
            "## Quality checklist",
        ]
        for marker in required_markers:
            if marker not in content:
                errors.append(f"{skill_path} missing marker: {marker}")
        if f'path = ".agents/skills/{skill}"' not in config:
            errors.append(f".codex/config.toml missing skill path: {skill}")

    for template in TEMPLATES:
        content = read_text(template)
        for marker in ["Evidence Snapshot", "evidence_id", "TODO", "MISSING", "Evidence Map"]:
            if marker not in content:
                errors.append(f"{template} missing marker: {marker}")

    agents = read_text("AGENTS.md")
    for marker in [
        "Evidence is the source of truth",
        "Do not overwrite files in `data/raw/`",
        "Segment-company exposure is many-to-many",
        "Do not output direct buy/sell/hold instructions",
    ]:
        if marker not in agents:
            errors.append(f"AGENTS.md missing principle: {marker}")

    quality = read_text(".agents/skills/quality-review/SKILL.md")
    for marker in [
        "是否所有关键结论都有 `evidence_id` 或 `claim_id`",
        "是否混淆事实、估计、推断、观点",
        "是否把管理层表述当成事实",
        "是否把券商预测当成事实",
        "是否标记缺失数据",
        "是否列出反证和不确定性",
        "是否说明指标口径、单位和周期",
        "是否存在过期证据",
        "是否有更新日志要求",
        "是否避免买卖建议",
    ]:
        if marker not in quality:
            errors.append(f"quality-review checklist missing: {marker}")

    research_config = read_text("config/research_config.yaml")
    for marker in [
        "segment_company_exposure",
        "evidence_id_format",
        "claim_id_format",
        "p0_non_goals",
    ]:
        if marker not in research_config:
            errors.append(f"research_config.yaml missing: {marker}")

    evidence_header = read_text("data/manifests/evidence_manifest.csv").strip()
    if "evidence_id,source_type,source_name,title,publisher,publish_date" not in evidence_header:
        errors.append("evidence_manifest.csv header is incomplete")

    smoke = read_text("docs/logs/p0/2026-07-01_p0_smoke_test.md")
    if "result: PASS" not in smoke or "P0 Blocking Issues" not in smoke:
        errors.append("P0 smoke test does not record PASS and blocking issues")

    closeout = read_text("docs/logs/p0/2026-07-01_p0_closeout.md")
    if "status: PASS" not in closeout or "暂停确认" not in closeout:
        errors.append("P0 closeout does not record PASS and pause confirmation")

    return errors


def test_p0_acceptance() -> None:
    errors = collect_errors()
    assert not errors, "\n".join(errors)


if __name__ == "__main__":
    found_errors = collect_errors()
    if found_errors:
        for error in found_errors:
            print(f"FAIL: {error}")
        raise SystemExit(1)
    print("P0 acceptance: PASS")
