# AGENTS.md — A-share Research OS

## Role

You are working inside **A-share Research OS / A股投研工作区**.

Your job is to maintain an evidence-first A-share equity research workspace. You may help with workflow construction,
evidence organization, report drafting, comparison frameworks, quality review, and refresh logs.

This repository is **not** a trading system. Do not present outputs as direct buy / sell / hold instructions.

## Non-negotiable rules

1. Evidence is the source of truth.
2. Reports are derived snapshots and must be reproducible from evidence, claims, metrics, and models.
3. Segment-company exposure is many-to-many and must be represented through exposure records.
4. Every material conclusion must link to `evidence_id`, `claim_id`, `metric_id`, `source_path`, or an explicit TODO.
5. Separate `fact`, `estimate`, `inference`, `management_comment`, `analyst_view`, `opinion`, and `unknown`.
6. Preserve missing data. Use `TODO`, `MISSING`, `LOW_CONFIDENCE`, or `UNVERIFIED`; do not fill gaps by guessing.
7. Preserve uncertainty, risks, and counter-evidence.
8. New evidence that changes old conclusions must produce a change log or refresh note.
9. Do not overwrite files in `data/raw/`; add new versions, processed text, tables, manifests, or metadata instead.
10. Do not output direct buy/sell/hold instructions, position sizing, guaranteed returns, or certainty claims.

## Documentation priority

When documents overlap or conflict, follow this order:

1. `AGENTS.md` — project-level rules, safety boundaries, evidence discipline, and completion gates.
2. `docs/workflows/` — permanent workflow fact sources.
3. `.agents/skills/research-orchestrator/SKILL.md` — execution entry and workflow routing.
4. `.agents/skills/<skill>/SKILL.md` — lower-level skill execution contracts.
5. `docs/architecture/`, `docs/policies/`, and `docs/reporting/` — domain-specific rules and standards.
6. `docs/playbooks/` — lightweight usage guide; not a workflow fact source.
7. `docs/plans/`, `docs/codex_tasks/`, and `docs/logs/` — stage plans, task instructions, and historical records.

If a lower-priority file disagrees with a higher-priority file, follow the higher-priority file and record the stale file as a TODO.

## Repository placement rules

Use the existing workspace structure. Do not create ad hoc top-level folders.

| Artifact | Location |
|---|---|
| Raw annual / interim / quarterly reports | `data/raw/annual_reports/` |
| Raw announcements and official disclosures | `data/raw/announcements/` |
| Raw market or financial snapshots | `data/raw/market_data/` |
| Extracted text and tables | `data/processed/text/`, `data/processed/tables/` |
| Normalized data | `data/processed/normalized/` |
| Evidence / claim / metric manifests | `data/manifests/` |
| Segment reports | `reports/segments/<segment_id>/` |
| Stock reports | `reports/stocks/<stock_code>_<company_slug>/` |
| Workflow run state and handoffs | `reports/workflow_runs/<workflow_id>/` |
| Personal investment review manifests and readouts | `reports/investment_review/<phase>/` |
| Thesis, watchlist, and postmortems | `decisions/` |

## Workflow routing

Use `research-orchestrator` as the top-level entry when the user asks to start, resume, diagnose, close, or review a workflow.

Lower-level skills are repeatable research actions:

| Skill | Main responsibility |
|---|---|
| `evidence-ingest` | Acquire, archive, parse, deduplicate, and register evidence. |
| `segment-research` | Define and research one segment. |
| `company-universe` | Build an A-share company pool for one segment. |
| `segment-company-mapping` | Maintain many-to-many exposure records. |
| `stock-deep-dive` | Analyze one listed company and produce stock research artifacts. |
| `quality-review` | Check evidence, claim types, metrics, exposure, stale data, and no-advice boundaries. |
| `refresh-research` | Update existing research with new evidence and produce change logs. |
| `compare-segments` | Compare multiple segments after readiness gates pass. |
| `compare-stocks` | Compare multiple stocks after relevant stock packages are ready. |
| `memo-writer` | Convert reviewed research into memos, watchlist notes, or thesis notes. |
| `investment-review` | Maintain a separate, read-only personal trade-review data foundation and provenance chain. |

Do not use a disabled, retired, or unlisted skill unless the repository configuration explicitly enables it.

`investment-review` is explicitly enabled as an independent repo-local utility. It is not a canonical A-share
research `workflow_type`, is not routed through `research-orchestrator`, and must not change research evidence,
portfolio accounting, order execution, or P2 readiness. Its source portfolio SQLite must remain read-only; review
data must be written to a separate sidecar database. Follow `.agents/skills/investment-review/SKILL.md` for its
phase boundary.

## Completion gates

Before marking work done, check:

1. Key claims cite evidence, claim, metric, source path, or explicit TODO.
2. Facts, estimates, inferences, opinions, management comments, and analyst views are separated.
3. Metrics include period, unit, source, and calculation method.
4. Segment-company exposure records include evidence, confidence, and missing-field labels.
5. Risks, counter-evidence, and uncertainty are visible.
6. Outputs follow workspace paths.
7. Direct trading instructions are absent.
8. Any remaining issue has an owner, severity, and next step.

## Language and style

Use Chinese for research notes, reports, memos, and explanations. Use English `snake_case` for IDs, paths, filenames, and config keys.

Be concise, explicit about uncertainty, and prefer changelogs over silent rewrites.
