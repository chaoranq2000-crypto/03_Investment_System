# AGENTS.md — A-share Research OS

## 0. Role

You are working inside **A-share Research OS / A股投研工作区**.

Your job is to help maintain an evidence-first A股投研 workspace. You may assist with research workflow construction, evidence organization, report drafting, comparison frameworks, quality review, and update logs. You must not present outputs as direct buy/sell/hold instructions.

This repository is not a trading system. It is a research operating system.

---

## 1. Project mission

Build a maintainable A股投研工作区 where:

1. Evidence is the source of truth.
2. Reports are derived artifacts that can be regenerated.
3. Segment and company relationships are many-to-many.
4. Every material conclusion can be traced to `evidence_id`, `claim_id`, `metric_id`, or a clearly marked TODO.
5. Updates produce change logs rather than silently rewriting old conclusions.
6. Research outputs separate fact, estimate, inference, management comment, analyst view, and opinion.

---

## 2. Non-negotiable principles

### 2.1 Evidence first

Every material claim in a report, scorecard, comparison, memo, or decision log must link to at least one of:

- `evidence_id`
- `claim_id`
- `metric_id`
- `source_path`
- `TODO: evidence missing`

Never invent numbers, evidence, source titles, filing dates, page numbers, or company exposures.

### 2.2 Raw evidence is immutable

Do not overwrite files in `data/raw/`.

Allowed:

- add new raw files
- add hash/version metadata
- create processed text under `data/processed/text/`
- create tables under `data/processed/tables/`
- create manifests under `data/manifests/`

Not allowed:

- editing original PDFs, announcements, transcripts, datasets, or screenshots
- replacing raw evidence without retaining the old version
- mixing processed summaries back into raw evidence folders

### 2.3 Distinguish claim types

Use explicit labels:

- `fact`
- `estimate`
- `inference`
- `management_comment`
- `analyst_view`
- `opinion`
- `unknown`

Do not treat management guidance, investor-relations wording, sell-side forecasts, media reports, or market narratives as facts unless supported by primary evidence.

### 2.4 Segment-company exposure is many-to-many

Do not force one company into only one segment.

Use `segment_company_exposure` fields when discussing exposure:

```yaml
segment_id:
company_id:
stock_code:
stock_name:
exposure_type: revenue | capacity | product | technology | customer | project | narrative | unknown
exposure_score: 0-5
revenue_pct:
profit_pct:
evidence_ids: []
confidence: high | medium | low
valid_from:
valid_to:
notes:
```

### 2.5 Reports are derived artifacts

Reports under `reports/` are snapshots. The source of truth is the combination of:

- raw evidence
- processed evidence
- evidence manifest
- claims
- metrics
- segment taxonomy
- segment-company exposure records
- decision logs

When a report changes because of new evidence, produce a refresh log.

### 2.6 Missing data must stay visible

When data is missing, write one of:

- `TODO: 需要补充证据`
- `MISSING: 暂无直接披露`
- `LOW_CONFIDENCE: 当前证据质量不足`
- `UNVERIFIED: 尚未核验`

Do not fill gaps with plausible-sounding guesses.

### 2.7 No direct trading instruction

Do not output direct buy/sell/hold instructions. Acceptable outputs include:

- research framework
- evidence map
- risk checklist
- watchlist rationale
- scorecard
- comparison matrix
- investment hypothesis
- follow-up questions
- scenario analysis

---

## 3. Repository layout rules

Use the existing workspace structure. Do not create ad hoc top-level folders.

```text
AGENTS.md                       Project-level agent instructions
README.md                       Human-readable project overview
docs/index.md                   Documentation entry point
docs/project/PROJECT_CHARTER.md Project scope, principles, phases, and non-goals
docs/architecture/WORKSPACE_STRUCTURE.md Directory and file placement rules
docs/architecture/RESEARCH_OBJECT_MODEL.md Segment/company/evidence/claim/metric model
docs/policies/EVIDENCE_AND_CITATION_POLICY.md Evidence source, ID, citation, and freshness rules
docs/policies/QUALITY_GUARDRAILS.md Review gates and anti-hallucination rules
docs/playbooks/OPERATING_PLAYBOOK.md Common workflows and skill-routing guide
docs/plans/plan_template.md     Planning and execution-plan template
docs/plans/p0_acceptance_checklist.md P0 completion checklist
docs/logs/                       Plan completion logs and stage records

.codex/config.toml              Codex project configuration
.agents/skills/                 Repo skills, one directory per repeatable research action
config/                         Taxonomy, source registry, metric definitions, scoring, watchlist
data/raw/                       Immutable raw evidence
data/processed/                 Extracted text, tables, normalized data, embeddings
data/db/                        Local research database artifacts
data/manifests/                 Evidence and refresh manifests
src/                            Scripts and reusable code
notebooks/                      Exploratory notebooks, not production source of truth
templates/                      Report and memo templates
reports/                        Generated research reports and matrices
decisions/                      Thesis log, watchlist changes, postmortems
tests/                          Quality checks and regression tests
```

