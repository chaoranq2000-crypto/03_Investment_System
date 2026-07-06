# OLD_STOCK_SKILL_CLEANUP Readout

date: 2026-07-06
status: accepted_with_todos
scope: old_stock_skill_cleanup

## Scope Boundary

- Did not enter P2.
- Did not change research conclusions.
- Did not delete old skill directories, raw evidence, source data, or workflow run outputs.
- Did not restore `stock-research-analyst` or `stock-report-writer` as active routes.
- Kept `stock-deep-dive` as the only active stock deep-dive execution skill.

## Active Route Check

| Check | Result | Notes |
|---|---:|---|
| `.codex/config.toml` old stock skill enablement | PASS | Active config enables `.agents/skills/stock-deep-dive`; old stock skill names are absent. |
| Active `.agents/skills/` old directories | PASS | `.agents/skills/stock-research-analyst` and `.agents/skills/stock-report-writer` are absent. |
| Active workflow default route | PASS | Permanent workflow route remains `research-orchestrator -> evidence-ingest -> stock-deep-dive -> segment-company-mapping -> quality-review`. |
| P2 boundary | PASS | No comparison workflow or P2 task was started. |

## Reference Classification

| Reference type | Paths / examples | Classification | Action |
|---|---|---|---|
| active routing | `.codex/config.toml`; `docs/workflows/RESEARCH_WORKFLOW.md`; `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md`; `.agents/skills/research-orchestrator/references/skill_routing_matrix.md` | active routing | No old stock skill route found. |
| active workflow note | `docs/workflows/README.md`; `docs/workflows/STOCK_REPORT_PRODUCTION_WORKFLOW.md`; `docs/meta/DOC_OWNERSHIP_MATRIX.md` | retired / merged note | Updated wording to say old split names are merged into `stock-deep-dive` and are not default routes. |
| inactive snippet | `.codex/config.stock_report_quality_upgrade.snippet.toml` | inactive snippet | Replaced old enablement blocks with a deprecated compatibility note. |
| historical workflow run output | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/*` | historical report / readout | Left unchanged per boundary. |
| historical plan/readout | `docs/plans/DOCS_AND_AGENTS_CLEANUP_PLAN.md`; `reports/p1_6/DOCS_AGENTS_CLEANUP_READOUT.md` | retired / pending-merge note | Left as historical records; this readout supersedes the open cleanup TODO. |
| project-learning snapshots | `docs/references/project_learning/deep_dives/.agents/skills/stock-research-analyst/*`; `docs/references/project_learning/deep_dives/.agents/skills/stock-report-writer/*`; project-learning indexes | inactive snippet / historical learning reference | Read and extracted rules; left unchanged because they are learning artifacts, not active skills. |
| tests and merge validator | `tests/test_stock_deep_dive_skill_merge.py`; `.agents/skills/stock-deep-dive/scripts/validate_stock_deep_dive_merge.py` | test compatibility reference | Updated to verify migrated rules and deprecated snippet state. |

## Old Directory Inspection

Active old skill directories were not present under `.agents/skills/`.

Learning snapshots were present and reviewed:

| Snapshot area | Files checked | Useful content |
|---|---:|---|
| `stock-research-analyst` | 6 | Analysis pack contract, business breakdown, forecast/valuation, market/sentiment/event, analysis pack template. |
| `stock-report-writer` | 3 | Writer boundary, sample-style report structure, evidence-light wording, report template. |

## Migration Result

| Source content | Destination | Status |
|---|---|---|
| Analyst must consume reviewed claims/metrics and not ingest evidence | `.agents/skills/stock-deep-dive/references/legacy_stock_skill_rules.md`; existing `data_layer_pack_consumption.md` | migrated |
| `stock_analysis_pack.yaml` as single report upstream | `legacy_stock_skill_rules.md`; `analysis_pack_contract.md`; `stock-deep-dive/SKILL.md` must-read list | migrated |
| Business-line and exposure guardrails | existing `business_breakdown_contract.md`; `legacy_stock_skill_rules.md` | migrated / not_needed_duplicate |
| Forecast, valuation, peer, scenario and no target-price rules | existing `forecast_valuation_contract.md`; `legacy_stock_skill_rules.md` | migrated / not_needed_duplicate |
| Technical, sentiment and event fields must be dated and clue-only when weak | existing `market_sentiment_event_contract.md`; `legacy_stock_skill_rules.md` | migrated / not_needed_duplicate |
| Writer is analysis-pack-to-narrative only | `report_style_guide.md`; `legacy_stock_skill_rules.md` | migrated |
| Section-level conclusion plus evidence, driver and risk/counter-evidence | `report_style_guide.md`; `legacy_stock_skill_rules.md` | migrated |
| Evidence-light wording for weak support | `report_style_guide.md`; `legacy_stock_skill_rules.md` | migrated |
| Separate old skill route and old writer handoff | `legacy_stock_skill_rules.md` `Not Needed After Merge` | not_needed_retired |

## Files Changed

| File | Change |
|---|---|
| `.agents/skills/stock-deep-dive/references/legacy_stock_skill_rules.md` | Added migrated analyst/writer rules and explicit not-needed list. |
| `.agents/skills/stock-deep-dive/SKILL.md` | Added `legacy_stock_skill_rules.md` to SDD-3 and must-read references. |
| `.agents/skills/stock-deep-dive/references/report_style_guide.md` | Added writer boundary: translate pack to narrative, do not invent or hide gaps. |
| `.codex/config.stock_report_quality_upgrade.snippet.toml` | Deprecated snippet and removed active skill config blocks. |
| `.agents/skills/stock-deep-dive/scripts/validate_stock_deep_dive_merge.py` | Extended merge validation to cover migrated rules and snippet retirement. |
| `tests/test_stock_deep_dive_skill_merge.py` | Extended targeted compatibility tests. |
| `docs/workflows/README.md` | Updated old skill wording from pending merge to merged reference. |
| `docs/workflows/STOCK_REPORT_PRODUCTION_WORKFLOW.md` | Updated old skill wording from pending merge to merged reference. |
| `docs/meta/DOC_OWNERSHIP_MATRIX.md` | Updated old skill status to `retired_after_merge_review`. |

## Delete / Archive Decision

delete_ready: false

Reason:

- Active old skill directories do not exist under `.agents/skills/`, so there is no active skill directory to delete.
- Remaining old-name directories are project-learning snapshots under `docs/references/project_learning/deep_dives/`; they are not active routes.
- Historical workflow outputs still record the skill names as provenance and must not be edited for this cleanup.
- Generated learning indexes still reference old paths as historical source entries; changing them would be a separate project-learning index refresh, not a stock skill route cleanup.

Recommended state:

```yaml
old_stock_skill_active_route: false
old_stock_skill_content_migrated: true
old_stock_skill_delete_ready: false
archive_preferred_for_learning_snapshots: true
delete_decision_file_created: false
```

No `reports/p1_6/OLD_STOCK_SKILL_DELETE_DECISION.md` was created because this pass does not recommend deletion.

## Checks

| Check | Result | Command |
|---|---:|---|
| stock-deep-dive merge validator | PASS | `conda run -p .\.conda\investment-system python .\.agents\skills\stock-deep-dive\scripts\validate_stock_deep_dive_merge.py` |
| targeted pytest | PASS | `conda run -p .\.conda\investment-system pytest -q tests/test_stock_deep_dive_skill_merge.py tests/test_stock_report_writer.py tests/test_stock_analysis_pack_builder.py tests/test_stock_report_quality_review.py` |
| `git diff --check` | PASS | whitespace check passed; only Git LF-to-CRLF warnings were printed |
| full pytest | PASS | `conda run -p .\.conda\investment-system pytest -q` -> `109 passed, 2 skipped` |

## Remaining TODOs

| Severity | TODO | Owner | Next step |
|---|---|---|---|
| low | Project-learning indexes still list historical old skill source paths. | Codex / user | Leave as historical learning references unless a separate project-learning index refresh is requested. |