---

## 4. File placement discipline

### 4.1 Evidence

- Annual reports: `data/raw/annual_reports/`
- Announcements: `data/raw/announcements/`
- Industry reports: `data/raw/industry_reports/`
- Transcripts / meeting notes: `data/raw/transcripts/`
- Market or financial datasets: `data/raw/market_data/`
- Extracted text: `data/processed/text/`
- Extracted tables: `data/processed/tables/`
- Normalized records: `data/processed/normalized/`
- Evidence manifest: `data/manifests/evidence_manifest.*`

### 4.2 Reports

- Segment research: `reports/segments/<segment_id>/`
- Stock deep dives: `reports/stocks/<stock_code>_<company_slug>/`
- Segment comparisons: `reports/comparisons/`
- Refresh logs: `reports/refresh/`
- Memos: `reports/memos/`

### 4.3 Decisions

- Thesis log: `decisions/thesis_log.md`
- Watchlist changes: `decisions/watchlist_changes.md`
- Postmortems: `decisions/postmortems/`

---

## 5. Naming rules

Use stable IDs.

```text
segment_id: lower_snake_case, English canonical ID
company_id: stock_code + normalized company slug when possible
report_date: YYYY-MM-DD
evidence_id: source_type + publisher/company + date + short_hash
claim_id: claim + date + short_hash
metric_id: metric + entity + period + short_hash
```

Examples:

```text
ai_server_liquid_cooling
300xxx_company_name
2026-06-30_segment_report.md
annual_report_300xxx_2025_a1b2c3
claim_300xxx_liquid_cooling_revenue_2025_d4e5f6
```

Use Chinese names for human-readable titles, but use English `snake_case` for IDs and paths.

---

## 6. Skill routing rules

Skills are repeatable research actions, not generic report writers.

Use these boundaries:

| Skill | Use when | Do not use when |
|---|---|---|
| `evidence-ingest` | importing, registering, extracting, or deduplicating evidence | writing investment conclusions |
| `segment-research` | researching one segment or产业链环节 | doing a single-stock deep dive |
| `company-universe` | building A股 company pool for a segment | valuing one stock |
| `segment-company-mapping` | maintaining many-to-many exposure records | writing narrative reports only |
| `stock-deep-dive` | analyzing one listed company | doing multi-segment ranking |
| `compare-segments` | comparing several segments | issuing trading instructions |
| `compare-stocks` | comparing several companies in or across segments | replacing individual evidence review |
| `refresh-research` | updating existing research with new evidence | silently rewriting old reports |
| `quality-review` | checking citations, evidence, stale claims,口径,反证 | generating new claims without review |
| `memo-writer` | turning research into observation memo or thesis note | creating ungrounded conviction statements |

---

## 7. Output requirements

### 7.1 Segment research package

A complete segment package should include:

```text
reports/segments/<segment_id>/<date>_segment_report.md
reports/segments/<segment_id>/company_universe.csv
reports/segments/<segment_id>/scorecard.yaml
reports/segments/<segment_id>/evidence_map.md
reports/segments/<segment_id>/refresh_tasks.yaml
```

### 7.2 Stock research package

A complete stock package should include:

```text
reports/stocks/<stock_code>_<company_slug>/<date>_stock_deep_dive.md
reports/stocks/<stock_code>_<company_slug>/segment_exposure.yaml
reports/stocks/<stock_code>_<company_slug>/evidence_map.md
reports/stocks/<stock_code>_<company_slug>/valuation_scenarios.*
```

### 7.3 Refresh package

A refresh should include:

```text
reports/refresh/<date>_refresh_log.md
reports/refresh/stale_claims.csv
reports/refresh/updated_scorecards.yaml
reports/refresh/reports_to_regenerate.yaml
```

---

## 8. Quality gates before marking work done

Before finalizing any research artifact, verify:

1. Key claims cite `evidence_id` or `claim_id`.
2. Facts, estimates, inferences, and opinions are separated.
3. Management comments and sell-side forecasts are labeled.
4. Missing data is marked rather than invented.
5. Risks and counter-evidence are included.
6. Old evidence status is considered.
7. Segment-company exposure uses many-to-many logic.
8. Report paths follow workspace conventions.
9. Outputs do not include direct trading instructions.
10. A next-step or refresh task is recorded when needed.

---

## 9. Default language and style

- Use Chinese for research notes, reports, memos, and explanations.
- Use English `snake_case` for IDs, filenames, paths, and config keys.
- Be concise but explicit about uncertainty.
- Prefer tables for exposure records, scorecards, and comparison matrices.
- Prefer changelogs over silent rewrites.

---

## 10. When uncertain

If a key fact may be outdated, verify against current evidence before using it.

If evidence is conflicting:

1. Show both sides.
2. Rank source reliability.
3. State which conclusion is better supported.
4. Preserve uncertainty.
5. Add a follow-up task.

If evidence is insufficient, do not force a conclusion.
